"""
Smoke tests for V2 Phase 2 — Inter-Agent Communication & Async Lifecycle.

All LLM calls are mocked — no real API calls.
"""

import asyncio
import time
from unittest.mock import AsyncMock

import pytest

pytestmark = [
    pytest.mark.smoke,
    pytest.mark.phase("v2-phase-2"),
]


class TestV2Phase2:
    """ST-V2-2.x: Inter-Agent Communication smoke tests."""

    def test_st_v2_2_1_message_model(self):
        """ST-V2-2.1: AgentMessage model and MessageType enum."""
        from agent_platform.core.models import AgentMessage, MessageType

        # MessageType enum values
        assert MessageType.TASK == "task"
        assert MessageType.RESULT == "result"
        assert MessageType.QUESTION == "question"
        assert MessageType.ANSWER == "answer"
        assert MessageType.GUIDANCE == "guidance"
        assert MessageType.STATUS_UPDATE == "status_update"

        # AgentMessage creation
        msg = AgentMessage(
            from_agent_id="agent-1",
            to_agent_id="agent-2",
            content="Do this task",
            message_type=MessageType.TASK,
        )
        assert msg.id is not None
        assert msg.from_agent_id == "agent-1"
        assert msg.to_agent_id == "agent-2"
        assert msg.content == "Do this task"
        assert msg.message_type == MessageType.TASK
        assert msg.timestamp is not None
        assert msg.in_reply_to is None

    @pytest.mark.asyncio
    async def test_st_v2_2_2_message_repo_crud(self, tmp_path):
        """ST-V2-2.2: SqliteMessageRepo CRUD operations."""
        from agent_platform.core.models import AgentMessage, MessageType
        from agent_platform.db.sqlite_message_repo import SqliteMessageRepo

        repo = SqliteMessageRepo(str(tmp_path / "msg.db"))
        await repo.initialize()

        # Create
        msg = AgentMessage(
            from_agent_id="a1",
            to_agent_id="a2",
            content="Hello",
            message_type=MessageType.TASK,
        )
        created = await repo.create(msg)
        assert created.id == msg.id

        # Get
        fetched = await repo.get(msg.id)
        assert fetched is not None
        assert fetched.content == "Hello"

        # List for agent (inbox)
        inbox = await repo.list_for_agent("a2", direction="inbox")
        assert len(inbox) == 1
        assert inbox[0].content == "Hello"

        # List between
        msg2 = AgentMessage(
            from_agent_id="a2",
            to_agent_id="a1",
            content="Reply",
            message_type=MessageType.ANSWER,
        )
        await repo.create(msg2)
        between = await repo.list_between("a1", "a2")
        assert len(between) == 2

        # Delete
        deleted = await repo.delete(msg.id)
        assert deleted is True
        assert await repo.get(msg.id) is None

        await repo.close()

    @pytest.mark.asyncio
    async def test_st_v2_2_3_spawn_returns_immediately(self, tmp_path):
        """ST-V2-2.3: spawn_agent returns immediately (async)."""
        from agent_platform.core.models import Agent, AgentConfig, AgentStatus
        from agent_platform.db.sqlite_agent_repo import SqliteAgentRepo
        from agent_platform.db.sqlite_conversation_repo import (
            SqliteConversationRepo,
        )
        from agent_platform.db.sqlite_message_repo import SqliteMessageRepo
        from agent_platform.llm.models import LLMResponse
        from agent_platform.observation.in_process_event_bus import (
            InProcessEventBus,
        )
        from agent_platform.tools.agent_spawner import AgentSpawnerProvider
        from agent_platform.tools.registry import ToolRegistry

        agent_repo = SqliteAgentRepo(str(tmp_path / "a.db"))
        conv_repo = SqliteConversationRepo(str(tmp_path / "c.db"))
        msg_repo = SqliteMessageRepo(str(tmp_path / "m.db"))
        event_bus = InProcessEventBus()
        await agent_repo.initialize()
        await conv_repo.initialize()
        await msg_repo.initialize()

        # Create parent
        parent = Agent(name="parent", config=AgentConfig(model="test"))
        await agent_repo.create(parent)

        # Mock LLM — slow response to prove non-blocking
        mock_llm = AsyncMock()

        async def slow_response(*a, **kw):
            await asyncio.sleep(0.5)
            return LLMResponse(content="Done", usage={})

        mock_llm.complete = slow_response

        spawner = AgentSpawnerProvider(
            agent_repo=agent_repo,
            conversation_repo=conv_repo,
            llm_provider=mock_llm,
            event_bus=event_bus,
            tool_registry=ToolRegistry(),
            message_repo=msg_repo,
        )

        start = time.monotonic()
        result = await spawner.call_tool(
            "spawn_agent",
            {
                "name": "child",
                "task": "Say hello",
                "agent_id": parent.id,
            },
        )
        elapsed = time.monotonic() - start

        assert result.success
        # Must return in under 0.3s (child takes 0.5s)
        assert elapsed < 0.3

        import json

        data = json.loads(result.output)
        assert "child_agent_id" in data
        assert data.get("status") == "running"

        # Yield to let background task start
        await asyncio.sleep(0.05)

        # Child should be RUNNING (mock takes 0.5s)
        child = await agent_repo.get(data["child_agent_id"])
        assert child is not None
        assert child.status == AgentStatus.RUNNING

        # Wait for background task to finish
        await asyncio.sleep(1.0)

        await agent_repo.close()
        await conv_repo.close()
        await msg_repo.close()

    @pytest.mark.asyncio
    async def test_st_v2_2_4_child_completes_in_background(self, tmp_path):
        """ST-V2-2.4: Child agent runs to completion in background."""
        from agent_platform.core.models import Agent, AgentConfig, AgentStatus
        from agent_platform.db.sqlite_agent_repo import SqliteAgentRepo
        from agent_platform.db.sqlite_conversation_repo import (
            SqliteConversationRepo,
        )
        from agent_platform.db.sqlite_message_repo import SqliteMessageRepo
        from agent_platform.llm.models import LLMResponse
        from agent_platform.observation.events import EventFilter, EventType
        from agent_platform.observation.in_process_event_bus import (
            InProcessEventBus,
        )
        from agent_platform.tools.agent_spawner import AgentSpawnerProvider
        from agent_platform.tools.registry import ToolRegistry

        db = str(tmp_path / "test.db")
        agent_repo = SqliteAgentRepo(db)
        conv_repo = SqliteConversationRepo(db)
        msg_repo = SqliteMessageRepo(db)
        event_bus = InProcessEventBus(db_path=str(tmp_path / "ev.db"))
        await agent_repo.initialize()
        await conv_repo.initialize()
        await msg_repo.initialize()
        await event_bus.initialize()

        parent = Agent(name="parent", config=AgentConfig(model="test"))
        await agent_repo.create(parent)

        mock_llm = AsyncMock()
        mock_llm.complete.return_value = LLMResponse(content="Task complete!", usage={})

        spawner = AgentSpawnerProvider(
            agent_repo=agent_repo,
            conversation_repo=conv_repo,
            llm_provider=mock_llm,
            event_bus=event_bus,
            tool_registry=ToolRegistry(),
            message_repo=msg_repo,
        )

        result = await spawner.call_tool(
            "spawn_agent",
            {"name": "bg-child", "task": "Do work", "agent_id": parent.id},
        )

        import json

        child_id = json.loads(result.output)["child_agent_id"]

        # Wait for completion
        await asyncio.sleep(0.5)

        child = await agent_repo.get(child_id)
        assert child is not None
        assert child.status == AgentStatus.IDLE

        # AGENT_COMPLETE event should exist
        events = await event_bus.query(
            EventFilter(
                agent_id=child_id,
                event_types=[EventType.AGENT_COMPLETE],
            )
        )
        assert len(events) >= 1

        await event_bus.close()
        await agent_repo.close()
        await conv_repo.close()
        await msg_repo.close()

    @pytest.mark.asyncio
    async def test_st_v2_2_5_wait_for_agent(self, tmp_path):
        """ST-V2-2.5: wait_for_agent blocks until child completes."""
        from agent_platform.core.models import Agent, AgentConfig
        from agent_platform.db.sqlite_agent_repo import SqliteAgentRepo
        from agent_platform.db.sqlite_conversation_repo import (
            SqliteConversationRepo,
        )
        from agent_platform.db.sqlite_message_repo import SqliteMessageRepo
        from agent_platform.llm.models import LLMResponse
        from agent_platform.observation.in_process_event_bus import (
            InProcessEventBus,
        )
        from agent_platform.tools.agent_spawner import AgentSpawnerProvider
        from agent_platform.tools.registry import ToolRegistry

        db = str(tmp_path / "test.db")
        agent_repo = SqliteAgentRepo(db)
        conv_repo = SqliteConversationRepo(db)
        msg_repo = SqliteMessageRepo(db)
        event_bus = InProcessEventBus()
        await agent_repo.initialize()
        await conv_repo.initialize()
        await msg_repo.initialize()

        parent = Agent(name="parent", config=AgentConfig(model="test"))
        await agent_repo.create(parent)

        mock_llm = AsyncMock()

        async def delayed(*a, **kw):
            await asyncio.sleep(0.3)
            return LLMResponse(content="Result!", usage={})

        mock_llm.complete = delayed

        spawner = AgentSpawnerProvider(
            agent_repo=agent_repo,
            conversation_repo=conv_repo,
            llm_provider=mock_llm,
            event_bus=event_bus,
            tool_registry=ToolRegistry(),
            message_repo=msg_repo,
        )

        # Spawn async
        import json

        spawn_result = await spawner.call_tool(
            "spawn_agent",
            {"name": "wait-child", "task": "Work", "agent_id": parent.id},
        )
        child_id = json.loads(spawn_result.output)["child_agent_id"]

        # Wait for agent
        wait_result = await spawner.call_tool(
            "wait_for_agent",
            {"child_agent_id": child_id, "agent_id": parent.id},
        )
        assert wait_result.success
        data = json.loads(wait_result.output)
        assert data["status"] == "idle"
        assert data["content"] is not None

        await agent_repo.close()
        await conv_repo.close()
        await msg_repo.close()

    @pytest.mark.asyncio
    async def test_st_v2_2_6_check_agent_status(self, tmp_path):
        """ST-V2-2.6: check_agent_status returns current status."""
        from agent_platform.core.models import Agent, AgentConfig
        from agent_platform.db.sqlite_agent_repo import SqliteAgentRepo
        from agent_platform.db.sqlite_conversation_repo import (
            SqliteConversationRepo,
        )
        from agent_platform.db.sqlite_message_repo import SqliteMessageRepo
        from agent_platform.llm.models import LLMResponse
        from agent_platform.observation.in_process_event_bus import (
            InProcessEventBus,
        )
        from agent_platform.tools.agent_spawner import AgentSpawnerProvider
        from agent_platform.tools.registry import ToolRegistry

        db = str(tmp_path / "test.db")
        agent_repo = SqliteAgentRepo(db)
        conv_repo = SqliteConversationRepo(db)
        msg_repo = SqliteMessageRepo(db)
        event_bus = InProcessEventBus()
        await agent_repo.initialize()
        await conv_repo.initialize()
        await msg_repo.initialize()

        parent = Agent(name="parent", config=AgentConfig(model="test"))
        await agent_repo.create(parent)

        mock_llm = AsyncMock()

        async def slow(*a, **kw):
            await asyncio.sleep(1.0)
            return LLMResponse(content="Done", usage={})

        mock_llm.complete = slow

        spawner = AgentSpawnerProvider(
            agent_repo=agent_repo,
            conversation_repo=conv_repo,
            llm_provider=mock_llm,
            event_bus=event_bus,
            tool_registry=ToolRegistry(),
            message_repo=msg_repo,
        )

        import json

        spawn_result = await spawner.call_tool(
            "spawn_agent",
            {"name": "status-child", "task": "Work", "agent_id": parent.id},
        )
        child_id = json.loads(spawn_result.output)["child_agent_id"]

        # Yield to let background task start
        await asyncio.sleep(0.05)

        # Check status — should be running (mock takes 1.0s)
        status_result = await spawner.call_tool(
            "check_agent_status",
            {"child_agent_id": child_id, "agent_id": parent.id},
        )
        assert status_result.success
        data = json.loads(status_result.output)
        assert data["status"] == "running"
        assert "name" in data

        # Cleanup
        await asyncio.sleep(1.5)
        await agent_repo.close()
        await conv_repo.close()
        await msg_repo.close()

    @pytest.mark.asyncio
    async def test_st_v2_2_7_stop_agent(self, tmp_path):
        """ST-V2-2.7: stop_agent cancels running child."""
        from agent_platform.core.models import Agent, AgentConfig, AgentStatus
        from agent_platform.db.sqlite_agent_repo import SqliteAgentRepo
        from agent_platform.db.sqlite_conversation_repo import (
            SqliteConversationRepo,
        )
        from agent_platform.db.sqlite_message_repo import SqliteMessageRepo
        from agent_platform.llm.models import LLMResponse
        from agent_platform.observation.in_process_event_bus import (
            InProcessEventBus,
        )
        from agent_platform.tools.agent_spawner import AgentSpawnerProvider
        from agent_platform.tools.registry import ToolRegistry

        db = str(tmp_path / "test.db")
        agent_repo = SqliteAgentRepo(db)
        conv_repo = SqliteConversationRepo(db)
        msg_repo = SqliteMessageRepo(db)
        event_bus = InProcessEventBus()
        await agent_repo.initialize()
        await conv_repo.initialize()
        await msg_repo.initialize()

        parent = Agent(name="parent", config=AgentConfig(model="test"))
        await agent_repo.create(parent)

        mock_llm = AsyncMock()

        async def very_slow(*a, **kw):
            await asyncio.sleep(10.0)
            return LLMResponse(content="Done", usage={})

        mock_llm.complete = very_slow

        spawner = AgentSpawnerProvider(
            agent_repo=agent_repo,
            conversation_repo=conv_repo,
            llm_provider=mock_llm,
            event_bus=event_bus,
            tool_registry=ToolRegistry(),
            message_repo=msg_repo,
        )

        import json

        spawn_result = await spawner.call_tool(
            "spawn_agent",
            {"name": "stop-child", "task": "Long work", "agent_id": parent.id},
        )
        child_id = json.loads(spawn_result.output)["child_agent_id"]

        await asyncio.sleep(0.1)

        # Stop it
        stop_result = await spawner.call_tool(
            "stop_agent",
            {"child_agent_id": child_id, "agent_id": parent.id},
        )
        assert stop_result.success

        await asyncio.sleep(0.2)

        child = await agent_repo.get(child_id)
        assert child is not None
        assert child.status == AgentStatus.IDLE

        await agent_repo.close()
        await conv_repo.close()
        await msg_repo.close()

    @pytest.mark.asyncio
    async def test_st_v2_2_8_send_message(self, tmp_path):
        """ST-V2-2.8: send_message creates message and emits events."""
        from agent_platform.core.models import Agent, AgentConfig
        from agent_platform.db.sqlite_agent_repo import SqliteAgentRepo
        from agent_platform.db.sqlite_conversation_repo import (
            SqliteConversationRepo,
        )
        from agent_platform.db.sqlite_message_repo import SqliteMessageRepo
        from agent_platform.observation.events import EventFilter, EventType
        from agent_platform.observation.in_process_event_bus import (
            InProcessEventBus,
        )
        from agent_platform.tools.agent_spawner import AgentSpawnerProvider
        from agent_platform.tools.registry import ToolRegistry

        db = str(tmp_path / "test.db")
        agent_repo = SqliteAgentRepo(db)
        conv_repo = SqliteConversationRepo(db)
        msg_repo = SqliteMessageRepo(db)
        event_bus = InProcessEventBus(db_path=str(tmp_path / "ev.db"))
        await agent_repo.initialize()
        await conv_repo.initialize()
        await msg_repo.initialize()
        await event_bus.initialize()

        a1 = Agent(name="sender", config=AgentConfig(model="test"))
        a2 = Agent(name="receiver", config=AgentConfig(model="test"))
        await agent_repo.create(a1)
        await agent_repo.create(a2)

        spawner = AgentSpawnerProvider(
            agent_repo=agent_repo,
            conversation_repo=conv_repo,
            llm_provider=AsyncMock(),
            event_bus=event_bus,
            tool_registry=ToolRegistry(),
            message_repo=msg_repo,
        )

        result = await spawner.call_tool(
            "send_message",
            {
                "target_agent_id": a2.id,
                "content": "Please do this",
                "message_type": "task",
                "agent_id": a1.id,
            },
        )
        assert result.success

        # Message in repo
        msgs = await msg_repo.list_for_agent(a2.id, direction="inbox")
        assert len(msgs) == 1
        assert msgs[0].content == "Please do this"

        # Events
        sent_events = await event_bus.query(
            EventFilter(
                agent_id=a1.id,
                event_types=[EventType.MESSAGE_SENT],
            )
        )
        assert len(sent_events) >= 1

        recv_events = await event_bus.query(
            EventFilter(
                agent_id=a2.id,
                event_types=[EventType.MESSAGE_RECEIVED],
            )
        )
        assert len(recv_events) >= 1

        await event_bus.close()
        await agent_repo.close()
        await conv_repo.close()
        await msg_repo.close()

    @pytest.mark.asyncio
    async def test_st_v2_2_9_receive_messages(self, tmp_path):
        """ST-V2-2.9: receive_messages returns inbox messages."""
        from agent_platform.core.models import (
            Agent,
            AgentConfig,
            AgentMessage,
            MessageType,
        )
        from agent_platform.db.sqlite_agent_repo import SqliteAgentRepo
        from agent_platform.db.sqlite_conversation_repo import (
            SqliteConversationRepo,
        )
        from agent_platform.db.sqlite_message_repo import SqliteMessageRepo
        from agent_platform.observation.in_process_event_bus import (
            InProcessEventBus,
        )
        from agent_platform.tools.agent_spawner import AgentSpawnerProvider
        from agent_platform.tools.registry import ToolRegistry

        db = str(tmp_path / "test.db")
        agent_repo = SqliteAgentRepo(db)
        conv_repo = SqliteConversationRepo(db)
        msg_repo = SqliteMessageRepo(db)
        event_bus = InProcessEventBus()
        await agent_repo.initialize()
        await conv_repo.initialize()
        await msg_repo.initialize()

        a1 = Agent(name="sender", config=AgentConfig(model="test"))
        a2 = Agent(name="receiver", config=AgentConfig(model="test"))
        await agent_repo.create(a1)
        await agent_repo.create(a2)

        # Pre-populate messages
        await msg_repo.create(
            AgentMessage(
                from_agent_id=a1.id,
                to_agent_id=a2.id,
                content="Task 1",
                message_type=MessageType.TASK,
            )
        )
        await msg_repo.create(
            AgentMessage(
                from_agent_id=a1.id,
                to_agent_id=a2.id,
                content="Guidance",
                message_type=MessageType.GUIDANCE,
            )
        )

        spawner = AgentSpawnerProvider(
            agent_repo=agent_repo,
            conversation_repo=conv_repo,
            llm_provider=AsyncMock(),
            event_bus=event_bus,
            tool_registry=ToolRegistry(),
            message_repo=msg_repo,
        )

        import json

        # All messages
        result = await spawner.call_tool(
            "receive_messages",
            {"agent_id": a2.id},
        )
        assert result.success
        msgs = json.loads(result.output)
        assert len(msgs) == 2

        # Filtered by type
        result = await spawner.call_tool(
            "receive_messages",
            {"agent_id": a2.id, "message_type": "guidance"},
        )
        msgs = json.loads(result.output)
        assert len(msgs) == 1
        assert msgs[0]["content"] == "Guidance"

        await agent_repo.close()
        await conv_repo.close()
        await msg_repo.close()

    @pytest.mark.asyncio
    async def test_st_v2_2_10_dismiss_agent(self, tmp_path):
        """ST-V2-2.10: dismiss_agent sets child to COMPLETED."""
        from agent_platform.core.models import Agent, AgentConfig, AgentStatus
        from agent_platform.db.sqlite_agent_repo import SqliteAgentRepo
        from agent_platform.db.sqlite_conversation_repo import (
            SqliteConversationRepo,
        )
        from agent_platform.db.sqlite_message_repo import SqliteMessageRepo
        from agent_platform.observation.in_process_event_bus import (
            InProcessEventBus,
        )
        from agent_platform.tools.agent_spawner import AgentSpawnerProvider
        from agent_platform.tools.registry import ToolRegistry

        db = str(tmp_path / "test.db")
        agent_repo = SqliteAgentRepo(db)
        conv_repo = SqliteConversationRepo(db)
        msg_repo = SqliteMessageRepo(db)
        event_bus = InProcessEventBus()
        await agent_repo.initialize()
        await conv_repo.initialize()
        await msg_repo.initialize()

        parent = Agent(name="parent", config=AgentConfig(model="test"))
        child = Agent(
            name="child",
            config=AgentConfig(model="test"),
            parent_agent_id=parent.id,
        )
        await agent_repo.create(parent)
        await agent_repo.create(child)

        spawner = AgentSpawnerProvider(
            agent_repo=agent_repo,
            conversation_repo=conv_repo,
            llm_provider=AsyncMock(),
            event_bus=event_bus,
            tool_registry=ToolRegistry(),
            message_repo=msg_repo,
        )

        result = await spawner.call_tool(
            "dismiss_agent",
            {"child_agent_id": child.id, "agent_id": parent.id},
        )
        assert result.success

        updated = await agent_repo.get(child.id)
        assert updated is not None
        assert updated.status == AgentStatus.COMPLETED

        await agent_repo.close()
        await conv_repo.close()
        await msg_repo.close()

    @pytest.mark.asyncio
    async def test_st_v2_2_11_guidance_injection(self, tmp_path):
        """ST-V2-2.11: Runtime injects GUIDANCE messages."""
        from agent_platform.core.models import (
            Agent,
            AgentConfig,
            AgentMessage,
            MessageType,
        )
        from agent_platform.core.runtime import AgentRuntime
        from agent_platform.db.sqlite_agent_repo import SqliteAgentRepo
        from agent_platform.db.sqlite_conversation_repo import (
            SqliteConversationRepo,
        )
        from agent_platform.db.sqlite_message_repo import SqliteMessageRepo
        from agent_platform.llm.models import LLMResponse
        from agent_platform.observation.in_process_event_bus import (
            InProcessEventBus,
        )

        db = str(tmp_path / "test.db")
        agent_repo = SqliteAgentRepo(db)
        conv_repo = SqliteConversationRepo(db)
        msg_repo = SqliteMessageRepo(db)
        event_bus = InProcessEventBus()
        await agent_repo.initialize()
        await conv_repo.initialize()
        await msg_repo.initialize()

        agent = Agent(
            name="guided",
            config=AgentConfig(model="test"),
            parent_agent_id="some-parent",
        )
        await agent_repo.create(agent)

        # Pre-populate a GUIDANCE message
        await msg_repo.create(
            AgentMessage(
                from_agent_id="some-parent",
                to_agent_id=agent.id,
                content="Change approach: use recursion",
                message_type=MessageType.GUIDANCE,
            )
        )

        mock_llm = AsyncMock()
        mock_llm.complete.return_value = LLMResponse(
            content="Understood, switching to recursion.",
            usage={},
        )

        runtime = AgentRuntime(
            agent_repo=agent_repo,
            conversation_repo=conv_repo,
            llm_provider=mock_llm,
            event_bus=event_bus,
            message_repo=msg_repo,
        )

        await runtime.run(agent.id, "Continue working")

        # Check that the LLM was called with guidance injected
        call_args = mock_llm.complete.call_args
        messages = call_args[0][0]  # first positional arg
        # Should have a system message with the guidance content
        guidance_found = any(
            "Change approach: use recursion" in str(m.content) for m in messages
        )
        assert guidance_found

        await agent_repo.close()
        await conv_repo.close()
        await msg_repo.close()

    @pytest.mark.asyncio
    async def test_st_v2_2_12_message_api_get(self, tmp_path):
        """ST-V2-2.12: Message API GET endpoint."""
        import httpx

        from agent_platform.api.main import create_app
        from agent_platform.core.config import Settings

        settings = Settings(
            openrouter_api_key="sk-test",  # type: ignore[arg-type]
        )
        app = create_app(settings, db_dir=str(tmp_path))

        async with app.router.lifespan_context(app):
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(
                transport=transport, base_url="http://test"
            ) as client:
                # Create agent
                resp = await client.post(
                    "/agents",
                    json={"name": "msg-test", "config": {"model": "test"}},
                )
                agent_id = resp.json()["id"]

                # Send a message via API
                await client.post(
                    f"/agents/{agent_id}/messages",
                    json={
                        "content": "Hello agent",
                        "message_type": "guidance",
                    },
                )

                # GET messages
                resp = await client.get(f"/agents/{agent_id}/messages")
                assert resp.status_code == 200
                msgs = resp.json()
                assert len(msgs) >= 1
                assert msgs[0]["content"] == "Hello agent"

    @pytest.mark.asyncio
    async def test_st_v2_2_13_message_api_post(self, tmp_path):
        """ST-V2-2.13: Message API POST endpoint."""
        import httpx

        from agent_platform.api.main import create_app
        from agent_platform.core.config import Settings

        settings = Settings(
            openrouter_api_key="sk-test",  # type: ignore[arg-type]
        )
        app = create_app(settings, db_dir=str(tmp_path))

        async with app.router.lifespan_context(app):
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(
                transport=transport, base_url="http://test"
            ) as client:
                resp = await client.post(
                    "/agents",
                    json={"name": "post-test", "config": {"model": "test"}},
                )
                agent_id = resp.json()["id"]

                resp = await client.post(
                    f"/agents/{agent_id}/messages",
                    json={
                        "content": "New task for you",
                        "message_type": "task",
                    },
                )
                assert resp.status_code == 201
                msg = resp.json()
                assert msg["content"] == "New task for you"
                assert msg["message_type"] == "task"
                assert msg["to_agent_id"] == agent_id

    @pytest.mark.asyncio
    async def test_st_v2_2_14_reusable_lifecycle(self, tmp_path):
        """ST-V2-2.14: Reusable lifecycle — send TASK to idle child."""
        import httpx

        from agent_platform.api.main import create_app
        from agent_platform.core.config import Settings

        settings = Settings(
            openrouter_api_key="sk-test",  # type: ignore[arg-type]
        )
        app = create_app(settings, db_dir=str(tmp_path))

        async with app.router.lifespan_context(app):
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(
                transport=transport, base_url="http://test"
            ) as client:
                # Create parent + child agents
                resp = await client.post(
                    "/agents",
                    json={"name": "reuse-parent", "config": {"model": "test"}},
                )
                parent_id = resp.json()["id"]

                resp = await client.post(
                    "/agents",
                    json={"name": "reuse-child", "config": {"model": "test"}},
                )
                child_id = resp.json()["id"]

                # Send TASK message to child
                resp = await client.post(
                    f"/agents/{child_id}/messages",
                    json={
                        "content": "Build feature X",
                        "message_type": "task",
                        "from_agent_id": parent_id,
                    },
                )
                assert resp.status_code == 201

                # Verify message is in child's inbox
                resp = await client.get(f"/agents/{child_id}/messages")
                msgs = resp.json()
                assert any(m["content"] == "Build feature X" for m in msgs)

                # Child can still receive prompts (conversation preserved)
                # This verifies the agent is reusable
                resp = await client.get(f"/agents/{child_id}")
                assert resp.status_code == 200
                assert resp.json()["status"] == "idle"
