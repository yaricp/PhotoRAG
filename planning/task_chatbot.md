# Phase 8: Conversational AI Agent (LangGraph + TDD)

**Goal:** Implement a chatbot capable of semantic search and metadata filtering with conversation history.

---

### Task 1: Tools Implementation (`src/graphs/tools.py`)
- [x] **Step 1**: Create `search_photos_semantic` tool (wraps `get_photos_by_vector`).
- [x] **Step 2**: Create `search_photos_metadata` tool (wraps `get_all_photos` filters).
- [x] **Step 3**: Create `get_photo_details` tool (wraps `get_photo_by_id`).
- [x] **Step 4**: Write unit tests in `tests/test_agent_tools.py`.

### Task 2: State & Persistence (`src/graphs/state.py`)
- [x] **Step 1**: Define `AgentState` with `messages`.
- [x] **Step 2**: Initialize `MemorySaver` for history.

### Task 3: Graph Construction (`src/graphs/ai_agent.py`)
- [x] **Step 1**: Define the ReAct graph (Model -> Tools -> Model).
- [x] **Step 2**: Bind tools to `gpt-4o-mini`.
- [x] **Step 3**: Implement System Prompt.
- [x] **Step 4**: Write logic tests in `tests/test_ai_agent.py`.

### Task 4: API Integration (`src/main.py`)
- [x] **Step 1**: Implement `POST /api/chat/`.
- [x] **Step 2**: Integrate `thread_id` for state persistence.
- [x] **Step 3**: Manual verification with search queries.

---

### TDD Requirements
- [x] All tools must have corresponding tests verifying data formatting.
- [x] The agent must be tested with mocked LLM outputs to verify tool-calling logic.
- [x] Integration tests should verify that history works (e.g., "Show me cats" followed by "What about dogs?").

### Task 5: Local LLM Support
- [x] **Step 1**: Update `ML_Settings` in `src/config.py` with chat mode and model settings.
- [x] **Step 2**: Implement `install_chat` in `src/install.py`.
- [x] **Step 3**: Integrate `chat_model` into `AIModelRegistry` in `src/ai/registry.py`.
- [x] **Step 4**: Refactor `src/graphs/ai_agent.py` to use `registry.chat_model`.
- [x] **Step 5**: Verify with local model download and execution.

---
**Status:** Completed 🟢 (2026-05-03)
**Summary:** Full agentic chat system implemented with hybrid support for OpenAI and Local LLMs. All tests passing.
