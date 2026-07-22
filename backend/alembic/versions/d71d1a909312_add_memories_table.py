"""add memories table

Revision ID: d71d1a909312
Revises: d7f67e3377f6
Create Date: 2026-07-22 17:12:57.036482

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd71d1a909312'
down_revision: Union[str, None] = 'd7f67e3377f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # NOTE: autogenerate also wanted to drop ix_conversations_user_updated and
    # ix_messages_conversation_created (see the same note in prior migrations) - removed,
    # untouched here.
    op.create_table('memories',
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('category', sa.String(length=50), nullable=False),
    sa.Column('memory_text', sa.Text(), nullable=False),
    sa.Column('importance', sa.Float(), nullable=False),
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_memories_user_id'), 'memories', ['user_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_memories_user_id'), table_name='memories')
    op.drop_table('memories')
