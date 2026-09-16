import json
from unittest.mock import patch

import pytest

from bzoj.problems import EXAMPLES, ProblemError, catalog, load_problem


def test_samples():
    counter = load_problem(EXAMPLES / 'counter.json')
    single = load_problem(EXAMPLES / 'hello-world.json')
    assert len(counter.tests) == len(single.tests) == 2
    assert counter.tests[0].expected == [None, None, 7]
    assert 'run_case' in single.driver_code


@pytest.mark.parametrize('raw', ['{', '{}', '{"schema_version": 2}', '{"input": NaN}'])
def test_invalid_files(tmp_path, raw):
    path = tmp_path / 'bad.json'
    path.write_text(raw)
    with pytest.raises(ProblemError, match='bad.json'):
        load_problem(path)


def test_missing_file(tmp_path):
    with pytest.raises(ProblemError, match='missing.json'):
        load_problem(tmp_path / 'missing.json')


def test_duplicate_slug_is_rejected_and_edits_are_reloaded(tmp_path):
    raw = (EXAMPLES / 'counter.json').read_text()
    path = tmp_path / 'custom.json'
    path.write_text(raw)
    with patch('bzoj.problems.PRIVATE', tmp_path):
        problems, errors = catalog()
        assert 'counter' not in problems
        assert 'duplicate slug' in errors[0]
        data = json.loads(raw)
        data['slug'] = 'custom'
        path.write_text(json.dumps(data))
        problems, errors = catalog()
        assert 'custom' in problems
        assert not errors


def test_size_and_slug_validation(tmp_path):
    path = tmp_path / 'bad.json'
    path.write_bytes(b' ' * (1024 * 1024 + 1))
    with pytest.raises(ProblemError, match='1 MiB'):
        load_problem(path)
    data = json.loads((EXAMPLES / 'counter.json').read_text())
    data['slug'] = '../escape'
    path.write_text(json.dumps(data))
    with pytest.raises(ProblemError, match='slug'):
        load_problem(path)


def test_nonfinite_numbers_and_deep_json_fail_cleanly(tmp_path):
    path = tmp_path / 'bad.json'
    for raw in ('{"value": 1e9999}', '[' * 2000 + ']' * 2000):
        path.write_text(raw)
        with pytest.raises(ProblemError):
            load_problem(path)
