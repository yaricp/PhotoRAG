import json
from loguru import logger
from typing import Literal, List
from langchain_core.messages import SystemMessage, ToolMessage
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from langgraph.checkpoint.memory import MemorySaver

from src.ai.registry import registry
from src.ai.prompts import PROMPTS
from src.graphs.state import AgentState
from src.graphs.tools import (
    get_categories,
    get_tags,
    get_cameras,
    get_geopositions,
    search_photos_semantic,
    search_photos_by_category_id,
    get_photo_details,
    resize_photo,
    get_exif_data,
    describe_photo

)
from src.schemas import Photo


# 1. Initialize Tools
tools = [
    get_categories,
    get_tags,
    get_cameras,
    get_geopositions,
    search_photos_semantic,
    search_photos_by_category_id,
    get_photo_details,
    get_exif_data,
    describe_photo
]
editing_tools = [
    resize_photo,
]

tool_node = ToolNode(tools)
editing_tool_node = ToolNode(editing_tools)

# 2. Initialize LLM
llm = registry.chat_model
llm_with_tools = llm.bind_tools(tools)


# 3. Define Nodes
def call_model(state: AgentState):
    """Call the LLM with the current state."""
    logger.info(f"[ai_agent] state: {state}")
    messages = state["messages"]

    if not any(isinstance(m, SystemMessage) for m in messages):
        system_msg = SystemMessage(content=PROMPTS["chat_agent"]["system_message"])
        messages = [system_msg] + messages

    response = llm_with_tools.invoke(messages)
    logger.info(f"[ai_agent] response: {response}")
    return {"messages": [response]}


def extract_photos(state: AgentState) -> dict:
    """
    Parse Photo objects from the most recent ToolMessages and write to state.
    Walks backwards through messages until it hits a non-ToolMessage.
    """
    extracted: List[Photo] = []

    for msg in reversed(state["messages"]):
        if not isinstance(msg, ToolMessage):
            break
        try:
            data = json.loads(msg.content)
            if isinstance(data, list):
                for item in data:
                    try:
                        extracted.append(Photo.model_validate(item))
                    except Exception as e:
                        logger.warning(f"[extract_photos] skipping item: {e}")
            elif isinstance(data, dict):
                try:
                    extracted.append(Photo.model_validate(data))
                except Exception as e:
                    logger.warning(f"[extract_photos] skipping dict: {e}")
        except (json.JSONDecodeError, TypeError):
            # Not JSON (e.g. plain text from get_categories) — skip
            pass

    logger.info(f"[extract_photos] extracted {len(extracted)} photo(s)")
    return {"photos": extracted}


def should_continue(state: AgentState) -> Literal["tools", END]:
    """Decide whether to call tools or finish."""
    last_message = state["messages"][-1]
    if last_message.tool_calls:
        logger.info("[ai_agent] should_continue → tools")
        return "tools"
    logger.info("[ai_agent] should_continue → END")
    return END


# 4. Build Graph
workflow = StateGraph(AgentState)

workflow.add_node("agent", call_model)
workflow.add_node("tools", tool_node)
workflow.add_node("extract_photos", extract_photos)

workflow.set_entry_point("agent")

workflow.add_conditional_edges("agent", should_continue)

# tools → extract_photos → agent (loop)
workflow.add_edge("tools", "extract_photos")
workflow.add_edge("extract_photos", "agent")

# 5. Compile with Persistence
checkpointer = MemorySaver()
app = workflow.compile(checkpointer=checkpointer)