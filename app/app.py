"""Task Manager - Flask web application."""
import os
import re
import secrets
import socket
from datetime import date, datetime
from functools import wraps

import pymysql
from flask import (Flask, abort, flash, jsonify, redirect, render_template,
                   request, session, url_for)
from werkzeug.security import check_password_hash, generate_password_hash

import db

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "dev-secret-change-me")

PRIORITIES = ("low", "medium", "high")
STATUSES = ("pending", "in_progress", "done")
STATUS_LABELS = {"pending": "Pending", "in_progress": "In Progress", "done": "Done"}


# ---------------------------------------------------------------- helpers
def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in first.", "error")
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapped


def parse_date(value):
    value = (value or "").strip()
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return "invalid"


def decorate(task):
    """Add display helpers to a task row."""
    task["status_label"] = STATUS_LABELS[task["status"]]
    task["overdue"] = bool(
        task["due_date"] and task["due_date"] < date.today() and task["status"] != "done"
    )
    return task


def get_own_task(task_id):
    task = db.query(
        "SELECT * FROM tasks WHERE id = %s AND user_id = %s",
        (task_id, session["user_id"]),
        one=True,
    )
    if not task:
        abort(404)
    return task


def validate_task_form(form):
    """Return (clean_data, errors)."""
    errors = []
    title = form.get("title", "").strip()
    description = form.get("description", "").strip()
    priority = form.get("priority", "medium")
    status = form.get("status", "pending")
    due = parse_date(form.get("due_date"))

    if not title:
        errors.append("Title is required.")
    elif len(title) > 150:
        errors.append("Title must be 150 characters or fewer.")
    if priority not in PRIORITIES:
        errors.append("Invalid priority.")
    if status not in STATUSES:
        errors.append("Invalid status.")
    if due == "invalid":
        errors.append("Due date is not valid.")
        due = None

    data = {"title": title, "description": description, "priority": priority,
            "status": status, "due_date": due}
    return data, errors


# ---------------------------------------------------------------- security
@app.before_request
def csrf_protect():
    if request.method == "POST":
        token = session.get("_csrf")
        if not token or token != request.form.get("_csrf"):
            abort(400, "Invalid or missing CSRF token. Go back and reload the page.")


@app.context_processor
def inject_globals():
    if "_csrf" not in session:
        session["_csrf"] = secrets.token_hex(16)
    return {
        "csrf_token": session["_csrf"],
        "current_user": session.get("username"),
        "host": socket.gethostname(),   # container id -> shows which instance answered
    }


# ---------------------------------------------------------------- public pages
@app.route("/")
def index():
    if "user_id" in session:
        return redirect(url_for("dashboard"))
    return render_template("index.html")


@app.route("/about")
def about():
    return render_template("about.html")


@app.route("/health")
def health():
    """Used by the AWS Load Balancer health check."""
    return "OK", 200


# ---------------------------------------------------------------- auth
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm", "")

        errors = []
        if not re.fullmatch(r"[A-Za-z0-9_]{3,30}", username):
            errors.append("Username must be 3-30 letters, numbers or underscores.")
        if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
            errors.append("Enter a valid email address.")
        if len(password) < 6:
            errors.append("Password must be at least 6 characters.")
        if password != confirm:
            errors.append("Passwords do not match.")

        if not errors:
            try:
                db.execute(
                    "INSERT INTO users (username, email, password_hash) VALUES (%s, %s, %s)",
                    (username, email, generate_password_hash(password)),
                )
                flash("Registration successful. Please log in.", "success")
                return redirect(url_for("login"))
            except pymysql.err.IntegrityError:
                errors.append("That username or email is already registered.")

        for e in errors:
            flash(e, "error")
        return render_template("register.html", username=username, email=email)
    return render_template("register.html", username="", email="")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user = db.query("SELECT * FROM users WHERE username = %s", (username,), one=True)
        if user and check_password_hash(user["password_hash"], password):
            session.clear()
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            session["_csrf"] = secrets.token_hex(16)
            flash(f"Welcome back, {user['username']}!", "success")
            return redirect(url_for("dashboard"))
        flash("Invalid username or password.", "error")
    return render_template("login.html")


@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("login"))


# ---------------------------------------------------------------- dashboard
@app.route("/dashboard")
@login_required
def dashboard():
    uid = session["user_id"]
    rows = db.query(
        "SELECT status, COUNT(*) AS n FROM tasks WHERE user_id = %s GROUP BY status", (uid,)
    )
    counts = {s: 0 for s in STATUSES}
    for r in rows:
        counts[r["status"]] = r["n"]
    total = sum(counts.values())

    overdue = db.query(
        "SELECT COUNT(*) AS n FROM tasks WHERE user_id = %s AND status <> 'done' "
        "AND due_date IS NOT NULL AND due_date < CURDATE()", (uid,), one=True
    )["n"]

    upcoming = [decorate(t) for t in db.query(
        "SELECT * FROM tasks WHERE user_id = %s AND status <> 'done' "
        "ORDER BY due_date IS NULL, due_date, id DESC LIMIT 5", (uid,)
    )]
    percent = round(counts["done"] * 100 / total) if total else 0
    return render_template("dashboard.html", counts=counts, total=total,
                           overdue=overdue, upcoming=upcoming, percent=percent)


