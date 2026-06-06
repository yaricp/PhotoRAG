from typing import Annotated, List, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages

from src.schemas import Photo


def replace_photos(existing: List[Photo], new: List[Photo]) -> List[Photo]:
    """Use new photos when found; keep existing when this tool round found none."""
    return new if new else existing


class AgentState(TypedDict):
    messages: Annotated[List[BaseMessage], add_messages]
    photos: Annotated[List[Photo], replace_photos]
