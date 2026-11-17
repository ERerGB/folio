import copy, hashlib, importlib.util, json, os, re, subprocess, sys, tempfile, unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'scripts/library_profile.py'
spec = importlib.util.spec_from_file_location('folio_library_profile', SCRIPT)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)
EXAMPLE = json.loads(re.search('```json\\n(.*?)\\n```', (ROOT / 'references/library-organization-profile.md').read_text(), re.S).group(1))

class ProfileTests(unittest.TestCase):

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='folio-profile-fixture-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.file = self.root / 'profile.json'
        self.raw = copy.deepcopy(EXAMPLE)

    def load(self):
        self.file.write_text(json.dumps(self.raw))
        return module.load_profile(self.file)

    def cli(self, *args):
        env = os.environ.copy()
        env['PYTHONDONTWRITEBYTECODE'] = '1'
        return subprocess.run([sys.executable, str(SCRIPT), str(self.file), *args], capture_output=True, text=True, env=env, timeout=5)

    def test_complete_documented_example_and_readonly_cli(self):
        p = self.load()
        before = {str(f.relative_to(self.root)): hashlib.sha256(f.read_bytes()).hexdigest() for f in self.root.rglob('*') if f.is_file()}
        r = self.cli()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(json.loads(r.stdout)['result'], 'valid')
        r = self.cli('--name', 'Article-e001.epub', '--reading-data', 'none')
        self.assertEqual(json.loads(r.stdout), {'decision': 'proposed_path', 'path': 'Books/Inbox/Article-e001.epub'})
        after = {str(f.relative_to(self.root)): hashlib.sha256(f.read_bytes()).hexdigest() for f in self.root.rglob('*') if f.is_file()}
        self.assertEqual(before, after)

    def test_default_unknown_reading_data_manual(self):
        self.load()
        r = self.cli('--name', 'Article.epub')
        self.assertEqual(json.loads(r.stdout)['decision'], 'manual_review')

    def test_case_insensitive_extensions(self):
        self.assertEqual(module.resolve(self.load(), 'A.EPUB', 'inbox', 'none')['decision'], 'proposed_path')

    def test_observe_only(self):
        self.assertEqual(module.resolve(self.load(), 'A.NOTE', 'inbox', 'none')['decision'], 'observe_only')

    def test_unlisted_extension(self):
        self.assertEqual(module.resolve(self.load(), 'A.pdf', 'inbox', 'none')['decision'], 'manual_review')

    def test_completed_needs_evidence(self):
        self.assertEqual(module.resolve(self.load(), 'A.epub', 'completed', 'none')['decision'], 'manual_review')

    def test_completed_with_user_evidence(self):
        self.assertEqual(module.resolve(self.load(), 'A.epub', 'completed', 'none', 'user-confirmed')['path'], 'Books/Completed/A.epub')

    def test_catalog_only_state(self):
        self.assertEqual(module.resolve(self.load(), 'A.epub', 'reading', 'none', 'reader-progress')['decision'], 'index_only')

    def test_existing_reading_data_preserved(self):
        self.assertEqual(module.resolve(self.load(), 'A.epub', 'completed', 'present', 'reader-progress')['decision'], 'index_only')

    def test_opened_manual_policy(self):
        self.raw['safeguards']['opened_file_move'] = 'manual_review'
        self.assertEqual(module.resolve(self.load(), 'A.epub', 'inbox', 'present')['decision'], 'manual_review')

    def test_invalid_status_evidence_rejected(self):
        with self.assertRaises(ValueError):
            module.resolve(self.load(), 'A.epub', 'completed', 'none', 'folder-name')

    def test_invalid_reading_data_rejected(self):
        with self.assertRaises(ValueError):
            module.resolve(self.load(), 'A.note', 'inbox', 'unchecked')

    def test_unsafe_filenames(self):
        p = self.load()
        for name in ['../A.epub', '/A.epub', 'a/A.epub', 'a\\A.epub', 'A\x00.epub', '.', '..']:
            with self.subTest(name=name), self.assertRaises(ValueError):
                module.resolve(p, name, 'inbox', 'none')

    def test_unsafe_root_and_index(self):
        for (target, key) in [('device', 'library_root'), ('organization', 'index_file')]:
            with self.subTest(target=target):
                self.raw = copy.deepcopy(EXAMPLE)
                self.raw[target][key] = '../escape'
                with self.assertRaises(ValueError):
                    self.load()

    def test_protected_case_variant_rejected(self):
        self.raw['organization']['state_folders']['inbox'] = 'vendor'
        with self.assertRaises(ValueError):
            self.load()

    def test_duplicate_state_case_variant_rejected(self):
        self.raw['organization']['state_folders']['completed'] = 'inbox'
        with self.assertRaises(ValueError):
            self.load()

    def test_extension_case_duplicate_rejected(self):
        self.raw['safeguards']['extension_policies']['.EPUB'] = 'managed'
        with self.assertRaises(ValueError):
            self.load()

    def test_boolean_version_and_unknown_keys_rejected(self):
        for change in [{'schema_version': True}, {'credential': 'synthetic-do-not-log'}]:
            with self.subTest(change=change):
                self.raw = copy.deepcopy(EXAMPLE)
                self.raw.update(change)
                with self.assertRaises(ValueError):
                    self.load()

    def test_topics_require_facet_and_unique_ids(self):
        self.raw['organization']['topics'] = [{'id': 'sample', 'label': 'Synthetic topic'}]
        self.load()
        self.raw['organization']['topics'] *= 2
        with self.assertRaises(ValueError):
            self.load()
        self.raw['organization']['topics'] = []
        self.raw['organization']['facets'] = ['source']
        self.raw['organization']['topics'] = [{'id': 'sample', 'label': 'Topic'}]
        with self.assertRaises(ValueError):
            self.load()

    def test_invalid_cli_and_missing_profile_do_not_write(self):
        self.load()
        r = self.cli('--name', 'A.epub', '--status-evidence', 'folder')
        self.assertEqual(r.returncode, 2)
        self.file.unlink()
        r = self.cli()
        self.assertEqual(r.returncode, 2)
        self.assertEqual(list(self.root.iterdir()), [])
if __name__ == '__main__':
    unittest.main(verbosity=2)
