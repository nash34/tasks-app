function showLogin(id) {
    document.getElementById('login-form-' + id).style.display = 'block';
}

function mark(checkbox, taskId, date, userId) {
    var form = document.createElement('form');
    form.method = 'post';
    form.action = '/mark_task';
    var h1 = document.createElement('input');
    h1.type = 'hidden';
    h1.name = 'task_id';
    h1.value = taskId;
    form.appendChild(h1);
    var h2 = document.createElement('input');
    h2.type = 'hidden';
    h2.name = 'date';
    h2.value = date;
    form.appendChild(h2);
    var h4 = document.createElement('input');
    h4.type = 'hidden';
    h4.name = 'user_id';
    h4.value = userId;
    form.appendChild(h4);
    if (checkbox.checked) {
        var h3 = document.createElement('input');
        h3.type = 'hidden';
        h3.name = 'completed';
        h3.value = 'on';
        form.appendChild(h3);
    }
    document.body.appendChild(form);
    form.submit();
}

function star(taskId, date, userId, currentStarred) {
    var starred = currentStarred ? 0 : 1;
    var form = document.createElement('form');
    form.method = 'post';
    form.action = '/star_task';
    var h1 = document.createElement('input');
    h1.type = 'hidden';
    h1.name = 'task_id';
    h1.value = taskId;
    form.appendChild(h1);
    var h2 = document.createElement('input');
    h2.type = 'hidden';
    h2.name = 'date';
    h2.value = date;
    form.appendChild(h2);
    var h3 = document.createElement('input');
    h3.type = 'hidden';
    h3.name = 'starred';
    h3.value = starred;
    form.appendChild(h3);
    var h4 = document.createElement('input');
    h4.type = 'hidden';
    h4.name = 'user_id';
    h4.value = userId;
    form.appendChild(h4);
    document.body.appendChild(form);
    form.submit();
}

function starAll(date, userId) {
    var form = document.createElement('form');
    form.method = 'post';
    form.action = '/star_all';
    var h1 = document.createElement('input');
    h1.type = 'hidden';
    h1.name = 'date';
    h1.value = date;
    form.appendChild(h1);
    var h2 = document.createElement('input');
    h2.type = 'hidden';
    h2.name = 'user_id';
    h2.value = userId;
    form.appendChild(h2);
    document.body.appendChild(form);
    form.submit();
}

function editTask(taskId) {
    var span = document.getElementById('task-name-' + taskId);
    var currentName = span.textContent;
    var input = document.createElement('input');
    input.type = 'text';
    input.value = currentName;
    input.className = 'edit-input';
    span.parentNode.replaceChild(input, span);
    input.focus();
    input.onblur = function() {
        var newName = input.value;
        if (newName === currentName) {
            input.parentNode.replaceChild(span, input);
            return;
        }
        var form = document.createElement('form');
        form.method = 'post';
        form.action = '/edit_task';
        var h1 = document.createElement('input');
        h1.type = 'hidden';
        h1.name = 'task_id';
        h1.value = taskId;
        form.appendChild(h1);
        var h2 = document.createElement('input');
        h2.type = 'hidden';
        h2.name = 'new_name';
        h2.value = newName;
        form.appendChild(h2);
        document.body.appendChild(form);
        form.submit();
    };
    input.onkeydown = function(e) {
        if (e.key === 'Enter') {
            input.blur();
        } else if (e.key === 'Escape') {
            input.value = currentName;
            input.blur();
        }
    };
}
