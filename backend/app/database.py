import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from dotenv import load_dotenv

load_dotenv()

# We expect POSTGRES_URL in the .env file.
# Default to a local postgres instance if not provided.
DATABASE_URL = os.getenv(
    "POSTGRES_URL", 
    "postgresql://postgres:postgres@localhost:5432/trace_ai"
)

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
