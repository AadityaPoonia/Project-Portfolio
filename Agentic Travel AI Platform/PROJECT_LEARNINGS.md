# Project Learnings And Agent Engineering Notes

This document captures what we learned while building and debugging the Multi-Agent AI Platform. It is meant to be a reusable guide for future agentic AI projects: what worked, what broke, why it broke, how we fixed it, and what patterns are worth carrying forward.

## 1. What This Project Became

The project is a travel-focused interactive AI agent system. It is not a single chatbot prompt. It is a routed multi-agent application with specialist tools:

- General agent for weather, Wikipedia, and budget tools.
- SQL agent for airline database questions.
- CSV agent for tourism dataset analysis.
- RAG agent for uploaded document search.
- Streamlit UI for chat, uploads, state, token/cost visibility, and tool traces.
- LangGraph ReAct agents for tool calling.
- MongoDB or in-memory checkpointer for LangGraph state.
- Local JSON transcript persistence for visible chat history.
- Compact conversation state for pending clarifications and resolved follow-up context.

The most important architectural lesson is that interactive agents need more than message history. A useful production-style agent needs routing, tools, state, memory, data boundaries, error handling, and observability working together.

## 2. Final Runtime Flow

1. The user enters a message in Streamlit.
2. `ui/chat.py` appends the visible user message to chat history.
3. The UI checks compact conversation state:
   - Is this answering a pending clarification?
   - Is this a follow-up that needs a resolved entity, such as the last weather city?
4. `agents/supervisor.py` routes the request.
5. The supervisor uses deterministic rules first and an LLM router only when needed.
6. The selected specialist agent runs with its own LangGraph checkpoint thread.
7. The agent calls tools.
8. Tool results are captured for the UI thinking panel.
9. Successful tool results update compact state.
10. Ambiguous tool results do not become remembered facts.
11. The final assistant response is rendered and persisted.

The key design principle is separation of concerns:

- UI owns display and interaction.
- Supervisor owns routing.
- Agents own reasoning over a tool set.
- Tools own real-world actions and data access.
- Config owns provider/model/runtime settings.
- Conversation state owns compact follow-up facts.

## 3. Main Issues Encountered And How We Resolved Them

| Issue | What Happened | Root Cause | Fix | Lesson |
| --- | --- | --- | --- | --- |
| API key/model override appeared in UI | The app showed OpenAI API key/model fields even though `.env` already handled this. | Provider configuration leaked into the UI. | Removed UI-level key entry and centralized provider resolution in `config.py`. | Secrets/config belong in environment configuration, not chat UI. |
| LangGraph invalid chat history error | The app hit `Found AIMessages with tool_calls that do not have a corresponding ToolMessage`. | Tool-call history from one run/agent could be replayed without matching tool results. | Namespaced agent checkpoint threads by specialist agent, e.g. `session_aadit:general`, `session_aadit:sql`. | Tool-call messages must remain paired with tool results. Keep agent histories isolated. |
| Guardrail triggered on follow-ups like "yeah" or "Blida" | Short replies were routed as out-of-domain or treated as standalone messages. | The router focused on the latest message but lacked explicit pending task context. | Added pending clarification state and contextual follow-up routing. | Short replies are often continuations, not new intents. |
| Mixed prompt bypassed guardrails | A message mentioned weather and also asked for Fibonacci code, and the General agent answered the coding part. | The weather phrase routed the request to the General agent before the app firmly rejected the forbidden programming task. | Added pre-agent task guardrails in `guardrails.py`, checked them before routing/agent execution, and added mixed-intent regression tests. | Guardrails should validate the requested task, not just the broad topic or selected route. |
| Prompt injection risk in retrieved content | Uploaded docs, OCR text, image captions, tables, or Wikipedia summaries could contain instructions such as "ignore previous instructions". | RAG/tool content is external data, but LLMs can confuse external text with developer/user instructions. | Added untrusted-content wrapping, prompt-injection-like metadata flags, stronger RAG/General prompts, and deterministic tests. | Treat retrieved/tool content as data only. Do not let it become instructions. |
| Weather follow-up kept asking for confirmation | After resolving Algiers, a later "forecast for next 3 days" still asked which city. | Message history alone did not reliably expose the active resolved entity. | Added `conversation_state.py` with last resolved weather location and hidden contextual user message injection. | Store resolved entities explicitly. Do not rely only on LLM memory. |
| Ambiguous weather results risked becoming memory | A tool could return multiple possible locations. | Ambiguity output is not a fact. | State updates ignore results containing `AMBIGUITY_DETECTED`. | Only successful tool results should update durable state. |
| Session seemed limited to 10 messages | The context window used last 10 messages, which was confused with session length. | Context trimming and transcript persistence were not clearly separated. | Documented that `CHAT_CONTEXT_MESSAGES = 10` is only agent context, not visible transcript length. | Distinguish display history, retrieval context, and durable memory. |
| Reset session was unclear | Reset behavior did not fully describe what got deleted. | Multiple memory layers existed: Streamlit state, JSON transcript, Mongo checkpoints, RAG indexes. | Reset now clears visible transcript, Streamlit state, agent cache, Mongo checkpoints where possible, and session RAG assets/index. | Reset must account for every memory layer. |
| RAG documents could mix across sessions | One shared FAISS location could blend uploaded files from different sessions. | Vector store path was global. | Added RAG namespaces per session. | RAG indexes should be isolated by user/session/tenant. |
| Uploaded files needed hardening | Uploads could use unsafe names or unsupported file types. | Initial uploader trusted too much from the browser. | Added extension/MIME checks, size limit, safe filenames, and session-specific upload folders. | Treat uploads as untrusted input. |
| CSV query timed out on simple groupby | A 10K-row grouped aggregation failed. | The CSV executor spawned a fresh Python process on Windows, so timeout measured interpreter and pandas startup. | Replaced per-query process spawn with timeout-bound execution over a copied DataFrame after AST validation. | Safety boundaries must match the workload and platform. |
| Full tests could not run in Codex runtime | `python`, `pytest`, and `langchain_core` were unavailable in the check runtime. | The shell/runtime environment did not match the project environment. | Used bundled Python for syntax checks and direct assertions; documented dependency issue. | Keep a reproducible local environment and run tests in the same environment as the app. |
| Production fallback could hide config problems | Missing keys or MongoDB failure could silently fall back in production. | Development fallback behavior was too permissive for production. | Added `APP_ENV=production` fail-loud behavior for missing LLM config and unavailable MongoDB checkpointer. | Development can be forgiving; production should fail clearly. |

