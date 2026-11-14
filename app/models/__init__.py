
"""
FloodShield database models.

All database models are imported here so that
SQLAlchemy and Flask-Migrate can discover them.
"""


"""
FloodShield database models.

All database models are imported here so that
SQLAlchemy and Flask-Migrate can discover them.
"""


from app.models.user import User
from app.models.flood_report import FloodReport
from app.models.weather_record import WeatherRecord
from app.models.risk_assessment import RiskAssessment
from app.models.report_media import FloodReportMedia
from app.models.moderation_history import ModerationHistory
from app.models.historical_flood_event import HistoricalFloodEvent
from app.models.historical_weather_record import HistoricalWeatherRecord
from app.models.notification import Notification
from app.models.device_token import DeviceToken
from app.models.notification_preference import NotificationPreference


# Authentication models
from app.models.email_verification_token import EmailVerificationToken
from app.models.password_reset_token import PasswordResetToken
from app.models.phone_otp_challenge import PhoneOtpChallenge
from app.models.refresh_session import RefreshSession
from app.models.revoked_token import RevokedToken
from app.models.pending_email_change import PendingEmailChange
#this __all__ defines what will be impoterd whensomeone does  from app.models import *

__all__ = [
    "User",
    "FloodReport",
    "WeatherRecord",
    "RiskAssessment",
    "FloodReportMedia",
    "ModerationHistory",
    "HistoricalFloodEvent",
    "HistoricalWeatherRecord",
    "Notification",
    "DeviceToken",
    "NotificationPreference",
    "EmailVerificationToken",
    "PasswordResetToken",
    "PhoneOtpChallenge",
    "RefreshSession",
    "RevokedToken",
    "PendingEmailChange",
]
