import json
import os
from pathlib import Path
import subprocess
import sys

import pytest
from pydantic import ValidationError

from oj.config import ROOT, load_settings


def test_config_is_independent_of_working_directory(tmp_path, monkeypatch):
    monkeypatch.delenv('OJ_CONFIG', raising=False)
    monkeypatch.chdir(tmp_path)
    assert load_settings().site.name == 'BZOJ'
    custom = tmp_path / 'custom.toml'
    custom.write_text('[site]\nname = " Practice Lab "\n')
    monkeypatch.setenv('OJ_CONFIG', str(custom))
    assert load_settings().site.name == 'Practice Lab'


@pytest.mark.parametrize('name', ['', '   ', 'x' * 81, 'name\nline', 12])
def test_invalid_site_names_fail_at_startup(tmp_path, name):
    path = tmp_path / 'invalid.toml'
    path.write_text(f'[site]\nname = {json.dumps(name)}\n')
    with pytest.raises(ValidationError):
        load_settings(path)


def test_custom_name_renders_and_sets_api_title(tmp_path):
    name = 'Practice <Lab> & Friends'
    path = tmp_path / 'site.toml'
    path.write_text(f'[site]\nname = {json.dumps(name)}\n')
    script = '''
import json
import sys
from pathlib import Path
from fastapi.testclient import TestClient
from oj.app import app
from oj import storage
storage.DB_PATH = Path(sys.argv[1])
client = TestClient(app, base_url="http://127.0.0.1")
for url in ("/", "/problems/hello-world", "/submissions"):
    page = client.get(url)
    assert page.status_code == 200
    assert "Practice &lt;Lab&gt; &amp; Friends" in page.text
    assert "Practice <Lab>" not in page.text
assert client.get("/openapi.json").json()["info"]["title"] == "Practice <Lab> & Friends"
print("Custom branding rendered on every page and API title.")
'''
    subprocess.run([sys.executable, '-c', script, str(tmp_path / 'test.sqlite3')],
                   cwd=ROOT, env={**os.environ, 'OJ_CONFIG': str(path)}, check=True,
                   capture_output=True, text=True)
