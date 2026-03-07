import logging
from datetime import datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from src.ai.embeddings import generate_embeddings_batch
from src.config import ChatIdentifier, get_chats_config
from src.database.repository import ChatIndexStatusRepository, MessageRepository
from src.indexer.client import get_indexer

logger = logging.getLogger(__name__)


class IndexingService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.message_repo = MessageRepository(session)
        self.status_repo = ChatIndexStatusRepository(session)
        self.indexer = get_indexer()
        self.config = get_chats_config()

    async def index_chats(
        self,
        chats: list[ChatIdentifier] | list[str] | None = None,
        days: int | None = None,
        force: bool = False,
    ) -> dict[str, int]:
        """
        Index messages from specified chats with smart incremental loading.
        
        Args:
            chats: List of ChatIdentifier or strings (username/ID) to index.
                   If None, uses default chats from config.
            days: Number of days to index. If None, uses default from config.
            force: If True, ignores cache and forces full reindexing.
        
        Returns:
            Dict mapping chat display name to number of messages indexed.
            -1 means skipped (cache fresh and no missing ranges).
        """
        if chats is None:
            chat_identifiers = self.config.get_chat_identifiers()
        else:
            chat_identifiers = [
                c if isinstance(c, ChatIdentifier) else ChatIdentifier.from_string(c)
                for c in chats
            ]
        
        if days is None:
            days = self.config.default_days
        
        days = min(days, self.config.max_days)
        cache_minutes = self.config.index_cache_minutes
        
        to_date = datetime.utcnow()
        from_date = to_date - timedelta(days=days)
        
        results = {}
        
        for chat in chat_identifiers:
            display_name = chat.display_name
            try:
                chat_id = await self.indexer.get_chat_id(chat)
                if chat_id is None:
                    logger.warning(f"Could not find chat: {display_name}")
                    results[display_name] = 0
                    continue
                
                if not force:
                    status = await self.status_repo.get_status(chat_id)
                    missing_ranges = self.status_repo.get_missing_ranges(
                        status, from_date, to_date
                    )
                    is_fresh = self.status_repo.is_cache_fresh(status, cache_minutes)
                    # #region agent log
                    logger.info(f"[DEBUG-a294c4] Chat {display_name} status: indexed_from={status.indexed_from_date if status else None}, indexed_until={status.indexed_until_date if status else None}, last_indexed={status.last_indexed_at if status else None}")
                    logger.info(f"[DEBUG-a294c4] Chat {display_name} missing_ranges={missing_ranges}, is_fresh={is_fresh}, requested from_date={from_date}, to_date={to_date}")
                    # #endregion
                    
                    if not missing_ranges and is_fresh:
                        logger.info(
                            f"Skipping {display_name}: fully indexed and cache fresh"
                        )
                        results[display_name] = -1
                        continue
                
                chat_username = await self.indexer.get_chat_username(chat)
                count = await self._index_chat(chat, chat_id, chat_username, days, force=force)
                results[display_name] = count
                
            except Exception as e:
                logger.error(f"Error indexing {display_name}: {e}")
                results[display_name] = 0
        
        return results

    async def _index_chat(
        self,
        chat: ChatIdentifier,
        chat_id: int,
        chat_username: str | None,
        days: int,
        force: bool = False,
    ) -> int:
        """
        Index a single chat with smart incremental loading.
        
        Only fetches messages for time ranges that haven't been indexed yet.
        If force=True, fetches the entire period regardless of cached status.
        """
        display_name = chat.display_name
        to_date = datetime.utcnow()
        from_date = to_date - timedelta(days=days)
        
        if force:
            # Force full reindex - use entire requested period
            missing_ranges = [(from_date, to_date)]
            logger.info(f"[DEBUG-a294c4] FORCE reindex {display_name}: full period from {from_date} to {to_date}")
        else:
            status = await self.status_repo.get_status(chat_id)
            missing_ranges = self.status_repo.get_missing_ranges(status, from_date, to_date)
        
        if not missing_ranges:
            logger.info(f"Skipping {display_name}: all data already indexed for requested period")
            return 0
        
        logger.info(
            f"Indexing {display_name}: {len(missing_ranges)} range(s) to fetch "
            f"(requested {days} days)"
        )
        
        all_messages = []
        for range_from, range_to in missing_ranges:
            logger.debug(f"Fetching {display_name} from {range_from} to {range_to}")
            messages = await self.indexer.fetch_messages(
                chat,
                from_date=range_from,
                to_date=range_to,
            )
            all_messages.extend(messages)
        
        if not all_messages:
            logger.info(f"No new messages found in {display_name}")
            await self.status_repo.upsert_status(
                chat_id=chat_id,
                chat_username=chat_username,
                indexed_from_date=from_date,
                indexed_until_date=to_date,
            )
            return 0
        
        texts = [m["text"] for m in all_messages]
        embeddings = await generate_embeddings_batch(texts)
        
        for i, msg in enumerate(all_messages):
            msg["embedding"] = embeddings[i] if i < len(embeddings) else None
        
        count = await self.message_repo.upsert_messages(all_messages)
        
        await self.status_repo.upsert_status(
            chat_id=chat_id,
            chat_username=chat_username,
            indexed_from_date=from_date,
            indexed_until_date=to_date,
        )
        
        logger.info(f"Indexed {count} new messages from {display_name}")
        return count

    async def get_chats_needing_reindex(
        self,
        chats: list[ChatIdentifier] | list[str] | None = None,
        days: int | None = None,
    ) -> list[ChatIdentifier]:
        """
        Get list of chats that need reindexing for the specified period.
        
        A chat needs reindexing if:
        - It has missing ranges for the requested period, OR
        - The cache is stale (not indexed recently)
        """
        if chats is None:
            chat_identifiers = self.config.get_chat_identifiers()
        else:
            chat_identifiers = [
                c if isinstance(c, ChatIdentifier) else ChatIdentifier.from_string(c)
                for c in chats
            ]
        
        if days is None:
            days = self.config.default_days
        
        days = min(days, self.config.max_days)
        cache_minutes = self.config.index_cache_minutes
        
        to_date = datetime.utcnow()
        from_date = to_date - timedelta(days=days)
        
        needs_reindex = []
        
        for chat in chat_identifiers:
            chat_id = await self.indexer.get_chat_id(chat)
            if chat_id is None:
                needs_reindex.append(chat)
                continue
            
            status = await self.status_repo.get_status(chat_id)
            missing_ranges = self.status_repo.get_missing_ranges(
                status, from_date, to_date
            )
            is_fresh = self.status_repo.is_cache_fresh(status, cache_minutes)
            
            if missing_ranges or not is_fresh:
                needs_reindex.append(chat)
        
        return needs_reindex
