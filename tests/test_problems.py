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
        data['number'] = 20
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


@pytest.mark.parametrize('number', [0, -1, True, 1.5, '2', None])
def test_problem_number_must_be_positive_integer(tmp_path, number):
    data = json.loads((EXAMPLES / 'counter.json').read_text())
    data['number'] = number
    path = tmp_path / 'bad-number.json'
    path.write_text(json.dumps(data))
    with pytest.raises(ProblemError, match='number'):
        load_problem(path)


def test_problem_number_is_required(tmp_path):
    data = json.loads((EXAMPLES / 'counter.json').read_text())
    del data['number']
    path = tmp_path / 'missing-number.json'
    path.write_text(json.dumps(data))
    with pytest.raises(ProblemError, match='number'):
        load_problem(path)


def test_catalog_sorts_by_stable_number_and_rejects_collisions(tmp_path):
    data = json.loads((EXAMPLES / 'counter.json').read_text())
    bundled, private = tmp_path / 'examples', tmp_path / 'private'
    bundled.mkdir()
    private.mkdir()
    for directory, filename, slug, number in [
        (bundled, 'a.json', 'ten', 10),
        (bundled, 'z.json', 'thirty', 30),
        (private, 'middle.json', 'two', 2),
    ]:
        (directory / filename).write_text(json.dumps({**data, 'slug': slug, 'number': number}))
    with patch('bzoj.problems.EXAMPLES', bundled), patch('bzoj.problems.PRIVATE', private):
        problems, errors = catalog()
        assert not errors
        assert [p.number for p in problems.values()] == [2, 10, 30]
        (private / 'middle.json').rename(private / 'renamed.json')
        assert list(catalog()[0]) == ['two', 'ten', 'thirty']
        (private / 'collision.json').write_text(json.dumps({**data, 'slug': 'collision', 'number': 10}))
        problems, errors = catalog()
        assert list(problems) == ['two', 'thirty']
        assert len(errors) == 2
        assert all('duplicate number 10' in error for error in errors)
