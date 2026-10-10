import base64
import importlib.util
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('mass_pr', ROOT / 'scripts/mass_pr.py')
mass_pr = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mass_pr)


class DeleteCampaignTests(unittest.TestCase):
    def config(self, files=None):
        return {
            'organization': 'Example', 'files': files or [{'target': '.github/workflows/old.yml', 'mode': 'delete'}],
            'work_branch_prefix': 'automation/cleanup', 'commit_message': 'chore: clean {{REPO_NAME}}',
            'pr_title': 'Clean old files', 'pr_body': 'Remove explicitly listed obsolete files.',
        }

    def apply(self, cfg, dry_run=False):
        return mass_pr.apply_files('Example/app', 'app', 'main', 'automation/cleanup-main', cfg, dry_run)

    def test_delete_only_config_needs_no_source(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp, 'config.json')
            path.write_text(json.dumps(self.config()))
            self.assertEqual(mass_pr.load_config(path), self.config())

    def test_missing_file_is_idempotent(self):
        with patch.object(mass_pr, 'fetch_file_meta', return_value=None), patch.object(mass_pr, 'delete_file') as delete:
            self.assertEqual(self.apply(self.config()), 0)
            delete.assert_not_called()

    def test_dry_run_reports_without_deleting(self):
        with patch.object(mass_pr, 'fetch_file_meta', return_value={'type': 'file', 'sha': 'blob-sha'}), \
             patch.object(mass_pr, 'delete_file') as delete, patch('builtins.print') as output:
            self.assertEqual(self.apply(self.config(), dry_run=True), 1)
            delete.assert_not_called()
            output.assert_called_with('    delete .github/workflows/old.yml')

    def test_delete_uses_work_branch_current_sha_and_rendered_message(self):
        with patch.object(mass_pr, 'fetch_file_meta', return_value={'type': 'file', 'sha': 'blob-sha'}), \
             patch.object(mass_pr, 'delete_file') as delete:
            self.assertEqual(self.apply(self.config()), 1)
            delete.assert_called_once_with('Example/app', '.github/workflows/old.yml',
                                           'automation/cleanup-main', 'chore: clean app', 'blob-sha')

    def test_delete_api_request(self):
        with patch.object(mass_pr, 'gh_text') as gh:
            mass_pr.delete_file('Example/app', 'old.yml', 'automation/cleanup-main', 'Cleanup', 'blob-sha')
            gh.assert_called_once_with(['api', '-X', 'DELETE', 'repos/Example/app/contents/old.yml',
                                        '-f', 'message=Cleanup', '-f', 'sha=blob-sha',
                                        '-f', 'branch=automation/cleanup-main'])

    def test_mixed_create_and_delete_campaign(self):
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp, 'new.yml')
            source.write_text('new workflow')
            cfg = self.config([{'target': 'new.yml', 'source': str(source)}, {'target': 'old.yml', 'mode': 'delete'}])
            with patch.object(mass_pr, 'fetch_file_meta', side_effect=[None, {'type': 'file', 'sha': 'old-sha'}]), \
                 patch.object(mass_pr, 'put_file') as put, patch.object(mass_pr, 'delete_file') as delete:
                self.assertEqual(self.apply(cfg), 2)
                self.assertEqual(put.call_count, 1)
                self.assertEqual(delete.call_count, 1)

    def test_rejects_non_file_and_invalid_targets(self):
        for target in ['*.yml', '/old.yml', '../old.yml', 'dir/../old.yml', 'dir/', 'a?b.yml', 'a[b].yml', 'dir\\old.yml']:
            with self.subTest(target=target), self.assertRaises(ValueError):
                mass_pr.validate_delete_target(target)
        for meta in [[{'type': 'file'}], {'type': 'dir', 'sha': 'dir-sha'}, {'type': 'symlink', 'sha': 'link-sha'}]:
            with patch.object(mass_pr, 'fetch_file_meta', return_value=meta), patch.object(mass_pr, 'delete_file') as delete:
                with self.assertRaises(ValueError):
                    self.apply(self.config())
                delete.assert_not_called()

    def test_permission_errors_are_not_missing_files(self):
        for code in [403, 500]:
            result = subprocess.CompletedProcess([], 1, '', f'gh: Error (HTTP {code})')
            with patch.object(mass_pr, 'run', return_value=result), self.assertRaises(RuntimeError):
                mass_pr.fetch_file_meta('Example/app', 'old.yml', 'automation/cleanup-main')
        result = subprocess.CompletedProcess([], 1, '', 'gh: Not Found (HTTP 404)')
        with patch.object(mass_pr, 'run', return_value=result):
            self.assertIsNone(mass_pr.fetch_file_meta('Example/app', 'old.yml', 'automation/cleanup-main'))

    def test_source_preflight_ignores_delete_entries(self):
        cfg = self.config()
        cfg['required_workflow_source'] = {'repository': 'Example/central', 'ref': 'stable'}
        with patch.object(mass_pr, 'tree_paths', return_value=[]):
            mass_pr.check_workflow_source(cfg)


if __name__ == '__main__':
    unittest.main()
