import io
import difflib
from flask import Blueprint, render_template, send_file, request, jsonify
from flask_login import login_required
from openpyxl import Workbook
from models import Document, User, TeachingAssignment, ExamSchedule, ROLE_EDITOR, STATUS_DISETUJUI, STATUS_REVISI, STATUS_SUDAH_DIREVISI, STATUS_UPLOAD_BARU
from routes.decorators import role_required
from collections import defaultdict
from extensions import db

editor_bp = Blueprint("editor", __name__)

def normalize_text(text):
    if not text: return ""
    text = str(text).lower().strip()
    text = text.replace("&", "dan")
    return " ".join(text.split())

def is_similar(str1, str2):
    s1 = normalize_text(str1)
    s2 = normalize_text(str2)
    if s1 == s2: return True
    if difflib.SequenceMatcher(None, s1, s2).ratio() > 0.75: return True
    if s1 in s2 or s2 in s1: return True
    return False

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
        assigns = TeachingAssignment.query.filter_by(class_name=s.class_name).all()
        teacher_assign = None
        for ta in assigns:
            if is_similar(s.subject, ta.subject):
                teacher_assign = ta
                break
                
        teacher_name = teacher_assign.user.username if teacher_assign else "Guru Tidak Diketahui"
        status = "Belum Upload"
        color_class = "bg-danger"
        
        # Data Default untuk dikirim ke HTML
        doc_data = {
            "doc_id": None,
            "duplicate_link": None,
            "collab_link": None,
            "is_processed": False,
            "status": status,
            "color": color_class,
            "teacher": teacher_name,
            "subject": s.subject
        }
        
        if teacher_assign:
            docs = Document.query.filter_by(user_id=teacher_assign.user_id).order_by(Document.updated_at.desc()).all()
            matched_doc = None
            for doc in docs:
                if s.class_name in doc.classes and is_similar(s.subject, doc.subject):
                    matched_doc = doc
                    break
            
            if matched_doc:
                doc_data["doc_id"] = matched_doc.id
                doc_data["duplicate_link"] = matched_doc.duplicate_link
                doc_data["collab_link"] = matched_doc.collab_link
                doc_data["is_processed"] = matched_doc.is_processed
                doc_data["status"] = matched_doc.status
                
                # Logika Warna
                if matched_doc.status == STATUS_DISETUJUI:
                    if matched_doc.is_processed:
                        doc_data["color"] = "bg-secondary opacity-75" # Abu-abu (Selesai)
                    elif matched_doc.duplicate_link and matched_doc.collab_link:
                        doc_data["color"] = "bg-success" # Hijau (Link Lengkap)
                    else:
                        doc_data["color"] = "bg-info text-dark" # Cyan (Link Belum Lengkap)
                elif matched_doc.status in [STATUS_REVISI, STATUS_SUDAH_DIREVISI]:
                    doc_data["color"] = "bg-warning text-dark" # Kuning
                elif matched_doc.status == STATUS_UPLOAD_BARU:
                    doc_data["color"] = "bg-primary" # Biru
                    
        matrix[s.date_str][s.class_name].append(doc_data)
        
    return render_template("editor/dashboard.html", matrix=matrix, classes=classes_list)

# ROUTE BARU: Untuk menyimpan checkbox secara background (AJAX)
@editor_bp.route("/toggle-processed/<int:doc_id>", methods=["POST"])
@login_required
@role_required(ROLE_EDITOR)
def toggle_processed(doc_id):
    doc = Document.query.get_or_404(doc_id)
    data = request.get_json()
    
    if 'is_processed' in data:
        doc.is_processed = bool(data['is_processed'])
        db.session.commit()
        return jsonify({"success": True, "is_processed": doc.is_processed})
        
    return jsonify({"success": False}), 400

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
            i, d.owner.username, d.owner.email or "-",
            d.title or d.filename, d.file_path,
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