#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""gersang-db 문서 생성기.

입력: data/monsters.json (수집 원본), data/areas.tsv (공식 지역안내 수집본)
출력: monsters/*.md, dungeons/dungeon_directory.md, items/*.md, data/dungeons.json,
      data/drops_index.json, data/monsters.csv
"""
import csv, json, os, re, sys
from collections import OrderedDict, defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, 'data')

ELEM_EN = {'불': '火', '물': '水', '바람': '風', '뇌전': '雷', '땅': '地'}
ELEM_ORDER = ['불', '물', '바람', '뇌전', '땅']


def load():
    monsters = json.load(open(os.path.join(DATA, 'monsters.json'), encoding='utf-8'))
    areas = []
    p = os.path.join(DATA, 'areas.tsv')
    if os.path.exists(p):
        for line in open(p, encoding='utf-8'):
            line = line.rstrip('\n')
            if not line.strip():
                continue
            f = line.split('\t')
            while len(f) < 7:
                f.append('')
            areas.append({'nation': f[0], 'name': f[1], 'location': f[2],
                          'entry': f[3], 'floors': f[4], 'feature': f[5], 'desc': f[6]})
    return monsters, areas


def fmt(n):
    return '—' if n is None or n == '' else f'{n:,}'


def elem_label(r):
    if r.get('element_raw'):
        return f"{r['element_raw']}({r['element']})"
    if r.get('element'):
        return r['element']
    return '무속성'


def stat_line(r):
    s = r.get('stats') or {}
    parts = []
    for k in ('힘', '민첩', '생명력', '지력'):
        parts.append(f"{k} {fmt(s.get(k))}")
    return ' · '.join(parts)


def combat_line(r):
    parts = [f"HP {fmt(r.get('hp'))}"]
    if r.get('hit_res') is not None or r.get('mag_res') is not None:
        parts.append(f"타격저항 {fmt(r.get('hit_res'))}%")
        parts.append(f"마법저항 {fmt(r.get('mag_res'))}%")
    parts.append(f"속성값 {fmt(r.get('elem_value'))}")
    parts.append(f"EXP {fmt(r.get('exp'))}")
    return ' · '.join(parts)


def monster_block(r, suffix=''):
    head = f"### {r['name']}" + (f" — {suffix}" if suffix else '')
    meta = [f"속성 {elem_label(r)}"]
    if r.get('grade'):
        meta.append(f"{r['grade']}등급")
    if r.get('category'):
        meta.append(r['category'])
    if r.get('variants', 1) > 1:
        meta.append(f"동일 스펙 {r['variants']}종 출현")
    out = [head, '- ' + ' · '.join(meta)]
    if any([r.get('hp'), r.get('hit_res'), r.get('exp')]):
        out.append('- ' + combat_line(r))
    if any((r.get('stats') or {}).values()):
        out.append('- 기본 스탯: ' + stat_line(r))
    if r.get('drops'):
        out.append('- 드랍: ' + ', '.join(r['drops']))
    return '\n'.join(out)


# 던전 -> 문서 배정
DOC_MAP = {
 '01_starter_and_fields': ['조선 필드', '일본 필드', '중국 필드', '대만 필드', '초보자 군영',
                           '하위 던전 주요 몬스터', '원공의 대나무숲', '검은 상단 야영지',
                           '수련장', '기타'],
 '02_classic_dungeons': ['대관령', '월기봉', '고수동굴', '무령왕릉', '거제해저동굴', '일본해저동굴',
                         '대만해저동굴', '귀곡성', '이시즈치산 1~2층', '대설산얼음계곡', '얼음성',
                         '한라산', '화구산', '하치만타이온천', '영혼의숲'],
 '03_famous_dungeons': ['유명계', '천년호', '륭산', '소림사', '만리장성', '진시황릉',
                        '챠우 신전·수호신의 호수', '샤오링의후원', '대둔산', '해적동굴', '북해빙굴',
                        '왕의무덤·몽골', '계림·오로치의둥지·빙궁·야수림', '파오의탑', '수상한 동굴',
                        '검은상단주둔지'],
 '04_india_and_sacred': ['석굴 사원', '태양사원', '데바의사원', '버려진 해안사원', '인도 무투장',
                         '타지마할', '백호림', '청룡담', '개마장원'],
 '05_sumisan_and_shinsungok': ['수미산', '신선곡', '염마굴(火)·흑룡담(水)·신선곡(風雷)',
                               '일천귀문(火雷)·월천귀문(水風)'],
 '06_endgame_dungeons': ['광려산 정상', '광려산 소금', '광려산 지하신전',
                         '광려산 은신처(火雷)·협곡(水風)', '환상계곡 석양(火雷)·새벽(水風)',
                         '악몽의틈(火雷)·악몽의근원(水風)', '별의 방', '샴발라 천옥',
                         '샴발라 관문·용맹의 시험장', '격전의 샴발라·홍염의 누각',
                         '검은상단 암시장', '여명·잠식·암흑', '천옥 신장'],
}
DOC_TITLES = {
 '01_starter_and_fields': '01. 초보자 군영 · 필드 몬스터',
 '02_classic_dungeons': '02. 클래식 던전',
 '03_famous_dungeons': '03. 유명 던전',
 '04_india_and_sacred': '04. 인도 · 성수(聖獸) 사냥터',
 '05_sumisan_and_shinsungok': '05. 수미산 · 신선곡',
 '06_endgame_dungeons': '06. 엔드게임 던전',
 '07_bosses_and_mythic': '07. 보스 · 신화급 존재',
 '08_special': '08. 특수 · 소환 · 이벤트 몬스터',
}
DOC_ORDER = ['01_starter_and_fields', '02_classic_dungeons', '03_famous_dungeons',
             '04_india_and_sacred', '05_sumisan_and_shinsungok', '06_endgame_dungeons',
             '07_bosses_and_mythic', '08_special']

DUNG2DOC = {}
for doc, lst in DOC_MAP.items():
    for d in lst:
        DUNG2DOC[d] = doc


def doc_for(dungeon):
    if dungeon in DUNG2DOC:
        return DUNG2DOC[dungeon]
    return '08_special'


# 공식 지역안내 이름 -> 데이터 던전 라벨
AREA_ALIAS = {
 '해저동굴(거제)': ['거제해저동굴'],
 '해저동굴(일본)': ['일본해저동굴'],
 '해저동굴(대만)': ['대만해저동굴'],
 '대설산 얼음계곡': ['대설산얼음계곡', '얼음성'],
 '석굴던전': ['석굴 사원'],
 '타지마할정원': ['타지마할'],
 '챠우신전': ['챠우 신전·수호신의 호수'],
 '빙궁': ['계림·오로치의둥지·빙궁·야수림'],
 '계림': ['계림·오로치의둥지·빙궁·야수림'],
 '환상계곡(석양)': ['환상계곡 석양(火雷)·새벽(水風)'],
 '환상계곡(새벽)': ['환상계곡 석양(火雷)·새벽(水風)'],
 '광려산은신처': ['광려산 은신처(火雷)·협곡(水風)'],
 '광려산협곡': ['광려산 은신처(火雷)·협곡(水風)'],
 '광려산 정상': ['광려산 소금', '광려산 지하신전'],
 '신선곡': ['신선곡', '일천귀문(火雷)·월천귀문(水風)'],
 '염마굴': ['염마굴(火)·흑룡담(水)·신선곡(風雷)'],
 '흑룡담': ['염마굴(火)·흑룡담(水)·신선곡(風雷)'],
 '악몽의 틈': ['악몽의틈(火雷)·악몽의근원(水風)'],
 '악몽의 근원': ['악몽의틈(火雷)·악몽의근원(水風)'],
 '왕의무덤': ['왕의무덤·몽골'],
 '검은상단야영지': ['검은 상단 야영지'],
 '검은상단주둔지': ['검은상단주둔지'],
}


def build_dungeons(monsters, areas):
    byd = defaultdict(list)
    for m in monsters:
        byd[m['dungeon']].append(m)
    dungeons = []
    used = set()
    for a in areas:
        labels = AREA_ALIAS.get(a['name'], [a['name']])
        mem = []
        for l in labels:
            used.add(l)
            mem.extend(byd.get(l, []))
        hps = [m['hp'] for m in mem if m.get('hp')]
        exps = [m['exp'] for m in mem if m.get('exp')]
        els = [m['element'] for m in mem if m.get('element')]
        dungeons.append(OrderedDict([
            ('name', a['name']), ('nation', a['nation']), ('location', a['location']),
            ('entry', a['entry']), ('floors', a['floors']), ('feature', a['feature']),
            ('official_monsters', a['desc']),
            ('labels', labels),
            ('monster_count', len(mem)),
            ('monster_ids', [m['id'] for m in mem]),
            ('hp_min', min(hps) if hps else None), ('hp_max', max(hps) if hps else None),
            ('exp_min', min(exps) if exps else None), ('exp_max', max(exps) if exps else None),
            ('elements', sorted(set(els), key=ELEM_ORDER.index)),
            ('source', 'gersang.co.kr/info/area.gs'),
        ]))
    for lbl, mem in byd.items():
        if lbl in used:
            continue
        hps = [m['hp'] for m in mem if m.get('hp')]
        exps = [m['exp'] for m in mem if m.get('exp')]
        els = [m['element'] for m in mem if m.get('element')]
        dungeons.append(OrderedDict([
            ('name', lbl), ('nation', None), ('location', None), ('entry', None),
            ('floors', None), ('feature', None), ('official_monsters', None),
            ('labels', [lbl]), ('monster_count', len(mem)),
            ('monster_ids', [m['id'] for m in mem]),
            ('hp_min', min(hps) if hps else None), ('hp_max', max(hps) if hps else None),
            ('exp_min', min(exps) if exps else None), ('exp_max', max(exps) if exps else None),
            ('elements', sorted(set(els), key=ELEM_ORDER.index)),
            ('source', 'gogolap.com'),
        ]))
    return dungeons


def write_monster_docs(monsters, dungeons):
    bydoc = defaultdict(lambda: defaultdict(list))
    for m in monsters:
        bydoc[doc_for(m['dungeon'])][m['dungeon']].append(m)
    area_by_name = {d['name']: d for d in dungeons}
    for doc in DOC_ORDER:
        if doc == '07_bosses_and_mythic':
            continue
        lines = [f"# {DOC_TITLES[doc]}", '',
                 '> 출몰 위치 · 등급 · 기본 스탯(힘/민첩/생명력/지력)은 거상 공식 홈페이지 기반 데이터,',
                 '> HP · 타격저항 · 마법저항 · 속성값 · EXP 는 커뮤니티 도감(gogolap) 수치다. 자세한 출처는 [README](../README.md).',
                 '> 값이 `—` 인 항목은 확인된 자료가 없는 것이다(추정값을 넣지 않았다).', '']
        if doc not in bydoc:
            lines.append('_수집된 몬스터가 없다._')
        for dung in sorted(bydoc[doc], key=lambda d: -max((m['hp'] or 0) for m in bydoc[doc][d])):
            mem = bydoc[doc][dung]
            a = area_by_name.get(dung) or {}
            lines.append(f"## {dung}")
            lines.append('')
            meta = []
            if a.get('nation'):
                meta.append(a['nation'])
            if a.get('entry'):
                meta.append(f"입장 {a['entry']}")
            if a.get('floors'):
                meta.append(a['floors'])
            if meta:
                lines.append('**' + ' · '.join(meta) + '**')
            if a.get('location') or a.get('feature'):
                bits = []
                if a.get('location'):
                    bits.append(f"위치 {a['location']}")
                if a.get('feature'):
                    bits.append(a['feature'])
                lines.append('> ' + ' · '.join(bits))
            hps = [m['hp'] for m in mem if m.get('hp')]
            exps = [m['exp'] for m in mem if m.get('exp')]
            summ = [f"수록 {len(mem)}종"]
            if hps:
                summ.append(f"HP {fmt(min(hps))} ~ {fmt(max(hps))}")
            if exps:
                summ.append(f"EXP {fmt(min(exps))} ~ {fmt(max(exps))}")
            els = sorted({m['element'] for m in mem if m.get('element')}, key=ELEM_ORDER.index)
            if els:
                summ.append('속성 ' + '·'.join(els))
            lines.append('')
            lines.append('_' + ' · '.join(summ) + '_')
            lines.append('')
            dup = defaultdict(int)
            for mm in mem:
                dup[mm['name']] += 1
            for m in sorted(mem, key=lambda x: (-(x['hp'] or 0), x['name'])):
                suffix = ''
                if dup[m['name']] > 1:
                    suffix = elem_label(m) + (' ' + m['category'] if m.get('category') else '')
                    if m.get('hp'):
                        suffix += f" · HP {fmt(m['hp'])}"
                lines.append(monster_block(m, suffix))
                lines.append('')
        path = os.path.join(ROOT, 'monsters', doc.split('_', 1)[0] + '_' + doc.split('_', 1)[1] + '.md')
        os.makedirs(os.path.dirname(path), exist_ok=True)
        open(path, 'w', encoding='utf-8').write('\n'.join(lines).rstrip() + '\n')
        print('wrote', path, len(lines))


BOSS_GROUPS = [
 ('사대 신수 (수미산)', ['신수청룡', '신수백호', '신수주작', '신수현무']),
 ('사대 흉수 · 각성 흉수', ['흉포한도철', '흉포한 도철', '냉혹한궁기', '냉혹한 궁기', '끈질긴도올', '끈질긴 도올',
                        '광기의혼돈', '광기의 혼돈', '타락한도철', '타락한 도철', '도철', '궁기', '도올', '혼돈']),
 ('사천왕', ['지국천왕', '광목천왕', '증장천왕', '다문천왕']),
 ('명왕', ['암흑명왕', '암흑 애염명왕', '암흑 육자명왕', '암흑 마두명왕', '암흑 공작명왕']),
 ('차원 · 신장 보스', ['진천신장', '현성신장', '개문신장', '경문신장', '나문신장']),
 ('지역 최종 보스', ['염라대왕', '불타는화룡', '불타는화룡(火)', '광풍의 아우타', '광호', '마룡', '백귀', '혼마',
                  '챠우_진(眞)', '파오_진(眞)', '불사의 진시황', '도철', '수룡', '바다의사신', '해저왕', '눈코끼리',
                  '라바나', '야마와 야미', '궁기', '도올', '혼돈', '오로치', '사악한이무기', '극우령_챠우',
                  '우귀', '탐', '야주타', '현천무녀소혼']),
]


def write_index_doc(monsters):
    bydoc = defaultdict(list)
    for m in monsters:
        bydoc[doc_for(m['dungeon'])].append(m)
    lines = ['# 몬스터 전체 색인 (가나다순)', '',
             '> 이름으로 몬스터를 찾을 때 쓰는 색인이다. 오른쪽은 상세 문서와 출몰지다.', '',
             '| 몬스터 | 속성 | 등급 | HP | 출몰지 | 문서 |', '|---|---|---|---|---|---|']
    docname = {}
    for doc in DOC_ORDER:
        fname = doc + '.md'
        docname[doc] = fname
    paths = {}
    for root, _, files in os.walk(os.path.join(ROOT, 'monsters')):
        for f in files:
            if re.match(r'^\d\d_', f):
                paths[f[:2]] = f
    for m in sorted(monsters, key=lambda x: x['name']):
        doc = doc_for(m['dungeon'])
        f = paths.get(doc[:2], doc + '.md')
        lines.append('| {} | {} | {} | {} | {} | [{}]({}) |'.format(
            m['name'], elem_label(m), m.get('grade') or '—', fmt(m.get('hp')),
            m['dungeon'], f[:2], f))
    lines.append('')
    path = os.path.join(ROOT, 'monsters', '00_index.md')
    open(path, 'w', encoding='utf-8').write('\n'.join(lines) + '\n')
    print('wrote', path)


def write_boss_doc(monsters):
    idx = defaultdict(list)
    for m in monsters:
        idx[m['name']].append(m)
        idx[re.sub(r'\s+', '', m['name'])].append(m)
    lines = ['# 07. 보스 · 신화급 존재', '',
             '> 이 파일은 다른 문서에 흩어져 있는 보스급 개체를 한눈에 보기 위한 색인이다. 수치는 각 개체의 출몰지 기준이며,',
             '> 상세 서식 정보는 같은 이름을 찾아 해당 던전 문서(02~06)를 보면 된다.', '']
    seen = set()
    for title, names in BOSS_GROUPS:
        rows = []
        for n in names:
            for m in idx.get(n, []) + idx.get(re.sub(r'\s+', '', n), []):
                key = (m['id'],)
                if key in seen:
                    continue
                seen.add(key)
                rows.append(m)
        if not rows:
            continue
        lines.append(f'## {title}')
        lines.append('')
        lines.append('| 이름 | 던전 | 속성 | 등급 | HP | 타저 | 마저 | 속성값 | EXP | 드랍 |')
        lines.append('|---|---|---|---|---|---|---|---|---|---|')
        for m in sorted(rows, key=lambda x: -(x['hp'] or 0)):
            drops = ', '.join(m['drops'][:4]) + (' 외' if len(m['drops']) > 4 else '')
            lines.append('| {} | {} | {} | {} | {} | {} | {} | {} | {} | {} |'.format(
                m['name'], m['dungeon'], elem_label(m), m.get('grade') or '—',
                fmt(m.get('hp')), fmt(m.get('hit_res')), fmt(m.get('mag_res')),
                fmt(m.get('elem_value')), fmt(m.get('exp')), drops or '—'))
        lines.append('')
    lines.append('## 전 던전 보스 목록(자동 추출)')
    lines.append('')
    lines.append('| 이름 | 던전 | 속성 | HP | 타저 | 마저 | 속성값 | EXP |')
    lines.append('|---|---|---|---|---|---|---|---|')
    bosses = [m for m in monsters if '보스' in (m.get('category') or '')]
    for m in sorted(bosses, key=lambda x: -(x['hp'] or 0)):
        lines.append('| {} | {} | {} | {} | {} | {} | {} | {} |'.format(
            m['name'], m['dungeon'], elem_label(m), fmt(m.get('hp')), fmt(m.get('hit_res')),
            fmt(m.get('mag_res')), fmt(m.get('elem_value')), fmt(m.get('exp'))))
    lines.append('')
    path = os.path.join(ROOT, 'monsters', '07_bosses_and_mythic.md')
    open(path, 'w', encoding='utf-8').write('\n'.join(lines) + '\n')
    print('wrote', path, 'bosses', len(bosses))


MONSTERS = []


def write_dungeon_directory(dungeons):
    global MONSTERS
    lines = ['# 던전 · 사냥터 디렉터리', '',
             '> 입장 조건 · 위치 · 층수 · 특징은 거상 공식 홈페이지 「거상정보 > 지역안내」(gersang.co.kr/info/area.gs, 2026-11-09 확인) 원문이다.',
             '> 공식 지역안내에 아직 실리지 않은 신규 던전은 입장 조건을 `미기재`로 두었다(추정하지 않았다).',
             '> 몬스터 수 · HP/EXP 범위는 수록 데이터 기준 집계다.',
             '> gogolap 던전 섹션이 여러 지역을 묶어 놓은 경우(예: `염마굴(火)·흑룡담(水)·신선곡(風雷)`)에는 같은 몬스터가 여러 지역에 중복 집계될 수 있다.', '']
    # 국가별
    nations = ['조선', '일본', '대만', '중국', '인도', '몽골']
    for nat in nations:
        rows = [d for d in dungeons if d['nation'] == nat]
        if not rows:
            continue
        lines.append(f'## {nat}')
        lines.append('')
        lines.append('| 던전 | 위치 | 입장 조건 | 규모(층) | 서식 몬스터(공식 안내) | 특징 |')
        lines.append('|---|---|---|---|---|---|')
        for d in rows:
            desc = (d['official_monsters'] or '').replace(' 몬스터가 층별로 출몰함', '').replace(' 몬스터가 출몰함', '')
            lines.append('| {} | {} | {} | {} | {} | {} |'.format(
                d['name'], d['location'] or '—', d['entry'] or '—',
                d['floors'] or '—', desc or '—', d['feature'] or '—'))
        lines.append('')
    # 미기재 던전
    rest = [d for d in dungeons if not d['nation']]
    if rest:
        lines.append('## 공식 지역안내 미수록(신규 · 특수 콘텐츠)')
        lines.append('')
        lines.append('| 던전 | 수록 몬스터 | HP 범위 | EXP 범위 | 속성 |')
        lines.append('|---|---|---|---|---|')
        for d in sorted(rest, key=lambda x: -(x['hp_max'] or 0)):
            lines.append('| {} | {}종 | {} ~ {} | {} ~ {} | {} |'.format(
                d['name'], d['monster_count'], fmt(d['hp_min']), fmt(d['hp_max']),
                fmt(d['exp_min']), fmt(d['exp_max']),
                '/'.join(d['elements']) or '—'))
        lines.append('')
    lines.append('## 수록 몬스터 수 요약')
    lines.append('')
    lines.append('| 던전 | 몬스터 | HP 최소 | HP 최대 | EXP 최대 | 최고 EXP/HP |')
    lines.append('|---|---|---|---|---|---|')
    byid = {m['id']: m for m in MONSTERS}
    for d in sorted(dungeons, key=lambda x: -(x['hp_max'] or 0)):
        best, ratio = '—', 0
        for mid in d['monster_ids']:
            m = byid.get(mid)
            if m and m.get('hp') and m.get('exp'):
                r_ = m['exp'] / m['hp']
                if r_ > ratio:
                    best, ratio = f"{m['name']} ({r_:.3f})", r_
        lines.append('| {} | {} | {} | {} | {} | {} |'.format(
            d['name'], d['monster_count'], fmt(d['hp_min']), fmt(d['hp_max']), fmt(d['exp_max']), best))
    lines.append('')
    path = os.path.join(ROOT, 'dungeons', 'dungeon_directory.md')
    os.makedirs(os.path.dirname(path), exist_ok=True)
    open(path, 'w', encoding='utf-8').write('\n'.join(lines) + '\n')
    print('wrote', path)


def anchor(name):
    s = name.lower()
    s = re.sub(r'[\.\(\)\[\]\,\?\!\`\*\_\<\>]', '', s)
    s = s.replace(' ', '-')
    return s


KEY_GROUPS = [
 ('유명계 · 차원 관련', ['유명계석', '유명계 보물지도']),
 ('흉수 · 신수 소재', ['흉수의혼', '환수의혼', '신수의근원', '고대신수의정수']),
 ('속성 · 정기 소재', ['정기구슬', '속성석', '속성의정령석', '정령석', '결정체']),
 ('심연 · 잿더미', ['심연']),
 ('명왕 · 사천왕 제작', ['명왕', '사천왕', '갑옷', '팔보호구']),
 ('제조서 · 주술비법', ['제조서', '주술비법', '주술 비법']),
 ('봉인 관련', ['봉인']),
 ('상재 판매 대상(일반 장비·재료)', []),
]


def write_items(monsters):
    items = defaultdict(set)
    for m in monsters:
        for it in m['drops']:
            items[it].add((m['name'], m['dungeon']))
    lines = ['# 주요 드랍 아이템 역색인', '',
             '> 각 몬스터의 드랍 목록을 아이템 기준으로 뒤집은 색인이다. 드랍 확률은 거상이 공식적으로 공개하지 않으므로 수록하지 않았다.',
             '> 전체 1,600여 종 아이템의 기계 판독용 색인은 [`data/drops_index.json`](../data/drops_index.json) 에 있다.', '']
    for title, kws in KEY_GROUPS:
        if not kws:
            continue
        hits = sorted({i for i in items if any(k in i for k in kws)})
        if not hits:
            continue
        lines.append(f'## {title}')
        lines.append('')
        lines.append('| 아이템 | 드랍 몬스터 (출몰지) |')
        lines.append('|---|---|')
        for it in hits:
            ms = sorted(items[it], key=lambda x: (x[1], x[0]))
            cell = ', '.join(f'{n}({d})' for n, d in ms)
            lines.append(f'| {it} | {cell} |')
        lines.append('')
    # 전체 역색인
    lines.append('## 전체 아이템 역색인')
    lines.append('')
    lines.append('| 아이템 | 드랍 몬스터(출몰지) |')
    lines.append('|---|---|')
    for it in sorted(items):
        ms = sorted(items[it], key=lambda x: (x[1], x[0]))
        cell = ', '.join(f'{n}({d})' for n, d in ms)
        lines.append(f'| {it} | {cell} |')
    lines.append('')
    path = os.path.join(ROOT, 'items', 'key_drops.md')
    os.makedirs(os.path.dirname(path), exist_ok=True)
    open(path, 'w', encoding='utf-8').write('\n'.join(lines) + '\n')
    print('wrote', path, 'items', len(items))
    # json 색인
    j = {it: [{'name': n, 'dungeon': d} for n, d in sorted(items[it], key=lambda x: (x[1], x[0]))] for it in sorted(items)}
    json.dump(j, open(os.path.join(DATA, 'drops_index.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)


def write_csv(monsters):
    cols = ['id', 'name', 'dungeon', 'element', 'grade', 'category', 'hp', 'hit_res', 'mag_res',
            'elem_value', 'exp', '힘', '민첩', '생명력', '지력', 'drops']
    with open(os.path.join(DATA, 'monsters.csv'), 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.writer(f)
        w.writerow(cols)
        for m in monsters:
            s = m.get('stats') or {}
            w.writerow([m['id'], m['name'], m['dungeon'], m.get('element') or '', m.get('grade') or '',
                        m.get('category') or '', m.get('hp') or '', m.get('hit_res') or '',
                        m.get('mag_res') or '', m.get('elem_value') or '', m.get('exp') or '',
                        s.get('힘') or '', s.get('민첩') or '', s.get('생명력') or '', s.get('지력') or '',
                        '|'.join(m['drops'])])
    print('wrote csv')


def main():
    monsters, areas = load()
    MONSTERS[:] = monsters
    dungeons = build_dungeons(monsters, areas)
    json.dump(dungeons, open(os.path.join(DATA, 'dungeons.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
    write_monster_docs(monsters, dungeons)
    write_boss_doc(monsters)
    write_index_doc(monsters)
    write_dungeon_directory(dungeons)
    write_items(monsters)
    write_csv(monsters)
    print('total monsters', len(monsters), 'dungeons', len(dungeons))


if __name__ == '__main__':
    main()
