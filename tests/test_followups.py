import json

import pytest
from fastapi.testclient import TestClient

from bzoj import storage
from bzoj.app import app
from bzoj.judge import JudgeResult
from bzoj.problems import EXAMPLES, ProblemError, catalog, load_problem

client = TestClient(app, base_url='http://127.0.0.1:8000')


@pytest.fixture
def definitions(tmp_path, monkeypatch):
    base = json.loads((EXAMPLES / 'hello-world.json').read_text())
    monkeypatch.setattr('bzoj.problems.EXAMPLES', tmp_path)
    monkeypatch.setattr('bzoj.problems.PRIVATE', tmp_path / 'missing')

    def write(slug, number, parent=None):
        path = tmp_path / f'{slug}.json'
        path.write_text(json.dumps({**base, 'slug': slug, 'number': number, 'follow_up_of': parent}))
        return path

    write('parent', 1)
    write('child', 2, 'parent')
    return write


def test_followup_chain_and_invalid_references(definitions):
    definitions('grandchild', 3, 'child')
    assert list(catalog()[0]) == ['parent', 'child', 'grandchild']
    definitions('parent', 1, 'grandchild')
    problems, errors = catalog()
    assert not problems
    assert len(errors) == 3
    assert all('cycle' in error for error in errors)
    definitions('parent', 1, 'missing')
    assert not catalog()[0]
    assert all('missing parent' in error for error in catalog()[1])
    definitions('parent', 1, 'parent')
    assert not catalog()[0]


@pytest.mark.parametrize('parent', ['', '../parent', 1, True])
def test_invalid_parent_slug(definitions, parent):
    with pytest.raises(ProblemError, match='follow_up_of'):
        load_problem(definitions('child', 2, parent))


def test_import_is_latest_read_only_and_scoped(definitions):
    problems, _ = catalog()
    parent, child = problems['parent'], problems['child']
    storage.create_submission(parent, '# old')
    latest = storage.create_submission(parent, '# latest\nprint("</script>")')
    storage.finish_submission(latest, JudgeResult(status='Wrong answer'))
    child_id = storage.create_submission(child, '# child draft')
    response = client.get('/problems/child/parent-submission')
    assert response.status_code == 200
    assert response.json() == {'source': '# latest\nprint("</script>")'}
    assert response.headers['cache-control'] == 'no-store'
    assert len(storage.list_submissions()) == 3
    assert storage.latest_source('child') == '# child draft'
    assert 'id="import-parent"' in client.get('/problems/child').text
    assert 'id="import-parent" disabled' in client.get('/problems/parent').text
    assert client.get('/problems/parent/parent-submission').status_code == 404
    assert client.get('/problems/missing/parent-submission').status_code == 404
    storage.create_submission(parent, '')
    assert client.get('/problems/child/parent-submission').json() == {'source': ''}
    # Current metadata governs imports, including when viewing an old submission.
    definitions('child', 2)
    assert 'id="import-parent" disabled' in client.get(f'/problems/child?submission={child_id}').text
    assert client.get('/problems/child/parent-submission').status_code == 404


def test_missing_submission_and_database_failure(definitions, monkeypatch):
    response = client.get('/problems/child/parent-submission')
    assert response.status_code == 404
    assert 'No submissions' in response.json()['detail']

    def fail(slug):
        import sqlite3
        raise sqlite3.OperationalError('private database details')

    monkeypatch.setattr(storage, 'latest_source', fail)
    response = client.get('/problems/child/parent-submission')
    assert response.status_code == 503
    assert 'private database details' not in response.text
