from datetime import datetime, timedelta

from sqlalchemy import delete, func, select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models import ChatIndexStatus, Message


class MessageRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def upsert_messages(self, messages: list[dict]) -> int:
        """Insert or update messages. Returns count of affected rows."""
        if not messages:
            return 0

        stmt = insert(Message).values(messages)
        stmt = stmt.on_conflict_do_update(
            index_elements=["chat_id", "message_id"],
            set_={
                "text": stmt.excluded.text,
                "embedding": stmt.excluded.embedding,
                "indexed_at": datetime.utcnow(),
            },
        )
        result = await self.session.execute(stmt)
        await self.session.commit()
        return result.rowcount

    async def search_similar(
        self,
        embedding: list[float],
        chat_ids: list[int] | None = None,
        from_date: datetime | None = None,
        limit: int = 50,
    ) -> list[Message]:
        """Search for similar messages using pgvector cosine distance."""
        query = select(Message).where(Message.embedding.isnot(None))

        if chat_ids:
            query = query.where(Message.chat_id.in_(chat_ids))

        if from_date:
            query = query.where(Message.date >= from_date)

        query = query.order_by(Message.embedding.cosine_distance(embedding))
        query = query.limit(limit)

        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_messages_by_chat(
        self,
        chat_id: int,
        from_date: datetime | None = None,
        to_date: datetime | None = None,
    ) -> list[Message]:
        """Get messages from a specific chat within date range."""
        query = select(Message).where(Message.chat_id == chat_id)

        if from_date:
            query = query.where(Message.date >= from_date)
        if to_date:
            query = query.where(Message.date <= to_date)

        query = query.order_by(Message.date.desc())
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def delete_old_messages(self, days: int = 30) -> int:
        """Delete messages older than specified days."""
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        stmt = delete(Message).where(Message.date < cutoff_date)
        result = await self.session.execute(stmt)
        await self.session.commit()
        return result.rowcount


class ChatIndexStatusRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_status(self, chat_id: int) -> ChatIndexStatus | None:
        """Get index status for a chat."""
        result = await self.session.execute(
            select(ChatIndexStatus).where(ChatIndexStatus.chat_id == chat_id)
        )
        return result.scalar_one_or_none()

    async def get_statuses(self, chat_ids: list[int]) -> dict[int, ChatIndexStatus]:
        """Get index statuses for multiple chats."""
        result = await self.session.execute(
            select(ChatIndexStatus).where(ChatIndexStatus.chat_id.in_(chat_ids))
        )
        return {status.chat_id: status for status in result.scalars().all()}

    async def upsert_status(
        self,
        chat_id: int,
        chat_username: str | None,
        indexed_from_date: datetime,
        indexed_until_date: datetime,
    ) -> None:
        """
        Update or insert index status for a chat.
        
        On conflict, expands the indexed range instead of overwriting:
        - indexed_from_date becomes the earlier of existing and new
        - indexed_until_date becomes the later of existing and new
        """
        stmt = insert(ChatIndexStatus).values(
            chat_id=chat_id,
            chat_username=chat_username,
            last_indexed_at=datetime.utcnow(),
            indexed_from_date=indexed_from_date,
            indexed_until_date=indexed_until_date,
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=["chat_id"],
            set_={
                "chat_username": chat_username,
                "last_indexed_at": datetime.utcnow(),
                "indexed_from_date": func.least(
                    ChatIndexStatus.indexed_from_date, indexed_from_date
                ),
                "indexed_until_date": func.greatest(
                    ChatIndexStatus.indexed_until_date, indexed_until_date
                ),
            },
        )
        await self.session.execute(stmt)
        await self.session.commit()

    async def needs_reindex(
        self, chat_id: int, cache_minutes: int = 60
    ) -> bool:
        """Check if chat needs reindexing based on cache time."""
        status = await self.get_status(chat_id)
        if status is None:
            return True

        cache_threshold = datetime.utcnow() - timedelta(minutes=cache_minutes)
        return status.last_indexed_at < cache_threshold

    def get_missing_ranges(
        self,
        status: ChatIndexStatus | None,
        requested_from: datetime,
        requested_until: datetime,
    ) -> list[tuple[datetime, datetime]]:
        """
        Calculate missing time ranges that need to be indexed.
        
        Args:
            status: Current index status for the chat (or None if never indexed)
            requested_from: Start of requested period
            requested_until: End of requested period
            
        Returns:
            List of (from_date, to_date) tuples representing gaps to fill
        """
        if status is None or status.indexed_from_date is None or status.indexed_until_date is None:
            return [(requested_from, requested_until)]
        
        missing_ranges = []
        
        if requested_from < status.indexed_from_date:
            missing_ranges.append((requested_from, status.indexed_from_date))
        
        if requested_until > status.indexed_until_date:
            missing_ranges.append((status.indexed_until_date, requested_until))
        
        return missing_ranges

    def is_cache_fresh(
        self,
        status: ChatIndexStatus | None,
        cache_minutes: int = 60,
    ) -> bool:
        """Check if cache is still fresh (indexed recently)."""
        if status is None:
            return False
        cache_threshold = datetime.utcnow() - timedelta(minutes=cache_minutes)
        return status.last_indexed_at >= cache_threshold


async def init_pgvector(session: AsyncSession) -> None:
    """Initialize pgvector extension."""
    await session.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    await session.commit()
