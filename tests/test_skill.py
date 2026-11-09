"""Meaningful filesystem/installation checks; execute through just test all."""
import copy
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch

if os.environ.get('LEVERAGE_TEST_ISOLATED') != '1':
    raise SystemExit('Run through just test all: filesystem tests require container isolation.')
SOURCE = Path(__file__).resolve().parents[1]

# A copy, not the source checkout, models the actual installed unit.
INSTALL = tempfile.TemporaryDirectory()
SKILL = Path(INSTALL.name) / 'leverage'
shutil.copytree(SOURCE / 'skills/leverage', SKILL)
sys.path.insert(0, str(SKILL / 'scripts'))
import bootstrap
import render
from report_data import normalize


HELP = '#!/bin/sh\nif [ "$1" = leverage ]; then echo "--dir --author --by-author --author-threshold --json"; exit 0; fi\nexit 0\n'


def fixture():
    scope = {'target': '/work/example', 'git_root': '/work/example', 'head': 'a' * 40,
             'manifest_digest': 'scope', 'content_digest': 'content', 'identity_digest': 'identity',
             'refs_digest': 'refs', 'files': 2, 'lines': 1000, 'code_lines': 700,
             'estimated_person_months': 10, 'config_sources': [], 'scan_arguments': []}
    summary = {'files': 2, 'lines': 1000, 'code_lines': 700, 'estimated_person_months': 10,
               'attribution_coverage': 1, 'buckets': {
                   'contributors': {'lines': 900, 'share': .9, 'estimated_person_months': 9},
                   'excluded_identities': {'lines': 0, 'share': 0, 'estimated_person_months': 0},
                   'uncommitted': {'lines': 100, 'share': .1, 'estimated_person_months': 1},
                   'unavailable': {'lines': 0, 'share': 0, 'estimated_person_months': 0}}}
    metadata = {'generated_at': '2025-06-15T12:00:00Z', 'tools': {'camp': 'fixture'},
                'summary': summary, 'diagnostics': []}
    repo = {'schema_version': 'leverage-repository/v1', 'view': 'summary', 'status': 'complete',
            'campaign': {'full_leverage': 4, 'actual_person_months': 2.5},
            'report': {**metadata, 'scope': scope, 'effort_method': 'fixture'}}
    authors = {'schema_version': 'leverage-contributors/v1', 'method': 'contributor_worktree_v1',
               'status': 'complete', **metadata, 'projects': [scope],
               'display': {'omitted_lines': 0, 'omitted_contributors': 0}, 'contributors': [
                   {'id': 'alice@private.test', 'name': 'Alice', 'lines': 800, 'share': .8,
                    'estimated_person_months': 8, 'elapsed_person_months': 2, 'leverage': 4, 'history_complete': True},
                   {'id': 'bob@private.test', 'name': 'Bob', 'lines': 100, 'share': .1,
                    'estimated_person_months': 1, 'elapsed_person_months': .1, 'leverage': 10, 'history_complete': True}]}
    return repo, authors


class BootstrapTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.install = self.root / 'bin'
        self.receipt = self.root / 'state/receipt.json'
        self.env = patch.dict(os.environ, {'LEVERAGE_INSTALL_DIR': str(self.install), 'XDG_STATE_HOME': str(self.root / 'state')})
        self.env.start()
        self.addCleanup(self.env.stop)

    def executable(self, path, content=HELP):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
        path.chmod(0o755)
        return path

    def payload(self, missing=None):
        return ('v1.2.3', {n: HELP.encode() for n in ('camp', 'fest', 'festival') if n != missing})

    def test_fresh_install_returns_capable_path_and_three_receipted_binaries(self):
        with patch.object(bootstrap, 'release_payload', return_value=self.payload()):
            camp = bootstrap.install_bundle(self.install, self.receipt, {})
        self.assertTrue(bootstrap.capable(camp))
        receipt = json.loads(self.receipt.read_text())
        self.assertEqual(len(receipt['files']), 3)
        for path in receipt['files']:
            self.assertTrue(bootstrap.owned(Path(path), receipt))

    def test_compatible_custom_camp_preserved_when_manager_missing(self):
        custom = self.executable(self.root / 'custom/camp')
        with patch.object(bootstrap, 'find_tool', side_effect=lambda name, _: custom if name == 'camp' else None), patch.object(bootstrap, 'release_payload', return_value=self.payload()):
            resolved = bootstrap.ensure()
        self.assertEqual(resolved, custom)
        self.assertEqual(custom.read_text(), HELP)
        self.assertFalse((self.install / 'camp').exists())
        self.assertTrue((self.install / 'festival').exists())

    def test_ready_install_is_no_network_no_write(self):
        camp = self.executable(self.root / 'existing/camp')
        manager = self.executable(self.root / 'existing/festival')
        with patch.object(bootstrap, 'find_tool', side_effect=lambda n, _: camp if n == 'camp' else manager), patch.object(bootstrap, 'fetch', side_effect=AssertionError('network')):
            self.assertEqual(bootstrap.ensure(), camp)
        self.assertFalse((self.root / 'state/leverage').exists())

    def test_check_mode_is_non_mutating(self):
        with patch.object(bootstrap, 'find_tool', return_value=None), patch.object(bootstrap, 'fetch', side_effect=AssertionError('network')):
            with self.assertRaises(bootstrap.BootstrapError) as error:
                bootstrap.ensure(check=True)
        self.assertEqual(error.exception.code, 6)
        self.assertFalse(self.install.exists())

    def test_unmanaged_old_and_changed_receipt_are_not_overwritten(self):
        custom = self.executable(self.root / 'bin/camp', '#!/bin/sh\necho old\n')
        with patch.object(bootstrap, 'find_tool', side_effect=lambda name, _: custom if name == 'camp' else None):
            with self.assertRaises(bootstrap.BootstrapError) as error:
                bootstrap.ensure()
        self.assertEqual(error.exception.code, 4)
        with patch.object(bootstrap, 'release_payload', return_value=self.payload()):
            with self.assertRaises(bootstrap.BootstrapError):
                bootstrap.install_bundle(self.install, self.receipt, {'files': {str(custom): 'wrong'}})
        self.assertIn('old', custom.read_text())

    def test_failed_capability_rolls_back_install(self):
        with patch.object(bootstrap, 'release_payload', return_value=('v1.2.3', {n: b'#!/bin/sh\nexit 0\n' for n in ('camp', 'fest', 'festival')})):
            with self.assertRaises(bootstrap.BootstrapError):
                bootstrap.install_bundle(self.install, self.receipt, {})
        self.assertFalse((self.install / 'camp').exists())
        self.assertFalse(self.receipt.exists())

    def test_package_managed_update_returns_owner_action_without_install(self):
        camp = self.executable(self.root/'old/camp', '#!/bin/sh\necho old\n')
        manager = self.executable(self.root/'old/festival')
        def calls(args):
            result = subprocess.CompletedProcess(args, 0, '', '')
            if args[1:]==['leverage', '--help']:
                result.stdout='old'
            elif args[1:]==['resolve', 'camp']:
                result.stdout=str(camp)
            else:
                result.stdout=json.dumps({'action':'package','upgrade':'brew upgrade festival'})
            return result
        with patch.object(bootstrap, 'find_tool', side_effect=lambda n,_: camp if n=='camp' else manager), patch.object(bootstrap, 'run', side_effect=calls), patch.object(bootstrap, 'fetch', side_effect=AssertionError('download')):
            with self.assertRaises(bootstrap.BootstrapError) as error:
                bootstrap.ensure()
        self.assertEqual(error.exception.code, 4)
        self.assertIn('brew upgrade', str(error.exception))

    def test_checksum_and_archive_members_validated_before_install(self):
        import hashlib
        buffer = io.BytesIO()
        with tarfile.open(fileobj=buffer, mode='w:gz') as archive:
            for name in ('camp', 'fest', 'festival'):
                info = tarfile.TarInfo(name)
                info.size = len(HELP.encode())
                archive.addfile(info, io.BytesIO(HELP.encode()))
        payload = buffer.getvalue()
        osname = 'macOS' if sys.platform == 'darwin' else 'linux'
        arch = 'arm64' if bootstrap.platform.machine() in ('arm64', 'aarch64') else 'x86_64'
        name = f'festival-1.2.3-{osname}-{"all" if osname == "macOS" else arch}.tar.gz'
        base = 'https://github.com/Obedience-Corp/festival/releases/download/v1.2.3/'
        meta = {'tag_name': 'v1.2.3', 'assets': [{'name': n, 'browser_download_url': base+n} for n in (name, 'checksums.txt')]}
        def download(url):
            if url.endswith('/latest'):
                return json.dumps(meta).encode()
            if url.endswith('checksums.txt'):
                return (hashlib.sha256(payload).hexdigest() + '  ' + name).encode()
            return payload
        with patch.object(bootstrap, 'fetch', side_effect=download):
            tag, files = bootstrap.release_payload()
        self.assertEqual(tag, 'v1.2.3')
        self.assertEqual(set(files), {'camp', 'fest', 'festival'})
        def bad(url):
            return b'0' * 64 + b'  ' + name.encode() if url.endswith('checksums.txt') else download(url)
        with patch.object(bootstrap, 'fetch', side_effect=bad), self.assertRaises(bootstrap.BootstrapError):
            bootstrap.release_payload()


