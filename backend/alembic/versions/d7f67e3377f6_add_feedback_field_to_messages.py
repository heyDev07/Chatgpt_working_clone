"""add feedback field to messages

Revision ID: d7f67e3377f6
Revises: ef7ab9407ba7
Create Date: 2026-07-22 17:03:27.619197

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd7f67e3377f6'
down_revision: Union[str, None] = 'ef7ab9407ba7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # NOTE: autogenerate also wanted to drop ix_conversations_user_updated and
    # ix_messages_conversation_created (see the same note in prior migrations) - removed,
    # untouched here. It also didn't detect the new CHECK constraint (constraint diffing
    # isn't enabled by default), so that's added explicitly below.
    op.add_column('messages', sa.Column('feedback', sa.String(length=10), nullable=True))
    op.create_check_constraint('ck_messages_feedback', 'messages', "feedback IN ('up','down')")


def downgrade() -> None:
    op.drop_constraint('ck_messages_feedback', 'messages', type_='check')
    op.drop_column('messages', 'feedback')
