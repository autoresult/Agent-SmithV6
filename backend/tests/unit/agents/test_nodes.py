"""
Unit tests for app/agents/nodes.py — Pure LangGraph node logic.

Testa as funções puras (sem LLM, sem LangChain async):
  - sanitize_history()     — limpeza do histórico de mensagens
  - build_system_prompt()  — montagem do system prompt
  - should_continue()      — roteador tools vs end

Estratégia:
  langchain_core.messages está mockado no conftest como MagicMock.
  Usamos @patch para substituir AIMessage/ToolMessage/HumanMessage dentro
  de app.agents.nodes por classes reais de teste — isso faz o isinstance()
  funcionar corretamente dentro das funções.
"""

import pytest
from unittest.mock import MagicMock, patch


# ===========================================================================
# Implementações reais de mensagem para uso nos testes
# ===========================================================================

class AIMessage:
    """Implementação de teste para AIMessage."""
    def __init__(self, content="", tool_calls=None):
        self.content = content
        self.tool_calls = tool_calls or []
        self.type = "ai"

    def __repr__(self):
        return f"AIMessage(content={self.content!r}, tool_calls={self.tool_calls})"


class ToolMessage:
    """Implementação de teste para ToolMessage."""
    def __init__(self, content="", tool_call_id=""):
        self.content = content
        self.tool_call_id = tool_call_id
        self.tool_calls = []
        self.type = "tool"

    def __repr__(self):
        return f"ToolMessage(tool_call_id={self.tool_call_id!r})"


class HumanMessage:
    """Implementação de teste para HumanMessage."""
    def __init__(self, content=""):
        self.content = content
        self.tool_calls = []
        self.type = "human"

    def __repr__(self):
        return f"HumanMessage(content={self.content!r})"


# Fixture que substitui as classes mocked por implementações reais
@pytest.fixture(autouse=True)
def patch_message_classes(monkeypatch):
    """
    Patcha AIMessage/ToolMessage/HumanMessage em app.agents.nodes
    com implementações reais para que isinstance() funcione corretamente.
    """
    import app.agents.nodes as nodes_mod
    monkeypatch.setattr(nodes_mod, "AIMessage", AIMessage)
    monkeypatch.setattr(nodes_mod, "ToolMessage", ToolMessage)
    monkeypatch.setattr(nodes_mod, "HumanMessage", HumanMessage)


# ===========================================================================
# SANITIZE HISTORY
# ===========================================================================


class TestSanitizeHistory:
    """Testa limpeza do histórico para compatibilidade multi-provider."""

    def test_empty_list_returns_empty(self):
        from app.agents.nodes import sanitize_history
        assert sanitize_history([]) == []

    def test_preserves_human_messages(self):
        from app.agents.nodes import sanitize_history
        msgs = [HumanMessage("Olá"), HumanMessage("Tudo bem?")]
        result = sanitize_history(msgs)
        assert len(result) == 2

    def test_preserves_ai_message_without_tool_calls(self):
        from app.agents.nodes import sanitize_history
        msgs = [AIMessage("Resposta simples")]
        result = sanitize_history(msgs)
        assert len(result) == 1

    def test_keeps_valid_tool_call_pair(self):
        """Par válido AIMessage(tool_call) + ToolMessage deve ser preservado."""
        from app.agents.nodes import sanitize_history

        ai_msg = AIMessage(
            content="",
            tool_calls=[{"id": "call-1", "name": "search", "args": {}}],
        )
        tool_msg = ToolMessage(content="result", tool_call_id="call-1")

        result = sanitize_history([ai_msg, tool_msg])
        # Ambas as mensagens devem estar presentes
        assert len(result) == 2

    def test_removes_orphan_tool_message(self):
        """ToolMessage sem AIMessage pai (tool_call_id sem par) deve ser removida."""
        from app.agents.nodes import sanitize_history

        orphan_tool = ToolMessage(content="result", tool_call_id="orphan-id")
        result = sanitize_history([orphan_tool])
        # ToolMessage órfã removida
        assert len(result) == 0

    def test_removes_ai_with_unmatched_tool_call_no_text(self):
        """
        AIMessage com tool_call sem ToolMessage correspondente E sem texto
        deve ser removida (não convertida).
        """
        from app.agents.nodes import sanitize_history

        ai_with_orphan_call = AIMessage(
            content="",
            tool_calls=[{"id": "unmatched-1", "name": "tool", "args": {}}],
        )
        result = sanitize_history([ai_with_orphan_call])
        # Sem texto → removida completamente
        assert len(result) == 0

    def test_converts_ai_orphan_call_to_text_when_has_content(self):
        """
        AIMessage com tool_call órfão MAS com texto → converte para AIMessage(texto).
        """
        from app.agents.nodes import sanitize_history

        ai_with_orphan_call = AIMessage(
            content="Deixa eu verificar isso.",
            tool_calls=[{"id": "orphan-2", "name": "tool", "args": {}}],
        )
        result = sanitize_history([ai_with_orphan_call])
        # Convertida para AIMessage com texto apenas
        assert len(result) == 1
        assert result[0].content == "Deixa eu verificar isso."

    def test_merges_consecutive_ai_messages(self):
        """
        AIMessages consecutivas sem tool_calls devem ser mergeadas
        (Gemini não aceita sequências AI→AI).
        """
        from app.agents.nodes import sanitize_history

        ai1 = AIMessage("Primeira parte.")
        ai2 = AIMessage("Segunda parte.")
        result = sanitize_history([ai1, ai2])
        assert len(result) == 1
        assert "Primeira parte." in result[0].content
        assert "Segunda parte." in result[0].content

    def test_does_not_merge_ai_messages_with_tool_calls(self):
        """
        AIMessages com tool_calls não devem ser mergeadas mesmo que consecutivas.
        """
        from app.agents.nodes import sanitize_history

        ai1 = AIMessage(
            content="",
            tool_calls=[{"id": "c1", "name": "t", "args": {}}],
        )
        tool_response = ToolMessage("result", tool_call_id="c1")
        ai2 = AIMessage(
            content="",
            tool_calls=[{"id": "c2", "name": "t", "args": {}}],
        )
        tool_response2 = ToolMessage("result2", tool_call_id="c2")

        result = sanitize_history([ai1, tool_response, ai2, tool_response2])
        # Todos os 4 mensagens preservadas sem merge
        assert len(result) == 4

    def test_mixed_history_preserved_correctly(self):
        """
        Human → AI → (AI+tool, ToolMsg) → AI  deve preservar tudo.
        """
        from app.agents.nodes import sanitize_history

        human = HumanMessage("Quero saber sobre X")
        ai_text = AIMessage("Vou verificar.")
        ai_with_tool = AIMessage(
            content="",
            tool_calls=[{"id": "t1", "name": "search", "args": {}}],
        )
        tool_resp = ToolMessage("dados sobre X", tool_call_id="t1")
        ai_final = AIMessage("X é isso aqui...")

        msgs = [human, ai_text, ai_with_tool, tool_resp, ai_final]
        result = sanitize_history(msgs)
        # human, ai_text+ai_final mergeados (consecutivas após sanitização? não — tem ai_with_tool+tool entre eles)
        # human, ai_text, ai_with_tool, tool_resp, ai_final → 5 mensagens (ai_text e ai_final não são consecutivas)
        assert len(result) == 5


