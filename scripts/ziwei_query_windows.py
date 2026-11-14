#!/usr/bin/env python3
"""Map Ziwei civil-date fact windows onto actual query instants."""

import argparse
from datetime import date, datetime, time, timedelta
import json
from pathlib import Path
import re
import subprocess

from time_scenarios import (
    TICK, UTC, check_timezone_source, civil_date_range_spans, civil_shichen_hours,
    fixed_offset_spans, iana_query_zone, parse_query_point, resolve_query_endpoint, timezone_provenance,
)


PLANNER = Path(__file__).with_name('ziwei_dynamic_windows.mjs')
FIRST_DATE, EXCLUSIVE_LIMIT = date(1901, 1, 1), date(2100, 1, 1)
# ISO query offsets can exceed the numeric birth option's 14-hour limit.
OFFSET_CEILING = timedelta(days=1)


def _label_plan(spans, layer):
    first = min(left.date() for left, _ in spans)
    last = max((right - TICK).date() for _, right in spans)
    result = subprocess.run([
        'node', str(PLANNER), '--start', first.isoformat(),
        '--end', (last + timedelta(days=1)).isoformat(), '--layer', layer,
    ], capture_output=True, text=True)
    if result.returncode:
        raise ValueError(result.stderr.strip() or '紫微日期标签分段未完成')
    return json.loads(result.stdout)


def _calendar_intersections(spans, label_windows, layer):
    for left, right in spans:
        for calendar in label_windows:
            start = max(left, datetime.fromisoformat(calendar['start_inclusive']).replace(tzinfo=left.tzinfo))
            end = min(right, datetime.fromisoformat(calendar['end_exclusive']).replace(tzinfo=left.tzinfo))
            if start >= end:
                continue
            if layer == 'day':
                # The locked adapter gates its daily combination at late Zi.
                late_zi = start.replace(hour=23, minute=0, second=0, microsecond=0)
                if start < late_zi < end:
                    yield start, late_zi, calendar
                    start = late_zi
            yield start, end, calendar


def _probe_at(start, tz):
    return dict(target_date=start.date().isoformat(), target_time_index=(start.hour + 1) // 2,
                civil_time=start.isoformat(), fold=start.astimezone(tz).fold if tz else 0)


def _project(spans, label_windows, tz, layer):
    segments = []
    previous_end, previous_calendar, previous_late_zi = None, None, None
    for start, end, calendar in _calendar_intersections(spans, label_windows, layer):
        index = (start.hour + 1) // 2
        late_zi = index == 12
        if previous_end is None:
            reasons = ['query_start']
        else:
            reasons = []
            if previous_end != start:
                reasons.append('civil_date_membership_gap')
            elif previous_end.utcoffset() != start.utcoffset():
                reasons.append('iana_utc_offset_change')
            if previous_calendar != calendar:
                reasons.append('calendar_window_change')
            if layer == 'day' and previous_late_zi != late_zi:
                reasons.append('late_zi_day_gate_change')
        segments.append(dict(
            start_inclusive=start.isoformat(), end_exclusive=end.isoformat(),
            boundary_reasons=reasons,
            calendar_window={key: value for key, value in calendar.items() if key != 'probe'},
            probe=_probe_at(start, tz),
        ))
        previous_end, previous_calendar, previous_late_zi = end, calendar, late_zi
    return segments


def query_windows(start_text, end_text, layer, zone=None, *, start_fold=None, end_fold=None,
                  _resolved_zone=None):
    start, end = parse_query_point(start_text), parse_query_point(end_text)
    if not (FIRST_DATE <= start.date() < EXCLUSIVE_LIMIT and FIRST_DATE <= end.date() <= EXCLUSIVE_LIMIT):
        raise ValueError('紫微查询使用 1901–2099 年民用日期，2100-01-01 仅用于排除终点')
    tz = _resolved_zone
    if tz is None and zone is not None:
        tz = iana_query_zone(zone)
    date_range = (tz is not None and start_text == start.date().isoformat() and
                  end_text == end.date().isoformat() and start_fold is None and end_fold is None)
    if date_range:
        spans = civil_date_range_spans(start.date(), end.date(), zone=zone, resolved_zone=tz)
    else:
        if tz is not None:
            start = resolve_query_endpoint(start, zone, tz, start_fold, '--start')
            end = resolve_query_endpoint(end, zone, tz, end_fold, '--end')
        else:
            if start_fold is not None or end_fold is not None:
                raise ValueError('--start-fold 和 --end-fold 仅用于 --timezone')
            if start.utcoffset() is None or start.utcoffset() != end.utcoffset():
                raise ValueError('查询起止须带同一明确 UTC 偏移，或提供 IANA 时区')
        if start.astimezone(UTC) >= end.astimezone(UTC):
            raise ValueError('查询起点须早于终点')
        spans = fixed_offset_spans(start, end, tz) if tz is not None else [(start, end)]
    if not spans:
        raise ValueError('所给民用日期范围无可达查询时刻')
    plan = _label_plan(spans, layer)
    requested = dict(start=start_text, end=end_text,
                     kind='civil_date_membership' if date_range else 'physical_interval')
    if start_fold is not None:
        requested['start_fold'] = start_fold
    if end_fold is not None:
        requested['end_fold'] = end_fold
    return dict(
        schema_version='ziwei-query-windows-v1', profile=plan['profile'], layer=layer,
        interval_semantics='physical_start_inclusive_end_exclusive_on_query_civil_clock',
        scope=plan['scope'], requested=requested,
        timezone=zone, provenance=dict(plan['provenance'], timezone_source=timezone_provenance(zone, resolved_zone=tz)),
        segments=_project(spans, plan['segments'], tz, layer),
    )


def _same_query_point(point, probe, require_civil=False):
    if (not isinstance(point, dict) or point.get('solar_date') != probe['target_date'] or
            type(point.get('time_index')) is not int or point['time_index'] != probe['target_time_index']):
        return False
    if 'civil_time' not in point:
        return not require_civil
    try:
        return parse_query_point(point['civil_time']).isoformat() == probe['civil_time']
    except (AttributeError, TypeError, ValueError):
        return False


def _retains_transformations(rows, transformations, layer):
    if not isinstance(rows, list):
        return False
    projected = [item for item in rows if isinstance(item, dict) and item.get('layer') == layer]
    if len(projected) != len(transformations):
        return False
    for original in transformations:
        match = next((item for item in projected if item.get('kind') == original['kind']), {})
        if any(key not in match or match[key] != value for key, value in original.items()):
            return False
    return True


def _dynamic_coordinate_matches(coordinate, branch, palace):
    from ziwei_life_reading import BRANCHES, _integer, _name

    if not isinstance(coordinate, dict) or not _integer(branch, 0, 11):
        return False
    index = (branch - BRANCHES.index('寅')) % 12
    path = f'/research_dynamic_iztro/source_astrolabe/palaces/{index}'
    return (_integer(coordinate.get('branch_index'), 0, 11) and coordinate['branch_index'] == branch and
            _integer(coordinate.get('iztro_array_index'), 0, 11) and coordinate['iztro_array_index'] == index and
            coordinate.get('earthly_branch') == BRANCHES[branch] and
            _name(coordinate.get('natal_palace')) == _name(palace) and
            coordinate.get('raw_pointer', path) == path)


