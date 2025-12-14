from fastapi import APIRouter

from app.data.seed import get_members

router = APIRouter()


@router.get("/members")
def list_members() -> list[dict]:
    return get_members()

