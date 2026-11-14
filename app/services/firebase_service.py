import os

import firebase_admin
from firebase_admin import credentials


def initialize_firebase(credentials_path):
    """Initialize Firebase Admin SDK for Firebase Cloud Messaging only."""

    if not credentials_path:
        return None

    if not os.path.isfile(credentials_path):
        raise FileNotFoundError(
            "Firebase service-account credentials file was not found"
        )

    try:
        return firebase_admin.get_app()
    except ValueError:
        firebase_credentials = credentials.Certificate(credentials_path)
        return firebase_admin.initialize_app(firebase_credentials)
