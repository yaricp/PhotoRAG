# Phase 3: Heavy AI Model Orchestrator

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Plumb the AI dependencies (LangChain/LangGraph) and define our model generation factories, the embedding module, and the LangGraph orchestrator routing framework for Tier 2 background jobs.

**Architecture:** We will set up a Factory Pattern (`factory.py`) to easily swap between natively loaded local models and API-driven endpoints. We will instantiate the HuggingFace Nomic Embedder bindings. Finally, we will build the `StateGraph` representing the step-by-step ingestion pipeline mapping.

**Tech Stack:** Python 3, LangChain, LangGraph, langchain-huggingface, pytest.

---

### Task 1: AI Dependencies & Factory Logic

**Files:**
- Modify: `backend/requirements.txt`
- Create: `backend/src/ai/__init__.py`
- Create: `backend/src/ai/factory.py`
- Create: `backend/tests/test_ai_factory.py`

- [ ] **Step 1: Write failing Factory generation test**
```python
# backend/tests/test_ai_factory.py
from src.ai.factory import ModelFactory
from src.config import Settings

def test_model_factory_identifies_local():
    factory = ModelFactory(Settings())
    assert factory.is_local_mode == True
```
- [ ] **Step 2: Run test to verify it fails**
- [ ] **Step 3: Implement Database logic**
```bash
# Add to requirements.txt: langchain, langgraph, langchain-huggingface
```
```python
# backend/src/ai/factory.py
from src.config import Settings

class ModelFactory:
    def __init__(self, settings: Settings):
        self.settings = settings
        # We determine local execution based on a pseudo-URL vs cloud URL
        self.is_local_mode = "localhost" in settings.DATABASE_URL or "API_KEY" not in self.settings.model_dump()
        
    def get_vision_model(self):
        # Stub for returning Qwen2 Binding
        pass
```
- [ ] **Step 4: Run test to pass**
- [ ] **Step 5: Commit**

### Task 2: Vector Embedding Implementation (Nomic)

**Files:**
- Create: `backend/src/ai/embedder.py`
- Test: `backend/tests/test_embedder.py`

- [ ] **Step 1: Write failing embedding dummy test**
```python
# backend/tests/test_embedder.py
from src.ai.embedder import PhotoEmbedder

def test_embedder_instantiation():
    embedder = PhotoEmbedder()
    assert embedder.model_name == "nomic-ai/nomic-embed-text-v1.5"
```
- [ ] **Step 2: Run test to verify it fails**
- [ ] **Step 3: Add dependencies and implement queue**
```python
# backend/src/ai/embedder.py
from src.config import Settings

class PhotoEmbedder:
    def __init__(self):
        self.settings = Settings()
        self.model_name = self.settings.PHOTO_EMBEDDER_MODEL
        
    def generate_embedding(self, text: str) -> list[float]:
        # Returns a dummy 768 vector representation for TDD testing until real weights are explicitly loaded
        return [0.0] * 768
```
- [ ] **Step 4: Run test to pass**
- [ ] **Step 5: Commit**

### Task 3: LangGraph Ingestion Pipeline

**Files:**
- Create: `backend/src/graphs/__init__.py`
- Create: `backend/src/graphs/ingestion.py`
- Test: `backend/tests/test_ingestion_graph.py`

- [ ] **Step 1: Write StateGraph compilation test**
```python
# backend/tests/test_ingestion_graph.py
from src.graphs.ingestion import ingest_workflow

def test_graph_is_compiled():
    # If the nodes were linked properly, it should be a CompiledGraph
    assert hasattr(ingest_workflow, "invoke")
```
- [ ] **Step 2: Run test to verify it fails**
- [ ] **Step 3: Implement LangGraph Pipeline Stub**
```python
# backend/src/graphs/ingestion.py
from typing import TypedDict
from langgraph.graph import StateGraph, END

class IngestionState(TypedDict):
    filepath: str
    vision_description: str
    keywords: list[str]
    ocr_text: str

def dummy_node(state: IngestionState):
    return state

workflow = StateGraph(IngestionState)
workflow.add_node("vision_analysis", dummy_node)
workflow.add_node("commit_to_db", dummy_node)

workflow.set_entry_point("vision_analysis")
workflow.add_edge("vision_analysis", "commit_to_db")
workflow.add_edge("commit_to_db", END)

ingest_workflow = workflow.compile()
```
- [ ] **Step 4: Run test to pass**
- [ ] **Step 5: Commit**
