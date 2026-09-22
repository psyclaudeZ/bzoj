from unittest.mock import patch

from fastapi.testclient import TestClient
import pytest

from bzoj import storage
from bzoj.app import app, get_problem

client = TestClient(app, base_url='http://127.0.0.1:8000')
URL = '/problems/hello-world/test'


def test_samples_only_without_saving_submission():
    problem = get_problem('hello-world')
    storage.create_submission(problem, '# saved submission')
    source = 'def hello_world(name):\n    assert name == "world"\n    return "hello " + name'
    response = client.post(URL, data={'source': source})
    assert response.status_code == 200
    assert 'Samples passed' in response.text
    assert 'Sample 1 — Accepted' in response.text
    assert 'Sample 2' not in response.text
    assert 'submission-link' not in response.text
    assert 'assert name ==' in response.text
    assert storage.latest_source('hello-world') == '# saved submission'
    assert len(storage.list_submissions()) == 1


@pytest.mark.parametrize('source, expected', [
    ('def hello_world(name): return "wrong"', 'Wrong answer'),
    ('raise ValueError("oops")', 'Runtime error'),
    ('while True: pass', 'Time limit exceeded'),
])
def test_sample_failures_are_not_submissions(source, expected):
    with patch('bzoj.runner.TIMEOUT_SECONDS', 0.2):
        response = client.post(URL, data={'source': source})
    assert expected in response.text
    assert storage.list_submissions() == []


def test_sample_request_validation():
    assert client.post(URL, data={'source': 'pass'}, headers={'origin': 'https://example.com'}).status_code == 403
    assert client.post(URL, json={'source': 'pass'}).status_code == 415
    assert client.post(URL, data={'source': 'x' * 65537}).status_code == 413
    assert client.post(URL, data={'other': 'pass'}).status_code == 400
    assert storage.list_submissions() == []


def test_no_samples_and_judge_failure():
    problem = get_problem('hello-world')
    hidden_only = problem.model_copy(update={'tests': [case for case in problem.tests if case.hidden]})
    with patch('bzoj.app.get_problem', return_value=hidden_only), patch('bzoj.app.judge') as run:
        response = client.post(URL, data={'source': '# draft'})
        assert 'no sample inputs' in response.text
        assert '# draft' in response.text
        run.assert_not_called()
    with patch('bzoj.app.judge', side_effect=RuntimeError):
        response = client.post(URL, data={'source': '# draft'})
        assert response.status_code == 502
        assert 'Judge error' in response.text
    assert storage.list_submissions() == []
