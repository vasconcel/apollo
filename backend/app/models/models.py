from sqlalchemy import Column, Integer, String, Text, Float, Boolean, ForeignKey, DateTime, UniqueConstraint, Index
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.session import Base


class Review(Base):
    __tablename__ = "reviews"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text)
    status = Column(String(50), default="active")
    created_at = Column(DateTime, server_default=func.now())
    
    articles = relationship("Article", back_populates="review")
    screening_decisions = relationship("ScreeningDecision", back_populates="review")
    conflicts = relationship("ScreeningConflict", back_populates="review")


class User(Base):
    __tablename__ = "users"
    
    user_id = Column(String(100), primary_key=True)
    name = Column(String(255), nullable=False)
    email = Column(String(255), unique=True, index=True)
    hashed_password = Column(String(255), nullable=True)
    role = Column(String(50), default="reviewer")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())
    
    review_access = relationship("ReviewAccess", back_populates="user")


class ReviewAccess(Base):
    __tablename__ = "review_access"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(100), ForeignKey("users.user_id"), nullable=False)
    review_id = Column(Integer, ForeignKey("reviews.id"), nullable=False)
    role = Column(String(50), default="reviewer")
    created_at = Column(DateTime, server_default=func.now())
    
    user = relationship("User", back_populates="review_access")
    
    __table_args__ = (
        UniqueConstraint('user_id', 'review_id', name='uq_user_review'),
    )


class Article(Base):
    __tablename__ = "articles"
    
    id = Column(Integer, primary_key=True, index=True)
    review_id = Column(Integer, ForeignKey("reviews.id"), nullable=False, index=True)
    title = Column(Text)
    authors = Column(Text)
    year = Column(Integer)
    abstract = Column(Text)
    doi = Column(String(255))
    url = Column(String(500))
    source = Column(String(255))
    literature_type = Column(String(50))
    status = Column(String(50), default="imported")
    created_at = Column(DateTime, server_default=func.now())
    ingestion_notes = Column(Text)
    
    review = relationship("Review", back_populates="articles")
    screening_decisions = relationship("ScreeningDecision", back_populates="article")
    final_decisions = relationship("FinalDecision", back_populates="article")
    quality_assessments = relationship("QualityAssessment", back_populates="article")
    fragments = relationship("Fragment", back_populates="article")
    assignments = relationship("Assignment", back_populates="article")


class ScreeningDecision(Base):
    __tablename__ = "screening_decisions"
    
    id = Column(Integer, primary_key=True, index=True)
    article_id = Column(Integer, ForeignKey("articles.id"), nullable=False, index=True)
    review_id = Column(Integer, ForeignKey("reviews.id"), nullable=False, index=True)
    reviewer_id = Column(String(100), nullable=False, index=True)
    decision = Column(String(20))
    exclusion_reason = Column(String(100))
    criteria_snapshot = Column(Text)
    qc_score = Column(Float)
    is_blind = Column(Boolean, default=False)
    cross_audit_for = Column(Integer, ForeignKey("screening_decisions.id"))
    created_at = Column(DateTime, server_default=func.now())
    
    article = relationship("Article", back_populates="screening_decisions")
    review = relationship("Review", back_populates="screening_decisions")
    
    __table_args__ = (
        UniqueConstraint('article_id', 'review_id', 'reviewer_id', name='uq_screening_decision'),
    )


class ScreeningConflict(Base):
    __tablename__ = "screening_conflicts"
    
    id = Column(Integer, primary_key=True, index=True)
    article_id = Column(Integer, ForeignKey("articles.id"), nullable=False, index=True)
    review_id = Column(Integer, ForeignKey("reviews.id"), nullable=False, index=True)
    reviewer_1 = Column(String(100), nullable=False)
    reviewer_2 = Column(String(100), nullable=False)
    decision_1 = Column(String(20))
    decision_2 = Column(String(20))
    qc_score_1 = Column(Float)
    qc_score_2 = Column(Float)
    resolved = Column(Boolean, default=False)
    resolution_notes = Column(Text)
    created_at = Column(DateTime, server_default=func.now())
    
    review = relationship("Review", back_populates="conflicts")


