
import os
import smtplib

from email.message import EmailMessage


def send_email(recipient, subject, body):
    """
    Send a plain-text email using the SMTP provider configured
    through environment variables.

    Required environment variables:
        SMTP_HOST
        SMTP_PORT
        SMTP_FROM_EMAIL

    Optional:
        SMTP_USERNAME
        SMTP_PASSWORD
        SMTP_USE_TLS
        SMTP_USE_SSL
        SMTP_TIMEOUT_SECONDS
    """

    if not isinstance(recipient, str) or not recipient.strip():
        raise ValueError("A valid email recipient is required")

    if not isinstance(subject, str) or not subject.strip():
        raise ValueError("An email subject is required")

    if not isinstance(body, str) or not body.strip():
        raise ValueError("Email content is required")

    smtp_host = os.getenv("SMTP_HOST")
    smtp_port = os.getenv("SMTP_PORT", "587")
    smtp_username = os.getenv("SMTP_USERNAME")
    smtp_password = os.getenv("SMTP_PASSWORD")
    smtp_from_email = os.getenv("SMTP_FROM_EMAIL")

    use_tls = os.getenv("SMTP_USE_TLS", "true").lower() == "true"
    use_ssl = os.getenv("SMTP_USE_SSL", "false").lower() == "true"

    try:
        timeout = int(os.getenv("SMTP_TIMEOUT_SECONDS", "15"))
        port = int(smtp_port)
    except ValueError as error:
        raise RuntimeError("Invalid SMTP port or timeout configuration") from error

    if not smtp_host or not smtp_from_email:
        raise RuntimeError("SMTP email configuration is incomplete")

    if use_tls and use_ssl:
        raise RuntimeError("SMTP TLS and SSL cannot both be enabled")

    if bool(smtp_username) != bool(smtp_password):
        raise RuntimeError("Both SMTP username and password must be configured")

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = smtp_from_email
    message["To"] = recipient.strip()
    message.set_content(body)

    try:
        if use_ssl:
            with smtplib.SMTP_SSL(
                smtp_host,
                port,
                timeout=timeout
            ) as server:
                if smtp_username:
                    server.login(smtp_username, smtp_password)

                server.send_message(message)

        else:
            with smtplib.SMTP(
                smtp_host,
                port,
                timeout=timeout
            ) as server:
                server.ehlo()

                if use_tls:
                    server.starttls()
                    server.ehlo()

                if smtp_username:
                    server.login(smtp_username, smtp_password)

                server.send_message(message)

    except (smtplib.SMTPException, OSError) as error:
        raise RuntimeError("Email delivery failed") from error

    return True
