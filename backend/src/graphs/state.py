from typing import Annotated, TypedDict, List, Union
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages

from src.schemas import Photo


class AgentState(TypedDict):
    # messages is a list of messages (Human, AI, Tool)
    # add_messages is a reducer that appends new messages to the list
    messages: Annotated[List[BaseMessage], add_messages]

