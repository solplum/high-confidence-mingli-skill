#!/usr/bin/env python3
"""Load the exact approved cards for native structural panels, not ledger rules."""
import argparse
import copy
import json
from pathlib import Path

import knowledge_catalog as knowledge

ROOT = Path(__file__).resolve().parents[1]
STARS = ['紫微', '天机', '太阳', '武曲', '天同', '廉贞', '天府', '太阴',
         '贪狼', '巨门', '天相', '天梁', '七杀', '破军']


def _catalog(root):
    root = Path(root or ROOT)
    try:
        data = json.loads((root / 'knowledge/catalog.json').read_text(encoding='utf-8'))
        errors = knowledge.validate(data, root)
        if errors:
            raise ValueError('来源登记检查失败：' + '; '.join(errors))
        return root, data
    except (OSError, KeyError, TypeError, ValueError) as exc:
        raise ValueError('无法加载受限结构资料：' + str(exc)) from exc


def _with_citation(record, catalog):
    row = copy.deepcopy(record)
    source = next(s for s in catalog['sources'] if s['id'] == row['source_id'])
    row['citation'] = {
        'record_id': row['id'], 'source_id': source['id'],
        'source_label': source['citation_label'], 'path': source['path'],
        'source_span': row.get('source_span'), 'sha256': source['sha256'],
        'revision': source.get('revision'),
        'locator': source['path'] + ' / ' + str(row.get('locator', row.get('source_span', ''))),
        'attribution_kind': 'project_paraphrase',
        'license_path': source['license_path'], 'license_scope': source['license_scope'],
        'upstream_url': source['upstream_url'],
        'primary_sources': row.get('primary_sources', []),
    }
    return row


def _records(system, profile, expected_ids, catalog):
    contract = knowledge.REVIEWED_PROFILES.get(profile)
    if not contract or contract['system'] != system:
        raise ValueError('未批准的体系或结构profile')
    expected = set(expected_ids)
    if expected != set(contract['records']):
        raise ValueError('模块请求的记录集不符合已批准范围')
    rows = knowledge.query(catalog, system, profile)
    if {r['id'] for r in rows} != expected or len(rows) != len(expected):
        raise ValueError('受限结构记录缺失、隔离或重复')
    return [_with_citation(r, catalog) for r in rows]


def load_profile(system, profile, expected_ids, root=None):
    """Validate source bytes on each call; return detached records and citations."""
    _, catalog = _catalog(root)
    return _records(system, profile, expected_ids, catalog)


def _star_themes(catalog):
    rows = [r for r in knowledge.query(catalog, 'ziwei', 'ziwei-domain-conditional') if r.get('star')]
    if len(rows) != len(STARS) or any(
            len([r for r in rows if r['id'] == 'ziwei-domain-star-' + str(i)
                 and r.get('star') == star and isinstance(r.get('theme'), str) and r['theme']]) != 1
            for i, star in enumerate(STARS)):
        raise ValueError('既有主星主题登记不完整')
    return [_with_citation(r, catalog) for r in rows]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--system', choices=('bazi', 'ziwei'), required=True)
    parser.add_argument('--profile', required=True)
    parser.add_argument('--root', default=str(ROOT))
    args = parser.parse_args(argv)
    try:
        _, catalog = _catalog(args.root)
        contract = knowledge.REVIEWED_PROFILES.get(args.profile)
        if not contract:
            raise ValueError('未批准的结构profile')
        result = {'records': _records(args.system, args.profile, contract['records'], catalog)}
        if args.system == 'ziwei':
            result['star_themes'] = _star_themes(catalog)
        print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
        return 0
    except (ValueError, OSError, KeyError, TypeError) as exc:
        print(json.dumps({'error': str(exc)}, ensure_ascii=False))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