class ReportTests(unittest.TestCase):
    def test_exact_accounting_and_portable_data(self):
        repo, authors = fixture()
        data = normalize(repo, authors)
        self.assertEqual(sum(r['estimated_person_months'] for r in data['contributors']), 9)
        self.assertNotIn('@private.test', json.dumps(data))
        self.assertNotIn('/work/', json.dumps(data))
        self.assertEqual(data['generated_at'], '2025-06-15T12:00:00Z')

    def test_mismatched_scope_rejected(self):
        repo, authors = fixture()
        authors = copy.deepcopy(authors)
        authors['projects'][0]['content_digest'] = 'different'
        with self.assertRaisesRegex(ValueError, 'scope'):
            normalize(repo, authors)

    def test_partial_null_and_empty_are_not_zero_scores(self):
        repo, authors = fixture()
        authors['status'] = 'partial'
        authors['contributors'][0]['leverage'] = None
        authors['contributors'][0]['elapsed_person_months'] = None
        data = normalize(contributors=authors)
        svg = render.figure(data, json.loads((SKILL/'assets/theme.json').read_text())['dark'], 'ownership', 10)
        self.assertIn('PARTIAL', svg)
        self.assertIn('unavailable', svg)
        self.assertIsNone(data['contributors'][0]['leverage'])
        repo['status'] = 'empty'
        repo['report']['summary'] = {'files': 0, 'lines': 0, 'code_lines': 0, 'estimated_person_months': 0,
                                    'buckets': {key: {'lines': 0, 'share': 0, 'estimated_person_months': 0} for key in render.BUCKETS}}
        repo['report']['scope'].update(files=0, lines=0, code_lines=0, estimated_person_months=0)
        empty = normalize(repository=repo)
        self.assertIn('EMPTY', render.figure(empty, json.loads((SKILL/'assets/theme.json').read_text())['dark'], 'ownership', 10))

    def test_score_only_views_display_selected_score_without_contributor_axes(self):
        import xml.etree.ElementTree as ET
        theme = json.loads((SKILL/'assets/theme.json').read_text())['dark']
        repo, _ = fixture()
        personal = copy.deepcopy(repo)
        personal['report']['matched_author_ids'] = ['alice@private.test']
        for data in (normalize(repository=repo), normalize(personal=personal)):
            for score in (4, None):
                data['score']['full_leverage'] = score
                svg = render.figure(data, theme, 'ownership', 10)
                texts = [node.text for node in ET.fromstring(svg).findall('{http://www.w3.org/2000/svg}text')]
                self.assertIn('4.00x' if score else 'unavailable', texts)
                self.assertIn('Effort proxy: 2.50 person-months', texts)
                self.assertIn('10.0', texts)  # Repository estimate stays separate from the selected score.
                self.assertNotIn('SHARE', texts)
                self.assertNotIn('MODEL RATIO', texts)
                if data['view'] == 'personal':
                    self.assertIn('Matched author identities: 1', texts)
                self.assertNotIn('| Contributor |', render.markdown(data, 'ownership', 10))

    def test_offline_restyle_preserves_all_measurements_without_external_commands(self):
        import csv
        repo, authors = fixture()
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for name, source in (('repository', repo), ('contributors', authors)):
                (root/f'{name}.json').write_text(json.dumps(source))
            render.write_bundle(normalize(repo, authors), root/'original')
            result = subprocess.run([
                sys.executable, str(SKILL/'scripts/render.py'),
                '--repository', str(root/'repository.json'), '--contributors', str(root/'contributors.json'),
                '--output', str(root/'light'), '--theme', 'light', '--sort', 'ratio',
            ], env={**os.environ, 'PATH': str(root/'no-tools')}, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual((root/'original/data/snapshot.json').read_bytes(), (root/'light/data/snapshot.json').read_bytes())
            def rows(name):
                with (root/name/'data/contributors.csv').open() as stream:
                    return list(csv.DictReader(stream))
            original, light = rows('original'), rows('light')
            self.assertEqual([r['name'] for r in light], ['Bob', 'Alice'])
            self.assertEqual(sorted(original, key=lambda r: r['row_id']), sorted(light, key=lambda r: r['row_id']))
            self.assertFalse((root/'light/raw').exists())

    def test_table_csv_svg_and_png_from_installed_copy(self):
        repo, authors = fixture()
        authors['contributors'][0]['name'] = '<A & B> | ' + 'Unicode 名' * 20
        data = normalize(repo, authors)
        with tempfile.TemporaryDirectory() as temp:
            render.write_bundle(data, Path(temp), png=True)
            import xml.etree.ElementTree as ET
            tree = ET.parse(Path(temp)/'assets/contributors.svg')
            self.assertIn('800', (Path(temp)/'report.md').read_text())
            self.assertIn('&lt;A &amp; B&gt;', (Path(temp)/'assets/contributors.svg').read_text())
            self.assertTrue((Path(temp)/'assets/contributors.png').read_bytes().startswith(b'\x89PNG'))
            self.assertEqual(len(tree.getroot().findall('{http://www.w3.org/2000/svg}text')) > 10, True)

    def test_duplicate_identity_invalid_number_and_broken_accounting_rejected(self):
        for modify in (lambda a: a['contributors'].append(a['contributors'][0]),
                       lambda a: a['contributors'][0].update(leverage=float('nan')),
                       lambda a: a['summary']['buckets']['contributors'].update(lines=899)):
            _, authors = fixture()
            modify(authors)
            with self.assertRaises(ValueError):
                normalize(contributors=authors)

    def test_png_is_optional_and_summary_label_is_not_a_contributor_sum(self):
        repo, authors = fixture()
        data = normalize(repo, authors)
        self.assertEqual(data['view'], 'overview')
        with tempfile.TemporaryDirectory() as temp, patch.object(render.shutil, 'which', return_value=None):
            render.write_bundle(data, Path(temp), png=True)
            self.assertTrue((Path(temp)/'assets/contributors.svg').is_file())
            self.assertFalse((Path(temp)/'assets/contributors.png').exists())
            self.assertIn('Repository ratio', (Path(temp)/'report.md').read_text())

    def test_filtered_input_is_labeled_and_not_promoted_to_complete_roster(self):
        _, authors = fixture()
        authors['contributors'].pop()
        authors['display'].update(omitted_contributors=1, omitted_lines=100)
        data = normalize(contributors=authors)
        self.assertFalse(data['contributors_complete'])
        self.assertIn('Input was filtered', render.markdown(data, 'ownership', 10))

    def test_skill_frontmatter_and_resource_links(self):
        import re
        import yaml
        body = (SKILL/'SKILL.md').read_text()
        meta = yaml.safe_load(body.split('---', 2)[1])
        self.assertEqual(meta['name'], 'leverage')
        self.assertTrue(meta['description'])
        for link in re.findall(r'\]\(([^)]+)\)', body):
            self.assertTrue((SKILL/link).is_file(), link)
        for script in ('collect.py', 'render.py', 'ensure-festival.sh'):
            self.assertTrue((SKILL/'scripts'/script).is_file())


if __name__ == '__main__':
    unittest.main(verbosity=2)
