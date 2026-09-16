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
    assert "def hello_world(name):" in page.text
    assert 'href="/problems/counter"' in home.text
    assert 'class="workspace"' in page.text
    assert client.get("/static/app.css").status_code == 200
    assert client.get("/health").json() == {"status": "ok"}
    assert client.get("/problems/missing").status_code == 404


def test_submission_runs_edited_code_and_preserves_it() -> None:
    source = "def hello_world(name):\n    print(6 * 7)\n    return 'hello ' + name"
    response = client.post(SUBMIT, data={"source": source})
    assert response.status_code == 200
    assert 'class="success">Accepted' in response.text
    assert '>42\n</pre>' in response.text
    assert "def hello_world(name):" in response.text
    assert "Test 2 · hidden — Accepted" in response.text


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
    with patch("bzoj.app.judge") as run:
        assert client.post(SUBMIT, data={"source": "print(1)"}, headers=headers).status_code == 403
        run.assert_not_called()


def test_same_origin_submission() -> None:
    response = client.post(SUBMIT, data={"source": "print('ok')"}, headers={"origin": "http://127.0.0.1:8000"})
    assert response.status_code == 200


def test_invalid_host_and_oversized_source() -> None:
    assert client.get("/", headers={"host": "example.com"}).status_code == 400
    with patch("bzoj.app.judge") as run:
        assert client.post(SUBMIT, data={"source": "x" * 65537}).status_code == 413
        assert client.post(SUBMIT, data={"source": "x" * 200000}).status_code == 413
        assert client.post(SUBMIT, data={"other": "print(1)"}).status_code == 400
        run.assert_not_called()


def test_private_files_are_not_served() -> None:
    for path in ("/local/bzoj.sqlite3", "/static/../app.py", "/static/%2e%2e/app.py"):
        assert client.get(path).status_code == 404


def test_counter_submission():
    source = '''class Counter:
    def __init__(self, initial): self.value = initial
    def increment(self): self.value += 1
    def get(self): return self.value
'''
    response = client.post('/problems/counter/submit', data={'source': source})
    assert response.status_code == 200
    assert 'class="success">Accepted' in response.text
    assert 'Actual: [null, null, 7]' in response.text
    assert '[-1, null, 0]' not in response.text


def test_json_problem_is_discovered_and_hidden_data_stays_private(tmp_path):
    import json
    from bzoj.problems import EXAMPLES
    data = json.loads((EXAMPLES / 'hello-world.json').read_text())
    data.update(number=20, slug='custom', title='Custom', statement='A **bold** statement <script>bad()</script>')
    data['tests'][1]['input']['name'] = 'SECRET_INPUT_782'
    data['tests'][1]['expected'] = 'SECRET_EXPECTED_413'
    (tmp_path / 'custom.json').write_text(json.dumps(data))
    with patch('bzoj.problems.PRIVATE', tmp_path):
        assert 'Custom' in client.get('/').text
        page = client.get('/problems/custom')
        assert '<strong>bold</strong>' in page.text
        assert '<script>' not in page.text
        result = client.post('/problems/custom/submit', data={
            'source': "def hello_world(name):\n    print(name)\n    return name",
        })
    for response in (page, result):
        assert 'SECRET_INPUT_782' not in response.text
        assert 'SECRET_EXPECTED_413' not in response.text
        assert 'def run_case' not in response.text


def test_invalid_problem_is_reported_without_breaking_list(tmp_path):
    (tmp_path / 'broken.json').write_text('{}')
    with patch('bzoj.problems.PRIVATE', tmp_path):
        response = client.get('/')
    assert response.status_code == 200
    assert 'broken.json' in response.text
    assert 'Hello World' in response.text


def test_home_uses_problem_numbers_in_numeric_order(tmp_path):
    import json
    from bzoj.problems import EXAMPLES
    data = json.loads((EXAMPLES / 'counter.json').read_text())
    for slug, number in [('first-file', 10), ('last-file', 2)]:
        (tmp_path / f'{slug}.json').write_text(json.dumps({**data, 'slug': slug, 'number': number}))
    with patch('bzoj.problems.EXAMPLES', tmp_path), patch('bzoj.problems.PRIVATE', tmp_path / 'empty'):
        response = client.get('/')
        assert response.status_code == 200
        assert response.text.index('href="/problems/last-file"') < response.text.index('href="/problems/first-file"')
        assert 'class="problem-number">2</span>' in response.text
        assert 'class="problem-number">10</span>' in response.text
        detail = client.get('/problems/first-file')
        assert '<h1 id="problem-title">10. Counter</h1>' in detail.text


def test_home_sort_controls_and_name_order(tmp_path):
    import json
    from bzoj.problems import EXAMPLES
    data = json.loads((EXAMPLES / 'counter.json').read_text())
    for slug, title, number in [('zulu', 'Zulu', 1), ('alpha-later', 'alpha', 10), ('alpha-first', 'Alpha', 2)]:
        (tmp_path / f'{slug}.json').write_text(json.dumps({**data, 'slug': slug, 'title': title, 'number': number}))
    with patch('bzoj.problems.EXAMPLES', tmp_path), patch('bzoj.problems.PRIVATE', tmp_path / 'empty'):
        for query, order, selected in [
            ('', ['zulu', 'alpha-first', 'alpha-later'], 'number'),
            ('?sort=number', ['zulu', 'alpha-first', 'alpha-later'], 'number'),
            ('?sort=name', ['alpha-first', 'alpha-later', 'zulu'], 'name'),
            ('?sort=invalid', ['zulu', 'alpha-first', 'alpha-later'], 'number'),
        ]:
            response = client.get('/' + query)
            assert response.status_code == 200
            positions = [response.text.index(f'href="/problems/{slug}"') for slug in order]
            assert positions == sorted(positions)
            assert f'href="/?sort={selected}" aria-current="true"' in response.text
            assert 'class="problem-number">10</span>' in response.text
