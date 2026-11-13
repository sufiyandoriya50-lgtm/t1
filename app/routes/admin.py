
import math
from datetime import datetime, timezone

from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt_identity
from sqlalchemy import func, or_

from app.extensions import db
from app.models.flood_report import FloodReport
from app.models.moderation_history import ModerationHistory
from app.services.media_service import get_report_media
from app.services.report_service import update_report_status
from app.utils.auth import admin_required
from app.utils.geo import calculate_distance_km


admin_bp = Blueprint("admin", __name__)


# Parses an optional ISO 8601 date/time value into a UTC-aware datetime.
def parse_admin_datetime(value):
    if not value:
        return None

    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)

    return parsed


# Retrieves all paginated flood reports waiting for administrator review.
# GET /api/admin/reports/pending
@admin_bp.route("/api/admin/reports/pending", methods=["GET"])
@admin_required
def get_pending_reports():

    page = request.args.get("page", default=1, type=int)
    per_page = request.args.get("per_page", default=20, type=int)

    if page < 1 or per_page < 1 or per_page > 100:
        return jsonify({
            "status": "error",
            "message": "Invalid pagination parameters"
        }), 400

    pagination = (
        FloodReport.query
        .filter_by(status="pending")
        .order_by(FloodReport.created_at.desc(), FloodReport.id.desc())
        .paginate(page=page, per_page=per_page, error_out=False)
    )

    reports = []

    for report in pagination.items:
        reports.append({
            "id": report.id,
            "user_id": report.user_id,
            "latitude": report.latitude,
            "longitude": report.longitude,
            "water_depth_cm": report.water_depth_cm,
            "description": report.description,
            "status": report.status,
            "created_at": (
                report.created_at.isoformat()
                if report.created_at else None
            )
        })

    return jsonify({
        "status": "success",
        "total_reports": pagination.total,
        "current_page": pagination.page,
        "per_page": pagination.per_page,
        "total_pages": pagination.pages,
        "reports": reports
    }), 200


# Retrieves full details of one flood report, including reporter and attached photos.
# GET /api/admin/reports/<report_id>
@admin_bp.route("/api/admin/reports/<int:report_id>", methods=["GET"])
@admin_required
def get_admin_report_details(report_id):

    report = db.session.get(FloodReport, report_id)

    if report is None:
        return jsonify({
            "status": "error",
            "message": "Flood report not found"
        }), 404

    report_data = {
        "id": report.id,
        "latitude": report.latitude,
        "longitude": report.longitude,
        "water_depth_cm": report.water_depth_cm,
        "description": report.description,
        "status": report.status,
        "created_at": (
            report.created_at.isoformat()
            if report.created_at else None
        ),
        "reporter": {
            "id": report.user.id,
            "name": report.user.name
        },
        "media": get_report_media(report.id)
    }

    return jsonify({
        "status": "success",
        "report": report_data
    }), 200


# Allows an administrator to verify a citizen's flood report.
# PATCH /api/admin/reports/<report_id>/verify
@admin_bp.route(
    "/api/admin/reports/<int:report_id>/verify",
    methods=["PATCH"]
)
@admin_required
def verify_flood_report(report_id):

    try:
        admin_id = int(get_jwt_identity())

        report = update_report_status(
            report_id=report_id,
            new_status="verified",
            admin_id=admin_id
        )

        if report is None:
            return jsonify({
                "status": "error",
                "message": "Flood report not found"
            }), 404

        return jsonify({
            "status": "success",
            "message": "Flood report verified successfully",
            "report_id": report.id,
            "report_status": report.status
        }), 200

    except Exception:
        db.session.rollback()
        return jsonify({
            "status": "error",
            "message": "Unable to verify flood report"
        }), 500


# Allows an administrator to reject an invalid or misleading flood report.
# PATCH /api/admin/reports/<report_id>/reject
@admin_bp.route(
    "/api/admin/reports/<int:report_id>/reject",
    methods=["PATCH"]
)
@admin_required
def reject_flood_report(report_id):

    try:
        admin_id = int(get_jwt_identity())

        report = update_report_status(
            report_id=report_id,
            new_status="rejected",
            admin_id=admin_id
        )

        if report is None:
            return jsonify({
                "status": "error",
                "message": "Flood report not found"
            }), 404

        return jsonify({
            "status": "success",
            "message": "Flood report rejected successfully",
            "report_id": report.id,
            "report_status": report.status
        }), 200

    except Exception:
        db.session.rollback()
        return jsonify({
            "status": "error",
            "message": "Unable to reject flood report"
        }), 500


