import pytest

from src.ai.validator import ValidationResult, validate_message


class TestValidationResult:
    def test_valid_result(self):
        result = ValidationResult(is_valid=True, reason=None, risk_score=0.0)
        assert result.is_valid is True
        assert result.reason is None
        assert result.risk_score == 0.0

    def test_invalid_result(self):
        result = ValidationResult(
            is_valid=False,
            reason="Prompt injection detected",
            risk_score=0.9,
        )
        assert result.is_valid is False
        assert result.reason == "Prompt injection detected"
        assert result.risk_score == 0.9


class TestValidateMessage:
    @pytest.mark.asyncio
    async def test_empty_message(self):
        result = await validate_message("")
        assert result.is_valid is False
        assert result.reason == "Пустое сообщение"
        assert result.risk_score == 0.0

    @pytest.mark.asyncio
    async def test_whitespace_only(self):
        result = await validate_message("   ")
        assert result.is_valid is False
        assert result.reason == "Пустое сообщение"

    @pytest.mark.asyncio
    async def test_too_long_message(self):
        long_message = "a" * 2001
        result = await validate_message(long_message)
        assert result.is_valid is False
        assert result.reason == "Сообщение слишком длинное"
        assert result.risk_score == 0.5


class TestValidatorPromptInjectionPatterns:
    """
    Tests for pattern-based validation checks.
    These tests verify basic validation without LLM calls.
    """

    @pytest.mark.asyncio
    async def test_normal_search_query_passes_basic_checks(self):
        result = await validate_message("Найди чемодан")
        assert result.risk_score <= 0.5 or result.is_valid is True

    @pytest.mark.asyncio
    async def test_message_length_boundary(self):
        exact_2000 = "a" * 2000
        result = await validate_message(exact_2000)
        assert result.reason != "Сообщение слишком длинное"

        over_2000 = "a" * 2001
        result = await validate_message(over_2000)
        assert result.reason == "Сообщение слишком длинное"