def _dynamic_coordinates_match(row, domains, calendar, layer):
    from ziwei_life_reading import NAMES, _effective_lunar_month, _integer, _name

    natal = {domain['branch']: _name(domain['domain']) for domain in domains}
    yearly_ming = (calendar['lunarYear'] - 4) % 12
    ming = yearly_ming
    if layer == 'monthly':
        natal_ming = next((branch for branch, name in natal.items() if name == '命'), None)
        if natal_ming is None:
            return False
        # The locked natal soul branch is effective birth month + 1 - birth
        # shichen. Substitute this in the same locked monthly palace formula.
        ming = (yearly_ming + _effective_lunar_month(calendar) + 1 - natal_ming) % 12
    coordinates = row.get('domain_coordinates')
    if (ming not in natal or not _dynamic_coordinate_matches(row.get('ming_coordinate'), ming, natal[ming]) or
            not isinstance(coordinates, list) or len(coordinates) != 12):
        return False
    observed = {}
    for domain in coordinates:
        coordinate = domain.get('natal_coordinate') if isinstance(domain, dict) else None
        branch = coordinate.get('branch_index') if isinstance(coordinate, dict) else None
        if not _integer(branch, 0, 11) or branch not in natal or not _dynamic_coordinate_matches(
                coordinate, branch, natal[branch]):
            return False
        observed[branch] = _name(domain.get('layer_palace_name'))
    return observed == {branch: NAMES[(branch - ming) % 12] for branch in range(12)}


def _dynamic_source_attachments_match(transformations, layer):
    from ziwei_life_reading import KINDS

    saved_paths = set()
    prefix = f'/admitted_dynamic_facts/layers/{layer}/transformations/'
    valid_paths = {prefix + str(index) for index in range(4)}
    raw_layer = f'/research_dynamic_iztro/raw_horoscope/{layer}/mutagen/'
    for item in transformations:
        if 'source_path' in item:
            path = item['source_path']
            # The admitted array may have been stored in a different order;
            # the raw mutagen index below is fixed by the kind.
            if not isinstance(path, str) or path not in valid_paths or path in saved_paths:
                return False
            saved_paths.add(path)
        if 'admitted_attachment' not in item:
            continue
        attachment = item['admitted_attachment']
        raw_path = raw_layer + str(KINDS.index(item['kind']))
        if (not isinstance(attachment, dict) or attachment.get('kind') != item['kind'] or
                attachment.get('star') != item['star'] or attachment.get('raw_pointer', raw_path) != raw_path):
            return False
        locations = attachment.get('natal_star_locations')
        if not isinstance(locations, list) or len(locations) != 1 or not isinstance(locations[0], dict):
            return False
        location, = locations
        coordinate = location.get('location')
        fact = item['fact']
        if (location.get('name') != item['star'] or
                not _dynamic_coordinate_matches(coordinate, fact['branch'], fact['domain'])):
            return False
        if 'raw_pointer' in location:
            palace_path = f"/research_dynamic_iztro/source_astrolabe/palaces/{coordinate['iztro_array_index']}"
            pointer = location['raw_pointer']
            group = 'majorStars' if fact['type'] == 'major' else '(?:minorStars|adjectiveStars)'
            if not isinstance(pointer, str) or not re.fullmatch(
                    palace_path + '/' + group + r'/(?:0|[1-9][0-9]*)', pointer):
                return False
    return True


def _dynamic_layer_coverage(panel, point_facts, profile, segment, layer, require_civil, fixed_transformations):
    from ziwei_life_reading import KINDS, STEMS, dynamic_layer_pillar

    probe = segment['probe']
    dynamic = panel.get('dynamic') or {}
    row = (dynamic.get('layers') or {}).get(layer) or {}
    if (dynamic.get('profile') != profile or dynamic.get('full_interval_coverage') is not False or
            dynamic.get('status') not in ('admitted', 'partial') or
            row.get('status') != 'admitted'):
        return 'withheld'
    transformations = row.get('transformations')
    if (not isinstance(transformations, list) or len(transformations) != 4 or
            not all(isinstance(item, dict) and item.get('layer') == layer for item in transformations)):
        return 'withheld'
    kinds = [item.get('kind') for item in transformations]
    if any(kind not in kinds for kind in '禄权科忌'):
        return 'withheld'
    point = dynamic.get('query_point')
    require_civil = require_civil or (isinstance(point, dict) and 'civil_time' in point)
    if (not _same_query_point(point, probe, require_civil) or
            any(not _same_query_point(item.get('query_point'), probe, require_civil) for item in transformations)):
        return 'point_mismatch'
    calendar = segment['calendar_window']['calendar_at_start']
    stem, branch = dynamic_layer_pillar(calendar, layer)
    if ((row.get('heavenly_stem'), row.get('earthly_branch')) != (stem, branch) or
            not _dynamic_coordinates_match(row, panel['domains'], calendar, layer) or
            any(item.get('star') != fixed_transformations[STEMS.index(stem)][KINDS.index(item['kind'])] or
                item.get('id') != layer + '.' + item['kind'] or item.get('fact') not in point_facts or
                item.get('star') != item['fact'].get('name') for item in transformations) or
            not _dynamic_source_attachments_match(transformations, layer) or
            not _retains_transformations(dynamic.get('transformations'), transformations, layer) or
            not _retains_transformations(panel.get('transformations'), transformations, layer)):
        return 'withheld'
    return 'admitted'


def _load_life_topic_sources():
    import reviewed_knowledge as knowledge
    from ziwei_life_reading import PROFILE, RECORD_IDS, _card

    _, catalog = knowledge._catalog(None)
    records = knowledge._records('ziwei', PROFILE, RECORD_IDS, catalog)
    themes = {row['star']: row for row in knowledge._star_themes(catalog)}
    if any(not isinstance(row.get('question'), str) or not row['question'].strip() for row in themes.values()):
        raise ValueError('既有十四主星反证问题登记不完整')
    contexts = [row for row in catalog['records'] if row.get('system') == 'ziwei'
                and row.get('profile') == 'ziwei-domain-conditional'
                and row.get('status') == 'usable' and not row.get('star')]
    four_palace_citation = None
    if len(contexts) == 2 and {row['id'] for row in contexts} == {'ziwei-domain-domains', 'ziwei-domain-brightness'}:
        domain = next(row for row in contexts if row['id'] == 'ziwei-domain-domains')
        four_palace_citation = knowledge._with_citation(domain, catalog)['citation']
    return {row['rule_id']: _card(row) for row in records}, themes, four_palace_citation


def _same_transform_topic(rows, expected):
    if not isinstance(rows, list):
        return False
    matches = [row for row in rows if isinstance(row, dict) and
               (row.get('layer'), row.get('kind')) == (expected['layer'], expected['kind'])]
    return matches == [expected]


def _matches_registered_card(recorded, card):
    return isinstance(recorded, dict) and all(
        recorded.get(key) == value for key, value in card.items()
        if key not in ('rows', 'status', 'unresolved'))


def _domain_evidence(row):
    return {key: row[key] for key in ('domain', 'branch', 'facts')}


def _checked_domain_topic(panel, row, card, themes, four_palace_citation):
    from ziwei_life_reading import _domain

    if panel.get('temporal_uncertainty') is not False or panel.get('source_errors'):
        return False
    try:
        expected = _domain(dict(name=row['domain'], branch=row['branch']), row['facts'], themes, card, False)
    except (AttributeError, KeyError, TypeError, ValueError):
        return False
    if card is None:
        return four_palace_citation is not None and row == dict(expected, citation=four_palace_citation)
    modules = panel.get('modules')
    recorded = modules.get(card['rule_id']) if isinstance(modules, dict) else None
    if not _matches_registered_card(recorded, card):
        return False
    return (row == expected and recorded.get('rows') == [expected] and
            recorded.get('status') == expected['status'] and recorded.get('unresolved') == expected['missing_conditions'])


def _natal_domain_topic_coverage(panel, natal_panel, sources):
    from ziwei_life_reading import DOMAIN_RULES, _name

    four_palaces = ('命', '财帛', '官禄', '迁移')
    domain_rules = {**DOMAIN_RULES, **dict.fromkeys(four_palaces)}
    statuses = dict.fromkeys(domain_rules, 'unverified' if panel is None else 'withheld')
    if panel is not None and sources:
        cards, themes, four_palace_citation = sources
        for domain, rule in domain_rules.items():
            card = cards.get(rule)
            if (rule is not None and card is None) or (rule is None and four_palace_citation is None):
                continue
            rows = [[row for row in owner['domains'] if _name(row['domain']) == domain]
                    for owner in (panel, natal_panel)]
            if all(len(matches) == 1 and _checked_domain_topic(owner, matches[0], card, themes, four_palace_citation)
                   for owner, matches in zip((panel, natal_panel), rows)):
                statuses[domain] = 'facts_only' if rows[0][0]['empty_palace'] else 'verified'
    return ({rule: statuses[domain] for domain, rule in DOMAIN_RULES.items()},
            {domain: statuses[domain] for domain in four_palaces})