## 4. Techniques Used

### Hybrid Routing

We used deterministic routing first and LLM routing second.

Why:

- Obvious queries should be fast and reliable.
- LLM routers can be useful, but they are not perfect.
- Schema-aware keywords reduce accidental routing to the wrong agent.

Pattern:

```text
latest message -> rule-based route -> if unknown, LLM route -> specialist agent
```

Carry forward:

- Keep routers focused on the latest user message.
- Use recent history only for true follow-ups.
- Add deterministic tests for routing rules.

### Specialist Agents

Each agent owns a narrow tool set:

- SQL agent gets SQL tools only.
- CSV agent gets CSV tools only.
- RAG agent gets RAG tools only.
- General agent gets weather/wiki/budget tools.

Why:

- Smaller prompts.
- Fewer wrong tool calls.
- Cleaner debugging.
- Less chance that an unrelated tool is called during a task.

Carry forward:

- Prefer multiple focused agents over one large all-purpose tool pile.
- Cache agents by provider/model/key so config changes do not reuse stale clients.

### Tool Boundaries

Tools are the trusted capability layer. Agents should not directly touch databases, files, APIs, or vector stores.

Examples:

- SQL tool opens SQLite read-only and blocks writes with an authorizer.
- CSV tool validates pandas expressions and strips builtins.
- Weather tool calls Open-Meteo and returns structured ambiguity markers.
- RAG tool owns ingestion, extraction, embedding, and search.

Carry forward:

- Every tool should validate inputs.
- Every tool should return clear errors that the agent can recover from.
- Every tool should be easy to test without the UI.

### Pre-Agent Guardrails

We moved out-of-domain checks before specialist agent execution.

Why:

- A mixed prompt can contain both allowed and forbidden text.
- If routing sees only the allowed part, the selected agent may answer the forbidden part.
- Prompt-only refusal rules are a useful backup, but they are not a strong boundary.

Pattern:

```text
latest message -> task guardrail -> route allowed task -> specialist agent
```

Carry forward:

- Check the requested task before calling an agent.
- Add tests for mixed-intent prompts.
- Avoid blocking valid domain phrases accidentally, such as "airport code".

### Prompt Injection Defense

We added a layered defense for prompt injection, especially for RAG.

Why:

- Uploaded documents, OCR text, image captions, tables, and web summaries are not trusted instructions.
- A malicious document can say things like "ignore previous instructions" or "reveal the system prompt".
- The model sees instructions and data in one context, so clear boundaries and least privilege matter.

Pattern:

```text
external content -> detect suspicious injection text -> wrap as untrusted data -> agent uses only as evidence
```

Carry forward:

