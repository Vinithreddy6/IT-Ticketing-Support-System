"""MySQL connection, schema setup, seed data and queries for the IT Helpdesk."""
import os
import hashlib
import secrets
from contextlib import contextmanager

import mysql.connector
from mysql.connector import Error  # noqa: F401  (re-exported for app.py)

# Target resolution time (hours) per priority. This is the "SLA deadline"
# that is stamped on a ticket when it is raised.
SLA_HOURS = {"Critical": 4, "High": 24, "Medium": 72, "Low": 168}
PRIORITIES = ["Low", "Medium", "High", "Critical"]
STATUSES = ["Open", "In Progress", "Resolved", "Closed"]


# --------------------------------------------------------------------------
# Connection handling
# --------------------------------------------------------------------------
def _config():
    """Read connection settings from Streamlit secrets or environment variables."""
    try:
        import streamlit as st
        secret_cfg = st.secrets.get("mysql", {})
    except Exception:
        secret_cfg = {}

    return {
        "host": secret_cfg.get("host", os.getenv("MYSQL_HOST", "localhost")),
        "port": int(secret_cfg.get("port", os.getenv("MYSQL_PORT", "3306"))),
        "user": secret_cfg.get("user", os.getenv("MYSQL_USER", "root")),
        "password": secret_cfg.get("password", os.getenv("MYSQL_PASSWORD", "")),
        "database": secret_cfg.get("database", os.getenv("MYSQL_DATABASE", "it_ticketing_system")),
    }


_POOL = None


def get_connection(with_database=True):
    global _POOL
    cfg = _config()
    if not with_database:
        cfg.pop("database", None)
        return mysql.connector.connect(**cfg)
    if _POOL is None:
        from mysql.connector.pooling import MySQLConnectionPool
        _POOL = MySQLConnectionPool(pool_name="it_helpdesk_pool", pool_size=8, **cfg)
    return _POOL.get_connection()


@contextmanager
def db_cursor(dictionary=True, commit=False):
    conn = get_connection()
    cursor = conn.cursor(dictionary=dictionary)
    try:
        yield cursor
        if commit:
            conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cursor.close()
        conn.close()


# --------------------------------------------------------------------------
# Passwords
# --------------------------------------------------------------------------
def hash_password(password: str) -> str:
    """PBKDF2 password hash; never store plain-text passwords."""
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 210_000)
    return f"pbkdf2_sha256$210000${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algorithm, iterations, salt_hex, digest_hex = stored.split("$")
        if algorithm != "pbkdf2_sha256":
            return False
        digest = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), bytes.fromhex(salt_hex), int(iterations)
        )
        return secrets.compare_digest(digest.hex(), digest_hex)
    except (ValueError, TypeError):
        return False


# --------------------------------------------------------------------------
# Schema + migrations (safe to run on an existing database)
# --------------------------------------------------------------------------
def _ensure_column(cur, table, column, ddl):
    cur.execute(
        """SELECT COUNT(*) FROM information_schema.COLUMNS
           WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME=%s AND COLUMN_NAME=%s""",
        (table, column),
    )
    if cur.fetchone()[0] == 0:
        cur.execute(f"ALTER TABLE {table} ADD COLUMN {ddl}")


def _ensure_index(cur, table, index, ddl):
    cur.execute(
        """SELECT COUNT(*) FROM information_schema.STATISTICS
           WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME=%s AND INDEX_NAME=%s""",
        (table, index),
    )
    if cur.fetchone()[0] == 0:
        cur.execute(f"ALTER TABLE {table} ADD INDEX {index} {ddl}")