def _checked_transform_topic(panel, original, cards, themes, uncertain):
    from ziwei_life_reading import KINDS, _transform_topics

    modules = panel.get('modules')
    rule = 'ZW-E%02d' % (KINDS.index(original['kind']) + 1)
    if not cards or not isinstance(modules, dict) or panel.get('source_errors'):
        return 'withheld'
    card = cards[rule]
    recorded = modules.get(rule)
    if not _matches_registered_card(recorded, card):
        return 'withheld'
    expected, = _transform_topics([original], {rule: dict(card, rows=[])}, themes, uncertain)
    if (_same_transform_topic(panel.get('transformations'), expected) and
            _same_transform_topic(recorded.get('rows'), expected)):
        return 'verified' if expected['status'] == 'conditional' else expected['status']
    return 'withheld'


def _transform_topic_coverage(panel, natal_panel, layer_status, sources):
    from ziwei_life_reading import KINDS

    results = {layer: dict.fromkeys(KINDS, 'unverified') for layer in layer_status}
    if panel is None:
        return results
    cards, themes, _ = sources or ({}, {}, None)
    uncertain = any(owner.get('temporal_uncertainty') is not False for owner in (panel, natal_panel))
    fact_fields = {'id', 'layer', 'kind', 'star', 'fact', 'source_path', 'admitted_attachment', 'query_point'}
    for layer, status in layer_status.items():
        if status != 'admitted':
            continue
        result = results[layer]
        result.update(dict.fromkeys(KINDS, 'withheld'))
        for original in panel['dynamic']['layers'][layer]['transformations']:
            # Replay from the native attachment, with no saved topic fields in the input.
            # A legacy row may omit its projected index while retaining the
            # independently checked native mutagen path.
            missing_projection = (original.keys() == fact_fields - {'source_path'} and
                                  'raw_pointer' in original['admitted_attachment'])
            if original.keys() == fact_fields or missing_projection:
                result[original['kind']] = _checked_transform_topic(panel, original, cards, themes, uncertain)
    return results


def _transform_component_coverage(panel, natal_panel, point_facts, layer_status, topic_status, sources, table, stem):
    from ziwei_life_reading import KINDS, _components, _natal_transforms, _same_identity

    layers = ['natal', *layer_status]
    result = dict(layers=layers, incomplete_layers=layers[:], groups=[], withheld_groups=[],
                  recorded_status='unverified')
    natal_topics = dict.fromkeys(KINDS, 'unverified')
    if panel is None:
        return result, natal_topics

    cards, themes, _ = sources or ({}, {}, None)
    uncertain = any(owner.get('temporal_uncertainty') is not False for owner in (panel, natal_panel))
    natal, errors = [], True
    if stem is not None:
        try:
            natal, errors = _natal_transforms(dict(lunarInfo=dict(yearStem=stem)), point_facts, table)
        except (AttributeError, KeyError, TypeError, ValueError, IndexError):
            pass
    inputs = [(row, _checked_transform_topic(panel, row, cards, themes, uncertain)) for row in natal]
    natal_topics.update((row['kind'], status) for row, status in inputs)
    incomplete = ['natal'] if errors else []
    for layer, status in layer_status.items():
        if status == 'admitted':
            inputs.extend((row, topic_status[layer][row['kind']])
                          for row in panel['dynamic']['layers'][layer]['transformations'])
        else:
            incomplete.append(layer)

    # Keep real membership when a single explanation fails, but do not use
    # that group for a combined reading. An incomplete layer may add members
    # to the scoped groups, so the projection cannot establish absence.
    unchecked = {row['id'] for row, status in inputs if status == 'withheld'}
    groups = _components([dict(row, status='conditional' if status == 'verified' else status)
                          for row, status in inputs])
    for group in groups:
        if unchecked.intersection(group['component_ids']):
            result['withheld_groups'].append(dict(kind=group['kind'], key=group['key']))
        else:
            result['groups'].append(group)
    result['incomplete_layers'] = incomplete
    if 'monthly' not in layer_status:
        result['recorded_status'] = 'not_applicable'
    elif not incomplete and not unchecked and cards:
        card = cards['ZW-E05']
        recorded = panel['modules'].get('ZW-E05')
        expected_status = 'conditional' if any(row['status'] == 'conditional' for row in groups) else 'withheld'
        result['recorded_status'] = 'withheld'
        if _matches_registered_card(recorded, card) and recorded.get('status') == expected_status:
            try:
                if _same_identity(recorded.get('rows'), groups):
                    result['recorded_status'] = 'verified'
            except (TypeError, ValueError):
                pass
    return result, natal_topics


def _indexed_stage_rows(rows):
    if not isinstance(rows, list) or len(rows) != 12 or any(
            not isinstance(row, dict) or type(row.get('index')) is not int for row in rows):
        return {}
    indexed = {row['index']: row for row in rows}
    return indexed if set(indexed) == set(range(12)) else {}


def _t02_stage_contract(panel):
    module = (panel.get('modules') or {}).get('ZW-T02')
    if not isinstance(module, dict) or module.get('status') != 'conditional':
        return None
    contracts = module.get('rows')
    if (isinstance(contracts, list) and len(contracts) == 1 and isinstance(contracts[0], dict)
            and contracts[0].get('status') == 'conditional' and contracts[0].get('errors') == []):
        return contracts[0]
    return None


def _natal_stage_basis(panel):
    basis = panel.get('natal_stage_basis')
    return basis if isinstance(basis, dict) else {}


def _same_replayed_natal(natal_panel, panel):
    from ziwei_life_reading import _integer

    basis = _natal_stage_basis(natal_panel)
    return (basis.get('gender') in ('male', 'female') and _integer(basis.get('year_branch'), 0, 11)
            and _integer(basis.get('wuxing_ju'), 2, 6) and basis == _natal_stage_basis(panel)
            and all(natal_panel.get(key) is not None and natal_panel[key] == panel.get(key)
                    for key in ('natal_solar_date', 'natal_civil_birth_year', 'temporal_uncertainty')))


def _same_birth_scenario(natal_panel, panel):
    from ziwei_life_reading import _same_identity

    original, point = (owner.get('birth_scenario') for owner in (natal_panel, panel))
    if original == point:
        return True
    if (not isinstance(original, dict) or not isinstance(point, dict)
            or original.get('scope') != 'selected_reachable_civil_band_candidate_only'
            or original.get('birth_time_confirmed') is not False
            or not isinstance(original.get('input'), dict)
            or not {'solar_date', 'birth_year', 'shichen_index', 'shichen', 'sex'} <= original['input'].keys()
            or not isinstance(original.get('civil_spans'), list) or not original['civil_spans']
            or not _same_replayed_natal(natal_panel, panel)):
        return False
    paths = (owner.get('chart_path') for owner in (original, point))
    if not all(isinstance(path, str) and re.fullmatch(r'candidates\[(?:[0-9]|1[01])\]\.native\.chart', path)
               for path in paths):
        return False
    # Narrowing can remove another candidate and move the selected raw row.
    # The physical spans and the complete discrete birth input must still match.
    try:
        before, after = ({key: value for key, value in owner.items() if key != 'chart_path'}
                         for owner in (original, point))
        return _same_identity(before, after)
    except (TypeError, ValueError):
        return False


