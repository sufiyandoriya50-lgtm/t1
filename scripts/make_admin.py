
from getpass import getpass

from app import create_app
from app.extensions import db
from app.models.user import User


# Promotes an existing account to administrator and securely sets its password.
def main():
    app = create_app()

    with app.app_context():
        email = input("Enter the existing account email: ").strip()

        user = User.query.filter_by(email=email).first()

        if user is None:
            print("Error: Account not found. Create the account first.")
            return

        print(f"\nAccount: {user.name}")
        print(f"Email: {user.email}")
        print(f"Current role: {user.role}")

        password = getpass("\nEnter new administrator password (minimum 12 characters): ")

        if len(password) < 12:
            print("Error: Password must contain at least 12 characters.")
            return

        confirmation = getpass("Confirm new password: ")

        if password != confirmation:
            print("Error: Passwords do not match.")
            return

        user.role = "admin"
        user.set_password(password)

        db.session.commit()

        print("\nAdministrator account successfully configured.")
        print("Email:", user.email)
        print("Role:", user.role)


if __name__ == "__main__":
    main()
