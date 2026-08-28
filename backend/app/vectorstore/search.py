from typing import List
from datetime import datetime, timedelta
import pandas as pd
from app.models.schemas import LogDocument
from app.vectorstore.ingest import get_collection

async def search_logs(
    query: str,
    start_time: datetime,
    end_time: datetime,
    time_buffer_hours: int = 24,
    top_k: int = 10
) -> List[LogDocument]:
    
    collection = get_collection()
    
    # Expand window
    effective_start = start_time - timedelta(hours=time_buffer_hours)
    effective_end = end_time + timedelta(hours=2)
    
    # Format to ISO string for string-based comparison in Chroma (if stored as strings)
    # Note: Chroma filters operate lexicographically on strings, so ISO 8601 works perfectly.
    effective_start_str = effective_start.isoformat() + "Z" if not effective_start.tzinfo else effective_start.isoformat()
    effective_end_str = effective_end.isoformat() + "Z" if not effective_end.tzinfo else effective_end.isoformat()
    
    # Semantic search with the query within the filtered set
    results = collection.query(
        query_texts=[query],
        n_results=top_k,
        where={
            "$and": [
                {"timestamp": {"$gte": effective_start_str}},
                {"timestamp": {"$lte": effective_end_str}}
            ]
        }
    )
    
    documents: List[LogDocument] = []
    
    if not results or not results['ids'] or not results['ids'][0]:
        return documents
        
    ids = results['ids'][0]
    docs = results['documents'][0]
    metadatas = results['metadatas'][0]
    distances = results['distances'][0] if 'distances' in results and results['distances'] else [0.0]*len(ids)
    
    for i in range(len(ids)):
        # Convert distance to a similarity score (1 - normalized distance, very roughly)
        # For L2 distance (Chroma default), lower is better. Let's just do a simple inversion or cap.
        sim_score = max(0.0, 1.0 - (distances[i] / 2.0))
        
        # Parse timestamp safely
        try:
            ts = pd.to_datetime(metadatas[i]["timestamp"]).to_pydatetime()
        except:
            ts = datetime.utcnow()
            
        doc = LogDocument(
            id=ids[i],
            timestamp=ts,
            source=metadatas[i]["source"],
            text_content=docs[i],
            similarity_score=sim_score,
            matched_query=query
        )
        documents.append(doc)
        
    # Sort by relevance score
    documents.sort(key=lambda x: x.similarity_score, reverse=True)
    return documents
