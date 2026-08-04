from sqlalchemy import Boolean, CheckConstraint, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class User(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "users"
    __table_args__ = (CheckConstraint("role IN ('user','admin')", name="ck_users_role"),)

    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # The first account ever registered is auto-promoted to admin (see AuthService.register) -
    # there's no separate admin-invite flow yet, so this is how the system bootstraps its first
    # admin without requiring manual DB surgery.
    role: Mapped[str] = mapped_column(String(20), nullable=False, default="user")
    # "password" or "google" - set on a genuine login (AuthService.issue_tokens's login_method
    # arg), never on a silent refresh-token rotation, so this reflects how the user last actually
    # signed in rather than just how their current session happens to have been renewed.
    last_login_method: Mapped[str | None] = mapped_column(String(20), nullable=True)
