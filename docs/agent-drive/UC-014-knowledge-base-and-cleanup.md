# UC-014: Knowledge Base & Technical Cleanup Validation

## Purpose

Validate the RAG knowledge base (V4P2) and verify the technical cleanup fixes (V4P1) are working in production. Tests knowledge ingestion, semantic search, agent grounding in documented knowledge, correct model resolution (no minimax), and ToolType consistency.

## Preconditions

- Backend running at `http://localhost:8000` (restart after V4P2 merge)
- Knowledge base documents in `knowledge/` directory (6 LLM model reference docs)
- Clean DB recommended for clearer cost analysis

## Steps

### Step 1: Verify knowledge base loaded at startup

```
GET /tools
```

**Expected:** `search_knowledge` and `ingest_document` appear in the tool list.

Check backend logs for: `Knowledge base: N sources indexed`

### Step 2: Create agent and test knowledge search

```
POST /agents
{"name": "knowledge-tester"}
```

```
POST /agents/{id}/prompt
{"message": "Search the knowledge base for information about Claude Opus pricing and capabilities."}
```

**Expected:**
- Agent calls `search_knowledge(query="Claude Opus pricing capabilities")`
- Returns chunks from `anthropic-claude-models.md` with source attribution and heading path
- Agent presents the information with source reference

### Step 3: Cross-document knowledge search

```
POST /agents/{id}/prompt
{"message": "Search the knowledge base to find which models are cheapest for high-volume text processing tasks."}
```

**Expected:**
- Returns chunks from `model-comparison.md` and possibly `openai-gpt-models.md`
- Agent synthesizes an answer referencing the documents

### Step 4: Knowledge-grounded comparison

```
POST /agents/{id}/prompt
{"message": "Using the knowledge base, compare the context window sizes across all major model providers. Which has the largest?"}
```

**Expected:**
- Agent searches knowledge base
- Finds: Gemini 2M, Claude 200K-1M, GPT 128K, Llama 128K
- Answer is grounded in the documents, not hallucinated

### Step 5: Verify analyze_capabilities includes knowledge

```
POST /agents/{id}/prompt
{"message": "Use analyze_capabilities to check what we have for this task: recommend the best model for a multilingual chatbot application."}
```

**Expected:**
- `analyze_capabilities` report includes `relevant_knowledge` field
- Knowledge chunks about multilingual capabilities (Llama, Mistral) appear
- Assessment references the knowledge base findings

### Step 6: Ingest a new document at runtime

```
POST /agents/{id}/prompt
{"message": "Ingest the file /home/radek/Code/lyra-seed/docs/PROJECT_ASSESSMENT.md into the knowledge base."}
```

**Expected:**
- Agent calls `ingest_document(path="...")`
- Returns chunk count
- Document immediately searchable

### Step 7: Search the newly ingested document

```
POST /agents/{id}/prompt
{"message": "Search the knowledge base for information about what makes this platform cutting-edge or innovative."}
```

**Expected:**
- Returns chunks from `PROJECT_ASSESSMENT.md`
- Agent finds the "agentic RAG" and "self-evolving capability" concepts

### Step 8: Verify V4P1 fixes — no minimax model

Check all LLM calls use the correct model:

```
GET /agents/{id}/events
```

**Expected:**
- All `llm_request` events show `openai/gpt-5.4` (agent model) or `openai/gpt-5.4-mini` (extraction/orchestration model)
- NO calls to `minimax/minimax-m2.7`
- This validates the LLMConfig default fix from V4P1

### Step 9: Verify ToolType consistency

```
GET /tools
```

**Expected:**
- All tools have `tool_type: "internal"` or `tool_type: "mcp"`
- No tool has `tool_type: "prompt_macro"` (renamed in V4P1)

### Step 10: Full self-improvement workflow with knowledge

```
POST /agents/{id}/prompt
{"message": "I need to choose an LLM for our new customer support chatbot. It needs to be fast, cheap, multilingual, and good at function calling. Use analyze_capabilities to check what we know, search the knowledge base for model comparisons, then give me a recommendation with reasoning grounded in the documentation."}
```

**Expected:** Agent should:
1. `analyze_capabilities` or `search_knowledge` first
2. Find relevant model comparison data
3. Recommend a specific model with reasoning citing the knowledge base
4. Not hallucinate pricing or features — all from documented sources

### Step 11: Collect data

```
GET /agents/{id}/events
GET /agents/{id}/cost
```

## Success criteria

1. Knowledge base loaded at startup (6 sources indexed)
2. search_knowledge returns relevant chunks with source and heading
3. Cross-document search works (results from multiple files)
4. Agent grounds answers in knowledge base (cites sources)
5. analyze_capabilities includes relevant_knowledge
6. Runtime ingestion works (ingest_document)
7. Newly ingested documents immediately searchable
8. No minimax model calls (V4P1 LLMConfig fix confirmed)
9. All tools use ToolType "internal" or "mcp" (no "prompt_macro")
10. Agent produces knowledge-grounded recommendation

## What to report

- Knowledge base source count at startup
- Search results: which documents returned for each query
- Whether agent cited sources in its responses
- Model usage in events (confirm no minimax)
- Tool types in GET /tools response
- Runtime ingestion chunk count
- Cost breakdown
- Quality of knowledge-grounded recommendation
