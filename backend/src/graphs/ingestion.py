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
