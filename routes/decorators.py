from functools import wraps
from flask import abort, redirect, url_for
from flask_login import current_user

def role_required(*roles):
    """Decorator RBAC. Mengarahkan guru first-login ke halaman aktivasi."""
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            if not current_user.is_authenticated:
                return redirect(url_for("auth.login"))
            if current_user.role not in roles:
                abort(403)
            if current_user.role == "guru" and current_user.is_first_login:
                return redirect(url_for("auth.first_login"))
            return f(*args, **kwargs)
        return wrapper
    return decorator