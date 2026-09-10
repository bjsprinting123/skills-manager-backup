"""Inventory owner: refresh writes metadata; readers only read JSON/stat known paths."""
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
import tempfile
from pathlib import Path

RELATIVE_PATH = Path('索引数据/model-locality-index.json')
LABELS = {'local_unique':'本地1份（登记路径）','local_multiple':'本地多份（登记路径）',
          'not_local':'非本地：仅资料／下载候选','quarantined':'隔离保留：不用于加载',
          'outside_root':'模型目录外：不作为已安装','path_missing':'登记路径失效',
          'stale':'库存待刷新','unknown':'库存未核对'}

def _read(path):
    return json.loads(Path(path).read_text('utf-8-sig'))

def _key(path):
    return os.path.normcase(str(Path(path).resolve()))

def _stamp(path):
    s=Path(path).stat()
    return [s.st_size,s.st_mtime_ns,s.st_ino]

def _digest(index):
    return hashlib.sha256(json.dumps(index['models'],sort_keys=True,ensure_ascii=False).encode()).hexdigest()

def unknown(reason, checked_at=None, previous=None):
    return dict(status='stale' if previous else 'unknown',label=LABELS['stale' if previous else 'unknown'],
                is_local=False,is_local_unique=False,eligible_for_local_cleanup=False,
                local_file_count=None,checked_at=checked_at,reason=reason,last_known_status=previous)

def refresh(library_root, models_root, quarantine_roots=()):
    """Explicit owner action. Does not load/hash/move/delete model weights or publish cards."""
    spec=importlib.util.spec_from_file_location('inventory_scanner',Path(__file__).with_name('inventory_models.py'))
    scanner=importlib.util.module_from_spec(spec);spec.loader.exec_module(scanner)
    EXTENSIONS,linked=scanner.EXTENSIONS,scanner.linked
    root=Path(library_root).resolve();models=Path(models_root).resolve()
    if not models.is_dir():raise ValueError('models_root must exist')
    index=_read(root/'索引数据/model-index.json');watch={};found=set();quarantine=[Path(p).resolve() for p in quarantine_roots]
    # Enumerate names/metadata only during owner refresh, never in the reader.
    for base,dirs,files in os.walk(models):
        dirs[:]=sorted(d for d in dirs if not linked(Path(base)/d))
        watch[str(Path(base))]=_stamp(base)
        found.update(_key(Path(base)/f) for f in files if Path(f).suffix.lower() in EXTENSIONS)
    records={};registered=set()
    now=datetime.now(timezone.utc).isoformat()
    for entry in index['models']:
        source=(root/next(p for p in entry['paths'] if p.endswith('.json'))).resolve()
        if not source.is_relative_to(root):raise ValueError('card path outside library')
        c=_read(source)['contribution'];m=c['model'];inside=[];outside=[];missing=[]
        for f in m['local_files']:
            p=Path(f['path']).resolve()
            if not p.is_file():missing.append(str(p));watch[str(p)]=None;continue
            watch[str(p)]=_stamp(p)
            if p.is_relative_to(models):inside.append(str(p));registered.add(_key(p))
            else:outside.append(str(p))
        inside=list({_key(p):p for p in inside}.values());outside=list({_key(p):p for p in outside}.values())
        if missing:state='path_missing'
        elif inside:state='local_unique' if len(inside)==1 else 'local_multiple'
        elif outside:state='quarantined' if all(any(Path(p).is_relative_to(q) for q in quarantine) for p in outside) else 'outside_root'
        else:state='not_local'
        records[m['model_id']]=dict(status=state,label=LABELS[state],is_local=state in ['local_unique','local_multiple'],
            is_local_unique=state=='local_unique',eligible_for_local_cleanup=state in ['local_unique','local_multiple'],
            local_file_count=len(inside),local_paths=inside,outside_paths=outside,missing_paths=missing,
            sha256=m['sha256'],card_revision=entry['current_revision'],checked_at=now)
        records[m['model_id']]['uniqueness_scope']='模型根目录内的已登记现存路径数，不是全盘内容去重或功能唯一证明'
        records[m['model_id']]['content_hash_rechecked']=False
    result=dict(schema_version=1,owner='comfyui-model-library',models_root=str(models),
        model_index_digest=_digest(index),checked_at=now,quarantine_roots=[str(p) for p in quarantine],uniqueness_scope='existing registered paths inside configured models_root; not unique function or byte-deduplication proof',
        unregistered_paths=sorted(found-registered),records=records,watch=watch)
    # Unknown files cannot be silently attached to a card by their filename.
    for r in records.values():r['unregistered_files_present']=bool(result['unregistered_paths'])
    path=root/RELATIVE_PATH
    with tempfile.NamedTemporaryFile(mode='w',encoding='utf-8',dir=path.parent,prefix='inventory-',suffix='.tmp',delete=False) as stream:
        json.dump(result,stream,ensure_ascii=False,indent=2);tmp=Path(stream.name)
    tmp.replace(path)
    return result

def read_state(library_root, index=None, models_root=None):
    """Fail closed when snapshot/index/known metadata changed; no model bytes read."""
    root=Path(library_root).resolve();path=root/RELATIVE_PATH
    try:
        if path.stat().st_size>16*1024*1024:raise ValueError('inventory index too large')
        d=_read(path)
        if d.get('schema_version')!=1 or d.get('owner')!='comfyui-model-library':raise ValueError('inventory schema/owner mismatch')
        if not isinstance(d.get('records'),dict) or not isinstance(d.get('watch'),dict):raise ValueError('inventory structure invalid')
        current=index if index is not None else _read(root/'索引数据/model-index.json')
        if set(d['records'])!={row['model_id'] for row in current['models']}:
            raise ValueError('inventory coverage does not match model index')
        reason=None
        if _digest(current)!=d['model_index_digest']:reason='模型卡索引已变更'
        elif models_root is not None and _key(models_root)!=_key(d['models_root']):reason='模型根目录与库存快照不同'
        else:
            for p,stamp in d['watch'].items():
                try:actual=_stamp(p)
                except OSError:actual=None
                if actual!=stamp:reason='已登记文件或模型目录元数据变更';break
        records={}
        for mid,row in d['records'].items():
            if row.get('status') not in LABELS:raise ValueError('inventory record status invalid')
            records[mid]=unknown(reason,d['checked_at'],row['status']) if reason else row
        return dict(fresh=reason is None,status='stale' if reason else 'fresh',reason=reason,
                    checked_at=d['checked_at'],records=records,unregistered_paths=d.get('unregistered_paths',[]))
    except (OSError,ValueError,TypeError,KeyError):
        return dict(fresh=False,status='unknown',reason='库存快照缺失或无效，需要模型库skill刷新',checked_at=None,records={},unregistered_paths=[])

if __name__=='__main__':
    parser=argparse.ArgumentParser(description='Refresh or inspect the separate local inventory snapshot')
    parser.add_argument('action',choices=['refresh','show']);parser.add_argument('library_root',type=Path)
    parser.add_argument('--models-root',type=Path);parser.add_argument('--quarantine-root',action='append',default=[])
    args=parser.parse_args()
    if args.action=='refresh':
        if args.models_root is None:parser.error('refresh requires --models-root')
        d=refresh(args.library_root,args.models_root,args.quarantine_root)
        from collections import Counter
        print(json.dumps({'records':len(d['records']),'states':dict(Counter(r['status'] for r in d['records'].values())),'unregistered_files':len(d['unregistered_paths'])},ensure_ascii=False))
    else:print(json.dumps(read_state(args.library_root,models_root=args.models_root),ensure_ascii=False))
