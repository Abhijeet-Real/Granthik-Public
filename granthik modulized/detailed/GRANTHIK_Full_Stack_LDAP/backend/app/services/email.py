"""
Email service for sending emails
"""
import os
import json
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from pathlib import Path
from typing import Optional, Dict, Any

from app.schemas.email import SMTPSettings, EmailMessage

# Path to the SMTP settings file
SMTP_CONFIG_PATH = os.path.join(os.path.dirname(__file__), "smtp_config.json")

def get_smtp_settings() -> Optional[SMTPSettings]:
    """
    Get SMTP settings from config file or environment variables
    
    Returns:
        SMTPSettings object or None if not configured
    """
    import logging
    from app.core.config import settings
    logger = logging.getLogger("uvicorn")
    
    # First try to get from config file
    if os.path.exists(SMTP_CONFIG_PATH):
        try:
            with open(SMTP_CONFIG_PATH, "r") as f:
                data = json.load(f)
                return SMTPSettings(**data)
        except Exception as e:
            logger.error(f"Error loading SMTP config from file: {str(e)}")
    
    # If not found in file, try to get from environment variables
    try:
        if settings.SMTP_USERNAME and settings.SMTP_PASSWORD:
            logger.info("Using SMTP settings from environment variables")
            return SMTPSettings(
                server=settings.SMTP_SERVER,
                port=settings.SMTP_PORT,
                username=settings.SMTP_USERNAME,
                password=settings.SMTP_PASSWORD,
                from_email=settings.SMTP_FROM_EMAIL,
                use_tls=settings.SMTP_USE_TLS,
                use_ssl=settings.SMTP_USE_SSL
            )
    except Exception as e:
        logger.error(f"Error loading SMTP config from environment: {str(e)}")
    
    return None

def save_smtp_settings(settings: SMTPSettings) -> bool:
    """
    Save SMTP settings to config file
    
    Args:
        settings: SMTPSettings object
        
    Returns:
        True if successful, False otherwise
    """
    try:
        # Ensure directory exists
        os.makedirs(os.path.dirname(SMTP_CONFIG_PATH), exist_ok=True)
        
        with open(SMTP_CONFIG_PATH, "w") as f:
            json.dump(settings.dict(), f, indent=2)
        return True
    except Exception as e:
        import logging
        logger = logging.getLogger("uvicorn")
        logger.error(f"Error saving SMTP config: {str(e)}")
        return False

