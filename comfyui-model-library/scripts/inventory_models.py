"""Read-only weight inventory. Standard library only; never deserialize pickle."""
import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import struct

EXTENSIONS = {'.safetensors', '.sft', '.gguf', '.ckpt', '.pt', '.pth', '.bin', '.onnx'}
HEADER_LIMIT = 16 * 1024 * 1024
DIRECTORY_HINTS = {
    'loras': '适配器目录', 'checkpoints': 'checkpoint 目录',
    'diffusion_models': '扩散主模型目录', 'unet': '扩散主模型目录',
    'clip': '编码器目录', 'text_encoders': '文本编码器目录',
    'clip_vision': '视觉编码器目录', 'audio_encoders': '音频编码器目录',
    'vae': '编解码器目录', 'vae_approx': '近似编解码器目录',
    'controlnet': '控制模型目录', 'model_patches': '模型补丁目录',
    'upscale_models': '像素放大目录', 'latent_upscale_models': '潜空间放大目录',
    'detection': '检测器目录', 'embeddings': '嵌入目录', 'llm': '语言模型目录',
}


def linked(path):
    return path.is_symlink() or (hasattr(path, 'is_junction') and path.is_junction())


def structure(path, size):
    if path.suffix.lower() == '.gguf':
        with path.open('rb') as stream:
            raw = stream.read(24)
        if len(raw) != 24 or raw[:4] != b'GGUF':
            raise ValueError('invalid GGUF header')
        version, tensors, metadata = struct.unpack('<IQQ', raw[4:])
        return {'kind': 'gguf_minimal_header', 'version': version,
                'tensor_count': tensors, 'metadata_count': metadata}
    if path.suffix.lower() not in {'.safetensors', '.sft'}:
        return {'kind': 'not_inspected', 'reason': 'No executable deserialization'}
    with path.open('rb') as stream:
        prefix = stream.read(8)
        if len(prefix) != 8:
            raise ValueError('short safetensors header')
        length = struct.unpack('<Q', prefix)[0]
        if not 2 <= length <= min(HEADER_LIMIT, size - 8):
            raise ValueError('invalid or over-limit header length')
        header = json.loads(stream.read(length))
    if not isinstance(header, dict):
        raise ValueError('invalid tensor map')
    dtypes, markers, count = Counter(), set(), 0
    for key, value in header.items():
        if key == '__metadata__':
            continue  # Do not export arbitrary metadata, prompts or credentials.
        if not isinstance(value, dict) or not isinstance(value.get('dtype'), str):
            raise ValueError('invalid tensor descriptor')
        offsets, shape = value.get('data_offsets'), value.get('shape')
        if (not isinstance(offsets, list) or len(offsets) != 2
                or not all(isinstance(n, int) for n in offsets)
                or not 0 <= offsets[0] <= offsets[1] <= size - 8 - length
                or not isinstance(shape, list)
                or not all(isinstance(n, int) and n >= 0 for n in shape)):
            raise ValueError('invalid tensor bounds')
        count += 1
        dtypes[value['dtype']] += 1
        for marker in ('lora_', 'lora.', 'lokr_', 'hada_'):
            if marker in key.lower():
                markers.add(marker)
    return {'kind': 'safetensors_header', 'tensor_count': count,
            'dtype_tensor_counts': dict(dtypes), 'adapter_markers': sorted(markers),
            'note': 'Header summary only; not full payload or inference validation'}


def hash_file(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def inventory(root, hash_mode='none'):
    root = Path(os.path.abspath(root))
    if linked(root) or not root.exists():
        raise ValueError('Input must exist and cannot itself be a link or junction')
    base = root if root.is_dir() else root.parent
    paths, skipped = [], []
    if root.is_file():
        if root.suffix.lower() not in EXTENSIONS:
            raise ValueError('Unsupported weight extension')
        paths = [root]
    else:
        def walk_error(error):
            skipped.append({'path': str(error.filename), 'reason': type(error).__name__})
        for folder, dirs, names in os.walk(root, followlinks=False, onerror=walk_error):
            for name in dirs[:]:
                child = Path(folder) / name
                if linked(child):
                    dirs.remove(name)
                    skipped.append({'path': str(child), 'reason': 'linked_directory'})
            for name in names:
                child = Path(folder) / name
                if child.suffix.lower() in EXTENSIONS:
                    if linked(child):
                        skipped.append({'path': str(child), 'reason': 'linked_file'})
                    else:
                        paths.append(child)
    records, size_groups = [], defaultdict(list)
    for path in sorted(paths, key=lambda p: str(p).casefold()):
        relative = path.relative_to(base).as_posix()
        hint = next((DIRECTORY_HINTS[p.lower()] for p in path.parts
                     if p.lower() in DIRECTORY_HINTS), '无目录提示')
        row = {'path': str(path), 'relative_path': relative,
               'directory_hint': hint + '（未核实用途）', 'sha256': None}
        try:
            before = path.stat()
            row.update(size_bytes=before.st_size, mtime_ns=before.st_mtime_ns)
            row['structure'] = structure(path, before.st_size)
            after = path.stat()
            row['status'] = ('ok' if (before.st_size, before.st_mtime_ns)
                             == (after.st_size, after.st_mtime_ns) else 'changed_during_read')
        except (OSError, ValueError, TypeError, struct.error) as error:
            row.update(status='error', error_type=type(error).__name__)
        records.append(row)
        if row['status'] == 'ok':
            size_groups[row['size_bytes']].append(row)
    same_size = [[r['relative_path'] for r in rows]
                 for rows in size_groups.values() if len(rows) > 1]
    exact = defaultdict(list)
    for row in records:
        if row['status'] != 'ok' or hash_mode == 'none':
            continue
        if hash_mode == 'duplicates' and len(size_groups[row['size_bytes']]) < 2:
            continue
        path = Path(row['path'])
        try:
            digest = hash_file(path)
            after = path.stat()
            if (row['size_bytes'], row['mtime_ns']) != (after.st_size, after.st_mtime_ns):
                row['status'] = 'changed_during_hash'
            else:
                row['sha256'] = digest
                exact[digest].append(row['relative_path'])
        except OSError as error:
            row.update(status='hash_error', error_type=type(error).__name__)
    return {'schema_version': 1, 'root': str(base), 'input': str(root),
            'scanned_at': datetime.now(timezone.utc).isoformat(), 'hash_mode': hash_mode,
            'file_count': len(records), 'hashed_count': sum(bool(r['sha256']) for r in records),
            'status_counts': dict(Counter(r['status'] for r in records)),
            'total_bytes': sum(r.get('size_bytes', 0) for r in records),
            'files': records, 'skipped': skipped, 'same_size_candidates': same_size,
            'exact_duplicate_groups': [{'sha256': digest, 'files': names}
                                       for digest, names in exact.items() if len(names) > 1]}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('root', type=Path)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--hash', choices=['none', 'duplicates', 'all'], default='none')
    args = parser.parse_args()
    if args.out.suffix.lower() != '.json':
        parser.error('--out must be a JSON report, not a model file')
    result = inventory(args.root, args.hash)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({k: result[k] for k in ('file_count', 'hashed_count', 'status_counts', 'total_bytes')}, ensure_ascii=False))
