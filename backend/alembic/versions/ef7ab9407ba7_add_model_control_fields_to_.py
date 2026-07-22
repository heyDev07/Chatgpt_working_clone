"""add model control fields to conversations

Revision ID: ef7ab9407ba7
Revises: 60e307098581
Create Date: 2026-07-22 16:51:01.203011

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ef7ab9407ba7'
down_revision: Union[str, None] = '60e307098581'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # NOTE: autogenerate also wanted to drop ix_conversations_user_updated and
    # ix_messages_conversation_created (see the same note in the two prior migrations) -
    # removed those, they're untouched by this migration.
    op.add_column('conversations', sa.Column('system_prompt', sa.Text(), nullable=True))
    op.add_column('conversations', sa.Column('temperature', sa.Float(), nullable=True))
    op.add_column('conversations', sa.Column('max_tokens', sa.Integer(), nullable=True))
    op.add_column('conversations', sa.Column('top_p', sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column('conversations', 'top_p')
    op.drop_column('conversations', 'max_tokens')
    op.drop_column('conversations', 'temperature')
    op.drop_column('conversations', 'system_prompt')