def _natal_domains_by_branch(domains):
    """Align saved arrays after checking each archive's own native fact paths."""
    from ziwei_life_reading import _integer

    if len(domains) != 12:
        return None
    ordered = {}
    for palace_index, domain in enumerate(domains):
        branch = domain['branch']
        if not _integer(branch, 0, 11) or branch in ordered:
            return None
        palace_path = f'chart.palaces[{palace_index}]'
        facts = domain['facts']
        for star_index, fact in enumerate(facts):
            if (not isinstance(fact, dict) or not isinstance(fact.get('name'), str) or
                    fact.get('palace_path') != palace_path or fact.get('path') != f'{palace_path}.stars[{star_index}]' or
                    not _integer(fact.get('branch'), 0, 11) or fact['branch'] != branch or
                    fact.get('domain') != domain['domain']):
                return None
        ordered[branch] = dict(domain, facts=sorted(facts, key=lambda fact: fact['name']))
    return ordered


def _optional_domain_annotations_match(natal, point, point_gaps):
    """Allow only explicit omissions of optional raw annotations on the same stars."""
    from ziwei_case_judgments import RAW_BRIGHTNESS
    from ziwei_life_reading import KINDS

    optional = {'brightness_raw': ('brightnessRaw', RAW_BRIGHTNESS),
                'natal_transform': ('siHua', tuple(KINDS))}
    if (natal['domain'], natal['branch']) != (point['domain'], point['branch']):
        return False
    before, after = natal.get('facts'), point.get('facts')
    if not isinstance(before, list) or not isinstance(after, list) or len(before) != len(after):
        return False
    for expected, observed in zip(before, after):
        point_path = observed['path']
        expected, observed = ({key: value for key, value in fact.items() if key not in ('path', 'palace_path')}
                              for fact in (expected, observed))
        if expected == observed:
            continue
        if (expected.keys() != observed.keys() or expected.get('brightness_conflict') or
                observed.get('brightness_conflict')):
            return False
        for field in expected:
            old, new = expected[field], observed[field]
            if old == new:
                continue
            if field not in optional or (old is not None and new is not None):
                return False
            raw_key, known_values = optional[field]
            if ((new if old is None else old) not in known_values or
                    (new is None and point_gaps is not None and f'{point_path}.{raw_key}' not in point_gaps)):
                return False
    return True


def _natal_domains_match(natal_panel, panel, birth_bounds):
    natal, point = natal_panel['domains'], panel.get('domains')
    if not (isinstance(natal, list) and isinstance(point, list) and len(natal) == len(point)):
        return False
    try:
        natal, point = ([_domain_evidence(row) for row in rows] for rows in (natal, point))
    except (KeyError, TypeError):
        return False
    if any(not isinstance(row['facts'], list) for rows in (natal, point) for row in rows):
        return False
    if natal == point:
        return True
    # Array and annotation differences require replayed birth identity on
    # both sides, plus the same recorded candidate or physical birth bounds.
    if not _same_replayed_natal(natal_panel, panel):
        return False
    same_bounds = birth_bounds is not None and _birth_time_bounds(panel) == birth_bounds
    scenario = natal_panel.get('birth_scenario')
    same_candidate = (isinstance(scenario, dict) and scenario.get('scope') in (
        'confirmed_civil_shichen_only', 'selected_reachable_civil_band_candidate_only', 'selected_birth_witness_only')
        and _same_birth_scenario(natal_panel, panel))
    if not (same_bounds or same_candidate):
        return False
    dynamic = panel.get('dynamic') or {}
    point_gaps = None
    if dynamic.get('status') in ('admitted', 'partial'):
        point_gaps = dynamic.get('unverified_static_fields', [])
        if not isinstance(point_gaps, list) or not all(isinstance(path, str) for path in point_gaps):
            return False
    natal, point = _natal_domains_by_branch(natal), _natal_domains_by_branch(point)
    return natal is not None and point is not None and all(
        _optional_domain_annotations_match(before, point[branch], point_gaps) for branch, before in natal.items())


STAGE_TOPIC_FIELDS = ('role', 'topic_fact_paths', 'empty_palace', 'domain_status', 'status')


def _stage_evidence(row):
    return {key: value for key, value in row.items() if key not in STAGE_TOPIC_FIELDS}


def _stage_current_from_evidence(panel, natal_panel, stage, year):
    from ziwei_life_reading import _integer, _name, _native_stage_order_error, _native_stage_placement

    contract = _t02_stage_contract(panel)
    if (contract is None or {key: value for key, value in contract.items() if key != 'rows'} != stage
            or stage.get('errors') != []):
        return None
    presented = panel['stage_relationship'].get('stages')
    if not isinstance(presented, list) or not all(isinstance(row, dict) for row in presented):
        return None
    native = _indexed_stage_rows(contract.get('rows'))
    displayed = _indexed_stage_rows([row.get('legacy_stage') for row in presented])
    if (not native or not displayed or
            any(_stage_evidence(row) != _stage_evidence(displayed[index]) for index, row in native.items())):
        return None
    birth_year, age = stage.get('birth_year'), stage.get('current_age')
    if (type(birth_year) is not int or type(age) is not int or not 1 <= birth_year <= year
            or age != year - birth_year + 1):
        return None
    query = f'{year:04d}-01-01'
    first = previous_end = None
    current = -1
    domains = {row['branch']: row['domain'] for row in panel['domains']}
    soul = [branch for branch, domain in domains.items() if _name(domain) == '命']
    sources = []
    for index in range(12):
        row = native[index]
        source = row.get('native')
        if not isinstance(source, dict):
            return None
        branch, palace, domain = source.get('palaceBranch'), source.get('palaceName'), row.get('domain')
        if (type(branch) is not int or not isinstance(domain, str)
                or domains.get(branch) != domain or _name(palace) != _name(domain)):
            return None
        sources.append(source)
        start_age, end_age = source.get('startAge'), source.get('endAge')
        if (type(start_age) is not int or type(end_age) is not int or not 1 <= start_age <= end_age
                or birth_year + end_age > 9999):
            return None
        start, end = f'{birth_year + start_age - 1:04d}-01-01', f'{birth_year + end_age:04d}-01-01'
        if (row.get('window') != dict(start_inclusive=start, end_exclusive=end)
                or (previous_end is not None and previous_end != start)):
            return None
        active = start <= query < end
        if row.get('current') is not active:
            return None
        if active:
            current = index
        first = first or start
        previous_end = end
    if (stage.get('covered_window') != dict(start_inclusive=first, end_exclusive=previous_end)
            or type(stage.get('current_index')) is not int or stage['current_index'] != current):
        return None
    if len(soul) != 1:
        return None
    # A legacy natal panel can have independently replayed birth data without
    # a readable T02 table. Its birth data still establish the stage order.
    basis = _natal_stage_basis(natal_panel)
    order_inputs = dict(mingGongBranch=soul[0], birthInfo=dict(gender=basis.get('gender')),
                        lunarInfo=dict(yearBranch=basis.get('year_branch')), wuxingJu=basis.get('wuxing_ju'))
    if _native_stage_order_error(order_inputs, sources):
        return None
    natal_contract = _t02_stage_contract(natal_panel)
    original = _indexed_stage_rows(natal_contract.get('rows')) if natal_contract else {}
    if original:
        if ([_native_stage_placement(original[i].get('native')) for i in range(12)] !=
                [_native_stage_placement(source) for source in sources]):
            return None
    elif (basis.get('gender') not in ('male', 'female') or not _integer(basis.get('year_branch'), 0, 11)
          or not _integer(basis.get('wuxing_ju'), 2, 6)):
        return None
    status = 'active' if current >= 0 else 'before_first_stage' if query < first else 'after_last_stage'
    return status if stage.get('current_status') == status else None


