import pytest
from unittest.mock import patch, MagicMock
from uuid import uuid4
from app.mcp.server import create_run, get_run_status, decide_finding

@patch("app.mcp.server.get_services")
def test_mcp_create_run(mock_get_services):
    db = MagicMock()
    run_service = MagicMock()
    doc_service = MagicMock()
    mock_get_services.return_value = (db, run_service, doc_service)
    
    mock_run = MagicMock()
    mock_run.id = uuid4()
    mock_run.name = "MCP Test Run"
    mock_run.status.value = "pending"
    mock_run.stage.value = "ingestion"
    run_service.create_run.return_value = mock_run
    
    res = create_run("MCP Test Run")
    assert res["name"] == "MCP Test Run"
    assert res["status"] == "pending"
    run_service.create_run.assert_called_once_with("MCP Test Run")
