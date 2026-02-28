"""
Unit tests for agents/utils.py — Pure utility functions for LangGraph agent.

Estratégia:
  langchain_core.messages está mockado no conftest como MagicMock.
  Definimos AIMessage real de teste e a injetamos em app.agents.utils
  para que a função sanitize_ai_message crie instâncias reais (não MagicMock).
"""

import pytest

from app.agents.utils import (
    extract_text_from_content,
    extract_token_usage,
    sanitize_ai_message,
)


# ---------------------------------------------------------------------------
# Implementação real de AIMessage para uso nos testes
# ---------------------------------------------------------------------------

class AIMessage:
    """Implementação de teste para AIMessage — armazena todos os args do ctor."""
    def __init__(self, content="", tool_calls=None, **kwargs):
        self.content = content
        self.tool_calls = tool_calls if tool_calls is not None else []
        # Armazena atributos extras (ex: usage_metadata, response_metadata)
        for k, v in kwargs.items():
            setattr(self, k, v)

    def __repr__(self):
        return f"AIMessage(content={self.content!r})"


@pytest.fixture(autouse=True)
def patch_ai_message_in_utils(monkeypatch):
    """
    Patcha AIMessage em app.agents.utils com a implementação real de teste.
    Isso faz sanitize_ai_message() retornar AIMessage reais, não MagicMocks.
    """
    import app.agents.utils as utils_mod
    monkeypatch.setattr(utils_mod, "AIMessage", AIMessage)


# ═══════════════════════════════════════════════════════════════════════════
# EXTRACT TEXT FROM CONTENT
# ═══════════════════════════════════════════════════════════════════════════


class TestExtractTextFromContent:

    def test_string_passthrough(self):
        assert extract_text_from_content("Hello, world!") == "Hello, world!"

    def test_none_returns_empty(self):
        assert extract_text_from_content(None) == ""

    def test_empty_string(self):
        assert extract_text_from_content("") == ""

    def test_list_of_text_blocks(self):
        """Reasoning models return list with type/text blocks."""
        content = [
            {"type": "text", "text": "Hello "},
            {"type": "text", "text": "world!"},
        ]
        assert extract_text_from_content(content) == "Hello world!"

    def test_list_filters_reasoning_blocks(self):
        """Should only extract 'text' type blocks, ignoring 'thinking'."""
        content = [
            {"type": "thinking", "text": "Let me reason..."},
            {"type": "text", "text": "Here's the answer"},
        ]
        assert extract_text_from_content(content) == "Here's the answer"

    def test_list_of_strings(self):
        assert extract_text_from_content(["part1", "part2"]) == "part1part2"

    def test_mixed_blocks_and_strings(self):
        content = [
            {"type": "text", "text": "Hello "},
            "plain string",
        ]
        assert extract_text_from_content(content) == "Hello plain string"

    def test_fallback_to_str(self):
        """Non-string, non-list falls back to str()."""
        assert extract_text_from_content(42) == "42"

    def test_empty_list(self):
        assert extract_text_from_content([]) == ""

    def test_list_with_missing_text_key(self):
        content = [{"type": "text"}]  # Missing 'text' key
        assert extract_text_from_content(content) == ""


# ═══════════════════════════════════════════════════════════════════════════
# EXTRACT TOKEN USAGE
# ═══════════════════════════════════════════════════════════════════════════


class TestExtractTokenUsage:

    def test_usage_metadata_modern(self):
        """LangChain modern format (GPT-5, o1)."""
        msg = AIMessage(content="test")
        msg.usage_metadata = {
            "input_tokens": 100,
            "output_tokens": 50,
            "total_tokens": 150,
        }

        tokens = extract_token_usage(msg)
        assert tokens["tokens_input"] == 100
        assert tokens["tokens_output"] == 50
        assert tokens["tokens_total"] == 150

    def test_usage_metadata_with_reasoning(self):
        """Reasoning models (o1/o3/GPT-5) include reasoning tokens."""
        msg = AIMessage(content="test")
        msg.usage_metadata = {
            "input_tokens": 200,
            "output_tokens": 100,
            "total_tokens": 300,
            "output_token_details": {"reasoning_tokens": 60},
        }

        tokens = extract_token_usage(msg)
        assert tokens["reasoning_tokens"] == 60

    def test_response_metadata_legacy(self):
        """Legacy format with response_metadata.token_usage."""
        msg = AIMessage(
            content="test",
            response_metadata={
                "token_usage": {
                    "prompt_tokens": 80,
                    "completion_tokens": 40,
                    "total_tokens": 120,
                }
            },
        )

        tokens = extract_token_usage(msg)
        assert tokens["tokens_input"] == 80
        assert tokens["tokens_output"] == 40
        assert tokens["tokens_total"] == 120

    def test_response_metadata_usage_key(self):
        """Alternative legacy with 'usage' instead of 'token_usage'."""
        msg = AIMessage(
            content="test",
            response_metadata={
                "usage": {
                    "prompt_tokens": 50,
                    "completion_tokens": 25,
                    "total_tokens": 75,
                }
            },
        )

        tokens = extract_token_usage(msg)
        assert tokens["tokens_input"] == 50
        assert tokens["tokens_output"] == 25

    def test_no_usage_data_returns_zeros(self):
        msg = AIMessage(content="test")
        tokens = extract_token_usage(msg)
        assert tokens["tokens_input"] == 0
        assert tokens["tokens_output"] == 0
        assert tokens["tokens_total"] == 0
        assert tokens["reasoning_tokens"] == 0

    def test_total_tokens_calculated_if_missing(self):
        """If total_tokens missing, should be sum of input+output."""
        msg = AIMessage(content="test")
        msg.usage_metadata = {
            "input_tokens": 30,
            "output_tokens": 20,
        }

        tokens = extract_token_usage(msg)
        assert tokens["tokens_total"] == 50


# ═══════════════════════════════════════════════════════════════════════════
# SANITIZE AI MESSAGE
# ═══════════════════════════════════════════════════════════════════════════


class TestSanitizeAiMessage:

    def test_string_content_unchanged(self):
        msg = AIMessage(content="Hello, world!")
        clean = sanitize_ai_message(msg)
        assert clean.content == "Hello, world!"

    def test_removes_reasoning_blocks(self):
        """Reasoning blocks should be stripped."""
        msg = AIMessage(content=[
            {"type": "thinking", "text": "Internal reasoning..."},
            {"type": "text", "text": "Final answer"},
        ])
        clean = sanitize_ai_message(msg)
        assert clean.content == "Final answer"
        assert isinstance(clean.content, str)

    def test_preserves_tool_calls(self):
        """tool_calls must be preserved for agent flow."""
        msg = AIMessage(content="Call a tool", tool_calls=[
            {"name": "search", "args": {"q": "test"}, "id": "tc-1"},
        ])
        clean = sanitize_ai_message(msg)
        assert len(clean.tool_calls) == 1
        assert clean.tool_calls[0]["name"] == "search"

    def test_empty_tool_calls_not_copied(self):
        msg = AIMessage(content="No tools")
        clean = sanitize_ai_message(msg)
        assert not getattr(clean, "tool_calls", None) or clean.tool_calls == []

    def test_returns_new_aimessage_instance(self):
        msg = AIMessage(content="Original")
        clean = sanitize_ai_message(msg)
        assert clean is not msg
