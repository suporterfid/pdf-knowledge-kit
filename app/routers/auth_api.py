from fastapi import APIRouter, Depends

from ..core.auth import TenantTokenPayload
from ..security.auth import get_current_token_payload, require_role

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.get("/roles")
async def get_roles(
    role: str = Depends(require_role("viewer")),
    payload: TenantTokenPayload = Depends(get_current_token_payload),
):
    roles = payload.get("roles") or []
    if isinstance(roles, str):  # pragma: no cover - defensive
        roles = [roles]
    if role not in roles:
        roles.append(role)
    return {"roles": sorted(set(roles))}
