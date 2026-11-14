
import pytest
from firebase_admin import messaging

from app.extensions import db
from app.models.user import User
from app.models.notification import Notification
from app.models.device_token import DeviceToken
from app.services.notification_service import send_notification


# Creates a valid citizen account for notification service tests.
@pytest.fixture()
def test_user(app):
    with app.app_context():
        user = User(
            name="Test Citizen",
            email="notification_test@example.com"
        )
        user.set_password("TestPassword123")

        db.session.add(user)
        db.session.commit()

        user_id = user.id

        yield user_id


# Tests that a notification is saved when the user has no active devices.
def test_notification_saved_when_no_devices(app, test_user):
    with app.app_context():
        notification = send_notification(
            user_id=test_user,
            title="Flood Alert",
            message="High flood risk detected in your area.",
            risk_level="high"
        )

        saved_notification = db.session.get(
            Notification,
            notification.id
        )

        assert saved_notification is not None
        assert saved_notification.delivery_status == "no_devices"
        assert saved_notification.risk_level == "high"


# Tests successful delivery to a registered device using mocked Firebase.
def test_notification_sent_successfully(app, test_user, monkeypatch):
    with app.app_context():
        device = DeviceToken(
            user_id=test_user,
            token="test-fcm-registration-token",
            fid=None,
            platform="android",
            is_active=True
        )
        db.session.add(device)
        db.session.commit()

        # Pretend Firebase has already been initialized.
        monkeypatch.setattr(
            "app.services.notification_service.firebase_admin.get_app",
            lambda: object()
        )

        # Pretend Firebase successfully accepts the message and capture
        # the destination to prove the FCM token (not the legacy FID) is used.
        sent_messages = []

        def mock_send(message, app=None):
            sent_messages.append(message)
            return "mock-message-id"

        monkeypatch.setattr(
            "app.services.notification_service.messaging.send",
            mock_send
        )

        notification = send_notification(
            user_id=test_user,
            title="Flood Alert",
            message="Severe flood risk detected.",
            risk_level="severe"
        )

        assert notification.delivery_status == "sent"
        assert len(sent_messages) == 1
        assert sent_messages[0].token == "test-fcm-registration-token"


# Tests that Firebase-invalid device tokens are deactivated.
# Tests that Firebase-invalid device tokens are deactivated.
def test_unregistered_device_token_is_deactivated(
    app,
    test_user,
    monkeypatch
):
    with app.app_context():
        device = DeviceToken(
            user_id=test_user,
            token="test-fcm-registration-token",
            fid=None,
            platform="android",
            is_active=True
        )
        db.session.add(device)
        db.session.commit()

        monkeypatch.setattr(
            "app.services.notification_service.firebase_admin.get_app",
            lambda: object()
        )

        # Simulates Firebase reporting that the device token is unregistered.
        def raise_unregistered(message, app=None):
            raise messaging.UnregisteredError("Device token is unregistered")

        monkeypatch.setattr(
            "app.services.notification_service.messaging.send",
            raise_unregistered
        )

        notification = send_notification(
            user_id=test_user,
            title="Flood Alert",
            message="High flood risk detected.",
            risk_level="high"
        )

        saved_device = db.session.get(DeviceToken, device.id)

        assert saved_device.is_active is False
        assert notification.delivery_status == "failed"

# Tests that notifications remain pending if Firebase is not initialized.
def test_notification_remains_pending_without_firebase(app, test_user, monkeypatch):
    with app.app_context():
        device = DeviceToken(
            user_id=test_user,
            token="test-fcm-registration-token",
            fid=None,
            platform="android",
            is_active=True
        )
        db.session.add(device)
        db.session.commit()

        def firebase_not_initialized():
            raise ValueError("Firebase application is not initialized")

        monkeypatch.setattr(
            "app.services.notification_service.firebase_admin.get_app",
            firebase_not_initialized
        )

        notification = send_notification(
            user_id=test_user,
            title="Flood Alert",
            message="Flood risk assessment completed."
        )

        assert notification.delivery_status == "pending"


# Tests that invalid notification data is rejected.
@pytest.mark.parametrize(
    "notification_data",
    [
        {"title": "", "message": "Flood alert"},
        {"title": "Flood alert", "message": ""},
        {"title": "Flood alert", "message": "Risk detected", "risk_level": "extreme"},
        {"title": "Flood alert", "message": "Risk detected", "latitude": 100},
        {"title": "Flood alert", "message": "Risk detected", "longitude": 200},
    ]
)
def test_invalid_notification_data_is_rejected(
    app,
    test_user,
    notification_data
):
    with app.app_context():
        with pytest.raises(ValueError):
            send_notification(
                user_id=test_user,
                **notification_data
            )


# Tests that sending a notification for a nonexistent user is rejected.
def test_notification_rejects_nonexistent_user(app):
    with app.app_context():
        with pytest.raises(ValueError, match="User does not exist"):
            send_notification(
                user_id=999999,
                title="Flood Alert",
                message="Test message"
            )