def _stage_coverage(panel, natal_panel, year):
    scope = panel.get('stage_query_scope', {})
    stage = panel.get('stage_relationship', {}).get('stage_contract') or {}
    if (scope.get('status') == 'analysis_year_mismatch' or
            any(value is not None and value != year for value in
                (scope.get('panel_analysis_year'), scope.get('query_civil_year'), stage.get('analysis_year')))):
        return 'year_mismatch', 'unverified'
    aligned = scope.get('aligned_to_query') is True and scope.get('query_civil_year') == year
    dynamic = panel.get('dynamic') or {}
    # An explicit static replay has no date witness. The replayed segment
    # supplies its own civil year; a cached dynamic point cannot use this path.
    static = (scope.get('query_civil_year') is None and scope.get('aligned_to_query') is None and
              type(scope.get('requested_analysis_year')) is int and scope['requested_analysis_year'] == year and
              dynamic.get('status') == 'not_requested' and 'query_point' not in dynamic)
    if (scope.get('status') == 'verified' and (aligned or static) and
            scope.get('panel_analysis_year') == year and
            stage.get('status') == 'conditional' and stage.get('analysis_year') == year):
        current = _stage_current_from_evidence(panel, natal_panel, stage, year)
        if current is not None:
            return 'verified', current
    return 'withheld', 'unverified'


def _stage_topic_coverage(panel):
    """Check the current stage's topic independently of its native window and models."""
    from ziwei_life_reading import ROLES, _name

    stage = next(row['legacy_stage'] for row in panel['stage_relationship']['stages']
                 if row['legacy_stage']['current'])
    contract = _t02_stage_contract(panel)
    native = next(row for row in contract['rows'] if row['current'])
    summaries = [stage, native]
    try:
        case_stage = panel['case_judgments']['modules']['ZW-RC03']['context']['current_stage']
    except (KeyError, TypeError):
        case_stage = None
    if isinstance(case_stage, dict) and _stage_evidence(case_stage) == _stage_evidence(stage):
        summaries.append(case_stage)
    anchor = next(row for row in panel['domains'] if row['branch'] == stage['native']['palaceBranch'])
    role = ROLES.get(_name(anchor['domain']))
    facts = anchor.get('facts')
    if role is None or not isinstance(facts, list) or not all(isinstance(fact, dict) for fact in facts):
        return 'withheld'
    major_paths = [fact.get('path') for fact in facts if fact.get('type') == 'major']
    if not all(isinstance(path, str) and path for path in major_paths):
        return 'withheld'
    empty = not major_paths
    status = 'withheld' if panel.get('temporal_uncertainty') or empty else 'conditional'
    expected = dict(role=role, topic_fact_paths=major_paths, domain_status=status, status=status)
    return 'verified' if all(summary.get('empty_palace') is empty and
                             all(summary.get(field) == value for field, value in expected.items())
                             for summary in summaries) else 'withheld'


def _replayed_static_year_stem(panel, table):
    """Recover a missing copy only from the native calendar and the old star facts."""
    from ziwei_life_reading import _integer
    from ziwei_native import run_ziwei

    stage = panel.get('stage_relationship')
    basis = _natal_stage_basis(panel)
    gender = basis.get('gender')
    if (not isinstance(stage, dict) or 'natal_year_stem' in stage or
            panel.get('temporal_uncertainty') is not False or panel.get('source_errors') or
            panel.get('natal_transform_errors') or gender not in ('male', 'female') or
            not _integer(basis.get('year_branch'), 0, 11) or not _integer(basis.get('wuxing_ju'), 2, 6)):
        return None
    try:
        day = date.fromisoformat(panel['natal_solar_date'])
        sex = {'male': '男', 'female': '女'}[gender]
        # Only the native lunar header is date-based and independent of the
        # hour. The reference hour supplies no palace or stage evidence.
        raw, _ = run_ziwei(day.year, day.month, day.day, None, None, sex, None, None,
                           age_year=day.year, birth_year=day.year, output_format='json', shichen='子')
        lunar = json.loads(raw)['chart']['lunarInfo']
        stem = lunar['yearStem']
        if not _integer(stem, 0, 9) or lunar.get('yearBranch') != basis['year_branch']:
            return None
        natal, errors = _replayed_natal_transformations(panel, stem, table)
        if not errors and _retains_transformations(panel.get('transformations'), natal, 'natal'):
            return stem
    except (AttributeError, KeyError, TypeError, ValueError, IndexError, OverflowError):
        pass
    return None


def _matching_natal_year_stem(panel, natal_panel, missing_static_stem):
    from ziwei_life_reading import _integer

    def stem(owner):
        stage = owner.get('stage_relationship') or {}
        row = stage.get('natal_year_stem') if isinstance(stage, dict) else None
        if (isinstance(row, dict) and row.get('path') == 'chart.lunarInfo.yearStem' and
                _integer(row.get('value'), 0, 9)):
            return row['value']
        return None

    point = stem(panel)
    original = stem(natal_panel)
    if missing_static_stem is not None and _same_replayed_natal(natal_panel, panel):
        original = missing_static_stem
    return point if point is not None and point == original else None


def _replayed_natal_transformations(panel, stem, table):
    from ziwei_life_reading import _natal_transforms

    facts = [fact for domain in panel['domains'] for fact in domain['facts']]
    return _natal_transforms(dict(lunarInfo=dict(yearStem=stem)), facts, table)


def _stage_model_coverage(panel, cards, fixed_transformations, stem):
    """Replay the current row's approved modules from its verified natal palace."""
    from ziwei_stage_relationship import STAGE_RULES, _context, _stage_modules

    staged = panel['stage_relationship']
    current, = [row for row in staged['stages'] if row['legacy_stage']['current']]
    domains = panel['domains']
    anchor = next(row for row in domains if row['branch'] == current['legacy_stage']['native']['palaceBranch'])
    context = _context(domains, anchor)
    recorded = current.get('modules')
    recorded_cards = staged.get('cards')
    if (not cards or not isinstance(recorded, dict) or not isinstance(recorded_cards, dict) or
            current.get('context') != context or
            current.get('overall_direction') != 'withheld'):
        return dict(status='withheld', unverified_rules=list(STAGE_RULES))

    natal = {}
    transforms = panel.get('transformations')
    if stem is not None and isinstance(transforms, list):
        # Validate the two relevant natal transformations separately so an
        # incomplete or stale kind cannot invalidate an unrelated model.
        try:
            original, _ = _replayed_natal_transformations(panel, stem, fixed_transformations)
        except (AttributeError, KeyError, TypeError, ValueError):
            original = []
        for fact in original:
            kind = fact['kind']
            if kind in ('权', '忌'):
                rows = [row for row in transforms if isinstance(row, dict) and row.get('kind') == kind]
                if _retains_transformations(rows, [fact], 'natal'):
                    natal[kind] = fact
    expected = _stage_modules(anchor, context, natal, cards, stem)
    mismatched = [rule for rule in STAGE_RULES
                  if recorded.get(rule) != expected[rule] or recorded_cards.get(rule) != cards[rule]]
    unknown = sorted(recorded.keys() - expected.keys())
    status = 'withheld' if len(mismatched) == len(STAGE_RULES) else (
        'partial' if mismatched or unknown else 'verified')
    return dict(status=status, unverified_rules=[*mismatched, *unknown])


E_TOPIC_FIELDS = frozenset((
    'rule_id', 'status', 'temporal_scope', 'reference', 'topic', 'star_theme',
    'countercheck', 'citation', 'net_effect', 'identity', 'unresolved',
    'theme_citation', 'health_scope', 'medical_boundary',
))


def _case_transform_evidence(row):
    """Compare the original attachment separately from copied E-card prose."""
    return {key: value for key, value in row.items() if key not in E_TOPIC_FIELDS}


def _facts_for_cases(rows):
    # The case predicates inspect the actual star and placement. They do not
    # require a successful E-card explanation of the same transformation.
    return [dict(row, status='facts_only') for row in rows]


