import json
import os
import bcrypt
from datetime import datetime

USERS_FILE = "memory/users.json"


def load_users():
    if not os.path.exists(USERS_FILE):
        return {}

    try:
        with open(USERS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_users(users):
    os.makedirs(os.path.dirname(USERS_FILE), exist_ok=True)
    with open(USERS_FILE, "w", encoding="utf-8") as f:
        json.dump(users, f, indent=4, ensure_ascii=False)


def sanitize_user(user):
    if not user:
        return None

    return {
        "username": user.get("username", ""),
        "name": user.get("name", ""),
        "created": user.get("created", ""),
        "plan": user.get("plan", "free")
    }


def register_user(username, password, name):
    username = str(username).strip().lower()
    password = str(password).strip()
    name = str(name).strip()

    if not username or not password or not name:
        return False, "All fields are required."

    if len(username) < 3:
        return False, "Username must be at least 3 characters."

    if len(password) < 6:
        return False, "Password must be at least 6 characters."

    users = load_users()

    if username in users:
        return False, "Username already exists."

    hashed = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

    users[username] = {
        "username": username,
        "password": hashed,
        "name": name,
        "created": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "plan": "free"
    }

    save_users(users)
    return True, "Account created successfully."


def login_user(username, password):
    username = str(username).strip().lower()
    password = str(password).strip()

    users = load_users()

    if username not in users:
        return False, "Username not found."

    user = users[username]

    if bcrypt.checkpw(password.encode("utf-8"), user["password"].encode("utf-8")):
        return True, sanitize_user(user)

    return False, "Wrong password."


def get_user(username):
    username = str(username).strip().lower()
    users = load_users()
    return sanitize_user(users.get(username))


def update_user_plan(username, plan):
    username = str(username).strip().lower()
    plan = str(plan).strip().lower()

    users = load_users()

    if username in users:
        users[username]["plan"] = plan
        save_users(users)
        return True

    return False