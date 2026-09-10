"""Prepare, validate and render report files only; never scan or load models."""
import argparse
from collections import Counter
from datetime import datetime
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import sys
from urllib.parse import parse_qsl, unquote, urlsplit


UNKNOWN = '未知（尚未核实）'
HASH = re.compile(r'[0-9a-fA-F]{64}\Z')
URL = re.compile(r'https?://[^\s<>"\']+', re.IGNORECASE)
SENSITIVE_QUERY = re.compile(r'token|secret|password|passwd|signature|credential|authorization|apikey|accesskey|privatekey', re.I)
DIRECTIONS = [
    '核对原作者或发布仓库、精确版本及文件；本地哈希本身不证明来源',
    '使用可信发布记录的完整 SHA256 比对；没有证据时保留未知',
    '核实用途、底模与任务、编码器/VAE、加载器和触发词',
    '逐段核实名称；区分量化、蒸馏、少步适配器与运行时加速',
    '记录收益、代价、限制及字段来源；未实测不宣称性能提升',
]
TEXT_FIELDS = ('role', 'one_sentence', 'use_when', 'suggested_name')
GROUPS = {
    'compatibility': ('base', 'task', 'encoder_vae', 'loader'),
    'usage': ('trigger', 'weight', 'steps', 'scheduler_cfg_shift'),
    'acceleration': ('kind', 'benefit', 'tradeoff'),
}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(value):
    return isinstance(value, str) and bool(HASH.fullmatch(value))


def nonempty(value):
    return isinstance(value, str) and bool(value.strip())


def safe_url(value):
    """Do not echo rejected URLs: they may contain a real credential."""
    require(nonempty(value), '来源 URL 不能为空')
    require(not any(c.isspace() or c in '<>' for c in value), '来源 URL 含不安全字符')
    try:
        parsed = urlsplit(value)
        require(parsed.scheme.lower() in {'http', 'https'} and parsed.hostname, '来源 URL 必须为完整 HTTP(S) URL')
        require(parsed.username is None and parsed.password is None, '拒绝含用户凭据的 URL')
        parsed.port  # Reject malformed ports without reproducing the input.
        for key, _ in parse_qsl(parsed.query, keep_blank_values=True):
            normalized = re.sub(r'[^a-z0-9]', '', unquote(key).lower())
            require(normalized not in {'key', 'sig', 'auth'} and not SENSITIVE_QUERY.search(normalized),
                    '拒绝含敏感查询参数的 URL；请使用不带凭据的来源页')
    except (ValueError, UnicodeError) as error:
        if isinstance(error, ValueError) and str(error).startswith(('拒绝', '来源')):
            raise
        raise ValueError('来源 URL 无效；已隐藏原始值') from None
    return value


def check_urls(value):
    if isinstance(value, str):
        for match in URL.finditer(value):
            safe_url(match.group())
    elif isinstance(value, dict):
        for key, item in value.items():
            check_urls(key)
            check_urls(item)
    elif isinstance(value, list):
        for item in value:
            check_urls(item)


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, 'JSON 包含重复字段')
        result[key] = value
    return result


def read_json(path):
    path = Path(path)
    require(path.suffix.lower() == '.json', '输入必须为 JSON 报告文件')
    raw = path.read_bytes()
    try:
        value = json.loads(raw.decode('utf-8-sig'), object_pairs_hook=unique_object)
    except (UnicodeError, json.JSONDecodeError):
        raise ValueError('输入不是有效的 UTF-8 JSON 报告') from None
    require(isinstance(value, dict), 'JSON 报告顶层必须为对象')
    return value, hashlib.sha256(raw).hexdigest()


def inventory_rows(inventory):
    require(type(inventory.get('schema_version')) is int and inventory['schema_version'] == 1,
            'inventory schema_version 必须为 1')
    require(isinstance(inventory.get('files'), list), 'inventory.files 必须为列表')
    require(isinstance(inventory.get('skipped', []), list), 'inventory.skipped 必须为列表')
    rows = {}
    for row in inventory['files']:
        require(isinstance(row, dict), 'inventory 文件记录必须为对象')
        path = row.get('relative_path')
        require(nonempty(path) and '\\' not in path and ':' not in path and
                not PurePosixPath(path).is_absolute() and
                all(part not in {'', '.', '..'} for part in path.split('/')),
                'inventory 必须使用规范的相对路径')
        require(path not in rows, 'inventory 包含重复相对路径')
        require(nonempty(row.get('status')), 'inventory 文件状态缺失')
        require(row.get('sha256') is None or digest(row['sha256']), 'inventory SHA256 必须为完整摘要或 null')
        rows[path] = row
    return rows


