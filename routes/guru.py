import os
import uuid
import json
from flask import (
    Blueprint, render_template, redirect, url_for, flash, request,
    current_app, abort
)
from flask_login import login_required, current_user
from extensions import db
from models import (
    Document, User, TeachingAssignment, 
    ROLE_GURU, ROLE_REVIEWER, STATUS_UPLOAD_BARU, STATUS_REVISI, STATUS_SUDAH_DIREVISI
)
from routes.decorators import role_required
from routes.wa_helper import send_wa

guru_bp = Blueprint("guru", __name__)

@guru_bp.route("/dashboard")
@login_required
@role_required(ROLE_GURU)
def dashboard():
    docs = Document.query.filter_by(user_id=current_user.id).order_by(Document.updated_at.desc()).all()
    
    # Ambil data pemetaan mengajar guru ini
    assignments = TeachingAssignment.query.filter_by(user_id=current_user.id).all()
    
    # Kelompokkan menjadi dictionary: { "TOI": ["X-F", "XI-F"], "Farmasi": ["XII-A"] }
    mappings = {}
    for a in assignments:
        if a.subject not in mappings:
            mappings[a.subject] = []
        if a.class_name not in mappings[a.subject]:
            mappings[a.subject].append(a.class_name)
            
    return render_template("guru/dashboard.html", docs=docs, mappings_json=json.dumps(mappings))

@guru_bp.route("/upload", methods=["POST"])
@login_required
@role_required(ROLE_GURU)
def upload():
    subject = request.form.get("subject", "").strip()
    exam_type = request.form.get("exam_type", "").strip()
    classes_list = request.form.getlist("classes")
    file_url = request.form.get("file_url", "").strip()

    if not subject or not exam_type or not classes_list or not file_url:
        flash("Semua kolom wajib diisi, termasuk memilih minimal 1 kelas.", "danger")
        return redirect(url_for("guru.dashboard"))

    # Validasi keamanan: pastikan kelas yang dipilih memang diajar oleh guru ini
    valid_classes = [ta.class_name for ta in TeachingAssignment.query.filter_by(user_id=current_user.id, subject=subject).all()]
    for c in classes_list:
        if c not in valid_classes:
            flash("Kelas yang Anda pilih tidak valid.", "danger")
            return redirect(url_for("guru.dashboard"))

    # Generate Judul Otomatis
    classes_str = ", ".join(classes_list)
    generated_title = f"{subject} - {exam_type} ({classes_str})"

    doc = Document(
        user_id=current_user.id,
        title=generated_title,
        filename="Link Eksternal", 
        file_path=file_url, 
        status=STATUS_UPLOAD_BARU,
        subject=subject,
        exam_type=exam_type,
        classes=classes_str
    )
    db.session.add(doc)
    db.session.commit()
    
    # Kirim WA ke Reviewer (Bu Neli)
    reviewers = User.query.filter_by(role=ROLE_REVIEWER).all()
    for rev in reviewers:
        if rev.phone:
            msg = f"Halo {rev.username},\n\n*DOKUMEN BARU*\nGuru: {current_user.username}\nJudul: {generated_title}\n\nSilakan cek aplikasi untuk mereview:\nhttps://progres.guardbansal.cloud/reviewer/dashboard"
            send_wa(rev.phone, msg)
            
    flash("Link Dokumen berhasil dikirim ke Bu Neli.", "success")
    return redirect(url_for("guru.dashboard"))

@guru_bp.route("/document/<int:doc_id>/update", methods=["POST"])
@login_required
@role_required(ROLE_GURU)
def update_document(doc_id):
    doc = Document.query.get_or_404(doc_id)
    if doc.user_id != current_user.id:
        abort(403)
        
    if doc.status != STATUS_REVISI:
        flash("Hanya dokumen berstatus 'Revisi' yang dapat diperbarui.", "warning")
        return redirect(url_for("guru.detail", doc_id=doc.id))

    subject = request.form.get("subject", "").strip()
    exam_type = request.form.get("exam_type", "").strip()
    classes_list = request.form.getlist("classes")
    file_url = request.form.get("file_url", "").strip()

    if not subject or not exam_type or not classes_list or not file_url:
        flash("Semua kolom wajib diisi, termasuk memilih minimal 1 kelas.", "danger")
        return redirect(url_for("guru.detail", doc_id=doc.id))

    # Validasi kelas
    valid_classes = [ta.class_name for ta in TeachingAssignment.query.filter_by(user_id=current_user.id, subject=subject).all()]
    for c in classes_list:
        if c not in valid_classes:
            flash("Kelas yang Anda pilih tidak valid.", "danger")
            return redirect(url_for("guru.detail", doc_id=doc.id))

    classes_str = ", ".join(classes_list)
    generated_title = f"{subject} - {exam_type} ({classes_str})"

    # Update database
    doc.title     = generated_title
    doc.file_path = file_url
    doc.subject   = subject
    doc.exam_type = exam_type
    doc.classes   = classes_str
    doc.status    = STATUS_SUDAH_DIREVISI 
    db.session.commit()

    # Kirim WA ke Reviewer (Bu Neli)
    reviewers = User.query.filter_by(role=ROLE_REVIEWER).all()
    for rev in reviewers:
        if rev.phone:
            msg = f"Halo {rev.username},\n\n*REVISI DARI GURU*\nGuru: {current_user.username}\nJudul: {generated_title}\n\nGuru telah mengunggah file revisi. Silakan cek aplikasi:\nhttps://progres.guardbansal.cloud/reviewer/dashboard"
            send_wa(rev.phone, msg)

    flash("Link revisi berhasil diunggah! Status berubah menjadi 'Sudah Direvisi Oleh Guru'.", "success")
    return redirect(url_for("guru.detail", doc_id=doc.id))

@guru_bp.route("/document/<int:doc_id>")
@login_required
@role_required(ROLE_GURU)
def detail(doc_id):
    doc = Document.query.get_or_404(doc_id)
    if doc.user_id != current_user.id:
        abort(403)
        
    # Ambil data pemetaan untuk form revisi
    assignments = TeachingAssignment.query.filter_by(user_id=current_user.id).all()
    mappings = {}
    for a in assignments:
        if a.subject not in mappings:
            mappings[a.subject] = []
        if a.class_name not in mappings[a.subject]:
            mappings[a.subject].append(a.class_name)

    return render_template("guru/detail.html", doc=doc, mappings_json=json.dumps(mappings))

@guru_bp.route("/document/<int:doc_id>/download")
@login_required
@role_required(ROLE_GURU)
def download(doc_id):
    doc = Document.query.get_or_404(doc_id)
    if doc.user_id != current_user.id:
        abort(403)
    # Karena ini link, kita arahkan (redirect) user ke link aslinya
    return redirect(doc.file_path)