# Retrieves the moderation history of a flood report.
# GET /api/admin/reports/<report_id>/history
@admin_bp.route(
    "/api/admin/reports/<int:report_id>/history",
    methods=["GET"]
)
@admin_required
def get_report_moderation_history(report_id):

    report = db.session.get(FloodReport, report_id)

    if report is None:
        return jsonify({
            "status": "error",
            "message": "Flood report not found"
        }), 404

    history_records = (
        ModerationHistory.query
        .filter_by(report_id=report_id)
        .order_by(
            ModerationHistory.created_at.desc(),
            ModerationHistory.id.desc()
        )
        .all()
    )

    history = []

    for record in history_records:
        history.append({
            "id": record.id,
            "report_id": record.report_id,
            "admin_id": record.admin_id,
            "admin_name": record.admin.name,
            "previous_status": record.previous_status,
            "new_status": record.new_status,
            "created_at": (
                record.created_at.isoformat()
                if record.created_at else None
            )
        })

    return jsonify({
        "status": "success",
        "report_id": report_id,
        "total_actions": len(history),
        "history": history
    }), 200


# Retrieves report totals, status breakdown and the five most recent reports.
# GET /api/admin/dashboard/stats
@admin_bp.route(
    "/api/admin/dashboard/stats",
    methods=["GET"]
)
@admin_required
def get_admin_dashboard_stats():

    status_results = (
        db.session.query(
            FloodReport.status,
            func.count(FloodReport.id)
        )
        .group_by(FloodReport.status)
        .all()
    )

    status_counts = {
        "pending": 0,
        "verified": 0,
        "rejected": 0
    }

    for status, count in status_results:
        if status in status_counts:
            status_counts[status] = count

    total_reports = sum(status_counts.values())

    recent_reports = (
        FloodReport.query
        .order_by(
            FloodReport.created_at.desc(),
            FloodReport.id.desc()
        )
        .limit(5)
        .all()
    )

    recent_data = []

    for report in recent_reports:
        recent_data.append({
            "id": report.id,
            "latitude": report.latitude,
            "longitude": report.longitude,
            "status": report.status,
            "description": report.description,
            "created_at": (
                report.created_at.isoformat()
                if report.created_at else None
            )
        })

    return jsonify({
        "status": "success",
        "statistics": {
            "total_reports": total_reports,
            "pending_reports": status_counts["pending"],
            "verified_reports": status_counts["verified"],
            "rejected_reports": status_counts["rejected"]
        },
        "recent_reports": recent_data
    }), 200