# ===========================================================================
# BUILD SYSTEM PROMPT
# ===========================================================================


class TestBuildSystemPrompt:
    """Testa montagem do system prompt a partir da config da empresa."""

    def test_returns_non_empty_string(self):
        from app.agents.nodes import build_system_prompt
        result = build_system_prompt({})
        assert isinstance(result, str)
        assert len(result) > 0

    def test_uses_company_agent_system_prompt(self):
        from app.agents.nodes import build_system_prompt
        config = {"agent_system_prompt": "Você é o assistente da Acme Corp."}
        result = build_system_prompt(config)
        assert "Acme Corp" in result

    def test_includes_company_name_when_provided(self):
        from app.agents.nodes import build_system_prompt
        config = {"company_name": "Tech Brasil Ltda"}
        result = build_system_prompt(config)
        assert "Tech Brasil Ltda" in result

    def test_no_rag_section_without_context(self):
        from app.agents.nodes import build_system_prompt
        result = build_system_prompt({}, rag_context=None)
        assert "CONTEXTO DOS DOCUMENTOS" not in result

    def test_includes_rag_context_when_provided(self):
        from app.agents.nodes import build_system_prompt
        rag = "Informação importante do documento: X custa R$ 100."
        result = build_system_prompt({}, rag_context=rag)
        assert "CONTEXTO DOS DOCUMENTOS" in result
        assert rag in result

    def test_default_prompt_when_no_system_prompt(self):
        """Sem agent_system_prompt → usa prompt padrão em português."""
        from app.agents.nodes import build_system_prompt
        result = build_system_prompt({})
        assert "assistente" in result.lower()


# ===========================================================================
# SHOULD CONTINUE
# ===========================================================================


class TestShouldContinue:
    """Testa roteamento: tools vs end."""

    def test_returns_tools_when_last_message_has_tool_calls(self):
        from app.agents.nodes import should_continue
        last_msg = MagicMock()
        last_msg.tool_calls = [{"id": "call-1", "name": "search"}]
        state = {"messages": [HumanMessage("oi"), last_msg]}
        assert should_continue(state) == "tools"

    def test_returns_end_without_tool_calls(self):
        from app.agents.nodes import should_continue
        last_msg = AIMessage("Resposta final.")
        state = {"messages": [HumanMessage("oi"), last_msg]}
        assert should_continue(state) == "end"

    def test_returns_end_with_empty_tool_calls_list(self):
        from app.agents.nodes import should_continue
        last_msg = AIMessage("Resposta.", tool_calls=[])
        state = {"messages": [last_msg]}
        assert should_continue(state) == "end"

    def test_returns_tools_with_multiple_tool_calls(self):
        from app.agents.nodes import should_continue
        last_msg = MagicMock()
        last_msg.tool_calls = [
            {"id": "c1", "name": "search"},
            {"id": "c2", "name": "calculator"},
        ]
        state = {"messages": [last_msg]}
        assert should_continue(state) == "tools"

    def test_single_human_message_returns_end(self):
        """Estado com apenas HumanMessage → end (sem tool_calls)."""
        from app.agents.nodes import should_continue
        last_msg = HumanMessage("Olá!")
        state = {"messages": [last_msg]}
        assert should_continue(state) == "end"
