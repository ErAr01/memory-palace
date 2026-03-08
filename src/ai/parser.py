import json
import logging
import re
from dataclasses import dataclass

from openai import AsyncOpenAI

from src.ai.embeddings import get_openai_client
from src.config import ChatIdentifier, get_chats_config, get_settings

logger = logging.getLogger(__name__)


@dataclass
class ParsedQuery:
    status: str  # "ready" or "need_clarification"
    search_query: str | None
    days: int
    chats: list[ChatIdentifier] | None
    clarification_question: str | None


PARSER_SYSTEM_PROMPT = """Ты - парсер запросов для бота поиска объявлений о продаже в Telegram чатах города Тбилиси.

Твоя задача - проанализировать запрос пользователя и извлечь:
1. Что именно ищет пользователь (конкретный товар)
2. За какой период искать (в днях)
3. В каких чатах искать (если указаны)

ВАЖНО: Если запрос слишком неопределённый и может означать разные вещи, нужно задать уточняющий вопрос.

Примеры неопределённых запросов:
- "лампа" → может быть лампочка, торшер, настольная лампа, люстра
- "стол" → письменный, обеденный, журнальный, компьютерный
- "кресло" → офисное, мягкое, компьютерное, кресло-качалка
- "шкаф" → платяной, книжный, кухонный

Примеры конкретных запросов (уточнение НЕ нужно):
- "чемодан" → достаточно конкретно
- "велосипед" → достаточно конкретно
- "iPhone 15" → достаточно конкретно
- "детская коляска" → достаточно конкретно
- "настольная лампа" → достаточно конкретно

Чаты могут быть указаны:
- По username: @baraholka_tbi, baraholka_tbi
- По ID чата: -1001234567890

Отвечай ТОЛЬКО в формате JSON:
{
  "status": "ready" или "need_clarification",
  "search_query": "конкретный товар для поиска" или null,
  "days": число дней (по умолчанию 7, максимум 30),
  "chats": ["@chat1", "-1001234567890"] или null если использовать дефолтные,
  "clarification_question": "текст вопроса" или null
}"""


async def parse_user_query(
    user_message: str,
    conversation_context: list[dict] | None = None,
) -> ParsedQuery:
    """
    Parse user message and extract search parameters.
    
    Args:
        user_message: The message from user.
        conversation_context: Previous messages in conversation for context.
    
    Returns:
        ParsedQuery with extracted parameters or clarification question.
    """
    settings = get_settings()
    config = get_chats_config()
    client = get_openai_client()
    
    messages = [{"role": "system", "content": PARSER_SYSTEM_PROMPT}]
    
    if conversation_context:
        messages.extend(conversation_context)
    
    messages.append({"role": "user", "content": user_message})
    
    try:
        response = await client.chat.completions.create(
            model=settings.openai_model,
            messages=messages,
            temperature=0.1,
            response_format={"type": "json_object"},
        )
        
        result_text = response.choices[0].message.content
        result = json.loads(result_text)
        
        days = result.get("days", config.default_days)
        days = min(max(1, days), config.max_days)
        
        chats_raw = result.get("chats")
        chats = None
        if chats_raw:
            chats = [parse_chat_identifier(c) for c in chats_raw]
        
        return ParsedQuery(
            status=result.get("status", "ready"),
            search_query=result.get("search_query"),
            days=days,
            chats=chats,
            clarification_question=result.get("clarification_question"),
        )
        
    except Exception as e:
        logger.error(f"Error parsing user query: {e}")
        return ParsedQuery(
            status="ready",
            search_query=extract_simple_query(user_message),
            days=config.default_days,
            chats=None,
            clarification_question=None,
        )


def parse_chat_identifier(value: str) -> ChatIdentifier:
    """Parse chat identifier from string - can be username or ID."""
    value = value.strip().lstrip("@")
    
    if value.lstrip("-").isdigit():
        return ChatIdentifier(chat_id=int(value))
    
    return ChatIdentifier(username=value)


def extract_simple_query(message: str) -> str:
    """Simple fallback extraction of search query from message."""
    prefixes = [
        "найди", "найти", "ищу", "нужен", "нужна", "нужно",
        "хочу", "продаётся", "продается", "есть ли",
    ]
    
    text = message.lower().strip()
    
    for prefix in prefixes:
        if text.startswith(prefix):
            text = text[len(prefix):].strip()
            break
    
    text = re.sub(r"[?!.,]", "", text)
    
    return text.strip() or message
