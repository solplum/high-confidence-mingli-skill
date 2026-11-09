#!/usr/bin/env python3
"""Local knowledge provenance gate. No network, code execution or predictive rating.

Exit 0 success, 1 refused/invalid catalog, 2 input error. A passing catalog proves
only the checks described here, never authenticity, copyright ownership or truth.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys

SYSTEMS = {'bazi', 'ziwei', 'qizheng'}
MODES = {'paraphrase', 'source_excerpt', 'classical_quote'}
MODULE_ONLY = 'conditional_module_only'
REVIEWED_PROFILES = {
    'bazi-reviewed-structure-v1': {
        'system': 'bazi', 'source_id': 'bazi-reviewed-structure-source',
        'records': {'bazi-reviewed-BZ-K%02d' % i: 'BZ-K%02d' % i for i in range(1, 5)},
    },
    'ziwei-reviewed-structure-v1': {
        'system': 'ziwei', 'source_id': 'ziwei-reviewed-structure-source',
        'records': dict(zip([
            'ziwei-reviewed-ZW-K01', 'ziwei-reviewed-ZW-K02-groups',
            'ziwei-reviewed-ZW-K02-fubi', 'ziwei-reviewed-ZW-K03',
            'ziwei-reviewed-ZW-K04', 'ziwei-reviewed-ZW-K05-attachment',
            'ziwei-reviewed-ZW-K05-lu'],
            ['ZW-K01', 'ZW-K02', 'ZW-K02', 'ZW-K03', 'ZW-K04', 'ZW-K05', 'ZW-K05'])),
    },
}


def validate_reviewed_record(record, source, sources, root):
    """Pin the approved module cards without promoting them to ledger rules."""
    profile_name = record.get('profile')
    profile = REVIEWED_PROFILES.get(profile_name) if isinstance(profile_name, str) else None
    rid = record['id']
    if not profile:
        return [rid + ': module source requires its approved profile']
    errors = []
    if (record.get('system') != profile['system'] or
            record.get('source_id') != profile['source_id'] or
            record.get('rule_id') != profile['records'].get(rid)):
        errors.append(rid + ': unapproved module record, system or source')
    if (not source or source.get('kind') != 'project_guidance' or
            source.get('usage_scope') != MODULE_ONLY or record.get('usage_scope') != MODULE_ONLY):
        errors.append(rid + ': conditional module-only scope required')
    for key in ('conditions', 'exclusions'):
        values = record.get(key)
        if not isinstance(values, list) or not values or not all(isinstance(v, str) and v.strip() for v in values):
            errors.append(rid + ': complete ' + key + ' required')
    try:
        span = record['source_span']
        a, b = span['start_line'], span['end_line']
        lines = local_file(root, source['path']).read_text(encoding='utf-8').splitlines()
        if type(a) is not int or type(b) is not int or a != b or not 1 <= a <= len(lines) or lines[a-1] != '项目释义：' + record['summary']:
            errors.append(rid + ': exact module paraphrase line required')
    except (KeyError, TypeError, ValueError, OSError):
        errors.append(rid + ': invalid module source span')
    primary = record.get('primary_sources')
    if not isinstance(primary, list) or not primary:
        return errors + [rid + ': primary source locators required']
    for row in primary:
        if not isinstance(row, dict):
            errors.append(rid + ': invalid primary source'); continue
        item = sources.get(row.get('source_id')) if isinstance(row.get('source_id'), str) else None
        if not item or item.get('system') != record.get('system') or item.get('id') == record.get('source_id'):
            errors.append(rid + ': missing or cross-system primary source'); continue
        if not isinstance(row.get('locator'), str) or not row['locator'].strip():
            errors.append(rid + ': primary locator required')
        if 'start_line' in row or 'end_line' in row:
            a, b = row.get('start_line'), row.get('end_line')
            try:
                total = len(local_file(root, item['path']).read_text(encoding='utf-8').splitlines())
                if type(a) is not int or type(b) is not int or not 1 <= a <= b <= total:
                    errors.append(rid + ': invalid primary line range')
            except (ValueError, OSError, KeyError):
                errors.append(rid + ': unreadable primary source')
        if 'artifact_sha256' in row:
            value = row['artifact_sha256']
            if not isinstance(value, str) or len(value) != 64 or any(c not in '0123456789abcdef' for c in value):
                errors.append(rid + ': invalid primary artifact hash')
    return errors


def local_file(root, value):
    if not isinstance(value, str) or not value or Path(value).is_absolute():
        raise ValueError('Expected a relative file path')
    path = (Path(root).resolve() / value).resolve()
    try:
        path.relative_to(Path(root).resolve())
    except ValueError:
        raise ValueError('Path escapes root')
    if not path.is_file():
        raise ValueError('File does not exist: ' + value)
    return path


def validate_quotation_packet(root, packet):
    """Fail closed on any unreviewed packet bytes, files or quotation budget.

    This is a review manifest, not automatic plagiarism/copyright detection.
    Updating its approved hashes requires reviewing all changed material.
    """
    try:
        manifest_path = local_file(root, packet['manifest_path'])
        raw = manifest_path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != packet['sha256']:
            return ['quotation packet manifest hash mismatch']
        manifest = json.loads(raw)
        base = manifest_path.parent
        actual = set()
        for path in base.rglob('*'):
            if path.is_symlink():
                return ['quotation packet symlink not allowed']
            if path.is_file() and path != manifest_path:
                actual.add(path.relative_to(base).as_posix())
        files = manifest['files']
        if actual != set(files):
            return ['quotation packet unreviewed or missing files']
        total = 0
        for name, info in files.items():
            source = local_file(base, name)
            data = source.read_bytes()
            if hashlib.sha256(data).hexdigest() != info['sha256']:
                return ['quotation packet unreviewed bytes: ' + name]
            lines = data.decode('utf-8').splitlines()
            seen = set()
            for span in info['quote_spans']:
                line, prefix = span['line'], span['prefix']
                if type(line) is not int or not 1 <= line <= len(lines) or line in seen:
                    return ['quotation packet invalid quote line']
                seen.add(line)
                if not isinstance(prefix, str) or not lines[line-1].startswith(prefix):
                    return ['quotation packet quote prefix mismatch']
                total += len(lines[line-1][len(prefix):])
        if type(manifest['max_quoted_characters']) is not int or not 0 <= total <= manifest['max_quoted_characters']:
            return ['quotation packet aggregate quotation budget exceeded']
        if total != manifest['reviewed_quoted_characters']:
            return ['quotation packet reviewed total mismatch']
        return []
    except (KeyError, ValueError, TypeError, OSError) as exc:
        return ['quotation packet invalid: ' + str(exc)]


def validate(catalog, root):
    errors = []
    if not isinstance(catalog, dict) or type(catalog.get('schema_version')) is not int or catalog['schema_version'] != 1:
        return ['Expected catalog schema_version 1']
    if not isinstance(catalog.get('sources'), list) or not isinstance(catalog.get('records'), list):
        return ['sources and records must be arrays']
    for packet in catalog.get('quotation_packets', []):
        errors.extend(validate_quotation_packet(root, packet))
    sources = {}
    for src in catalog['sources']:
        if not isinstance(src, dict) or not isinstance(src.get('id'), str) or not src['id']:
            errors.append('Invalid source id'); continue
        sid = src['id']
        if sid in sources:
            errors.append('Duplicate source: ' + sid)
        sources[sid] = src
        if not isinstance(src.get('system'), str) or src.get('system') not in SYSTEMS:
            errors.append(sid + ': invalid system')
        if not isinstance(src.get('kind'), str) or src.get('kind') not in {'modern_compilation', 'implementation_reference', 'digital_transcription', 'classical_edition', 'project_guidance'}:
            errors.append(sid + ': invalid source kind')
        if type(src.get('classical_quote_verified')) is not bool:
            errors.append(sid + ': classical_quote_verified must be a boolean')
        for key in ['citation_label', 'upstream_url', 'provenance_status', 'license_scope']:
            if not isinstance(src.get(key), str) or not src[key].strip():
                errors.append(sid + ': missing ' + key)
        try:
            raw = local_file(root, src.get('path')).read_bytes()
            raw.decode('utf-8')
            if hashlib.sha256(raw).hexdigest() != src.get('sha256'):
                errors.append(sid + ': source hash mismatch')
            local_file(root, src.get('license_path'))
        except (ValueError, OSError) as exc:
            errors.append(sid + ': ' + str(exc))
        if src.get('license_id') == 'CC-BY-SA-4.0':
            for key in ['license_url', 'attribution', 'contributors_url', 'change_notice']:
                if not isinstance(src.get(key), str) or not src[key].strip():
                    errors.append(sid + ': missing redistribution ' + key)
        if src.get('classical_quote_verified') is True:
            errors.append(sid + ': classical quotation disabled: self-declared edition or verification record is not external verification')
    ids = set()
    for rec in catalog['records']:
        if not isinstance(rec, dict) or not isinstance(rec.get('id'), str) or not rec['id']:
            errors.append('Invalid record id'); continue
        rid = rec['id']
        if rid in ids:
            errors.append('Duplicate record: ' + rid)
        ids.add(rid)
        source = sources.get(rec.get('source_id')) if isinstance(rec.get('source_id'), str) else None
        if not source or source.get('system') != rec.get('system'):
            errors.append(rid + ': missing or cross-system source')
        if not isinstance(rec.get('status'), str) or rec.get('status') not in {'usable', 'quarantined'}:
            errors.append(rid + ': invalid status')
        for key in ['summary', 'title', 'profile', 'limitations']:
            if not isinstance(rec.get(key), str) or not rec[key].strip():
                errors.append(rid + ': missing ' + key)
        if rec.get('content_kind') != 'project_paraphrase':
            errors.append(rid + ': v1 records only support project_paraphrase')
        if rec.get('status') == 'quarantined' and not rec.get('reason'):
            errors.append(rid + ': quarantine reason required')
        if rec.get('status') == 'quarantined':
            span = rec.get('source_span')
            if not isinstance(span, dict) or type(span.get('start_line')) is not int or type(span.get('end_line')) is not int or not 1 <= span['start_line'] <= span['end_line']:
                errors.append(rid + ': valid quarantine source_span required')
            elif source:
                try:
                    total = len(local_file(root, source['path']).read_text(encoding='utf-8').splitlines())
                    if span['end_line'] > total:
                        errors.append(rid + ': quarantine source_span exceeds file')
                except (ValueError, OSError):
                    errors.append(rid + ': unreadable quarantine source')

        if rec.get('usage_scope') == 'conditional_traditional_interpretation':
            if not source or source.get('kind') != 'project_guidance' or rec.get('profile') != 'bazi-traditional-conditional':
                errors.append(rid + ': restricted interpretation must reference project guidance')
            if rec.get('interpretation_label') != '未校勘数字转录的传统规则释义（项目整理，非预测验证）':
                errors.append(rid + ': restricted interpretation label missing')
            for key in ['conditions', 'exclusions']:
                if not isinstance(rec.get(key), list) or not rec[key] or not all(isinstance(v, str) and v.strip() for v in rec[key]):
                    errors.append(rid + ': restricted interpretation requires ' + key)
            try:
                span = rec['source_span']
                a, b = span['start_line'], span['end_line']
                lines = local_file(root, source['path']).read_text(encoding='utf-8').splitlines()
                if type(a) is not int or type(b) is not int or a != b or not 1 <= a <= len(lines) or lines[a-1] != '项目释义：' + rec['summary']:
                    errors.append(rid + ': restricted interpretation must pin one exact paraphrase line')
            except (KeyError, TypeError, ValueError, OSError):
                errors.append(rid + ': invalid restricted interpretation span')

        if (isinstance(rec.get('profile'), str) and rec['profile'] in REVIEWED_PROFILES) or (source and source.get('usage_scope') == MODULE_ONLY):
            errors.extend(validate_reviewed_record(rec, source, sources, root))
        if not isinstance(rec.get('topics'), list) or not all(isinstance(v, str) and v for v in rec['topics']):
            errors.append(rid + ': invalid topics')
    return errors


def query(catalog, system, profile, term=''):
    """Exact profile match. Unknown profiles are not wildcards."""
    return [r for r in catalog['records']
            if r['status'] == 'usable' and r['system'] == system and r['profile'] == profile
            and (not term or term.casefold() in (' '.join(r['topics']) + r['title'] + r['summary']).casefold())]


def citation(catalog, root, source_id, mode='paraphrase', start=None, end=None):
    """Callers must validate first. Source-level quotation gate is fail-closed."""
    if mode not in MODES:
        raise ValueError('Unknown citation mode')
    source = next((s for s in catalog['sources'] if s['id'] == source_id), None)
    if source is None:
        raise ValueError('Unknown source')
    if mode == 'classical_quote':
        raise ValueError('Classical quotation refused: this release has no externally verified editions; metadata cannot enable this mode')
    result = dict(source_id=source_id, mode=mode, label=source['citation_label'],
                  path=source['path'], sha256=source['sha256'], upstream_url=source['upstream_url'],
                  edition=source.get('edition'), provenance_status=source['provenance_status'],
                  warning='Hash and text matching do not authenticate a classical edition or prove predictive validity.')
    result.update(license_path=source['license_path'], license_scope=source['license_scope'],
                  license_notice=local_file(root, source['license_path']).read_text(encoding='utf-8'),
                  revision=source.get('revision'))
    for key in ['license_id', 'license_url', 'attribution', 'contributors_url', 'change_notice']:
        if key in source:
            result[key] = source[key]
    if mode in {'source_excerpt', 'classical_quote'}:
        lines = local_file(root, source['path']).read_text(encoding='utf-8').splitlines()
        if type(start) is not int or type(end) is not int or not 1 <= start <= end <= len(lines):
            raise ValueError('Valid start/end lines required')
        if end - start > 9:
            raise ValueError('Excerpt limited to 10 lines; use the source document for reading')
        result.update(start_line=start, end_line=end, text='\n'.join(lines[start-1:end]))
        if mode == 'source_excerpt':
            result['warning'] += ' This is an excerpt from the registered digital source, not an authenticated quotation of the named ancient book.'
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', default=str(Path(__file__).resolve().parents[1]))
    parser.add_argument('--catalog', default='knowledge/catalog.json')
    commands = parser.add_subparsers(dest='command', required=True)
    commands.add_parser('validate')
    q = commands.add_parser('query')
    q.add_argument('--system', choices=sorted(SYSTEMS), required=True)
    q.add_argument('--profile', required=True)
    q.add_argument('--term', default='')
    c = commands.add_parser('cite')
    c.add_argument('--source', required=True)
    c.add_argument('--mode', choices=sorted(MODES), default='paraphrase')
    c.add_argument('--start', type=int); c.add_argument('--end', type=int)
    args = parser.parse_args(argv)
    try:
        catalog = json.loads(local_file(args.root, args.catalog).read_text(encoding='utf-8'))
        errors = validate(catalog, args.root)
        if errors:
            print(json.dumps({'ok': False, 'errors': errors}, ensure_ascii=False, indent=2)); return 1
        if args.command == 'validate':
            result = {'ok': True, 'sources': len(catalog['sources']), 'records': len(catalog['records']), 'scope': 'file integrity and metadata only'}
        elif args.command == 'query':
            records = query(catalog, args.system, args.profile, args.term)
            result = {'ok': True, 'matches': records, 'status': 'found' if records else 'insufficient', 'warning': 'Records are project paraphrases, not classical quotations. Check chart facts and exceptions before applying.'}
        else:
            try:
                result = {'ok': True, 'citation': citation(catalog, args.root, args.source, args.mode, args.start, args.end)}
            except ValueError as exc:
                print(json.dumps({'ok': False, 'refused': str(exc)}, ensure_ascii=False, indent=2)); return 1
        print(json.dumps(result, ensure_ascii=False, indent=2)); return 0
    except (ValueError, OSError, TypeError) as exc:
        print(json.dumps({'ok': False, 'input_error': str(exc)}, ensure_ascii=False, indent=2)); return 2


TRADITIONAL_USE = 'conditional_traditional_interpretation'
TRADITIONAL_LABEL = '未校勘数字转录的传统规则释义（项目整理，非预测验证）'


def interpretation_record(rule, source, catalog):
    """Whitelist one exact project-paraphrase line, never the raw transcription."""
    if rule.get('reading_use') != TRADITIONAL_USE:
        return None
    rec = next((r for r in catalog['records'] if r['id'] == rule.get('catalog_record_id')), None)
    if not rec or rec.get('usage_scope') != TRADITIONAL_USE or rec.get('status') != 'usable' or rec.get('profile') != 'bazi-traditional-conditional':
        return None
    registered = next((s for s in catalog['sources'] if s['id'] == rec['source_id']), None)
    if not registered or registered['sha256'] != source.get('sha256') or registered['kind'] != 'project_guidance':
        return None
    span = rec.get('source_span', {})
    if rule.get('start_line') != span.get('start_line') or rule.get('end_line') != span.get('end_line'):
        return None
    if rule.get('quote') != rec['summary'] or rule.get('system') != rec['system']:
        return None
    if rule.get('interpretation_label') != TRADITIONAL_LABEL or rule.get('predictive_status') != 'unvalidated':
        return None
    if rule.get('authenticity_status') != 'uncollated_digital_transcription' or rule.get('guaranteed_prediction') is not False:
        return None
    return rec


def check_ledger_rule(rule, source, catalog):
    """Known source ranges are blocked; unknown sources require explicit labeling.

    This is a provenance consistency check, not authentication of caller-owned
    files or proof of semantic applicability. Classical quotations are disabled.
    """
    errors = []
    locator = rule.get('locator', '')
    permitted = interpretation_record(rule, source, catalog)
    if rule.get('reading_use') == TRADITIONAL_USE and permitted is None:
        errors.append('conditional interpretation requires exact registered paraphrase and unvalidated attribution')
    matches = [s for s in catalog['sources'] if s['sha256'] == source.get('sha256')]
    named = [s for s in catalog['sources'] if isinstance(locator, str) and s['path'] in locator]
    if named and any(s not in matches for s in named):
        errors.append('registered source locator has a different hash; register the changed source as unverified')
    if not matches:
        if rule.get('attribution_kind') != 'caller_declared_unverified':
            errors.append('unknown source requires attribution_kind=caller_declared_unverified; register before claiming verified provenance')
        if rule.get('source_label') != '调用方提供的未核验资料（非核验古籍原文）':
            errors.append('unknown source requires the unverified source_label')
        return errors
    for item in matches:
        if item.get('usage_scope') == MODULE_ONLY:
            errors.append('conditional module-only source requires native module evidence and review; not authorized as a general ledger rule')
        if rule.get('attribution_kind') != 'registered_source_excerpt':
            errors.append('known unverified source requires attribution_kind=registered_source_excerpt; not an original classical quotation')
        if rule.get('source_label') != item['citation_label']:
            errors.append('known unverified source requires its registered source_label')
        if permitted is not None:
            metadata = rule.get('redistribution')
            required = ['license_id', 'license_url', 'attribution', 'contributors_url',
                        'change_notice', 'upstream_url', 'revision']
            if not isinstance(metadata, dict) or any(metadata.get(key) != item.get(key) for key in required):
                errors.append('restricted interpretation requires unchanged redistribution attribution and license metadata')
            if not isinstance(metadata, dict) or not isinstance(metadata.get('license_notice'), str) or not metadata['license_notice'].strip():
                errors.append('restricted interpretation requires full redistribution license_notice')
        start, end = rule.get('start_line'), rule.get('end_line')
        if type(start) is not int or type(end) is not int or not 1 <= start <= end:
            errors.append('known source requires valid start_line/end_line')
            continue
        for record in catalog['records']:
            if record['source_id'] == item['id'] and record['status'] == 'quarantined':
                span = record.get('source_span')
                if span and start <= span['end_line'] and end >= span['start_line'] and permitted is None:
                    errors.append('quarantined source range cannot support a reading: ' + record['id'])
    return errors


if __name__ == "__main__":
    sys.exit(main())
