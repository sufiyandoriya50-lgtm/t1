from flask import Blueprint, jsonify, request
from sqlalchemy import func, or_

from app.extensions import db
from app.models.user import User
from app.models.flood_report import FloodReport
from app.utils.auth import admin_required


citizen_management_bp = Blueprint(
    "citizen_management",
    __name__
)


def valid_pagination():
    page = request.args.get("page", default=1, type=int)
    per_page = request.args.get("per_page", default=20, type=int)

    if page < 1 or per_page < 1 or per_page > 100:
        return None, None

    return page, per_page


def serialize_citizen(user, report_count=None):
    return {
        "id": user.id,
        "name": user.name,
        "email": user.email,
        "phone_number": user.phone_number,
        "role": user.role,
        "created_at": (
            user.created_at.isoformat()
            if user.created_at else None
        ),
        "firebase_linked": bool(user.firebase_uid),
        "report_count": report_count
    }


@citizen_management_bp.route(
    "/api/admin/citizens",
    methods=["GET"]
)
@admin_required
def list_citizens():
    page, per_page = valid_pagination()

    if page is None:
        return jsonify({
            "status": "error",
            "message": "Invalid pagination parameters"
        }), 400

    search = request.args.get("search", "").strip()

    if len(search) > 120:
        return jsonify({
            "status": "error",
            "message": "Search text cannot exceed 120 characters"
        }), 400

    query = (
        db.session.query(
            User,
            func.count(FloodReport.id).label("report_count")
        )
        .outerjoin(
            FloodReport,
            FloodReport.user_id == User.id
        )
        .filter(User.role == "citizen")
        .group_by(User.id)
    )

    if search:
        pattern = f"%{search}%"
        query = query.filter(
            or_(
                User.name.ilike(pattern),
                User.email.ilike(pattern),
                User.phone_number.ilike(pattern)
            )
        )

    query = query.order_by(
        User.created_at.desc(),
        User.id.desc()
    )

    pagination = query.paginate(
        page=page,
        per_page=per_page,
        error_out=False
    )

    citizens = [
        serialize_citizen(user, report_count)
        for user, report_count in pagination.items
    ]

    return jsonify({
        "status": "success",
        "citizens": citizens,
        "pagination": {
            "total_records": pagination.total,
            "page": pagination.page,
            "per_page": pagination.per_page,
            "total_pages": pagination.pages
        }
    }), 200


@citizen_management_bp.route(
    "/api/admin/citizens/<int:citizen_id>",
    methods=["GET"]
)
@admin_required
def get_citizen_details(citizen_id):
    citizen = User.query.filter_by(
        id=citizen_id,
        role="citizen"
    ).first()

    if citizen is None:
        return jsonify({
            "status": "error",
            "message": "Citizen not found"
        }), 404

    page, per_page = valid_pagination()

    if page is None:
        return jsonify({
            "status": "error",
            "message": "Invalid pagination parameters"
        }), 400

    status_rows = (
        db.session.query(
            FloodReport.status,
            func.count(FloodReport.id)
        )
        .filter(FloodReport.user_id == citizen.id)
        .group_by(FloodReport.status)
        .all()
    )

    report_summary = {
        "total": 0,
        "pending": 0,
        "verified": 0,
        "rejected": 0
    }

    for status, count in status_rows:
        report_summary["total"] += count

        if status in report_summary:
            report_summary[status] = count

    reports_pagination = (
        FloodReport.query
        .filter_by(user_id=citizen.id)
        .order_by(
            FloodReport.created_at.desc(),
            FloodReport.id.desc()
        )
        .paginate(
            page=page,
            per_page=per_page,
            error_out=False
        )
    )

    reports = [
        {
            "id": report.id,
            "latitude": report.latitude,
            "longitude": report.longitude,
            "water_depth_cm": report.water_depth_cm,
            "description": report.description,
            "status": report.status,
            "created_at": (
                report.created_at.isoformat()
                if report.created_at else None
            )
        }
        for report in reports_pagination.items
    ]

    return jsonify({
        "status": "success",
        "citizen": serialize_citizen(citizen),
        "report_summary": report_summary,
        "reports": reports,
        "pagination": {
            "total_records": reports_pagination.total,
            "page": reports_pagination.page,
            "per_page": reports_pagination.per_page,
            "total_pages": reports_pagination.pages
        }
    }), 200