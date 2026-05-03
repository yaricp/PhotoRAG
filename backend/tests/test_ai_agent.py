import pytest
from unittest.mock import MagicMock, patch
from langchain_core.messages import HumanMessage, AIMessage, ToolCall, SystemMessage
from src.graphs.ai_agent import app

@pytest.fixture
def mock_llm():
    with patch("src.graphs.ai_agent.llm_with_tools") as mock:
        yield mock

def test_agent_simple_response(mock_llm):
    # Mock LLM to return a simple text response (no tool calls)
    mock_llm.invoke.return_value = AIMessage(content="Hello! How can I help you?")
    
    config = {"configurable": {"thread_id": "1"}}
    inputs = {"messages": [HumanMessage(content="Hi")]}
    
    result = app.invoke(inputs, config)
    
    # Result messages: HumanMessage, AIMessage (System is internal to call_model)
    assert len(result["messages"]) >= 2
    assert result["messages"][-1].content == "Hello! How can I help you?"

def test_agent_tool_calling_logic(mock_llm):
    # 1. Mock LLM to call a tool
    tool_call = ToolCall(
        name="search_photos_semantic",
        args={"query": "cat", "k": 5},
        id="call_1"
    )
    mock_llm.invoke.side_effect = [
        AIMessage(content="", tool_calls=[tool_call]),
        AIMessage(content="I found a cat photo for you.")
    ]
    
    # 2. Mock the underlying service and SessionLocal
    with patch("src.graphs.tools.get_photos_by_vector") as mock_service, \
         patch("src.graphs.tools.SessionLocal"):
        
        mock_photo = MagicMock()
        mock_photo.id = 1
        mock_photo.file_path = "cat.jpg"
        mock_photo.description = "A cute cat"
        mock_service.return_value = [mock_photo]
        
        config = {"configurable": {"thread_id": "2"}}
        inputs = {"messages": [HumanMessage(content="Find me a cat")]}
        
        result = app.invoke(inputs, config)
        
        # Verify service was called
        mock_service.assert_called_once()
        # Verify final response
        assert result["messages"][-1].content == "I found a cat photo for you."
        # Verify history contains tool response
        tool_msgs = [m for m in result["messages"] if hasattr(m, "tool_call_id")]
        assert len(tool_msgs) == 1
        assert "A cute cat" in tool_msgs[0].content

def test_agent_history_retention(mock_llm):
    # Mock LLM responses for two consecutive turns
    mock_llm.invoke.side_effect = [
        AIMessage(content="Response 1"),
        AIMessage(content="Response 2")
    ]
    
    config = {"configurable": {"thread_id": "3"}}
    
    # First turn
    app.invoke({"messages": [HumanMessage(content="Turn 1")]}, config)
    # Second turn
    result = app.invoke({"messages": [HumanMessage(content="Turn 2")]}, config)
    
    # Verify that history contains Human1, AI1, Human2, AI2 (Total 4)
    assert len(result["messages"]) >= 4 
    assert result["messages"][-1].content == "Response 2"
    # Verify Human 1 is still there
    assert result["messages"][0].content == "Turn 1"