def initialize_database():
    """Create tables and upgrade older databases. The database itself must already exist."""
    statements = [
        """
        CREATE TABLE IF NOT EXISTS users (
            user_id INT AUTO_INCREMENT PRIMARY KEY,
            name VARCHAR(100) NOT NULL,
            email VARCHAR(150) NOT NULL UNIQUE,
            password_hash VARCHAR(255) NOT NULL,
            role ENUM('Employee','IT Staff','Admin') NOT NULL DEFAULT 'Employee',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS categories (
            category_id INT AUTO_INCREMENT PRIMARY KEY,
            category_name VARCHAR(80) NOT NULL UNIQUE
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS tickets (
            ticket_id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT NOT NULL,
            assigned_to INT NULL,
            category_id INT NOT NULL,
            title VARCHAR(180) NOT NULL,
            description TEXT NOT NULL,
            priority ENUM('Low','Medium','High','Critical') NOT NULL DEFAULT 'Medium',
            status ENUM('Open','In Progress','Resolved','Closed') NOT NULL DEFAULT 'Open',
            due_date DATETIME NULL,
            resolved_at DATETIME NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(user_id),
            FOREIGN KEY (assigned_to) REFERENCES users(user_id) ON DELETE SET NULL,
            FOREIGN KEY (category_id) REFERENCES categories(category_id),
            INDEX idx_ticket_status (status),
            INDEX idx_ticket_user (user_id)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS comments (
            comment_id INT AUTO_INCREMENT PRIMARY KEY,
            ticket_id INT NOT NULL,
            user_id INT NOT NULL,
            comment TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (ticket_id) REFERENCES tickets(ticket_id) ON DELETE CASCADE,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS ticket_events (
            event_id INT AUTO_INCREMENT PRIMARY KEY,
            ticket_id INT NOT NULL,
            user_id INT NULL,
            event_text VARCHAR(255) NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (ticket_id) REFERENCES tickets(ticket_id) ON DELETE CASCADE,
            FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE SET NULL,
            INDEX idx_event_ticket (ticket_id)
        )
        """,
    ]
    conn = get_connection()
    cur = conn.cursor()
    try:
        for statement in statements:
            cur.execute(statement)

        # Upgrade databases created by the earlier version of this project.
        _ensure_column(cur, "tickets", "due_date", "due_date DATETIME NULL")
        _ensure_column(cur, "tickets", "resolved_at", "resolved_at DATETIME NULL")
        _ensure_index(cur, "tickets", "idx_ticket_assignee", "(assigned_to)")
        _ensure_index(cur, "tickets", "idx_ticket_due", "(due_date)")

        # Back-fill deadlines / resolution times for older tickets.
        # "updated_at=updated_at" stops MySQL from touching the timestamp.
        cur.execute(
            """UPDATE tickets
               SET due_date = DATE_ADD(created_at, INTERVAL CASE priority
                      WHEN 'Critical' THEN 4 WHEN 'High' THEN 24
                      WHEN 'Medium' THEN 72 ELSE 168 END HOUR),
                   updated_at = updated_at
               WHERE due_date IS NULL"""
        )
        cur.execute(
            """UPDATE tickets SET resolved_at = updated_at, updated_at = updated_at
               WHERE status IN ('Resolved','Closed') AND resolved_at IS NULL"""
        )

        for category in ("Hardware", "Software", "Network", "Email", "Access & Accounts", "Other"):
            cur.execute("INSERT IGNORE INTO categories (category_name) VALUES (%s)", (category,))
        conn.commit()
    finally:
        cur.close()
        conn.close()


# --------------------------------------------------------------------------
# Demo data
# --------------------------------------------------------------------------
DEMO_USERS = [
    ("Demo Employee", "employee@demo.com", "Employee", "Employee@123"),
    ("Demo IT Staff", "itstaff@demo.com", "IT Staff", "ITStaff@123"),
    ("Demo Admin", "admin@demo.com", "Admin", "Admin@123"),
]
EXTRA_DEMO_USERS = [
    ("Ravi Kumar", "ravi@demo.com", "IT Staff", "ITStaff@123"),
    ("Meera Iyer", "meera@demo.com", "IT Staff", "ITStaff@123"),
    ("Arjun Mehta", "arjun@demo.com", "Employee", "Employee@123"),
    ("Sneha Rao", "sneha@demo.com", "Employee", "Employee@123"),
    ("Karan Patel", "karan@demo.com", "Employee", "Employee@123"),
]