def _annual_case_evidence(module, verified_yearly=()):
    context = module.get('context', {})
    if 'transformations' not in context:
        return module
    yearly = {row['id']: row for row in verified_yearly}

    def transform_evidence(row):
        evidence = _case_transform_evidence(row)
        # A saved case copy can omit the derived index. Only the same
        # independently admitted annual attachment can supply that index.
        if row['layer'] == 'yearly' and 'source_path' not in evidence:
            verified = yearly.get(row['id'], {})
            pointer = row.get('admitted_attachment', {}).get('raw_pointer')
            if (isinstance(pointer, str) and pointer == verified.get('admitted_attachment', {}).get('raw_pointer')
                    and 'source_path' in verified):
                evidence['source_path'] = verified['source_path']
        return evidence

    # The case includes all layers for human review, while only natal and
    # yearly transformations can establish the annual result.
    rows = sorted((transform_evidence(row) for row in context['transformations'] if row.get('layer') != 'monthly'),
                  key=lambda row: row['id'])
    checks = [dict(check, evidence=transform_evidence(check['evidence'])) if 'evidence' in check else check
              for check in module['checks']]
    # Copied palace topics are audited separately from the star placements used by RC03.
    surrounds = {key: [_domain_evidence(row) for row in context[key]]
                 for key in ('natal_ming_surrounding', 'career_stage_surrounding')}
    return dict(module, checks=checks, context=dict(
        context, transformations=rows, current_stage=_stage_evidence(context['current_stage']), **surrounds))


def _annual_case_coverage(panel, fixed_transformations, stem):
    from ziwei_case_judgments import PROFILE, evaluate

    recorded = panel.get('case_judgments')
    if (stem is None or panel.get('natal_transform_errors') or
            not isinstance(recorded, dict) or recorded.get('profile') != PROFILE):
        return 'withheld'
    try:
        natal, errors = _replayed_natal_transformations(panel, stem, fixed_transformations)
        if errors or not _retains_transformations(panel.get('transformations'), natal, 'natal'):
            return 'withheld'
        saved = recorded['modules']['ZW-RC03']
        yearly = panel['dynamic']['layers']['yearly']['transformations']
        replay_panel = dict(panel, transformations=_facts_for_cases(natal + yearly))
        replayed = evaluate(replay_panel)['modules']['ZW-RC03']
        if (replayed['status'] in ('conditional', 'not_triggered') and
                _annual_case_evidence(saved, yearly) == _annual_case_evidence(replayed)):
            return 'verified'
    except (AttributeError, KeyError, TypeError, IndexError, ValueError):
        pass
    return 'withheld'


def _annual_case_yearly_precondition(panel):
    """Report the annual placements only after their layer passes the point audit."""
    from ziwei_case_judgments import _annual_career_placement, _name

    rows = {row['kind']: row for row in panel['dynamic']['layers']['yearly']['transformations']}
    attachments = []
    for kind in ('禄', '权'):
        row = rows[kind]
        attachments.append(dict(kind=kind, star=row['star'], domain=_name(row['fact']['domain']),
                                actual_major=row['fact']['type'] == 'major',
                                matched=_annual_career_placement(row, panel['domains'])))
    return dict(status='met' if all(row['matched'] for row in attachments) else 'excluded', attachments=attachments)


def _natal_body_topic_coverage(panel, natal_panel, sources):
    from ziwei_life_reading import _body, _integer

    branch = natal_panel.get('natal_body_branch')
    if panel is None or branch is None:
        return 'unverified'
    point_branch = panel.get('natal_body_branch', branch)
    if not _integer(branch, 0, 11) or not _integer(point_branch, 0, 11) or point_branch != branch:
        return 'withheld'
    card = sources[0].get('ZW-S01') if sources else None
    if card is None:
        return 'withheld'
    for owner in (natal_panel, panel):
        modules = owner.get('modules')
        if (owner.get('temporal_uncertainty') is not False or owner.get('source_errors')
                or not isinstance(modules, dict)):
            return 'withheld'
        recorded = modules.get('ZW-S01')
        if not _matches_registered_card(recorded, card):
            return 'withheld'
        domains = owner['domains']
        try:
            expected = _body(dict(shenGongBranch=branch, palaces=domains), domains, False)
        except (KeyError, IndexError, TypeError, ValueError, StopIteration):
            return 'withheld'
        if (expected['status'] != 'conditional' or recorded.get('rows') != [expected] or
                recorded.get('status') != expected['status'] or recorded.get('unresolved') != card['unresolved']):
            return 'withheld'
    return 'verified'


NATAL_RELATIONSHIP_RULES = ('ZW-RL01', 'ZW-RC01', 'ZW-RC02')


def _spouse_case_evidence(module, kinds):
    try:
        context = module['context']
        return dict(module, context=dict(
            context, domain=_domain_evidence(context['domain']),
            transformations=[_case_transform_evidence(row) for row in context['transformations']
                             if row['kind'] in kinds]))
    except (AttributeError, KeyError, TypeError):
        return None


def _natal_relationship_coverage(panel, natal_panel, stage_cards, fixed_transformations, stem):
    from ziwei_case_judgments import KINDS, PROFILE as CASE_PROFILE, _actual_major, evaluate
    from ziwei_stage_relationship import PROFILE as STAGE_PROFILE, _relationship, _validated_domains

    statuses = dict.fromkeys(NATAL_RELATIONSHIP_RULES, 'withheld')
    if panel.get('temporal_uncertainty') is not False or panel.get('source_errors'):
        return statuses
    stage = panel.get('stage_relationship', {})
    rule = 'ZW-RL01'
    # The native relationship branch uses the natal stars and six malefics,
    # independently of the stage date or the transformation layer.
    if (stage_cards and stage.get('profile') == STAGE_PROFILE and
            not stage.get('input_errors') and not stage.get('source_errors')):
        try:
            expected = _relationship(_validated_domains(panel), stage_cards[rule])
            if (expected['status'] in ('conditional', 'not_triggered') and
                    stage['relationship'] == expected and stage['cards'][rule] == stage_cards[rule]):
                statuses[rule] = 'verified'
        except (AttributeError, KeyError, TypeError, ValueError, StopIteration):
            pass

    saved = panel.get('case_judgments')
    if (not isinstance(saved, dict) or saved.get('profile') != CASE_PROFILE or
            saved.get('input_errors') or saved.get('source_errors')):
        return statuses
    try:
        rows = panel.get('transformations')
        if not isinstance(rows, list):
            return statuses
        if stem is None:
            # Both panels explicitly lack the stem. Only a replayed geometric
            # exclusion can pass below, without crediting any natal transform.
            missing = dict(value=None, path='chart.lunarInfo.yearStem')
            if any(owner.get('stage_relationship', {}).get('natal_year_stem') != missing
                   for owner in (panel, natal_panel)):
                return statuses
            _validated_domains(panel)
            errors = panel.get('natal_transform_errors', {})
            reference_rows = natal_panel.get('transformations')
            if (set(errors) != set(KINDS) or not isinstance(reference_rows, list) or
                    any(row.get('layer') == 'natal' for row in (*rows, *reference_rows))):
                return statuses
            natal = []
        else:
            natal, errors = _replayed_natal_transformations(panel, stem, fixed_transformations)
        error = '；'.join(dict.fromkeys(errors.values())) if errors else None
        natal_only = dict(panel, transformations=_facts_for_cases(natal))
        replayed = evaluate(natal_only, natal_transform_error=error)['modules']
        for rule, kinds in (('ZW-RC01', ('权', '忌')), ('ZW-RC02', ('忌',))):
            expected = replayed[rule]
            if expected['status'] not in ('conditional', 'not_triggered'):
                continue
            proofs = [kinds]
            if expected['status'] == 'not_triggered':
                spouse = expected['context']['domain']
                majors = [fact['name'] for fact in spouse['facts'] if fact['type'] == 'major']
                # Geometry alone can rule a case out even when projected
                # transformations are missing or conflict.
                if (rule == 'ZW-RC01' and len(majors) != 2) or (rule == 'ZW-RC02' and '巨门' not in majors):
                    proofs = [()]
                elif rule == 'ZW-RC01':
                    # Either known transformation failing the actual spouse-major test rules out RC01.
                    off_spouse_majors = [(row['kind'],) for row in natal
                                         if row['kind'] in kinds and not _actual_major(row, [spouse])]
                    if off_spouse_majors:
                        proofs = off_spouse_majors
            for proof in proofs:
                observed = [row for row in rows if isinstance(row, dict) and row.get('kind') in proof]
                required = [row for row in natal if row['kind'] in proof]
                if (len(required) == len(proof) and _retains_transformations(observed, required, 'natal') and
                        _spouse_case_evidence(saved['modules'].get(rule), proof) ==
                        _spouse_case_evidence(expected, proof)):
                    statuses[rule] = 'verified'
                    break
    except (AttributeError, KeyError, TypeError, ValueError, IndexError):
        pass
    return statuses


