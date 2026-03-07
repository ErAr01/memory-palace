import pytest
from pathlib import Path

from src.config import ChatIdentifier, ChatsConfig


class TestChatIdentifier:
    def test_from_string_username(self):
        chat = ChatIdentifier.from_string("test_chat")
        assert chat.username == "test_chat"
        assert chat.chat_id is None
    
    def test_from_string_username_with_at(self):
        chat = ChatIdentifier.from_string("@test_chat")
        assert chat.username == "test_chat"
        assert chat.chat_id is None
    
    def test_from_string_positive_id(self):
        chat = ChatIdentifier.from_string("1234567890")
        assert chat.chat_id == 1234567890
        assert chat.username is None
    
    def test_from_string_negative_id(self):
        chat = ChatIdentifier.from_string("-1001234567890")
        assert chat.chat_id == -1001234567890
        assert chat.username is None
    
    def test_identifier_prefers_id(self):
        chat = ChatIdentifier(username="test", chat_id=-1001234567890)
        assert chat.identifier == -1001234567890
    
    def test_identifier_uses_username_when_no_id(self):
        chat = ChatIdentifier(username="test")
        assert chat.identifier == "test"
    
    def test_display_name_with_name(self):
        chat = ChatIdentifier(username="test", name="Test Chat")
        assert chat.display_name == "Test Chat"
    
    def test_display_name_with_username(self):
        chat = ChatIdentifier(username="test")
        assert chat.display_name == "@test"
    
    def test_display_name_with_id_only(self):
        chat = ChatIdentifier(chat_id=-1001234567890)
        assert chat.display_name == "-1001234567890"
    
    def test_from_config(self):
        config_dict = {
            "username": "test_chat",
            "id": -1001234567890,
            "name": "Test Chat"
        }
        chat = ChatIdentifier.from_config(config_dict)
        assert chat.username == "test_chat"
        assert chat.chat_id == -1001234567890
        assert chat.name == "Test Chat"


class TestChatsConfig:
    @pytest.fixture
    def config_path(self, tmp_path):
        config_file = tmp_path / "chats.yaml"
        config_file.write_text("""
default_chats:
  - username: test_chat1
    name: "Test Chat 1"
  - username: test_chat2
    id: -1001234567890
    name: "Test Chat 2"

settings:
  default_days: 7
  max_days: 30
  index_cache_minutes: 60
""")
        return config_file
    
    def test_loads_default_chats(self, config_path):
        config = ChatsConfig(config_path)
        assert len(config.default_chats) == 2
        assert config.default_chats[0]["username"] == "test_chat1"
    
    def test_get_chat_usernames(self, config_path):
        config = ChatsConfig(config_path)
        usernames = config.get_chat_usernames()
        assert usernames == ["test_chat1", "test_chat2"]
    
    def test_get_chat_identifiers(self, config_path):
        config = ChatsConfig(config_path)
        identifiers = config.get_chat_identifiers()
        assert len(identifiers) == 2
        assert identifiers[0].username == "test_chat1"
        assert identifiers[0].chat_id is None
        assert identifiers[1].username == "test_chat2"
        assert identifiers[1].chat_id == -1001234567890
    
    def test_default_days(self, config_path):
        config = ChatsConfig(config_path)
        assert config.default_days == 7
    
    def test_max_days(self, config_path):
        config = ChatsConfig(config_path)
        assert config.max_days == 30
    
    def test_index_cache_minutes(self, config_path):
        config = ChatsConfig(config_path)
        assert config.index_cache_minutes == 60
