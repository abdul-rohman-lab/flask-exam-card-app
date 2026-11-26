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
    
    # AMBIL SEMUA DRAFT YANG ADA
    drafts = {r.document_id: r for r in Review.query.filter_by(is_draft=True).all()}
    
    # Kirim data drafts ke template
    return render_template("reviewer/dashboard.html", docs=docs, drafts=drafts)

@reviewer_bp.route("/document/<int:doc_id>", methods=["GET", "POST"])
@login_required
@role_required(ROLE_REVIEWER)
def review(doc_id):
    doc = Document.query.get_or_404(doc_id)

    if request.method == "POST":
        target_status = request.form.get("status")
        action = request.form.get("action", "final") 

        if target_status not in ALL_STATUSES:
            flash("Status tidak valid.", "danger")
            return redirect(url_for("reviewer.review", doc_id=doc_id))

        # Cari apakah ada draft terakhir untuk dokumen ini
        last_draft = Review.query.filter_by(document_id=doc.id, is_draft=True).order_by(Review.created_at.desc()).first()

        if action == 'draft':
            # LOGIKA SIMPAN DRAFT
            if not last_draft:
                last_draft = Review(document_id=doc.id, is_draft=True)
                db.session.add(last_draft)
            
            last_draft.status = "Draf"
            last_draft.target_status = target_status
            db.session.flush()
            
            # Hapus item draft lama, ganti dengan yang baru
            ReviewItem.query.filter_by(review_id=last_draft.id).delete()
            review_to_update = last_draft
            
            flash("Draf berhasil disimpan. Status dokumen belum berubah. WA belum dikirim.", "info")

        else:
            # LOGIKA FINALISASI
            if last_draft:
                # Jika ada draft, ubah draft menjadi final
                last_draft.is_draft = False
                last_draft.status = target_status
                db.session.flush()
                ReviewItem.query.filter_by(review_id=last_draft.id).delete()
                review_to_update = last_draft
            else:
                # Jika tidak ada draft (langsung final)
                review_to_update = Review(document_id=doc.id, status=target_status, is_draft=False)
                db.session.add(review_to_update)
                db.session.flush()

            # Ubah status dokumen utama
            doc.status = target_status
            flash("Review difinalisasi & WA terkirim.", "success")

        # Proses Upload Gambar & Catatan (sama untuk draft maupun final)
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
                    elif shot.content_type == 'image/jpeg': ext = 'jpg'
                    elif shot.content_type == 'image/gif': ext = 'gif'
                    elif shot.content_type == 'image/webp': ext = 'webp'
                    elif shot.content_type == 'image/bmp': ext = 'bmp'

                    if ext in current_app.config["ALLOWED_IMG_EXTENSIONS"]:
                        base_name = secure_filename(shot.filename) if shot.filename else "pasted_image"
                        if not base_name.lower().endswith(f".{ext}"):
                            base_name = f"{base_name}.{ext}"
                        stored_name = f"{doc_id}_{uuid.uuid4().hex}_{base_name}"
                        shot.save(os.path.join(current_app.config["SCREENSHOT_UPLOAD_FOLDER"], stored_name))

                item = ReviewItem(review_id=review_to_update.id, screenshot_path=stored_name, notes=catatan, order=i)
                db.session.add(item)

        db.session.commit()

        if action == 'final':
            try:
                _send_review_wa(doc, target_status, "Silakan cek aplikasi untuk detail gambar dan catatan.")
            except Exception as exc:
                flash(f"Review tersimpan, namun WA gagal: {exc}", "warning")

        return redirect(url_for("reviewer.review", doc_id=doc_id))

    # Ambil riwayat, pisahkan draft dan final
    draft = Review.query.filter_by(document_id=doc.id, is_draft=True).order_by(Review.created_at.desc()).first()
    history = Review.query.filter_by(document_id=doc.id, is_draft=False).order_by(Review.created_at.desc()).all()
    
    return render_template("reviewer/detail.html", doc=doc, history=history, draft=draft)

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

    review.status = status
    items = sorted(review.items, key=lambda x: x.order)
    for i, item in enumerate(items):
        if i < len(notes_list):
            item.notes = notes_list[i].strip()

    latest_review = Review.query.filter_by(document_id=doc.id, is_draft=False).order_by(Review.created_at.desc()).first()
    if latest_review and latest_review.id == review.id:
        doc.status = status

    db.session.commit()
    try:
        _send_review_wa(doc, status, "Review telah diperbarui oleh Bu Nelly. Silakan cek aplikasi untuk detail terbarunya.")
        flash("Riwayat review berhasil diperbarui & WA notifikasi terkirim.", "success")
    except Exception as exc:
        flash(f"Riwayat review diperbarui, namun WA gagal: {exc}", "warning")

    return redirect(url_for("reviewer.review", doc_id=doc.id))

@reviewer_bp.route("/screenshot/<path:filename>")
@login_required
def screenshot(filename):
    rev_item = ReviewItem.query.filter_by(screenshot_path=filename).first()
    if not rev_item: abort(404)
    doc = rev_item.review.document
    if current_user.role == ROLE_GURU and doc.user_id != current_user.id: abort(403)
    return send_from_directory(current_app.config["SCREENSHOT_UPLOAD_FOLDER"], filename)

def _send_review_wa(doc: Document, status: str, notes: str) -> None:
    guru = User.query.get(doc.user_id)
    if guru and guru.phone:
        msg_guru = f"Bismillahirrahmanirrahim Bapak/Ibu {guru.username},\n\n*REVIEW DOKUMEN SELESAI*\nJudul: {doc.title}\nStatus: *{status}*\n\nCatatan: {notes}\nSilakan login ke aplikasi untuk melihat detail & screenshot:\nhttps://progres.guardbansal.cloud"
        send_wa(guru.phone, msg_guru)

    if status == STATUS_DISETUJUI:
        editors = User.query.filter_by(role=ROLE_EDITOR).all()
        for ed in editors:
            if ed.phone:
                msg_editor = f"Bismillahirrahmanirrahim Bapak/Ibu {ed.username},\n\n*DOKUMEN DISETUJUI*\nGuru: {guru.username}\nJudul: {doc.title}\n\nDokumen telah disetujui oleh Bu Nelly dan siap diunduh di Dashboard Editor:\nhttps://progres.guardbansal.cloud"
                send_wa(ed.phone, msg_editor)