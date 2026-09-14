from fastapi.testclient import TestClient

from bzoj.app import app
from bzoj.execution import ExecutionError
from unittest.mock import patch

client = TestClient(app)


def test_home() -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "BZOJ" in response.text


def test_health() -> None:
    assert client.get("/health").json() == {"status": "ok"}


def test_hello_world_form_executes_script() -> None:
    page = client.get("/")
    assert '<form action="/hello-world" method="post">' in page.text
    assert '<button type="submit">hello world</button>' in page.text
    response = client.post("/hello-world")
    assert response.status_code == 200
    assert '<p role="status">Success</p>' in response.text
    assert "<pre>hello world</pre>" in response.text


def test_execution_failure_is_rendered() -> None:
    with patch("bzoj.app.run_hello_world", side_effect=ExecutionError("Script timed out.")):
        response = client.post("/hello-world")
    assert response.status_code == 502
    assert 'role="alert">Script timed out.' in response.text
    assert "Success" not in response.text


def test_script_output_is_html_escaped() -> None:
    with patch("bzoj.app.run_hello_world", return_value="<script>alert(1)</script>"):
        response = client.post("/hello-world")
    assert "<script>" not in response.text
    assert "&lt;script&gt;" in response.text