# ---------------------------------------------------------------- tasks CRUD
@app.route("/tasks")
@login_required
def tasks():
    status = request.args.get("status", "")
    q = request.args.get("q", "").strip()

    sql = "SELECT * FROM tasks WHERE user_id = %s"
    params = [session["user_id"]]
    if status in STATUSES:
        sql += " AND status = %s"
        params.append(status)
    if q:
        sql += " AND (title LIKE %s OR description LIKE %s)"
        params += [f"%{q}%", f"%{q}%"]
    sql += " ORDER BY (status = 'done'), due_date IS NULL, due_date, id DESC"

    items = [decorate(t) for t in db.query(sql, params)]
    return render_template("tasks.html", tasks=items, status=status, q=q,
                           statuses=STATUSES, labels=STATUS_LABELS)


@app.route("/tasks/new", methods=["GET", "POST"])
@login_required
def task_new():
    if request.method == "POST":
        data, errors = validate_task_form(request.form)
        if not errors:
            db.execute(
                "INSERT INTO tasks (user_id, title, description, priority, status, due_date) "
                "VALUES (%s, %s, %s, %s, %s, %s)",
                (session["user_id"], data["title"], data["description"],
                 data["priority"], data["status"], data["due_date"]),
            )
            flash("Task created.", "success")
            return redirect(url_for("tasks"))
        for e in errors:
            flash(e, "error")
        return render_template("task_form.html", task=data, mode="new",
                               priorities=PRIORITIES, statuses=STATUSES, labels=STATUS_LABELS)
    blank = {"title": "", "description": "", "priority": "medium",
             "status": "pending", "due_date": None}
    return render_template("task_form.html", task=blank, mode="new",
                           priorities=PRIORITIES, statuses=STATUSES, labels=STATUS_LABELS)


@app.route("/tasks/<int:task_id>/edit", methods=["GET", "POST"])
@login_required
def task_edit(task_id):
    task = get_own_task(task_id)
    if request.method == "POST":
        data, errors = validate_task_form(request.form)
        if not errors:
            db.execute(
                "UPDATE tasks SET title=%s, description=%s, priority=%s, status=%s, due_date=%s "
                "WHERE id=%s AND user_id=%s",
                (data["title"], data["description"], data["priority"], data["status"],
                 data["due_date"], task_id, session["user_id"]),
            )
            flash("Task updated.", "success")
            return redirect(url_for("tasks"))
        for e in errors:
            flash(e, "error")
        task = {**task, **data}
    return render_template("task_form.html", task=task, mode="edit",
                           priorities=PRIORITIES, statuses=STATUSES, labels=STATUS_LABELS)


@app.route("/tasks/<int:task_id>/toggle", methods=["POST"])
@login_required
def task_toggle(task_id):
    task = get_own_task(task_id)
    new_status = "pending" if task["status"] == "done" else "done"
    db.execute("UPDATE tasks SET status=%s WHERE id=%s AND user_id=%s",
               (new_status, task_id, session["user_id"]))
    flash("Task marked as done." if new_status == "done" else "Task re-opened.", "success")
    return redirect(request.referrer or url_for("tasks"))


@app.route("/tasks/<int:task_id>/delete", methods=["POST"])
@login_required
def task_delete(task_id):
    get_own_task(task_id)
    db.execute("DELETE FROM tasks WHERE id=%s AND user_id=%s", (task_id, session["user_id"]))
    flash("Task deleted.", "info")
    return redirect(url_for("tasks"))


# ---------------------------------------------------------------- JSON API
@app.route("/api/tasks")
@login_required
def api_tasks():
    items = db.query(
        "SELECT id, title, description, priority, status, due_date FROM tasks "
        "WHERE user_id = %s ORDER BY id DESC", (session["user_id"],)
    )
    for t in items:
        t["due_date"] = t["due_date"].isoformat() if t["due_date"] else None
    return jsonify(items)


# ---------------------------------------------------------------- errors
@app.errorhandler(404)
def not_found(_e):
    return render_template("error.html", code=404, message="Page not found."), 404


@app.errorhandler(400)
def bad_request(e):
    return render_template("error.html", code=400, message=getattr(e, "description", "Bad request.")), 400


# create tables when the app starts
db.init_db()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