def _replay_query_plan(plan, expected_request):
    if not isinstance(plan, dict) or plan.get('schema_version') != 'ziwei-query-windows-v1':
        raise ValueError('需要本次紫微实际查询分段计划')
    saved = plan.get('requested')
    if not isinstance(saved, dict):
        raise ValueError('缺少已记录的紫微原查询请求')
    stored = dict(start=saved.get('start'), end=saved.get('end'),
                  layer=plan.get('layer'), timezone=plan.get('timezone'))
    folds = ('start_fold', 'end_fold')
    stored.update((key, saved[key]) for key in folds if key in saved)
    request = stored if expected_request is None else expected_request
    if (not isinstance(request, dict) or not all(isinstance(request.get(key), str) for key in ('start', 'end'))
            or request.get('layer') not in ('year', 'month', 'day')
            or (request.get('timezone') is not None and not isinstance(request['timezone'], str))
            or any(type(request[key]) is not int or request[key] not in (0, 1)
                   for key in folds if key in request and request[key] is not None)):
        raise ValueError('须提供有效的紫微原请求起止、时间层、时区和重复端点 fold')
    if any(request.get(key) != value for key, value in stored.items()):
        raise ValueError('已保存的紫微计划与独立确认的原请求不一致')
    provenance = plan.get('provenance', {})
    if not isinstance(provenance, dict):
        raise ValueError('保存的紫微时区来源记录格式无效')
    if 'timezone_source' in provenance:
        check_timezone_source(provenance['timezone_source'], request.get('timezone'))
    try:
        zone = request.get('timezone')
        tz = iana_query_zone(zone) if zone is not None else None
        replayed = query_windows(request['start'], request['end'], request['layer'], zone,
                                 start_fold=request.get('start_fold'), end_fold=request.get('end_fold'),
                                 _resolved_zone=tz)
    except ValueError as exc:
        raise ValueError('无法按紫微原请求重建分段；请核实原端点、时区及所需 fold。' + str(exc)) from exc
    if (saved.get('kind') != replayed['requested']['kind'] or any(
            plan.get(key) != replayed[key] for key in ('profile', 'interval_semantics'))):
        raise ValueError('已保存的紫微计划与原请求重建的口径不一致')
    return replayed, tz


def _birth_time_bounds(natal_panel):
    scenario = natal_panel.get('birth_scenario') or {}
    bounds = natal_panel.get('birth_time_bounds', scenario.get('birth_time_bounds'))
    spans = scenario.get('civil_spans')
    if bounds is None and not spans:
        return None
    try:
        if bounds is None:
            endpoints = [(parse_query_point(row['start_utc']), parse_query_point(row['end_exclusive_utc']))
                         for row in spans]
        else:
            endpoints = [(parse_query_point(bounds['earliest_utc']), parse_query_point(bounds['latest_utc']))]
        if any(left.utcoffset() is None or right.utcoffset() is None or left > right for left, right in endpoints):
            raise ValueError
        return min(left for left, _ in endpoints), max(right for _, right in endpoints)
    except (AttributeError, KeyError, TypeError, ValueError) as exc:
        raise ValueError('已核本命面板的实际出生范围无效，请按原出生输入重建') from exc


def latest_birth_for_order(natal_panel, bounds=None):
    """Return an upper bound for ordering, even when an old birth has no UTC clock."""
    if natal_panel.get('birth_time_error'):
        return None
    bounds = bounds if bounds is not None else _birth_time_bounds(natal_panel)
    if bounds is not None:
        return bounds[1]
    if natal_panel.get('temporal_uncertainty'):
        return None
    scenario = natal_panel.get('birth_scenario') or {}
    if scenario.get('scope') == 'confirmed_civil_shichen_only':
        source = scenario.get('input') or {}
        solar = source.get('solar_date')
        index = source.get('shichen_index')
        if type(index) is not int or not 0 <= index <= 11:
            return None
        latest_hour = max(end for _, end in civil_shichen_hours(index))
    else:
        # A native chart date is a civil or solar clock date. Neither clock
        # is more than one day away from UTC under the supported contracts.
        solar = natal_panel.get('natal_solar_date')
        latest_hour = 24
    try:
        return datetime.combine(date.fromisoformat(solar), time(), UTC) + timedelta(hours=latest_hour) + OFFSET_CEILING
    except (TypeError, ValueError, OverflowError):
        return None


def date_index_after_birth(day, index, latest):
    """A bare date and index can stand alone only if the whole clock bucket is later."""
    hour = max(0, 2 * index - 1)
    return latest is not None and datetime.combine(day, time(hour), UTC) - OFFSET_CEILING >= latest


def _segments_at_birth(plan, bounds, latest, tz):
    if latest is None:
        for segment in plan['segments']:
            yield segment, 'birth_time_unverified'
        return
    for segment in plan['segments']:
        start, end = (parse_query_point(segment[key]) for key in ('start_inclusive', 'end_exclusive'))
        cuts = sorted({point.astimezone(start.tzinfo) for point in (bounds or (latest,)) if start < point < end})
        edges = [start, *cuts, end]
        for left, right in zip(edges, edges[1:]):
            if bounds is not None and right <= bounds[0]:
                status = 'before_birth'
            elif left >= latest:
                status = 'after_birth'
            else:
                status = 'birth_time_uncertain' if bounds is not None else 'birth_time_unverified'
            yield dict(segment, start_inclusive=left.isoformat(), end_exclusive=right.isoformat(),
                       probe=_probe_at(left, tz)), status


def _birth_year_mismatch(value, birth_year):
    return value is not None and birth_year is not None and (type(value) is not int or value != birth_year)


