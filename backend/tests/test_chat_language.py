"""
TDD tests for chat AI language injection — Phase 8.4.

When default_language is non-English, the agent's system prompt
must include an instruction to respond in the selected language.
"""

from unittest.mock import MagicMock, patch

LANG_INSTRUCTIONS = {
    "ru": "Отвечай на русском языке.",
    "es": "Responde en español.",
}


class TestCallModelLanguageInjection:
    """Tests for ai_agent.call_model inserting language instructions."""

    def _make_state(self):
        from langchain_core.messages import HumanMessage

        return {"messages": [HumanMessage(content="Hello")]}

    def _captured_system_content(self, mock_llm_with_tools) -> str:
        """Extract the content of the SystemMessage sent to the LLM."""
        from langchain_core.messages import SystemMessage

        call_args = mock_llm_with_tools.invoke.call_args
        messages = call_args[0][0]
        system_msgs = [m for m in messages if isinstance(m, SystemMessage)]
        assert system_msgs, "No SystemMessage found in LLM call"
        return system_msgs[0].content

    def _run_call_model(self, state, language: str):
        mock_response = MagicMock()
        mock_response.content = "reply"
        mock_registry = MagicMock()
        mock_registry.chat_model.bind_tools.return_value.invoke.return_value = mock_response

        with (
            patch("src.graphs.ai_agent.get_prompt", return_value="Base system prompt"),
            patch("src.graphs.ai_agent._get_ui_language", return_value=language),
            patch("src.ai.registry.registry", mock_registry),
        ):
            from src.graphs.ai_agent import call_model

            call_model(state)

        return mock_registry.chat_model.bind_tools.return_value

    def test_system_prompt_contains_russian_instruction_when_language_is_ru(self):
        state = self._make_state()
        llm = self._run_call_model(state, "ru")
        content = self._captured_system_content(llm)
        assert LANG_INSTRUCTIONS["ru"] in content

    def test_system_prompt_contains_spanish_instruction_when_language_is_es(self):
        state = self._make_state()
        llm = self._run_call_model(state, "es")
        content = self._captured_system_content(llm)
        assert LANG_INSTRUCTIONS["es"] in content

    def test_no_language_instruction_when_english(self):
        state = self._make_state()
        llm = self._run_call_model(state, "en")
        content = self._captured_system_content(llm)
        for instruction in LANG_INSTRUCTIONS.values():
            assert instruction not in content

    def test_base_prompt_always_present(self):
        state = self._make_state()
        llm = self._run_call_model(state, "ru")
        content = self._captured_system_content(llm)
        assert "Base system prompt" in content

    def test_system_message_not_duplicated_if_already_present(self):
        from langchain_core.messages import HumanMessage, SystemMessage

        state = {
            "messages": [
                SystemMessage(content="Existing system"),
                HumanMessage(content="Hello"),
            ]
        }
        mock_response = MagicMock()
        mock_registry = MagicMock()
        mock_registry.chat_model.bind_tools.return_value.invoke.return_value = mock_response

        with (
            patch("src.graphs.ai_agent.get_prompt", return_value="Base"),
            patch("src.graphs.ai_agent._get_ui_language", return_value="ru"),
            patch("src.ai.registry.registry", mock_registry),
        ):
            from src.graphs.ai_agent import call_model

            call_model(state)

        call_args = mock_registry.chat_model.bind_tools.return_value.invoke.call_args
        messages = call_args[0][0]
        system_msgs = [m for m in messages if isinstance(m, SystemMessage)]
        assert len(system_msgs) == 1


class TestGetUiLanguage:
    """Tests for the helper that reads language from settings DB."""

    def test_returns_language_from_db(self):
        from src.graphs.ai_agent import _get_ui_language

        with (
            patch("src.graphs.ai_agent.SessionLocal") as mock_sl,
            patch("src.graphs.ai_agent.get_setting", return_value="ru"),
        ):
            mock_sl.return_value.__enter__ = lambda s: MagicMock()
            mock_sl.return_value.__exit__ = MagicMock(return_value=False)
            result = _get_ui_language()
        assert result == "ru"

    def test_falls_back_to_english_when_not_set(self):
        from src.graphs.ai_agent import _get_ui_language

        with (
            patch("src.graphs.ai_agent.SessionLocal") as mock_sl,
            patch("src.graphs.ai_agent.get_setting", return_value=None),
        ):
            mock_sl.return_value.__enter__ = lambda s: MagicMock()
            mock_sl.return_value.__exit__ = MagicMock(return_value=False)
            result = _get_ui_language()
        assert result == "en"
