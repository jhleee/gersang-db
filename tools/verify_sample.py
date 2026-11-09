#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""수록 수치를 제3의 출처 표본과 대조한다.

data/verify_sample.tsv 는 본 저장소와 무관한 커뮤니티 표(지플릭스 '단풍석 드랍 몬스터', 2026-10-18 기준)에서
옮긴 HP·EXP·타격저항·마법저항이다. 이 값과 monsters.json 이 일치하는지 확인한다.
"""
import json, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
m = json.load(open(os.path.join(ROOT, 'data', 'monsters.json'), encoding='utf-8'))
rows = [l.rstrip('\n').split('\t') for l in open(os.path.join(ROOT, 'data', 'verify_sample.tsv'), encoding='utf-8')][1:]
ok = bad = miss = 0
for name, hp, exp, hr, mr, _src in rows:
    key = name.replace(' ', '')
    hits = [r for r in m if r['name_key'] == key]
    if not hits:
        print('MISSING', name); miss += 1; continue
    exp_ = (int(hp), int(exp), int(hr), int(mr))
    matched = [r for r in hits if (r['hp'], r['exp'], r['hit_res'], r['mag_res']) == exp_]
    if matched:
        ok += 1
    else:
        bad += 1
        for r in hits:
            print('DIFF', name, r['dungeon'], (r['hp'], r['exp'], r['hit_res'], r['mag_res']), 'expected', exp_)
print(f'sample={len(rows)} match={ok} diff={bad} missing={miss}')
sys.exit(0 if bad == 0 and miss == 0 else 1)
