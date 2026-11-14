from unittest.mock import Mock

import pytest

from app.services import sms_service


def test_fast2sms_sends_correct_otp_payload(app, monkeypatch):
    app.config["FAST2SMS_API_KEY"] = "test-api-key"
    app.config["FAST2SMS_SENDER_ID"] = "TESTID"
    app.config["FAST2SMS_MESSAGE_ID"] = "12345"

    captured = {}

    response = Mock()
    response.json.return_value = {"return": True}

    def fake_post(url, **kwargs):
        captured["url"] = url
        captured.update(kwargs)
        return response

    monkeypatch.setattr(
        sms_service.requests,
        "post",
        fake_post,
    )

    with app.app_context():
        result = sms_service.send_phone_otp(
            "+919876543210",
            "123456",
        )

    assert result is True
    assert captured["url"] == sms_service.FAST2SMS_API_URL
    assert captured["headers"]["Authorization"] == "test-api-key"
    assert captured["json"]["numbers"] == "9876543210"
    assert captured["json"]["variables_values"] == "123456"
    assert captured["json"]["route"] == "dlt"
    assert captured["json"]["sender_id"] == "TESTID"
    assert captured["json"]["message"] == "12345"


@pytest.mark.parametrize(
    "phone",
    ["12345", "1234567890", "abcdefghij", "+911234567890"],
)
def test_fast2sms_rejects_invalid_phone_numbers(phone):
    with pytest.raises(ValueError):
        sms_service.normalize_indian_phone_number(phone)


def test_fast2sms_rejects_invalid_otp(app):
    app.config["FAST2SMS_API_KEY"] = "test-api-key"
    app.config["FAST2SMS_SENDER_ID"] = "TESTID"
    app.config["FAST2SMS_MESSAGE_ID"] = "12345"

    with app.app_context():
        with pytest.raises(ValueError):
            sms_service.send_phone_otp(
                "9876543210",
                "12AB56",
            )


def test_fast2sms_rejects_missing_configuration(app):
    app.config["FAST2SMS_API_KEY"] = None
    app.config["FAST2SMS_SENDER_ID"] = None
    app.config["FAST2SMS_MESSAGE_ID"] = None

    with app.app_context():
        with pytest.raises(RuntimeError):
            sms_service.send_phone_otp(
                "9876543210",
                "123456",
            )