def blank_card(path):
    return {
        'files': [path],
        'identity': {'status': 'unknown', 'sha256': None, 'publisher': UNKNOWN,
                     'version': UNKNOWN, 'remote_file': UNKNOWN},
        'role': UNKNOWN, 'one_sentence': UNKNOWN, 'use_when': UNKNOWN,
        'compatibility': {key: UNKNOWN for key in GROUPS['compatibility']},
        'name_parts': {},
        'usage': {key: UNKNOWN for key in GROUPS['usage']},
        'acceleration': {'kind': 'unknown', 'benefit': UNKNOWN, 'tradeoff': UNKNOWN},
        'limitations': ['占位卡尚未完成来源与用途研究；未执行模型加载、生成或性能测试'],
        'sources': [], 'tested': {'load': False, 'generation': False, 'performance': False},
        'suggested_name': '保持原名；用途与引用影响尚未核实',
    }


def validate_data(inventory, snapshot_hash, catalog):
    rows = inventory_rows(inventory)
    require(type(catalog.get('schema_version')) is int and catalog['schema_version'] == 1,
            'catalog schema_version 必须为 1')
    require(catalog.get('inventory_sha256') == snapshot_hash,
            'inventory 快照不匹配；catalog 必须绑定本次输入文件的原始字节')
    require(isinstance(catalog.get('cards'), list), 'catalog.cards 必须为列表')
    check_urls(catalog)
    covered = []
    for card in catalog['cards']:
        require(isinstance(card, dict), '每张卡必须为对象')
        files = card.get('files')
        require(isinstance(files, list) and files and all(isinstance(p, str) for p in files),
                '每张卡必须包含非空 files 路径列表')
        require(all(path in rows for path in files), 'catalog 含清单外路径')
        covered.extend(files)
        local = [rows[path] for path in files]
        if len(files) > 1:
            require(all(row['status'] == 'ok' and digest(row.get('sha256')) for row in local)
                    and len({row['sha256'].lower() for row in local}) == 1,
                    '共享卡必须所有本地文件状态为 ok 且完整 SHA256 一致；同大小不足以共享')
        identity = card.get('identity')
        require(isinstance(identity, dict) and identity.get('status') in {'unknown', 'partial', 'verified'},
                'identity.status 必须为 unknown、partial 或 verified')
        require(identity.get('sha256') is None or digest(identity['sha256']), 'identity.sha256 必须为完整摘要或 null')
        for field in ('publisher', 'version', 'remote_file'):
            require(isinstance(identity.get(field), str), 'identity 文本字段缺失')
        for field in TEXT_FIELDS:
            require(nonempty(card.get(field)), '卡片用途/命名字段不能为空；未核实请填未知原因')
        for group, fields in GROUPS.items():
            require(isinstance(card.get(group), dict) and all(nonempty(card[group].get(key)) for key in fields),
                    '卡片搭配/用法/加速字段缺失；未核实请填未知原因')
        require(card['acceleration']['kind'] in {'none', 'few_step_adapter', 'distilled_base', 'quantization', 'runtime', 'unknown'},
                'acceleration.kind 不受支持')
        require(isinstance(card.get('name_parts'), dict) and all(isinstance(v, str) for v in card['name_parts'].values()),
                'name_parts 必须为文本映射')
        require(isinstance(card.get('limitations'), list) and all(isinstance(v, str) for v in card['limitations']),
                'limitations 必须为文本列表')
        require(isinstance(card.get('tested'), dict) and
                all(type(card['tested'].get(key)) is bool for key in ('load', 'generation', 'performance')),
                'tested 三项必须为布尔值；未实测填 false')
        sources = card.get('sources')
        require(isinstance(sources, list), 'sources 必须为列表')
        identity_sources = []
        for source in sources:
            require(isinstance(source, dict), '来源记录必须为对象')
            safe_url(source.get('url'))
            require(all(nonempty(source.get(key)) for key in ('publisher', 'version_or_revision', 'checked_at')),
                    '来源必须记录 publisher、version_or_revision 和 checked_at')
            try:
                datetime.fromisoformat(source['checked_at'].replace('Z', '+00:00'))
            except ValueError:
                raise ValueError('checked_at 必须为 ISO 日期或时间') from None
            supports = source.get('supports')
            require(isinstance(supports, list) and supports and all(nonempty(v) for v in supports),
                    '来源 supports 必须为非空字段列表')
            require(source.get('file_sha256') is None or digest(source['file_sha256']),
                    '来源 file_sha256 必须为完整摘要或 null')
            if 'identity' in supports:
                identity_sources.append(source)
        if identity['status'] == 'verified':
            require(digest(identity.get('sha256')), 'verified 身份必须有完整 SHA256')
            expected = identity['sha256'].lower()
            require(all(row['status'] == 'ok' and digest(row.get('sha256'))
                        and row['sha256'].lower() == expected for row in local),
                    '异常、变化、无完整哈希或哈希不匹配的文件不能认证为 verified')
            require(identity_sources and all(digest(source.get('file_sha256')) and
                    source['file_sha256'].lower() == expected for source in identity_sources),
                    'verified 缺少与本地完整 SHA256 一致且 supports 含 identity 的来源证据')
    require(Counter(covered) == Counter(rows.keys()), '清单每个路径必须被恰好一张卡覆盖；存在缺失或重复')
    return rows


