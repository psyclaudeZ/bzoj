import subprocess
import sys
from unittest.mock import patch

from fastapi.testclient import TestClient
import pytest

from bzoj.app import app
from bzoj import storage

client = TestClient(app, base_url='http://127.0.0.1:8000')
URL = '/problems/hello-world'
SOLUTION = "def hello_world(name):\n    return 'hello ' + name\n"


def test_editor_history_and_restart():
    assert 'def hello_world(name):' in client.get(URL).text
    response = client.post(URL + '/submit', data={'source': SOLUTION})
    assert response.status_code == 200
    records = storage.list_submissions('hello-world')
    identity = records[0]['id']
    assert records[0]['status'] == 'Accepted'
    history = client.get('/submissions?problem=hello-world')
    assert f'href="/submissions/{identity}"' in history.text
    detail = client.get(f'/submissions/{identity}')
    assert detail.status_code == 200
    assert 'hello &#39; + name' in detail.text
    assert 'hello Python' not in detail.text  # Hidden expected output stays private.
    assert 'def run_case' not in detail.text
    with TestClient(app, base_url='http://127.0.0.1:8000') as restarted:
        assert 'hello &#39; + name' in restarted.get(URL).text
    # Verify persisted source from another interpreter, not just another connection.
    output = subprocess.check_output([sys.executable, '-c',
        'from pathlib import Path; from bzoj import storage; import sys; '
        'storage.DB_PATH=Path(sys.argv[1]); print(storage.latest_source("hello-world"), end="")',
        str(storage.DB_PATH)], text=True)
    assert output == SOLUTION
    client.post(URL + '/submit', data={'source': ''})
    assert storage.latest_source('hello-world') == ''
    assert '>\n    pass\n</textarea>' not in client.get(URL).text
    assert 'class Counter:' in client.get('/problems/counter').text


@pytest.mark.parametrize('source', [
    'def hello_world(name): return "hello world"',
    'def hello_world(name): return "hello Python"',
])
def test_wrong_answer_counts_visible_and_hidden_passes(source):
    response = client.post(URL + '/submit', data={'source': source})
    assert 'Wrong answer (1/2)' in response.text
    identity = storage.list_submissions()[0]['id']
    assert 'Wrong answer (1/2)' in client.get(f'{URL}/history/{identity}').text
    assert 'Wrong answer (1/2)' in client.get(f'/submissions/{identity}').text
    samples = client.post(URL + '/test', data={'source': 'def hello_world(name): return "wrong"'})
    assert 'Wrong answer (0/1)' in samples.text


@pytest.mark.parametrize('source, status', [
    ("def hello_world(name): return 'wrong'", 'Wrong answer'),
    ("raise ValueError('oops')", 'Runtime error'),
    ('while True: pass', 'Time limit exceeded'),
])
def test_failed_submissions_are_saved(source, status):
    with patch('bzoj.runner.TIMEOUT_SECONDS', 0.2):
        response = client.post(URL + '/submit', data={'source': source})
    assert response.status_code == 200
    row = storage.list_submissions()[0]
    assert row['status'] == status
    assert storage.get_submission(row['id'])['source'] == source
    assert status in client.get(f'/submissions/{row["id"]}').text
    assert storage.latest_source('hello-world') == source


def test_history_survives_problem_removal_and_escapes_source(tmp_path):
    source = 'print("</pre><script>alert(1)</script>")'
    client.post(URL + '/submit', data={'source': source})
    record = storage.list_submissions()[0]
    with patch('bzoj.problems.EXAMPLES', tmp_path / 'missing'), patch('bzoj.problems.PRIVATE', tmp_path / 'missing'):
        detail = client.get(f'/submissions/{record["id"]}')
        assert detail.status_code == 200
        assert 'Hello World' in detail.text
        assert '<script>' not in detail.text
        assert '&lt;script&gt;' in detail.text
        assert client.get('/submissions?problem=hello-world').status_code == 200
    assert client.get('/submissions/9999').status_code == 404


def test_rejected_request_does_not_create_history():
    assert client.post(URL + '/submit', data={'source': SOLUTION}, headers={'origin': 'https://example.com'}).status_code == 403
    assert storage.list_submissions() == []
    assert 'No submissions yet.' in client.get('/submissions').text


def test_database_failure_preserves_editor_and_does_not_execute():
    import sqlite3
    with patch('bzoj.storage.create_submission', side_effect=sqlite3.OperationalError), patch('bzoj.app.judge') as run:
        response = client.post(URL + '/submit', data={'source': 'print(42)'})
    assert response.status_code == 503
    assert 'print(42)' in response.text
    assert 'Code was not run' in response.text
    run.assert_not_called()


def test_unexpected_judge_error_is_recorded():
    with patch('bzoj.app.judge', side_effect=RuntimeError):
        response = client.post(URL + '/submit', data={'source': SOLUTION})
    assert response.status_code == 502
    assert 'Judge error (0/2)' in response.text
    assert storage.list_submissions()[0]['status'] == 'Judge error'


@pytest.mark.parametrize('status', ['Runtime error', 'Time limit exceeded', 'Output limit exceeded', 'Judge error'])
def test_output_counts_for_all_failure_verdicts(status):
    from bzoj.app import get_problem
    from bzoj.judge import JudgeResult

    problem = get_problem('hello-world')
    problem.tests.append(problem.tests[-1])
    identity = storage.create_submission(problem, '# code')
    storage.finish_submission(identity, JudgeResult(status=status, cases=[
        {'number': 1, 'hidden': False, 'status': 'Accepted'},
        {'number': 2, 'hidden': True, 'status': status},
        {'number': 3, 'hidden': True, 'status': 'Not run'},
    ]))
    page = client.get(f'{URL}?submission={identity}')
    output = page.text.split('<section class="results"', 1)[1]
    assert f'{status} (1/3)' in output


def test_refresh_does_not_resubmit_and_problem_scope_is_checked():
    response = client.post(URL + '/submit', data={'source': SOLUTION}, follow_redirects=False)
    assert response.status_code == 303
    for _ in range(2):
        assert client.get(response.headers['location']).status_code == 200
    assert len(storage.list_submissions()) == 1
    identity = storage.list_submissions()[0]['id']
    assert client.get(f'/problems/counter?submission={identity}').status_code == 404


def test_history_panels_are_scoped_and_do_not_change_latest_source():
    client.post(URL + '/submit', data={'source': SOLUTION})
    first = storage.list_submissions()[0]['id']
    client.post(URL + '/submit', data={'source': '# newer draft'})
    page = client.get(URL)
    assert 'role="tab" aria-selected="true"' in page.text
    assert 'aria-controls="history-panel"' in page.text
    assert '/static/problem.js' in page.text
    panel = client.get(URL + '/history')
    assert panel.status_code == 200
    assert f'href="{URL}/history/{first}"' in panel.text
    assert '<html' not in panel.text
    detail = client.get(f'{URL}/history/{first}')
    assert detail.status_code == 200
    assert 'hello &#39; + name' in detail.text
    assert 'hello Python' not in detail.text
    assert storage.latest_source('hello-world') == '# newer draft'
    assert client.get(f'/problems/counter/history/{first}').status_code == 404
    assert client.get(URL + '/history/9999').status_code == 404
    assert 'No submissions yet.' in client.get('/problems/counter/history').text
