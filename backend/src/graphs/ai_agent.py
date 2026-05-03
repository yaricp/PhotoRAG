from langgraph.graph import StateGraph, END, START
from typing import TypedDict, List
from loguru import logger

from langchain.chat_models import init_chat_model
from langchain.agents import create_react_agent
from langchain.prompts import PromptTemplate


class AgentState(TypedDict):
    photo_id: int
    photo_path: str
    description: str
    tags: List[str]
    rating: int
    reviews: List[str]

llm = init_chat_model(
    model="gpt-4o-mini",
    temperature=0.5,
    model_kwargs={
        "image_input_type": "url",
    }
)

prompt = PromptTemplate(
    input_variables=["photo_path"],
    template="""You are an AI assistant that analyzes photos.
    
    Input:
    - photo_path: {photo_path}
    
    Output:
    - description: A detailed description of the photo.
    - tags: A list of tags describing the photo.
    - rating: A rating of the photo on a scale of 1-10.
    """
)