def text(value):
    value = str(value).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
    return re.sub(r'([\\`*_{}\[\]()#+.!|])', r'\\\1', value).replace('\n', '<br>')


def markdown(inventory, snapshot_hash, catalog):
    rows = validate_data(inventory, snapshot_hash, catalog)
    counts = Counter(card['identity']['status'] for card in catalog['cards'])
    lines = ['# 模型库说明', '',
             '> 研究草稿：占位卡不是完成报告。结构验证仅检查快照、覆盖和证据字段一致性，不证明来源或描述真实。', '',
             f'- 清单文件：{len(rows)}；模型卡：{len(catalog["cards"])}（不是逻辑模型数量）。',
             f'- 异常文件：{sum(row["status"] != "ok" for row in rows.values())}；跳过项：{len(inventory.get("skipped", []))}（不计入模型卡）。',
             f'- 身份状态：已核实 {counts["verified"]}；部分核实 {counts["partial"]}；未知 {counts["unknown"]}。',
             f'- 原始 inventory 文件 SHA256：`{snapshot_hash}`',
             '- 本工具没有扫描、下载、加载、生成、改名或删除任何模型；实测标记由研究者填写，本工具不验证实测记录。', '']
    status_names = {'unknown': '未知', 'partial': '部分核实', 'verified': '已核实（仅证据字段校验通过）'}
    labels = {
        'role': '角色', 'one_sentence': '一句话用途', 'use_when': '适用场景', 'suggested_name': '建议名称',
        'base': '底模', 'task': '任务', 'encoder_vae': '编码器 / VAE', 'loader': '加载器',
        'trigger': '触发词', 'weight': '权重', 'steps': '步数', 'scheduler_cfg_shift': '采样器 / CFG / Shift',
        'kind': '加速类别', 'benefit': '预期收益', 'tradeoff': '代价',
    }
    for number, card in enumerate(catalog['cards'], 1):
        lines += [f'## {number}. {text(PurePosixPath(card["files"][0]).name)}', '',
                  '| 文件（相对路径） | 文件状态 | 本地完整 SHA256 |', '|---|---|---|']
        for path in card['files']:
            row = rows[path]
            lines.append(f'| {text(path)} | {text(row["status"])} | {row.get("sha256") or "未计算"} |')
        ident = card['identity']
        lines += ['', f'身份：{status_names[ident["status"]]}；发布者：{text(ident["publisher"])}；版本：{text(ident["version"])}。',
                  f'上游文件：{text(ident["remote_file"])}；身份声明 SHA256：{ident.get("sha256") or "未知"}。', '']
        for field in TEXT_FIELDS[:-1]:
            lines.append(f'- {labels[field]}：{text(card[field])}')
        for group, title in (('compatibility', '搭配与兼容性'), ('usage', '用法'), ('acceleration', '加速说明')):
            lines += ['', f'### {title}', '']
            lines += [f'- {labels[key]}：{text(card[group][key])}' for key in GROUPS[group]]
        lines += ['', '### 名称含义', '']
        lines += ([f'- {text(key)}：{text(value)}' for key, value in card['name_parts'].items()] or [UNKNOWN])
        lines += ['', '### 限制与实测', '']
        lines += [f'- {text(value)}' for value in card['limitations']] or ['- 未记录；不代表无限制。']
        lines += ['- ' + '；'.join(f'{label}：{"研究者标记已实测" if card["tested"][key] else "未实测"}'
                  for key, label in (('load', '加载'), ('generation', '生成'), ('performance', '性能'))),
                  f'- 建议名称：{text(card["suggested_name"])}（仅建议，不执行改名）', '', '### 来源与字段依据', '']
        if not card['sources']:
            lines.append('未知：尚未收集可核查来源。')
        for source in card['sources']:
            lines += [f'- <{source["url"]}>',
                      f'  - 发布者：{text(source["publisher"])}；版本 / revision：{text(source["version_or_revision"])}；核查时间：{text(source["checked_at"])}',
                      f'  - 支持字段：{text("、".join(source["supports"]))}；来源文件 SHA256：{source.get("file_sha256") or "未提供"}']
        lines.append('')
    return '\n'.join(lines) + '\n'


