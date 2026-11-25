from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from models import User

auth_bp = Blueprint("auth", __name__)

DASHBOARD_BY_ROLE = {
    "admin":    "admin.dashboard",
    "guru":     "guru.dashboard",
    "reviewer": "reviewer.dashboard",
    "editor":   "editor.dashboard",
}

@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for(DASHBOARD_BY_ROLE.get(current_user.role, "auth.login")))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user = User.query.filter_by(username=username).first()
        
        if user and user.check_password(password):
            login_user(user)
            # Langsung arahkan ke dashboard sesuai role, tanpa cek is_first_login
            return redirect(url_for(DASHBOARD_BY_ROLE.get(user.role, "auth.login")))
            
        flash("Username atau password salah.", "danger")

    return render_template("auth/login.html")

@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash("Anda telah logout.", "info")
    return redirect(url_for("auth.login"))