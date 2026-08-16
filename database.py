"""
database.py — SQLite User Database
===================================
Handles user authentication with secure password hashing.
Database file is stored in Flask's instance folder (excluded from git).
"""

import os
import sqlite3
from pathlib import Path
from werkzeug.security import generate_password_hash, check_password_hash
from flask import current_app, g


def get_db_path() -> Path:
    """Get the path to the SQLite database file."""
    # Use Flask's instance folder (auto-created, gitignored by default)
    instance_path = Path(current_app.instance_path)
    instance_path.mkdir(parents=True, exist_ok=True)
    return instance_path / "users.db"


def get_db():
    """Get a database connection for the current request."""
    if "db" not in g:
        db_path = get_db_path()
        g.db = sqlite3.connect(
            db_path,
            detect_types=sqlite3.PARSE_DECLTYPES
        )
        g.db.row_factory = sqlite3.Row
    return g.db


def close_db(e=None):
    """Close the database connection at the end of the request."""
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    """Initialize the database schema."""
    db = get_db()
    db.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT DEFAULT 'user',
            approved INTEGER DEFAULT 1,
            is_team INTEGER DEFAULT 0,
            full_name TEXT DEFAULT '',
            course TEXT DEFAULT '',
            bio TEXT DEFAULT '',
            avatar TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    # Migration for existing databases: add any missing columns
    cols = {row["name"] for row in db.execute("PRAGMA table_info(users)").fetchall()}
    if "approved" not in cols:
        db.execute("ALTER TABLE users ADD COLUMN approved INTEGER DEFAULT 1")
    for col, ddl in {
        "is_team": "ALTER TABLE users ADD COLUMN is_team INTEGER DEFAULT 0",
        "full_name": "ALTER TABLE users ADD COLUMN full_name TEXT DEFAULT ''",
        "course": "ALTER TABLE users ADD COLUMN course TEXT DEFAULT ''",
        "bio": "ALTER TABLE users ADD COLUMN bio TEXT DEFAULT ''",
        "avatar": "ALTER TABLE users ADD COLUMN avatar TEXT DEFAULT ''",
    }.items():
        if col not in cols:
            db.execute(ddl)
    db.commit()


