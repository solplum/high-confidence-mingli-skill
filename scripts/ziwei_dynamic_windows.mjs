#!/usr/bin/env node
// Plan civil date windows for the locked Ziwei fact adapter.
import { createHash } from 'node:crypto';
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';

const DAY = 86400000;
const FIRST = '1901-01-01';
const LIMIT = '2100-01-01';
const engine = new URL('./pai_pan_ziwei/', import.meta.url);
const help = 'Usage: node scripts/ziwei_dynamic_windows.mjs --start YYYY-MM-DD --end YYYY-MM-DD --layer year|month|day';

function readArgs(argv) {
  const args = new Map();
  for (let i = 0; i < argv.length; i += 2) {
    const [key, value] = argv.slice(i, i + 2);
    if (!['--start', '--end', '--layer'].includes(key) || value === undefined || args.has(key)) {
      throw Error(help);
    }
    args.set(key, value);
  }
  const start = args.get('--start');
  const end = args.get('--end');
  const layer = args.get('--layer');
  if (!start || !end || !['year', 'month', 'day'].includes(layer)) throw Error(help);
  return {start, end, layer};
}

function civilDay(text, allowLimit) {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(text) || text < FIRST || text > LIMIT ||
      (!allowLimit && text === LIMIT)) {
    throw Error('Use civil date labels from 1901–2099; 2100-01-01 is only an exclusive end.');
  }
  // UTC is an iterator for date labels. It is not the user's query timezone.
  const date = new Date(text + 'T00:00:00Z');
  if (!Number.isFinite(date.getTime()) || label(date) !== text) {
    throw Error('Invalid civil date: ' + text);
  }
  return date.getTime();
}

function label(date) {
  return date.toISOString().slice(0, 10);
}

function calendar() {
  const require = createRequire(new URL('package.json', engine));
  const lock = readFileSync(new URL('package-lock.json', engine));
  const pinned = JSON.parse(lock).packages;
  const versions = {};
  for (const name of ['iztro', 'lunar-lite', 'lunar-typescript']) {
    const packagePath = new URL('node_modules/' + name + '/package.json', engine);
    const installed = JSON.parse(readFileSync(packagePath, 'utf8')).version;
    if (installed !== pinned['node_modules/' + name]?.version) {
      throw Error('Installed package does not match lock: ' + name);
    }
    versions[name] = installed;
  }
  const { astro } = require('iztro');
  if (versions.iztro !== '2.6.1' || astro.getConfig().horoscopeDivide !== 'normal') {
    throw Error('This window planner requires the existing iztro 2.6.1 lunar year/month profile.');
  }
  return {
    solar2lunar: require('lunar-lite').solar2lunar,
    versions, lock_sha256: createHash('sha256').update(lock).digest('hex'),
  };
}

function boundaryReasons(previous, next, layer) {
  const reasons = [];
  if (previous.civilYear !== next.civilYear) reasons.push('legacy_civil_year');
  if (previous.lunarYear !== next.lunarYear) reasons.push('lunar_new_year');
  if (layer !== 'year') {
    if (previous.lunarMonth !== next.lunarMonth || previous.isLeap !== next.isLeap) {
      reasons.push('lunar_month_start');
    }
    if (next.isLeap && next.lunarDay === 16) reasons.push('leap_month_second_half');
  }
  if (layer === 'day') reasons.push('civil_date_change');
  return reasons;
}

function plan({start, end, layer}) {
  const first = civilDay(start, false);
  const limit = civilDay(end, true);
  if (first >= limit) throw Error('The exclusive end must be later than the start.');
  const {solar2lunar, versions, lock_sha256} = calendar();
  const segments = [];
  let previous = null;
  for (let day = first; day < limit; day += DAY) {
    const civil = label(new Date(day));
    const {lunarYear, lunarMonth, lunarDay, isLeap} = solar2lunar(civil);
    const next = {civilYear: Number(civil.slice(0, 4)), lunarYear, lunarMonth, lunarDay, isLeap};
    const reasons = previous === null ? ['query_start'] : boundaryReasons(previous, next, layer);
    if (reasons.length) {
      if (segments.length) segments[segments.length - 1].end_exclusive = civil;
      segments.push({
        start_inclusive: civil, end_exclusive: end, boundary_reasons: reasons,
        calendar_at_start: next,
        probe: {target_date: civil, target_time_index: 0},
      });
    }
    previous = next;
  }
  return {
    schema_version: 'ziwei-dynamic-windows-v1',
    profile: 'iztro-2.6.1-lunar-year-month-v1', layer,
    interval_semantics: 'caller_resolved_civil_date_labels_start_inclusive_end_exclusive',
    scope: 'calendar_window_plan_only; run ziwei_dynamic_facts.mjs for each point',
    start, end, segments,
    provenance: {versions, lock_sha256, calendar_function: 'lunar-lite:solar2lunar'},
  };
}

try {
  const argv = process.argv.slice(2);
  if (argv.length === 1 && ['--help', '-h'].includes(argv[0])) {
    console.log(help);
  } else {
    console.log(JSON.stringify(plan(readArgs(argv)), null, 2));
  }
} catch (error) {
  console.error(error.message);
  process.exitCode = 2;
}
