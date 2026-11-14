#!/usr/bin/env node
// Facts-only adapter. Interpretation authority is defined separately by the approved profile.
import { createRequire } from 'node:module';
import { readFileSync } from 'node:fs';
import { createHash } from 'node:crypto';
import { spawnSync } from 'node:child_process';
import { resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const defaultRepo = fileURLToPath(new URL('..', import.meta.url));
const argv = process.argv.slice(2);
if (argv.length === 1 && ['--help','-h'].includes(argv[0])) {
  console.log('Usage: node scripts/ziwei_dynamic_facts.mjs --solar YYYY-MM-DD --birth-year YYYY --shichen-index 0..11 --sex 男|女 --target-date YYYY-MM-DD --target-time-index 0..12 --source-label reading-id [--target-civil offset-bearing-ISO] [--repo path]');
  process.exit(0);
}
const args = {};
for (let i = 0; i < argv.length; i += 2) {
  if (!argv[i]?.startsWith('--') || argv[i + 1] === undefined) throw Error('Expected --key value pairs.');
  const key = argv[i].slice(2);
  if (key in args) throw Error('Duplicate argument: ' + key);
  args[key] = argv[i + 1];
}
const allowed = ['repo','solar','birth-year','shichen-index','sex','target-date','target-time-index','target-civil','source-label'];
for (const key of Object.keys(args)) if (!allowed.includes(key)) throw Error('Unknown argument: ' + key);
for (const key of ['solar','birth-year','shichen-index','sex','target-date','target-time-index','source-label']) {
  if (!(key in args)) throw Error('Required: --' + key);
}
const repo = resolve(args.repo ?? defaultRepo);
const engineDir = repo + '/scripts/pai_pan_ziwei';
const require = createRequire(engineDir + '/package.json');
const { astro } = require('iztro');
const { solar2lunar } = require('lunar-lite');
const { getMutagensByHeavenlyStem } = require('iztro/lib/utils/index.js');
const stems = [...'甲乙丙丁戊己庚辛壬癸'];
const branches = [...'子丑寅卯辰巳午未申酉戌亥'];
const kinds = ['禄','权','科','忌'];
function date(value) {
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value);
  if (!m) throw Error('Use explicit YYYY-MM-DD civil calendar dates.');
  const [y, mo, d] = m.slice(1).map(Number);
  const check = new Date(Date.UTC(y, mo - 1, d));
  if (y < 1901 || y > 2099 || check.getUTCFullYear() !== y ||
      check.getUTCMonth() !== mo - 1 || check.getUTCDate() !== d) {
    throw Error('Prototype accepts valid 1901-2099 dates only; this is an engineering bound.');
  }
  return y;
}
const birthClockYear = date(args.solar);
const birthYear = Number(args['birth-year']);
if (!/^\d{4}$/.test(args['birth-year']) || !Number.isInteger(birthYear) || birthYear < 1901 || birthYear > 2099 || Math.abs(birthYear - birthClockYear) > 1) {
  throw Error('--birth-year must be the explicit original civil birth year compatible with the resolved chart clock.');
}
const targetYear = date(args['target-date']);
for (const key of ['shichen-index','target-time-index']) {
  if (!/^[0-9]+$/.test(args[key])) throw Error('--' + key + ' requires an explicit non-empty decimal index.');
}
if (!args['source-label'].trim()) throw Error('--source-label must identify the input source.');
const birthIndex = Number(args['shichen-index']);
const targetIndex = Number(args['target-time-index']);
if (!Number.isInteger(birthIndex) || birthIndex < 0 || birthIndex > 11) throw Error('Birth index must match current wrapper: 0-11.');
if (!Number.isInteger(targetIndex) || targetIndex < 0 || targetIndex > 12) throw Error('Raw iztro target index must be explicit: 0-12.');
const targetCivil = args['target-civil'];
if (targetCivil !== undefined) {
  const clock = /^(\d{4}-\d{2}-\d{2})T([01]\d|2[0-3]):[0-5]\d(?::[0-5]\d(?:\.\d{1,6})?)?(?:Z|[+-](?:[01]\d|2[0-3]):[0-5]\d(?::[0-5]\d(?:\.\d{1,6})?)?)$/.exec(targetCivil);
  if (!clock || clock[1] !== args['target-date'] || Math.floor((Number(clock[2]) + 1) / 2) !== targetIndex) {
    throw Error('--target-civil must be an offset-bearing ISO clock matching the target date and index.');
  }
} else if (targetYear < birthYear || args['target-date'] < args.solar) {
  throw Error('Target precedes synthetic birth input. Supply the resolved target clock for facts-only replay.');
}
// The caller independently verifies physical birth and the query instant before personal admission.
const nativeReferenceYear = Math.max(targetYear, birthYear);
if (!['男','女'].includes(args.sex)) throw Error('--sex must be 男 or 女.');
const hash = file => createHash('sha256').update(readFileSync(file)).digest('hex');
const dependencies = {};
const lock = JSON.parse(readFileSync(engineDir + '/package-lock.json', 'utf8'));
for (const name of ['iztro','lunar-lite','lunar-typescript','lunar-javascript','dayjs','tsx']) {
  const pkg = JSON.parse(readFileSync(engineDir + '/node_modules/' + name + '/package.json', 'utf8'));
  const pinned = lock.packages['node_modules/' + name];
  if (pkg.version !== pinned.version) throw Error('Installed package does not match lock: ' + name);
  dependencies[name] = {version:pkg.version, integrity:pinned.integrity, resolved:pinned.resolved, license:pkg.license};
}
if (dependencies.iztro.version !== '2.6.1') throw Error('Prototype source was reviewed only for iztro 2.6.1.');
const nativeArgs = [
  '--import', engineDir + '/node_modules/tsx/dist/loader.mjs', engineDir + '/pai_pan.ts',
  '--solar', args.solar, '--shichen', branches[birthIndex], '--sex', args.sex,
  '--age-year', String(nativeReferenceYear), '--birth-year', String(birthYear), '--format', 'json',
];
const nativeRun = spawnSync(process.execPath, nativeArgs, {cwd:engineDir, encoding:'utf8', timeout:30000, maxBuffer:8*1024*1024});
if (nativeRun.status !== 0) throw Error('Existing wrapper failed: ' + nativeRun.stderr);
const native = JSON.parse(nativeRun.stdout);
const astrolabe = astro.bySolar(args.solar, birthIndex, args.sex, true, 'zh-CN');
const rawAstrolabe = astrolabe.toJSON();
const horoscope = astrolabe.horoscope(args['target-date'], targetIndex);
const raw = horoscope.toJSON();
const coordinate = (index) => {
  const p = rawAstrolabe.palaces[index];
  return p ? {iztro_array_index:index, earthly_branch:p.earthlyBranch,
    branch_index:branches.indexOf(p.earthlyBranch), natal_palace:p.name,
    raw_pointer:'/research_dynamic_iztro/source_astrolabe/palaces/' + index} : null;
};
const starsByName = name => rawAstrolabe.palaces.flatMap((p, pi) =>
  ['majorStars','minorStars','adjectiveStars'].flatMap(group => (p[group] ?? []).flatMap((s, si) =>
    s.name === name ? [{name, location:coordinate(pi), raw_pointer:'/research_dynamic_iztro/source_astrolabe/palaces/' + pi + '/' + group + '/' + si}] : [])));