# (requester, assignee, category, title, description, priority, status,
#  hours_ago_created, hours_to_resolve)
SAMPLE_TICKETS = [
    ("employee", "itstaff", "Network", "Office Wi-Fi disconnecting",
     "Wi-Fi disconnects every few minutes in the office.", "High", "In Progress", 20, None),
    ("employee", None, "Hardware", "Keyboard keys not responding",
     "Several keys on my keyboard are not working.", "Medium", "Open", 6, None),
    ("arjun", "ravi", "Access & Accounts", "Cannot log in to the HR portal",
     "Password reset email never arrives and my account looks locked.", "Critical", "In Progress", 3, None),
    ("sneha", "ravi", "Software", "Excel crashes when opening large files",
     "Excel closes without warning on any file over 20 MB.", "Medium", "In Progress", 30, None),
    ("karan", "meera", "Email", "Shared mailbox not syncing",
     "The finance shared mailbox stopped syncing on my phone.", "High", "Open", 10, None),
    ("employee", "meera", "Software", "Install design software licence",
     "Need Adobe Illustrator installed for the marketing project.", "Low", "Open", 40, None),
    ("arjun", None, "Hardware", "Projector not detected in meeting room B",
     "Laptops cannot detect the projector over HDMI.", "High", "Open", 2, None),
    ("sneha", "itstaff", "Network", "VPN drops every hour",
     "VPN disconnects roughly once an hour while working from home.", "High", "Resolved", 60, 18),
    ("karan", "ravi", "Hardware", "Laptop battery drains very fast",
     "Battery only lasts 40 minutes after the last update.", "Medium", "Resolved", 90, 30),
    ("employee", "meera", "Access & Accounts", "Need access to the shared drive",
     "Please add me to the Sales shared drive.", "Low", "Closed", 120, 12),
    ("arjun", "itstaff", "Email", "Spam filter blocking client emails",
     "Emails from a key client land in junk.", "Critical", "Resolved", 48, 3),
    ("sneha", "meera", "Other", "Request second monitor",
     "Would like a second monitor for the data work.", "Low", "Closed", 150, 40),
    ("karan", "itstaff", "Software", "Teams camera not working",
     "Camera shows a black screen in Teams only.", "Medium", "Resolved", 70, 20),
    ("employee", "ravi", "Network", "Printer offline on floor 3",
     "Floor 3 printer shows offline for everyone.", "Medium", "Closed", 100, 26),
]


def seed_demo_data():
    """Create demo accounts and sample tickets without overwriting existing data."""
    with db_cursor(commit=True) as cur:
        cur.execute("SELECT COUNT(*) AS n FROM users WHERE email='ravi@demo.com'")
        richer_demo_missing = cur.fetchone()["n"] == 0
        for name, email, role, password in DEMO_USERS + EXTRA_DEMO_USERS:
            cur.execute("SELECT user_id FROM users WHERE email=%s", (email,))
            if not cur.fetchone():
                cur.execute(
                    "INSERT INTO users (name,email,password_hash,role) VALUES (%s,%s,%s,%s)",
                    (name, email, hash_password(password), role),
                )
        cur.execute("SELECT COUNT(*) AS n FROM tickets")
        ticket_count = cur.fetchone()["n"]

        # New database, or an old database that only holds the original 2 demo tickets.
        old_demo_only = richer_demo_missing and ticket_count <= 2
        if ticket_count == 0 or old_demo_only:
            # An old database already holds the first 2 sample tickets - keep them.
            _insert_sample_tickets(cur, skip=2 if old_demo_only else 0)


