import os
from loguru import logger
from typing import Literal
from langchain_openai import ChatOpenAI
from langchain.chat_models import init_chat_model
from langchain_core.messages import SystemMessage
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
    get_photo_details
)


# 1. Initialize Tools
tools = [
    get_categories,
    get_tags,
    get_cameras,
    get_geopositions,
    search_photos_semantic,
    search_photos_by_category_id,
    get_photo_details
]
tool_node = ToolNode(tools)

# 2. Initialize LLM from Registry
llm = registry.chat_model
llm_with_tools = llm.bind_tools(tools)

# 3. Define Nodes
def call_model(state: AgentState):
    """Call the LLM with the current state"""
    logger.info(f"[ai_agent] state: {state}")
    messages = state["messages"]
    
    # Optional: Insert System Message if not present
    if not any(isinstance(m, SystemMessage) for m in messages):
        system_msg = SystemMessage(
            content=PROMPTS["chat_agent"]["system_message"]
        )
        messages = [system_msg] + messages
    
    response = llm_with_tools.invoke(messages)
    logger.info(f"[ai_agent] response: {response}")
    return { "messages": [response] }

def should_continue(state: AgentState) -> Literal["tools", END]:
    """Condition for graph to continue or end"""
    messages = state["messages"]
    last_message = messages[-1]
    logger.info(f"[ai_agent] should_continue: {last_message}")
    if last_message.tool_calls:
        logger.info("[ai_agent] should_continue: tools")
        return "tools"
    logger.info("[ai_agent] should_continue: END")
    return END

# 4. Construct Graph
workflow = StateGraph(AgentState)

workflow.add_node("agent", call_model)
workflow.add_node("tools", tool_node)

workflow.set_entry_point("agent")

workflow.add_conditional_edges(
    "agent",
    should_continue,
)

workflow.add_edge("tools", "agent")

# 5. Compile with Persistence
checkpointer = MemorySaver()
app = workflow.compile(checkpointer=checkpointer)