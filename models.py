from datetime import datetime
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from extensions import db

ROLE_ADMIN    = "admin"
ROLE_GURU     = "guru"
ROLE_REVIEWER = "reviewer"
ROLE_EDITOR   = "editor"

STATUS_UPLOAD_BARU    = "Upload Baru"
STATUS_REVISI         = "Revisi"
STATUS_DISETUJUI      = "Disetujui"
STATUS_SUDAH_DIREVISI = "Sudah Direvisi Oleh Guru"
ALL_STATUSES = [STATUS_UPLOAD_BARU, STATUS_REVISI, STATUS_DISETUJUI, STATUS_SUDAH_DIREVISI]

class User(UserMixin, db.Model):
    __tablename__ = "users"
    id            = db.Column(db.Integer, primary_key=True)
    username      = db.Column(db.String(80), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role          = db.Column(db.String(20), nullable=False, default=ROLE_GURU)
    email         = db.Column(db.String(120))
    phone         = db.Column(db.String(20))
    is_first_login = db.Column(db.Boolean, default=True, nullable=False)
    created_at    = db.Column(db.DateTime, default=datetime.now)

    documents = db.relationship("Document", backref="owner", lazy=True, cascade="all, delete-orphan")
    assignments = db.relationship("TeachingAssignment", backref="user", lazy=True, cascade="all, delete-orphan")

    def set_password(self, raw: str) -> None:
        self.password_hash = generate_password_hash(raw)

    def check_password(self, raw: str) -> bool:
        return check_password_hash(self.password_hash, raw)

class TeachingAssignment(db.Model):
    __tablename__ = "teaching_assignments"
    id         = db.Column(db.Integer, primary_key=True)
    user_id    = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    subject    = db.Column(db.String(100), nullable=False)
    class_name = db.Column(db.String(50), nullable=False)

class Document(db.Model):
    __tablename__ = "documents"
    id         = db.Column(db.Integer, primary_key=True)
    user_id    = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    title      = db.Column(db.String(255), nullable=True)
    filename   = db.Column(db.String(255), nullable=False)
    file_path  = db.Column(db.String(500), nullable=False)
    status     = db.Column(db.String(30), default=STATUS_UPLOAD_BARU, nullable=False)
    
    subject    = db.Column(db.String(100))
    exam_type  = db.Column(db.String(50))
    classes    = db.Column(db.String(100))

    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

    reviews = db.relationship("Review", backref="document", lazy=True, cascade="all, delete-orphan")

class Review(db.Model):
    __tablename__ = "reviews"
    id              = db.Column(db.Integer, primary_key=True)
    document_id     = db.Column(db.Integer, db.ForeignKey("documents.id"), nullable=False)
    status          = db.Column(db.String(30), nullable=False)
    created_at      = db.Column(db.DateTime, default=datetime.now)
    
    items = db.relationship("ReviewItem", backref="review", lazy=True, cascade="all, delete-orphan")

class ReviewItem(db.Model):
    __tablename__ = "review_items"
    id              = db.Column(db.Integer, primary_key=True)
    review_id       = db.Column(db.Integer, db.ForeignKey("reviews.id"), nullable=False)
    notes           = db.Column(db.Text)
    screenshot_path = db.Column(db.String(500))
    order           = db.Column(db.Integer, default=0)

# TABEL BARU UNTUK JADWAL UJIAN
class ExamSchedule(db.Model):
    __tablename__ = "exam_schedules"
    id         = db.Column(db.Integer, primary_key=True)
    date_str   = db.Column(db.String(50), nullable=False)
    class_name = db.Column(db.String(50), nullable=False)
    subject    = db.Column(db.String(100), nullable=False)