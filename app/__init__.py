import logging

from flask import Flask, jsonify, request
from flask_cors import CORS
from werkzeug.exceptions import HTTPException

from app.extensions import db, migrate, jwt, limiter

# Make database models discoverable to Flask-Migrate.
from app import models
from app.models.moderation_history import ModerationHistory

# Import API blueprints.
from app.routes.health import health_bp
from app.routes.weather import weather_bp
from app.routes.reports import reports_bp
from app.routes.auth import auth_bp
from app.routes.admin import admin_bp
from app.routes.risk import risk_bp
from app.routes.historical_floods import historical_floods_bp
from app.routes.historical_weather import historical_weather_bp
from app.routes.notifications import notifications_bp
from app.routes.admin_pages import admin_pages_bp
from app.routes.citizen_management import citizen_management_bp

from app.services.firebase_service import initialize_firebase
from app.models.revoked_token import RevokedToken

    
from datetime import datetime, timezone
    
from app.models.revoked_token import RevokedToken
from app.models.refresh_session import RefreshSession


def validate_security_config(app):
    """Validate essential application security settings."""

    if not app.config.get("SECRET_KEY"):
        raise RuntimeError(
            "SECRET_KEY is missing from application configuration."
        )

    if not app.config.get("JWT_SECRET_KEY"):
        raise RuntimeError(
            "JWT_SECRET_KEY is missing from application configuration."
        )


def configure_logging(app):
    """Configure consistent application logging."""

    log_level = getattr(
        logging,
        app.config.get("LOG_LEVEL", "INFO"),
        logging.INFO
    )

    app.logger.setLevel(log_level)

    if not app.logger.handlers:
        handler = logging.StreamHandler()
        app.logger.addHandler(handler)

    formatter = logging.Formatter(
        "[%(asctime)s] %(levelname)s "
        "%(name)s: %(message)s"
    )

    for handler in app.logger.handlers:
        handler.setFormatter(formatter)

    app.logger.propagate = False


def register_error_handlers(app):
    """Register consistent JSON error responses."""

    @app.errorhandler(HTTPException)
    def handle_http_exception(error):
        response = {
            "status": "error",
            "error": error.name,
            "message": error.description
        }

        return jsonify(response), error.code

    @app.errorhandler(Exception)
    def handle_unexpected_exception(error):
        app.logger.exception(
            "Unhandled application exception"
        )

        return jsonify({
            "status": "error",
            "error": "Internal Server Error",
            "message": "An unexpected server error occurred."
        }), 500


def create_app(config_class=None):
    """Application factory for the FloodShield backend."""

    app = Flask(__name__)

    if config_class is None:
        from app.config import DevelopmentConfig
        config_class = DevelopmentConfig

    app.config.from_object(config_class)

    configure_logging(app)
    validate_security_config(app)

    if config_class.__name__ == "ProductionConfig":
        config_class.validate_security_config()
        config_class.validate_database_config()
        config_class.validate_rate_limit_config()

    if not app.config.get("TESTING"):
        firebase_credentials_path = app.config.get(
            "FIREBASE_CREDENTIALS_PATH"
        )

        if (
            app.config.get("REQUIRE_FIREBASE")
            and not firebase_credentials_path
        ):
            raise RuntimeError(
                "FIREBASE_CREDENTIALS_PATH is required in production."
            )

        initialize_firebase(firebase_credentials_path)

    db.init_app(app)
    migrate.init_app(app, db)
    jwt.init_app(app)
    @jwt.token_in_blocklist_loader
    def check_if_token_revoked(jwt_header, jwt_payload):
        jti = jwt_payload.get("jti")
    
        if not jti:
            return True
    
        # Check individual token revocation.
        token = RevokedToken.query.filter_by(jti=jti).first()
    
        if token is not None:
            return True
    
        # Check session-family validity for access tokens.
        if jwt_payload.get("type") == "access":
            family_id = jwt_payload.get("sid")
    
            if family_id:
                now = datetime.now(timezone.utc)
    
                active_session = RefreshSession.query.filter_by(
                    family_id=family_id,
                    revoked_at=None
                ).filter(
                    RefreshSession.expires_at > now
                ).first()
    
                # No active refresh session means the family is revoked
                # or expired, so reject its access tokens.
                if active_session is None:
                    return True
    
        return False

    limiter.init_app(app)

    # Enable CORS only for explicitly configured origins. Native Android
    # clients do not need browser CORS permissions.
    allowed_origins = app.config.get("CORS_ORIGINS") or []
    if allowed_origins:
        CORS(
            app,
            resources={
                r"/api/*": {
                    "origins": allowed_origins,
                    "methods": ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
                    "allow_headers": [
                        "Authorization",
                        "Content-Type",
                        "X-CSRF-TOKEN",
                    ],
                    "expose_headers": [
                        "X-RateLimit-Limit",
                        "X-RateLimit-Remaining",
                        "Retry-After",
                    ],
                    "supports_credentials": False,
                    "max_age": 600,
                }
            },
        )

    @app.after_request
    def add_security_headers(response):
        """Apply baseline browser security headers to every response."""
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault(
            "Referrer-Policy",
            "strict-origin-when-cross-origin",
        )
        response.headers.setdefault(
            "Permissions-Policy",
            "camera=(), microphone=(), geolocation=(self)",
        )

        if request.is_secure and not app.config.get("TESTING"):
            response.headers.setdefault(
                "Strict-Transport-Security",
                "max-age=31536000; includeSubDomains",
            )

        # Authentication responses contain credentials or identity data.
        if request.path.startswith("/api/auth/") or request.path in {
            "/admin/session",
            "/admin/logout",
        }:
            response.headers["Cache-Control"] = "no-store"
            response.headers["Pragma"] = "no-cache"

        return response

    # Register API blueprints.
    app.register_blueprint(health_bp)
    app.register_blueprint(weather_bp)
    app.register_blueprint(reports_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(historical_floods_bp)
    app.register_blueprint(historical_weather_bp)
    app.register_blueprint(risk_bp)
    app.register_blueprint(notifications_bp)
    app.register_blueprint(citizen_management_bp)

    # Register dashboard pages.
    app.register_blueprint(admin_pages_bp)

    register_error_handlers(app)

    @app.route("/", methods=["GET"])
    def home():
        return {
            "application": "FloodShield",
            "message": "FloodShield Backend API is running",
            "status": "success"
        }, 200

    return app