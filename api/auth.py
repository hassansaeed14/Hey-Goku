import json
import os
import bcrypt
from datetime import datetime

USERS_FILE = "memory/users.json"

def load_users():
    if not os.path.exists(USERS_FILE):
        return {}
    with open(USERS_FILE, "r") as f:
        return json.load(f)

def save_users(users):
    with open(USERS_FILE, "w") as f:
        json.dump(users, f, indent=4)

def register_user(username, password, name):
    users = load_users()
    if username in users:
        return False, "Username already exists!"
    
    hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    users[username] = {
        "username": username,
        "password": hashed,
        "name": name,
        "created": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "plan": "free"
    }
    save_users(users)
    return True, "Account created successfully!"

def login_user(username, password):
    users = load_users()
    if username not in users:
        return False, "Username not found!"
    
    user = users[username]
    if bcrypt.checkpw(password.encode(), user["password"].encode()):
        return True, user
    return False, "Wrong password!"

def get_user(username):
    users = load_users()
    return users.get(username, None)

def update_user_plan(username, plan):
    users = load_users()
    if username in users:
        users[username]["plan"] = plan
        save_users(users)
        return True
    return False