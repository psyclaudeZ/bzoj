from fastapi.testclient import TestClient

from bzoj.app import app

client = TestClient(app)


def test_home() -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "BZOJ" in response.text


def test_health() -> None:
    assert client.get("/health").json() == {"status": "ok"}
