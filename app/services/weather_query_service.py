# Reads saved weather records for a specific location.
from datetime import datetime, timezone

from app.models.weather_record import WeatherRecord


def serialize_weather_record(record):
    """Return the safe, consistent API representation of a stored observation."""

    return {
        "id": record.id,
        "latitude": record.latitude,
        "longitude": record.longitude,
        "rainfall_mm": record.rainfall_mm,
        "precipitation_interval_seconds": (
            record.precipitation_interval_seconds
        ),
        "temperature_c": record.temperature_c,
        "wind_speed_kmh": record.wind_speed_kmh,
        "source": record.source,
        "recorded_at": record.recorded_at.isoformat(),
        "created_at": (
            record.created_at.isoformat()
            if record.created_at else None
        ),
    }


def get_latest_weather(latitude, longitude):
    """
    Retrieve the latest stored weather observation for exact coordinates.
    """

    record = (
        WeatherRecord.query
        .filter_by(
            latitude=latitude,
            longitude=longitude
        )
        .order_by(
            WeatherRecord.recorded_at.desc(),
            WeatherRecord.id.desc()
        )
        .first()
    )

    if record is None:
        return None

    return serialize_weather_record(record)


def get_weather_history(latitude, longitude, limit=24):
    """Retrieve the newest stored weather observations for exact coordinates."""

    records = (
        WeatherRecord.query
        .filter_by(
            latitude=latitude,
            longitude=longitude
        )
        .order_by(
            WeatherRecord.recorded_at.desc(),
            WeatherRecord.id.desc()
        )
        .limit(limit)
        .all()
    )

    return [
        serialize_weather_record(record)
        for record in records
    ]


def get_weather_history_by_date(
    latitude,
    longitude,
    start_date,
    end_date
):
    """Retrieve stored weather observations inside an ISO 8601 time range."""

    start_datetime = datetime.fromisoformat(start_date)
    end_datetime = datetime.fromisoformat(end_date)

    if start_datetime.tzinfo is None:
        start_datetime = start_datetime.replace(tzinfo=timezone.utc)

    if end_datetime.tzinfo is None:
        end_datetime = end_datetime.replace(tzinfo=timezone.utc)

    records = (
        WeatherRecord.query
        .filter(
            WeatherRecord.latitude == latitude,
            WeatherRecord.longitude == longitude,
            WeatherRecord.recorded_at >= start_datetime,
            WeatherRecord.recorded_at <= end_datetime
        )
        .order_by(
            WeatherRecord.recorded_at.asc(),
            WeatherRecord.id.asc()
        )
        .all()
    )

    return [
        serialize_weather_record(record)
        for record in records
    ]
