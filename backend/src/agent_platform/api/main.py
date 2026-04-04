"""FastAPI application factory."""

import asyncio
import logging
import os
from contextlib import asynccontextmanager
from functools import partial
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from agent_platform.api import _deps
from agent_platform.api.config_routes import router as config_router
from agent_platform.api.memory_routes import router as memory_router
from agent_platform.api.message_routes import router as message_router
from agent_platform.api.observation_routes import router as observation_router
from agent_platform.api.routes import router
from agent_platform.api.skill_routes import router as skill_router
from agent_platform.api.template_routes import router as template_router
from agent_platform.api.ws_routes import router as ws_router
from agent_platform.core.config import Settings
from agent_platform.core.platform_config import (
    load_platform_config,
    load_system_prompt,
    resolve_agent_config,
    resolve_system_prompt,
)
from agent_platform.core.runtime import AgentRuntime
from agent_platform.db.sqlite_agent_repo import SqliteAgentRepo
from agent_platform.db.sqlite_conversation_repo import SqliteConversationRepo
from agent_platform.db.sqlite_message_repo import SqliteMessageRepo
from agent_platform.llm.openrouter import OpenRouterProvider
from agent_platform.llm.openrouter_embeddings import OpenRouterEmbeddingProvider
from agent_platform.memory.chroma_memory_store import ChromaMemoryStore
from agent_platform.memory.context_manager import ContextManager
from agent_platform.memory.extractor import FactExtractor
from agent_platform.memory.memory_tools import MemoryToolProvider
from agent_platform.observation.in_process_event_bus import InProcessEventBus
from agent_platform.orchestration.tool_provider import OrchestrationToolProvider
from agent_platform.tools.agent_spawner import AgentSpawnerProvider
from agent_platform.tools.mcp_client import MCPClientProvider, MCPStdioClient
from agent_platform.tools.mcp_server_manager import MCPServerManager
from agent_platform.tools.registry import ToolRegistry
from agent_platform.tools.skill_provider import SkillProvider
from agent_platform.tools.template_provider import TemplateProvider

logger = logging.getLogger(__name__)

# Resolve project root (parent of backend/)
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent.parent


async def _shutdown(
    event_bus,
    mcp_provider,
    agent_repo,
    conv_repo,
    message_repo,
    *,
    has_mcp,
):
    """Shut down all resources. Called with a timeout wrapper."""
    await event_bus.close()
    if has_mcp:
        await mcp_provider.close_all()
    await agent_repo.close()
    await conv_repo.close()
    if message_repo:
        await message_repo.close()


