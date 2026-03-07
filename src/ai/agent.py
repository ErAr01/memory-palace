import json
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from src.ai.embeddings import generate_embedding, get_openai_client
from src.ai.parser import ParsedQuery, parse_user_query
from src.config import ChatIdentifier, get_chats_config, get_settings
from src.database.models import Message
from src.database.repository import MessageRepository
from src.indexer.service import IndexingService

logger = logging.getLogger(__name__)


@dataclass
class SearchResult:
    success: bool
    messages: list[Message]
    formatted_response: str
    need_clarification: bool
    clarification_question: str | None


FILTER_SYSTEM_PROMPT = """Ты - агент фильтрации объявлений о продаже.

Твоя задача - из списка сообщений отобрать только те, которые являются реальными объявлениями о продаже искомого товара.

Критерии отбора:
1. Сообщение должно быть объявлением о ПРОДАЖЕ (не покупке, не поиске)
2. Товар должен соответствовать поисковому запросу
3. Предпочтение сообщениям с указанной ценой
4. Игнорировать спам, рекламу услуг, не относящиеся сообщения

Поисковый запрос: {search_query}

Сообщения для анализа:
{messages}

Отвечай в формате JSON:
{{
  "relevant_ids": [список ID релевантных сообщений],
  "summary": "краткое описание найденных объявлений"
}}"""


FORMAT_RESPONSE_PROMPT = """Сформатируй найденные объявления о продаже для пользователя.

Поисковый запрос: {search_query}

Объявления:
{messages}

Сформируй ответ в виде нумерованного списка объявлений. Для каждого объявления ОБЯЗАТЕЛЬНО укажи:
- Краткое описание товара
- Цену (если указана)
- Дату публикации
- Ссылку на сообщение (используй предоставленную ссылку!)

Формат ссылки: [Перейти к объявлению](ссылка)

Если объявлений нет - сообщи об этом.
Отвечай на русском языке."""


def generate_message_link(chat_id: int, chat_username: str | None, message_id: int) -> str:
    """
    Generate Telegram link to a specific message.
    
    For public chats: https://t.me/{username}/{message_id}
    For private chats: https://t.me/c/{chat_id}/{message_id}
    """
    if chat_username:
        return f"https://t.me/{chat_username}/{message_id}"
    
    normalized_id = chat_id
    if chat_id < 0:
        chat_id_str = str(abs(chat_id))
        if chat_id_str.startswith("100"):
            normalized_id = int(chat_id_str[3:])
        else:
            normalized_id = abs(chat_id)
    
    return f"https://t.me/c/{normalized_id}/{message_id}"


