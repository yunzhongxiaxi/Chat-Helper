from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from pathlib import Path
from backend.services.parser_agent import parser_agent
from backend.services.profile_service import create_profile_service
from backend.services.rag_service import create_rag_service
from backend.models.db import Database
from backend.config import config

router = APIRouter(prefix="/api", tags=["upload"])

@router.post("/upload")
async def upload_chat_records(
    file: UploadFile = File(...),
    contact_id: str = Form(...)
):
    try:
        content = await file.read()
        suffix = Path(file.filename or '').suffix.lower()

        if suffix == '.xlsx':
            records = parser_agent.parse_xlsx_records(content, contact_id)
        else:
            file_content = content.decode('utf-8')
            records = parser_agent.parse_records(file_content, contact_id)

        db = Database(config.database.get('path', './data/chathelper.db'))
        new_records = db.insert_new_chat_records(contact_id, records)

        if new_records:
            profile_service = create_profile_service()
            profile_service.generate_profile(contact_id, new_records)

            rag_service = create_rag_service()
            rag_service.insert_records(contact_id, new_records)

        return {
            "success": True,
            "message": "解析成功",
            "records_count": len(records),
            "new_records_count": len(new_records),
            "skipped_records_count": len(records) - len(new_records)
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
