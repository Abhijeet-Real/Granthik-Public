"""
API routes for exporting data
"""
import os
import logging
from typing import Any, Dict, List, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from fastapi.responses import FileResponse, Response
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.db.models import User, ChatHistory, DocumentSummary, Document
from app.api.deps import get_current_user
from app.utils.docx_export import create_docx_summary
from app.services.docx_export import create_summary_docx
from app.services.export import (
    export_to_docx, 
    export_to_pdf, 
    export_to_txt, 
    export_to_html
)

router = APIRouter()
logger = logging.getLogger("uvicorn")

@router.post("/export/summary/docx", response_class=FileResponse)
def export_summary_to_docx(
    *,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    title: str,
    summary: str,
    chat_id: Optional[int] = None,
    include_chat_history: bool = False
) -> Any:
    """
    Export a summary to DOCX format
    
    Args:
        title: Document title
        summary: Summary text
        chat_id: Optional chat ID to include history from
        include_chat_history: Whether to include chat history
        
    Returns:
        DOCX file as download
    """
    try:
        logger.info(f"Exporting summary to DOCX: {title}")
        
        # Get chat history if requested
        chat_history = None
        if include_chat_history and chat_id:
            chat_messages = db.query(ChatHistory).filter(
                ChatHistory.id == chat_id
            ).all()
            
            if chat_messages:
                chat_history = [
                    {
                        "query": msg.query,
                        "answer": msg.answer,
                        "model_used": msg.model_used,
                        "created_at": msg.created_at.isoformat() if msg.created_at else None
                    }
                    for msg in chat_messages
                ]
        
        # Create a temporary directory for the file
        import tempfile
        temp_dir = tempfile.gettempdir()
        safe_title = "".join(c for c in title if c.isalnum() or c in " _-").strip()
        safe_title = safe_title.replace(" ", "_")
        
        # Create the DOCX file
        output_path = create_docx_summary(
            title=title,
            summary_text=summary,
            chat_history=chat_history,
            output_path=os.path.join(temp_dir, f"{safe_title}.docx")
        )
        
        # Return the file as a download
        return FileResponse(
            path=output_path,
            filename=f"{safe_title}.docx",
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )
    
    except Exception as e:
        logger.error(f"Error exporting summary to DOCX: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to export summary: {str(e)}"
        )

