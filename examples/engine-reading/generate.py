#!/usr/bin/env python3
"""Reproducible ENGINE QA using fictional inputs, not an automatic fortune teller.
No network or user inputs. Human-authored, deliberately bounded interpretations.
"""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'scripts'))
import pai_pan_bazi as bazi
from datetime import timedelta

def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    cases = [('summer', '2000-05-15', '12:00', 'civil'),
             ('before-zi', '2000-05-15', '22:59', 'civil'),
             ('after-zi', '2000-05-15', '23:01', 'civil'),
             ('solar-zi', '2000-05-15', '22:59', 'apparent-solar')]
    term = bazi.solar_term_beijing(2000, 315)
    for name, delta in [('before-term', -2), ('after-term', 2)]:
        dt = term + timedelta(minutes=delta)
        cases.append((name, dt.strftime('%Y-%m-%d'), dt.strftime('%H:%M'), 'civil'))
    snapshots, commands = {}, []
    for name, day, hour, basis in cases:
        cmd = [sys.executable, str(ROOT / 'scripts/build_chart.py'), '--solar', day,
               '--hour', hour, '--sex', '男', '--lat', '31.23', '--lon', '121.47',
               '--analysis-year', '2026', '--time-basis', basis, '--format', 'json']
        result = subprocess.run(cmd, check=True, text=True, capture_output=True)
        data = json.loads(result.stdout)
        assert data['ziwei'] is not None, data['degradation']
        snapshots[name] = data
        save(OUT / (name + '.json'), data)
        commands.append({'scenario_id': name, 'argv': ['python3', 'scripts/build_chart.py'] + cmd[2:]})
    save(OUT / 'commands.json', commands)
    # Executed boundaries, not guessed values or validator-only fixtures.
    assert snapshots['before-zi']['bazi']['pillars']['day'] != snapshots['after-zi']['bazi']['pillars']['day']
    assert snapshots['before-term']['bazi']['pillars']['year'] != snapshots['after-term']['bazi']['pillars']['year']
    assert snapshots['before-term']['bazi']['pillars']['month'] != snapshots['after-term']['bazi']['pillars']['month']
    assert snapshots['before-zi']['qizheng'] == snapshots['solar-zi']['qizheng']
    assert snapshots['before-zi']['bazi']['pillars']['hour'] != snapshots['solar-zi']['bazi']['pillars']['hour']
    ledger = dict(schema_version=1, purpose='synthetic_test', sources=[], scenarios=[], facts=[], rules=[], claims=[], syntheses=[])
    for name, day, hour, basis in cases:
        ledger['scenarios'].append(dict(id=name, label='虚构输入 '+name, time_basis=basis,
            assumptions='工程案例；非真实人。固定 UTC+08；经纬度为上海附近公共坐标。节气候选由同一引擎定位，不是外部天文黄金值。'))
        for system in ('bazi', 'ziwei', 'qizheng'):
            ledger['sources'].append(dict(id=name+'-'+system,kind='chart',path=name+'.json',
                sha256=digest(OUT/(name+'.json')),system=system,scenario_id=name,pointer_prefix='/'+system))
    rules = [('bazi', 'references/bazi/classical-texts.md', '夏生火旺，须用水调候；冬生水旺，须用火调候。'),
             ('ziwei', 'references/ziwei/classics.md', '空宫借对宫论事'),
             ('qizheng', 'references/qizheng/reading.md', '**身宫/身主引擎未算**')]
    for system, path, needle in rules:
        source = ROOT/path
        dest = OUT/(system+'-source.md')
        shutil.copyfile(source, dest)
        lines = source.read_text().splitlines()
        n = next(i for i,line in enumerate(lines,1) if needle in line)
        ledger['sources'].append(dict(id=system+'-source',kind='reference',path=dest.name,sha256=digest(dest)))
        ledger['rules'].append(dict(id=system+'-rule',system=system,source_id=system+'-source',school='本仓整理资料，未核原刊本',
            locator=path+':'+str(n),start_line=n,end_line=n,quote=lines[n-1],
            **({'attribution_kind': 'registered_source_excerpt', 'source_label': '本地上游整理资料（未核原典版本）'} if system in ('bazi', 'ziwei') else {'attribution_kind': 'caller_declared_unverified', 'source_label': '调用方提供的未核验资料（非核验古籍原文）'})))
    def fact(system, scenario, pointer):
        value=snapshots[scenario]
        for part in pointer.strip('/').split('/'):
            value=value[int(part)] if isinstance(value,list) else value[part]
        fid='f'+str(len(ledger['facts']))
        ledger['facts'].append(dict(id=fid,system=system,scenario_id=scenario,source_id=scenario+'-'+system,pointer=pointer,value=value))
        return fid
    summer_ids=['summer','before-zi','after-zi','solar-zi']
    def claim(cid, system, scenarios, facts, statement, counter, alternative, plain, technical, boundary='conditional', status='conditional'):
        ledger['claims'].append(dict(id=cid,system=system,domain='解释范围',time_scope='本命传统解释',statement=statement,status=status,
            fact_ids=facts,rule_ids=[system+'-rule'],depends_on=[],scenario_ids=scenarios,
            conditions='仅限所列虚构候选与本仓口径；不能据此推断真实人的经历。',counterevidence=counter,alternatives=alternative,
            boundary=boundary,explanation=dict(plain=plain,technical=technical,action='先核对出生记录；现实决定以实际情况为准。'),
            limitations='可追溯的有限解释，不是完整详批或预测效力评测。'))
    bf=[fact('bazi',x,'/bazi/pillars/'+p) for x in summer_ids for p in ['month','day','hour']]
    claim('bazi-season','bazi',summer_ids,bf,'夏季调候仅是候选观察角度，不据此确定喜用或性格。',
        '日柱在 23 点前后改变；月柱相同不能证明完整格局相同。未完成通根强弱及破格逐项评估。',
        '旺衰或格局体系需另行评估；季节总则不能替代各日干十二月细则。',
        '出生时间靠近一天的分界时，部分计算可能改变，解释需要重新检查。本例不足以确定两个候选是否支持同一套性格描述。',
        '四个五月候选均巳月；日时字段不同。摘要中的夏生总则只支持开始检查季节，不支持确定用神。')
    empty=next(i for i,p in enumerate(snapshots['summer']['ziwei']['chart']['palaces']) if p['isEmpty'])
    zf=[fact('ziwei','summer',f'/ziwei/chart/palaces/{empty}/'+key) for key in ['name','isEmpty','stars','borrowedStars','borrowedFromName']]
    claim('ziwei-borrow','ziwei',['summer'],zf,'空宫的借星是解释关系，不是原宫实有，也不是该生活领域为空。',
        '本宫仍有辅星；没有主星不等于没有信息。这里只检查空宫字段和借星来源，未判吉凶。',
        '不采用借星的派别需另行说明；三方四正与四化尚未完整分析。',
        '图上有些位置没有主要标记，不代表生活里缺少这件事；这里不据此判断家庭或财产好坏。',
        '实际快照田宅为空宫，借子女宫天同、天梁；借用不改写原宫 stars。', boundary='unassessed')
    qf=[fact('qizheng',x,'/qizheng/day_night/type') for x in ['before-zi','after-zi','solar-zi']]
    claim('qizheng-limit','qizheng',['before-zi','after-zi','solar-zi'],qf,'夜生所重身度主字段未计算，相关综合判断暂不作出。',
        '现有命度、宫主数据不能替代缺失的身主；已有其他字段不消除这项缺口。',
        '可只描述十一曜位置；若需完整身主解释须另有核实过的算法和资料。',
        '这部分缺少关键计算，暂时不下结论；不能把缺数据说成对你不利。',
        '夜生三个候选触发 reading.md 的身宫/身主未算限制。', status='withheld')
    ledger['syntheses'].append(dict(id='comparison',claim_ids=['bazi-season','ziwei-borrow','qizheng-limit'],relation='insufficient',
        explanation='各盘只完成不同范围的局部检查，不能据此合成个人性格或事件结论。',shared_inputs='共用出生输入、地点、程序及本仓整理资料。',limits='没有可称独立验证的现实结果。'))
    save(OUT/'ledger.json',ledger)
    result=subprocess.run([sys.executable,str(ROOT/'scripts/validate_claim_ledger.py'),str(OUT/'ledger.json'),'--root',str(OUT)],text=True,capture_output=True,check=True)
    (OUT/'validation.json').write_text(result.stdout)
    rows=[]
    for name,_,_,basis in cases:
        s=snapshots[name]
        pillars=[''.join(s['bazi']['pillars'][p][:2]) for p in ['year','month','day','hour']]
        rows.append('- '+name+'：'+basis+'；'+s['time']['chart_clock']+'；'+ ' / '.join(pillars)+'；'+s['qizheng']['day_night']['type'])
    (OUT/'boundary-results.md').write_text('# 实际运行边界结果\n\n'+'\n'.join(rows)+'\n\n断言通过：23 点前后日柱变化；立春前后年/月柱变化；同一瞬间换太阳钟面不改变七政结果，但改变本例八字时柱。\n')
    report = ["# 虚构输入演示：这次能说到哪里", "",
        "这是工程演示，不对应真实的人，也不是完整人生详批。最重要的结果是：出生时间靠近分界时，部分计算会改变；缺少关键资料时应当停下来，而不是补一段听起来很准的话。", "",
        "## 一、第一套方法", ledger['claims'][0]['explanation']['plain'],
        "为什么：四个五月候选共享季节，但分界前后的计算不同。现有材料不足以确定性格或人生走向。[bazi-season]", "",
        "## 二、第二套方法", ledger['claims'][1]['explanation']['plain'],
        "为什么：计算区分原有标记和从另一位置参照的标记，不能把参照内容说成原本就有。[ziwei-borrow]", "",
        "## 三、第三套方法", ledger['claims'][2]['explanation']['plain'],
        "为什么：夜间候选需要的一项关键计算尚未实现，已有其他结果不能替代它。[qizheng-limit]", "",
        "## 四、放在一起怎么看", "这三条检查回答的问题不同，不能拼成一个关于你的结论，也不能说三次一致就更准确。", "",
        "## 五、可以做什么", "如果这是真实咨询，先核对出生记录和时间误差，再决定哪些部分值得继续分析。生活中的重要决定要看现实证据，而不是这份图。", "",
        "## 六、过去经历", "本例没有真实经历，也没有进行准确率验证。没有样例可以继续，不需要编造或反复追问。", "",
        "## 七、收束", "目前能把握的是资料与判断之间的距离：知道哪些已经查过，哪些没有查过。暂时没有结论，也比把缺口包装成答案更有用。", "",
        "技术附录另见 ledger.json、boundary-results.md 与 README.md。正文由本文件中的明确模板生成，不是完整自动解读器。"]
    (OUT/'report.md').write_text("\n".join(report)+"\n")
    print('6 actual three-engine scenarios; boundary assertions and ledger validation passed.')

if __name__=='__main__':
    main()
