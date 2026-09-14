from unittest.mock import patch

from fastapi.testclient import TestClient
import pytest

from bzoj.app import app

client = TestClient(app, base_url="http://127.0.0.1:8000")
SUBMIT = "/problems/hello-world/submit"


def test_problem_list_and_editor() -> None:
    home = client.get("/")
    assert home.status_code == 200
    assert 'href="/problems/hello-world"' in home.text
    page = client.get("/problems/hello-world")
    assert page.status_code == 200
    assert 'name="source"' in page.text
    assert "print(&#34;hello world&#34;)" in page.text
    assert 'class="workspace"' in page.text
    assert client.get("/static/app.css").status_code == 200
    assert client.get("/health").json() == {"status": "ok"}
    assert client.get("/problems/missing").status_code == 404


def test_submission_runs_edited_code_and_preserves_it() -> None:
    source = "print(6 * 7)"
    response = client.post(SUBMIT, data={"source": source})
    assert response.status_code == 200
    assert 'class="success">Success' in response.text
    assert '>42\n</pre>' in response.text
    assert source in response.text
    assert "exit 0" in response.text


def test_source_and_output_are_escaped() -> None:
    source = 'print("</textarea><script>alert(1)</script>")'
    response = client.post(SUBMIT, data={"source": source})
    assert "<script>" not in response.text
    assert "&lt;script&gt;" in response.text
    assert response.text.count("</textarea>") == 1


@pytest.mark.parametrize("source, expected", [
    ("raise ValueError('broken')", "ValueError: broken"),
    ("while True: pass", "Time limit exceeded"),
    ("while True: print('x' * 8192)", "Output was truncated"),
    ("", "(no output)"),
])
def test_execution_feedback(source, expected) -> None:
    with patch("bzoj.runner.TIMEOUT_SECONDS", 0.5):
        response = client.post(SUBMIT, data={"source": source})
    assert response.status_code == 200
    assert expected in response.text


@pytest.mark.parametrize("headers", [
    {"origin": "https://example.com"},
    {"origin": "null"},
    {"sec-fetch-site": "cross-site"},
])
def test_cross_site_requests_cannot_execute(headers) -> None:
    with patch("bzoj.app.run_source") as run:
        assert client.post(SUBMIT, data={"source": "print(1)"}, headers=headers).status_code == 403
        run.assert_not_called()


def test_same_origin_submission() -> None:
    response = client.post(SUBMIT, data={"source": "print('ok')"}, headers={"origin": "http://127.0.0.1:8000"})
    assert response.status_code == 200


def test_invalid_host_and_oversized_source() -> None:
    assert client.get("/", headers={"host": "example.com"}).status_code == 400
    with patch("bzoj.app.run_source") as run:
        assert client.post(SUBMIT, data={"source": "x" * 65537}).status_code == 413
        assert client.post(SUBMIT, data={"source": "x" * 200000}).status_code == 413
        assert client.post(SUBMIT, data={"other": "print(1)"}).status_code == 400
        run.assert_not_called()


def test_private_files_are_not_served() -> None:
    for path in ("/local/bzoj.sqlite3", "/static/../app.py", "/static/%2e%2e/app.py"):
        assert client.get(path).status_code == 404
