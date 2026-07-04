import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@db:5432/alemenodb")

engine = create_engine(DATABASE_URL,pool_size=20,          # Maintain 20 open connections in the pool
    max_overflow=30,       
    pool_timeout=30,       
    pool_pre_ping=True,    
    pool_recycle=1800)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
  db = SessionLocal()
  try:
    yield db
  finally:
    db.close()
    
