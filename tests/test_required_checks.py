import importlib.util
import re
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
spec = importlib.util.spec_from_file_location('run_required_checks', ROOT / 'scripts/run_required_checks.py')
run_required_checks = importlib.util.module_from_spec(spec)
spec.loader.exec_module(run_required_checks)

CHECKS = [
    {'workflow': 'pre-commit.yml', 'accepts_base_sha': True},
    {'workflow': 'linter.yml', 'accepts_base_sha': False},
]


def release_steps():
    workflow = yaml.load((ROOT / '.github/workflows/tag-and-promote-from-pr-label-reusable.yml').read_text(),
                         Loader=yaml.BaseLoader)
    return workflow['jobs']['tag-and-promote']['steps']


class FakeGitHub:
    """Stands in for the gh CLI: each workflow has runs that already exist and runs that appear after dispatch."""

    def __init__(self, old_runs, new_runs):
        self.old_runs = old_runs
        self.new_runs = new_runs
        self.dispatched = []

    def run(self, command):
        self.dispatched.append(command)

    def gh_json(self, args):
        workflow = args[args.index('--workflow') + 1]
        runs = list(self.old_runs.get(workflow, []))
        if any(workflow in command for command in self.dispatched):
            runs += self.new_runs.get(workflow, [])
        return runs


class RequiredChecksScript(unittest.TestCase):
    def check(self, fake):
        with patch.object(run_required_checks, 'run', fake.run), \
             patch.object(run_required_checks, 'gh_json', fake.gh_json):
            checks = run_required_checks.RequiredChecks('org/app', 'release/bump-v15.1.0', 'abc', 'base', CHECKS)
            checks.start()
            return checks.wait(timeout_seconds=0, poll_seconds=0)

    def test_base_sha_only_sent_to_checks_that_accept_it(self):
        fake = FakeGitHub({}, {name: [{'databaseId': 1, 'status': 'completed', 'conclusion': 'success', 'url': 'u'}]
                               for name in ['pre-commit.yml', 'linter.yml']})
        self.assertEqual(self.check(fake), [])
        pre_commit, linter = fake.dispatched
        self.assertIn('base-sha=base', pre_commit)
        self.assertNotIn('-f', linter)

    def test_failed_check_is_reported(self):
        fake = FakeGitHub({}, {
            'pre-commit.yml': [{'databaseId': 1, 'status': 'completed', 'conclusion': 'failure', 'url': 'run-1'}],
            'linter.yml': [{'databaseId': 2, 'status': 'completed', 'conclusion': 'success', 'url': 'run-2'}],
        })
        self.assertEqual(self.check(fake), ['pre-commit.yml: failure run-1'])

    def test_old_successful_run_does_not_count(self):
        old = {'databaseId': 1, 'status': 'completed', 'conclusion': 'success', 'url': 'old'}
        fake = FakeGitHub({'pre-commit.yml': [old], 'linter.yml': [old]}, {})
        failures = self.check(fake)
        self.assertEqual(len(failures), 2)
        self.assertTrue(all('no result' in failure for failure in failures))

    def test_app_not_onboarded_runs_nothing(self):
        result = subprocess.run([sys.executable, ROOT / 'scripts/run_required_checks.py', '--repository',
                                 'Aakvatech-Limited/csf_tz', '--branch', 'b', '--sha', 's', '--base-sha', 'b'],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0)
        self.assertIn('no required checks to run', result.stdout)


class ReleaseFlow(unittest.TestCase):
    def test_release_commit_reaches_target_only_after_checks(self):
        names = [step.get('name') for step in release_steps()]
        commit_step = next(step for step in release_steps() if step.get('name') == 'Create release commit')
        self.assertNotIn('HEAD:$TARGET_BRANCH', commit_step['run'])
        self.assertIn('refs/heads/$CHECK_BRANCH', commit_step['run'])
        self.assertLess(names.index('Run required checks on release commit'),
                        names.index('Push release commit to target branch'))
        self.assertLess(names.index('Push release commit to target branch'), names.index('Create and push version tag'))

    def test_existing_release_detects_old_and_new_subjects(self):
        step = next(step for step in release_steps() if step.get('name') == 'Check for an existing release')
        pattern = re.search(r'=~ (.+?) \]\] &&', step['run'])[1]
        for subject, version in [('chore(release): Bumped to Version 15.2.1', '15.2.1'),
                                 ('chore(release): bump to version 15.3.0', '15.3.0')]:
            with self.subTest(subject=subject):
                script = f'[[ "$1" =~ {pattern} ]] && echo "${{BASH_REMATCH[2]}}"'
                result = subprocess.run(['bash', '-c', script, 'bash', subject], capture_output=True, text=True)
                self.assertEqual(result.stdout.strip(), version)

    def test_release_subject_follows_commit_rules(self):
        step = next(step for step in release_steps() if step.get('name') == 'Create release commit')
        subject = re.search(r'git commit -m "([^"]+)"', step['run'])[1]
        self.assertRegex(subject, r'^chore\(release\): [a-z]')


if __name__ == '__main__':
    unittest.main()