class FinalDecision(Base):
    __tablename__ = "final_decisions"
    
    article_id = Column(Integer, ForeignKey("articles.id"), primary_key=True)
    review_id = Column(Integer, ForeignKey("reviews.id"), nullable=False, index=True)
    final_decision = Column(String(20))
    resolved_by = Column(String(100))
    resolution_notes = Column(Text)
    created_at = Column(DateTime, server_default=func.now())
    
    article = relationship("Article", back_populates="final_decisions")


class QualityAssessment(Base):
    __tablename__ = "quality_assessments"
    
    id = Column(Integer, primary_key=True, index=True)
    article_id = Column(Integer, ForeignKey("articles.id"), nullable=False, index=True)
    review_id = Column(Integer, ForeignKey("reviews.id"), nullable=False, index=True)
    reviewer_id = Column(String(100), nullable=False)
    criteria_scores = Column(Text)
    total_score = Column(Float)
    decision = Column(String(20))
    created_at = Column(DateTime, server_default=func.now())
    
    article = relationship("Article", back_populates="quality_assessments")


class Fragment(Base):
    __tablename__ = "fragments"
    
    id = Column(Integer, primary_key=True, index=True)
    article_id = Column(Integer, ForeignKey("articles.id"), nullable=False, index=True)
    review_id = Column(Integer, ForeignKey("reviews.id"), nullable=False, index=True)
    rq_code = Column(String(10), nullable=False, index=True)
    fragment_text = Column(Text, nullable=False)
    theme_category = Column(String(100))
    reviewer_id = Column(String(100), nullable=False)
    page_or_section = Column(String(100))
    created_at = Column(DateTime, server_default=func.now())
    
    article = relationship("Article", back_populates="fragments")


class Code(Base):
    __tablename__ = "codes"
    
    id = Column(Integer, primary_key=True, index=True)
    code_label = Column(String(100), nullable=False)
    code_description = Column(Text)
    rq_code = Column(String(10), nullable=False, index=True)
    reviewer_id = Column(String(100), nullable=False)
    created_at = Column(DateTime, server_default=func.now())


class Theme(Base):
    __tablename__ = "themes"
    
    id = Column(Integer, primary_key=True, index=True)
    theme_code = Column(String(50), nullable=False, unique=True)
    theme_label = Column(String(255), nullable=False)
    theme_description = Column(Text)
    rq_code = Column(String(10), nullable=False, index=True)
    created_at = Column(DateTime, server_default=func.now())


class Assignment(Base):
    __tablename__ = "assignments"
    
    id = Column(Integer, primary_key=True, index=True)
    article_id = Column(Integer, ForeignKey("articles.id"), nullable=False, index=True)
    review_id = Column(Integer, ForeignKey("reviews.id"), nullable=False, index=True)
    user_id = Column(String(100), nullable=False, index=True)
    assigned_at = Column(DateTime, server_default=func.now())
    
    article = relationship("Article", back_populates="assignments")
    
    __table_args__ = (
        UniqueConstraint('article_id', 'user_id', 'review_id', name='uq_assignment'),
    )


class ReviewState(Base):
    __tablename__ = "review_state"
    
    id = Column(Integer, primary_key=True)
    current_stage = Column(String(50), nullable=False, default="calibration")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class AuditLog(Base):
    __tablename__ = "audit_logs"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(100), nullable=True)
    action = Column(String(100), nullable=False)
    entity = Column(String(100), nullable=False)
    entity_id = Column(Integer, nullable=True)
    review_id = Column(Integer, nullable=True)
    details = Column(Text)
    created_at = Column(DateTime, server_default=func.now())
    
    __table_args__ = (
        Index('idx_audit_user', 'user_id'),
        Index('idx_audit_review', 'review_id'),
        Index('idx_audit_created', 'created_at'),
    )