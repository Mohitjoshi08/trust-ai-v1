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

def get_collection(dataset_id: str, client=None):
    if not client:
        client = get_chroma_client()
    
    # Chroma collection names must be valid: alphanumeric, underscores, hyphens.
    collection_name = f"logs_{dataset_id.replace('-', '_')}"
    # all-MiniLM-L6-v2 is the default embedding function used by Chroma if none is provided.
    collection = client.get_or_create_collection(name=collection_name)
    return collection

def ingest_logs(dataset_id: str, logs_path: str) -> int:
    """Load JSON logs, embed, and store in ChromaDB. Returns count.
    
    NOTE: This is intentionally a sync function (not async) so that 
    FastAPI's BackgroundTasks runs it in a thread pool, keeping the 
    main event loop free for other requests.
    """
    try:
        with open(logs_path, "r", encoding="utf-8") as f:
            logs = json.load(f)
    except FileNotFoundError:
        logger.error(f"Logs file not found at {logs_path}")
        return 0
        
    if not logs:
        return 0
        
    collection = get_collection(dataset_id)
    
    # Process in batches of 500 to avoid memory spikes with large log sets
    BATCH_SIZE = 500
    total = len(logs)
    
    for i in range(0, total, BATCH_SIZE):
        batch = logs[i:i + BATCH_SIZE]
        ids = [log["id"] for log in batch]
        documents = [log["text_content"] for log in batch]
        metadatas = [{"timestamp": log["timestamp"], "source": log["source"]} for log in batch]
        
        collection.upsert(
            ids=ids,
            documents=documents,
            metadatas=metadatas
        )
        logger.info(f"Ingested batch {i // BATCH_SIZE + 1}/{(total + BATCH_SIZE - 1) // BATCH_SIZE} ({len(batch)} logs)")
    
    logger.info(f"Ingested {total} logs total into ChromaDB for dataset {dataset_id}.")
    return total
