import os
from flask import Flask, redirect, url_for
from config import Config
from extensions import db, login_manager, mail


def create_app(config_class=Config):
    app = Flask(__name__, instance_relative_config=False)
    app.config.from_object(config_class)

    # Ensure upload directories exist
    os.makedirs(app.config["DOCUMENT_UPLOAD_FOLDER"], exist_ok=True)
    os.makedirs(app.config["SCREENSHOT_UPLOAD_FOLDER"], exist_ok=True)

    db.init_app(app)
    login_manager.init_app(app)
    mail.init_app(app)

    # Blueprints
    from routes.auth     import auth_bp
    from routes.admin    import admin_bp
    from routes.guru     import guru_bp
    from routes.reviewer import reviewer_bp
    from routes.editor   import editor_bp
    from routes.api      import api_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp,    url_prefix="/admin")
    app.register_blueprint(guru_bp,     url_prefix="/guru")
    app.register_blueprint(reviewer_bp, url_prefix="/reviewer")
    app.register_blueprint(editor_bp,   url_prefix="/editor")
    app.register_blueprint(api_bp,      url_prefix="/api")

    # User loader
    from models import User

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    @app.route("/")
    def index():
        return redirect(url_for("auth.login"))

    @app.errorhandler(403)
    def forbidden(_e):
        return "403 — Akses Ditolak", 403

    # DB init + seed akun bawaan
    with app.app_context():
        db.create_all()
        _seed_default_users()

    return app


def _seed_default_users():
    from models import User, ROLE_ADMIN, ROLE_REVIEWER, ROLE_EDITOR, ROLE_GURU

    # Tambahkan dummy phone (format 08xxx)
    defaults = [
        ("admin",    "admin123",   ROLE_ADMIN,    "admin@sekolah.local", "08111111111"),
        ("nelly",  "nelly123",    ROLE_REVIEWER, "nely@sekolah.local", "085722342802"),
        ("editor",   "editor123",  ROLE_EDITOR,   "editor@sekolah.local","081292811927"),
        ("oman",   "guru123",  ROLE_GURU,   "oman@sekolah.local","081292811927"),
    ]
    for username, pw, role, email, phone in defaults:
        if not User.query.filter_by(username=username).first():
            u = User(username=username, role=role, email=email, phone=phone, is_first_login=False)
            u.set_password(pw)
            db.session.add(u)
    db.session.commit()


if __name__ == "__main__":
    create_app().run(host="0.0.0.0", port=5000, debug=True)