class User:
    """User model for Flask-Login."""

    PROFILE_COLS = "id, username, role, approved, is_team, full_name, course, bio, avatar, created_at"

    def __init__(self, id: int, username: str, role: str = "user", approved: bool = True,
                 is_team: bool = False,
                 full_name: str = "", course: str = "", bio: str = "", avatar: str = ""):
        self.id = id
        self.username = username
        self.role = role
        self.approved = bool(approved)
        self.is_team = bool(is_team)
        self.full_name = full_name or ""
        self.course = course or ""
        self.bio = bio or ""
        self.avatar = avatar or ""

    @property
    def is_authenticated(self):
        return True

    @property
    def is_active(self):
        # Inactive = rejected/disabled users cannot log in.
        # Pending (unapproved) users are kept "active" so we can control
        # the redirect message at login time.
        return True

    @property
    def is_anonymous(self):
        return False

    @property
    def display_name(self) -> str:
        """Name shown on the team page (full name, falling back to username)."""
        return self.full_name.strip() or self.username

    def get_id(self):
        return str(self.id)

    @staticmethod
    def _row_to_user(row):
        return User(
            row["id"], row["username"], row["role"], row["approved"],
            row["is_team"], row["full_name"], row["course"], row["bio"], row["avatar"],
        )

    @staticmethod
    def get(user_id: int):
        """Load user by ID (for Flask-Login)."""
        db = get_db()
        row = db.execute(
            f"SELECT {User.PROFILE_COLS} FROM users WHERE id = ?", (user_id,)
        ).fetchone()
        if row:
            return User._row_to_user(row)
        return None

    @staticmethod
    def get_by_username(username: str):
        """Load user by username."""
        db = get_db()
        row = db.execute(
            f"SELECT {User.PROFILE_COLS}, password_hash FROM users WHERE username = ?",
            (username,)
        ).fetchone()
        if row:
            user = User._row_to_user(row)
            user.password_hash = row["password_hash"]
            return user
        return None

    @staticmethod
    def create(username: str, password: str, role: str = "user", approved: bool = False):
        """Create a new user with hashed password.

        Regular self-registrations are created with approved=False (pending).
        Admin-created users pass approved=True.
        """
        db = get_db()
        password_hash = generate_password_hash(password)
        try:
            cursor = db.execute(
                "INSERT INTO users (username, password_hash, role, approved) VALUES (?, ?, ?, ?)",
                (username, password_hash, role, 1 if approved else 0)
            )
            db.commit()
            return User(cursor.lastrowid, username, role, approved)
        except sqlite3.IntegrityError:
            raise ValueError("Username already exists")

    def check_password(self, password: str) -> bool:
        """Verify a password against the stored hash."""
        return check_password_hash(self.password_hash, password)

    @staticmethod
    def set_approved(user_id: int, approved: bool):
        """Approve (True) or reject (False) a user."""
        db = get_db()
        db.execute(
            "UPDATE users SET approved = ? WHERE id = ?",
            (1 if approved else 0, user_id)
        )
        db.commit()

    @staticmethod
    def update_profile(user_id: int, full_name: str = "", course: str = "",
                       bio: str = "", avatar: str = None):
        """Update a user's profile fields. Pass avatar=None to keep the existing one."""
        db = get_db()
        sql = "UPDATE users SET full_name = ?, course = ?, bio = ?"
        params = [full_name.strip(), course.strip(), bio.strip()]
        if avatar is not None:
            sql += ", avatar = ?"
            params.append(avatar)
        sql += " WHERE id = ?"
        params.append(user_id)
        db.execute(sql, params)
        db.commit()

    @staticmethod
    def change_password(user_id: int, new_password: str):
        """Set a new password hash for a user."""
        db = get_db()
        password_hash = generate_password_hash(new_password)
        db.execute(
            "UPDATE users SET password_hash = ? WHERE id = ?",
            (password_hash, user_id)
        )
        db.commit()

    @staticmethod
    def delete(user_id: int):
        """Delete a user by ID."""
        db = get_db()
        db.execute("DELETE FROM users WHERE id = ?", (user_id,))
        db.commit()

    @staticmethod
    def list_all():
        """Return all users (newest first)."""
        db = get_db()
        rows = db.execute(
            "SELECT id, username, role, approved, is_team, full_name, created_at FROM users "
            "ORDER BY created_at DESC, id DESC"
        ).fetchall()
        return [dict(r) for r in rows]

    @staticmethod
    def list_team():
        """Return approved users explicitly marked as team members.

        Only accounts with is_team = 1 appear on the public Team page,
        so not every registered user shows up.
        """
        db = get_db()
        rows = db.execute(
            f"SELECT {User.PROFILE_COLS} FROM users "
            "WHERE approved = 1 AND is_team = 1 "
            "ORDER BY role DESC, id ASC"
        ).fetchall()
        return [User._row_to_user(r) for r in rows]

    @staticmethod
    def set_team(user_id: int, is_team: bool):
        """Mark (True) or unmark (False) a user as a team member."""
        db = get_db()
        db.execute(
            "UPDATE users SET is_team = ? WHERE id = ?",
            (1 if is_team else 0, user_id)
        )
        db.commit()

    @staticmethod
    def set_role(user_id: int, role: str):
        """Set a user's role ('admin' or 'user')."""
        db = get_db()
        db.execute("UPDATE users SET role = ? WHERE id = ?", (role, user_id))
        db.commit()

    @staticmethod
    def count_admins() -> int:
        """Count users with the admin role."""
        db = get_db()
        return db.execute(
            "SELECT COUNT(*) FROM users WHERE role = 'admin'"
        ).fetchone()[0]

    @staticmethod
    def count_pending():
        """Count users awaiting approval."""
        db = get_db()
        return db.execute(
            "SELECT COUNT(*) FROM users WHERE approved = 0"
        ).fetchone()[0]


def create_default_admin():
    """Create a default admin user if none exists."""
    db = get_db()
    count = db.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    if count == 0:
        import os
        username = os.environ.get("ADMIN_USERNAME", "admin")
        password = os.environ.get("ADMIN_PASSWORD", "admin123")
        # Create default admin - CHANGE THIS PASSWORD IN PRODUCTION!
        User.create(username, password, role="admin", approved=True)
        print(f"  ⚠️  Created default admin user (username: {username}, password: {password})")
        print("     Please change the password after first login!")