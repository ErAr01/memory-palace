import logging
from collections import defaultdict
from dataclasses import dataclass

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import Message

from src.ai.agent import CUSTOM_CHAT_DAYS, SearchAgent
from src.ai.validator import validate_message
from src.config import ChatIdentifier
from src.database.connection import get_session_maker

logger = logging.getLogger(__name__)

router = Router()

conversation_contexts: dict[int, list[dict]] = defaultdict(list)


@dataclass
class PendingIndexing:
    """State for pending custom chat indexing."""
    original_query: str
    chats_to_index: list[ChatIdentifier]


pending_indexing_requests: dict[int, PendingIndexing] = {}

MAX_CONTEXT_MESSAGES = 6


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    """Handle /start command."""
    await message.answer(
        "Привет! Я помогу найти объявления о продаже в чатах Тбилиси.\n\n"
        "Просто напишите, что вы ищете, например:\n"
        "• <i>Найди мне чемодан</i>\n"
        "• <i>Ищу велосипед за последние 2 недели</i>\n"
        "• <i>Нужна детская коляска</i>\n\n"
        "Я найду подходящие объявления о продаже!"
    )


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    """Handle /help command."""
    await message.answer(
        "<b>Как пользоваться ботом:</b>\n\n"
        "1. Просто напишите, что вы ищете\n"
        "2. Я найду объявления о продаже в чатах Тбилиси\n\n"
        "<b>Примеры запросов:</b>\n"
        "• <i>Найди мне чемодан</i>\n"
        "• <i>Ищу велосипед за последние 2 недели</i>\n"
        "• <i>iPhone в @tbilisi_baraholka</i>\n\n"
        "<b>Дополнительные параметры:</b>\n"
        "• Укажите период: <i>за 2 недели</i>, <i>за месяц</i>\n"
        "• Укажите чат: <i>в @название_чата</i>\n\n"
        "/clear - очистить историю диалога"
    )


@router.message(Command("clear"))
async def cmd_clear(message: Message) -> None:
    """Clear conversation context."""
    user_id = message.from_user.id
    conversation_contexts[user_id].clear()
    await message.answer("История диалога очищена.")


@router.message(F.text)
async def handle_search(message: Message) -> None:
    """Handle search requests."""
    user_id = message.from_user.id
    user_message = message.text.strip()
    
    if not user_message:
        return
    
    user_message_lower = user_message.lower()
    if user_id in pending_indexing_requests:
        pending = pending_indexing_requests[user_id]
        
        if user_message_lower in ("да", "yes", "ок", "ok", "давай"):
            del pending_indexing_requests[user_id]
            await _handle_indexing_confirmation(message, pending, confirmed=True)
            return
        elif user_message_lower in ("нет", "no", "отмена", "cancel"):
            del pending_indexing_requests[user_id]
            await _handle_indexing_confirmation(message, pending, confirmed=False)
            return
    
    validation = await validate_message(user_message)
    if not validation.is_valid:
        logger.warning(
            f"Message rejected: user={user_id}, risk={validation.risk_score}, "
            f"reason={validation.reason}"
        )
        await message.answer(
            "Извините, я могу помочь только с поиском товаров в чатах Тбилиси.\n\n"
            "Напишите, что вы хотите найти, например:\n"
            "• <i>Найди чемодан</i>\n"
            "• <i>Ищу велосипед</i>"
        )
        return
    
    processing_msg = await message.answer("🔍 Ищу объявления...")
    
    try:
        session_maker = get_session_maker()
        async with session_maker() as session:
            agent = SearchAgent(session)
            
            context = conversation_contexts[user_id][-MAX_CONTEXT_MESSAGES:]
            
            result = await agent.search(
                user_message=user_message,
                conversation_context=context if context else None,
            )
            
            conversation_contexts[user_id].append({
                "role": "user",
                "content": user_message,
            })
            
            if result.need_indexing and result.chats_to_index:
                pending_indexing_requests[user_id] = PendingIndexing(
                    original_query=user_message,
                    chats_to_index=result.chats_to_index,
                )
                chat_names = ", ".join(f"@{c.display_name}" for c in result.chats_to_index)
                warning_msg = (
                    f"⚠️ Чат(ы) {chat_names} ещё не проиндексированы.\n\n"
                    f"Индексация может занять несколько минут (загружаются сообщения за 2 недели).\n\n"
                    f"Хотите проиндексировать?\n"
                    f"Ответьте <b>Да</b> или <b>Нет</b>"
                )
                conversation_contexts[user_id].append({
                    "role": "assistant",
                    "content": warning_msg,
                })
                await processing_msg.edit_text(warning_msg)
            elif result.need_clarification:
                conversation_contexts[user_id].append({
                    "role": "assistant",
                    "content": result.clarification_question,
                })
                await processing_msg.edit_text(result.clarification_question)
            else:
                conversation_contexts[user_id].append({
                    "role": "assistant",
                    "content": result.formatted_response,
                })
                
                if len(result.formatted_response) > 4000:
                    chunks = split_message(result.formatted_response)
                    await processing_msg.edit_text(chunks[0])
                    for chunk in chunks[1:]:
                        await message.answer(chunk)
                else:
                    await processing_msg.edit_text(result.formatted_response)
            
            if len(conversation_contexts[user_id]) > MAX_CONTEXT_MESSAGES * 2:
                conversation_contexts[user_id] = conversation_contexts[user_id][-MAX_CONTEXT_MESSAGES:]
                
    except Exception as e:
        logger.exception(f"Error processing search: {e}")
        await processing_msg.edit_text(
            "Произошла ошибка при обработке запроса. Попробуйте позже."
        )


