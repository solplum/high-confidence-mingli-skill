#!/usr/bin/env python3
"""Validate evidence provenance, not the truth/predictive validity of divination.

Python 3.8+, standard library only. Never executes source files or reads outside
--root. Exit 0: mechanically consistent; 1: validation errors; 2: input error.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import importlib.util

# Load sibling explicitly: this module is also imported by path in tests.
_KSPEC = importlib.util.spec_from_file_location("mingli_knowledge_catalog", Path(__file__).with_name("knowledge_catalog.py"))
_KNOWLEDGE = importlib.util.module_from_spec(_KSPEC)
_KSPEC.loader.exec_module(_KNOWLEDGE)

SYSTEMS = {"bazi", "ziwei", "qizheng"}


def _json_equal(left, right):
    """JSON equality without Python's nested bool/int coercion."""
    if type(left) is not type(right):
        return False
    if isinstance(left, dict):
        return left.keys() == right.keys() and all(_json_equal(left[k], right[k]) for k in left)
    if isinstance(left, list):
        return len(left) == len(right) and all(_json_equal(a, b) for a, b in zip(left, right))
    return left == right


def _pointer(document, pointer):
    if not isinstance(pointer, str) or not pointer.startswith("/"):
        raise ValueError("JSON pointer must start with /")
    for part in pointer[1:].split("/"):
        part = part.replace("~1", "/").replace("~0", "~")
        if isinstance(document, list):
            if not re.fullmatch(r"0|[1-9][0-9]*", part):
                raise ValueError("invalid array index")
            document = document[int(part)]
        else:
            document = document[part]
    return document


