import os
import uuid
from flask import (
    Blueprint, render_template, redirect, url_for, flash, request,
    current_app, abort, send_from_directory
)
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from extensions import db
from models import (
    Document, User, Review, ReviewItem, 
    ROLE_GURU, ROLE_REVIEWER, ROLE_EDITOR, 
    STATUS_DISETUJUI, ALL_STATUSES
)
from routes.decorators import role_required
from routes.wa_helper import send_wa

reviewer_bp = Blueprint("reviewer", __name__)

@reviewer_bp.route("/dashboard")
@login_required
@role_required(ROLE_REVIEWER)
def dashboard():
    docs = Document.query.order_by(Document.updated_at.desc()).all()
    return render_template("reviewer/dashboard.html", docs=docs)

@reviewer_bp.route("/document/<int:doc_id>/raw")
@login_required
@role_required(ROLE_REVIEWER, ROLE_GURU)
def raw_file(doc_id):
    doc = Document.query.get_or_404(doc_id)
    if current_user.role == ROLE_GURU and doc.user_id != current_user.id:
        abort(403)
    return send_from_directory(
        current_app.config["DOCUMENT_UPLOAD_FOLDER"],
        doc.file_path,
        as_attachment=False
    )

@reviewer_bp.route("/document/<int:doc_id>", methods=["GET", "POST"])
@login_required
@role_required(ROLE_REVIEWER)
def review(doc_id):
    doc = Document.query.get_or_404(doc_id)

    if request.method == "POST":
        status = request.form.get("status")
        if status not in ALL_STATUSES:
            flash("Status tidak valid.", "danger")
            return redirect(url_for("reviewer.review", doc_id=doc_id))

        new_review = Review(document_id=doc.id, status=status)
        db.session.add(new_review)
        db.session.flush()

        screenshots = request.files.getlist("screenshots[]")
        notes_list = request.form.getlist("notes[]")

        max_items = max(len(screenshots), len(notes_list))
        
        for i in range(max_items):
            shot = screenshots[i] if i < len(screenshots) else None
            catatan = notes_list[i].strip() if i < len(notes_list) else ""
            
            has_image = shot and (shot.filename or shot.content_type.startswith('image/'))
            
            if has_image or catatan:
                stored_name = None
                if has_image:
                    ext = "png" 
                    if shot.filename:
                        ext = shot.filename.rsplit(".", 1)[-1].lower()
                    else:
                        if shot.content_type == 'image/jpeg': ext = 'jpg'
                        elif shot.content_type == 'image/gif': ext = 'gif'
                        elif shot.content_type == 'image/webp': ext = 'webp'
                        elif shot.content_type == 'image/bmp': ext = 'bmp'

                    if ext in current_app.config["ALLOWED_IMG_EXTENSIONS"]:
                        base_name = secure_filename(shot.filename) if shot.filename else "pasted_image"
                        if not base_name.lower().endswith(f".{ext}"):
                            base_name = f"{base_name}.{ext}"
                        
                        stored_name = f"{doc_id}_{uuid.uuid4().hex}_{base_name}"
                        shot.save(os.path.join(current_app.config["SCREENSHOT_UPLOAD_FOLDER"], stored_name))

                item = ReviewItem(
                    review_id=new_review.id,
                    screenshot_path=stored_name,
                    notes=catatan,
                    order=i
                )
                db.session.add(item)

        doc.status = status
        db.session.commit()

        # Kirim Notifikasi WA
        try:
            _send_review_wa(doc, status, "Silakan cek aplikasi untuk detail gambar dan catatan.")
            flash("Review disimpan & WA terkirim.", "success")
        except Exception as exc:
            flash(f"Review tersimpan, namun WA gagal: {exc}", "warning")

        return redirect(url_for("reviewer.review", doc_id=doc_id))

    history = Review.query.filter_by(document_id=doc.id).order_by(Review.created_at.desc()).all()
    return render_template("reviewer/detail.html", doc=doc, history=history)


# ==========================================
# ROUTE BARU: UNTUK EDIT RIWAYAT REVIEW
# ==========================================
@reviewer_bp.route("/review/<int:review_id>/edit", methods=["POST"])
@login_required
@role_required(ROLE_REVIEWER)
def edit_review(review_id):
    review = Review.query.get_or_404(review_id)
    doc = review.document
    
    status = request.form.get("status")
    notes_list = request.form.getlist("notes[]")

    if status not in ALL_STATUSES:
        flash("Status tidak valid.", "danger")
        return redirect(url_for("reviewer.review", doc_id=doc.id))

    # 1. Update Status Review
    review.status = status

    # 2. Update Catatan (Notes) berdasarkan urutan item
    items = sorted(review.items, key=lambda x: x.order)
    for i, item in enumerate(items):
        if i < len(notes_list):
            item.notes = notes_list[i].strip()

    # 3. Sinkronisasi Status Dokumen (Jika review ini adalah review paling baru)
    latest_review = Review.query.filter_by(document_id=doc.id).order_by(Review.created_at.desc()).first()
    if latest_review and latest_review.id == review.id:
        doc.status = status

    db.session.commit()

    # (Opsional) Kirim WA Notifikasi Pembaruan
    try:
        _send_review_wa(doc, status, "Review telah diperbarui oleh Reviewer. Silakan cek aplikasi untuk detail terbarunya.")
        flash("Riwayat review berhasil diperbarui & WA notifikasi terkirim.", "success")
    except Exception as exc:
        flash(f"Riwayat review diperbarui, namun WA gagal: {exc}", "warning")

    return redirect(url_for("reviewer.review", doc_id=doc.id))
# ==========================================


@reviewer_bp.route("/screenshot/<path:filename>")
@login_required
def screenshot(filename):
    rev_item = ReviewItem.query.filter_by(screenshot_path=filename).first()
    if not rev_item:
        abort(404)
    doc = rev_item.review.document
    if current_user.role == ROLE_GURU and doc.user_id != current_user.id:
        abort(403)
    return send_from_directory(current_app.config["SCREENSHOT_UPLOAD_FOLDER"], filename)


def _send_review_wa(doc: Document, status: str, notes: str) -> None:
    guru = User.query.get(doc.user_id)
    
    # 1. Kirim WA ke Guru
    if guru and guru.phone:
        msg_guru = f"Halo {guru.username},\n\n*REVIEW DOKUMEN SELESAI*\nJudul: {doc.title}\nStatus: *{status}*\n\nCatatan: {notes}\nSilakan login ke aplikasi untuk melihat detail & screenshot:\nhttps://progres.guardbansal.cloud"
        send_wa(guru.phone, msg_guru)

    # 2. Jika Disetujui, Kirim WA ke Editor
    if status == STATUS_DISETUJUI:
        editors = User.query.filter_by(role=ROLE_EDITOR).all()
        for ed in editors:
            if ed.phone:
                msg_editor = f"Halo {ed.username},\n\n*DOKUMEN DISETUJUI*\nGuru: {guru.username}\nJudul: {doc.title}\n\nDokumen telah disetujui dan siap diunduh di Dashboard Editor:\nhttps://progres.guardbansal.cloud"
                send_wa(ed.phone, msg_editor)