from __future__ import annotations

from security.auth_manager import get_user, register_user


def login_user(username, password, ip_address="local", user_agent="legacy"):
    from security.auth_manager import authenticate_user

    success, result, token = authenticate_user(
        username,
        password,
        ip_address=ip_address,
        user_agent=user_agent,
    )
    if success:
        payload = dict(result)
        if token:
            payload["session_token"] = token
        return True, payload
    return False, result


def update_user_plan(username, plan):
    from security.auth_manager import load_users, save_users

    normalized_username = str(username or "").strip().lower()
    normalized_plan = str(plan or "").strip().lower()
    users = load_users()
    if normalized_username not in users:
        return False
    users[normalized_username]["plan"] = normalized_plan or "private"
    save_users(users)
    return True