def send_email(message: EmailMessage) -> Dict[str, Any]:
    """
    Send an email using configured SMTP settings
    
    Args:
        message: EmailMessage object
        
    Returns:
        Dict with success status and message
    """
    import logging
    logger = logging.getLogger("uvicorn")
    
    settings = get_smtp_settings()
    if not settings:
        logger.error("SMTP settings not configured")
        return {"success": False, "message": "SMTP not configured"}
    
    logger.info(f"Attempting to send email to {message.to} using server {settings.server}:{settings.port}")
    
    try:
        # Create message
        msg = MIMEMultipart()
        msg["Subject"] = message.subject
        msg["From"] = settings.from_email
        msg["To"] = message.to
        
        # Check if body is HTML (simple check for HTML tags)
        is_html = "<html" in message.body.lower() or "<body" in message.body.lower() or "<div" in message.body.lower()
        logger.info(f"Email body format: {'HTML' if is_html else 'Plain text'}")
        
        # Check if this is a document summary (contains "Document Summary" in the subject)
        is_document_summary = "document summary" in message.subject.lower()
        
        if is_document_summary:
            # Create a simple HTML wrapper for the email body
            html_content = f"""
            <html>
            <body>
            <h2>{message.subject}</h2>
            <p>Please find the document summary attached as a PDF.</p>
            <p>This email was sent from GRANTHIK.</p>
            </body>
            </html>
            """
            
            # Add HTML part
            html_part = MIMEText(html_content, "html")
            msg.attach(html_part)
            
            # Create PDF attachment from the message body
            try:
                from reportlab.lib.pagesizes import letter
                from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
                from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
                from reportlab.lib.units import inch
                import io
                
                # Create PDF in memory
                buffer = io.BytesIO()
                doc = SimpleDocTemplate(buffer, pagesize=letter)
                styles = getSampleStyleSheet()
                
                # Create content for PDF
                content = []
                
                # Add title
                title_style = ParagraphStyle(
                    'Title',
                    parent=styles['Heading1'],
                    fontSize=16,
                    spaceAfter=12
                )
                content.append(Paragraph("Document Summary", title_style))
                content.append(Spacer(1, 0.25*inch))
                
                # Process the body text
                body_text = message.body
                if is_html:
                    # Strip HTML tags for PDF content
                    import re
                    body_text = re.sub(r'<[^>]*>', '', body_text)
                
                # Split by lines and create paragraphs
                lines = body_text.split('\\n')
                for line in lines:
                    if line.strip():
                        content.append(Paragraph(line, styles["Normal"]))
                        content.append(Spacer(1, 0.1*inch))
                
                # Build PDF
                doc.build(content)
                
                # Get PDF data
                pdf_data = buffer.getvalue()
                buffer.close()
                
                # Attach PDF
                pdf_attachment = MIMEBase('application', 'pdf')
                pdf_attachment.set_payload(pdf_data)
                encoders.encode_base64(pdf_attachment)
                pdf_attachment.add_header(
                    'Content-Disposition',
                    f'attachment; filename="Document_Summary.pdf"'
                )
                msg.attach(pdf_attachment)
                logger.info("Created and attached PDF summary")
                
            except Exception as pdf_error:
                logger.error(f"Error creating PDF attachment: {str(pdf_error)}")
                # Fall back to regular email if PDF creation fails
                if is_html:
                    html_part = MIMEText(message.body, "html")
                    msg.attach(html_part)
                else:
                    text_part = MIMEText(message.body, "plain")
                    msg.attach(text_part)
        else:
            # Regular email handling
            if is_html:
                # Add HTML part
                html_part = MIMEText(message.body, "html")
                msg.attach(html_part)
                
                # Add a plain text alternative (simple strip of HTML tags)
                plain_text = message.body.replace("<br />", "\n").replace("<br>", "\n")
                # Very basic HTML tag removal
                import re
                plain_text = re.sub(r'<[^>]*>', '', plain_text)
                text_part = MIMEText(plain_text, "plain")
                msg.attach(text_part)
            else:
                # Add text part
                text_part = MIMEText(message.body, "plain")
                msg.attach(text_part)
        
        # Connect to SMTP server with timeout
        logger.info(f"Connecting to SMTP server: SSL={settings.use_ssl}, TLS={settings.use_tls}")
        
        try:
            if settings.use_ssl:
                server = smtplib.SMTP_SSL(settings.server, settings.port, timeout=10)
                logger.info("Connected to SMTP server using SSL")
            else:
                server = smtplib.SMTP(settings.server, settings.port, timeout=10)
                logger.info("Connected to SMTP server")
                
                if settings.use_tls:
                    server.starttls()
                    logger.info("Started TLS")
            
            # Set debug level
            server.set_debuglevel(1)
            
            # Login if credentials provided
            if settings.username and settings.password:
                logger.info(f"Attempting login with username: {settings.username}")
                server.login(settings.username, settings.password)
                logger.info("Login successful")
            
            # Send email
            logger.info(f"Sending email from {settings.from_email} to {message.to}")
            server.sendmail(settings.from_email, message.to, msg.as_string())
            logger.info("Email sent successfully")
            
            server.quit()
            logger.info("SMTP connection closed")
            
            return {"success": True, "message": "Email sent successfully"}
        except smtplib.SMTPAuthenticationError:
            logger.error("SMTP Authentication Error: Invalid username or password")
            return {"success": False, "message": "SMTP Authentication Error: Invalid username or password"}
        except smtplib.SMTPConnectError:
            logger.error("SMTP Connection Error: Failed to connect to the server")
            return {"success": False, "message": "SMTP Connection Error: Failed to connect to the server"}
        except smtplib.SMTPServerDisconnected:
            logger.error("SMTP Server Disconnected: Server unexpectedly disconnected")
            return {"success": False, "message": "SMTP Server Disconnected: Server unexpectedly disconnected"}
        except smtplib.SMTPException as e:
            logger.error(f"SMTP Error: {str(e)}")
            return {"success": False, "message": f"SMTP Error: {str(e)}"}
            
    except Exception as e:
        logger.error(f"Error sending email: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return {"success": False, "message": f"Failed to send email: {str(e)}"}