import os
import shutil
import uuid
from typing import Optional
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends, Query
from sqlalchemy.orm import Session
from app.tasks import process_transactions_task
from app.database import get_db
# FIXED: Imported all required SQLAlchemy models
from app.models import Job, Transaction, JobSummary
from app.schemas import JobListResponse


os.makedirs("/app/uploads", exist_ok=True)

router = APIRouter(
    prefix="/jobs",
    tags=["Jobs"]
)

@router.post("/upload", status_code=202)
def upload_transactions(
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """
    Accepts a CSV file, creates an audit tracking job, and dispatches background processing.
    NOTE: Defined as synchronous ('def') so FastAPI offloads disk I/O to a threadpool!
    """
    if not file.filename or not file.filename.endswith('.csv'):
        raise HTTPException(status_code=400, detail="Only CSV files are allowed.")
    
    job_id = str(uuid.uuid4())
    file_path = f"/app/uploads/{job_id}_{file.filename}"
    
    # Threadpool-safe synchronous disk writing
    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save file to disk: {str(e)}")
        
    new_job = Job(
        id=job_id,
        filename=file.filename,
        status="pending"
    )
    
    try:
        db.add(new_job)
        db.commit()
        db.refresh(new_job)
    except Exception as e:
        db.rollback()
        # Clean up orphaned disk file if DB commit fails
        if os.path.exists(file_path):
            os.remove(file_path)
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
        
    # Dispatch to Celery background worker
    try:
        process_transactions_task.delay(job_id, file_path)
    except Exception as e:
        # If Redis is unreachable, mark job as failed immediately
        new_job.status = "failed"
        new_job.error_message = "Message broker unreachable."
        db.commit()
        raise HTTPException(status_code=503, detail="Background task queue is currently unavailable.")

    return {
        "message": "File uploaded and job created successfully",
        "job_id": new_job.id,
        "status": new_job.status
    }
  
@router.get("/{job_id}/status")
def get_status(job_id: str, db: Session = Depends(get_db)):
    """
    Polling endpoint for clients to check background job progress.
    """
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
        
    response = {
        "job_id": job.id,
        "status": job.status,
        "filename": job.filename
    }
    if job.status == "failed" and job.error_message:
        response["error"] = job.error_message
        
    return response

@router.get("/{job_id}/results")
def get_results(
    job_id: str, 
    limit: int = Query(100, ge=1, le=1000, description="Number of transactions to return"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    db: Session = Depends(get_db)
):
    """
    Returns the AI summary report and paginated transaction results to prevent OOM errors.
    """
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status != "completed":
        raise HTTPException(status_code=400, detail=f"Results not ready. Current status: {job.status}")
    
    # Fetch summary
    summary = db.query(JobSummary).filter(JobSummary.job_id == job_id).first()
    
    # 100x Scale Optimization: Paginated database query instead of .all()
    transactions_query = db.query(Transaction).filter(Transaction.job_id == job_id)
    total_count = transactions_query.count()
    transactions = transactions_query.offset(offset).limit(limit).all()
    
    return {
        "job_id": job.id,
        "status": job.status,
        "pagination": {
            "total_records": total_count,
            "limit": limit,
            "offset": offset,
            "has_more": (offset + limit) < total_count
        },
        "summary": summary,
        "transactions": transactions
    }
    
@router.get("/", response_model=JobListResponse)
def list_jobs(
    status: Optional[str] = Query(None, description="Filter jobs by status (e.g., pending, processing, completed, failed)"),
    limit: int = Query(50, ge=1, le=200, description="Number of jobs to return per request"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    db: Session = Depends(get_db)
):
    """
    List all transaction processing jobs with optional status filtering and pagination.
    Ordered by creation date (newest first).
    """
    # Start with the base query
    query = db.query(Job)
    
    # Apply optional status filter if provided in the URL query parameters (?status=completed)
    if status:
        # Normalize status to lowercase to prevent case-sensitivity bugs
        query = query.filter(Job.status == status.lower().strip())
        
    # Get total count before applying limit/offset for the pagination metadata
    total_count = query.count()
    
    # Apply ordering (newest first) and pagination
    jobs = query.order_by(Job.created_at.desc()).offset(offset).limit(limit).all()
    
    return {
        "total_jobs": total_count,
        "limit": limit,
        "offset": offset,
        "jobs": jobs
    } 