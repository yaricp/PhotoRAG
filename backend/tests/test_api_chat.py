import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, AsyncMock
from src.main import app
from src.schemas import ChatResponse
from langchain_core.messages import AIMessage

client = TestClient(app)

@pytest.mark.asyncio
async def test_chat_endpoint_success():
    """Test the POST /api/chat/ endpoint with a successful agent response"""
    
    # Mock the LangGraph agent's ainvoke method
    mock_response = {
        "messages": [
            AIMessage(content="I found 2 photos of money for you.")
        ]
    }
    
    with patch("src.main.agent_app.ainvoke", new_callable=AsyncMock) as mock_ainvoke:
        mock_ainvoke.return_value = mock_response
        
        chat_request = {
            "message": "Find photos about money",
            "thread_id": "test_thread_123"
        }
        
        response = client.post("/api/chat/", json=chat_request)
        
        assert response.status_code == 200
        data = response.json()
        assert data["response"] == "I found 2 photos of money for you."
        assert data["thread_id"] == "test_thread_123"
        
        # Verify agent was called with correct inputs
        mock_ainvoke.assert_called_once()
        args, kwargs = mock_ainvoke.call_args
        assert args[0]["messages"][0].content == "Find photos about money"
        assert args[1]["configurable"]["thread_id"] == "test_thread_123"

@pytest.mark.asyncio
async def test_chat_endpoint_persistence():
    """Test that chat endpoint passes the thread_id to the agent"""
    
    with patch("src.main.agent_app.ainvoke", new_callable=AsyncMock) as mock_ainvoke:
        mock_ainvoke.return_value = {"messages": [AIMessage(content="Hi")]}
        
        response = client.post("/api/chat/", json={
            "message": "Hello",
            "thread_id": "thread_abc"
        })
        
        assert response.status_code == 200
        assert response.json()["thread_id"] == "thread_abc"
        
        # In main.py: ainvoke(inputs, config)
        # So inputs is args[0], config is args[1]
        args, _ = mock_ainvoke.call_args
        assert args[1]["configurable"]["thread_id"] == "thread_abc"
