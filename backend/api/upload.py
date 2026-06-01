from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from typing import Optional
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
    contact_id: Optional[str] = Form(None)
):
    try:
        content = await file.read()
        suffix = Path(file.filename or '').suffix.lower()

        metadata = {}
        if suffix == '.xlsx':
            parsed = parser_agent.parse_xlsx(content)
            metadata = parsed['metadata']
            records = parsed['records']
            contact_id = contact_id or metadata.get('contact_id')
        else:
            if not contact_id:
                raise HTTPException(status_code=400, detail="非 XLSX 文件必须提供 contact_id")
            file_content = content.decode('utf-8')
            records = parser_agent.parse_records(file_content, contact_id)

        if not contact_id:
            raise HTTPException(status_code=400, detail="未提供 contact_id，且文件中未解析到微信ID")

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
            "skipped_records_count": len(records) - len(new_records),
            "contact_id": contact_id,
            "metadata": metadata
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
