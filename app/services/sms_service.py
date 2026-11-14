
import re

import requests

from flask import current_app


FAST2SMS_API_URL = "https://www.fast2sms.com/dev/bulkV2"
FAST2SMS_TIMEOUT_SECONDS = 15


def normalize_indian_phone_number(phone_number):
    """Normalize an Indian mobile number to ten digits."""

    if not isinstance(phone_number, str):
        raise ValueError("A valid Indian mobile number is required")

    digits = re.sub(r"[\s()+-]", "", phone_number.strip())

    if digits.startswith("91") and len(digits) == 12:
        digits = digits[2:]

    if (
        len(digits) != 10
        or not digits.isdigit()
        or digits[0] not in "6789"
    ):
        raise ValueError("A valid Indian mobile number is required")

    return digits


def send_phone_otp(phone_number, otp):
    """
    Deliver a FloodShield-generated OTP through Fast2SMS.

    FloodShield remains responsible for OTP generation,
    hashing, storage, expiry and verification.

    Fast2SMS is used only for SMS delivery.
    """

    phone_number = normalize_indian_phone_number(phone_number)

    if (
        not isinstance(otp, str)
        or len(otp) != 6
        or not otp.isdigit()
    ):
        raise ValueError("A valid six-digit OTP is required")

    api_key = current_app.config.get("FAST2SMS_API_KEY")
    sender_id = current_app.config.get("FAST2SMS_SENDER_ID")
    message_id = current_app.config.get("FAST2SMS_MESSAGE_ID")

    if not api_key or not sender_id or not message_id:
        raise RuntimeError(
            "Fast2SMS configuration is incomplete"
        )

    payload = {
        "sender_id": sender_id,
        "message": message_id,
        "variables_values": otp,
        "route": "dlt",
        "numbers": phone_number,
    }

    headers = {
        "Authorization": api_key,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    try:
        response = requests.post(
            FAST2SMS_API_URL,
            headers=headers,
            json=payload,
            timeout=FAST2SMS_TIMEOUT_SECONDS,
        )

        response.raise_for_status()

        result = response.json()

        if not isinstance(result, dict) or result.get("return") is not True:
            raise RuntimeError("Fast2SMS rejected the SMS request")

        return True

    except requests.RequestException as error:
        raise RuntimeError("SMS delivery failed") from error
