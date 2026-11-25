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
    ROLE_GURU, ROLE_REVIEWER, STATUS_UPLOAD_BARU, STATUS_REVISI, STATUS_SUDAH_DIREVISI, STATUS_DISETUJUI
)
from routes.decorators import role_required
from routes.wa_helper import send_wa

guru_bp = Blueprint("guru", __name__)

@guru_bp.route("/dashboard")
@login_required
@role_required(ROLE_GURU)
def dashboard():
    docs = Document.query.filter_by(user_id=current_user.id).order_by(Document.updated_at.desc()).all()
    
    assignments = TeachingAssignment.query.filter_by(user_id=current_user.id).all()
    
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

    valid_classes = [ta.class_name for ta in TeachingAssignment.query.filter_by(user_id=current_user.id, subject=subject).all()]
    for c in classes_list:
        if c not in valid_classes:
            flash("Kelas yang Anda pilih tidak valid.", "danger")
            return redirect(url_for("guru.dashboard"))

    classes_str = ", ".join(classes_list)
    generated_title = f"{subject} - {exam_type} ({classes_str})"

    # ==========================================
    # FITUR BARU: CEK DAN HAPUS DATA DUPLIKAT LAMA
    # ==========================================
    old_docs = Document.query.filter_by(
        user_id=current_user.id,
        subject=subject,
        exam_type=exam_type,
        classes=classes_str
    ).all()
    
    for old_doc in old_docs:
        db.session.delete(old_doc) # Hapus data lama yang duplikat
    db.session.commit()
    # ==========================================

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
    
    reviewers = User.query.filter_by(role=ROLE_REVIEWER).all()
    for rev in reviewers:
        if rev.phone:
            msg = f"Halo {rev.username},\n\n*DOKUMEN BARU*\nGuru: {current_user.username}\nJudul: {generated_title}\n\nSilakan cek aplikasi untuk mereview:\nhttps://progres.guardbansal.cloud/reviewer/dashboard"
            send_wa(rev.phone, msg)
            
    flash("Link Dokumen berhasil dikirim ke Bu Nelly.", "success")
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

    new_title = request.form.get("title", "").strip()
    file_url = request.form.get("file_url", "").strip()

    if not file_url:
        flash("Link revisi wajib diisi.", "danger")
        return redirect(url_for("guru.detail", doc_id=doc.id))

    if new_title:
        doc.title = new_title
    doc.file_path = file_url
    doc.status    = STATUS_UPLOAD_BARU
    db.session.commit()

    reviewers = User.query.filter_by(role=ROLE_REVIEWER).all()
    for rev in reviewers:
        if rev.phone:
            msg = f"Halo {rev.username},\n\n*REVISI DARI GURU*\nGuru: {current_user.username}\nJudul: {doc.title}\n\nGuru telah mengunggah link perbaikan. Silakan cek aplikasi:\nhttps://progres.guardbansal.cloud/reviewer/dashboard"
            send_wa(rev.phone, msg)

    flash("Link revisi berhasil dikirim! Status berubah menjadi 'Upload Baru'.", "success")
    return redirect(url_for("guru.detail", doc_id=doc.id))

@guru_bp.route("/document/<int:doc_id>")
@login_required
@role_required(ROLE_GURU)
def detail(doc_id):
    doc = Document.query.get_or_404(doc_id)
    if doc.user_id != current_user.id:
        abort(403)
        
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
    return redirect(doc.file_path)

@guru_bp.route("/document/<int:doc_id>/submit-links", methods=["POST"])
@login_required
@role_required(ROLE_GURU)
def submit_links(doc_id):
    doc = Document.query.get_or_404(doc_id)
    if doc.user_id != current_user.id:
        abort(403)
        
    if doc.status != STATUS_DISETUJUI:
        flash("Hanya dokumen berstatus 'Disetujui' yang dapat mengunggah link ini.", "warning")
        return redirect(url_for("guru.detail", doc_id=doc.id))

    duplicate_link = request.form.get("duplicate_link", "").strip()
    collab_link = request.form.get("collab_link", "").strip()

    if not duplicate_link or not collab_link:
        flash("Kedua link wajib diisi.", "danger")
        return redirect(url_for("guru.detail", doc_id=doc.id))

    doc.duplicate_link = duplicate_link
    doc.collab_link = collab_link
    db.session.commit()

    flash("Link Duplikat dan Link Kolaborasi berhasil disimpan.", "success")
    return redirect(url_for("guru.detail", doc_id=doc.id))