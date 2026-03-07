"""Debug script for force reindexing a specific chat."""
import asyncio
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")

async def main():
    from src.database.connection import get_session_maker
    from src.indexer.service import IndexingService
    from src.config import ChatIdentifier
    
    session_maker = get_session_maker()
    async with session_maker() as session:
        service = IndexingService(session)
        
        chat = ChatIdentifier(username="baraholka_tbi", name="Барахолка Тбилиси")
        
        print("Starting FORCE reindex for baraholka_tbi (14 days)...")
        result = await service.index_chats(
            chats=[chat],
            days=14,
            force=True,
        )
        print(f"Reindex result: {result}")

if __name__ == "__main__":
    asyncio.run(main())
