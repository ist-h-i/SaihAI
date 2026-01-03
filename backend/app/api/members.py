from fastapi import APIRouter, Depends
from sqlalchemy.engine import Connection

from app.db import get_db
from app.db.repository import fetch_members

router = APIRouter()


@router.get("/members")
def list_members(conn: Connection = Depends(get_db)) -> list[dict]:
    return fetch_members(conn)
