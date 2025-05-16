from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.db.base_class import Base
from datetime import datetime

class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String, nullable=False)
    filepath = Column(String, nullable=False)
    filetype = Column(String)
    uploaded_by = Column(String)
    uploaded_at = Column(DateTime, default=datetime.utcnow)
    status = Column(String, default="pending")