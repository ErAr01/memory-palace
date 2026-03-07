import pytest

from src.ai.parser import extract_simple_query


class TestExtractSimpleQuery:
    def test_removes_prefix_naidi(self):
        assert extract_simple_query("найди чемодан") == "чемодан"
    
    def test_removes_prefix_ischu(self):
        assert extract_simple_query("ищу велосипед") == "велосипед"
    
    def test_removes_prefix_nuzhen(self):
        assert extract_simple_query("нужен ноутбук") == "ноутбук"
    
    def test_removes_punctuation(self):
        assert extract_simple_query("найди чемодан!") == "чемодан"
        assert extract_simple_query("ищу велосипед?") == "велосипед"
    
    def test_preserves_complex_query(self):
        result = extract_simple_query("найди настольную лампу")
        assert "настольную лампу" in result
    
    def test_handles_empty_string(self):
        result = extract_simple_query("")
        assert result == ""
    
    def test_handles_only_prefix(self):
        result = extract_simple_query("найди")
        assert result == "найди"
