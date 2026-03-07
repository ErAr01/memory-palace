import logging
from datetime import datetime, timedelta

from telethon import TelegramClient
from telethon.tl.types import Channel, Chat, User

from src.config import ChatIdentifier, get_chats_config, get_settings

logger = logging.getLogger(__name__)


class TelegramIndexer:
    def __init__(self):
        settings = get_settings()
        self.client = TelegramClient(
            "userbot",
            settings.api_id,
            settings.api_hash,
        )
        self.phone_number = settings.phone_number
        self._connected = False
        self._entity_cache: dict[str | int, tuple] = {}

    async def connect(self) -> None:
        """Connect to Telegram."""
        if not self._connected:
            await self.client.start(phone=self.phone_number)
            self._connected = True
            logger.info("Telegram indexer connected")

    async def disconnect(self) -> None:
        """Disconnect from Telegram."""
        if self._connected:
            await self.client.disconnect()
            self._connected = False
            logger.info("Telegram indexer disconnected")

    async def get_chat_entity(self, chat: ChatIdentifier | str | int):
        """
        Get chat entity by ChatIdentifier, username, or ID.
        
        Args:
            chat: ChatIdentifier object, username string, or chat ID integer
        """
        await self.connect()
        
        if isinstance(chat, ChatIdentifier):
            identifier = chat.identifier
        else:
            identifier = chat
        
        if identifier in self._entity_cache:
            return self._entity_cache[identifier]
        
        try:
            entity = await self.client.get_entity(identifier)
            self._entity_cache[identifier] = entity
            if hasattr(entity, 'id'):
                self._entity_cache[entity.id] = entity
            if hasattr(entity, 'username') and entity.username:
                self._entity_cache[entity.username] = entity
            return entity
        except Exception as e:
            logger.error(f"Failed to get chat entity for {identifier}: {e}")
            return None

    async def get_chat_id(self, chat: ChatIdentifier | str | int) -> int | None:
        """
        Get chat ID from ChatIdentifier, username, or return ID if already provided.
        
        Args:
            chat: ChatIdentifier object, username string, or chat ID integer
        """
        if isinstance(chat, ChatIdentifier) and chat.chat_id is not None:
            return chat.chat_id
        
        if isinstance(chat, int):
            return chat
        
        entity = await self.get_chat_entity(chat)
        if entity:
            return entity.id
        return None

    async def get_chat_username(self, chat: ChatIdentifier | str | int) -> str | None:
        """Get chat username from ChatIdentifier or entity."""
        if isinstance(chat, ChatIdentifier) and chat.username:
            return chat.username
        
        if isinstance(chat, str) and not chat.lstrip("-").isdigit():
            return chat.lstrip("@")
        
        entity = await self.get_chat_entity(chat)
        if entity and hasattr(entity, 'username'):
            return entity.username
        return None

    async def fetch_messages(
        self,
        chat: ChatIdentifier | str | int,
        from_date: datetime | None = None,
        to_date: datetime | None = None,
        limit: int = 1000,
    ) -> list[dict]:
        """
        Fetch messages from a chat within date range.
        
        Args:
            chat: ChatIdentifier object, username string, or chat ID integer
            from_date: Start date for message retrieval
            to_date: End date for message retrieval
            limit: Maximum number of messages to fetch
            
        Returns:
            List of message dicts ready for database insertion.
        """
        await self.connect()

        entity = await self.get_chat_entity(chat)
        if not entity:
            display = chat.display_name if isinstance(chat, ChatIdentifier) else str(chat)
            logger.warning(f"Could not find chat: {display}")
            return []

        chat_id = entity.id
        chat_username = getattr(entity, 'username', None)
        
        if isinstance(chat, ChatIdentifier):
            chat_username = chat_username or chat.username
        
        messages = []
        # #region agent log
        total_iterated = 0
        skipped_no_text = 0
        chapman_found = False
        # #endregion

        try:
            async for message in self.client.iter_messages(
                entity,
                limit=limit,
                offset_date=to_date,
                reverse=False,
            ):
                # #region agent log
                total_iterated += 1
                if message.text and 'chapman' in message.text.lower():
                    chapman_found = True
                    logger.info(f"[DEBUG-a294c4] FOUND CHAPMAN! msg_id={message.id}, date={message.date}, text={message.text[:200]}")
                # #endregion
                
                if message.text is None or len(message.text.strip()) == 0:
                    # #region agent log
                    skipped_no_text += 1
                    # #endregion
                    continue

                if from_date and message.date.replace(tzinfo=None) < from_date:
                    break

                if to_date and message.date.replace(tzinfo=None) > to_date:
                    continue

                messages.append({
                    "chat_id": chat_id,
                    "chat_username": chat_username,
                    "message_id": message.id,
                    "text": message.text,
                    "date": message.date.replace(tzinfo=None),
                    "sender_id": message.sender_id,
                })

            display = chat.display_name if isinstance(chat, ChatIdentifier) else str(chat)
            # #region agent log
            logger.info(f"[DEBUG-a294c4] fetch_messages stats: total_iterated={total_iterated}, skipped_no_text={skipped_no_text}, chapman_found={chapman_found}")
            # #endregion
            logger.info(
                f"Fetched {len(messages)} messages from {display} "
                f"(from {from_date} to {to_date})"
            )
        except Exception as e:
            display = chat.display_name if isinstance(chat, ChatIdentifier) else str(chat)
            logger.error(f"Error fetching messages from {display}: {e}")

        return messages

    async def fetch_messages_for_period(
        self,
        chat: ChatIdentifier | str | int,
        days: int = 7,
    ) -> list[dict]:
        """Fetch messages for the last N days."""
        to_date = datetime.utcnow()
        from_date = to_date - timedelta(days=days)
        return await self.fetch_messages(
            chat,
            from_date=from_date,
            to_date=to_date,
        )


_indexer: TelegramIndexer | None = None


def get_indexer() -> TelegramIndexer:
    """Get singleton indexer instance."""
    global _indexer
    if _indexer is None:
        _indexer = TelegramIndexer()
    return _indexer
