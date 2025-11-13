from typing import Annotated

from fastapi import APIRouter, Depends

from ..core.auth import TenantTokenPayload
from ..security.auth import get_current_token_payload, require_role

router = APIRouter(prefix="/api/auth", tags=["auth"])

ViewerRole = Annotated[str, Depends(require_role("viewer"))]
TokenPayloadDep = Annotated[TenantTokenPayload, Depends(get_current_token_payload)]


@router.get("/roles")
async def get_roles(role: ViewerRole, payload: TokenPayloadDep):
    roles = payload.get("roles") or []
    if isinstance(roles, str):  # pragma: no cover - defensive
        roles = [roles]
    if role not in roles:
        roles.append(role)
    return {"roles": sorted(set(roles))}
