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

from chromadb.api.types import Documents, EmbeddingFunction, Embeddings
from app.config import settings

class GeminiEmbeddingFunction(EmbeddingFunction):
    def __call__(self, input: Documents) -> Embeddings:
        from google import genai
        client = genai.Client(api_key=settings.GEMINI_API_KEY)
        embeddings = []
        for text in input:
            response = client.models.embed_content(
                model='gemini-embedding-2',
                contents=text
            )
            embeddings.append(response.embeddings[0].values)
        return embeddings

def get_collection(dataset_id: str, client=None):
    if not client:
        client = get_chroma_client()
    
    # Chroma collection names must be valid: alphanumeric, underscores, hyphens.
    collection_name = f"logs_{dataset_id.replace('-', '_')}"
    
    # Use Gemini embeddings to completely eliminate PyTorch OOM crashes
    gemini_ef = GeminiEmbeddingFunction()
    
    collection = client.get_or_create_collection(
        name=collection_name, 
        embedding_function=gemini_ef
    )
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
    
    # Process in very small batches of 20 to avoid Gemini API batch and safety limits
    BATCH_SIZE = 20
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
