import os
import firebase_admin
from firebase_admin import credentials, auth
from fastapi import Request, HTTPException, Security, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.db_models import User, Organization

security = HTTPBearer()

# Initialize Firebase Admin
# In production, use a service account JSON file
# e.g., cred = credentials.Certificate("path/to/serviceAccountKey.json")
# Here we'll try to initialize default if FIREBASE_CREDENTIALS is set
firebase_cred_path = os.getenv("FIREBASE_CREDENTIALS")
if firebase_cred_path and os.path.exists(firebase_cred_path):
    cred = credentials.Certificate(firebase_cred_path)
    firebase_admin.initialize_app(cred)
else:
    # This might fail if no default credentials are found, but we'll try
    try:
        firebase_admin.initialize_app()
    except ValueError:
        print("Warning: Firebase Admin app already initialized or no credentials provided.")


def verify_firebase_token(credentials: HTTPAuthorizationCredentials = Security(security)):
    token = credentials.credentials
    try:
        decoded_token = auth.verify_id_token(token)
        return decoded_token
    except Exception as e:
        raise HTTPException(
            status_code=401,
            detail=f"Invalid Firebase token: {str(e)}"
        )

def get_current_user(
    decoded_token: dict = Depends(verify_firebase_token),
    db: Session = Depends(get_db)
):
    firebase_uid = decoded_token.get("uid")
    email = decoded_token.get("email")

    user = db.query(User).filter(User.firebase_uid == firebase_uid).first()
    
    # If the user doesn't exist, we could auto-create them and an organization for MVP
    if not user:
        org = Organization(name=f"{email}'s Organization")
        db.add(org)
        db.flush() # flush to get org.id

        user = User(
            firebase_uid=firebase_uid,
            email=email,
            org_id=org.id
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        
    return user