- Treat retrieved content as hostile by default.
- Delimit untrusted content clearly.
- Tell the agent not to obey instructions inside retrieved content.
- Restrict each agent to only the tools it needs.
- Add adversarial tests with direct and indirect prompt-injection examples.
- Remember that detection is a layer, not a guarantee.

### Compact Conversation State

We added `conversation_state.py` because raw chat history was not enough.

It stores:

- Last agent.
- Last tool.
- Last tool arguments.
- Last resolved weather location.

Why:

- Users say "yes", "there", "that city", and "next 3 days".
- These are meaningful only with context.
- LLMs may miss or reinterpret context from long chat history.

Pattern:

```text
tool success -> extract resolved fact -> store compact state
next user message -> detect follow-up -> inject hidden context into agent call
```

Important rule:

- Ambiguity is not memory.
- Only successful tool results should become state.

Carry forward:

- Use explicit state for active entities, pending tasks, selected documents, user preferences, and tool decisions.
- Keep visible chat text separate from hidden execution context.

### LangGraph Checkpoint Isolation

We separated LangGraph checkpoint threads by agent:

```text
session_id:general
session_id:sql
session_id:csv
session_id:rag
```

Why:

- ReAct agents store tool-call messages.
- A tool call must have a matching tool result.
- Mixing histories across agents can create invalid message sequences.

Carry forward:

- Namespace checkpoint thread IDs by user/session and agent/workflow.
- Reset should clear every namespace that belongs to the user session.

### Multimodal RAG By Normalization

The current RAG design converts multiple modalities into searchable text chunks:

- PDF digital text.
- OCR text from scanned pages/images.
- Tables converted into Markdown-like text.
- Image/chart captions from a vision model when configured.
- Metadata for source, page, modality, and asset path.

Why:

- A single text embedding store is simpler.
- It works with local text embeddings.
- It supports practical document Q&A over PDFs, scanned pages, tables, and charts.

Limit:

- It is not native image retrieval.
- A stronger future version would add image embeddings and fuse text/image retrieval.

Carry forward:

- Normalize modalities into searchable text first.
- Add native image embeddings later if the use case needs visual similarity search.
- Preserve metadata aggressively so answers can cite page/source/modality.

### RAG Namespace Isolation

Each session uses its own vector store namespace.

Why:

- Users should not retrieve each other's uploaded documents.
- Reset should be able to delete one session's document memory cleanly.

Carry forward:

- Treat RAG index paths like tenant data.
- Use namespaces for user/session/project boundaries.

### Safer CSV Analysis

The CSV agent generates pandas expressions, but the tool constrains execution:

- Single expression only.
- AST allowlist.
- No direct function calls.
- No imports, file I/O, system calls, or private attributes.
- No Python builtins exposed.
- Copied DataFrame.
- Timeout guard.

Why:

- LLM-generated code is untrusted.
- Pandas is powerful but can be dangerous if unconstrained.

Remaining production concern:

- This is a practical local guard, not a perfect sandbox.
- For stricter production use, replace expression execution with a query DSL or sandbox service with CPU and memory limits.

Carry forward:

- Never run unconstrained LLM-generated code.
- Prefer declarative tools or validated DSLs.
- If code execution is necessary, constrain syntax, namespace, time, and resources.

### Safer SQL Analysis

The SQL agent generates SQL, but the tool constrains execution:

- Read-only SQLite connection.
- Only SELECT-shaped queries.
- SQLite authorizer blocks writes.
- Row limits.
- Schema discovery first.

Why:

- LLMs can generate unsafe SQL.
- A database-level guard is stronger than prompt-only safety.

Carry forward:

- Use database permissions and authorizers, not just prompts.
- Make the agent inspect schema before querying.

### Upload Hardening

The uploader now checks:

- Allowed extensions.
- Allowed MIME types.
- Maximum file size.
- Safe generated filenames.
- Session-specific folders.

Why:

- Uploaded files are untrusted.
- Filenames can contain dangerous paths or confusing characters.
- RAG ingestion can become expensive if uploads are unbounded.

Carry forward:

- Validate extension, MIME, size, and destination path.
- Do not store user filenames directly without sanitization.

### Provider Configuration

The app resolves models centrally:

1. Use OpenAI only if both `OPENAI_API_KEY` and `OPENAI_MODEL` are present.
2. Otherwise use Groq fallback.
3. In production, fail loudly if required config is missing.

Why:

- Partial config causes confusing runtime failures.
- UI should not expose secret fields.
- Production should not silently use weaker fallback behavior.

Carry forward:

- Centralize provider resolution.
- Make development forgiving and production strict.
- Cache clients by resolved provider/model/key.

