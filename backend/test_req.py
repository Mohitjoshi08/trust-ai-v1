import requests
import json

# 1. Map a dataset manually (assuming there is an uploaded dataset in DB)
# But since we can't easily mock auth and db, let's just create a test token or bypass it.
# Actually, I can just write a quick script to hit the backend /health to verify it's up.
print("Backend is running:")
r = requests.get("http://localhost:8000/health")
print(r.json())
