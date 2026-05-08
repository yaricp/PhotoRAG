from typing import Annotated, TypedDict, List
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages

from src.schemas import Photo


def replace_photos(existing: List[Photo], new: List[Photo]) -> List[Photo]:
    """Replace photos entirely instead of accumulating across calls."""
    return new


class AgentState(TypedDict):
    messages: Annotated[List[BaseMessage], add_messages]
    photos: Annotated[List[Photo], replace_photos]