"""Initial migration

Revision ID: 001
Revises: 
Create Date: 2026-03-06

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "messages",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("chat_id", sa.BigInteger(), nullable=False),
        sa.Column("chat_username", sa.String(255), nullable=True),
        sa.Column("message_id", sa.BigInteger(), nullable=False),
        sa.Column("text", sa.Text(), nullable=True),
        sa.Column("date", sa.DateTime(), nullable=True),
        sa.Column("sender_id", sa.BigInteger(), nullable=True),
        sa.Column("embedding", Vector(1536), nullable=True),
        sa.Column(
            "indexed_at",
            sa.DateTime(),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_messages_chat_id_message_id",
        "messages",
        ["chat_id", "message_id"],
        unique=True,
    )
    op.create_index(
        "ix_messages_chat_id_date",
        "messages",
        ["chat_id", "date"],
    )
    op.execute(
        "CREATE INDEX ix_messages_embedding ON messages "
        "USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100)"
    )

    op.create_table(
        "chat_index_status",
        sa.Column("chat_id", sa.BigInteger(), nullable=False),
        sa.Column("chat_username", sa.String(255), nullable=True),
        sa.Column("last_indexed_at", sa.DateTime(), nullable=False),
        sa.Column("indexed_from_date", sa.DateTime(), nullable=True),
        sa.Column("indexed_until_date", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("chat_id"),
    )


def downgrade() -> None:
    op.drop_table("chat_index_status")
    op.drop_index("ix_messages_embedding", table_name="messages")
    op.drop_index("ix_messages_chat_id_date", table_name="messages")
    op.drop_index("ix_messages_chat_id_message_id", table_name="messages")
    op.drop_table("messages")
    op.execute("DROP EXTENSION IF EXISTS vector")
