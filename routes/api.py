from flask import Blueprint, jsonify, request
from flask_login import login_required, current_user
from extensions import db
from models import Document, ALL_STATUSES, ROLE_GURU, ROLE_REVIEWER

api_bp = Blueprint("api", __name__)


@api_bp.route("/me")
@login_required
def me():
    return jsonify({
        "id": current_user.id,
        "username": current_user.username,
        "role": current_user.role,
        "email": current_user.email,
        "is_first_login": current_user.is_first_login,
    })


@api_bp.route("/documents")
@login_required
def list_documents():
    if current_user.role == ROLE_GURU:
        docs = Document.query.filter_by(user_id=current_user.id).all()
    elif current_user.role in ("reviewer", "editor", "admin"):
        docs = Document.query.all()
    else:
        return jsonify({"error": "forbidden"}), 403

    return jsonify([{
        "id": d.id,
        "user_id": d.user_id,
        "username": d.owner.username,
        "filename": d.filename,
        "status": d.status,
        "created_at": d.created_at.isoformat(),
        "updated_at": d.updated_at.isoformat(),
    } for d in docs])


@api_bp.route("/documents/<int:doc_id>")
@login_required
def get_document(doc_id):
    d = Document.query.get_or_404(doc_id)
    if current_user.role == ROLE_GURU and d.user_id != current_user.id:
        return jsonify({"error": "forbidden"}), 403
    return jsonify({
        "id": d.id, "filename": d.filename, "status": d.status,
        "user_id": d.user_id, "username": d.owner.username,
        "created_at": d.created_at.isoformat(),
        "updated_at": d.updated_at.isoformat(),
    })


@api_bp.route("/documents/<int:doc_id>/reviews")
@login_required
def get_reviews(doc_id):
    d = Document.query.get_or_404(doc_id)
    if current_user.role == ROLE_GURU and d.user_id != current_user.id:
        return jsonify({"error": "forbidden"}), 403
    return jsonify([{
        "id": r.id,
        "notes": r.notes,
        "screenshot_path": r.screenshot_path,
        "created_at": r.created_at.isoformat(),
    } for r in d.reviews])


@api_bp.route("/documents/<int:doc_id>/status", methods=["PATCH"])
@login_required
def update_status(doc_id):
    if current_user.role != ROLE_REVIEWER:
        return jsonify({"error": "forbidden"}), 403
    d = Document.query.get_or_404(doc_id)
    data = request.get_json(silent=True) or {}
    if data.get("status") not in ALL_STATUSES:
        return jsonify({"error": "invalid status"}), 400
    d.status = data["status"]
    db.session.commit()
    return jsonify({"ok": True, "status": d.status})