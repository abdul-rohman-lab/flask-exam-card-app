import io
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required
from openpyxl import load_workbook
from extensions import db
from models import User, TeachingAssignment, ExamSchedule, ROLE_GURU, ROLE_ADMIN
from routes.decorators import role_required

admin_bp = Blueprint("admin", __name__)

@admin_bp.route("/dashboard")
@login_required
@role_required(ROLE_ADMIN)
def dashboard():
    gurus = User.query.filter_by(role=ROLE_GURU).order_by(User.username).all()
    assignments = TeachingAssignment.query.order_by(TeachingAssignment.user_id).all()
    return render_template("admin/dashboard.html", gurus=gurus, assignments=assignments)

@admin_bp.route("/upload-teachers", methods=["POST"])
@login_required
@role_required(ROLE_ADMIN)
def upload_teachers():
    f = request.files.get("file")
    if not f or not f.filename.lower().endswith((".xlsx", ".xls")):
        flash("File harus berformat Excel (.xlsx/.xls).", "danger")
        return redirect(url_for("admin.dashboard"))

    try:
        wb = load_workbook(filename=io.BytesIO(f.read()), data_only=True)
        ws = wb.active
        created = skipped = 0
        for row in ws.iter_rows(min_row=2, values_only=True):
            if not row or not row[0]:
                continue
            username = str(row[0]).strip()
            password = str(row[1]).strip() if len(row) > 1 and row[1] else "guru123"
            phone    = str(row[2]).strip() if len(row) > 2 and row[2] else None

            if User.query.filter_by(username=username).first():
                skipped += 1
                continue
                
            u = User(username=username, role=ROLE_GURU, is_first_login=False, phone=phone)
            u.set_password(password)
            db.session.add(u)
            created += 1
        db.session.commit()
        flash(f"Berhasil membuat {created} akun. Dilewati (sudah ada): {skipped}.", "success")
    except Exception as exc:
        db.session.rollback()
        flash(f"Gagal memproses file akun: {exc}", "danger")

    return redirect(url_for("admin.dashboard"))

@admin_bp.route("/upload-mapping", methods=["POST"])
@login_required
@role_required(ROLE_ADMIN)
def upload_mapping():
    f = request.files.get("file")
    if not f or not f.filename.lower().endswith((".xlsx", ".xls")):
        flash("File harus berformat Excel (.xlsx/.xls).", "danger")
        return redirect(url_for("admin.dashboard"))

    try:
        wb = load_workbook(filename=io.BytesIO(f.read()), data_only=True)
        ws = wb.active
        headers = [str(cell.value).strip() if cell.value else "" for cell in ws[1]]
        
        db.session.query(TeachingAssignment).delete()
        
        success_count = 0
        for row in ws.iter_rows(min_row=2, values_only=True):
            if not row or not row[0] or not row[1]:
                continue
            username = str(row[0]).strip()
            subject = str(row[1]).strip()
            
            user = User.query.filter_by(username=username, role=ROLE_GURU).first()
            if not user:
                continue
                
            for i in range(2, len(headers)):
                class_name = headers[i]
                cell_value = row[i] if i < len(row) else None
                
                if class_name and cell_value is not None and str(cell_value).strip() != "":
                    ta = TeachingAssignment(user_id=user.id, subject=subject, class_name=class_name)
                    db.session.add(ta)
                    success_count += 1
                    
        db.session.commit()
        flash(f"Berhasil memproses {success_count} pemetaan mengajar.", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Gagal memproses file pemetaan: {e}", "danger")
        
    return redirect(url_for("admin.dashboard"))

@admin_bp.route("/upload-schedule", methods=["POST"])
@login_required
@role_required(ROLE_ADMIN)
def upload_schedule():
    f = request.files.get("file")
    if not f or not f.filename.lower().endswith((".xlsx", ".xls")):
        flash("File harus berformat Excel (.xlsx/.xls).", "danger")
        return redirect(url_for("admin.dashboard"))

    try:
        wb = load_workbook(filename=io.BytesIO(f.read()), data_only=True)
        ws = wb.active
        headers = [str(cell.value).strip() if cell.value else "" for cell in ws[1]]
        
        db.session.query(ExamSchedule).delete()
        
        success_count = 0
        last_date = None
        
        for row in ws.iter_rows(min_row=2, values_only=True):
            if not row:
                continue
                
            if row[0] and str(row[0]).strip() != "":
                last_date = str(row[0]).strip()
            
            if not last_date:
                continue
            
            for i in range(2, len(headers)):
                class_name = headers[i]
                cell_value = row[i] if i < len(row) else None
                
                if class_name and cell_value is not None and str(cell_value).strip() != "":
                    subject = str(cell_value).strip()
                    es = ExamSchedule(date_str=last_date, class_name=class_name, subject=subject)
                    db.session.add(es)
                    success_count += 1
                    
        db.session.commit()
        flash(f"Berhasil memproses {success_count} jadwal ujian.", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Gagal memproses file jadwal: {e}", "danger")
        
    return redirect(url_for("admin.dashboard"))

# --- FITUR EDIT & HAPUS GURU ---
@admin_bp.route("/guru/<int:user_id>/edit", methods=["POST"])
@login_required
@role_required(ROLE_ADMIN)
def edit_guru(user_id):
    user = User.query.get_or_404(user_id)
    if user.role != ROLE_GURU:
        flash("User bukan guru.", "danger")
        return redirect(url_for("admin.dashboard"))

    email       = request.form.get("email", "").strip()
    phone       = request.form.get("phone", "").strip()
    new_password = request.form.get("password", "").strip()

    if email: user.email = email
    if phone: user.phone = phone
    if new_password: user.set_password(new_password)

    db.session.commit()
    flash(f"Akun '{user.username}' berhasil diperbarui.", "success")
    return redirect(url_for("admin.dashboard"))

@admin_bp.route("/guru/<int:user_id>/delete", methods=["POST"])
@login_required
@role_required(ROLE_ADMIN)
def delete_guru(user_id):
    user = User.query.get_or_404(user_id)
    if user.role != ROLE_GURU:
        flash("User bukan guru.", "danger")
        return redirect(url_for("admin.dashboard"))
    
    username = user.username
    db.session.delete(user)
    db.session.commit()
    flash(f"Akun '{username}' berhasil dihapus.", "success")
    return redirect(url_for("admin.dashboard"))

# --- FITUR EDIT & HAPUS PEMETAAN ---
@admin_bp.route("/assignment/<int:assignment_id>/edit", methods=["POST"])
@login_required
@role_required(ROLE_ADMIN)
def edit_assignment(assignment_id):
    ta = TeachingAssignment.query.get_or_404(assignment_id)
    subject = request.form.get("subject", "").strip()
    class_name = request.form.get("class_name", "").strip()

    if subject and class_name:
        ta.subject = subject
        ta.class_name = class_name
        db.session.commit()
        flash("Data pemetaan berhasil diperbarui.", "success")
    else:
        flash("Mapel dan Kelas tidak boleh kosong.", "danger")
        
    return redirect(url_for("admin.dashboard"))

@admin_bp.route("/assignment/<int:assignment_id>/delete", methods=["POST"])
@login_required
@role_required(ROLE_ADMIN)
def delete_assignment(assignment_id):
    ta = TeachingAssignment.query.get_or_404(assignment_id)
    db.session.delete(ta)
    db.session.commit()
    flash("Data pemetaan berhasil dihapus.", "success")
    return redirect(url_for("admin.dashboard"))