# Searches reports using database-side filters and efficient pagination.
# GET /api/admin/reports
@admin_bp.route("/api/admin/reports", methods=["GET"])
@admin_required
def search_admin_reports():

    status = request.args.get("status", "").strip().lower()
    search = request.args.get("search", "").strip()

    latitude_raw = request.args.get("latitude")
    longitude_raw = request.args.get("longitude")
    radius_raw = request.args.get("radius_km")

    start_date = request.args.get("start_date")
    end_date = request.args.get("end_date")

    page = request.args.get("page", default=1, type=int)
    per_page = request.args.get("per_page", default=20, type=int)

    allowed_statuses = {"pending", "verified", "rejected"}

    if status and status not in allowed_statuses:
        return jsonify({
            "status": "error",
            "message": "Invalid status filter"
        }), 400

    if page < 1 or per_page < 1 or per_page > 100:
        return jsonify({
            "status": "error",
            "message": "Invalid pagination parameters"
        }), 400

    if len(search) > 200:
        return jsonify({
            "status": "error",
            "message": "Search text cannot exceed 200 characters"
        }), 400

    # Parse and validate optional geographic filters.
    latitude = None
    longitude = None
    radius_km = None

    location_values = (
        latitude_raw,
        longitude_raw,
        radius_raw
    )

    if any(value is not None for value in location_values):

        if any(
            value is None or not value.strip()
            for value in location_values
        ):
            return jsonify({
                "status": "error",
                "message": (
                    "latitude, longitude and radius_km "
                    "are all required"
                )
            }), 400

        try:
            latitude = float(latitude_raw)
            longitude = float(longitude_raw)
            radius_km = float(radius_raw)

        except (TypeError, ValueError):
            return jsonify({
                "status": "error",
                "message": "Invalid geographic filter values"
            }), 400

        if not all(map(
            math.isfinite,
            (latitude, longitude, radius_km)
        )):
            return jsonify({
                "status": "error",
                "message": "Geographic values must be finite numbers"
            }), 400

        if (
            not -90 <= latitude <= 90
            or not -180 <= longitude <= 180
            or not 0 < radius_km <= 500
        ):
            return jsonify({
                "status": "error",
                "message": "Invalid location or radius values"
            }), 400

    # Parse date filters.
    try:
        parsed_start = parse_admin_datetime(start_date)
        parsed_end = parse_admin_datetime(end_date)

        if (
            parsed_start is not None
            and parsed_end is not None
            and parsed_start > parsed_end
        ):
            return jsonify({
                "status": "error",
                "message": "Start date must not be after end date"
            }), 400

    except (ValueError, TypeError):
        return jsonify({
            "status": "error",
            "message": "Dates must be valid ISO 8601 date/time values"
        }), 400

    # Build the query using database-side filtering.
    query = FloodReport.query

    if status:
        query = query.filter(FloodReport.status == status)

    if search:
        query = query.filter(
            FloodReport.description.ilike(f"%{search}%")
        )

    if parsed_start is not None:
        query = query.filter(
            FloodReport.created_at >= parsed_start
        )

    if parsed_end is not None:
        query = query.filter(
            FloodReport.created_at <= parsed_end
        )

    # Apply a geographic bounding box before exact distance checks.
    if latitude is not None:

        # Approximate kilometres per degree of latitude.
        latitude_delta = radius_km / 111.045

        min_latitude = max(-90, latitude - latitude_delta)
        max_latitude = min(90, latitude + latitude_delta)

        query = query.filter(
            FloodReport.latitude >= min_latitude,
            FloodReport.latitude <= max_latitude
        )

        # Near the poles, longitude is not a useful bounding constraint.
        if min_latitude > -90 and max_latitude < 90:

            longitude_scale = math.cos(math.radians(latitude))

            if longitude_scale > 0:
                longitude_delta = min(
                    180,
                    radius_km / (111.045 * longitude_scale)
                )

                min_longitude = longitude - longitude_delta
                max_longitude = longitude + longitude_delta

                if longitude_delta < 180:

                    if min_longitude < -180:
                        query = query.filter(
                            or_(
                                FloodReport.longitude >= (
                                    min_longitude + 360
                                ),
                                FloodReport.longitude <= max_longitude
                            )
                        )

                    elif max_longitude > 180:
                        query = query.filter(
                            or_(
                                FloodReport.longitude >= min_longitude,
                                FloodReport.longitude <= (
                                    max_longitude - 360
                                )
                            )
                        )

                    else:
                        query = query.filter(
                            FloodReport.longitude >= min_longitude,
                            FloodReport.longitude <= max_longitude
                        )

    # Stable ordering prevents reports from moving between pages
    # when multiple reports have identical timestamps.
    query = query.order_by(
        FloodReport.created_at.desc(),
        FloodReport.id.desc()
    )

    # Without geographic filtering, let the database perform
    # the count and pagination instead of loading every report.
    if latitude is None:

        total_reports = query.count()

        paginated_reports = (
            query
            .offset((page - 1) * per_page)
            .limit(per_page)
            .all()
        )

    else:
        # The bounding box is an approximation. Calculate the exact
        # distance for its candidates before calculating pagination.
        candidates = query.all()

        filtered_reports = []

        for report in candidates:
            distance = calculate_distance_km(
                latitude,
                longitude,
                report.latitude,
                report.longitude
            )

            if distance <= radius_km:
                filtered_reports.append(report)

        total_reports = len(filtered_reports)

        start_index = (page - 1) * per_page
        end_index = start_index + per_page

        paginated_reports = filtered_reports[
            start_index:end_index
        ]

    report_data = []

    for report in paginated_reports:
        report_data.append({
            "id": report.id,
            "user_id": report.user_id,
            "latitude": report.latitude,
            "longitude": report.longitude,
            "water_depth_cm": report.water_depth_cm,
            "description": report.description,
            "status": report.status,
            "created_at": (
                report.created_at.isoformat()
                if report.created_at else None
            )
        })

    total_pages = (
        (total_reports + per_page - 1) // per_page
    )

    return jsonify({
        "status": "success",
        "total_reports": total_reports,
        "current_page": page,
        "per_page": per_page,
        "total_pages": total_pages,
        "reports": report_data
    }), 200
