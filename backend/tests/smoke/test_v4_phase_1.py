"""
Smoke tests for V4 Phase 1 — Technical Alignment & Cleanup.
"""

import os
from unittest.mock import AsyncMock

import pytest

pytestmark = [
    pytest.mark.smoke,
    pytest.mark.phase("v4-phase-1"),
]


class TestV4Phase1:
    """ST-V4-1.x: Technical Alignment & Cleanup."""

    def test_st_v4_1_1_llmconfig_default_none(self):
        """ST-V4-1.1: LLMConfig default model is None."""
        from agent_platform.llm.models import LLMConfig

        config = LLMConfig()
        assert config.model is None

        config2 = LLMConfig(temperature=0.5)
        assert config2.model is None

    def test_st_v4_1_2_openrouter_fallback(self):
        """ST-V4-1.2: OpenRouterProvider uses fallback model."""
        from agent_platform.llm.openrouter import OpenRouterProvider

        provider = OpenRouterProvider(
            api_key="test-key",
            default_model="openai/gpt-test",
        )
        assert provider._default_model == "openai/gpt-test"

    def test_st_v4_1_3_tooltype_internal(self):
        """ST-V4-1.3: ToolType.INTERNAL exists."""
        from agent_platform.tools.models import ToolType

        assert ToolType.INTERNAL == "internal"
        assert ToolType.MCP == "mcp"
        assert not hasattr(ToolType, "PROMPT_MACRO")

    def test_st_v4_1_4_shared_cosine_similarity(self):
        """ST-V4-1.4: Shared cosine_similarity in utils."""
        from agent_platform.core.utils import cosine_similarity

        assert cosine_similarity([1, 0, 0], [1, 0, 0]) == pytest.approx(1.0)
        assert cosine_similarity([1, 0, 0], [0, 1, 0]) == pytest.approx(0.0)
        assert cosine_similarity([0, 0, 0], [1, 0, 0]) == pytest.approx(0.0)

    def test_st_v4_1_5_shared_resolve_env_vars(self):
        """ST-V4-1.5: Shared resolve_env_vars in utils."""
        from agent_platform.core.utils import resolve_env_vars

        os.environ["TEST_V4_KEY"] = "resolved"
        try:
            result = resolve_env_vars({"A": "${TEST_V4_KEY}", "B": "literal"})
            assert result["A"] == "resolved"
            assert result["B"] == "literal"
        finally:
            del os.environ["TEST_V4_KEY"]

    @pytest.mark.asyncio
    async def test_st_v4_1_6_capability_tools_agent_model(self, tmp_path):
        """ST-V4-1.6: capability_tools uses agent model."""
        from agent_platform.core.models import Agent, AgentConfig
        from agent_platform.db.sqlite_agent_repo import SqliteAgentRepo
        from agent_platform.llm.models import LLMResponse
        from agent_platform.tools.capability_tools import CapabilityToolProvider

        db = str(tmp_path / "test.db")
        agent_repo = SqliteAgentRepo(db)
        await agent_repo.initialize()

        agent = Agent(
            name="model-test",
            config=AgentConfig(model="my-test-model"),
        )
        await agent_repo.create(agent)

        used_model = None
        mock_llm = AsyncMock()

        async def capture(messages, *a, **kw):
            nonlocal used_model
            config = kw.get("config")
            if config and config.model:
                used_model = config.model
            return LLMResponse(content="Assessment done.", usage={})

        mock_llm.complete = capture

        provider = CapabilityToolProvider(
            llm_provider=mock_llm,
            agent_repo=agent_repo,
        )

        await provider.call_tool(
            "analyze_capabilities",
            {"task": "test task", "agent_id": agent.id},
        )

        assert used_model == "my-test-model"
        await agent_repo.close()