def _insert_sample_tickets(cur, skip=0):
    cur.execute("SELECT user_id, email FROM users")
    by_key = {r["email"].split("@")[0]: r["user_id"] for r in cur.fetchall()}
    cur.execute("SELECT category_id, category_name FROM categories")
    cats = {r["category_name"]: r["category_id"] for r in cur.fetchall()}

    for (req, asg, cat, title, desc, prio, status, ago, to_resolve) in SAMPLE_TICKETS[skip:]:
        sla = SLA_HOURS[prio]
        cur.execute(
            """INSERT INTO tickets
               (user_id,assigned_to,category_id,title,description,priority,status,
                created_at,updated_at,due_date,resolved_at)
               VALUES (%s,%s,%s,%s,%s,%s,%s,
                       DATE_SUB(NOW(), INTERVAL %s HOUR),
                       DATE_SUB(NOW(), INTERVAL %s HOUR),
                       DATE_ADD(DATE_SUB(NOW(), INTERVAL %s HOUR), INTERVAL %s HOUR),
                       DATE_ADD(DATE_SUB(NOW(), INTERVAL %s HOUR), INTERVAL %s HOUR))""",
            (by_key[req], by_key.get(asg), cats[cat], title, desc, prio, status,
             ago, (ago - to_resolve) if to_resolve else ago, ago, sla, ago, to_resolve),
        )
        tid = cur.lastrowid
        cur.execute(
            """INSERT INTO ticket_events (ticket_id,user_id,event_text,created_at)
               VALUES (%s,%s,%s,DATE_SUB(NOW(), INTERVAL %s HOUR))""",
            (tid, by_key[req], "raised the ticket", ago),
        )
        if asg:
            cur.execute("SELECT name FROM users WHERE user_id=%s", (by_key[asg],))
            asg_name = cur.fetchone()["name"]
            cur.execute(
                """INSERT INTO ticket_events (ticket_id,user_id,event_text,created_at)
                   VALUES (%s,%s,%s,DATE_SUB(NOW(), INTERVAL %s HOUR))""",
                (tid, by_key["admin"], f"assigned the ticket to {asg_name}", max(ago - 1, 0)),
            )
        if status in ("Resolved", "Closed") and to_resolve:
            cur.execute(
                """INSERT INTO ticket_events (ticket_id,user_id,event_text,created_at)
                   VALUES (%s,%s,%s,DATE_SUB(NOW(), INTERVAL %s HOUR))""",
                (tid, by_key[asg], f"changed status to {status}", max(ago - to_resolve, 0)),
            )
        if asg and status == "In Progress":
            cur.execute(
                """INSERT INTO comments (ticket_id,user_id,comment,created_at)
                   VALUES (%s,%s,%s,DATE_SUB(NOW(), INTERVAL %s HOUR))""",
                (tid, by_key[asg], "Looking into this now - I'll update you shortly.", max(ago - 2, 0)),
            )


# --------------------------------------------------------------------------
# Users
# --------------------------------------------------------------------------
def get_user_by_email(email):
    with db_cursor() as cur:
        cur.execute(
            "SELECT user_id,name,email,password_hash,role FROM users WHERE email=%s",
            (email.strip().lower(),),
        )
        return cur.fetchone()


def create_user(name, email, password, role="Employee"):
    with db_cursor(commit=True) as cur:
        cur.execute(
            "INSERT INTO users (name,email,password_hash,role) VALUES (%s,%s,%s,%s)",
            (name.strip(), email.strip().lower(), hash_password(password), role),
        )


def get_all_users():
    with db_cursor() as cur:
        cur.execute(
            """SELECT u.user_id,u.name,u.email,u.role,u.created_at,
                      COUNT(t.ticket_id) AS tickets_raised
               FROM users u LEFT JOIN tickets t ON t.user_id=u.user_id
               GROUP BY u.user_id,u.name,u.email,u.role,u.created_at
               ORDER BY FIELD(u.role,'Admin','IT Staff','Employee'), u.name"""
        )
        return cur.fetchall()


def set_user_role(user_id, role):
    if role not in ("Employee", "IT Staff", "Admin"):
        raise ValueError("Invalid role")
    with db_cursor(commit=True) as cur:
        cur.execute("UPDATE users SET role=%s WHERE user_id=%s", (role, user_id))


def get_staff():
    """IT Staff and Admins who can own tickets, with their current active workload."""
    with db_cursor() as cur:
        cur.execute(
            """SELECT u.user_id,u.name,u.email,u.role,
                      COALESCE(SUM(t.status IN ('Open','In Progress')),0) AS active_tickets
               FROM users u LEFT JOIN tickets t ON t.assigned_to=u.user_id
               WHERE u.role IN ('IT Staff','Admin')
               GROUP BY u.user_id,u.name,u.email,u.role
               ORDER BY u.name"""
        )
        return cur.fetchall()