const view = scope => {
  if (scope === 'daily' && targetIndex === 12) {
    return {status:'withheld',reason:'iztro_2_6_1_late_zi_day_coordinate_and_stem_mismatch',
      raw_pointer:'/research_dynamic_iztro/raw_horoscope/daily',
      interpretation:'Do not combine the source palace day with next-day stem/transformations.'};
  }
  const layer = raw[scope];
  return {
    raw_pointer:'/research_dynamic_iztro/raw_horoscope/' + scope,
    ming_coordinate:coordinate(layer.index),
    heavenly_stem:layer.heavenlyStem, earthly_branch:layer.earthlyBranch,
    domain_coordinates:layer.palaceNames.map((name, i) => ({layer_palace_name:name, natal_coordinate:coordinate(i)})),
    transformations:layer.mutagen.map((name,i)=>({kind:kinds[i],star:name,
      raw_pointer:'/research_dynamic_iztro/raw_horoscope/' + scope + '/mutagen/' + i,
      natal_star_locations:starsByName(name)})),
    flow_stars:layer.stars.map((row, i)=>({natal_coordinate:coordinate(i),stars:row})),
    interpretation_status:'facts_only_no_effect_verdict',
  };
};
const nativeDx = native.chart.daXians[native.chart.currentDaXianIndex] ?? null;
const rawDx = coordinate(raw.decadal.index);
const conflicts = [
  {
    id:'age_contract',
    native_age:native.chart.currentAge, raw_iztro_age:raw.age.nominalAge,
    native_definition:nativeReferenceYear === targetYear ? 'target civil year - original civil birth year + 1' :
      'original civil birth year used only for natal replay; the target has no legacy stage in its civil year',
    raw_iztro_definition:'target lunar year - birth lunar year + 1 (ageDivide=normal)',
    age_differs:native.chart.currentAge !== raw.age.nominalAge,
    native_current_decadal:nativeDx, raw_current_decadal:rawDx,
    decadal_location_differs:nativeDx?.palaceBranch !== rawDx?.branch_index,
    resolution:'Keep both layers separate. Raw decadal/age is not used to overwrite or explain native fields.',
  },
  {
    id:'annual_label_contract',
    native_yearly_label:{civil_year:nativeReferenceYear,stem:stems[((nativeReferenceYear-4)%10+10)%10],branch:branches[((nativeReferenceYear-4)%12+12)%12]},
    raw_iztro_yearly_label:{stem:raw.yearly.heavenlyStem,branch:raw.yearly.earthlyBranch},
    differs:stems[((nativeReferenceYear-4)%10+10)%10] !== raw.yearly.heavenlyStem ||
      branches[((nativeReferenceYear-4)%12+12)%12] !== raw.yearly.earthlyBranch,
    resolution:'Legacy annual text label is a civil-year tag. Raw iztro changes at lunar new year; never merge them.',
  },
];
const birthLunar = solar2lunar(args.solar);
const targetLunar = solar2lunar(args['target-date']);
const sourceFiles = [
  'scripts/pai_pan_ziwei/pai_pan.ts','scripts/pai_pan_ziwei/vendor/algorithm.ts',
  'scripts/pai_pan_ziwei/vendor/constants.ts','scripts/pai_pan_ziwei/vendor/sihua.ts',
  'scripts/pai_pan_ziwei/package-lock.json','knowledge/catalog.json','docs/time-contract.md',
  'docs/interpretation-standard.md','references/vendor/iztro-docs/learn/horoscope.md',
  'references/vendor/iztro-docs/learn/mutagen.md',
  'scripts/pai_pan_ziwei/node_modules/iztro/lib/astro/FunctionalAstrolabe.js',
  'scripts/pai_pan_ziwei/node_modules/iztro/lib/astro/astro.js',
  'scripts/pai_pan_ziwei/node_modules/iztro/lib/data/heavenlyStems.js',
  'scripts/pai_pan_ziwei/node_modules/lunar-lite/lib/ganzhi.js',
  'scripts/pai_pan_ziwei/node_modules/lunar-lite/lib/convertor.js',
];
const fixedTable = Object.fromEntries([...readFileSync(engineDir + '/vendor/constants.ts','utf8')
  .matchAll(/^\s*(\d): \[([^\]]+)\]/gm)].slice(0,10).map(m=>[stems[Number(m[1])],[...m[2].matchAll(/'([^']+)'/g)].map(x=>x[1])]));
const fortyCellCheck = stems.flatMap(stem => getMutagensByHeavenlyStem(stem).map((name,i)=>({
  stem,kind:kinds[i],native_fixed_star:fixedTable[stem][i],iztro_star:name,matched:fixedTable[stem][i]===name,
})));
const output = {
  schema_version:'ziwei-dynamic-facts-v1',
  status:'facts_only_separate_lunar_time_profile',
  inputs:{source_label:args['source-label'],birth:{solar:args.solar,original_civil_birth_year:birthYear,shichen_index:birthIndex,sex:args.sex,
    birth_clock_contract:'Already-resolved civil date and current-wrapper 0-11 index; no solar-clock/timezone conversion performed.'},
    target:{solar_date:args['target-date'],time_index:targetIndex,
      ...(targetCivil === undefined ? {} : {civil_time:targetCivil}),
      clock_contract:'Explicit caller-resolved civil calendar date plus iztro 0-12 time index; no Date/now/UTC-to-local conversion.'}},
  provenance:{repo,prototype_path:import.meta.url,prototype_sha256:hash(new URL(import.meta.url)),
    git_identity: 'Source identity is recorded by exact file hashes and lock; no parent repository state is read.',
    node:process.version,process_TZ:process.env.TZ??null,
    detected_runtime_timezone:Intl.DateTimeFormat().resolvedOptions().timeZone,
    dependencies,source_hashes:Object.fromEntries(sourceFiles.map(p=>[p,hash(repo+'/'+p)])),
    upstream:{repository:'https://github.com/SylarLong/iztro',tag:'v2.6.1',tag_commit:'b78dfe391f65e938d79f2419dddb80f74c6bbb8e',
      source:'https://github.com/SylarLong/iztro/blob/b78dfe391f65e938d79f2419dddb80f74c6bbb8e/src/astro/FunctionalAstrolabe.ts',
      license:'MIT; Copyright (c) 2023 All Contributors'},
    config:astro.getConfig(),source_docs_revision:'1beef80029cd3f1a40b769d3b1c911004ecb9789',
    native_invocation:[process.execPath,...nativeArgs],native_stdout_sha256:createHash('sha256').update(nativeRun.stdout).digest('hex'),
    scope:'Engine reproducibility and data contracts only. No personal readings, benchmark answers, interpretation rules or outcomes.'},
  native_wrapper_snapshot:native,
  admitted_dynamic_facts:{
    profile:'iztro-2.6.1-lunar-year-month-v1',
    usage:'year/month/day coordinates and raw labels only; no potency or event rules',
    native_age_and_decadal_unchanged:true,
    full_interval_coverage:false,
    snapshot_scope:'one caller-resolved calendar date and time index; not an entire query interval',
    forbidden_layers:['age','decadal','hourly'],
    layers:Object.fromEntries(['yearly','monthly','daily'].map(scope=>[scope, {status:'facts_only',...view(scope)}])),
  },
  research_dynamic_iztro:{
    source_astrolabe:rawAstrolabe,raw_horoscope:raw,
    selected_fact_views:Object.fromEntries(['yearly','monthly','daily'].map(scope=>[scope,view(scope)])),
    calendar_observation:{birth_lunar:birthLunar,target_lunar:targetLunar,
      lunar_leap_after_day15_changes_month_coordinate:targetLunar.isLeap && targetLunar.lunarDay>15,
      late_zi_warning:targetIndex===12?'2.6.1 uses targetDate for lunar/day palace index, while day stem/branch is next day at late Zi under forward. Inspect raw fields separately; not repaired here.':null},
    conflicts,
    forbidden_to_import_as_current_school:['raw_horoscope.age','raw_horoscope.decadal',
      'raw_horoscope.hourly','all potency or event interpretations'],
    fixed_table_check:{cells:fortyCellCheck,all_40_matched:fortyCellCheck.every(x=>x.matched)},
  },
};
console.log(JSON.stringify(output,null,2));