# Tests rejection of invalid user ID types and values.
@pytest.mark.parametrize(
    "invalid_user_id",
    [True, 0, -1, "1", 1.5, None],
)
def test_rejects_invalid_user_id(app, invalid_user_id):
    with app.app_context():
        with pytest.raises(ValueError, match="valid user ID"):
            send_notification(
                user_id=invalid_user_id,
                title="Flood Alert",
                message="Test message",
            )

# Tests validation of notification fields and optional values.
@pytest.mark.parametrize(
    "notification_data, expected_message",
    [
        ({"title": "A" * 151}, "title cannot exceed 150"),
        ({"message": 123}, "message is required"),
        ({"notification_type": ""}, "type is required"),
        ({"notification_type": 123}, "type is required"),
        ({"deduplication_key": 123}, "must be a string"),
        ({"deduplication_key": "   "}, "cannot be empty"),
        ({"deduplication_key": "A" * 101}, "cannot exceed 100"),
        ({"latitude": True}, "must be numeric"),
        ({"latitude": "23.02"}, "must be numeric"),
        ({"latitude": float("inf")}, "must be finite"),
        ({"longitude": float("nan")}, "must be finite"),
    ],
)


def test_rejects_invalid_notification_fields(
    app,
    test_user,
    notification_data,
    expected_message,
):
    with app.app_context():
        data = {
            "user_id": test_user,
            "title": "Flood Alert",
            "message": "Test message",
        }

        data.update(notification_data)

        with pytest.raises(ValueError, match=expected_message):
            send_notification(**data)

# Tests rollback when saving a new notification fails.
def test_notification_creation_rolls_back_on_database_error(
    app,
    test_user,
    monkeypatch,
):
    with app.app_context():
        def fail_commit():
            raise RuntimeError("Database commit failed")

        monkeypatch.setattr(db.session, "commit", fail_commit)

        with pytest.raises(RuntimeError, match="Database commit failed"):
            send_notification(
                user_id=test_user,
                title="Flood Alert",
                message="Test message",
            )

        db.session.rollback()

        assert Notification.query.filter_by(
            user_id=test_user,
            title="Flood Alert",
        ).count() == 0

# Tests that legacy Firebase Installation IDs are not used as FCM destinations.
def test_legacy_fid_only_devices_are_not_used(
    app,
    test_user,
    monkeypatch,
):
    with app.app_context():
        device = DeviceToken(
            user_id=test_user,
            token=None,
            fid="legacy-firebase-installation-id",
            platform="android",
            is_active=True,
        )

        db.session.add(device)
        db.session.commit()

        def firebase_should_not_initialize():
            raise AssertionError(
                "Firebase should not initialize without an FCM token"
            )

        monkeypatch.setattr(
            "app.services.notification_service.firebase_admin.get_app",
            firebase_should_not_initialize,
        )

        notification = send_notification(
            user_id=test_user,
            title="Flood Alert",
            message="Test message",
        )

        assert notification.delivery_status == "no_devices"

# Tests partial delivery when one device fails and another succeeds.
def test_notification_partial_delivery(
    app,
    test_user,
    monkeypatch,
):
    with app.app_context():
        devices = [
            DeviceToken(
                user_id=test_user,
                token="fcm-registration-token-one",
                fid=None,
                platform="android",
                is_active=True,
            ),
            DeviceToken(
                user_id=test_user,
                token="fcm-registration-token-two",
                fid=None,
                platform="ios",
                is_active=True,
            ),
        ]

        db.session.add_all(devices)
        db.session.commit()

        monkeypatch.setattr(
            "app.services.notification_service.firebase_admin.get_app",
            lambda: object(),
        )

        send_count = 0

        def send_with_one_failure(firebase_message, app=None):
            nonlocal send_count
            send_count += 1

            if send_count == 1:
                raise RuntimeError("Temporary Firebase error")

            return "mock-message-id"

        monkeypatch.setattr(
            "app.services.notification_service.messaging.send",
            send_with_one_failure,
        )

        notification = send_notification(
            user_id=test_user,
            title="Flood Alert",
            message="Test partial delivery",
        )

        assert send_count == 2
        assert notification.delivery_status == "partial"

# Tests rollback when saving the final delivery status fails.
def test_delivery_status_commit_failure_rolls_back(
    app,
    test_user,
    monkeypatch,
):
    with app.app_context():
        device = DeviceToken(
            user_id=test_user,
            fid="firebase-installation-commit-test",
            platform="android",
            is_active=True,
        )

        db.session.add(device)
        db.session.commit()

        monkeypatch.setattr(
            "app.services.notification_service.firebase_admin.get_app",
            lambda: object(),
        )

        monkeypatch.setattr(
            "app.services.notification_service.messaging.send",
            lambda firebase_message, app=None: "mock-message-id",
        )

        original_commit = db.session.commit
        commit_count = 0

        def fail_second_commit():
            nonlocal commit_count
            commit_count += 1

            if commit_count == 2:
                raise RuntimeError("Delivery status commit failed")

            return original_commit()

        monkeypatch.setattr(
            db.session,
            "commit",
            fail_second_commit,
        )

        with pytest.raises(
            RuntimeError,
            match="Delivery status commit failed",
        ):
            send_notification(
                user_id=test_user,
                title="Flood Alert",
                message="Test message",
            )

        assert commit_count == 2
        db.session.rollback()