def get_categories():
    with db_cursor() as cur:
        cur.execute("SELECT category_id,category_name FROM categories ORDER BY category_name")
        return cur.fetchall()


# --------------------------------------------------------------------------
# Tickets
# --------------------------------------------------------------------------
def _log(cur, ticket_id, user_id, text):
    cur.execute(
        "INSERT INTO ticket_events (ticket_id,user_id,event_text) VALUES (%s,%s,%s)",
        (ticket_id, user_id, text[:255]),
    )


def create_ticket(user_id, category_id, title, description, priority):
    with db_cursor(commit=True) as cur:
        cur.execute(
            """INSERT INTO tickets (user_id,category_id,title,description,priority,due_date)
               VALUES (%s,%s,%s,%s,%s,DATE_ADD(NOW(), INTERVAL %s HOUR))""",
            (user_id, category_id, title.strip(), description.strip(), priority,
             SLA_HOURS.get(priority, 72)),
        )
        ticket_id = cur.lastrowid
        _log(cur, ticket_id, user_id, "raised the ticket")
        return ticket_id


_TICKET_SELECT = """
    SELECT t.ticket_id,t.title,t.description,t.priority,t.status,t.created_at,t.updated_at,
           t.due_date,t.resolved_at,t.user_id,t.assigned_to,
           c.category_name, requester.name AS requester_name,
           requester.email AS requester_email, assignee.name AS assignee_name,
           TIMESTAMPDIFF(MINUTE, NOW(), t.due_date) AS minutes_left,
           (t.status IN ('Open','In Progress') AND t.due_date IS NOT NULL
            AND t.due_date < NOW()) AS is_overdue
    FROM tickets t
    JOIN categories c ON c.category_id=t.category_id
    JOIN users requester ON requester.user_id=t.user_id
    LEFT JOIN users assignee ON assignee.user_id=t.assigned_to
"""


def fetch_tickets(user, status=None, search_text=None, priority=None,
                  assigned_to=None, unassigned_only=False, active_only=False,
                  overdue_only=False, order="priority", limit=500):
    """Fetch tickets visible to `user`. Employees only ever see their own."""
    conditions, params = [], []
    if user["role"] == "Employee":
        conditions.append("t.user_id=%s")
        params.append(user["user_id"])
    if status and status != "All":
        conditions.append("t.status=%s")
        params.append(status)
    if priority and priority != "All":
        conditions.append("t.priority=%s")
        params.append(priority)
    if assigned_to:
        conditions.append("t.assigned_to=%s")
        params.append(assigned_to)
    if unassigned_only:
        conditions.append("t.assigned_to IS NULL")
    if active_only:
        conditions.append("t.status IN ('Open','In Progress')")
    if overdue_only:
        conditions.append("t.status IN ('Open','In Progress') AND t.due_date < NOW()")
    if search_text:
        like = f"%{search_text}%"
        conditions.append(
            "(t.title LIKE %s OR CAST(t.ticket_id AS CHAR) LIKE %s "
            "OR requester.name LIKE %s OR assignee.name LIKE %s)"
        )
        params.extend([like, like, like, like])

    sql = _TICKET_SELECT
    if conditions:
        sql += " WHERE " + " AND ".join(conditions)
    if order == "newest":
        sql += " ORDER BY t.created_at DESC"
    else:  # most urgent first, finished work last
        sql += """ ORDER BY (t.status IN ('Resolved','Closed')),
                   FIELD(t.priority,'Critical','High','Medium','Low'),
                   (t.due_date IS NULL), t.due_date, t.created_at DESC"""
    sql += " LIMIT %s"
    params.append(int(limit))
    with db_cursor() as cur:
        cur.execute(sql, tuple(params))
        return cur.fetchall()


