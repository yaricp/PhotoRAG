from typing import TypedDict, List
from langgraph.graph import StateGraph, END
from src.metadata import get_exif_data
from src.database import SessionLocal
from src.db_service import create_photo_record, check_photo_hash_exists
from src.utils import generate_file_hash
from src.ai.ocr import extract_text_from_image
from src.ai.clip import ClipTagger
from src.ai.vision import QwenVisionGenerator
from src.config import ML_Settings

class IngestionState(TypedDict):
    filepath: str
    file_hash: str
    metadata: dict
    ocr_text: str
    keywords: List[str]
    description: str

def metadata_node(state: IngestionState):
    # Tier 1 Enrichment: EXIF & DB Registration
    filepath = state["filepath"]
    file_hash = generate_file_hash(filepath)
    exif = get_exif_data(filepath)
    
    db = SessionLocal()
    try:
        # Crucial: Create the record so subsequent nodes have a row to update
        create_photo_record(db, file_hash, filepath)
        # Update with EXIF (simplification: create_photo_record could handle this)
    finally:
        db.close()
        
    return {"file_hash": file_hash, "metadata": exif}

def ocr_node(state: IngestionState):
    text = extract_text_from_image(state["filepath"])
    # Database update normally happens here or in a final node
    return {"ocr_text": text}

def clip_node(state: IngestionState):
    tagger = ClipTagger()
    keywords = tagger.generate_keywords(state["filepath"])
    return {"keywords": keywords}

def vision_node(state: IngestionState):
    gen = QwenVisionGenerator(ML_Settings())
    desc = gen.describe_scene(state["filepath"])
    return {"description": desc}

def final_commit_node(state: IngestionState):
    # Final consolidated RDBM update
    db = SessionLocal()
    try:
        # Update record logic here
        pass
    finally:
        db.close()
    return state

workflow = StateGraph(IngestionState)
workflow.add_node("metadata", metadata_node)
workflow.add_node("ocr", ocr_node)
workflow.add_node("clip", clip_node)
workflow.add_node("vision", vision_node)
workflow.add_node("commit", final_commit_node)

workflow.set_entry_point("metadata")
workflow.add_edge("metadata", "ocr")
workflow.add_edge("metadata", "clip")
workflow.add_edge("metadata", "vision")

# For simplicity in this TDD cycle, we'll run them sequentially 
# but LangGraph allows branching
workflow.add_edge("ocr", "commit")
workflow.add_edge("clip", "commit")
workflow.add_edge("vision", "commit")
workflow.add_edge("commit", END)

ingest_workflow = workflow.compile()
