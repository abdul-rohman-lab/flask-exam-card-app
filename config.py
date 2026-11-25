import os
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
INSTANCE_DIR = os.path.join(BASE_DIR, "instance")
os.makedirs(INSTANCE_DIR, exist_ok=True)

class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key-change-me")
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", "sqlite:///" + os.path.join(INSTANCE_DIR, "kartu_soal.db")
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Upload folders (dipisah: dokumen vs screenshot)
    UPLOAD_ROOT = os.path.join(BASE_DIR, "static", "uploads")
    DOCUMENT_UPLOAD_FOLDER = os.path.join(UPLOAD_ROOT, "documents")
    SCREENSHOT_UPLOAD_FOLDER = os.path.join(UPLOAD_ROOT, "screenshots")

    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16 MB
    ALLOWED_DOC_EXTENSIONS = {"pdf", "doc", "docx", "xls", "xlsx"}
    ALLOWED_IMG_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp", "bmp", "tiff", "svg"}
    
    FONNTE_TOKEN = os.environ.get("FONNTE_TOKEN", "")

    # Flask-Mail
    MAIL_SERVER = os.environ.get("MAIL_SERVER", "smtp.gmail.com")
    MAIL_PORT = int(os.environ.get("MAIL_PORT", 587))
    MAIL_USE_TLS = os.environ.get("MAIL_USE_TLS", "True").lower() == "true"
    MAIL_USERNAME = os.environ.get("MAIL_USERNAME")
    MAIL_PASSWORD = os.environ.get("MAIL_PASSWORD")
    MAIL_DEFAULT_SENDER = os.environ.get("MAIL_DEFAULT_SENDER", "noreply@sekolah.local")