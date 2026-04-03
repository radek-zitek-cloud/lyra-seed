# UC-003: Tool System Validation

## Purpose

Verify that the agent can discover and use the tool system end-to-end: MCP filesystem tools (read/write files), MCP shell tools (execute commands), and prompt macros (CRUD via API). Validates V1 Phase 3 deliverables.

## Preconditions

- Backend running at `http://localhost:8000`
- MCP servers configured in `lyra.config.json` (filesystem + shell)
- Work directory exists or is creatable: `/home/radek/Code/lyra-seed/work/test/`
- No specific DB state required

## Steps

### Step 1: Verify tool discovery

```
GET /tools
```

**Expected:**
- MCP tools from `filesystem` source (fast_read_file, fast_write_file, fast_list_directory, etc.)
- MCP tools from `shell` source (shell_execute)
- Core tools: remember, recall, forget, spawn_agent, orchestrate, etc.
- Each tool has: name, description, input_schema, tool_type, source

### Step 2: Create agent

```
POST /agents
{"name": "tool-tester"}
```

### Step 3: Test filesystem write

```
POST /agents/{id}/prompt
{"message": "Create a file at /home/radek/Code/lyra-seed/work/test/hello.txt with the content 'Hello from Lyra Agent Platform! Created by the tool system test.'"}
```

**Expected:**
- Agent calls `fast_write_file` (or similar filesystem tool)
- File is created on disk
- Event timeline shows TOOL_CALL and TOOL_RESULT events with tool_name and duration
- Agent reports success

### Step 4: Test filesystem read

```
POST /agents/{id}/prompt
{"message": "Read the file at /home/radek/Code/lyra-seed/work/test/hello.txt and tell me what it contains."}
```

**Expected:**
- Agent calls `fast_read_file`
- Response includes the file content written in Step 3
- TOOL_CALL/TOOL_RESULT events emitted

### Step 5: Test shell execution

```
POST /agents/{id}/prompt
{"message": "Run the command 'uname -a' using the shell tool and tell me what operating system this machine is running."}
```

**Expected:**
- Agent calls `shell_execute` with command `uname -a`
- Response includes the OS information from the command output
- TOOL_CALL/TOOL_RESULT events emitted

### Step 6: Test prompt macro CRUD

Create a prompt macro via API:

```
POST /macros
{
  "name": "summarize_text",
  "description": "Summarize the given text into a concise bullet list",
  "template": "Summarize the following text into 3-5 bullet points:\n\n{{text}}",
  "parameters": {
    "type": "object",
    "properties": {
      "text": {"type": "string", "description": "The text to summarize"}
    },
    "required": ["text"]
  }
}
```

Verify it appears in the tool list:
```
GET /tools
```

**Expected:** `summarize_text` appears as a `prompt_macro` tool.

### Step 7: Test prompt macro execution

```
POST /agents/{id}/prompt
{"message": "Use the summarize_text tool to summarize this text: 'The Lyra Agent Platform is an experimental multi-agent system where agents can spawn sub-agents, communicate via messages, use tools through MCP servers, store memories across sessions, and orchestrate complex tasks through decomposition and parallel execution. It features a web-based observation UI for monitoring agent execution in real-time.'"}
```

**Expected:**
- Agent calls the `summarize_text` macro
- Macro expands the template with the text and makes an LLM sub-call
- Agent returns the summarized bullet points
- TOOL_CALL/TOOL_RESULT events show the macro execution

### Step 8: Test tool call history

```
GET /tools/fast_write_file/calls
GET /tools/shell_execute/calls
```

**Expected:** Returns history of calls to each tool with timestamps, arguments, results.

### Step 9: Verify file on disk

```bash
cat /home/radek/Code/lyra-seed/work/test/hello.txt
```

**Expected:** File exists with the content from Step 3.

### Step 10: Cleanup

```
DELETE /macros/{macro_id}
```

Remove the test macro. Optionally delete the test file.

## Success criteria

1. Tool discovery returns all registered tools with correct metadata
2. Filesystem write creates a file on disk
3. Filesystem read returns the correct file content
4. Shell execution runs a command and returns output
5. Prompt macro CRUD works (create, list, execute, delete)
6. Prompt macro execution makes an LLM sub-call and returns results
7. Tool call history endpoint returns correct data
8. All tool interactions emit TOOL_CALL and TOOL_RESULT events with tool names and durations
9. Agent uses tools autonomously based on the prompt (no explicit tool name needed)

## What to report

- Tool discovery: count of tools by type and source
- Each tool call: tool name, arguments (summarized), result (summarized), duration
- Event timeline for each turn
- Whether the agent chose the correct tool autonomously
- Prompt macro: created ID, execution result
- File verification: content matches
- Cost breakdown
- Any tool call failures or unexpected behavior
