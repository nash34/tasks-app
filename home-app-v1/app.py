from flask import Flask, request, redirect, url_for, render_template, session
from flask_session import Session
import sqlite3
from datetime import datetime, timedelta
import os
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = 'super_secret_key'
app.config['SESSION_TYPE'] = 'filesystem'
Session(app)
app.config['UPLOAD_FOLDER'] = 'static/uploads'
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

def get_db():
    conn = sqlite3.connect('users.db')
    conn.row_factory = sqlite3.Row
    return conn

# Initialize database tables
with get_db() as conn:
    conn.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        type TEXT NOT NULL,
        passcode TEXT NOT NULL,
        profile_pic INTEGER DEFAULT 0
    )''')
    conn.execute('''CREATE TABLE IF NOT EXISTS tasks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        category TEXT NOT NULL
    )''')
    conn.execute('''CREATE TABLE IF NOT EXISTS task_completions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        task_id INTEGER,
        date DATE,
        completed INTEGER DEFAULT 0,
        starred INTEGER DEFAULT 0
    )''')

@app.before_request
def update_last_activity():
    if 'user_id' in session:
        if datetime.now().timestamp() - session.get('last_activity', 0) > 5 * 60:
            session.clear()
            return redirect(url_for('landing'))
        session['last_activity'] = datetime.now().timestamp()

@app.route('/')
def landing():
    with get_db() as conn:
        users = conn.execute('SELECT * FROM users').fetchall()
    return render_template('landing.html', users=users)

@app.route('/login', methods=['POST'])
def login():
    user_id = request.form['user_id']
    passcode = request.form['passcode']
    with get_db() as conn:
        user = conn.execute('SELECT * FROM users WHERE id = ? AND passcode = ?', (user_id, passcode)).fetchone()
    if user:
        session['user_id'] = user['id']
        session['type'] = user['type']
        session['name'] = user['name']
        session['last_activity'] = datetime.now().timestamp()
        if user['type'] == 'kid':
            return redirect(url_for('home'))
        else:
            return redirect(url_for('kids'))
    return redirect(url_for('landing'))

@app.route('/kids')
def kids():
    if 'user_id' not in session or session['type'] != 'parent':
        return redirect(url_for('landing'))
    with get_db() as conn:
        kids = conn.execute('SELECT * FROM users WHERE type = "kid"').fetchall()
    return render_template('kids.html', kids=kids)

@app.route('/home')
def home():
    if 'user_id' not in session:
        return redirect(url_for('landing'))
    user_id = request.args.get('user_id', session['user_id'])
    if session['type'] != 'parent' and int(user_id) != session['user_id']:
        return redirect(url_for('home'))
    date = request.args.get('date', datetime.now().strftime('%Y-%m-%d'))
    current_date = datetime.strptime(date, '%Y-%m-%d')
    prev_date = (current_date - timedelta(days=1)).strftime('%Y-%m-%d')
    next_date = (current_date + timedelta(days=1)).strftime('%Y-%m-%d')
    with get_db() as conn:
        tasks = conn.execute('SELECT * FROM tasks').fetchall()
        completions = conn.execute('SELECT * FROM task_completions WHERE user_id = ? AND date = ?', (user_id, date)).fetchall()
        completions = {c['task_id']: c for c in completions}
    is_parent = session['type'] == 'parent'
    today = datetime.now().strftime('%Y-%m-%d')
    yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
    can_mark = is_parent or (date in (today, yesterday) and int(user_id) == session['user_id'])
    return render_template('home.html', date=date, prev_date=prev_date, next_date=next_date, tasks=tasks, completions=completions, can_mark=can_mark, is_parent=is_parent, viewed_user_id=user_id)

@app.route('/mark_task', methods=['POST'])
def mark_task():
    if 'user_id' not in session:
        return redirect(url_for('landing'))
    task_id = request.form['task_id']
    date = request.form['date']
    completed = 1 if 'completed' in request.form else 0
    target_user_id = request.form.get('user_id', session['user_id'])
    is_parent = session['type'] == 'parent'
    if not is_parent and int(target_user_id) != session['user_id']:
        return redirect(url_for('landing'))
    if not is_parent:
        today = datetime.now().strftime('%Y-%m-%d')
        yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
        if date not in (today, yesterday):
            return redirect(url_for('home'))
    with get_db() as conn:
        existing = conn.execute('SELECT starred FROM task_completions WHERE user_id = ? AND task_id = ? AND date = ?', (target_user_id, task_id, date)).fetchone()
        starred = existing['starred'] if existing else 0
        conn.execute('INSERT OR REPLACE INTO task_completions (user_id, task_id, date, completed, starred) VALUES (?, ?, ?, ?, ?)', (target_user_id, task_id, date, completed, starred))
        conn.commit()
    return redirect(url_for('home', date=date, user_id=target_user_id))

@app.route('/star_task', methods=['POST'])
def star_task():
    if 'user_id' not in session or session['type'] != 'parent':
        return redirect(url_for('landing'))
    task_id = request.form['task_id']
    date = request.form['date']
    starred = request.form['starred']
    target_user_id = request.form.get('user_id', session['user_id'])
    with get_db() as conn:
        existing = conn.execute('SELECT completed FROM task_completions WHERE user_id = ? AND task_id = ? AND date = ?', (target_user_id, task_id, date)).fetchone()
        completed = existing['completed'] if existing else 0
        conn.execute('INSERT OR REPLACE INTO task_completions (user_id, task_id, date, completed, starred) VALUES (?, ?, ?, ?, ?)', (target_user_id, task_id, date, completed, starred))
        conn.commit()
    return redirect(url_for('home', date=date, user_id=target_user_id))

@app.route('/star_all', methods=['POST'])
def star_all():
    if 'user_id' not in session or session['type'] != 'parent':
        return redirect(url_for('landing'))
    date = request.form['date']
    target_user_id = request.form.get('user_id', session['user_id'])
    with get_db() as conn:
        conn.execute('UPDATE task_completions SET starred = 1 WHERE user_id = ? AND date = ? AND completed = 1', (target_user_id, date))
        conn.commit()
    return redirect(url_for('home', date=date, user_id=target_user_id))

@app.route('/history')
def history():
    if 'user_id' not in session:
        return redirect(url_for('landing'))
    user_id = request.args.get('user_id', session['user_id'])
    is_parent = session['type'] == 'parent'
    if not is_parent and int(user_id) != session['user_id']:
        return redirect(url_for('history'))
    with get_db() as conn:
        weeks = conn.execute('SELECT strftime("%Y-%W", date) as week, COUNT(*) as stars FROM task_completions WHERE user_id = ? AND starred = 1 GROUP BY week ORDER BY week DESC LIMIT 4', (user_id,)).fetchall()
        months = conn.execute('SELECT strftime("%Y-%m", date) as month, COUNT(*) as stars FROM task_completions WHERE user_id = ? AND starred = 1 GROUP BY month ORDER BY month DESC LIMIT 12', (user_id,)).fetchall()
    return render_template('history.html', weeks=weeks, months=months)

@app.route('/settings')
def settings():
    if 'user_id' not in session:
        return redirect(url_for('landing'))
    is_parent = session['type'] == 'parent'
    with get_db() as conn:
        users = conn.execute('SELECT * FROM users').fetchall()
        tasks = conn.execute('SELECT * FROM tasks').fetchall()
    return render_template('settings.html', is_parent=is_parent, users=users, tasks=tasks)

@app.route('/add_user', methods=['POST'])
def add_user():
    if 'user_id' not in session or session['type'] != 'parent':
        return redirect(url_for('landing'))
    name = request.form['name']
    passcode = request.form['passcode']
    user_type = request.form['type']
    with get_db() as conn:
        conn.execute('INSERT INTO users (name, type, passcode) VALUES (?, ?, ?)', (name, user_type, passcode))
        conn.commit()
    return redirect(url_for('settings'))

@app.route('/delete_user', methods=['POST'])
def delete_user():
    if 'user_id' not in session or session['type'] != 'parent':
        return redirect(url_for('landing'))
    user_id = request.form['user_id']
    with get_db() as conn:
        conn.execute('DELETE FROM users WHERE id = ?', (user_id,))
        conn.execute('DELETE FROM task_completions WHERE user_id = ?', (user_id,))
        conn.commit()
    return redirect(url_for('settings'))

@app.route('/reset_passcode', methods=['POST'])
def reset_passcode():
    if 'user_id' not in session or session['type'] != 'parent':
        return redirect(url_for('landing'))
    user_id = request.form['user_id']
    new_passcode = request.form['new_passcode']
    with get_db() as conn:
        conn.execute('UPDATE users SET passcode = ? WHERE id = ?', (new_passcode, user_id))
        conn.commit()
    return redirect(url_for('settings'))

@app.route('/update_passcode', methods=['POST'])
def update_passcode():
    if 'user_id' not in session:
        return redirect(url_for('landing'))
    old_passcode = request.form['old_passcode']
    new_passcode = request.form['new_passcode']
    with get_db() as conn:
        user = conn.execute('SELECT * FROM users WHERE id = ? AND passcode = ?', (session['user_id'], old_passcode)).fetchone()
        if user:
            conn.execute('UPDATE users SET passcode = ? WHERE id = ?', (new_passcode, session['user_id']))
            conn.commit()
    return redirect(url_for('settings'))

@app.route('/add_task', methods=['POST'])
def add_task():
    if 'user_id' not in session or session['type'] != 'parent':
        return redirect(url_for('landing'))
    name = request.form['name']
    category = request.form['category']
    with get_db() as conn:
        conn.execute('INSERT INTO tasks (name, category) VALUES (?, ?)', (name, category))
        conn.commit()
    return redirect(url_for('settings'))

@app.route('/delete_task', methods=['POST'])
def delete_task():
    if 'user_id' not in session or session['type'] != 'parent':
        return redirect(url_for('landing'))
    task_id = request.form['task_id']
    with get_db() as conn:
        conn.execute('DELETE FROM tasks WHERE id = ?', (task_id,))
        conn.execute('DELETE FROM task_completions WHERE task_id = ?', (task_id,))
        conn.commit()
    return redirect(url_for('settings'))

@app.route('/edit_task', methods=['POST'])
def edit_task():
    if 'user_id' not in session or session['type'] != 'parent':
        return redirect(url_for('landing'))
    task_id = request.form['task_id']
    new_name = request.form['new_name']
    with get_db() as conn:
        conn.execute('UPDATE tasks SET name = ? WHERE id = ?', (new_name, task_id))
        conn.commit()
    return redirect(url_for('settings'))

@app.route('/upload_pic', methods=['POST'])
def upload_pic():
    if 'user_id' not in session:
        return redirect(url_for('landing'))
    file = request.files['file']
    if file:
        filename = secure_filename(str(session['user_id']) + '.png')
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        with get_db() as conn:
            conn.execute('UPDATE users SET profile_pic = 1 WHERE id = ?', (session['user_id'],))
            conn.commit()
    return redirect(url_for('settings'))

if __name__ == '__main__':
    app.run(debug=True)
