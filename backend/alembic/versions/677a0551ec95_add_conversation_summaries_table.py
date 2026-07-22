"""add conversation_summaries table

Revision ID: 677a0551ec95
Revises: d71d1a909312
Create Date: 2026-07-22 23:01:39.038395

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '677a0551ec95'
down_revision: Union[str, None] = 'd71d1a909312'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # NOTE: autogenerate also wanted to drop ix_conversations_user_updated and
    # ix_messages_conversation_created (see the same note in prior migrations) - removed,
    # untouched here.
    op.create_table('conversation_summaries',
    sa.Column('conversation_id', sa.UUID(), nullable=False),
    sa.Column('summary', sa.Text(), nullable=False),
    sa.Column('summarized_through_message_id', sa.UUID(), nullable=True),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['conversation_id'], ['conversations.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['summarized_through_message_id'], ['messages.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('conversation_id')
    )


def downgrade() -> None:
    op.drop_table('conversation_summaries')
