import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User


class UserRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, user_id: uuid.UUID) -> User | None:
        return await self.db.get(User, user_id)

    async def get_by_email(self, email: str) -> User | None:
        result = await self.db.execute(select(User).where(User.email == email))
        return result.scalar_one_or_none()

    async def count(self) -> int:
        result = await self.db.execute(select(func.count()).select_from(User))
        return result.scalar_one()

    async def list_all(self) -> list[User]:
        result = await self.db.execute(select(User).order_by(User.created_at))
        return list(result.scalars().all())

    async def create(
        self, email: str, password_hash: str, full_name: str | None, role: str = "user"
    ) -> User:
        user = User(email=email, password_hash=password_hash, full_name=full_name, role=role)
        self.db.add(user)
        await self.db.flush()
        return user

    async def update(
        self, user: User, *, is_active: bool | None = None, role: str | None = None
    ) -> User:
        if is_active is not None:
            user.is_active = is_active
        if role is not None:
            user.role = role
        await self.db.flush()
        await self.db.refresh(user)
        return user

    async def delete(self, user: User) -> None:
        await self.db.delete(user)
        await self.db.flush()
