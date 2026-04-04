# Lyra Memory System

## Overview

The memory system gives agents persistent knowledge that spans conversations. It has three layers: context memory (within a conversation), cross-context memory (across conversations), and long-term memory (durable knowledge).

## How Memory Works

### Automatic Extraction

After each agent response, the platform automatically extracts noteworthy facts, decisions, preferences, and procedures. The extraction uses a separate LLM call (extraction model) with a specialized prompt. Agents don't need to explicitly remember routine information.

### Memory Injection

At the start of each agent turn, the platform searches memory for entries relevant to the current query. Matching memories are injected as a system message before the LLM call. Public memories from other agents are included and marked [shared].

### Context Summarization

When a conversation grows too long (exceeds max_context_tokens), older messages are summarized by the LLM and saved as episodic memories. A summary marker replaces the removed messages to preserve continuity.

### Memory Decay

Memories that are rarely accessed and have low importance gradually decay. The decay score is computed using a time-decay strategy with configurable half-life. Memories below the prune threshold are archived or deleted during garbage collection.

## Memory Types

| Type | Purpose | Default Visibility |
|------|---------|-------------------|
| fact | Objective information | public |
| preference | User preferences and style | private |
| decision | Decisions made during work | private |
| outcome | Results of actions | private |
| procedure | How-to steps, workflows | public |
| tool_knowledge | Tool capabilities and quirks | public |
| domain_knowledge | Domain-specific facts | public |
| episodic | Session summaries (auto-generated) | private |

## Memory Tools

### remember

Store a memory explicitly. Parameters:
- content (required): self-contained information
- memory_type: one of the types above (default: fact)
- importance: 0.0-1.0 (default: 0.5, higher resists decay)
- visibility: public, private, or team

### recall

Semantic search over memories. Parameters:
- query (required): natural language search query
- memory_type: filter to specific type
- top_k: number of results (default: 5)
- include_public: include other agents' public memories (default: true)

### forget

Delete a memory by its ID (obtained from recall results).

## Cross-Agent Memory Sharing

Memories with public visibility are accessible to all agents. When agent A stores a fact as public, agent B can find it via recall. This enables knowledge sharing across the agent network.

The memory_sharing config in agent JSON files controls default visibility per memory type.

## Storage

Memories are stored in ChromaDB with vector embeddings for semantic search. The embedding model (configurable) converts memory content to vectors. Cosine similarity is used for retrieval.

## Configuration

Key config fields:
- `memoryGC.prune_threshold`: decay score below which memories are pruned (default: 0.1)
- `memoryGC.max_entries`: max memories per agent (default: 500)
- `memoryGC.dedup_threshold`: similarity threshold to prevent duplicate memories (default: 0.9)
- `context.max_tokens`: max context window before compression (default: 100000)
- `context.memory_top_k`: memories injected per turn (default: 5)
- `auto_extract`: enable/disable automatic extraction (default: true)

## Patterns and Reflections

The capability tools store patterns and reflections as PROCEDURE memories:
- `store_pattern`: saves orchestration patterns with [PATTERN] prefix
- `reflect`: saves post-task retrospectives with [REFLECTION] prefix
- `find_pattern`: searches PROCEDURE memories for reusable approaches
