"""Bounded source-study calculations, never fortune predictions or ledger evidence.

The registry supplies reviewed provenance and conditions. Fixed handlers enforce its
versioned selector contract; a registry is not executable code or authorization.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path

import qizheng_rule_profiles as profiles

ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = ROOT / 'knowledge/qizheng-traditional-study.json'
SELECTORS = {
    'QZT01': 'palace_identity',
    'QZT02': 'dignity_terminology',
    'QZT03': 'aspect_vs_branch',
    'QZT04': 'qianyuan_natal_palace',
    'QZT05': 'qianyuan_limit_mansion',
}
# Review lock: changing evidence or conditions requires an explicit code review.
REGISTRY_SHA256 = '3ded3449332df41b33c675d4b07373b5251c4078bd85f42f8fdd9091bb60f0e4'
REGISTRY_CANONICAL_SHA256 = '2868e2a4b73df94c076440e2114cbc902b86134d7dcf2eb7468c92afa591bcc7'
BRANCHES = '子丑寅卯辰巳午未申酉戌亥'
FRAMES = ('ecliptic-of-date', 'j2000-ecliptic')
MANSION_LORDS = {row[0]: row[3] for row in profiles.engine.MANSIONS}
RELATIONS = {'同': '同我', '用': '我生', '仇': '我克', '难': '克我', '恩': '生我'}


def load_registry(path=REGISTRY_PATH):
    raw = Path(path).read_bytes()
    if hashlib.sha256(raw).hexdigest() != REGISTRY_SHA256:
        raise ValueError('registry bytes differ from reviewed evidence lock')
    return json.loads(raw.decode('utf-8'))


def _texts(value):
    return isinstance(value, list) and bool(value) and all(isinstance(x, str) and x.strip() for x in value)


def validate(data):
    """Return validation errors without executing an untrusted registry selector."""
    errors = []
    if not isinstance(data, dict):
        return ['registry must be an object']
    try:
        digest = hashlib.sha256(json.dumps(data, sort_keys=True, ensure_ascii=False,
                                         separators=(',', ':'), allow_nan=False).encode('utf-8')).hexdigest()
        if digest != REGISTRY_CANONICAL_SHA256:
            errors.append('registry metadata differs from reviewed evidence lock')
    except (ValueError, TypeError):
        errors.append('registry must contain finite JSON data')
    if type(data.get('schema_version')) is not int or data['schema_version'] != 1:
        errors.append('unsupported schema_version')
    sources = data.get('sources')
    source_ids = set()
    if not isinstance(sources, list) or not sources:
        errors.append('sources must be a nonempty list')
        sources = []
    for source in sources:
        if not isinstance(source, dict):
            errors.append('source must be an object')
            continue
        sid = source.get('id')
        if not isinstance(sid, str) or not sid or sid in source_ids:
            errors.append('missing or duplicate source id')
        else:
            source_ids.add(sid)
        url = source.get('url')
        if not isinstance(url, str) or not url.startswith(('https://', 'http://')):
            errors.append('source requires a source URL')
        if source.get('classical_quote_authorized', False) is not False:
            errors.append('study source cannot authorize classical quotation')
    cards = data.get('rule_cards')
    if not isinstance(cards, list):
        return errors + ['rule_cards must be a list']
    seen = set()
    for card in cards:
        if not isinstance(card, dict):
            errors.append('rule card must be an object')
            continue
        rid = card.get('id')
        if not isinstance(rid, str) or rid not in SELECTORS:
            errors.append('unknown rule id')
            continue
        if rid in seen:
            errors.append('duplicate rule id: ' + rid)
        seen.add(rid)
        if card.get('selector') != SELECTORS[rid]:
            errors.append('unsupported or tampered selector: ' + rid)
        for field in ('conditions', 'counterconditions', 'source_ids'):
            if not _texts(card.get(field)):
                errors.append(rid + ' requires ' + field)
        if _texts(card.get('source_ids')) and not set(card['source_ids']).issubset(source_ids):
            errors.append(rid + ' references an unknown source')
        if card.get('classical_quote_authorized', False) is not False:
            errors.append(rid + ' cannot authorize classical quotation')
    if seen != set(SELECTORS):
        errors.append('registry must contain all five supported rule cards')
    return errors


def _fields(facts, required):
    if not isinstance(facts, dict):
        raise ValueError('facts must be an object')
    if set(facts) != set(required):
        raise ValueError('required facts exactly: ' + ', '.join(required))


def _member(value, allowed, name):
    if isinstance(allowed, str):
        allowed = tuple(allowed)
    if not isinstance(value, str) or value not in allowed:
        raise ValueError('invalid or missing ' + name)
    return value


def _longitude(value):
    if type(value) not in (int, float) or not 0 <= value < 360 or not math.isfinite(value):
        raise ValueError('longitude must be finite, non-boolean, and in [0,360)')
    return value


def _palace(facts):
    _fields(facts, ('branch',))
    branch = _member(facts['branch'], BRANCHES, 'branch')
    return dict(status='conditional_study', calculation=profiles.palace_identity(branch),
                explanation='支五行与宫主是不同字段；本规则不将支五行替代宫主五行。')


def _dignity(facts):
    _fields(facts, ('term', 'scheme'))
    _member(facts['term'], ('庙', '乐', '垣'), 'term')
    _member(facts['scheme'], ('unresolved-legacy-compilation',), 'scheme')
    return dict(status='withheld', reason_code='terminology_conflict',
                explanation='旧汇编中庙、乐、垣的歌诀与表格口径未统一；尚无已核验的数值庙旺方案，不能合并或给出得地评分。')


def _aspect(facts):
    _fields(facts, ('longitude_a', 'longitude_b', 'branch_a', 'branch_b', 'coordinate_frame'))
    frame = _member(facts['coordinate_frame'], FRAMES, 'shared coordinate_frame')
    a, b = _longitude(facts['longitude_a']), _longitude(facts['longitude_b'])
    ba = _member(facts['branch_a'], BRANCHES, 'branch_a')
    bb = _member(facts['branch_b'], BRANCHES, 'branch_b')
    distance = abs(a - b)
    distance = min(distance, 360 - distance)
    delta = (BRANCHES.index(ba) - BRANCHES.index(bb)) % 12
    branch_relations = []
    if delta == 0:
        branch_relations.append('同支')
    if delta == 6:
        branch_relations.append('对宫')
    if delta in (2, 10):
        branch_relations.append('隔二宫')
    if delta in (4, 8):
        branch_relations.append('三方')
    if delta in (3, 6, 9):
        branch_relations.append('四正')
    return dict(status='conditional_study', calculation={
        'coordinate_frame': frame, 'separation_degrees': distance,
        'angular_residuals_degrees': {str(angle): abs(distance - angle) for angle in (60, 90, 120, 180)},
        'branch_a': ba, 'branch_b': bb, 'branch_relations': branch_relations,
        'angular_contact_judgment': 'not_evaluated_no_orb_contract'},
        explanation='角距残差与地支三方、四正、对宫分列；支位关系不证明精确角距，未设置容许度，也不判吉凶。')


def _reference(facts, context, basis, field):
    _fields(facts, ('context', 'reference_basis', field, 'other_element'))
    _member(facts['context'], (context,), 'context')
    _member(facts['reference_basis'], (basis,), 'reference_basis')
    other = _member(facts['other_element'], tuple(profiles.ELEMENTS), 'other_element')
    if basis == 'palace_lord':
        identity = profiles.palace_identity(_member(facts[field], BRANCHES, field))
        lord, phase = identity['palace_lord'], identity['palace_lord_element']
    else:
        mansion = _member(facts[field], MANSION_LORDS, field)
        lord = MANSION_LORDS[mansion]
        phase = profiles.engine.MANSION_WX_TO_PHASE[lord]
        identity = {'mansion': mansion, 'mansion_lord': lord}
    return dict(status='conditional_study', calculation=dict(identity, reference_basis=basis,
                context=context, reference_element=phase, other_element=other,
                relation=RELATIONS[profiles.relation(phase, other)]),
                explanation=('此本命研究规则以宫主为参照，不混用命度宿主。' if context == 'natal' else
                             '此行限研究规则仅对已提供的宿作假设分类，不计算实际行限、限度或应期；不能改取宫五行。'))


HANDLERS = {
    'palace_identity': _palace,
    'dignity_terminology': _dignity,
    'aspect_vs_branch': _aspect,
    'qianyuan_natal_palace': lambda f: _reference(f, 'natal', 'palace_lord', 'branch'),
    'qianyuan_limit_mansion': lambda f: _reference(f, 'limit', 'mansion_lord', 'mansion'),
}


def evaluate(rule_id, facts, registry=None):
    """Evaluate one explicit registered rule; malformed facts fail closed."""
    result = dict(rule_id=rule_id, status='withheld', scope='source_study_only',
                  predictive_validity='unvalidated', classical_quote_authorized=False,
                  personal_ledger_authorized=False)
    try:
        data = load_registry() if registry is None else registry
        errors = validate(data)
        if errors:
            result.update(reason_code='invalid_registry', reasons=errors)
            return result
        if not isinstance(rule_id, str) or rule_id not in SELECTORS:
            raise ValueError('unknown rule id; choose one explicit QZT01–QZT05 rule')
        card = next(c for c in data['rule_cards'] if c['id'] == rule_id)
        result.update(selector=card['selector'], title=card['title'],
                      plain_language=card['plain_language'], conditions=card['conditions'],
                      counterconditions=card['counterconditions'], source_ids=card['source_ids'],
                      sources=[s for s in data['sources'] if s['id'] in card['source_ids']],
                      source_locators=card.get('locators', []),
                      license=data.get('license'), attribution=data.get('attribution'),
                      changes=data.get('changes'))
        result.update(HANDLERS[card['selector']](facts))
    except (ValueError, TypeError, OSError) as exc:
        result.update(reason_code='invalid_or_missing_requirements', reason=str(exc))
    return result


def format_reading(result):
    """Render a bounded study result without dumping the registry's metadata."""
    title = result.get('title', '七政规则研究')
    lines = [str(result.get('rule_id', '')) + ' · ' + title]
    withheld = result.get('status') == 'withheld'
    lines.append('状态：暂不判定' if withheld else '状态：条件性研究演算')
    if result.get('plain_language'):
        lines.append('释义：' + result['plain_language'])
    calculation = result.get('calculation', {})
    if calculation:
        if 'zhi' in calculation:
            lines.append('宫位：%s宫；地支五行%s；宫主%s；宫主折合五行%s。' % (
                calculation['zhi'], calculation['branch_element'],
                calculation['palace_lord'], calculation['palace_lord_element']))
        if 'mansion' in calculation:
            lines.append('给定宿：%s；宿主%s；折合五行%s（项目约定）。' % (
                calculation['mansion'], calculation['mansion_lord'], calculation['reference_element']))
        if 'relation' in calculation:
            lines.append('参照：%s（%s）；另一五行%s，相对参照五行%s为“%s”。' % (
                calculation['reference_basis'], calculation['context'], calculation['other_element'],
                calculation['reference_element'], calculation['relation']))
        if 'separation_degrees' in calculation:
            lines.append('黄经差：%g°；共同坐标框架：%s。' % (
                calculation['separation_degrees'], calculation['coordinate_frame']))
            lines.append('角距残差：' + '；'.join('%s°目标差%g°' % (angle, residual)
                         for angle, residual in calculation['angular_residuals_degrees'].items()) + '。')
            relations = '、'.join(calculation['branch_relations']) or '未命中本卡列出的支位关系'
            lines.append('支位关系：%s与%s，%s；不等同于精确角距接触。' % (
                calculation['branch_a'], calculation['branch_b'], relations))
    if result.get('explanation'):
        lines.append('说明：' + result['explanation'])
    if result.get('reason'):
        lines.append('未判原因：' + result['reason'])
    lines.extend('未判原因：' + reason for reason in result.get('reasons', []))
    for label, field in [('条件', 'conditions'), ('反条件', 'counterconditions')]:
        lines.extend(label + '：' + value for value in result.get(field, []))
    levels = {
        'single_edition_scan_inspected': '单一版本影像已检查登记小节，非全书校勘',
        'unverified_digital_transcription': '数字转录，未对影像校勘',
        'modern_project_interpretation': '现代项目释义',
    }
    for source in result.get('sources', []):
        lines.append('来源：%s [%s]；%s' % (
            source.get('title', source['id']), levels.get(source.get('kind'), '来源层级未声明'), source['url']))
        if source.get('history_url'):
            lines.append('贡献历史：' + source['history_url'])
    lines.extend('定位：' + locator for locator in result.get('source_locators', []))
    if result.get('license'):
        lines.append('资料包许可：%s；署名：%s。' % (result['license'], result.get('attribution', '')))
        lines.append('许可全文：https://creativecommons.org/licenses/by-sa/4.0/legalcode')
    if result.get('changes'):
        lines.append('改编说明：' + result['changes'])
    lines.append('仅作来源研究；不授权古籍逐字引文或个人论断台账，预测有效性未经验证。')
    return '\n'.join(lines)