def write_new(path, content):
    with Path(path).open('x', encoding='utf-8', newline='\n') as stream:
        stream.write(content)


def prepare(inventory_path, out):
    inventory, snapshot_hash = read_json(inventory_path)
    rows = inventory_rows(inventory)
    catalog = {'schema_version': 1, 'inventory_sha256': snapshot_hash,
               'cards': [blank_card(path) for path in rows]}
    tasks = {'schema_version': 1, 'inventory_sha256': snapshot_hash, 'tasks': [
        {'relative_path': path, 'sha256': row.get('sha256'), 'basename': PurePosixPath(path).name,
         'file_status': row['status'], 'research_directions': DIRECTIONS +
         (['文件异常或扫描时变化：先解决清单异常，不得认证身份'] if row['status'] != 'ok' else [])}
        for path, row in rows.items()]}
    check_urls(tasks)
    report = markdown(inventory, snapshot_hash, catalog)
    out = Path(out)
    out.mkdir()  # Fail if any file, directory or link already occupies this path.
    write_new(out / 'catalog.json', json.dumps(catalog, ensure_ascii=False, indent=2) + '\n')
    write_new(out / 'research_tasks.json', json.dumps(tasks, ensure_ascii=False, indent=2) + '\n')
    write_new(out / '模型库说明.md', report)
    return len(rows)


def validate(inventory_path, catalog_path):
    inventory, snapshot_hash = read_json(inventory_path)
    catalog, _ = read_json(catalog_path)
    validate_data(inventory, snapshot_hash, catalog)
    return inventory, snapshot_hash, catalog


def render(inventory_path, catalog_path, out):
    require(Path(out).suffix.lower() == '.md', 'render 输出必须为新建的 .md 报告')
    inventory, snapshot_hash, catalog = validate(inventory_path, catalog_path)
    write_new(out, markdown(inventory, snapshot_hash, catalog))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    for command in ('prepare', 'validate', 'render'):
        sub = commands.add_parser(command)
        sub.add_argument('inventory', type=Path)
        if command != 'prepare':
            sub.add_argument('catalog', type=Path)
        if command != 'validate':
            sub.add_argument('--out', type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == 'prepare':
            count = prepare(args.inventory, args.out)
            print(f'已创建 {count} 张未知占位卡与待查任务；这不是完成报告。')
        elif args.command == 'validate':
            validate(args.inventory, args.catalog)
            print('结构验证通过；未验证来源真实性，也未实测模型。')
        else:
            render(args.inventory, args.catalog, args.out)
            print('中文报告已写入新文件；未验证来源真实性，也未实测模型。')
        return 0
    except (OSError, ValueError, TypeError, KeyError) as error:
        message = str(error) if isinstance(error, ValueError) else type(error).__name__
        print(f'失败：{message}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
