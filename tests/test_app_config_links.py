import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
spec = importlib.util.spec_from_file_location('app_config_links', ROOT / 'scripts/app_config_links.py')
app_config_links = importlib.util.module_from_spec(spec)
spec.loader.exec_module(app_config_links)

TARGETS = [item['target'] for item in json.loads((ROOT / 'configs/app-config-files.json').read_text())['files']]


def git_app(temp):
    app = Path(temp, 'app')
    app.mkdir()
    subprocess.run(['git', 'init', '-q', app], check=True)
    return app


class AppConfigLinksTest(unittest.TestCase):
    def test_ci_links_every_config_to_frappe_maintenance(self):
        with tempfile.TemporaryDirectory() as temp:
            app = git_app(temp)
            self.assertEqual(app_config_links.prepare_ci(app, 'av_tools'), 0)
            for target in TARGETS:
                with self.subTest(target=target):
                    self.assertTrue(Path(app, target).is_symlink())
                    self.assertTrue(Path(app, target).resolve().is_relative_to(ROOT / 'templates'))

    def test_ci_fails_when_app_commits_a_managed_file(self):
        with tempfile.TemporaryDirectory() as temp:
            app = git_app(temp)
            Path(app, 'ruff.toml').write_text('line-length = 120\n')
            subprocess.run(['git', '-C', app, 'add', 'ruff.toml'], check=True)
            self.assertEqual(app_config_links.prepare_ci(app, 'av_tools'), 1)
            self.assertFalse(Path(app, 'ruff.toml').is_symlink())

    def test_app_not_onboarded_keeps_its_own_files(self):
        with tempfile.TemporaryDirectory() as temp:
            app = git_app(temp)
            self.assertEqual(app_config_links.prepare_ci(app, 'csf_tz'), 0)
            self.assertFalse(any(Path(app, target).exists() for target in TARGETS))

    def test_local_links_are_hidden_from_git_once(self):
        with tempfile.TemporaryDirectory() as temp:
            app = git_app(temp)
            links = app_config_links.AppConfigLinks(app)
            links.link()
            links.exclude_locally()
            links.exclude_locally()
            status = subprocess.run(['git', '-C', app, 'status', '--porcelain'], capture_output=True, text=True)
            self.assertEqual(status.stdout, '')
            exclude = Path(app, '.git/info/exclude').read_text()
            self.assertEqual(exclude.count('/ruff.toml'), 1)

    def test_link_refuses_to_replace_a_real_file(self):
        with tempfile.TemporaryDirectory() as temp:
            app = git_app(temp)
            Path(app, '.pre-commit-config.yaml').write_text('repos: []\n')
            with self.assertRaises(FileExistsError):
                app_config_links.AppConfigLinks(app).link()


if __name__ == '__main__':
    unittest.main()
