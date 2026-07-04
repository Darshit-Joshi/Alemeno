from pydantic import BaseModel
from datetime import datetime
from typing import Optional, List

class JobResponse(BaseModel):
    id: str
    filename: str
    status: str
    row_count_raw: int
    row_count_clean: int
    created_at: datetime
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None

    class Config:
        from_attributes = True  # Allows Pydantic to read directly from SQLAlchemy ORM objects

class JobListResponse(BaseModel):
    total_jobs: int
    limit: int
    offset: int
    jobs: List[JobResponse]