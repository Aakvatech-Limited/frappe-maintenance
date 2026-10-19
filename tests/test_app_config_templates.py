import re
import subprocess
import tomllib
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = ROOT / 'templates'


def hooks_by_id(config):
    return {hook['id']: hook for repo in config['repos'] for hook in repo['hooks']}


class PreCommitTemplate(unittest.TestCase):
    def setUp(self):
        self.config = yaml.safe_load((TEMPLATES / 'pre-commit-config.yaml').read_text())

    def test_has_no_app_specific_paths(self):
        # One file serves every app, so no hook may limit itself to an app package.
        for hook in hooks_by_id(self.config).values():
            self.assertNotIn('files', hook)

    def test_installs_all_hook_stages(self):
        self.assertEqual(self.config['default_install_hook_types'], ['pre-commit', 'commit-msg', 'pre-push'])

    def test_blocks_commit_to_production_branches(self):
        args = hooks_by_id(self.config)['no-commit-to-branch']['args']
        pattern = args[args.index('--pattern') + 1]
        for branch in ['version-15', 'version-16', 'version-17', 'version-18']:
            self.assertRegex(branch, pattern)
        for branch in ['version-15-hotfix', 'develop', 'feat/version-15']:
            self.assertNotRegex(branch, pattern)

    def test_blocks_push_to_production_branches(self):
        entry = hooks_by_id(self.config)['no-push-to-production-branch']['entry']
        script = re.fullmatch(r"bash -c '(.*)'", entry)[1]
        cases = {
            'refs/heads/version-15': 1,
            'refs/heads/version-18': 1,
            'refs/heads/version-15-hotfix': 0,
            'refs/heads/develop': 0,
        }
        for remote_branch, code in cases.items():
            with self.subTest(remote_branch=remote_branch):
                result = subprocess.run(['bash', '-c', script], env={'PRE_COMMIT_REMOTE_BRANCH': remote_branch},
                                        capture_output=True)
                self.assertEqual(result.returncode, code)

    def test_excludes_built_assets(self):
        exclude = re.compile(self.config['exclude'])
        for path in ['av_tools/public/dist/x.js', 'hms_tz/public/frontend/a.js', 'node_modules/a.js']:
            self.assertIsNotNone(exclude.search(path))
        for path in ['av_tools/hooks.py', 'av_tools/public/js/form.js']:
            self.assertIsNone(exclude.search(path))


class OtherTemplates(unittest.TestCase):
    def test_ruff_config_uses_frappe_style(self):
        config = tomllib.loads((TEMPLATES / 'ruff.toml').read_text())
        self.assertNotIn('tool', config)
        self.assertEqual(config['format']['indent-style'], 'tab')
        self.assertEqual(config['format']['quote-style'], 'double')
        self.assertIn('I', config['lint']['select'])

    def test_commitlint_config_is_valid_javascript(self):
        subprocess.run(['node', '--check', TEMPLATES / 'commitlint.config.js'], check=True)

    def test_setup_script_syntax(self):
        subprocess.run(['bash', '-n', TEMPLATES / 'setup-git-hooks.sh'], check=True)


if __name__ == '__main__':
    unittest.main()
