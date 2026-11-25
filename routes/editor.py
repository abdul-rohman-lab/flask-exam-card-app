import io
from flask import Blueprint, render_template, send_file
from flask_login import login_required
from openpyxl import Workbook
from models import Document, User, TeachingAssignment, ExamSchedule, ROLE_EDITOR, STATUS_DISETUJUI, STATUS_REVISI, STATUS_SUDAH_DIREVISI, STATUS_UPLOAD_BARU
from routes.decorators import role_required
from collections import defaultdict

editor_bp = Blueprint("editor", __name__)

@editor_bp.route("/dashboard")
@login_required
@role_required(ROLE_EDITOR)
def dashboard():
    schedules = ExamSchedule.query.order_by(ExamSchedule.id).all()
    
    classes_set = set()
    for s in schedules:
        classes_set.add(s.class_name)
    classes_list = sorted(list(classes_set))
    
    matrix = defaultdict(lambda: defaultdict(list))
    
    for s in schedules:
        teacher_assign = TeachingAssignment.query.filter_by(subject=s.subject, class_name=s.class_name).first()
        
        teacher_name = teacher_assign.user.username if teacher_assign else "Guru Tidak Diketahui"
        status = "Belum Upload"
        color_class = "bg-danger" # Merah Default
        
        if teacher_assign:
            doc = Document.query.filter(
                Document.user_id == teacher_assign.user_id, 
                Document.subject == s.subject, 
                Document.classes.like(f'%{s.class_name}%')
            ).order_by(Document.updated_at.desc()).first()
            
            if doc:
                status = doc.status
                if status == STATUS_DISETUJUI:
                    color_class = "bg-success" # Hijau
                elif status == STATUS_REVISI or status == STATUS_SUDAH_DIREVISI:
                    color_class = "bg-warning text-dark" # Kuning
                elif status == STATUS_UPLOAD_BARU:
                    color_class = "bg-primary" # Biru
                    
        matrix[s.date_str][s.class_name].append({
            "subject": s.subject,
            "teacher": teacher_name,
            "status": status,
            "color": color_class
        })
        
    return render_template("editor/dashboard.html", matrix=matrix, classes=classes_list)

@editor_bp.route("/export-approved")
@login_required
@role_required(ROLE_EDITOR)
def export_approved():
    docs = (
        Document.query.filter_by(status=STATUS_DISETUJUI)
        .order_by(Document.updated_at.desc()).all()
    )
    
    wb = Workbook()
    ws = wb.active
    ws.title = "Disetujui"
    
    ws.append(["No", "Guru", "Email", "Judul Dokumen", "Link File", "Tanggal Disetujui"])
    
    for i, d in enumerate(docs, 1):
        ws.append([
            i, 
            d.owner.username, 
            d.owner.email or "-",
            d.title or d.filename,
            d.file_path,
            d.updated_at.strftime("%Y-%m-%d %H:%M"),
        ])

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return send_file(
        buf, as_attachment=True,
        download_name="kartu_soal_disetujui.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )