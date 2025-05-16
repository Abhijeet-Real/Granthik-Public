import logging
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.db.session import SessionLocal
from app.schemas.user import UserCreate
from app.crud.user import get_user_by_email, create_user

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def clean_database(db: Session) -> None:
    """Clean up the database by removing problematic data"""
    try:
        # Clean up chat history with null user_id
        db.execute(text("DELETE FROM chat_history WHERE user_id IS NULL"))
        db.commit()
        logger.info("Cleaned up chat history with null user_id")
    except Exception as e:
        logger.error(f"Error cleaning database: {str(e)}")
        db.rollback()

def init_db(db: Session) -> None:
    # First clean up any problematic data
    clean_database(db)
    
    # Create initial admin user
    admin_email = "admin@granthik.com"
    admin = get_user_by_email(db, email=admin_email)
    
    # Only create admin if it doesn't exist
    if not admin:
        # Create new admin user with active and approved status
        user_in = UserCreate(
            email=admin_email,
            username="admin",
            password="Admin@123",  # Secure password for production
            is_superuser=True,
            is_active=True,
            is_approved=True,
            approval_status="approved"
        )
        user = create_user(db, obj_in=user_in)
        logger.info(f"Admin user created with email: {admin_email}")
    else:
        # Ensure existing admin is active and approved
        if not admin.is_active or not admin.is_approved:
            admin.is_active = True
            admin.is_approved = True
            admin.approval_status = "approved"
            db.commit()
            logger.info(f"Updated admin user {admin_email} to active and approved status")
        logger.info(f"Admin user already exists with email: {admin_email}")
    
    # Create a backup admin user
    backup_email = "321148@fsm.ac.in"
    backup_admin = get_user_by_email(db, email=backup_email)
    
    if not backup_admin:
        # Create backup admin user with active and approved status
        user_in = UserCreate(
            email=backup_email,
            username="backup_admin",
            password="Abmatbhulna@12",  # Secure password for production
            is_superuser=True,
            is_active=True,
            is_approved=True,
            approval_status="approved"
        )
        user = create_user(db, obj_in=user_in)
        logger.info(f"Backup admin user created with email: {backup_email}")
    else:
        # Ensure existing backup admin is active and approved
        if not backup_admin.is_active or not backup_admin.is_approved:
            backup_admin.is_active = True
            backup_admin.is_approved = True
            backup_admin.approval_status = "approved"
            db.commit()
            logger.info(f"Updated backup admin user {backup_email} to active and approved status")
        logger.info(f"Backup admin user already exists with email: {backup_email}")

def main() -> None:
    logger.info("Creating initial data")
    db = SessionLocal()
    init_db(db)
    logger.info("Initial data created")

if __name__ == "__main__":
    main()