async def _handle_indexing_confirmation(
    message: Message,
    pending: PendingIndexing,
    confirmed: bool,
) -> None:
    """Handle user's response to indexing confirmation."""
    user_id = message.from_user.id
    
    if not confirmed:
        await message.answer(
            "Хорошо, поиск будет выполнен только в стандартных чатах.\n"
            "Повторите ваш запрос."
        )
        return
    
    chat_names = ", ".join(f"@{c.display_name}" for c in pending.chats_to_index)
    processing_msg = await message.answer(
        f"⏳ Индексирую {chat_names}...\n"
        f"Это может занять несколько минут."
    )
    
    try:
        session_maker = get_session_maker()
        async with session_maker() as session:
            agent = SearchAgent(session)
            
            indexed_results = await agent.index_custom_chats(
                chats=pending.chats_to_index,
                days=CUSTOM_CHAT_DAYS,
            )
            
            indexed_count = sum(c for c in indexed_results.values() if c > 0)
            await processing_msg.edit_text(
                f"✅ Индексация завершена! Проиндексировано {indexed_count} сообщений.\n\n"
                f"🔍 Ищу объявления..."
            )
            
            context = conversation_contexts[user_id][-MAX_CONTEXT_MESSAGES:]
            result = await agent.search(
                user_message=pending.original_query,
                conversation_context=context if context else None,
                force_days=CUSTOM_CHAT_DAYS,  # Для custom чатов период фиксирован, не задаётся пользователем
            )
            
            conversation_contexts[user_id].append({
                "role": "user",
                "content": pending.original_query,
            })
            conversation_contexts[user_id].append({
                "role": "assistant",
                "content": result.formatted_response,
            })
            
            if len(result.formatted_response) > 4000:
                chunks = split_message(result.formatted_response)
                await processing_msg.edit_text(chunks[0])
                for chunk in chunks[1:]:
                    await message.answer(chunk)
            else:
                await processing_msg.edit_text(result.formatted_response)
                
    except Exception as e:
        logger.exception(f"Error during custom chat indexing: {e}")
        await processing_msg.edit_text(
            "Произошла ошибка при индексации. Попробуйте позже."
        )


def split_message(text: str, max_length: int = 4000) -> list[str]:
    """Split long message into chunks."""
    if len(text) <= max_length:
        return [text]
    
    chunks = []
    current_chunk = ""
    
    for line in text.split("\n"):
        if len(current_chunk) + len(line) + 1 > max_length:
            if current_chunk:
                chunks.append(current_chunk.strip())
            current_chunk = line
        else:
            current_chunk += "\n" + line if current_chunk else line
    
    if current_chunk:
        chunks.append(current_chunk.strip())
    
    return chunks