def get_ticket(ticket_id):
    with db_cursor() as cur:
        cur.execute(_TICKET_SELECT + " WHERE t.ticket_id=%s", (ticket_id,))
        return cur.fetchone()


def update_ticket(ticket_id, actor_id, status, priority, assigned_to,
                  due_date=None, recalc_sla=False):
    """Update a ticket and record what changed in the activity timeline."""
    with db_cursor(commit=True) as cur:
        cur.execute(
            """SELECT t.status,t.priority,t.assigned_to,t.due_date,a.name AS assignee_name
               FROM tickets t LEFT JOIN users a ON a.user_id=t.assigned_to
               WHERE t.ticket_id=%s FOR UPDATE""",
            (ticket_id,),
        )
        old = cur.fetchone()
        if not old:
            return False
        finished = status in ("Resolved", "Closed")
        sets = ["status=%s", "priority=%s", "assigned_to=%s",
                "resolved_at=IF(%s, COALESCE(resolved_at, NOW()), NULL)"]
        params = [status, priority, assigned_to, finished]
        if recalc_sla:
            sets.append("due_date=DATE_ADD(NOW(), INTERVAL %s HOUR)")
            params.append(SLA_HOURS.get(priority, 72))
        else:
            sets.append("due_date=%s")
            params.append(due_date)
        params.append(ticket_id)
        cur.execute(f"UPDATE tickets SET {', '.join(sets)} WHERE ticket_id=%s", tuple(params))

        if old["assigned_to"] != assigned_to:
            if assigned_to is None:
                _log(cur, ticket_id, actor_id, "unassigned the ticket")
            else:
                cur.execute("SELECT name FROM users WHERE user_id=%s", (assigned_to,))
                _log(cur, ticket_id, actor_id,
                     f"assigned the ticket to {cur.fetchone()['name']}")
        if old["status"] != status:
            _log(cur, ticket_id, actor_id, f"changed status from {old['status']} to {status}")
        if old["priority"] != priority:
            _log(cur, ticket_id, actor_id,
                 f"changed priority from {old['priority']} to {priority}")
        if recalc_sla:
            _log(cur, ticket_id, actor_id, f"reset the deadline to the {priority} target")
        elif due_date is not None and old["due_date"] != due_date:
            _log(cur, ticket_id, actor_id,
                 f"set the deadline to {due_date.strftime('%d %b %Y, %H:%M')}")
        return True


def claim_ticket(ticket_id, staff_id):
    """Let a staff member pick up an unassigned ticket. Returns True if they got it."""
    with db_cursor(commit=True) as cur:
        cur.execute(
            """UPDATE tickets
               SET assigned_to=%s, status=IF(status='Open','In Progress',status)
               WHERE ticket_id=%s AND assigned_to IS NULL
                 AND status IN ('Open','In Progress')""",
            (staff_id, ticket_id),
        )
        if cur.rowcount == 0:
            return False
        _log(cur, ticket_id, staff_id, "picked up the ticket")
        return True


def add_comment(ticket_id, user_id, comment):
    with db_cursor(commit=True) as cur:
        cur.execute(
            "INSERT INTO comments (ticket_id,user_id,comment) VALUES (%s,%s,%s)",
            (ticket_id, user_id, comment.strip()),
        )


def get_comments(ticket_id):
    with db_cursor() as cur:
        cur.execute(
            """SELECT c.comment,c.created_at,u.name,u.role
               FROM comments c JOIN users u ON u.user_id=c.user_id
               WHERE c.ticket_id=%s ORDER BY c.created_at""",
            (ticket_id,),
        )
        return cur.fetchall()


def get_timeline(ticket_id):
    """Comments and system events for one ticket, oldest first."""
    with db_cursor() as cur:
        cur.execute(
            """SELECT 'comment' AS kind, c.comment AS text, c.created_at,
                      u.name AS actor, u.role AS actor_role
               FROM comments c JOIN users u ON u.user_id=c.user_id
               WHERE c.ticket_id=%s
               UNION ALL
               SELECT 'event' AS kind, e.event_text AS text, e.created_at,
                      COALESCE(u.name,'System') AS actor, COALESCE(u.role,'') AS actor_role
               FROM ticket_events e LEFT JOIN users u ON u.user_id=e.user_id
               WHERE e.ticket_id=%s
               ORDER BY created_at""",
            (ticket_id, ticket_id),
        )
        return cur.fetchall()


