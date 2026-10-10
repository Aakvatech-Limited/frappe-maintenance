import importlib.util
import json
import re
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def read_yaml(path):
    # BaseLoader keeps GitHub's `on` key as a string, rather than a YAML 1.1 boolean.
    return yaml.load(path.read_text(), Loader=yaml.BaseLoader)


class WorkflowContracts(unittest.TestCase):
    def test_callers_resolve_and_grant_required_permissions(self):
        for path in (ROOT / 'templates/workflows').glob('*.yml'):
            with self.subTest(caller=path.name):
                caller = read_yaml(path)
                self.assertNotIn('concurrency', caller)
                for job in caller['jobs'].values():
                    self.assertNotIn('steps', job)
                    match = re.fullmatch(
                        r'Aakvatech-Limited/frappe-maintenance/(.github/workflows/[^/]+)@stable',
                        job['uses'],
                    )
                    self.assertIsNotNone(match)
                    callee = read_yaml(ROOT / match[1])
                    self.assertIn('workflow_call', callee['on'])
                    for scope, permission in callee.get('permissions', {}).items():
                        self.assertEqual(caller['permissions'][scope], permission)

    def test_trigger_contracts(self):
        expected = {
            'backport': {'pull_request_target'},
            'tag-and-promote-from-pr-label': {'pull_request_target'},
            'label-failed-prs': {'workflow_run', 'workflow_dispatch'},
            'linter': {'pull_request', 'workflow_dispatch'},
            'pre-commit': {'pull_request', 'workflow_dispatch'},
            'semantic-commits': {'pull_request'},
            'no-raw-sql': {'pull_request', 'push', 'workflow_dispatch'},
            'modernize-frappe': {'workflow_dispatch'},
            'custom-app-compliance': {'workflow_dispatch'},
        }
        for name, events in expected.items():
            caller = read_yaml(ROOT / f'templates/workflows/{name}.yml')
            self.assertEqual(set(caller['on']), events)
        for name in ['backport', 'tag-and-promote-from-pr-label']:
            caller = read_yaml(ROOT / f'templates/workflows/{name}.yml')
            self.assertEqual(caller['on']['pull_request_target']['types'], ['closed', 'labeled'])
        labels = read_yaml(ROOT / 'templates/workflows/label-failed-prs.yml')
        self.assertEqual(labels['on']['workflow_run']['workflows'], ['*', '!Label Failed Pull Requests'])

    def test_legacy_template_paths_match(self):
        for name in ['label-failed-prs', 'modernize-frappe']:
            self.assertEqual((ROOT / f'templates/{name}.yml').read_text(),
                             (ROOT / f'templates/workflows/{name}.yml').read_text())

    def test_all_campaigns_only_distribute_callers(self):
        for path in (ROOT / 'configs').glob('*.json'):
            config = json.loads(path.read_text())
            for item in config.get('files', []):
                if item.get('mode') != 'delete' and item['target'].startswith('.github/workflows/'):
                    caller = read_yaml(ROOT / item['source'])
                    self.assertTrue(all('uses' in job and 'steps' not in job
                                        for job in caller['jobs'].values()))

    def test_embedded_script_syntax(self):
        for path in (ROOT / '.github/workflows').glob('*.yml'):
            workflow = read_yaml(path)
            for job in workflow['jobs'].values():
                for step in job.get('steps', []):
                    if 'run' in step:
                        script = re.sub(r'\$\{\{.*?\}\}', 'placeholder', step['run'])
                        subprocess.run(['bash', '-n'], input=script, text=True, check=True)
                        for snippet in re.findall(r"python(?:3)? - <<'PY'\n(.*?)\nPY", script, re.S):
                            compile(snippet, str(path), 'exec')
                    if 'github-script@' in step.get('uses', ''):
                        script = step['with']['script']
                        subprocess.run(['node', '--check'],
                                       input='async function run() {\n' + script + '\n}',
                                       text=True, check=True)

    def test_no_raw_sql_policy(self):
        workflow = read_yaml(ROOT / '.github/workflows/no-raw-sql-reusable.yml')
        script = workflow['jobs']['no-raw-sql']['steps'][-1]['run']
        for content, expected_code in [
            ('frappe.qb.from_(doctype).select(doctype.name).run()\n', 0),
            ('frappe.db.sql("select 1")\n', 1),
            ('frappe.db.multisql({})\n', 1),
            ('db.sql("select 1")\n', 1),
        ]:
            with self.subTest(content=content), tempfile.TemporaryDirectory() as temp:
                Path(temp, 'example.py').write_text(content)
                result = subprocess.run(['bash', '-c', script], env={'APP_DIR': temp, 'PATH': '/usr/bin:/bin'},
                                        capture_output=True, text=True)
                self.assertEqual(result.returncode, expected_code, result.stdout + result.stderr)

    def test_release_branch_guard(self):
        workflow = read_yaml(ROOT / '.github/workflows/tag-and-promote-from-pr-label-reusable.yml')
        script = workflow['jobs']['tag-and-promote']['steps'][0]['with']['script']
        cases = [
            ('main', ['promote/main'], '[Backport main] fix: example', True, None),
            ('main', [], 'fix: example', False, 'false'),
            ('version-16-hotfix', ['promote/version-16-hotfix'], '[Backport version-16-hotfix] fix: example', False, 'true'),
            ('version-16-hotfix', [], '[Backport version-16-hotfix] fix: example', False, 'false'),
            ('version-15-hotfix', ['promote/version-15-hotfix'], 'fix: example', False, 'false'),
        ]
        for branch, labels, title, failure, release in cases:
            with self.subTest(branch=branch, labels=labels, title=title):
                payload = {'base': {'ref': branch}, 'labels': [{'name': label} for label in labels], 'title': title}
                harness = ('const context = {payload: {pull_request: ' + json.dumps(payload) + '}};\n'
                           'const result = {failed: false, outputs: {}};\n'
                           'const core = {info: () => {}, setFailed: () => {result.failed = true;}, '
                           'setOutput: (k,v) => {result.outputs[k] = v;}};\n'
                           '(async () => {\n' + script + '\n})().then(() => console.log(JSON.stringify(result)));')
                result = json.loads(subprocess.check_output(['node', '-e', harness], text=True))
                self.assertEqual(result['failed'], failure)
                self.assertEqual(result['outputs'].get('should_release'), release)


