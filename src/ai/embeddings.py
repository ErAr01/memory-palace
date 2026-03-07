import logging
from typing import Sequence

from openai import AsyncOpenAI

from src.config import get_settings

logger = logging.getLogger(__name__)

_client: AsyncOpenAI | None = None


def get_openai_client() -> AsyncOpenAI:
    """Get OpenAI client singleton."""
    global _client
    if _client is None:
        settings = get_settings()
        _client = AsyncOpenAI(api_key=settings.openai_api_key)
    return _client


async def generate_embedding(text: str) -> list[float]:
    """Generate embedding for a single text."""
    settings = get_settings()
    client = get_openai_client()

    try:
        response = await client.embeddings.create(
            model=settings.embedding_model,
            input=text,
        )
        return response.data[0].embedding
    except Exception as e:
        logger.error(f"Error generating embedding: {e}")
        return []


async def generate_embeddings_batch(
    texts: Sequence[str],
    batch_size: int = 100,
) -> list[list[float]]:
    """
    Generate embeddings for multiple texts in batches.
    
    Args:
        texts: List of texts to generate embeddings for.
        batch_size: Number of texts to process in each batch.
    
    Returns:
        List of embeddings (same order as input texts).
    """
    settings = get_settings()
    client = get_openai_client()
    
    all_embeddings = []
    
    for i in range(0, len(texts), batch_size):
        batch = texts[i:i + batch_size]
        
        try:
            response = await client.embeddings.create(
                model=settings.embedding_model,
                input=list(batch),
            )
            batch_embeddings = [item.embedding for item in response.data]
            all_embeddings.extend(batch_embeddings)
            
            logger.debug(f"Generated embeddings for batch {i//batch_size + 1}")
        except Exception as e:
            logger.error(f"Error generating embeddings for batch: {e}")
            all_embeddings.extend([[] for _ in batch])
    
    return all_embeddings
