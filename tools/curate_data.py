#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""원시 수집본(gogolap 카드 + kakao.gg 몬스터 도감)을 하나의 레코드로 정리한다.

정리 규칙
1. '하위 던전 주요 몬스터' 섹션은 하위 던전 몬스터를 다시 모아 놓은 요약본이므로 제외하고,
   거기에만 있던 개체는 실제 출몰지로 옮긴다.
2. 카카오 도감에만 있는 개체의 출몰지 문자열을 gogolap 던전 라벨로 정규화한다(공백/괄호 무시 부분일치).
3. 완전히 같은 (이름, 던전, 스탯) 중복 카드는 variants 로 합친다.
"""
import json, os, re, unicodedata
from collections import OrderedDict, defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, 'data')


def norm(n):
    n = unicodedata.normalize('NFKC', n or '')
    n = re.sub(r'[\(（\[][^\)）\]]*[\)）\]]', '', n)
    return re.sub(r'\s+', '', n).lower()


AREA_ALIAS = {
    '초보자던전': '초보자 군영',
    '중국 북부': '중국 필드',
    '악몽의 제단,악몽의 방': '악몽의틈(火雷)·악몽의근원(水風)',
    '광려산 정상(환상의계곡 새벽)': '환상계곡 석양(火雷)·새벽(水風)',
    '광려산 정상(환상의계곡 석양)': '환상계곡 석양(火雷)·새벽(水風)',
    '수미산, 광목천왕 지역.': '수미산',
    '수미산, 다문천왕 지역.': '수미산',
    '검은상단병영_비밀의장소': '검은상단주둔지',
    '계림 내성': '계림·오로치의둥지·빙궁·야수림',
    '얼음성 3층, 아마쿠사 타루와 출현': '얼음성',
    '신수청룡,증장천왕과 출현.': '수미산',
}


def resolve(dungeon, labels):
    """카카오 출몰지 문자열을 gogolap 던전 라벨로 맞춘다."""
    if dungeon in AREA_ALIAS:
        return AREA_ALIAS[dungeon]
    if dungeon in labels:
        return dungeon
    nd = norm(dungeon)
    best = None
    for l in labels:
        nl = norm(l)
        if nd and (nd in nl or nl in nd):
            if best is None or len(nl) < len(norm(best)):
                best = l
    # 던전 라벨이 '·' 로 묶인 복합 라벨인 경우 조각으로도 확인
    if best is None:
        for l in labels:
            for part in l.split('·'):
                if nd and (nd in norm(part) or norm(part) in nd):
                    best = l
                    break
            if best:
                break
    return best or dungeon


def main():
    raw = json.load(open(os.path.join(DATA, 'monsters.json'), encoding='utf-8'))
    labels = [r['dungeon'] for r in raw if r['hp'] is not None or 'gogolap' in r['sources']]
    seen = []
    for l in labels:
        if l not in seen:
            seen.append(l)
    out = []
    for r in raw:
        if r['dungeon'] == '하위 던전 주요 몬스터':
            if r['name'] in ('수상한 도깨비', '수상한 보부상'):
                r['dungeon'] = '검은상단주둔지'
            else:
                continue
        if r['kakao_url'] and r['hp'] is None:
            r['dungeon'] = resolve(r['dungeon'], seen)
        out.append(r)
    grouped = OrderedDict()
    for r in out:
        key = (r['name_key'], r['dungeon'], r['hp'], r['hit_res'], r['mag_res'],
               r['elem_value'], r['exp'])
        if key in grouped:
            g = grouped[key]
            g['variants'] = g.get('variants', 1) + 1
            for d in r['drops']:
                if d not in g['drops']:
                    g['drops'].append(d)
            for s in r['sources']:
                if s not in g['sources']:
                    g['sources'].append(s)
            continue
        r['variants'] = 1
        grouped[key] = r
    recs = list(grouped.values())
    for i, r in enumerate(recs):
        r['id'] = 'M%04d' % (i + 1)
    json.dump(recs, open(os.path.join(DATA, 'monsters.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
    print('records', len(recs), 'dungeons', len({r['dungeon'] for r in recs}))
    from collections import Counter
    print('with hp', sum(1 for r in recs if r['hp']), 'with grade', sum(1 for r in recs if r['grade']))
    print('with base stats', sum(1 for r in recs if (r['stats'] or {}).get('힘')))
    print('with drops', sum(1 for r in recs if r['drops']))


if __name__ == '__main__':
    main()
