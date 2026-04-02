"""OpenRouter embedding provider — real API calls for semantic embeddings.

Implements both the EmbeddingProvider protocol (async) and ChromaDB's
EmbeddingFunction interface (sync, called internally by ChromaDB).
"""

import logging
import time

import httpx

from agent_platform.observation.cost_tracker import _get_cost_per_million
from agent_platform.observation.events import Event, EventType
from agent_platform.observation.in_process_event_bus import InProcessEventBus

logger = logging.getLogger(__name__)

OPENROUTER_EMBEDDING_URL = "https://openrouter.ai/api/v1/embeddings"


class OpenRouterEmbeddingProvider:
    """Embedding provider backed by OpenRouter API.

    Uses a sync httpx.Client for ChromaDB's synchronous calls and
    an async httpx.AsyncClient for the async protocol methods.
    """

    def __init__(
        self,
        api_key: str,
        model: str = "openai/text-embedding-3-large",
        http_client: httpx.AsyncClient | None = None,
        event_bus: InProcessEventBus | None = None,
        agent_id: str = "system",
        timeout: float = 60.0,
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._async_client = http_client or httpx.AsyncClient(
            timeout=httpx.Timeout(timeout, connect=10.0)
        )
        self._sync_client = httpx.Client(timeout=httpx.Timeout(timeout, connect=10.0))
        self._event_bus = event_bus
        self._agent_id = agent_id
        self._dimensions: int | None = None
        self._headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

    def set_agent_id(self, agent_id: str) -> None:
        """Set the agent_id for event attribution."""
        self._agent_id = agent_id

    # ── Async protocol (EmbeddingProvider) ──────────────

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Embed a batch of texts (async)."""
        return await self._call_api_async(texts)

    async def embed_single(self, text: str) -> list[float]:
        """Embed a single query text (async)."""
        results = await self._call_api_async([text])
        return results[0]

    # ── ChromaDB EmbeddingFunction interface (sync) ─────

    def __call__(self, input: list[str]) -> list[list[float]]:
        """ChromaDB calls this synchronously for document embedding."""
        return self._call_api_sync(input)

    def embed_documents(self, input: list[str]) -> list[list[float]]:
        """ChromaDB 1.x: embed documents for storage."""
        return self._call_api_sync(input)

    def embed_query(self, input: list[str]) -> list[list[float]]:
        """ChromaDB 1.x: embed query texts for search (sync)."""
        return self._call_api_sync(input)

    @staticmethod
    def name() -> str:
        """ChromaDB EmbeddingFunction name."""
        return "openrouter_embedding_provider"

    # ── Sync implementation (for ChromaDB) ──────────────

    def _call_api_sync(self, texts: list[str]) -> list[list[float]]:
        """Call OpenRouter embedding API synchronously."""
        self._fire_event_sync(
            EventType.LLM_REQUEST,
            {
                "model": self._model,
                "text_count": len(texts),
                "total_chars": sum(len(t) for t in texts),
            },
        )

        from agent_platform.llm.retry import sync_retry

        start = time.monotonic()

        resp = sync_retry(
            lambda: self._sync_client.post(
                OPENROUTER_EMBEDDING_URL,
                json={"model": self._model, "input": texts},
                headers=self._headers,
            )
        )
        duration_ms = int((time.monotonic() - start) * 1000)

        if resp.status_code >= 400:
            error_detail = resp.text[:200]
            logger.error(
                "Embedding API error %d: %s",
                resp.status_code,
                error_detail,
            )
            self._fire_event_sync(
                EventType.ERROR,
                {"error": f"HTTP {resp.status_code}", "detail": error_detail},
                duration_ms=duration_ms,
            )
            resp.raise_for_status()

        data = resp.json()

        if "error" in data:
            error_msg = data["error"].get("message", str(data["error"]))
            raise RuntimeError(f"Embedding API error: {error_msg}")

        embeddings = self._parse_embeddings(data)
        usage = data.get("usage", {})

        prompt_tok = (usage.get("prompt_tokens", 0) or 0)
        in_rate, out_rate = _get_cost_per_million(self._model)
        cost = prompt_tok / 1_000_000 * in_rate

        self._fire_event_sync(
            EventType.LLM_RESPONSE,
            {
                "model": self._model,
                "text_count": len(texts),
                "dimensions": self._dimensions,
                "usage": usage,
                "cost_usd": round(cost, 6),
            },
            duration_ms=duration_ms,
        )
        return embeddings

    # ── Async implementation (for protocol) ─────────────

    async def _call_api_async(self, texts: list[str]) -> list[list[float]]:
        """Call OpenRouter embedding API asynchronously."""
        if self._event_bus:
            await self._event_bus.emit(
                Event(
                    agent_id=self._agent_id,
                    event_type=EventType.LLM_REQUEST,
                    module="embedding.openrouter",
                    payload={
                        "model": self._model,
                        "text_count": len(texts),
                        "total_chars": sum(len(t) for t in texts),
                    },
                )
            )

        from agent_platform.llm.retry import async_retry

        start = time.monotonic()

        resp = await async_retry(
            lambda: self._async_client.post(
                OPENROUTER_EMBEDDING_URL,
                json={"model": self._model, "input": texts},
                headers=self._headers,
            )
        )
        duration_ms = int((time.monotonic() - start) * 1000)

        if resp.status_code >= 400:
            error_detail = resp.text[:200]
            logger.error(
                "Embedding API error %d: %s",
                resp.status_code,
                error_detail,
            )
            if self._event_bus:
                await self._event_bus.emit(
                    Event(
                        agent_id=self._agent_id,
                        event_type=EventType.ERROR,
                        module="embedding.openrouter",
                        payload={
                            "error": f"HTTP {resp.status_code}",
                            "detail": error_detail,
                        },
                        duration_ms=duration_ms,
                    )
                )
            resp.raise_for_status()

        data = resp.json()

        if "error" in data:
            error_msg = data["error"].get("message", str(data["error"]))
            raise RuntimeError(f"Embedding API error: {error_msg}")

        embeddings = self._parse_embeddings(data)
        usage = data.get("usage", {})

        prompt_tok = (usage.get("prompt_tokens", 0) or 0)
        in_rate, _out_rate = _get_cost_per_million(self._model)
        cost = prompt_tok / 1_000_000 * in_rate

        if self._event_bus:
            await self._event_bus.emit(
                Event(
                    agent_id=self._agent_id,
                    event_type=EventType.LLM_RESPONSE,
                    module="embedding.openrouter",
                    payload={
                        "model": self._model,
                        "text_count": len(texts),
                        "dimensions": self._dimensions,
                        "usage": usage,
                        "cost_usd": round(cost, 6),
                    },
                    duration_ms=duration_ms,
                )
            )

        return embeddings

    # ── Shared helpers ──────────────────────────────────

    def _parse_embeddings(self, data: dict) -> list[list[float]]:
        """Parse OpenAI-format embedding response."""
        embeddings: list[list[float]] = []
        for item in sorted(data.get("data", []), key=lambda x: x["index"]):
            embeddings.append(item["embedding"])
        if embeddings and self._dimensions is None:
            self._dimensions = len(embeddings[0])
        return embeddings

    def _fire_event_sync(
        self,
        event_type: EventType,
        payload: dict,
        duration_ms: int | None = None,
    ) -> None:
        """Emit an event from a sync context.

        Schedules the async emit on the running event loop (if any).
        ChromaDB calls us synchronously from within FastAPI's async
        context, so there's always a running loop.
        """
        if not self._event_bus:
            return
        import asyncio

        event = Event(
            agent_id=self._agent_id,
            event_type=event_type,
            module="embedding.openrouter",
            payload=payload,
            duration_ms=duration_ms,
        )
        try:
            loop = asyncio.get_running_loop()
            loop.call_soon_threadsafe(
                lambda: asyncio.ensure_future(self._event_bus.emit(event))
            )
        except RuntimeError:
            # No running loop — skip event emission
            pass
