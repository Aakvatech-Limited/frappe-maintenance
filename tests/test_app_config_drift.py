import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'scripts/check_app_config_drift.py'
CONFIG = ROOT / 'configs/sync-app-ci.json'


def synced_app(temp):
    """Write every managed file exactly as the campaign would."""
    for item in json.loads(CONFIG.read_text())['files']:
        target = Path(temp, item['target'])
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((ROOT / item['source']).read_bytes())
    return Path(temp)


class AppConfigDrift(unittest.TestCase):
    def run_check(self, app, repository='av_tools'):
        command = [sys.executable, SCRIPT, '--root', app, '--repository', repository, '--branch', 'version-15-hotfix']
        return subprocess.run(command, capture_output=True, text=True)

    def test_synced_app_passes(self):
        with tempfile.TemporaryDirectory() as temp:
            result = self.run_check(synced_app(temp))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_local_edit_fails(self):
        with tempfile.TemporaryDirectory() as temp:
            app = synced_app(temp)
            with Path(app, 'ruff.toml').open('a') as handle:
                handle.write('line-length = 120\n')
            result = self.run_check(app)
        self.assertEqual(result.returncode, 1)
        self.assertIn('ruff.toml: differs from templates/ruff.toml', result.stdout)

    def test_missing_file_fails(self):
        with tempfile.TemporaryDirectory() as temp:
            app = synced_app(temp)
            Path(app, '.pre-commit-config.yaml').unlink()
            result = self.run_check(app)
        self.assertEqual(result.returncode, 1)
        self.assertIn('.pre-commit-config.yaml: missing', result.stdout)

    def test_app_not_onboarded_is_skipped(self):
        with tempfile.TemporaryDirectory() as temp:
            result = self.run_check(Path(temp), repository='csf_tz')
        self.assertEqual(result.returncode, 0)
        self.assertIn('skipping', result.stdout)

    def test_delete_entry_must_be_absent(self):
        with tempfile.TemporaryDirectory() as temp:
            app = synced_app(temp)
            Path(app, '.github/workflows').mkdir(parents=True, exist_ok=True)
            Path(app, '.github/workflows/old.yml').write_text('name: old\n')
            config = json.loads(CONFIG.read_text())
            config['files'].append({'target': '.github/workflows/old.yml', 'mode': 'delete'})
            Path(temp, 'config.json').write_text(json.dumps(config))
            result = subprocess.run([sys.executable, SCRIPT, '--root', app, '--repository', 'av_tools',
                                     '--branch', 'main', '--config', Path(temp, 'config.json')],
                                    capture_output=True, text=True)
        self.assertEqual(result.returncode, 1)
        self.assertIn('.github/workflows/old.yml: must be removed', result.stdout)


if __name__ == '__main__':
    unittest.main()
