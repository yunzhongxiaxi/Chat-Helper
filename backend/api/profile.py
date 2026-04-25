from fastapi import APIRouter, HTTPException
from backend.models.db import Database
from backend.config import config

router = APIRouter(prefix="/api", tags=["profile"])

@router.get("/profile/{contact_id}")
async def get_profile(contact_id: str):
    try:
        db = Database(config.database.get('path', './data/chathelper.db'))
        profile = db.get_profile(contact_id)

        if not profile:
            raise HTTPException(status_code=404, detail="画像不存在")

        return {
            "contact_id": contact_id,
            "user_profile": profile['user_profile'],
            "contact_profile": profile['contact_profile'],
            "updated_at": profile['updated_at']
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