def validate(ledger, root):
    errors = []
    root = Path(root).resolve()
    catalog_root = Path(__file__).resolve().parents[1]
    try:
        catalog = json.loads((catalog_root / "knowledge/catalog.json").read_text(encoding="utf-8"))
        catalog_errors = _KNOWLEDGE.validate(catalog, catalog_root)
        if catalog_errors:
            return ["knowledge catalog: " + e for e in catalog_errors]
    except (OSError, ValueError) as exc:
        return ["knowledge catalog unavailable: " + str(exc)]

    def require(ok, message):
        if not ok:
            errors.append(message)
        return bool(ok)

    def text(value):
        return isinstance(value, str) and bool(value.strip())

    def table(name):
        result = {}
        rows = ledger.get(name)
        if not require(isinstance(rows, list), name + " must be an array"):
            return result
        for row in rows:
            if not require(isinstance(row, dict) and text(row.get("id")), name + ": invalid record/id"):
                continue
            require(row["id"] not in result, name + ": duplicate id " + row["id"])
            result[row["id"]] = row
        return result

    def refs(row, key, target, nonempty=False):
        values = row.get(key)
        if not require(isinstance(values, list) and all(text(v) for v in values), row["id"] + ": invalid " + key):
            return []
        require(len(set(values)) == len(values), row["id"] + ": duplicate " + key)
        if nonempty:
            require(bool(values), row["id"] + ": empty " + key)
        for value in values:
            require(value in target, row["id"] + ": unknown " + key + " " + value)
        return [target[v] for v in values if v in target]

    if not isinstance(ledger, dict):
        return ["ledger must be an object"]
    require(type(ledger.get("schema_version")) is int and ledger.get("schema_version") == 1, "schema_version must be 1")
    require(ledger.get("purpose") in ("reading", "synthetic_test"), "invalid purpose")
    sources, scenarios, facts, rules, claims, links = [table(n) for n in
        ("sources", "scenarios", "facts", "rules", "claims", "syntheses")]
    # Reject malformed container/scalar types before graph traversal.
    for rows in (sources, scenarios, facts, rules, claims, links):
        for rid, row in rows.items():
            for key in ("system", "source_id", "scenario_id", "kind", "status", "boundary", "relation", "domain", "time_scope"):
                if key in row:
                    require(isinstance(row[key], str), rid + ": invalid type for " + key)
            for key in ("fact_ids", "rule_ids", "depends_on", "scenario_ids", "claim_ids"):
                if key in row:
                    require(isinstance(row[key], list) and all(text(v) for v in row[key]), rid + ": invalid type for " + key)
    if errors:
        return errors
    require(bool(scenarios), "at least one scenario required")
    require(bool(claims), "at least one claim required")
    content = {}
    chart_paths = {}
    for sid, source in sources.items():
        require(source.get("kind") in {"chart", "reference"}, sid + ": invalid source kind")
        try:
            if not text(source.get("path")):
                raise ValueError("missing source path")
            if Path(source["path"]).is_absolute():
                raise ValueError("source path must be relative")
            path = (root / source["path"]).resolve()
            path.relative_to(root)
            if not path.is_file():
                raise ValueError("source must be a regular file")
            if source.get("kind") == "chart":
                require(source.get("system") in SYSTEMS, sid + ": chart source requires system binding")
                require(source.get("scenario_id") in scenarios, sid + ": chart source requires scenario binding")
                prefix = source.get("pointer_prefix")
                require(text(prefix) and prefix.startswith("/"), sid + ": chart source requires pointer_prefix")
                prior = chart_paths.setdefault(path, [])
                for other in prior:
                    require(other.get("scenario_id") == source.get("scenario_id"), sid + ": chart path reused across scenarios")
                    a, b = other.get("pointer_prefix"), prefix
                    if text(a) and text(b) and (a == b or a.startswith(b + "/") or b.startswith(a + "/")):
                        require(other.get("system") == source.get("system"), sid + ": overlapping system scopes")
                prior.append(source)
            raw = path.read_bytes()
            require(hashlib.sha256(raw).hexdigest() == source.get("sha256"), sid + ": source hash mismatch")
            content[sid] = raw.decode("utf-8")
        except (OSError, ValueError, RuntimeError) as exc:
            errors.append(sid + ": unreadable/out-of-root source: " + str(exc))
    for sid, scenario in scenarios.items():
        for key in ("label", "time_basis", "assumptions"):
            require(text(scenario.get(key)), sid + ": missing " + key)
    for fid, fact in facts.items():
        require(fact.get("system") in SYSTEMS, fid + ": invalid system")
        require(fact.get("scenario_id") in scenarios, fid + ": unknown scenario")
        source = sources.get(fact.get("source_id", ""), {})
        require(source.get("kind") == "chart", fid + ": fact requires chart source")
        require(source.get("system") == fact.get("system"), fid + ": source system binding mismatch")
        require(source.get("scenario_id") == fact.get("scenario_id"), fid + ": source scenario binding mismatch")
        prefix, pointer = source.get("pointer_prefix"), fact.get("pointer")
        require(text(prefix) and text(pointer) and (pointer == prefix or pointer.startswith(prefix + "/")), fid + ": pointer outside system scope")
        try:
            actual = _pointer(json.loads(content[fact["source_id"]]), fact.get("pointer"))
            require("value" in fact and _json_equal(actual, fact["value"]), fid + ": chart value mismatch")
        except (KeyError, IndexError, ValueError, TypeError):
            errors.append(fid + ": unresolved chart pointer")
    for rid, rule in rules.items():
        source = sources.get(rule.get("source_id", ""), {})
        require(source.get("kind") == "reference", rid + ": rule requires reference source")
        errors.extend(rid + ": " + e for e in _KNOWLEDGE.check_ledger_rule(rule, source, catalog))
        require(rule.get("system") in SYSTEMS, rid + ": invalid system")
        for key in ("school", "locator", "quote"):
            require(text(rule.get(key)), rid + ": missing " + key)
        start, end = rule.get("start_line"), rule.get("end_line")
        lines = content.get(rule.get("source_id"), "").splitlines()
        if require(type(start) is int and type(end) is int and 1 <= start <= end <= len(lines), rid + ": invalid source line range"):
            require(text(rule.get("quote")) and rule["quote"] in "\n".join(lines[start-1:end]), rid + ": quote not found at source lines")
    for cid, claim in claims.items():
        require(claim.get("system") in SYSTEMS, cid + ": invalid system")
        require(claim.get("status") in {"supported", "conditional", "withheld"}, cid + ": invalid status")
        require(claim.get("boundary") in {"stable", "conditional", "unassessed"}, cid + ": invalid boundary")
        for key in ("statement", "domain", "time_scope", "conditions", "counterevidence", "alternatives", "limitations"):
            require(text(claim.get(key)), cid + ": missing " + key)
        explanation = claim.get("explanation", {})
        if require(isinstance(explanation, dict), cid + ": invalid explanation"):
            for key in ("plain", "technical", "action"):
                require(text(explanation.get(key)), cid + ": missing explanation." + key)
        active = claim.get("status") != "withheld"
        evidence = refs(claim, "fact_ids", facts, active)
        citations = refs(claim, "rule_ids", rules, active)
        dependencies = refs(claim, "depends_on", claims)
        covered = refs(claim, "scenario_ids", scenarios, True)
        for row in evidence + citations + dependencies:
            require(row.get("system") == claim.get("system"), cid + ": cross-system evidence/dependency")
        for row in evidence:
            require(row.get("scenario_id") in claim.get("scenario_ids", []), cid + ": fact outside claim scenarios")
        if claim.get("boundary") == "stable":
            require(len(covered) == len(scenarios), cid + ": stable claim must cover every scenario")
            require(set(f.get("scenario_id") for f in evidence) == set(scenarios), cid + ": stable claim lacks evidence for a scenario")
        if claim.get("boundary") != "stable":
            require(claim.get("status") != "supported", cid + ": unassessed/conditional boundary cannot be supported")
        for dependency in dependencies:
            require(set(claim.get("scenario_ids", [])) <= set(dependency.get("scenario_ids", [])), cid + ": dependency does not cover claim scenarios")
            require(claim.get("time_scope") == dependency.get("time_scope"), cid + ": dependency time_scope mismatch")
            require(dependency.get("status") != "withheld" or not active, cid + ": depends on withheld claim")
            require(dependency.get("status") != "conditional" or claim.get("status") != "supported", cid + ": cannot strengthen conditional dependency")
    # A narrow opt-in for explanations, not promotion of quarantined text to predictions.
    restricted_rules = {}
    for rid, rule in rules.items():
        rec = _KNOWLEDGE.interpretation_record(rule, sources.get(rule.get('source_id'), {}), catalog)
        if rec is not None:
            restricted_rules[rid] = rec
            registered = next(s for s in catalog['sources'] if s['id'] == rec['source_id'])
            expected_notice = _KNOWLEDGE.local_file(catalog_root, registered['license_path']).read_text(encoding='utf-8')
            metadata = rule.get('redistribution')
            require(isinstance(metadata, dict) and metadata.get('license_notice') == expected_notice,
                    rid + ': redistribution license_notice must preserve the complete registered license')

    def restricted_declarations(row, rid):
        require(row.get('reading_use') == _KNOWLEDGE.TRADITIONAL_USE, rid + ': restricted interpretation reading_use required')
        require(row.get('interpretation_label') == _KNOWLEDGE.TRADITIONAL_LABEL, rid + ': uncollated interpretation label required')
        require(row.get('authenticity_status') == 'uncollated_digital_transcription', rid + ': verified authority claim forbidden')
        require(row.get('predictive_status') == 'unvalidated', rid + ': interpretation is not predictively validated')
        require(row.get('guaranteed_prediction') is False, rid + ': guaranteed prediction forbidden')
        require(row.get('domain') == '传统结构解释', rid + ': restricted to traditional structural explanation')
        require(row.get('status') in ('conditional', 'withheld'), rid + ': interpretation cannot become supported')

    restricted_claims = {cid for cid, claim in claims.items()
                         if any(rid in restricted_rules for rid in claim.get('rule_ids', []))}
    # Preserve the limit transitively so another claim cannot launder the interpretation.
    changed = True
    while changed:
        before = len(restricted_claims)
        restricted_claims.update(cid for cid, claim in claims.items()
                                 if any(dep in restricted_claims for dep in claim.get('depends_on', [])))
        changed = before != len(restricted_claims)
    for cid in restricted_claims:
        claim = claims[cid]
        restricted_declarations(claim, cid)
        checks = claim.get('application_checks')
        if not require(isinstance(checks, list), cid + ': application_checks required'):
            continue
        expected = {rid for rid in claim.get('rule_ids', []) if rid in restricted_rules}
        ids = [row.get('rule_id') for row in checks if isinstance(row, dict)]
        if not require(len(ids) == len(checks) and len(set(str(v) for v in ids)) == len(ids)
                       and set(str(v) for v in ids) == expected, cid + ': checks must cover each restricted rule once'):
            continue
        for check in checks:
            rec = restricted_rules[check['rule_id']]
            for field, terms in [('conditions', rec['conditions']), ('exclusions', rec['exclusions'])]:
                rows = check.get(field)
                if not require(isinstance(rows, list) and len(rows) == len(terms), cid + ': complete ' + field + ' checklist required'):
                    continue
                for row, term in zip(rows, terms):
                    if not require(isinstance(row, dict), cid + ': invalid checklist item'):
                        continue
                    require(row.get('criterion') == term, cid + ': criterion must match registered card')
                    require(text(row.get('assessment')), cid + ': checklist assessment required')
                    allowed = {'met', 'not_met', 'unknown'} if field == 'conditions' else {'reviewed', 'unresolved'}
                    require(isinstance(row.get('result'), str) and row.get('result') in allowed, cid + ': invalid checklist result')
                    if claim.get('status') != 'withheld':
                        require(row.get('result') == ('met' if field == 'conditions' else 'reviewed'),
                                cid + ': unmet or unresolved criteria require withholding')
                    bound = row.get('fact_ids')
                    require(isinstance(bound, list) and bool(bound) and all(isinstance(v, str) and v in claim.get('fact_ids', []) for v in bound),
                            cid + ': each checklist item needs bound chart facts')
                    if isinstance(bound, list):
                        scenarios_seen = {facts[v]['scenario_id'] for v in bound if isinstance(v, str) and v in facts}
                        require(set(claim.get('scenario_ids', [])) <= scenarios_seen,
                                cid + ': checklist missing scenario evidence')
    for lid, link in links.items():
        if any(cid in restricted_claims for cid in link.get('claim_ids', [])):
            restricted_declarations(link, lid)
            if any(claims[cid].get('status') == 'withheld' for cid in link.get('claim_ids', []) if cid in claims):
                require(link.get('status') == 'withheld', lid + ': synthesis cannot strengthen a withheld member')
    visiting, visited = set(), set()
    def walk(cid):
        if cid in visiting:
            errors.append(cid + ": cyclic claim dependency")
            return
        if cid in visited:
            return
        visiting.add(cid)
        dependencies = claims[cid].get("depends_on", [])
        if isinstance(dependencies, list):
            for dep in dependencies:
                if isinstance(dep, str) and dep in claims:
                    walk(dep)
        visiting.remove(cid)
        visited.add(cid)
    for cid in claims:
        walk(cid)
    for lid, link in links.items():
        members = refs(link, "claim_ids", claims, True)
        require(len({c.get("system") for c in members}) >= 2, lid + ": synthesis requires independent systems")
        require(link.get("relation") in {"agreement", "conflict", "different_scope", "insufficient"}, lid + ": invalid relation")
        for key in ("explanation", "shared_inputs", "limits"):
            require(text(link.get(key)), lid + ": missing " + key)
        if link.get("relation") == "agreement":
            require(all(c.get("status") != "withheld" for c in members), lid + ": agreement uses withheld claim")
            for key in ("domain", "time_scope"):
                require(len({c.get(key) for c in members}) == 1, lid + ": agreement has mismatched " + key)
            require(len({tuple(sorted(c.get("scenario_ids", []))) for c in members}) == 1, lid + ": agreement has mismatched scenarios")
    # This field check is deliberately narrow, not a claim to detect unsafe prose.
    for rows in (claims, links):
        for cid, row in rows.items():
            require(not ({"probability", "confidence_percent", "accuracy_percent", "stars"} & set(row)), cid + ": unsupported numeric/star confidence field")
    return errors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ledger", type=Path)
    parser.add_argument("--root", type=Path, required=True, help="Private evidence directory; sources cannot escape it")
    args = parser.parse_args()
    try:
        data = json.loads(args.ledger.read_text(encoding="utf-8"))
        errors = validate(data, args.root)
    except (OSError, ValueError, RecursionError) as exc:
        print(json.dumps({"ok": False, "input_error": str(exc)}, ensure_ascii=False))
        return 2
    unverified = [r.get("id") for r in data.get("rules", []) if isinstance(r, dict) and r.get("attribution_kind") == "caller_declared_unverified"] if isinstance(data, dict) and isinstance(data.get("rules"), list) else []
    print(json.dumps({"ok": not errors, "errors": errors,
        "caller_declared_unverified_rule_ids": unverified,
        "provenance_notice": "未知资料即使标签齐全仍未验证来源；通过只表示结构与标签一致，不是原典认证",
        "scope": "结构、引用和文件一致性；不验证推断正确性或预测能力"}, ensure_ascii=False, indent=2))
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