class SearchAgent:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.message_repo = MessageRepository(session)
        self.indexing_service = IndexingService(session)
        self.config = get_chats_config()
        self.settings = get_settings()

    async def search(
        self,
        user_message: str,
        conversation_context: list[dict] | None = None,
    ) -> SearchResult:
        """
        Process user search request.
        
        Args:
            user_message: User's search message.
            conversation_context: Previous messages for context.
        
        Returns:
            SearchResult with found messages or clarification request.
        """
        parsed = await parse_user_query(user_message, conversation_context)
        
        if parsed.status == "need_clarification":
            return SearchResult(
                success=False,
                messages=[],
                formatted_response="",
                need_clarification=True,
                clarification_question=parsed.clarification_question,
            )
        
        chats = parsed.chats or self.config.get_chat_identifiers()
        # #region agent log
        logger.info(f"[DEBUG-a294c4] Search params: search_query={parsed.search_query}, days={parsed.days}, chats={[c.display_name for c in chats]}")
        # #endregion
        
        await self.indexing_service.index_chats(
            chats=chats,
            days=parsed.days,
            force=False,
        )
        
        messages = await self._search_messages(
            search_query=parsed.search_query,
            chats=chats,
            days=parsed.days,
        )
        # #region agent log
        logger.info(f"[DEBUG-a294c4] _search_messages returned {len(messages)} messages")
        for m in messages[:10]:
            logger.info(f"[DEBUG-a294c4] Message id={m.id}, chat={m.chat_username}, date={m.date}, text={m.text[:100] if m.text else 'None'}...")
        # #endregion
        
        if not messages:
            return SearchResult(
                success=True,
                messages=[],
                formatted_response=f"К сожалению, объявлений о продаже «{parsed.search_query}» не найдено за последние {parsed.days} дней.",
                need_clarification=False,
                clarification_question=None,
            )
        
        filtered_messages = await self._filter_relevant_messages(
            search_query=parsed.search_query,
            messages=messages,
        )
        
        if not filtered_messages:
            return SearchResult(
                success=True,
                messages=[],
                formatted_response=f"К сожалению, релевантных объявлений о продаже «{parsed.search_query}» не найдено.",
                need_clarification=False,
                clarification_question=None,
            )
        
        formatted = await self._format_response(
            search_query=parsed.search_query,
            messages=filtered_messages,
        )
        
        return SearchResult(
            success=True,
            messages=filtered_messages,
            formatted_response=formatted,
            need_clarification=False,
            clarification_question=None,
        )

    async def _search_messages(
        self,
        search_query: str,
        chats: list[ChatIdentifier],
        days: int,
    ) -> list[Message]:
        """Search for similar messages using embeddings."""
        query_embedding = await generate_embedding(search_query)
        
        if not query_embedding:
            logger.error("Failed to generate query embedding")
            return []
        
        from_date = datetime.utcnow() - timedelta(days=days)
        
        from src.indexer.client import get_indexer
        indexer = get_indexer()
        
        chat_ids = []
        for chat in chats:
            chat_id = await indexer.get_chat_id(chat)
            if chat_id:
                chat_ids.append(chat_id)
        
        # #region agent log
        logger.info(f"[DEBUG-a294c4] _search_messages: chat_ids={chat_ids}, from_date={from_date}")
        # #endregion
        messages = await self.message_repo.search_similar(
            embedding=query_embedding,
            chat_ids=chat_ids if chat_ids else None,
            from_date=from_date,
            limit=50,
        )
        
        return messages

    async def _filter_relevant_messages(
        self,
        search_query: str,
        messages: list[Message],
    ) -> list[Message]:
        """Use LLM to filter only relevant sale announcements."""
        if not messages:
            return []
        
        client = get_openai_client()
        
        messages_text = "\n\n".join([
            f"ID: {m.id}\nТекст: {m.text[:500]}..."
            if len(m.text or "") > 500 else f"ID: {m.id}\nТекст: {m.text}"
            for m in messages
        ])
        
        prompt = FILTER_SYSTEM_PROMPT.format(
            search_query=search_query,
            messages=messages_text,
        )
        
        try:
            response = await client.chat.completions.create(
                model=self.settings.openai_model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                response_format={"type": "json_object"},
            )
            
            result = json.loads(response.choices[0].message.content)
            relevant_ids = set(result.get("relevant_ids", []))
            # #region agent log
            logger.info(f"[DEBUG-a294c4] _filter_relevant_messages: input_ids={[m.id for m in messages]}, relevant_ids={relevant_ids}, summary={result.get('summary')}")
            # #endregion
            
            return [m for m in messages if m.id in relevant_ids]
            
        except Exception as e:
            logger.error(f"Error filtering messages: {e}")
            return messages[:10]

    async def _format_response(
        self,
        search_query: str,
        messages: list[Message],
    ) -> str:
        """Format search results for user."""
        if not messages:
            return f"Объявлений о продаже «{search_query}» не найдено."
        
        client = get_openai_client()
        
        messages_text = "\n\n".join([
            f"Чат: @{m.chat_username or m.chat_id}\n"
            f"Дата: {m.date.strftime('%d.%m.%Y %H:%M') if m.date else 'N/A'}\n"
            f"Ссылка: {generate_message_link(m.chat_id, m.chat_username, m.message_id)}\n"
            f"Текст: {m.text}"
            for m in messages
        ])
        
        prompt = FORMAT_RESPONSE_PROMPT.format(
            search_query=search_query,
            messages=messages_text,
        )
        
        try:
            response = await client.chat.completions.create(
                model=self.settings.openai_model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            logger.error(f"Error formatting response: {e}")
            result_lines = [f"Найдено {len(messages)} объявлений:\n"]
            for m in messages[:10]:
                link = generate_message_link(m.chat_id, m.chat_username, m.message_id)
                result_lines.append(
                    f"• {m.text[:150]}...\n"
                    f"  📅 {m.date.strftime('%d.%m.%Y') if m.date else 'N/A'} | "
                    f"[Открыть]({link})"
                )
            return "\n\n".join(result_lines)