# --------------------------------------------------------------------------
# Dashboards and analytics
# --------------------------------------------------------------------------
def get_dashboard_stats(user):
    where_sql, where_params = "", []
    if user["role"] == "Employee":
        where_sql, where_params = " WHERE user_id=%s", [user["user_id"]]
    with db_cursor() as cur:
        cur.execute(
            f"""SELECT COUNT(*) AS total,
                COALESCE(SUM(status='Open'),0) AS open_count,
                COALESCE(SUM(status='In Progress'),0) AS progress_count,
                COALESCE(SUM(status='Resolved'),0) AS resolved_count,
                COALESCE(SUM(status='Closed'),0) AS closed_count,
                COALESCE(SUM(status IN ('Open','In Progress')
                             AND due_date IS NOT NULL AND due_date < NOW()),0) AS overdue,
                COALESCE(SUM(status IN ('Open','In Progress')
                             AND assigned_to IS NULL),0) AS unassigned,
                COALESCE(SUM(status IN ('Open','In Progress') AND assigned_to=%s),0) AS my_active,
                COALESCE(SUM(status IN ('Resolved','Closed') AND assigned_to=%s),0) AS my_done,
                COALESCE(SUM(status IN ('Open','In Progress') AND assigned_to=%s
                             AND due_date IS NOT NULL AND due_date < NOW()),0) AS my_overdue,
                COALESCE(SUM(status IN ('Open','In Progress') AND assigned_to=%s
                             AND due_date BETWEEN NOW()
                                 AND DATE_ADD(NOW(), INTERVAL 24 HOUR)),0) AS my_due_soon
                FROM tickets{where_sql}""",
            tuple([user["user_id"]] * 4 + where_params),
        )
        row = cur.fetchone()
    return {k: int(v or 0) for k, v in row.items()}


def get_admin_overview():
    """Everything the admin command center needs, in one round trip."""
    out = {}
    with db_cursor() as cur:
        cur.execute("SELECT status, COUNT(*) AS total FROM tickets GROUP BY status")
        out["status"] = cur.fetchall()
        cur.execute("SELECT priority, COUNT(*) AS total FROM tickets GROUP BY priority")
        out["priority"] = cur.fetchall()
        cur.execute(
            """SELECT c.category_name, COUNT(*) AS total
               FROM tickets t JOIN categories c ON c.category_id=t.category_id
               GROUP BY c.category_name ORDER BY total DESC"""
        )
        out["category"] = cur.fetchall()
        cur.execute(
            """SELECT u.user_id, u.name, u.role,
                      COUNT(t.ticket_id) AS assigned,
                      COALESCE(SUM(t.status='Open'),0) AS open_count,
                      COALESCE(SUM(t.status='In Progress'),0) AS in_progress,
                      COALESCE(SUM(t.status IN ('Resolved','Closed')),0) AS resolved,
                      COALESCE(SUM(t.status IN ('Open','In Progress')
                                   AND t.due_date IS NOT NULL AND t.due_date < NOW()),0) AS overdue,
                      ROUND(AVG(CASE WHEN t.resolved_at IS NOT NULL
                                THEN TIMESTAMPDIFF(MINUTE, t.created_at, t.resolved_at)/60 END),1)
                          AS avg_hours
               FROM users u LEFT JOIN tickets t ON t.assigned_to=u.user_id
               WHERE u.role IN ('IT Staff','Admin')
               GROUP BY u.user_id, u.name, u.role
               HAVING u.role='IT Staff' OR COUNT(t.ticket_id) > 0
               ORDER BY assigned DESC, u.name"""
        )
        out["staff"] = cur.fetchall()
        cur.execute(
            """SELECT DATE(created_at) AS day, COUNT(*) AS total FROM tickets
               WHERE created_at >= DATE_SUB(CURDATE(), INTERVAL 13 DAY)
               GROUP BY DATE(created_at)"""
        )
        out["created_by_day"] = cur.fetchall()
        cur.execute(
            """SELECT DATE(resolved_at) AS day, COUNT(*) AS total FROM tickets
               WHERE resolved_at >= DATE_SUB(CURDATE(), INTERVAL 13 DAY)
               GROUP BY DATE(resolved_at)"""
        )
        out["resolved_by_day"] = cur.fetchall()
        cur.execute(
            """SELECT COUNT(*) AS resolved_total,
                      COALESCE(SUM(resolved_at <= due_date),0) AS on_time,
                      ROUND(AVG(TIMESTAMPDIFF(MINUTE, created_at, resolved_at)/60),1) AS avg_hours
               FROM tickets WHERE resolved_at IS NOT NULL AND due_date IS NOT NULL"""
        )
        out["sla"] = cur.fetchone()
        cur.execute(
            """SELECT e.event_text, e.created_at, e.ticket_id, t.title,
                      COALESCE(u.name,'System') AS actor
               FROM ticket_events e
               JOIN tickets t ON t.ticket_id=e.ticket_id
               LEFT JOIN users u ON u.user_id=e.user_id
               ORDER BY e.created_at DESC, e.event_id DESC LIMIT 10"""
        )
        out["activity"] = cur.fetchall()
    return out


