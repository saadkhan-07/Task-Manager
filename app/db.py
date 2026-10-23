"""Database helper functions (MySQL via PyMySQL)."""
import os
import time

import pymysql
from werkzeug.security import generate_password_hash

CONFIG = {
    "host": os.getenv("DB_HOST", "db"),
    "user": os.getenv("DB_USER", "taskuser"),
    "password": os.getenv("DB_PASSWORD", "taskpass"),
    "database": os.getenv("DB_NAME", "tasksdb"),
    "cursorclass": pymysql.cursors.DictCursor,
    "autocommit": True,
}


def get_connection(retries=15, delay=3):
    """Connect to MySQL; retry while the DB container is still starting."""
    for attempt in range(1, retries + 1):
        try:
            return pymysql.connect(**CONFIG)
        except pymysql.MySQLError as exc:
            print(f"[db] not ready (attempt {attempt}/{retries}): {exc}", flush=True)
            time.sleep(delay)
    raise RuntimeError("Could not connect to the database")


def query(sql, params=(), one=False):
    """Run a SELECT. Returns a list of dicts (or one dict / None if one=True)."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()
    finally:
        conn.close()
    if one:
        return rows[0] if rows else None
    return rows


def execute(sql, params=()):
    """Run INSERT / UPDATE / DELETE. Returns (lastrowid, rowcount)."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            return cur.lastrowid, cur.rowcount
    finally:
        conn.close()


def init_db():
    """Create tables and a demo account (safe to run many times)."""
    execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INT AUTO_INCREMENT PRIMARY KEY,
            username VARCHAR(30) NOT NULL UNIQUE,
            email VARCHAR(120) NOT NULL UNIQUE,
            password_hash VARCHAR(255) NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    execute(
        """
        CREATE TABLE IF NOT EXISTS tasks (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT NOT NULL,
            title VARCHAR(150) NOT NULL,
            description TEXT,
            priority ENUM('low','medium','high') NOT NULL DEFAULT 'medium',
            status ENUM('pending','in_progress','done') NOT NULL DEFAULT 'pending',
            due_date DATE NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
        """
    )

    # Demo user, so login works on every EC2 instance (each has its own DB)
    user_id, created = execute(
        "INSERT IGNORE INTO users (username, email, password_hash) VALUES (%s, %s, %s)",
        ("demo", "demo@example.com", generate_password_hash("demo123")),
    )
    if created == 1:
        samples = [
            ("Finish DevOps lab report", "Add screenshots of Docker and AWS steps.", "high", "in_progress"),
            ("Prepare for viva", "Revise Docker volumes and Compose.", "medium", "pending"),
            ("Push code to GitHub", "Commit Dockerfile and docker-compose.yml.", "low", "done"),
        ]
        for title, desc, prio, status in samples:
            execute(
                "INSERT INTO tasks (user_id, title, description, priority, status) "
                "VALUES (%s, %s, %s, %s, %s)",
                (user_id, title, desc, prio, status),
            )
