
from app import create_app
from app.extensions import db
from app.models.user import User


def main():
    app = create_app()

    with app.app_context():
        print("\n=== Create FloodShield Admin ===\n")

        name = input("Admin name: ").strip()
        email = input("Admin email: ").strip().lower()
        password = input("Admin password: ")
        confirmation = input("Confirm password: ")

        if not name or not email:
            print("Error: Name and email are required.")
            return

        if User.query.filter_by(email=email).first():
            print("Error: This email already exists.")
            return

        if len(password) < 12:
            print("Error: Password must be at least 12 characters.")
            return

        if password != confirmation:
            print("Error: Passwords do not match.")
            return

        admin = User(
            name=name,
            email=email,
            role="admin"
        )

        admin.set_password(password)

        db.session.add(admin)
        db.session.commit()

        print("\nAdmin created successfully!")
        print("Name:", admin.name)
        print("Email:", admin.email)
        print("Role:", admin.role)


if __name__ == "__main__":
    main()
