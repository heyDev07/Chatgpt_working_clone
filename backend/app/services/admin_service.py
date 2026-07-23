import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, ValidationAppError
from app.models.user import User
from app.repositories.user_repo import UserRepository


class AdminService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.users = UserRepository(db)

    async def list_users(self) -> list[User]:
        return await self.users.list_all()

    async def set_user_status(self, acting_user_id: uuid.UUID, user_id: uuid.UUID, is_active: bool) -> User:
        if user_id == acting_user_id and not is_active:
            raise ValidationAppError("You cannot deactivate your own account")
        user = await self.users.get_by_id(user_id)
        if not user:
            raise NotFoundError("User not found")
        user = await self.users.update(user, is_active=is_active)
        await self.db.commit()
        return user

    async def set_user_role(self, acting_user_id: uuid.UUID, user_id: uuid.UUID, role: str) -> User:
        if user_id == acting_user_id and role != "admin":
            raise ValidationAppError("You cannot remove your own admin access")
        user = await self.users.get_by_id(user_id)
        if not user:
            raise NotFoundError("User not found")
        user = await self.users.update(user, role=role)
        await self.db.commit()
        return user
