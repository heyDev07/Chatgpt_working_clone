"""add is_pinned to conversations

Revision ID: 60e307098581
Revises: 169d5240ef19
Create Date: 2026-07-22 15:31:01.149076

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '60e307098581'
down_revision: Union[str, None] = '169d5240ef19'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # NOTE: autogenerate also wanted to drop ix_conversations_user_updated and
    # ix_messages_conversation_created - both use a raw sa.text() expression
    # (updated_at DESC) that isn't reflected in the ORM model metadata, so autogenerate
    # can't see they're still wanted. Removed those from this migration; they're untouched.
    op.add_column(
        'conversations',
        sa.Column('is_pinned', sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.alter_column('conversations', 'is_pinned', server_default=None)


def downgrade() -> None:
    op.drop_column('conversations', 'is_pinned')