def get_report_data():
    with db_cursor() as cur:
        cur.execute("SELECT status,COUNT(*) AS total FROM tickets GROUP BY status ORDER BY status")
        statuses = cur.fetchall()
        cur.execute(
            """SELECT c.category_name,COUNT(*) AS total
               FROM tickets t JOIN categories c ON c.category_id=t.category_id
               GROUP BY c.category_name ORDER BY total DESC"""
        )
        categories = cur.fetchall()
        return statuses, categories


def get_advanced_analytics():
    """Joined, grouped, HAVING and subquery-based reports executed in MySQL."""
    with db_cursor() as cur:
        cur.execute("""
            SELECT u.user_id, u.name AS staff_name,
                   COUNT(t.ticket_id) AS assigned_tickets,
                   SUM(t.status='Resolved') AS resolved_tickets,
                   SUM(t.status IN ('Open','In Progress')) AS active_tickets
            FROM users u
            LEFT JOIN tickets t ON t.assigned_to = u.user_id
            WHERE u.role = 'IT Staff'
            GROUP BY u.user_id, u.name
            ORDER BY assigned_tickets DESC, u.name
        """)
        staff_workload = cur.fetchall()

        cur.execute("""
            SELECT u.user_id, u.name, u.email, COUNT(t.ticket_id) AS ticket_count
            FROM users u
            JOIN tickets t ON t.user_id = u.user_id
            WHERE u.role = 'Employee'
            GROUP BY u.user_id, u.name, u.email
            HAVING COUNT(t.ticket_id) > (
                SELECT AVG(employee_ticket_count)
                FROM (
                    SELECT COUNT(*) AS employee_ticket_count
                    FROM tickets
                    GROUP BY user_id
                ) AS ticket_counts
            )
            ORDER BY ticket_count DESC
        """)
        above_average_employees = cur.fetchall()

        cur.execute("""
            SELECT c.category_name, t.status, COUNT(*) AS ticket_count
            FROM tickets t
            INNER JOIN categories c ON c.category_id = t.category_id
            GROUP BY c.category_name, t.status
            ORDER BY c.category_name, ticket_count DESC
        """)
        category_status = cur.fetchall()

        cur.execute("""
            SELECT COUNT(*) AS total_tickets,
                   SUM(priority='Critical') AS critical_tickets,
                   SUM(priority='High') AS high_tickets,
                   SUM(priority IN ('Low','Medium')) AS normal_tickets,
                   ROUND(AVG(TIMESTAMPDIFF(HOUR, created_at, updated_at)), 1)
                       AS avg_update_hours
            FROM tickets
        """)
        service_metrics = cur.fetchone()

    return staff_workload, above_average_employees, category_status, service_metrics