from fastapi import APIRouter

from app.data.seed import get_projects

router = APIRouter()


@router.get("/projects")
def list_projects() -> list[dict]:
    return get_projects()

