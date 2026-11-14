
from getpass import getpass

from app import create_app
from app.extensions import db
from app.models.user import User

app = create_app()

with app.app_context():
    print("\n=== FloodShield Create Test User ===\n")

    name = input("Enter user's name: ").strip()
    email = input("Enter user's email: ").strip().lower()

    if not name or not email:
        print("\nName and email are required.")
        raise SystemExit(1)

    existing_user = User.query.filter_by(email=email).first()

    if existing_user:
        print("\nA user with this email already exists.")
        raise SystemExit(1)

    password = input("Enter password: ")
    confirm_password = input("Confirm password: ")

    if len(password) < 8:
        print("\nPassword must contain at least 8 characters.")
        raise SystemExit(1)

    if password != confirm_password:
        print("\nPasswords do not match.")
        raise SystemExit(1)

    user = User(
        name=name,
        email=email
    )

    user.set_password(password)

    db.session.add(user)
    db.session.commit()

    print("\nUser created successfully!")
    print("Name:", user.name)
    print("Email:", user.email)
