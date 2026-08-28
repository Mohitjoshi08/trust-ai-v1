import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    DEMO_MODE: bool = os.getenv("DEMO_MODE", "true").lower() == "true"
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    CACHE_DIR: str = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "golden_cache")
    DATA_DIR: str = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")

settings = Settings()