def create_app(
    settings: Settings | None = None,
    db_dir: str | None = None,
    project_root: Path | None = None,
) -> FastAPI:
    """Create and configure the FastAPI application."""
    if settings is None:
        settings = Settings()

    if project_root is None:
        project_root = _PROJECT_ROOT

    # Load .env into os.environ (for MCP server env var resolution)
    env_file = project_root / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, _, value = line.partition("=")
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key not in os.environ:
                    os.environ[key] = value

    # Load platform config (lyra.config.json)
    platform_config = load_platform_config(project_root)

    # Resolve data directory
    if db_dir is None:
        data_dir_cfg = Path(platform_config.dataDir)
        if not data_dir_cfg.is_absolute():
            data_dir_cfg = project_root / data_dir_cfg
        db_dir = str(data_dir_cfg)
    os.makedirs(db_dir, exist_ok=True)

    # Single consolidated database
    db_path = os.path.join(db_dir, "lyra.db")

    event_bus = InProcessEventBus(db_path=db_path)
    agent_repo = SqliteAgentRepo(db_path)
    conv_repo = SqliteConversationRepo(db_path)
    message_repo = SqliteMessageRepo(db_path)

    # Configure retry defaults from platform config
    from agent_platform.llm.retry import configure as configure_retry

    retry_cfg = platform_config.retry
    configure_retry(
        max_retries=retry_cfg.max_retries,
        base_delay=retry_cfg.base_delay,
        max_delay=retry_cfg.max_delay,
    )

    llm_provider = OpenRouterProvider(
        api_key=settings.openrouter_api_key.get_secret_value(),
        event_bus=event_bus,
        timeout=retry_cfg.timeout,
        default_model=platform_config.defaultModel,
    )

    # Tool system
    tool_registry = ToolRegistry()

    # MCP servers from config
    mcp_provider = MCPClientProvider()
    for name, server_cfg in platform_config.mcpServers.items():
        from agent_platform.core.utils import resolve_env_vars

        resolved_env = resolve_env_vars(server_cfg.env)
        client = MCPStdioClient(
            server_name=name,
            command=server_cfg.command,
            args=server_cfg.args,
            env=resolved_env,
            request_timeout=platform_config.mcpRequestTimeout,
        )
        mcp_provider.add_client(client)

    if platform_config.mcpServers:
        tool_registry.register_provider(mcp_provider)

    # Memory system with real embeddings
    memory_dir = os.path.join(db_dir, "memory")
    os.makedirs(memory_dir, exist_ok=True)
    embedding_provider = OpenRouterEmbeddingProvider(
        api_key=settings.openrouter_api_key.get_secret_value(),
        model=platform_config.embeddingModel,
        event_bus=event_bus,
        timeout=retry_cfg.timeout,
    )
    gc_cfg = platform_config.memoryGC
    from agent_platform.memory.decay import TimeDecayStrategy

    decay_strategy = TimeDecayStrategy(
        half_life_days=gc_cfg.half_life_days,
        decay_weights=gc_cfg.decay_weights,
    )
    memory_store = ChromaMemoryStore(
        persist_dir=memory_dir,
        embedding_fn=embedding_provider,
        dedup_threshold=gc_cfg.dedup_threshold,
        decay_strategy=decay_strategy,
    )
    memory_provider = MemoryToolProvider(memory_store=memory_store, event_bus=event_bus)
    tool_registry.register_provider(memory_provider)

    # Skills
    skills_dir_cfg = Path(platform_config.skillsDir)
    if not skills_dir_cfg.is_absolute():
        skills_dir_cfg = project_root / skills_dir_cfg
    eval_prompt = load_system_prompt("evaluate_skill", project_root)
    skill_provider = SkillProvider(
        skills_dir=str(skills_dir_cfg),
        llm_provider=llm_provider,
        agent_repo=agent_repo,
        embedding_provider=embedding_provider,
        eval_prompt=eval_prompt,
    )
    tool_registry.register_provider(skill_provider)

    # Template discovery
    template_provider = TemplateProvider(
        prompts_dir=str(project_root / platform_config.systemPromptsDir),
        embedding_provider=embedding_provider,
    )
    tool_registry.register_provider(template_provider)

    # MCP Server Manager (agent-managed servers)
    mcp_servers_dir_cfg = Path(platform_config.mcpServersDir)
    if not mcp_servers_dir_cfg.is_absolute():
        mcp_servers_dir_cfg = project_root / mcp_servers_dir_cfg
    mcp_server_manager = MCPServerManager(
        mcp_servers_dir=str(mcp_servers_dir_cfg),
        embedding_provider=embedding_provider,
        mcp_provider=mcp_provider,
    )
    tool_registry.register_provider(mcp_server_manager)

    # Load system prompts for summarization and extraction
    summary_prompt = load_system_prompt("summarize", project_root)
    extraction_prompt = load_system_prompt("extract_facts", project_root)

    context_manager = ContextManager(
        memory_store=memory_store,
        top_k=5,
        llm_provider=llm_provider,
        summary_model=platform_config.summaryModel,
        summary_prompt=summary_prompt,
        event_bus=event_bus,
    )

    extractor = FactExtractor(
        llm_provider=llm_provider,
        extraction_model=platform_config.extractionModel,
        memory_store=memory_store,
        event_bus=event_bus,
        system_prompt=extraction_prompt,
    )

    # System prompt resolver
    prompt_resolver = partial(
        resolve_system_prompt,
        prompts_dir=platform_config.systemPromptsDir,
        project_root=project_root,
    )

    config_resolver = partial(
        resolve_agent_config,
        prompts_dir=platform_config.systemPromptsDir,
        project_root=project_root,
    )

    # Agent spawner tools (sub-agent spawning)
    agent_spawner = AgentSpawnerProvider(
        agent_repo=agent_repo,
        conversation_repo=conv_repo,
        llm_provider=llm_provider,
        event_bus=event_bus,
        context_manager=context_manager,
        extractor=extractor,
        system_prompt_resolver=prompt_resolver,
        agent_config_resolver=config_resolver,
        tool_registry=tool_registry,
        message_repo=message_repo,
        max_spawn_depth=platform_config.maxSpawnDepth,
    )
    tool_registry.register_provider(agent_spawner)

    # Orchestration tools (decompose_task, orchestrate)
    decompose_prompt = load_system_prompt("decompose_task", project_root)
    synthesize_prompt = load_system_prompt("synthesize_results", project_root)
    orchestration_provider = OrchestrationToolProvider(
        llm_provider=llm_provider,
        tool_registry=tool_registry,
        agent_repo=agent_repo,
        conversation_repo=conv_repo,
        event_bus=event_bus,
        decompose_prompt=decompose_prompt,
        synthesize_prompt=synthesize_prompt,
        agent_spawner=agent_spawner,
        orchestration_temperature=platform_config.orchestrationTemperature,
    )
    tool_registry.register_provider(orchestration_provider)

    # Capability tools (analyze, reflect, analytics, patterns)
    # Knowledge base
    from agent_platform.knowledge.store import KnowledgeStore
    from agent_platform.knowledge.tools import KnowledgeToolProvider

    kb_dir_cfg = Path(platform_config.knowledgeDir)
    if not kb_dir_cfg.is_absolute():
        kb_dir_cfg = project_root / kb_dir_cfg
    knowledge_store = KnowledgeStore(
        persist_dir=os.path.join(db_dir, "knowledge_index"),
        embedding_fn=embedding_provider,
    )
    knowledge_provider = KnowledgeToolProvider(
        knowledge_store=knowledge_store,
    )
    tool_registry.register_provider(knowledge_provider)

    # Unified discovery
    from agent_platform.tools.discovery_provider import DiscoveryProvider

    discovery_provider = DiscoveryProvider(
        skill_provider=skill_provider,
        template_provider=template_provider,
        mcp_server_manager=mcp_server_manager,
        knowledge_store=knowledge_store,
        memory_store=memory_store,
        embedding_provider=embedding_provider,
    )
    tool_registry.register_provider(discovery_provider)

    # Capability tools
    from agent_platform.tools.capability_tools import (
        CapabilityToolProvider,
    )

    reflect_prompt = load_system_prompt("reflect", project_root)
    capability_provider = CapabilityToolProvider(
        llm_provider=llm_provider,
        event_bus=event_bus,
        reflect_prompt=reflect_prompt,
        agent_repo=agent_repo,
        discovery_provider=discovery_provider,
    )
    tool_registry.register_provider(capability_provider)

    runtime = AgentRuntime(
        agent_repo=agent_repo,
        conversation_repo=conv_repo,
        llm_provider=llm_provider,
        event_bus=event_bus,
        tool_registry=tool_registry,
        context_manager=context_manager,
        extractor=extractor,
        message_repo=message_repo,
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # Startup
        await event_bus.initialize()
        await agent_repo.initialize()
        await conv_repo.initialize()
        await message_repo.initialize()

        # Ingest knowledge base (after event bus is ready)
        if kb_dir_cfg.exists():
            knowledge_store.ingest_directory(kb_dir_cfg)
            logger.info(
                "Knowledge base: %d sources indexed",
                len(knowledge_store.get_sources()),
            )

        # Connect MCP servers
        if platform_config.mcpServers:
            logger.info("Connecting %d MCP servers...", len(platform_config.mcpServers))
            await mcp_provider.connect_all()

        # Connect agent-managed MCP servers
        connected = await mcp_server_manager.connect_deployed()
        if connected:
            logger.info(
                "Connected %d agent-managed MCP servers: %s", len(connected), connected
            )

        # Cleanup agents stuck from previous crash
        await runtime.cleanup_stuck_agents()

        # Configure cost tracking from config
        from agent_platform.observation.cost_tracker import (
            configure as configure_costs,
        )

        configure_costs(
            model_costs=platform_config.modelCosts,
            default_cost=platform_config.defaultModelCost,
        )

        _deps.configure(
            agent_repo,
            conv_repo,
            event_bus,
            runtime,
            skill_provider=skill_provider,
            template_provider=template_provider,
            mcp_server_manager=mcp_server_manager,
            tool_registry=tool_registry,
            system_prompt_resolver=prompt_resolver,
            agent_config_resolver=config_resolver,
            default_model=platform_config.defaultModel,
            platform_config=platform_config,
            project_root=project_root,
            memory_store=memory_store,
            message_repo=message_repo,
        )
        yield
        # Shutdown — disconnect agent-managed MCP servers
        await mcp_server_manager.disconnect_all()
        # Shutdown — cancel running child agents
        await agent_spawner.cancel_all_tasks()
        # Shutdown — with timeout to prevent hanging on reload
        logger.info("Shutting down...")
        try:
            await asyncio.wait_for(
                _shutdown(
                    event_bus,
                    mcp_provider,
                    agent_repo,
                    conv_repo,
                    message_repo,
                    has_mcp=bool(platform_config.mcpServers),
                ),
                timeout=10.0,
            )
        except TimeoutError:
            logger.warning("Shutdown timed out after 10s, forcing exit")

    app = FastAPI(title="Agent Platform", version="0.1.0", lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            o.strip() for o in settings.cors_origins.split(",") if o.strip()
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.state.event_bus = event_bus
    app.state.agent_repo = agent_repo
    app.state.conversation_repo = conv_repo
    app.state.runtime = runtime
    app.state.tool_registry = tool_registry

    app.include_router(router)
    app.include_router(skill_router)
    app.include_router(template_router)
    app.include_router(config_router)
    app.include_router(observation_router)
    app.include_router(memory_router)
    app.include_router(message_router)
    app.include_router(ws_router)

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    return app


app = create_app()