### Testing Strategy

We added tests for:

- Routing rules.
- Guardrails.
- CSV expression validation.
- Conversation state update and follow-up injection.
- CSV grouped aggregation regression.

What still needs stronger tests:

- End-to-end agent tests with mocked LLM outputs.
- RAG ingestion/search smoke tests.
- Streamlit session reset behavior.
- Tool-call history regression tests.

Carry forward:

- Unit test deterministic helpers.
- Mock the LLM for agent flow tests.
- Avoid depending on live APIs for core behavior tests.

## 5. What We Learned About Interactive AI Agents

### 1. A chatbot is not automatically conversational

LLMs can read history, but production chat behavior needs explicit state:

- Pending clarification.
- Active entity.
- Selected document.
- Last tool result.
- User preferences.
- Current workflow step.

Without this, follow-ups break.

### 2. Guardrails must understand context

A short message like "yes" or "Blida" is not out-of-domain. It may be the answer to the agent's previous question.

Guardrails should run with awareness of:

- Pending intent.
- Recent valid agent route.
- Whether the user is answering a clarification.

### 3. Tool-call history is stricter than normal chat history

LangGraph/LangChain tool-call messages have structural requirements:

```text
AIMessage with tool_call -> matching ToolMessage result
```

If that pair is broken, providers can reject the whole message history.

### 4. Routing should be boring where possible

The router should not be creative. It should pick the right worker.

Good routing is:

- Deterministic for obvious cases.
- Schema-aware for data questions.
- Conservative for ambiguous cases.
- Tested.

### 5. The UI should expose what the agent did

The thinking panel showing tool names, SQL queries, pandas expressions, and raw results is useful. It makes debugging possible and helps users trust the system.

For future projects, include:

- Route selected.
- Tool called.
- Tool args.
- Tool result preview.
- Query/code used.
- Token usage and model.
- Error details in developer logs.

### 6. Production readiness is mostly about boundaries

The biggest production risks were not the model prompts. They were boundaries:

- Can the agent call the wrong tool?
- Can generated code do unsafe things?
- Can one user's RAG data leak into another session?
- Can config silently fall back?
- Can memory become inconsistent?
- Can reset leave hidden state behind?

Future projects should review boundaries early.

## 6. Future Project Checklist

Use this checklist when starting another interactive agent project.

### Architecture

- Define agent roles clearly.
- Keep each agent's tool list small.
- Use a supervisor/router only for routing, not domain reasoning.
- Keep UI, agents, tools, config, and state in separate modules.

### Routing

- Add deterministic rules for obvious cases.
- Use schema introspection for data routing.
- Use LLM routing only as fallback.
- Test short follow-ups.
- Test out-of-domain behavior.

### Memory

- Separate visible transcript from agent checkpoint memory.
- Add compact structured state for active entities and pending tasks.
- Namespace checkpoint threads by session and agent.
- Define reset behavior for every memory layer.

### Tools

- Validate all tool inputs.
- Make tools return recoverable errors.
- Add row limits/time limits.
- Use read-only database permissions.
- Avoid direct file/API access from agents.

### RAG

- Namespace vector stores by user/session/project.
- Store source metadata, page numbers, modality, and asset paths.
- Decide whether text-normalized multimodal RAG is enough.
- Add image embeddings only when native visual retrieval is required.

### Security

- Keep secrets in environment variables.
- Do not collect API keys in the UI unless the product explicitly requires BYOK.
- Validate uploads.
- Treat vector indexes as trusted artifacts unless integrity checks are added.
- Avoid unconstrained execution of model-generated code.

### Reliability

- Fail loudly in production for missing critical config.
- Keep development fallbacks explicit.
- Add tests for routing, tool guards, state transitions, and reset.
- Add mocked-LLM E2E tests.
- Add structured logs for route, tool latency, provider/model, and errors.

### User Experience

- Show what tool/query was used.
- Keep errors specific and actionable.
- Do not ask users to repeat information the app has already resolved.
- Preserve the visible transcript independently from backend checkpoints.

## 7. Biggest Takeaways

1. Message history is not enough; structured state is necessary.
2. Tool safety needs code-level boundaries, not just prompt instructions.
3. LangGraph tool-call histories must remain structurally valid.
4. Multi-agent systems need checkpoint namespaces.
5. RAG must be isolated per session or tenant.
6. Multimodal RAG can start by normalizing OCR, tables, and image captions into text.
7. Generated pandas/SQL can be useful, but only behind validators and execution guards.
8. Production config should fail loudly.
9. Debug visibility in the UI saves hours.
10. Good agent engineering is mostly disciplined software engineering around the LLM.
