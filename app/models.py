from sqlalchemy import Column, Integer, String, Float, Boolean, ForeignKey, DateTime,Index
from sqlalchemy.sql import func
from .database import Base

class Job(Base):
  __tablename__ = "jobs"
  
  id = Column(String , primary_key=True, index=True)
  filename  = Column(String)
  status = Column(String, default="pending")
  row_count_raw = Column(Integer, default=0)
  row_count_clean = Column(Integer, default=0)
  created_at = Column(DateTime(timezone=True), server_default=func.now())
  completed_at = Column(DateTime(timezone=True), nullable=True)
  error_message = Column(String, nullable=True)
  
class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(String, ForeignKey("jobs.id")) # Links to the Job table
    txn_id = Column(String, nullable=True)
    date = Column(String) # We will store the cleaned ISO 8601 date as a string
    merchant = Column(String)
    amount = Column(Float)
    currency = Column(String)
    status = Column(String)
    category = Column(String, default="Uncategorised")
    account_id = Column(String)
    notes = Column(String, nullable=True)
    
    # Anomaly and AI Classification fields
    is_anomaly = Column(Boolean, default=False)
    anomaly_reason = Column(String, nullable=True)
    llm_category = Column(String, nullable=True)
    llm_failed = Column(Boolean, default=False)
    
    __table_args__ = (Index("ix_job_anomaly", "job_id", "is_anomaly"),)
    
class JobSummary(Base):
    __tablename__ = "job_summaries"

    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(String, ForeignKey("jobs.id"), unique=True)
    total_spend_inr = Column(Float, default=0.0)
    total_spend_usd = Column(Float, default=0.0)
    top_merchants = Column(String) # We will store this as a JSON string
    anomaly_count = Column(Integer, default=0)
    narrative = Column(String)
    risk_level = Column(String) # low, medium, high