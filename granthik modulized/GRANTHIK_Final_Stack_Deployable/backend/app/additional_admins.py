"""
Script to create additional admin users
"""
import logging
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.schemas.user import UserCreate
from app.crud.user import get_user_by_email, create_user

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def init_additional_admins(db: Session) -> None:
    # List of admin users to create
    admin_users = [
        {
            "email": "aashit@granthik.com",
            "username": "aashit",
            "password": "Admin@123"
        },
        {
            "email": "ashok@granthik.com",
            "username": "ashok",
            "password": "Admin@123"
        },
        {
            "email": "arindam@granthik.com",
            "username": "arindam",
            "password": "Admin@123"
        },
        {
            "email": "admin1@granthik.com",
            "username": "admin1",
            "password": "Admin@123"
        },
        {
            "email": "admin2@granthik.com",
            "username": "admin2",
            "password": "Admin@123"
        }
    ]
    
    for user_data in admin_users:
        email = user_data["email"]
        existing_user = get_user_by_email(db, email=email)
        
        if not existing_user:
            # Create new admin user with active and approved status
            user_in = UserCreate(
                email=email,
                username=user_data["username"],
                password=user_data["password"],
                is_superuser=True,
                is_active=True,
                is_approved=True,
                approval_status="approved"
            )
            user = create_user(db, obj_in=user_in)
            logger.info(f"Admin user created with email: {email}")
        else:
            # Ensure existing user is active, approved, and a superuser
            if not existing_user.is_active or not existing_user.is_approved or not existing_user.is_superuser:
                existing_user.is_active = True
                existing_user.is_approved = True
                existing_user.is_superuser = True
                existing_user.approval_status = "approved"
                db.commit()
                logger.info(f"Updated user {email} to active, approved admin status")
            logger.info(f"Admin user already exists with email: {email}")

def main() -> None:
    logger.info("Creating additional admin users")
    db = SessionLocal()
    try:
        init_additional_admins(db)
    finally:
        db.close()
    logger.info("Additional admin users created successfully")

if __name__ == "__main__":
    main()