@router.post("/export/print/html")
def get_printable_html(
    *,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    title: str,
    content: str,
) -> Dict[str, Any]:
    """
    Get HTML content formatted for printing
    
    Args:
        title: Document title
        content: HTML content
        
    Returns:
        Dictionary with HTML content ready for printing
    """
    try:
        # Create a simple HTML template for printing
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>{title}</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; }}
                h1 {{ color: #333; }}
                .content {{ line-height: 1.6; }}
                @media print {{
                    body {{ margin: 0.5in; }}
                }}
            </style>
        </head>
        <body>
            <h1>{title}</h1>
            <div class="content">{content}</div>
        </body>
        </html>
        """
        
        return {
            "success": True,
            "html": html_content
        }
    
    except Exception as e:
        logger.error(f"Error generating printable HTML: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate printable content: {str(e)}"
        )

@router.get("/export/summary/{summary_id}/docx", response_class=Response)
async def export_summary_docx(
    *,
    db: Session = Depends(get_db),
    summary_id: int,
    current_user: User = Depends(get_current_user),
) -> Any:
    """
    Export a document summary to DOCX format
    
    Args:
        summary_id: ID of the summary to export
        
    Returns:
        DOCX file as download
    """
    try:
        # Get the summary
        summary = db.query(DocumentSummary).filter(DocumentSummary.id == summary_id).first()
        if not summary:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Summary not found"
            )
        
        # Get the document
        document = db.query(Document).filter(Document.id == summary.document_id).first()
        if not document:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Document not found"
            )
        
        # Check if user has access to this document
        if document.owner_id != current_user.id and not document.is_public:
            # Check if document is shared with any of user's groups
            user_group_ids = [group.id for group in current_user.groups]
            document_group_ids = [group.id for group in document.groups]
            if not any(g_id in user_group_ids for g_id in document_group_ids):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Not enough permissions to access this document"
                )
        
        # Export to DOCX
        docx_bytes = export_to_docx(
            summary_text=summary.summary_text,
            filename=document.filename,
            model_used=summary.model_used,
            created_at=summary.created_at,
            summary_type=summary.summary_type
        )
        
        # Create a safe filename
        safe_filename = "".join(c for c in document.filename if c.isalnum() or c in " _-").strip()
        safe_filename = safe_filename.replace(" ", "_")
        
        # Return the file
        return Response(
            content=docx_bytes,
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            headers={
                "Content-Disposition": f'attachment; filename="{safe_filename}_summary.docx"'
            }
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error exporting summary to DOCX: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to export summary: {str(e)}"
        )

@router.get("/export/summary/{summary_id}/pdf", response_class=Response)
async def export_summary_pdf(
    *,
    db: Session = Depends(get_db),
    summary_id: int,
    current_user: User = Depends(get_current_user),
) -> Any:
    """
    Export a document summary to PDF format
    
    Args:
        summary_id: ID of the summary to export
        
    Returns:
        PDF file as download
    """
    try:
        # Get the summary
        summary = db.query(DocumentSummary).filter(DocumentSummary.id == summary_id).first()
        if not summary:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Summary not found"
            )
        
        # Get the document
        document = db.query(Document).filter(Document.id == summary.document_id).first()
        if not document:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Document not found"
            )
        
        # Check if user has access to this document
        if document.owner_id != current_user.id and not document.is_public:
            # Check if document is shared with any of user's groups
            user_group_ids = [group.id for group in current_user.groups]
            document_group_ids = [group.id for group in document.groups]
            if not any(g_id in user_group_ids for g_id in document_group_ids):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Not enough permissions to access this document"
                )
        
        # Export to PDF
        pdf_bytes = export_to_pdf(
            summary_text=summary.summary_text,
            filename=document.filename,
            model_used=summary.model_used,
            created_at=summary.created_at,
            summary_type=summary.summary_type
        )
        
        # Create a safe filename
        safe_filename = "".join(c for c in document.filename if c.isalnum() or c in " _-").strip()
        safe_filename = safe_filename.replace(" ", "_")
        
        # Return the file
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="{safe_filename}_summary.pdf"'
            }
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error exporting summary to PDF: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to export summary: {str(e)}"
        )

@router.get("/export/summary/{summary_id}/txt", response_class=Response)
async def export_summary_txt(
    *,
    db: Session = Depends(get_db),
    summary_id: int,
    current_user: User = Depends(get_current_user),
) -> Any:
    """
    Export a document summary to TXT format
    
    Args:
        summary_id: ID of the summary to export
        
    Returns:
        TXT file as download
    """
    try:
        # Get the summary
        summary = db.query(DocumentSummary).filter(DocumentSummary.id == summary_id).first()
        if not summary:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Summary not found"
            )
        
        # Get the document
        document = db.query(Document).filter(Document.id == summary.document_id).first()
        if not document:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Document not found"
            )
        
        # Check if user has access to this document
        if document.owner_id != current_user.id and not document.is_public:
            # Check if document is shared with any of user's groups
            user_group_ids = [group.id for group in current_user.groups]
            document_group_ids = [group.id for group in document.groups]
            if not any(g_id in user_group_ids for g_id in document_group_ids):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Not enough permissions to access this document"
                )
        
        # Export to TXT
        txt_bytes = export_to_txt(
            summary_text=summary.summary_text,
            filename=document.filename,
            model_used=summary.model_used,
            created_at=summary.created_at,
            summary_type=summary.summary_type
        )
        
        # Create a safe filename
        safe_filename = "".join(c for c in document.filename if c.isalnum() or c in " _-").strip()
        safe_filename = safe_filename.replace(" ", "_")
        
        # Return the file
        return Response(
            content=txt_bytes,
            media_type="text/plain",
            headers={
                "Content-Disposition": f'attachment; filename="{safe_filename}_summary.txt"'
            }
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error exporting summary to TXT: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to export summary: {str(e)}"
        )

@router.get("/export/summary/{summary_id}/html", response_class=Response)
async def export_summary_html(
    *,
    db: Session = Depends(get_db),
    summary_id: int,
    current_user: User = Depends(get_current_user),
) -> Any:
    """
    Export a document summary to HTML format for printing
    
    Args:
        summary_id: ID of the summary to export
        
    Returns:
        HTML content for printing
    """
    try:
        # Get the summary
        summary = db.query(DocumentSummary).filter(DocumentSummary.id == summary_id).first()
        if not summary:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Summary not found"
            )
        
        # Get the document
        document = db.query(Document).filter(Document.id == summary.document_id).first()
        if not document:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Document not found"
            )
        
        # Check if user has access to this document
        if document.owner_id != current_user.id and not document.is_public:
            # Check if document is shared with any of user's groups
            user_group_ids = [group.id for group in current_user.groups]
            document_group_ids = [group.id for group in document.groups]
            if not any(g_id in user_group_ids for g_id in document_group_ids):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Not enough permissions to access this document"
                )
        
        # Export to HTML
        html_bytes = export_to_html(
            summary_text=summary.summary_text,
            filename=document.filename,
            model_used=summary.model_used,
            created_at=summary.created_at,
            summary_type=summary.summary_type
        )
        
        # Return the HTML content
        return Response(
            content=html_bytes,
            media_type="text/html"
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error exporting summary to HTML: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to export summary: {str(e)}"
        )