"""Synthetic report-only tests; no real model files or external requests."""
import contextlib
import copy
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest

import catalog_tools as ct


class CatalogTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.inventory_path = self.root / 'inventory.json'
        self.inventory = {'schema_version': 1, 'root': 'DO_NOT_EXPORT', 'files': [
            {'relative_path': 'loras/中文角色.safetensors', 'status': 'ok', 'sha256': 'a' * 64,
             'size_bytes': 10, 'metadata': {'secret': 'DO_NOT_EXPORT'}},
            {'relative_path': 'checkpoints/base.safetensors', 'status': 'ok', 'sha256': 'b' * 64,
             'size_bytes': 10},
        ]}
        self.save_inventory()
        self.out = self.root / 'draft'
        ct.prepare(self.inventory_path, self.out)
        self.catalog_path = self.out / 'catalog.json'
        self.catalog = json.loads(self.catalog_path.read_text(encoding='utf-8'))

    def save_inventory(self):
        self.inventory_path.write_text(json.dumps(self.inventory, ensure_ascii=False), encoding='utf-8')

    def save_catalog(self):
        self.catalog_path.write_text(json.dumps(self.catalog, ensure_ascii=False), encoding='utf-8')

    def check(self):
        self.save_catalog()
        return ct.validate(self.inventory_path, self.catalog_path)

    def verified(self, index=0):
        card = self.catalog['cards'][index]
        sha = self.inventory['files'][index]['sha256']
        card['identity'].update(status='verified', sha256=sha, publisher='Example Org',
                                version='v1', remote_file='weights.safetensors')
        card['sources'] = [{'url': 'https://example.org/models/v1', 'publisher': 'Example Org',
                            'version_or_revision': 'v1', 'checked_at': '2026-09-04',
                            'file_sha256': sha, 'supports': ['identity', 'purpose']}]
        return card

    def test_prepare_unknown_and_no_metadata_export(self):
        self.assertTrue(all(card['identity']['status'] == 'unknown' for card in self.catalog['cards']))
        self.assertTrue(all(card['identity']['sha256'] is None for card in self.catalog['cards']))
        tasks = (self.out / 'research_tasks.json').read_text(encoding='utf-8')
        self.assertNotIn('DO_NOT_EXPORT', tasks)
        self.assertEqual(json.loads(tasks)['tasks'][0]['sha256'], 'a' * 64)
        self.assertEqual(self.catalog['inventory_sha256'], hashlib.sha256(self.inventory_path.read_bytes()).hexdigest())
        self.check()

    def test_snapshot_mismatch_even_whitespace(self):
        self.inventory_path.write_bytes(self.inventory_path.read_bytes() + b'\n')
        with self.assertRaisesRegex(ValueError, '快照不匹配'):
            self.check()

    def test_missing_path(self):
        self.catalog['cards'].pop()
        with self.assertRaisesRegex(ValueError, '恰好'):
            self.check()

    def test_duplicate_path(self):
        self.catalog['cards'].append(copy.deepcopy(self.catalog['cards'][0]))
        with self.assertRaisesRegex(ValueError, '恰好'):
            self.check()

    def test_extra_path(self):
        self.catalog['cards'][0]['files'] = ['unlisted.safetensors']
        with self.assertRaisesRegex(ValueError, '清单外'):
            self.check()

    def test_hash_alone_does_not_verify_identity(self):
        self.catalog['cards'][0]['identity'].update(status='verified', sha256='a' * 64)
        with self.assertRaisesRegex(ValueError, '来源证据'):
            self.check()

    def test_verified_source_required_fields(self):
        for field in ('url', 'publisher', 'version_or_revision', 'checked_at', 'file_sha256', 'supports'):
            with self.subTest(field=field):
                card = self.verified()
                del card['sources'][0][field]
                with self.assertRaises(ValueError):
                    self.check()

    def test_verified_source_hash_mismatch(self):
        card = self.verified()
        card['sources'][0]['file_sha256'] = 'c' * 64
        with self.assertRaisesRegex(ValueError, '来源证据'):
            self.check()

    def test_verified_identity_hash_mismatch(self):
        card = self.verified()
        card['identity']['sha256'] = 'c' * 64
        with self.assertRaisesRegex(ValueError, '不能认证'):
            self.check()

    def test_same_size_different_hash_cannot_share(self):
        self.catalog['cards'][0]['files'] += self.catalog['cards'][1]['files']
        self.catalog['cards'].pop()
        with self.assertRaisesRegex(ValueError, '共享卡'):
            self.check()

    def test_same_hash_can_share_and_verify(self):
        self.inventory['files'][1]['sha256'] = 'A' * 64
        self.save_inventory()
        self.catalog['inventory_sha256'] = hashlib.sha256(self.inventory_path.read_bytes()).hexdigest()
        self.verified()
        self.catalog['cards'][0]['files'] += self.catalog['cards'][1]['files']
        self.catalog['cards'].pop()
        self.check()

    def test_error_and_changed_files_kept_but_not_verified(self):
        for status in ('error', 'changed_during_read', 'changed_during_hash', 'hash_error'):
            with self.subTest(status=status):
                self.inventory['files'][0]['status'] = status
                self.save_inventory()
                draft = self.root / status
                ct.prepare(self.inventory_path, draft)
                catalog = json.loads((draft / 'catalog.json').read_text(encoding='utf-8'))
                self.assertEqual(len(catalog['cards']), 2)
                self.catalog = catalog
                self.check()
                self.verified()
                with self.assertRaisesRegex(ValueError, '不能认证'):
                    self.check()

    def test_no_full_hash_cannot_verify(self):
        self.inventory['files'][0]['sha256'] = None
        self.save_inventory()
        self.catalog['inventory_sha256'] = hashlib.sha256(self.inventory_path.read_bytes()).hexdigest()
        card = self.verified()
        card['identity']['sha256'] = 'a' * 64
        card['sources'][0]['file_sha256'] = 'a' * 64
        with self.assertRaisesRegex(ValueError, '不能认证'):
            self.check()

    def test_outputs_never_overwrite(self):
        with self.assertRaises(FileExistsError):
            ct.prepare(self.inventory_path, self.out)
        target = self.root / 'report.md'
        target.write_text('KEEP', encoding='utf-8')
        with self.assertRaises(FileExistsError):
            ct.render(self.inventory_path, self.catalog_path, target)
        self.assertEqual(target.read_text(), 'KEEP')

    def test_chinese_render_and_research_fields(self):
        card = self.verified()
        card['one_sentence'] = '为角色增加细节。'
        card['compatibility']['base'] = '仅示例底模'
        card['name_parts'] = {'v1': '来源发布版本'}
        self.save_catalog()
        target = self.root / '说明.md'
        ct.render(self.inventory_path, self.catalog_path, target)
        body = target.read_text(encoding='utf-8')
        for phrase in ('为角色增加细节', '仅示例底模', '来源发布版本', '加速说明', '未实测', 'https://example.org/models/v1', '不证明来源或描述真实'):
            self.assertIn(phrase, body)

    def test_report_separates_error_files_and_skipped_items(self):
        self.inventory['files'][0]['status'] = 'error'
        self.inventory['skipped'] = [{'reason': 'link'}, {'reason': 'not_weight'}]
        self.save_inventory()
        target = self.root / 'counts'
        ct.prepare(self.inventory_path, target)
        body = (target / '模型库说明.md').read_text(encoding='utf-8')
        self.assertIn('清单文件：2；模型卡：2', body)
        self.assertIn('异常文件：1；跳过项：2', body)
        self.assertIn('| error |', body)

    def test_credentials_urls_rejected_without_echo(self):
        for url in ('https://user:password@example.org/model', 'https://example.org/?token=SECRET',
                    'https://example.org/?X-Amz-Signature=SECRET', 'https://example.org/?api_key=SECRET'):
            with self.subTest(url=url):
                card = self.verified()
                card['sources'][0]['url'] = url
                self.save_catalog()
                stderr = io.StringIO()
                with contextlib.redirect_stderr(stderr):
                    self.assertEqual(ct.main(['validate', str(self.inventory_path), str(self.catalog_path)]), 1)
                self.assertNotIn('SECRET', stderr.getvalue())
                self.assertNotIn('password', stderr.getvalue())

    def test_credential_url_in_prose_also_rejected(self):
        self.catalog['cards'][0]['one_sentence'] = '来源 https://example.org/?key=SECRET'
        with self.assertRaisesRegex(ValueError, '敏感查询'):
            self.check()

    def test_render_validates_before_creating_file(self):
        self.catalog['cards'].pop()
        self.save_catalog()
        target = self.root / 'never.md'
        with self.assertRaises(ValueError):
            ct.render(self.inventory_path, self.catalog_path, target)
        self.assertFalse(target.exists())

    def test_invalid_inventory_paths_and_hash(self):
        for field, value in (('relative_path', '../escape'), ('relative_path', 'C:/model'), ('sha256', 'abc')):
            with self.subTest(field=field, value=value):
                malformed = copy.deepcopy(self.inventory)
                malformed['files'][0][field] = value
                with self.assertRaises(ValueError):
                    ct.inventory_rows(malformed)


if __name__ == '__main__':
    unittest.main()
