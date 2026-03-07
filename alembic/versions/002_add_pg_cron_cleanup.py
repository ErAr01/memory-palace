"""Add pg_cron cleanup for old messages

Revision ID: 002
Revises: 001
Create Date: 2026-03-07

"""
from typing import Sequence, Union

from alembic import op

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_cron")
    
    op.execute("""
        CREATE OR REPLACE FUNCTION cleanup_old_messages()
        RETURNS void AS $$
        DECLARE
            deleted_count INTEGER;
        BEGIN
            DELETE FROM messages WHERE date < NOW() - INTERVAL '30 days';
            GET DIAGNOSTICS deleted_count = ROW_COUNT;
            RAISE NOTICE 'Deleted % old messages', deleted_count;
            
            UPDATE chat_index_status 
            SET indexed_from_date = GREATEST(indexed_from_date, NOW() - INTERVAL '30 days')
            WHERE indexed_from_date < NOW() - INTERVAL '30 days';
        END;
        $$ LANGUAGE plpgsql;
    """)
    
    op.execute("""
        SELECT cron.schedule(
            'cleanup-old-messages',
            '0 3 * * *',
            'SELECT cleanup_old_messages()'
        );
    """)


def downgrade() -> None:
    op.execute("SELECT cron.unschedule('cleanup-old-messages')")
    op.execute("DROP FUNCTION IF EXISTS cleanup_old_messages()")
    op.execute("DROP EXTENSION IF EXISTS pg_cron")
