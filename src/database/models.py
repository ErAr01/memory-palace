from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import BigInteger, DateTime, Index, String, Text, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    chat_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    chat_username: Mapped[str | None] = mapped_column(String(255))
    message_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    text: Mapped[str | None] = mapped_column(Text)
    date: Mapped[datetime | None] = mapped_column(DateTime)
    sender_id: Mapped[int | None] = mapped_column(BigInteger)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(1536))
    indexed_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )

    __table_args__ = (
        Index("ix_messages_chat_id_message_id", "chat_id", "message_id", unique=True),
        Index("ix_messages_chat_id_date", "chat_id", "date"),
    )


class ChatIndexStatus(Base):
    __tablename__ = "chat_index_status"

    chat_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    chat_username: Mapped[str | None] = mapped_column(String(255))
    last_indexed_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    indexed_from_date: Mapped[datetime | None] = mapped_column(DateTime)
    indexed_until_date: Mapped[datetime | None] = mapped_column(DateTime)
