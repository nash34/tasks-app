from flask import Flask, render_template, request, redirect, url_for, session, flash, send_from_directory
from flask_session import Session
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import sqlite3
import os
from datetime import datetime, timedelta
import json
import logging

app = Flask(__name__)
app.secret_key = 'super_secret_key'  # Change in production
app.config['SESSION_TYPE'] = 'filesystem'
app.config['UPLOAD_FOLDER'] = os.path.join('static', 'uploads')
Session(app)

# Setup logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Ensure upload folder exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Database connection
def get_db():
    conn = sqlite3.connect('home.db')
    conn.row_factory = sqlite3.Row
    return conn

# Init DB
def init_db():
    with get_db() as db:
        db.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                type TEXT NOT NULL,  -- 'parent' or 'kid'
                passcode TEXT NOT NULL,
                profile_pic TEXT
            )
        ''')
        db.execute('''
            CREATE TABLE IF NOT EXISTS task_templates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                category TEXT NOT NULL,  -- 'morning', 'evening', 'night'
                order_num INTEGER DEFAULT 0
            )
        ''')
        db.execute('''
            CREATE TABLE IF NOT EXISTS task_instances (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_template_id INTEGER,
                user_id INTEGER,
                date TEXT NOT NULL,  -- YYYY-MM-DD
                done INTEGER DEFAULT 0,
                starred INTEGER DEFAULT 0,
                FOREIGN KEY(task_template_id) REFERENCES task_templates(id) ON DELETE CASCADE,
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        ''')
        # Add default parent user for testing if none exist (no hardcoded tasks)
        cursor = db.execute('SELECT COUNT(*) FROM users')
        if cursor.fetchone()[0] == 0:
            hashed = generate_password_hash('1234')
            db.execute('INSERT INTO users (name, type, passcode, profile_pic) VALUES (?, ?, ?, ?)',
                       ('Test Parent', 'parent', hashed, 'default.png'))
        # Add order_num column if not exists
        try:
            db.execute('ALTER TABLE task_templates ADD COLUMN order_num INTEGER DEFAULT 0')
        except sqlite3.OperationalError:
            pass  # Column already exists
        db.commit()

init_db()

# Helper: Get task instance or create
def get_or_create_task_instance(task_id, user_id, date):
    with get_db() as db:
        instance = db.execute('SELECT * FROM task_instances WHERE task_template_id = ? AND user_id = ? AND date = ?',
                              (task_id, user_id, date)).fetchone()
        if not instance:
            db.execute('INSERT INTO task_instances (task_template_id, user_id, date) VALUES (?, ?, ?)',
                       (task_id, user_id, date))
            db.commit()
            instance = db.execute('SELECT * FROM task_instances WHERE task_template_id = ? AND user_id = ? AND date = ?',
                                  (task_id, user_id, date)).fetchone()
        return instance

# Landing page
@app.route('/', methods=['GET'])
def landing():
    with get_db() as db:
        kids = db.execute("SELECT * FROM users WHERE type = 'kid'").fetchall()
        parents = db.execute("SELECT * FROM users WHERE type = 'parent'").fetchall()
        
        today_str = datetime.now().strftime('%Y-%m-%d')
        yesterday_str = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
        kids_list = []
        for kid in kids:
            kid_dict = dict(kid)
            today = datetime.now()
            month_start = today.replace(day=1).strftime('%Y-%m-%d')
            next_month = today.replace(day=1) + timedelta(days=32)
            month_end = (next_month.replace(day=1) - timedelta(days=1)).strftime('%Y-%m-%d')
            stars_month = db.execute('SELECT COUNT(*) FROM task_instances WHERE user_id = ? AND starred = 1 AND date BETWEEN ? AND ?',
                                    (kid['id'], month_start, month_end)).fetchone()[0]
            stars_last_two_days = db.execute('SELECT COUNT(*) FROM task_instances WHERE user_id = ? AND starred = 1 AND date IN (?, ?)',
                                            (kid['id'], yesterday_str, today_str)).fetchone()[0]
            kid_dict['stars_month'] = stars_month
            kid_dict['stars_last_two_days'] = stars_last_two_days
            kids_list.append(kid_dict)
        
        parents_list = [dict(parent) for parent in parents]
        
    return render_template('landing.html', kids=kids_list, parents=parents_list)

# Login
@app.route('/login/<int:user_id>', methods=['GET', 'POST'])
def login(user_id):
    if request.method == 'POST':
        passcode = request.form.get('passcode')
        with get_db() as db:
            user = db.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
            if user and check_password_hash(user['passcode'], passcode):
                session['user_id'] = user['id']
                session['type'] = user['type']
                logger.debug(f"User {user['name']} logged in. Session: {session}")
                if user['type'] == 'kid':
                    session['view_user_id'] = user['id']
                    return redirect(url_for('home'))
                else:
                    return redirect(url_for('kids'))
            else:
                flash('Invalid passcode.')
    return render_template('login.html', user_id=user_id)

# Select kid (for parents)
@app.route('/kids')
def kids():
    if 'user_id' not in session or session['type'] != 'parent':
        logger.debug(f"Access to /kids denied. Session: {session}")
        return redirect(url_for('landing'))
    with get_db() as db:
        kids = db.execute("SELECT * FROM users WHERE type = 'kid'").fetchall()
    return render_template('kids.html', kids=kids)

@app.route('/set_view/<int:kid_id>')
def set_view(kid_id):
    if 'user_id' not in session or session['type'] != 'parent':
        logger.debug(f"Access to /set_view denied. Session: {session}")
        return redirect(url_for('landing'))
    session['view_user_id'] = kid_id
    logger.debug(f"Set view_user_id to {kid_id}. Session: {session}")
    return redirect(url_for('home'))

# Home page
@app.route('/home', methods=['GET', 'POST'])
def home():
    if 'user_id' not in session:
        logger.debug("Access to /home denied: No user_id in session")
        return redirect(url_for('landing'))
    view_user_id = session.get('view_user_id')
    if not view_user_id and session['type'] == 'parent':
        logger.debug("Redirecting to /kids: No view_user_id for parent")
        return redirect(url_for('kids'))
    
    today_str = datetime.now().strftime('%Y-%m-%d')
    yesterday_str = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
    tomorrow_str = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')
    
    date = request.args.get('date', today_str)
    try:
        date_obj = datetime.strptime(date, '%Y-%m-%d')
    except:
        date = today_str
        date_obj = datetime.now()
    
    prev_date = (date_obj - timedelta(days=1)).strftime('%Y-%m-%d')
    next_date = (date_obj + timedelta(days=1)).strftime('%Y-%m-%d')
    
    # Date displays with labels
    current_display = date + ' (Today)' if date == today_str else date
    prev_display = '&lt; Yesterday' if prev_date == yesterday_str else '&lt; ' + prev_date
    next_display = 'Tomorrow &gt;' if next_date == tomorrow_str else next_date + ' &gt;'
    
    is_parent = session['type'] == 'parent'
    is_kid = session['type'] == 'kid'
    is_editable = True
    if is_kid:
        is_editable = date in [today_str, yesterday_str]
    
    with get_db() as db:
        templates = db.execute('SELECT * FROM task_templates ORDER BY category, order_num').fetchall()
        if not templates:
            logger.debug("No task templates found in database")
            return render_template('home.html', date=date, prev_date=prev_date, next_date=next_date,
                                   current_display=current_display, prev_display=prev_display, next_display=next_display,
                                   categories={}, is_parent=is_parent, is_editable=is_editable, no_data=True)
    
    categories = {'morning': [], 'evening': [], 'night': []}
    for t in templates:
        instance = get_or_create_task_instance(t['id'], view_user_id, date)
        categories[t['category']].append({
            'template': t,
            'instance': instance
        })
    
    if request.method == 'POST':
        action = request.form.get('action')
        if action is None:
            flash('Invalid action.')
            return redirect(url_for('home', date=date))
        with get_db() as db:
            if action == 'toggle_done' and (is_parent or is_editable):
                instance_id = request.form.get('instance_id')
                if instance_id:
                    db.execute('UPDATE task_instances SET done = NOT done WHERE id = ?', (instance_id,))
            elif action == 'toggle_star' and is_parent:
                instance_id = request.form.get('instance_id')
                if instance_id:
                    db.execute('UPDATE task_instances SET starred = NOT starred WHERE id = ?', (instance_id,))
            elif action == 'star_all' and is_parent:
                for cat in categories.values():
                    for task in cat:
                        if task['instance']['done']:
                            db.execute('UPDATE task_instances SET starred = 1 WHERE id = ?', (task['instance']['id'],))
            db.commit()
        logger.debug(f"Action {action} performed")
        return redirect(url_for('home', date=date))
    
    return render_template('home.html', date=date, prev_date=prev_date, next_date=next_date,
                          current_display=current_display, prev_display=prev_display, next_display=next_display,
                          categories=categories, is_parent=is_parent, is_editable=is_editable, no_data=False)

# History
@app.route('/history')
def history():
    if 'user_id' not in session:
        logger.debug("Access to /history denied: No user_id in session")
        return redirect(url_for('landing'))
    view_user_id = session.get('view_user_id')
    if not view_user_id:
        logger.debug("Redirecting to /kids: No view_user_id")
        return redirect(url_for('kids'))
    
    with get_db() as db:
        # Weekly: last 8 weeks
        weeks = []
        week_labels = []
        today = datetime.now()
        for i in range(8):
            start = (today - timedelta(days=7*(i+1) + today.weekday())).strftime('%Y-%m-%d')
            end = (today - timedelta(days=7*i + today.weekday() + 1)).strftime('%Y-%m-%d')
            count = db.execute('SELECT COUNT(*) FROM task_instances WHERE user_id = ? AND date BETWEEN ? AND ? AND starred = 1',
                               (view_user_id, start, end)).fetchone()[0]
            weeks.append(count)
            week_labels.append(f'Week {8-i}')
        weeks.reverse()
        week_labels.reverse()
        
        # Monthly: last 12 months
        months = []
        month_labels = []
        for i in range(12):
            month_start = (today.replace(day=1) - timedelta(days=30*i)).replace(day=1).strftime('%Y-%m-%d')
            next_month = (today.replace(day=1) - timedelta(days=30*(i-1))) if i > 0 else today + timedelta(days=1)
            month_end = (next_month.replace(day=1) - timedelta(days=1)).strftime('%Y-%m-%d')
            count = db.execute('SELECT COUNT(*) FROM task_instances WHERE user_id = ? AND date BETWEEN ? AND ? AND starred = 1',
                               (view_user_id, month_start, month_end)).fetchone()[0]
            months.append(count)
            month_labels.append(month_start[:7])  # YYYY-MM
        months.reverse()
        month_labels.reverse()
    
    return render_template('history.html', week_data=json.dumps(weeks), week_labels=json.dumps(week_labels),
                           month_data=json.dumps(months), month_labels=json.dumps(month_labels))

# Settings
@app.route('/settings', methods=['GET', 'POST'])
def settings():
    if 'user_id' not in session:
        logger.debug("Access to /settings denied: No user_id in session")
        return redirect(url_for('landing'))
    user_id = session['user_id']
    is_parent = session['type'] == 'parent'
    
    if request.method == 'POST':
        action = request.form.get('action')
        if action is None:
            flash('Invalid action.')
            return redirect(url_for('settings'))
        with get_db() as db:
            if action == 'update_passcode':
                new_passcode = request.form.get('new_passcode')
                if new_passcode and len(new_passcode) == 4 and new_passcode.isdigit():
                    hashed = generate_password_hash(new_passcode)
                    db.execute('UPDATE users SET passcode = ? WHERE id = ?', (hashed, user_id))
                    db.commit()
                    flash('Passcode updated.')
                else:
                    flash('Passcode must be 4 digits.')
            elif action == 'reset_passcode' and is_parent:
                target_id = request.form.get('target_id')
                new_passcode = request.form.get('new_passcode')
                if target_id and new_passcode and len(new_passcode) == 4 and new_passcode.isdigit():
                    hashed = generate_password_hash(new_passcode)
                    db.execute('UPDATE users SET passcode = ? WHERE id = ?', (hashed, target_id))
                    db.commit()
                    flash('Passcode reset.')
                else:
                    flash('Passcode must be 4 digits.')
            elif action == 'update_pic':
                if 'profile_pic' in request.files:
                    file = request.files['profile_pic']
                    if file.filename:
                        filename = secure_filename(file.filename)
                        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                        db.execute('UPDATE users SET passcode = ? WHERE id = ?', (filename, user_id))
                        db.commit()
                    flash('Profile picture updated.')
            elif action == 'add_user' and is_parent:
                name = request.form.get('name')
                user_type = request.form.get('type')
                passcode = request.form.get('passcode')
                if name and user_type and passcode and len(passcode) == 4 and passcode.isdigit():
                    hashed = generate_password_hash(passcode)
                    profile_pic = 'default.png'
                    if 'profile_pic' in request.files:
                        file = request.files['profile_pic']
                        if file.filename:
                            filename = secure_filename(file.filename)
                            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                            profile_pic = filename
                    db.execute('INSERT INTO users (name, type, passcode, profile_pic) VALUES (?, ?, ?, ?)',
                               (name, user_type, hashed, profile_pic))
                    db.commit()
                    flash('User added successfully.')
                else:
                    flash('Invalid input for adding user.')
            elif action == 'delete_user' and is_parent:
                target_id = request.form.get('target_id')
                if target_id and int(target_id) != user_id:
                    # Delete task_instances first (though CASCADE should handle)
                    db.execute('DELETE FROM task_instances WHERE user_id = ?', (target_id,))
                    db.execute('DELETE FROM users WHERE id = ?', (target_id,))
                    db.commit()
                    flash('User deleted successfully.')
                else:
                    flash('Cannot delete your own account.')
            elif action == 'add_task' and is_parent:
                name = request.form.get('task_name')
                category = request.form.get('category')
                if name and category in ['morning', 'evening', 'night']:
                    # Set order_num to max +1 in category
                    max_order = db.execute('SELECT MAX(order_num) FROM task_templates WHERE category = ?', (category,)).fetchone()[0] or 0
                    order_num = max_order + 1
                    db.execute('INSERT INTO task_templates (name, category, order_num) VALUES (?, ?, ?)', (name, category, order_num))
                    db.commit()
                    flash('Task added successfully.')
                else:
                    flash('Invalid task name or category.')
            elif action == 'delete_task' and is_parent:
                task_id = request.form.get('task_id')
                if task_id:
                    category = db.execute('SELECT category FROM task_templates WHERE id = ?', (task_id,)).fetchone()['category']
                    db.execute('DELETE FROM task_templates WHERE id = ?', (task_id,))
                    # Reorder remaining tasks in category
                    remaining = db.execute('SELECT id FROM task_templates WHERE category = ? ORDER BY order_num', (category,)).fetchall()
                    for idx, task in enumerate(remaining, 1):
                        db.execute('UPDATE task_templates SET order_num = ? WHERE id = ?', (idx, task['id']))
                    db.commit()
                    flash('Task deleted successfully.')
                else:
                    flash('Invalid task ID.')
            elif action == 'move_task_up' and is_parent:
                task_id = request.form.get('task_id')
                if task_id:
                    task = db.execute('SELECT category, order_num FROM task_templates WHERE id = ?', (task_id,)).fetchone()
                    if task and task['order_num'] > 1:
                        db.execute('UPDATE task_templates SET order_num = order_num + 1 WHERE category = ? AND order_num = ?', (task['category'], task['order_num'] - 1))
                        db.execute('UPDATE task_templates SET order_num = order_num - 1 WHERE id = ?', (task_id,))
                        db.commit()
                        flash('Task moved up.')
            elif action == 'move_task_down' and is_parent:
                task_id = request.form.get('task_id')
                if task_id:
                    task = db.execute('SELECT category, order_num FROM task_templates WHERE id = ?', (task_id,)).fetchone()
                    max_order = db.execute('SELECT MAX(order_num) FROM task_templates WHERE category = ?', (task['category'],)).fetchone()[0]
                    if task and task['order_num'] < max_order:
                        db.execute('UPDATE task_templates SET order_num = order_num - 1 WHERE category = ? AND order_num = ?', (task['category'], task['order_num'] + 1))
                        db.execute('UPDATE task_templates SET order_num = order_num + 1 WHERE id = ?', (task_id,))
                        db.commit()
                        flash('Task moved down.')
    
    with get_db() as db:
        users = db.execute('SELECT * FROM users WHERE id != ?', (user_id,)).fetchall() if is_parent else None
        tasks = db.execute('SELECT * FROM task_templates ORDER BY category, order_num').fetchall() if is_parent else None
    return render_template('settings.html', is_parent=is_parent, users=users, tasks=tasks)

# Logout
@app.route('/logout')
def logout():
    logger.debug(f"User logged out. Session: {session}")
    session.clear()
    return redirect(url_for('landing'))

# Serve uploads
@app.route('/uploads/<filename>')
def uploads(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

if __name__ == '__main__':
    app.run(debug=True)
