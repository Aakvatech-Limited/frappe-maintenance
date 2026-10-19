import fnmatch
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
spec = importlib.util.spec_from_file_location('apply_rulesets', ROOT / 'scripts/apply_rulesets.py')
apply_rulesets = importlib.util.module_from_spec(spec)
spec.loader.exec_module(apply_rulesets)

CHECKS = json.loads((ROOT / 'configs/required-checks.json').read_text())['checks']
TEMPLATE = json.loads((ROOT / 'configs/rulesets/required-checks.json').read_text())


def read_yaml(path):
    return yaml.load(path.read_text(), Loader=yaml.BaseLoader)


class RequiredCheckRuleset(unittest.TestCase):
    def test_each_context_matches_its_central_job(self):
        # A context that no job reports would block every merge.
        trigger = read_yaml(ROOT / 'templates/workflows/aakvatech-ci.yml')
        (trigger_job, _), = trigger['jobs'].items()
        router = read_yaml(ROOT / '.github/workflows/router.yml')['jobs']
        for check in CHECKS:
            with self.subTest(job=check['job']):
                callee = read_yaml(ROOT / router[check['job']]['uses'].split('/', 2)[2].split('@')[0])
                names = [job.get('name', key) for key, job in callee['jobs'].items()]
                self.assertIn(check['context'], [f"{trigger_job} / {check['job']} / {name}" for name in names])

    def test_ruleset_lists_every_check_from_github_actions(self):
        ruleset = apply_rulesets.build_ruleset(TEMPLATE, CHECKS)
        rule = ruleset['rules'][0]['parameters']['required_status_checks']
        self.assertEqual([item['context'] for item in rule], [check['context'] for check in CHECKS])
        self.assertTrue(all(item['integration_id'] == apply_rulesets.GITHUB_ACTIONS_APP_ID for item in rule))
        self.assertEqual(TEMPLATE['rules'][0]['parameters']['required_status_checks'], [])

    def test_ruleset_covers_release_branches_only(self):
        include = TEMPLATE['conditions']['ref_name']['include']
        self.assertIn('~DEFAULT_BRANCH', include)
        patterns = [pattern for pattern in include if pattern.startswith('refs/heads/')]
        for branch, covered in [('version-15', True), ('version-16-hotfix', True),
                                ('release/bump-v15.1.0', False), ('backport-35-to-version-15', False)]:
            with self.subTest(branch=branch):
                self.assertEqual(any(fnmatch.fnmatch(f'refs/heads/{branch}', p) for p in patterns), covered)

    def test_only_onboarded_apps_get_the_ruleset(self):
        with tempfile.TemporaryDirectory() as temp:
            apps = Path(temp, 'apps.json')
            apps.write_text(json.dumps({'repositories': ['av_tools']}))
            self.assertEqual(apply_rulesets.get_repositories(apps, None), ['av_tools'])
            with self.assertRaises(SystemExit):
                apply_rulesets.get_repositories(apps, 'csf_tz')


if __name__ == '__main__':
    unittest.main()
