import json
import logging
import chromadb
from chromadb.config import Settings
from pathlib import Path

logger = logging.getLogger(__name__)

def get_chroma_client():
    # Use persistent storage at ./chroma_db in backend root
    current_dir = Path(__file__).resolve().parent
    db_path = current_dir.parent.parent / "chroma_db"
    
    client = chromadb.PersistentClient(path=str(db_path))
    return client

def get_collection(client=None):
    if not client:
        client = get_chroma_client()
    # all-MiniLM-L6-v2 is the default embedding function used by Chroma if none is provided.
    collection = client.get_or_create_collection(name="operational_logs")
    return collection

async def ingest_logs(logs_path: str) -> int:
    """Load JSON logs, embed, and store in ChromaDB. Returns count."""
    try:
        with open(logs_path, "r", encoding="utf-8") as f:
            logs = json.load(f)
    except FileNotFoundError:
        logger.error(f"Logs file not found at {logs_path}")
        return 0
        
    if not logs:
        return 0
        
    collection = get_collection()
    
    ids = []
    documents = []
    metadatas = []
    
    for log in logs:
        ids.append(log["id"])
        documents.append(log["text_content"])
        metadatas.append({
            "timestamp": log["timestamp"],
            "source": log["source"]
        })
        
    # Chroma can handle batches, but for our synthetic data (~56 logs) we can do it in one go.
    collection.upsert(
        ids=ids,
        documents=documents,
        metadatas=metadatas
    )
    
    logger.info(f"Ingested {len(ids)} logs into ChromaDB.")
    return len(ids)