def audit_query_windows(plan, panels_by_start, *, natal_panel, expected_request=None):
    """Audit admitted life-panel layers for each planned probe and birth scenario.

    Supply a verified static panel for the same birth input used for the point
    panels. Replay the recorded endpoints, or check them against independently
    retained start, end, layer, timezone and any explicit endpoint folds.
    The result includes the actual birth cuts when the static panel retains
    verified bounds. Use those returned probes for the post-birth readings.
    The current stage's saved rule matches are checked separately from the
    annual window. The annual action case needs both the yearly facts and the
    current stage to pass. The stage and annual prerequisites are reported independently.
    Daily adapter facts and interpretation are outside this audit.
    """
    if not natal_panel.get('domains'):
        raise ValueError('需要已核本命领域面板')
    if natal_panel.get('birth_time_error'):
        raise ValueError('无法核对本命实际出生范围，请按原出生输入重建。' + natal_panel['birth_time_error'])
    plan, tz = _replay_query_plan(plan, expected_request)
    birth_bounds = _birth_time_bounds(natal_panel)
    latest_birth = latest_birth_for_order(natal_panel, birth_bounds)
    segments = list(_segments_at_birth(plan, birth_bounds, latest_birth, tz))
    if panels_by_start.keys() - {segment['start_inclusive'] for segment, _ in segments}:
        raise ValueError('已提供面板的时段起点不属于本次查询计划')

    from ziwei_life_reading import _name, _table
    from ziwei_stage_relationship import _load_cards

    fixed_transformations = _table(Path(__file__).resolve().parents[1]) if panels_by_start else {}
    missing_static_stem = _replayed_static_year_stem(natal_panel, fixed_transformations) if panels_by_start else None
    stage_cards = None
    life_sources = None
    layers = ('yearly',) if plan['layer'] == 'year' else ('yearly', 'monthly')
    natal_stage = natal_panel.get('stage_relationship', {}).get('stage_contract') or {}
    natal_gender = _natal_stage_basis(natal_panel).get('gender')
    birth_year = natal_panel.get('natal_civil_birth_year', natal_stage.get('birth_year'))
    birth_date = natal_panel.get('natal_solar_date')
    audited = []
    for segment, birth_status in segments:
        start, end = segment['start_inclusive'], segment['end_exclusive']
        probe = segment['probe']
        calendar = segment['calendar_window']['calendar_at_start']
        year = calendar['civilYear']
        target_date = date.fromisoformat(probe['target_date'])
        earlier_year = birth_year is not None and year < birth_year
        require_civil = birth_status == 'after_birth' and (
            earlier_year or (isinstance(birth_date, str) and probe['target_date'] < birth_date) or
            not date_index_after_birth(target_date, probe['target_time_index'], latest_birth))
        panel = panels_by_start.get(start)
        current_status = 'unverified'
        stage_topic_status = 'unverified'
        stage_models = dict(status='unverified', unverified_rules=[])
        annual_case_status = 'unverified'
        annual_case_stage_precondition = dict(status='unverified', domain=None, window=None)
        annual_case_yearly_precondition = dict(status='unverified', attachments=[])
        natal_relationship_status = dict.fromkeys(NATAL_RELATIONSHIP_RULES, 'unverified')
        point_facts = None
        stem = None
        if birth_status != 'after_birth':
            layer_status, stage_status = dict.fromkeys(layers, birth_status), birth_status
        elif panel is None:
            layer_status, stage_status = dict.fromkeys(layers, 'unread'), 'unread'
        else:
            dynamic = panel.get('dynamic') or {}
            point_stage = panel.get('stage_relationship', {}).get('stage_contract') or {}
            point_gender = _natal_stage_basis(panel).get('gender')
            point_birth_year = panel.get('natal_civil_birth_year')
            dynamic_birth_mismatch = _birth_year_mismatch(dynamic.get('original_civil_birth_year'), birth_year)
            stage_birth_mismatch = _birth_year_mismatch(point_stage.get('birth_year'), birth_year)
            if (panel.get('profile') != natal_panel.get('profile') or
                    not _same_birth_scenario(natal_panel, panel) or not _natal_domains_match(natal_panel, panel, birth_bounds) or
                    (natal_gender is not None and point_gender is not None and point_gender != natal_gender) or
                    (birth_date is not None and panel.get('natal_solar_date', birth_date) != birth_date) or
                    panel.get('birth_time_error') or
                    (birth_bounds is not None and 'birth_time_bounds' in panel and
                     _birth_time_bounds(panel) != birth_bounds) or
                    _birth_year_mismatch(point_birth_year, birth_year) or
                    (point_birth_year is None and (dynamic_birth_mismatch or stage_birth_mismatch))):
                layer_status, stage_status = dict.fromkeys(layers, 'birth_mismatch'), 'birth_mismatch'
            else:
                if stage_cards is None:
                    try:
                        stage_cards = _load_cards(None)
                    except (OSError, ValueError, KeyError, TypeError, IndexError):
                        stage_cards = {}
                stem = _matching_natal_year_stem(panel, natal_panel, missing_static_stem)
                natal_relationship_status = _natal_relationship_coverage(
                    panel, natal_panel, stage_cards, fixed_transformations, stem)
                point_facts = [fact for domain in panel['domains'] for fact in domain.get('facts', [])]
                if dynamic_birth_mismatch:
                    layer_status = dict.fromkeys(layers, 'birth_mismatch')
                else:
                    layer_status = {layer: _dynamic_layer_coverage(
                        panel, point_facts, plan['profile'], segment, layer, require_civil, fixed_transformations)
                        for layer in layers}
                if layer_status['yearly'] == 'admitted':
                    annual_case_yearly_precondition = _annual_case_yearly_precondition(panel)
                if earlier_year:
                    stage_status = 'before_birth_civil_year'
                elif stage_birth_mismatch:
                    stage_status = 'birth_mismatch'
                else:
                    stage_status, current_status = _stage_coverage(panel, natal_panel, year)
                    if stage_status == 'verified':
                        if current_status == 'active':
                            current_stage = next(row['legacy_stage'] for row in panel['stage_relationship']['stages']
                                                 if row['legacy_stage']['current'])
                            domain = _name(current_stage['domain'])
                            annual_case_stage_precondition = dict(
                                status='met' if domain == '官禄' else 'excluded',
                                domain=domain, window=dict(current_stage['window']))
                            stage_topic_status = _stage_topic_coverage(panel)
                            stage_models = _stage_model_coverage(panel, stage_cards, fixed_transformations, stem)
                        else:
                            stage_topic_status = 'not_applicable'
                            stage_models['status'] = 'not_applicable'
                            if current_status == 'before_first_stage':
                                annual_case_stage_precondition = dict(
                                    status='excluded', domain=None, window=None, reason='before_first_stage',
                                    first_stage_start=point_stage['covered_window']['start_inclusive'])
                        if layer_status['yearly'] == 'admitted':
                            annual_case_status = _annual_case_coverage(panel, fixed_transformations, stem)
        if life_sources is None and point_facts is not None:
            try:
                life_sources = _load_life_topic_sources()
            except (OSError, ValueError, KeyError, TypeError, IndexError):
                life_sources = {}, {}, None
        verified_panel = panel if point_facts is not None else None
        natal_topics, four_palace_topics = _natal_domain_topic_coverage(verified_panel, natal_panel, life_sources)
        topic_status = _transform_topic_coverage(verified_panel, natal_panel, layer_status, life_sources)
        components, natal_transform_topics = _transform_component_coverage(
            verified_panel, natal_panel, point_facts, layer_status, topic_status, life_sources, fixed_transformations, stem)
        body_topic_status = _natal_body_topic_coverage(verified_panel, natal_panel, life_sources)
        audited.append(dict(start_inclusive=start, end_exclusive=end, probe=probe,
                            birth_time_status=birth_status, requires_civil_clock=require_civil,
                            dynamic_layers=layer_status, stage_year=year, stage_status=stage_status,
                            stage_current_status=current_status, stage_topic_status=stage_topic_status,
                            stage_models=stage_models,
                            annual_case_status=annual_case_status,
                            annual_case_stage_precondition=annual_case_stage_precondition,
                            annual_case_yearly_precondition=annual_case_yearly_precondition,
                            natal_relationship_status=natal_relationship_status,
                            natal_body_topic_status=body_topic_status,
                            natal_domain_topic_status=natal_topics,
                            natal_four_palace_topic_status=four_palace_topics,
                            natal_transformation_topic_status=natal_transform_topics,
                            transformation_topic_status=topic_status, transformation_components=components))
    return dict(layer=plan['layer'], segments=audited)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--start', required=True, help='ISO 民用日期时间；IANA 查询两端也可都用纯日期')
    parser.add_argument('--end', required=True, help='区间终点，不包含终点')
    parser.add_argument('--layer', required=True, choices=('year', 'month', 'day'))
    parser.add_argument('--timezone', help='查询地的 IANA 民用时区')
    parser.add_argument('--start-fold', type=int, choices=(0, 1), help='重复起点 0 较早，1 较晚')
    parser.add_argument('--end-fold', type=int, choices=(0, 1), help='重复终点 0 较早，1 较晚')
    args = parser.parse_args(argv)
    try:
        plan = query_windows(args.start, args.end, args.layer, args.timezone,
                             start_fold=args.start_fold, end_fold=args.end_fold)
    except (ValueError, OverflowError, OSError) as exc:
        parser.error(str(exc))
    print(json.dumps(plan, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
