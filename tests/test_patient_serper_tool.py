"""
Tests for PatientSerperDevTool's retry classification
(change deterministic-enforcement-v1-9-1).
"""
import json
from unittest.mock import MagicMock, patch

import pytest
import requests

from utils.patient_serper_tool import MAX_RETRIES, PatientSerperDevTool


def _mock_response(status_code, body=b'{"organic": []}'):
    resp = MagicMock()
    resp.status_code = status_code
    resp.content = body
    resp.json.return_value = json.loads(body)
    if status_code >= 400:
        resp.raise_for_status.side_effect = requests.exceptions.HTTPError(response=resp)
    else:
        resp.raise_for_status.side_effect = None
    return resp


@pytest.fixture(autouse=True)
def _serper_api_key(monkeypatch):
    monkeypatch.setenv("SERPER_API_KEY", "test-key")


@pytest.fixture(autouse=True)
def _no_real_sleep():
    with patch("utils.patient_serper_tool.time.sleep") as mock_sleep:
        yield mock_sleep


def test_400_fails_fast_with_no_retry():
    tool = PatientSerperDevTool()
    with patch("requests.post", return_value=_mock_response(400, b'{"error": "bad request"}')) as mock_post:
        with pytest.raises(requests.exceptions.HTTPError):
            tool._make_api_request("AAPL stocks", "search")
        assert mock_post.call_count == 1


def test_401_fails_fast_with_no_retry():
    tool = PatientSerperDevTool()
    with patch("requests.post", return_value=_mock_response(401)) as mock_post:
        with pytest.raises(requests.exceptions.HTTPError):
            tool._make_api_request("AAPL stocks", "search")
        assert mock_post.call_count == 1


def test_429_retries_up_to_max_then_raises():
    tool = PatientSerperDevTool()
    with patch("requests.post", return_value=_mock_response(429)) as mock_post:
        with pytest.raises(requests.exceptions.HTTPError):
            tool._make_api_request("AAPL stocks", "search")
        assert mock_post.call_count == 1 + MAX_RETRIES


def test_503_succeeds_after_one_retry():
    tool = PatientSerperDevTool()
    responses = [_mock_response(503), _mock_response(200)]
    with patch("requests.post", side_effect=responses) as mock_post:
        result = tool._make_api_request("AAPL stocks", "search")
        assert result == {"organic": []}
        assert mock_post.call_count == 2


def test_connection_error_is_treated_as_retryable():
    tool = PatientSerperDevTool()
    with patch("requests.post", side_effect=requests.exceptions.ConnectionError("boom")) as mock_post:
        with pytest.raises(requests.exceptions.ConnectionError):
            tool._make_api_request("AAPL stocks", "search")
        assert mock_post.call_count == 1 + MAX_RETRIES