class MigrationBranches(unittest.TestCase):
    def test_missing_central_workflow_blocks_rollout(self):
        spec = importlib.util.spec_from_file_location('mass_pr', ROOT / 'scripts/mass_pr.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        config = module.load_config(ROOT / 'configs/migrate-reusable-workflows.json')
        config['files'] = [{**item, 'source': str(ROOT / item['source'])} for item in config['files']]
        with patch.object(module, 'tree_paths', return_value=[]):
            with self.assertRaisesRegex(ValueError, 'publish stable first'):
                module.check_workflow_source(config)
        paths = [str(path.relative_to(ROOT)) for path in (ROOT / '.github/workflows').glob('*-reusable.yml')]
        with patch.object(module, 'tree_paths', return_value=paths):
            module.check_workflow_source(config)

    def test_default_and_version_branches_only(self):
        spec = importlib.util.spec_from_file_location('mass_pr', ROOT / 'scripts/mass_pr.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        config = module.load_config(ROOT / 'configs/migrate-reusable-workflows.json')
        for branch in ['develop', 'version-15-hotfix', 'version-16-hotfix', 'version-16']:
            self.assertTrue(module.branch_matches_config(branch, 'develop', config))
        for branch in ['feature/example', 'automation/old', 'version-16-test']:
            self.assertFalse(module.branch_matches_config(branch, 'develop', config))
        config['branch_exclude_regex'] = '^develop$'
        self.assertFalse(module.branch_matches_config('develop', 'develop', config))
        config['include_default_branch'] = False
        config['branch_exclude_regex'] = '$^'
        self.assertFalse(module.branch_matches_config('develop', 'develop', config))


if __name__ == '__main__':
    unittest.main()
