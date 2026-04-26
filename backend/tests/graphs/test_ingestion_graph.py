from src.graphs.ingestion import ingest_workflow

def test_graph_is_compiled():
    assert hasattr(ingest_workflow, "invoke")
