from unittest.mock import patch

import pytest

from bzoj.judge import judge
from bzoj.problems import EXAMPLES, load_problem

COUNTER = '''class Counter:
    def __init__(self, initial):
        self.value = initial
    def increment(self):
        self.value += 1
    def get(self):
        return self.value
'''
GREETING = "def hello_world(name):\n    return 'hello ' + name\n"


@pytest.mark.parametrize('slug, source', [('counter', COUNTER), ('hello-world', GREETING)])
def test_class_and_single_function(slug, source):
    result = judge(load_problem(EXAMPLES / f'{slug}.json'), source)
    assert result.status == 'Accepted'
    assert [c['status'] for c in result.cases] == ['Accepted', 'Accepted']
    assert set(result.cases[1]) == {'number', 'hidden', 'status'}


@pytest.mark.parametrize('source, status', [
    ("def hello_world(name): return 'wrong'", 'Wrong answer'),
    ("def hello_world(name): raise ValueError('broken')", 'Runtime error'),
    ('def broken(', 'Runtime error'),
    ('import os; os._exit(0)', 'Runtime error'),
    ("def hello_world(name): return {1, 2}", 'Runtime error'),
    ("def hello_world(name): return float('nan')", 'Runtime error'),
    ('while True: pass', 'Time limit exceeded'),
    ("while True: print('x' * 8192)", 'Output limit exceeded'),
])
def test_verdicts(source, status):
    with patch('bzoj.runner.TIMEOUT_SECONDS', 0.3):
        result = judge(load_problem(EXAMPLES / 'hello-world.json'), source)
    assert result.status == status


def test_driver_error():
    problem = load_problem(EXAMPLES / 'hello-world.json')
    problem.driver_code = 'pass'
    assert judge(problem, GREETING).status == 'Judge error'


def test_hidden_debug_output_is_not_returned():
    problem = load_problem(EXAMPLES / 'hello-world.json')
    source = "def hello_world(name):\n    print(name)\n    raise ValueError(name)"
    result = judge(problem, source)
    assert 'world' in result.stdout
    assert 'Python' not in result.stdout + result.stderr + str(result.cases)


def test_boolean_is_not_numeric_match():
    problem = load_problem(EXAMPLES / 'hello-world.json')
    problem.tests = [problem.tests[0]]
    problem.tests[0].expected = 1
    assert judge(problem, 'def hello_world(name): return True').status == 'Wrong answer'


def test_case_state_is_fresh_and_budget_is_shared():
    problem = load_problem(EXAMPLES / 'hello-world.json')
    source = "import time\ntime.sleep(0.2)\n" + GREETING
    with patch('bzoj.runner.TIMEOUT_SECONDS', 0.35):
        result = judge(problem, source)
    assert result.cases[0]['status'] == 'Accepted'
    assert result.cases[1]['status'] == 'Time limit exceeded'
