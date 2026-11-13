
from datetime import datetime

from flask import Blueprint, jsonify, request

from app.services.weather_service import get_current_weather
from app.services.weather_storage_service import save_weather_record
from app.services.weather_query_service import (
    get_latest_weather,
    get_weather_history,
    get_weather_history_by_date,
)
from app.utils.auth import admin_required


weather_bp = Blueprint("weather", __name__)


# Validates geographical coordinates supplied to weather endpoints.
def validate_coordinates(latitude, longitude):
    if latitude is None or longitude is None:
        return False

    return (
        -90 <= latitude <= 90
        and -180 <= longitude <= 180
    )


# Retrieves current weather data from Open-Meteo.
@weather_bp.route("/api/weather/current", methods=["GET"])
def current_weather():
    latitude = request.args.get("latitude", type=float)
    longitude = request.args.get("longitude", type=float)

    if not validate_coordinates(latitude, longitude):
        return jsonify({
            "status": "error",
            "message": "Valid latitude and longitude are required"
        }), 400

    try:
        weather = get_current_weather(latitude, longitude)

        return jsonify({
            "status": "success",
            "message": "Weather fetched successfully",
            "data": weather
        }), 200

    except ValueError as error:
        return jsonify({
            "status": "error",
            "message": str(error)
        }), 400

    except RuntimeError as error:
        return jsonify({
            "status": "error",
            "message": str(error)
        }), 502


# Fetches current weather and saves it; restricted to administrators.
@weather_bp.route("/api/weather/collect", methods=["POST"])
@admin_required
def collect_weather():
    latitude = request.args.get("latitude", type=float)
    longitude = request.args.get("longitude", type=float)

    if not validate_coordinates(latitude, longitude):
        return jsonify({
            "status": "error",
            "message": "Valid latitude and longitude are required"
        }), 400

    try:
        weather = get_current_weather(latitude, longitude)
        saved_record = save_weather_record(weather)

        return jsonify({
            "status": "success",
            "message": "Weather fetched and saved successfully",
            "data": {
                **weather,
                "database_record_id": saved_record.id
            }
        }), 201

    except ValueError as error:
        return jsonify({
            "status": "error",
            "message": str(error)
        }), 400

    except RuntimeError as error:
        return jsonify({
            "status": "error",
            "message": str(error)
        }), 502


# Retrieves the latest stored weather record for supplied coordinates.
@weather_bp.route("/api/weather/latest", methods=["GET"])
def latest_weather():
    latitude = request.args.get("latitude", type=float)
    longitude = request.args.get("longitude", type=float)

    if not validate_coordinates(latitude, longitude):
        return jsonify({
            "status": "error",
            "message": "Valid latitude and longitude are required"
        }), 400

    try:
        weather = get_latest_weather(latitude, longitude)

        if weather is None:
            return jsonify({
                "status": "error",
                "message": "No weather records found for these coordinates"
            }), 404

        return jsonify({
            "status": "success",
            "data": weather
        }), 200

    except Exception:
        return jsonify({
            "status": "error",
            "message": "Unable to retrieve weather records"
        }), 500


# Retrieves a limited number of stored weather records.
@weather_bp.route("/api/weather/history", methods=["GET"])
def weather_history():
    latitude = request.args.get("latitude", type=float)
    longitude = request.args.get("longitude", type=float)
    limit = request.args.get("limit", default=24, type=int)

    if not validate_coordinates(latitude, longitude):
        return jsonify({
            "status": "error",
            "message": "Valid latitude and longitude are required"
        }), 400

    if limit < 1 or limit > 100:
        return jsonify({
            "status": "error",
            "message": "Limit must be between 1 and 100"
        }), 400

    try:
        records = get_weather_history(latitude, longitude, limit)

        return jsonify({
            "status": "success",
            "count": len(records),
            "data": records
        }), 200

    except Exception:
        return jsonify({
            "status": "error",
            "message": "Unable to retrieve weather history"
        }), 500


# Retrieves stored weather records within an ISO 8601 date range.
@weather_bp.route("/api/weather/history/date-range", methods=["GET"])
def weather_history_date_range():
    latitude = request.args.get("latitude", type=float)
    longitude = request.args.get("longitude", type=float)
    start_date = request.args.get("start_date")
    end_date = request.args.get("end_date")

    if (
        not validate_coordinates(latitude, longitude)
        or not start_date
        or not end_date
    ):
        return jsonify({
            "status": "error",
            "message": (
                "Valid latitude, longitude, start_date and end_date are required"
            )
        }), 400

    try:
        start_datetime = datetime.fromisoformat(start_date)
        end_datetime = datetime.fromisoformat(end_date)

        if start_datetime > end_datetime:
            return jsonify({
                "status": "error",
                "message": "start_date must be before or equal to end_date"
            }), 400

        records = get_weather_history_by_date(
            latitude,
            longitude,
            start_date,
            end_date
        )

        return jsonify({
            "status": "success",
            "count": len(records),
            "data": records
        }), 200

    except ValueError:
        return jsonify({
            "status": "error",
            "message": "Invalid date format. Use ISO 8601 format."
        }), 400

    except Exception:
        return jsonify({
            "status": "error",
            "message": "Unable to retrieve weather records"
        }), 500
