from sqlalchemy import Boolean, Column, ForeignKey, Integer, String, Table, Text, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

# Association table for many-to-many relationship between users and groups
user_group = Table(
    "user_group",
    Base.metadata,
    Column("user_id", Integer, ForeignKey("users.id")),
    Column("group_id", Integer, ForeignKey("groups.id"))
)

# Association table for many-to-many relationship between documents and groups
document_group = Table(
    "document_group",
    Base.metadata,
    Column("document_id", Integer, ForeignKey("documents.id")),
    Column("group_id", Integer, ForeignKey("groups.id"))
)

# Association table for many-to-many relationship between documents and tags
document_tag = Table(
    "document_tag",
    Base.metadata,
    Column("document_id", Integer, ForeignKey("documents.id")),
    Column("tag_id", Integer, ForeignKey("tags.id"))
)

# User-Role association table
user_role = Table(
    "user_role",
    Base.metadata,
    Column("user_id", Integer, ForeignKey("users.id")),
    Column("role_id", Integer, ForeignKey("roles.id"))
)

# Role-Permission association table
role_permission = Table(
    "role_permission",
    Base.metadata,
    Column("role_id", Integer, ForeignKey("roles.id")),
    Column("permission_id", Integer, ForeignKey("permissions.id"))
)

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)
    username = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    is_active = Column(Boolean, default=False)  # Changed default to False - requires approval
    is_superuser = Column(Boolean, default=False)
    is_approved = Column(Boolean, default=False)  # New field for admin approval
    approval_status = Column(String, default="pending")  # pending, approved, rejected
    password_reset_required = Column(Boolean, default=True)  # Require password change on first login
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    groups = relationship("Group", secondary=user_group, back_populates="users")
    roles = relationship("Role", secondary=user_role, back_populates="users")
    documents = relationship("Document", back_populates="owner")
    chat_history = relationship("ChatHistory", back_populates="user")

class Group(Base):
    __tablename__ = "groups"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    description = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    users = relationship("User", secondary=user_group, back_populates="groups")
    documents = relationship("Document", secondary=document_group, back_populates="groups")

class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String, index=True)
    file_path = Column(String)
    file_id = Column(String, unique=True, index=True)  # UUID for vector DB reference
    owner_id = Column(Integer, ForeignKey("users.id"))
    is_public = Column(Boolean, default=False)
    chunk_count = Column(Integer, default=0)
    chunk_size = Column(Integer, default=1000)
    chunk_overlap = Column(Integer, default=200)
    chunking_strategy = Column(String, default="hybrid")  # FIXED_SIZE, PARAGRAPH, SENTENCE, HYBRID
    processing_status = Column(String, default="pending")  # pending, processing, completed, failed
    processing_progress = Column(Integer, default=0)  # 0-100 percentage
    processing_message = Column(String, nullable=True)  # Additional status message
    file_size = Column(Integer, default=0)  # File size in bytes
    file_type = Column(String, nullable=True)  # File type/extension
    document_type = Column(String, nullable=True)  # Document category (e.g., case, complaint, report)
    brief_summary = Column(String, nullable=True)  # Brief one-line summary
    ocr_text = Column(Text, nullable=True)  # First few lines of OCR text for quick reference
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    owner = relationship("User", back_populates="documents")
    groups = relationship("Group", secondary=document_group, back_populates="documents")
    summaries = relationship("DocumentSummary", back_populates="document")
    tags = relationship("Tag", secondary=document_tag, back_populates="documents")

class DocumentSummary(Base):
    __tablename__ = "document_summaries"

    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("documents.id"))
    summary_text = Column(Text)
    model_used = Column(String)
    summary_type = Column(String, default="comprehensive")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    created_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    # Relationships
    document = relationship("Document", back_populates="summaries")
    created_by = relationship("User", backref="document_summaries")

class ChatHistory(Base):
    __tablename__ = "chat_history"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    query = Column(Text)
    answer = Column(Text)
    model_used = Column(String)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    user = relationship("User", back_populates="chat_history")

class Tag(Base):
    __tablename__ = "tags"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    color = Column(String, default="#3f51b5")  # Default color for tags
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    documents = relationship("Document", secondary=document_tag, back_populates="tags")

class Permission(Base):
    __tablename__ = "permissions"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    description = Column(String, nullable=True)
    resource = Column(String, index=True)  # e.g., "documents", "users", "groups"
    action = Column(String, index=True)    # e.g., "create", "read", "update", "delete"
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    roles = relationship("Role", secondary=role_permission, back_populates="permissions")

class Role(Base):
    __tablename__ = "roles"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    description = Column(String, nullable=True)
    is_default = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    users = relationship("User", secondary=user_role, back_populates="roles")
    permissions = relationship("Permission", secondary=role_permission, back_populates="roles")