def parse_facts_json(raw):
    """Reject ambiguous JSON objects at every depth; dict API stays unchanged."""
    def unique_object(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError('duplicate JSON key in facts: ' + key)
            result[key] = value
        return result

    def reject_constant(value):
        raise ValueError('non-finite JSON constant in facts: ' + value)

    return json.loads(raw, object_pairs_hook=unique_object,
                      parse_constant=reject_constant)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--registry', default=str(REGISTRY_PATH))
    sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('validate')
    ev = sub.add_parser('evaluate')
    ev.add_argument('--format', choices=('json', 'text'), default='json')
    ev.add_argument('--rule-id', required=True, choices=tuple(SELECTORS))
    ev.add_argument('--facts', required=True, help='JSON object, or @path to a JSON file')
    args = parser.parse_args(argv)
    try:
        registry = load_registry(args.registry)
        if args.command == 'validate':
            errors = validate(registry)
            output = {'valid': not errors, 'errors': errors}
            code = 1 if errors else 0
        else:
            raw = Path(args.facts[1:]).read_text(encoding='utf-8') if args.facts.startswith('@') else args.facts
            output = evaluate(args.rule_id, parse_facts_json(raw), registry)
            code = 1 if output['status'] == 'withheld' else 0
    except (ValueError, OSError) as exc:
        output, code = {'status': 'withheld', 'reason': str(exc)}, 1
    if args.command == 'evaluate' and args.format == 'text':
        print(format_reading(output))
    else:
        print(json.dumps(output, ensure_ascii=False, indent=2, allow_nan=False))
    return code


if __name__ == '__main__':
    raise SystemExit(main())
