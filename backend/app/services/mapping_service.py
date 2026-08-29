import json
import os
from typing import Dict, Any, List
from google import genai

def generate_schema_mapping(platform: str, columns: List[str]) -> Dict[str, Any]:
    """Uses LLM to automatically map source columns to target Trace.ai schema."""
    
    prompt = f"""
    You are a data mapping assistant. We have a source dataset from {platform} with the following columns:
    {json.dumps(columns)}
    
    Map these columns to our internal metrics system which expects:
    1. A primary timestamp/date column (key: 'timestamp').
    2. A primary metric column (e.g. revenue, amount, sessions, sales) (key: 'metric').
    3. Additional dimension columns (key: 'dimensions', as a list of strings).
    
    Return the result strictly as a JSON object with keys: 'timestamp', 'metric', and 'dimensions'.
    Only output valid JSON, no markdown formatting.
    """

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return _fallback_mapping(platform, columns)

    try:
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=prompt
        )
        text = response.text.strip()
        if text.startswith("```json"):
            text = text[7:-3]
        elif text.startswith("```"):
            text = text[3:-3]
        return json.loads(text.strip())
    except Exception as e:
        print(f"LLM mapping failed: {e}")
        return _fallback_mapping(platform, columns)

def _fallback_mapping(platform: str, columns: List[str]) -> Dict[str, Any]:
    if platform == "shopify":
        return {"timestamp": "created_at", "metric": "total_price", "dimensions": ["currency", "order_number"]}
    elif platform == "stripe":
        return {"timestamp": "created", "metric": "amount", "dimensions": ["currency", "status"]}
    elif platform == "google_analytics":
        return {"timestamp": "date", "metric": "sessions", "dimensions": ["pageviews", "bounce_rate"]}
    elif platform == "csv":
        return {"timestamp": "date", "metric": "revenue", "dimensions": ["region", "product_name"]}
    return {"timestamp": columns[0] if columns else "", "metric": columns[1] if len(columns) > 1 else "", "dimensions": columns[2:] if len(columns) > 2 else []}
