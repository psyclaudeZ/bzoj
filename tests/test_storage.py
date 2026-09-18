import sqlite3

from bzoj import storage
from bzoj.judge import JudgeResult
from bzoj.problems import EXAMPLES, load_problem


def example():
    return load_problem(EXAMPLES / 'hello-world.json')


def test_persistence_and_snapshot():
    problem = example()
    source = "def hello_world(name): return 'hello ' + name"
    identity = storage.create_submission(problem, source)
    result = JudgeResult(status='Accepted', stdout='debug', stderr='warning', duration_ms=12,
                         cases=[{'number': 1, 'status': 'Accepted', 'hidden': False}])
    storage.finish_submission(identity, result)
    storage.initialize()  # Reopen/reinitialize without losing existing rows.
    problem.title = 'Changed title'
    record = storage.get_submission(identity)
    assert record['source'] == source
    assert record['problem'].title == 'Hello World'
    assert record['result']['stdout'] == 'debug'
    assert record['result']['stderr'] == 'warning'
    assert record['result']['cases'] == result.cases
    assert record['status'] == 'Accepted'
    assert record['duration_ms'] == 12
    assert record['created_at'].endswith('+00:00')
    with sqlite3.connect(storage.DB_PATH) as db:
        assert db.execute('PRAGMA user_version').fetchone()[0] == 1


def test_latest_is_submission_order_not_completion_order():
    problem = example()
    assert storage.latest_source(problem.slug) is None
    first = storage.create_submission(problem, 'older')
    second = storage.create_submission(problem, '')
    storage.finish_submission(second, JudgeResult(status='Runtime error'))
    storage.finish_submission(first, JudgeResult(status='Accepted'))
    assert storage.latest_source(problem.slug) == ''
    assert storage.latest_source('another-problem') is None
    assert [row['id'] for row in storage.list_submissions(problem.slug)] == [second, first]
    assert storage.get_submission(999) is None


def test_pagination_and_filtering():
    problem = example()
    for index in range(55):
        storage.create_submission(problem, str(index))
    other = load_problem(EXAMPLES / 'counter.json')
    storage.create_submission(other, 'other')
    page = storage.list_submissions(problem.slug)
    assert len(page) == 51
    older = storage.list_submissions(problem.slug, before=page[49]['id'])
    assert len(older) == 5
    assert not set(row['id'] for row in page[:50]) & set(row['id'] for row in older)
    assert len(storage.list_submissions(other.slug)) == 1


def test_definition_hash_tracks_execution():
    problem = example()
    original = storage.definition_hash(problem)
    problem.title = 'Renamed'
    assert storage.definition_hash(problem) == original
    problem.driver_code += '\n# revised driver'
    assert storage.definition_hash(problem) != original
    problem = example()
    problem.tests[0].expected = 'changed'
    assert storage.definition_hash(problem) != original
