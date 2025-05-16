from typing import Optional
from pydantic import BaseModel, EmailStr, Field

class SMTPSettings(BaseModel):
    server: str = Field(..., description="SMTP server address")
    port: int = Field(..., description="SMTP server port")
    username: str = Field(..., description="SMTP username")
    password: str = Field(..., description="SMTP password")
    from_email: EmailStr = Field(..., description="Email address to send from")
    use_tls: bool = Field(True, description="Use TLS for connection")
    use_ssl: bool = Field(False, description="Use SSL for connection")

class EmailMessage(BaseModel):
    to: EmailStr = Field(..., description="Email address to send to")
    subject: str = Field(..., description="Email subject")
    body: str = Field(..., description="Email body or HTML body")