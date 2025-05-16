from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.models import User
from app.schemas.email import SMTPSettings, EmailMessage
from app.api.deps import get_current_user, get_db
from app.services.email import get_smtp_settings, save_smtp_settings, send_email

router = APIRouter()

@router.get("/email/settings", response_model=Dict[str, Any])
def get_email_settings(
    current_user: User = Depends(get_current_user),
) -> Any:
    """
    Get SMTP settings status
    """
    settings = get_smtp_settings()
    if settings:
        # Don't return the password
        settings_dict = settings.dict()
        settings_dict["password"] = "********" if settings_dict["password"] else ""
        return {
            "configured": True,
            "settings": settings_dict
        }
    return {"configured": False}

@router.post("/email/settings", response_model=Dict[str, Any])
def update_email_settings(
    settings: SMTPSettings,
    current_user: User = Depends(get_current_user),
) -> Any:
    """
    Update SMTP settings
    """
    success = save_smtp_settings(settings)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save SMTP settings"
        )
    
    return {"success": True, "message": "SMTP settings updated successfully"}

@router.post("/email/test", response_model=Dict[str, Any])
def test_email_settings(
    email: EmailMessage,
    current_user: User = Depends(get_current_user),
) -> Any:
    """
    Test SMTP settings by sending a test email
    """
    result = send_email(email)
    if not result["success"]:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=result["message"]
        )
    
    return result

@router.post("/email/send", response_model=Dict[str, Any])
def send_email_api(
    email: EmailMessage,
    current_user: User = Depends(get_current_user),
) -> Any:
    """
    Send an email
    """
    result = send_email(email)
    if not result["success"]:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=result["message"]
        )
    
    return result