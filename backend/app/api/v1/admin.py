import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_admin_user, get_db
from app.models.user import User
from app.schemas.admin import UserAdminOut, UserRoleUpdate, UserStatusUpdate
from app.schemas.analytics import UsageOverview
from app.services.admin_service import AdminService
from app.services.analytics_service import AnalyticsService

router = APIRouter(prefix="/admin", tags=["admin"])


def _get_service(db: AsyncSession = Depends(get_db)) -> AdminService:
    return AdminService(db)


def _get_analytics_service(db: AsyncSession = Depends(get_db)) -> AnalyticsService:
    return AnalyticsService(db)


@router.get("/analytics/usage", response_model=UsageOverview)
async def get_usage_analytics(
    days: int = 14,
    admin: User = Depends(get_current_admin_user),
    service: AnalyticsService = Depends(_get_analytics_service),
):
    return await service.get_overview(days=days)


@router.get("/users", response_model=list[UserAdminOut])
async def list_users(
    admin: User = Depends(get_current_admin_user),
    service: AdminService = Depends(_get_service),
):
    return await service.list_users()


@router.patch("/users/{user_id}/status", response_model=UserAdminOut)
async def set_user_status(
    user_id: uuid.UUID,
    payload: UserStatusUpdate,
    admin: User = Depends(get_current_admin_user),
    service: AdminService = Depends(_get_service),
):
    return await service.set_user_status(admin.id, user_id, payload.is_active)


@router.patch("/users/{user_id}/role", response_model=UserAdminOut)
async def set_user_role(
    user_id: uuid.UUID,
    payload: UserRoleUpdate,
    admin: User = Depends(get_current_admin_user),
    service: AdminService = Depends(_get_service),
):
    return await service.set_user_role(admin.id, user_id, payload.role)
