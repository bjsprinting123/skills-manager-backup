import json
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch

import inventory_models as scanner


def weight(path, payload=b'1234'):
    header = json.dumps({'__metadata__': {'private_note': 'DO_NOT_EXPORT'},
                         'lokr_w1': {'dtype': 'F32', 'shape': [1],
                                     'data_offsets': [0, 4]}}).encode()
    path.write_bytes(struct.pack('<Q', len(header)) + header + payload)


class InventoryTests(unittest.TestCase):
    def test_same_size_is_not_duplicate_and_metadata_is_not_exported(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            weight(root / 'a.safetensors')
            weight(root / 'b.safetensors')
            weight(root / 'c.safetensors', b'5678')
            (root / 'broken.safetensors').write_bytes(b'bad')
            # Opaque pickle-like files are inventoried without being loaded.
            (root / 'opaque.pth').write_bytes(b'not a pickle')
            result = scanner.inventory(root, 'duplicates')
            self.assertEqual(result['file_count'], 5)
            self.assertEqual(result['hashed_count'], 3)
            self.assertEqual(result['status_counts'], {'ok': 4, 'error': 1})
            self.assertEqual(result['exact_duplicate_groups'][0]['files'],
                             ['a.safetensors', 'b.safetensors'])
            self.assertNotIn('DO_NOT_EXPORT', json.dumps(result))
            self.assertEqual(result['files'][0]['structure']['adapter_markers'], ['lokr_'])
            self.assertEqual(scanner.inventory(root)['hashed_count'], 0)

    def test_changes_during_hash_are_excluded(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            weight(root / 'a.safetensors')
            actual_hash = scanner.hash_file

            def mutate(path):
                digest = actual_hash(path)
                with path.open('ab') as stream:
                    stream.write(b'x')
                return digest

            with patch.object(scanner, 'hash_file', side_effect=mutate):
                result = scanner.inventory(root, 'all')
            self.assertEqual(result['hashed_count'], 0)
            self.assertEqual(result['files'][0]['status'], 'changed_during_hash')

    def test_huge_header_and_bad_offsets(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'huge.safetensors').write_bytes(struct.pack('<Q', 2**50))
            weight(root / 'short.safetensors', b'1')
            result = scanner.inventory(root, 'all')
            self.assertEqual(result['status_counts'], {'error': 2})
            self.assertEqual(result['hashed_count'], 0)


if __name__ == '__main__':
    unittest.main()
