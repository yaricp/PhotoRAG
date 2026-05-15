import json
from loguru import logger
from typing import Literal, List
from langchain_core.messages import SystemMessage, ToolMessage
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from langgraph.checkpoint.memory import MemorySaver

from src.ai.prompts import get_prompt
from src.graphs.state import AgentState
from src.graphs.tools import (
    get_categories,
    get_tags,
    get_cameras,
    get_geopositions,
    search_photos_semantic,
    search_photos_by_category_id,
    search_photos_metadata,
    get_photo_details,
    resize_photo,
    get_exif_data,
    describe_photo,
    recognize_text_in_photos,
    get_action_history,
    undo_last_action,
    create_folder,
    move_photos,
    archive_photos,
    # Group A — garbage / quality
    get_garbage_photos,
    get_garbage_total_size,
    estimate_photo_quality_quick,
    estimate_photo_quality_deep,
    get_photo_visual_metrics,
    # Group B — duplicate comparison
    compare_photos_quick,
    compare_photos_deep,
    # Group C — annotation
    add_tag_to_photos,
    add_category_to_photos,
    add_geoposition_to_photos,
    geocode_photo_from_exif,
    mark_photos_as_duplicates,
    # Group D — search / filter
    get_photos_by_tag_id,
    search_photos_by_exif,
    filter_photos,
)
from src.schemas import Photo


# 1. Initialize Tools
tools = [
    # Lookup helpers
    get_categories,
    get_tags,
    get_cameras,
    get_geopositions,
    # Photo search / retrieval
    search_photos_semantic,
    search_photos_by_category_id,
    search_photos_metadata,
    get_photo_details,
    get_exif_data,
    describe_photo,
    recognize_text_in_photos,
    filter_photos,
    get_photos_by_tag_id,
    search_photos_by_exif,
    # Garbage / quality
    get_garbage_photos,
    get_garbage_total_size,
    estimate_photo_quality_quick,
    estimate_photo_quality_deep,
    get_photo_visual_metrics,
    # Duplicate comparison
    compare_photos_quick,
    compare_photos_deep,
    # Annotation (write)
    add_tag_to_photos,
    add_category_to_photos,
    add_geoposition_to_photos,
    geocode_photo_from_exif,
    mark_photos_as_duplicates,
    # File operations (write)
    create_folder,
    move_photos,
    archive_photos,
    # History
    get_action_history,
    undo_last_action,
]
editing_tools = [
    resize_photo,
]

tool_node = ToolNode(tools)
editing_tool_node = ToolNode(editing_tools)


# 3. Define Nodes
def call_model(state: AgentState):
    """Call the LLM with the current state."""
    logger.info(f"[ai_agent] state: {state}")
    messages = state["messages"]

    if not any(isinstance(m, SystemMessage) for m in messages):
        system_msg = SystemMessage(content=get_prompt("chat_agent.system_message"))
        messages = [system_msg] + messages

    from src.ai.registry import registry as _registry  # local import avoids LangGraph closure introspection
    llm_with_tools = _registry.chat_model.bind_tools(tools)
    response = llm_with_tools.invoke(messages)
    # logger.info(f"[ai_agent] response: {response}")
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