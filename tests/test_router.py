import json
import re
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
CHECKS = json.loads((ROOT / 'configs/required-checks.json').read_text())['checks']


def read_yaml(path):
    return yaml.load(path.read_text(), Loader=yaml.BaseLoader)


TRIGGER = read_yaml(ROOT / 'templates/workflows/aakvatech-ci.yml')
ROUTER = read_yaml(ROOT / '.github/workflows/router.yml')


def callee(job):
    return read_yaml(ROOT / job['uses'].split('/', 2)[2].split('@')[0])


class RouterContracts(unittest.TestCase):
    def test_required_checks_run_on_every_pull_request(self):
        # A skipped job counts as passed, so a required check must never be skipped on a PR.
        for check in CHECKS:
            with self.subTest(job=check['job']):
                condition = ROUTER['jobs'][check['job']]['if']
                self.assertTrue(condition.startswith("github.event_name == 'pull_request' ||"), condition)

    def test_trigger_grants_every_router_permission(self):
        granted = TRIGGER['permissions']
        order = {'read': 1, 'write': 2}
        for name, job in ROUTER['jobs'].items():
            for scope, level in job.get('permissions', {}).items():
                with self.subTest(job=name, scope=scope):
                    self.assertGreaterEqual(order[granted[scope]], order[level])

    def test_router_jobs_narrow_to_their_callee_permissions(self):
        for name, job in ROUTER['jobs'].items():
            for scope, level in callee(job).get('permissions', {}).items():
                with self.subTest(job=name, scope=scope):
                    self.assertEqual(job['permissions'][scope], level)

    def test_pull_request_target_jobs_never_check_out_pr_code(self):
        for name, job in ROUTER['jobs'].items():
            if 'pull_request_target' not in job['if']:
                continue
            with self.subTest(job=name):
                text = (ROOT / job['uses'].split('/', 2)[2].split('@')[0]).read_text()
                self.assertNotRegex(text, r'pull_request\.head\.(sha|ref)')

    def test_manual_tasks_match_trigger_choices(self):
        choices = set(TRIGGER['on']['workflow_dispatch']['inputs']['task']['options'])
        tasks = {match for job in ROUTER['jobs'].values() for match in re.findall(r"inputs\.task == '(\w+)'", job['if'])}
        self.assertEqual(tasks, choices)

    def test_failure_labels_follow_own_pull_request_runs(self):
        self.assertEqual(TRIGGER['on']['workflow_run']['workflows'], [TRIGGER['name']])
        self.assertIn("github.event.workflow_run.event == 'pull_request'", ROUTER['jobs']['label-failed-prs']['if'])

    def test_required_checks_dispatch_the_trigger(self):
        config = json.loads((ROOT / 'configs/required-checks.json').read_text())
        self.assertTrue((ROOT / 'templates/workflows' / config['trigger']).is_file())


class OnboardingCampaign(unittest.TestCase):
    def test_campaign_adds_trigger_and_removes_every_old_file(self):
        files = json.loads((ROOT / 'configs/onboard-central-ci.json').read_text())['files']
        created = [item['target'] for item in files if item.get('mode') != 'delete']
        deleted = {item['target'] for item in files if item.get('mode') == 'delete'}
        self.assertEqual(created, ['.github/workflows/aakvatech-ci.yml'])
        managed = {item['target'] for item in json.loads((ROOT / 'configs/app-config-files.json').read_text())['files']}
        old_callers = {f'.github/workflows/{path.name}' for path in (ROOT / 'templates/workflows').glob('*.yml')
                       if path.name != 'aakvatech-ci.yml'}
        self.assertLessEqual(managed | old_callers, deleted)


if __name__ == '__main__':
    unittest.main()
