import logging

from flask import Flask, jsonify
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
    limiter.init_app(app)

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