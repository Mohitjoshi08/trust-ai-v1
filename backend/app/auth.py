import os
import logging
from fastapi import Request, HTTPException, Security, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.db_models import User, Organization
from app.config import settings

logger = logging.getLogger(__name__)

security = HTTPBearer(auto_error=False)

# --- Firebase initialization (only when NOT in demo mode) ---
_firebase_initialized = False

def _ensure_firebase():
    global _firebase_initialized
    if _firebase_initialized:
        return
    try:
        import firebase_admin
        from firebase_admin import credentials
        firebase_cred_path = os.getenv("FIREBASE_CREDENTIALS")
        firebase_cred_json = os.getenv("FIREBASE_SERVICE_ACCOUNT_JSON")

        if firebase_cred_json:
            import json
            cred_dict = json.loads(firebase_cred_json)
            cred = credentials.Certificate(cred_dict)
            firebase_admin.initialize_app(cred)
        elif firebase_cred_path and os.path.exists(firebase_cred_path):
            cred = credentials.Certificate(firebase_cred_path)
            firebase_admin.initialize_app(cred)
        else:
            firebase_admin.initialize_app(options={'projectId': 'traceai-42679'})
        _firebase_initialized = True
    except Exception as e:
        logger.warning(f"Firebase init skipped: {e}")


def verify_firebase_token(credentials: HTTPAuthorizationCredentials = Security(security)):
    """Verify Firebase JWT. In demo mode, returns a mock token."""
    if settings.DEMO_MODE:
        return {"uid": "demo-user", "email": "demo@trace.ai"}

    if credentials is None:
        raise HTTPException(status_code=401, detail="Missing authorization token")

    _ensure_firebase()
    try:
        from firebase_admin import auth
        token = credentials.credentials
        decoded_token = auth.verify_id_token(token)
        return decoded_token
    except Exception as e:
        logger.error(f"Firebase token verification failed: {str(e)}")
        raise HTTPException(
            status_code=401,
            detail=f"Invalid Firebase token: {str(e)}"
        )

def get_current_user(
    decoded_token: dict = Depends(verify_firebase_token),
    db: Session = Depends(get_db)
):
    """Get or create the current user. In demo mode, returns a mock user."""
    if settings.DEMO_MODE:
        # Return a lightweight mock user object for demo mode
        return type('MockUser', (), {
            'id': 'demo-user-id',
            'firebase_uid': 'demo-user',
            'email': 'demo@trace.ai',
            'org_id': 'demo-org-id',
            'role': 'admin'
        })()

    firebase_uid = decoded_token.get("uid")
    email = decoded_token.get("email")

    user = db.query(User).filter(User.firebase_uid == firebase_uid).first()

    # If the user doesn't exist, auto-create them and an organization for MVP
    if not user:
        org = Organization(name=f"{email}'s Organization")
        db.add(org)
        db.flush()  # flush to get org.id

        user = User(
            firebase_uid=firebase_uid,
            email=email,
            org_id=org.id
        )
        db.add(user)
        db.commit()
        db.refresh(user)

    return user
