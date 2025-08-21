from fastapi import APIRouter, Depends

from ..security.auth import require_role

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.get("/roles")
async def get_roles(role: str = Depends(require_role("viewer"))):
    return {"roles": [role]}
