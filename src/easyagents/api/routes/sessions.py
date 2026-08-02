from fastapi import APIRouter, HTTPException
from easyagents import SessionManager, SQLiteSessionStore

router = APIRouter()
_session_mgr = SessionManager(SQLiteSessionStore(":memory:"))


@router.get("/")
async def list_sessions():
    return {"sessions": _session_mgr.list_sessions()}


@router.post("/", status_code=201)
async def create_session():
    session = _session_mgr.create()
    return {"conversation_id": session.conversation_id}


@router.get("/{conversation_id}")
async def get_session(conversation_id: str):
    session = _session_mgr.get(conversation_id)
    if not session:
        raise HTTPException(404, "Session not found")
    return {"conversation_id": session.conversation_id, "message_count": len(session.messages)}


@router.delete("/{conversation_id}", status_code=204)
async def delete_session(conversation_id: str):
    session = _session_mgr.get(conversation_id)
    if not session:
        raise HTTPException(404, "Session not found")
    _session_mgr.delete(conversation_id)
