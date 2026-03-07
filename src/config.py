from dataclasses import dataclass
from pathlib import Path
from functools import lru_cache
import re

import yaml
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    bot_token: str = Field(..., description="Telegram Bot token")
    
    api_id: int = Field(..., description="Telegram API ID for userbot")
    api_hash: str = Field(..., description="Telegram API Hash for userbot")
    phone_number: str = Field(..., description="Phone number for userbot")
    
    database_url: str = Field(
        default="postgresql+asyncpg://postgres:postgres@localhost:5432/memory_palace"
    )
    
    openai_api_key: str = Field(..., description="OpenAI API key")
    openai_model: str = Field(default="gpt-4.1-mini")
    embedding_model: str = Field(default="text-embedding-3-small")


@dataclass
class ChatIdentifier:
    """Universal chat identifier - can be username or ID."""
    username: str | None = None
    chat_id: int | None = None
    name: str | None = None
    
    @property
    def identifier(self) -> str | int:
        """Returns the best identifier to use with Telethon."""
        if self.chat_id is not None:
            return self.chat_id
        return self.username
    
    @property
    def display_name(self) -> str:
        """Returns human-readable name for display."""
        if self.name:
            return self.name
        if self.username:
            return f"@{self.username}"
        return str(self.chat_id)
    
    def __hash__(self):
        return hash((self.username, self.chat_id))
    
    def __eq__(self, other):
        if not isinstance(other, ChatIdentifier):
            return False
        if self.chat_id and other.chat_id:
            return self.chat_id == other.chat_id
        return self.username == other.username
    
    @classmethod
    def from_string(cls, value: str) -> "ChatIdentifier":
        """Parse chat identifier from string (username or ID)."""
        value = value.strip()
        
        value = value.lstrip("@")
        
        if value.lstrip("-").isdigit():
            return cls(chat_id=int(value))
        
        return cls(username=value)
    
    @classmethod
    def from_config(cls, config_dict: dict) -> "ChatIdentifier":
        """Create ChatIdentifier from config dictionary."""
        return cls(
            username=config_dict.get("username"),
            chat_id=config_dict.get("id"),
            name=config_dict.get("name"),
        )


class ChatsConfig:
    def __init__(self, config_path: Path | None = None):
        if config_path is None:
            config_path = Path(__file__).parent.parent / "config" / "chats.yaml"
        
        with open(config_path, "r", encoding="utf-8") as f:
            self._config = yaml.safe_load(f)
    
    @property
    def default_chats(self) -> list[dict]:
        return self._config.get("default_chats", [])
    
    @property
    def default_days(self) -> int:
        return self._config.get("settings", {}).get("default_days", 7)
    
    @property
    def max_days(self) -> int:
        return self._config.get("settings", {}).get("max_days", 30)
    
    @property
    def index_cache_minutes(self) -> int:
        return self._config.get("settings", {}).get("index_cache_minutes", 60)
    
    def get_chat_usernames(self) -> list[str]:
        """Legacy method - returns usernames only."""
        return [chat["username"] for chat in self.default_chats if chat.get("username")]
    
    def get_chat_identifiers(self) -> list[ChatIdentifier]:
        """Returns list of ChatIdentifier objects."""
        return [ChatIdentifier.from_config(chat) for chat in self.default_chats]


@lru_cache
def get_settings() -> Settings:
    return Settings()


@lru_cache
def get_chats_config() -> ChatsConfig:
    return ChatsConfig()
