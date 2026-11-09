# 거상 몬스터 · 던전 DB (Gersang Agent Reference)

천하제일상 거상(The Great Merchant)의 **몬스터 · 출몰지 · 능력치 · 저항 · 속성값 · 경험치 · 드랍 아이템 · 던전 입장 조건**을
AI 에이전트가 그대로 읽고 계산에 쓸 수 있게 마크다운 위키 + 정형 JSON 으로 정리한 저장소다.

> 🎯 **거상 YOLO 객체탐지 (몬스터·드랍아이템)**: [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/jhleee/gersang-db/blob/main/notebooks/gersang_yolo_training.ipynb)  · [검수 리포트](docs/yolo_report.md)  
> 🌐 **웹 도감 & 육의전 시세 뷰어 (GitHub Pages)**: [https://jhleee.github.io/gersang-db/](https://jhleee.github.io/gersang-db/)  
> - 아이템 1,687종 및 드랍 몬스터 역색인 실시간 검색  
> - 비호 서버 포함 13개 전 서버 육의전 실시간 시세 및 딥링크  
> - 190렙 짭호선 뉴비 가성비 사냥터 가이드 & 저항 깎기(주박/허영) 데미지 계산기 내장  

- 수집 기준일: **2026-11-09** (본서버)
- 수록 규모: **몬스터 906레코드(이름 816종) / 던전·지역 75곳 / 드랍 아이템 1,687종**
  - 거상 공식 몬스터 도감에 등록된 **662종을 이름 기준 100% 포함**하고, 커뮤니티 도감에만 있는 신규 콘텐츠(샴발라·명왕·천옥 등)를 더했다.
- 원칙: **확인된 자료만 넣는다.** 출처에 없는 값은 `—` 로 두고 추정하지 않았다. (아래 [데이터 한계](#데이터-한계) 참고)

```
gersang-db/
├── README.md                     ← 이 문서 (개요 · 상성표 · 공식 요약 · 에이전트 사용법)
├── mechanics/
│   └── combat_and_resist.md      ← 저항→데미지 공식, 저깍, 속성값 공식, 상재 계산
├── monsters/
│   ├── 00_index.md               ← 전체 몬스터 가나다순 색인
│   ├── 01_starter_and_fields.md  ← 초보자 군영 · 조선/일본/중국/대만 필드
│   ├── 02_classic_dungeons.md    ← 대관령, 월기봉, 고수동굴, 무령왕릉, 해저동굴, 귀곡성, 이시즈치산, 대설산 …
│   ├── 03_famous_dungeons.md     ← 유명계, 천년호, 륭산, 소림사, 만리장성, 진시황릉, 챠우신전, 대둔산, 해적동굴 …
│   ├── 04_india_and_sacred.md    ← 인도 전역, 백호림, 청룡담, 개마장원
│   ├── 05_sumisan_and_shinsungok.md ← 수미산, 신선곡, 염마굴·흑룡담, 일천/월천귀문
│   ├── 06_endgame_dungeons.md    ← 광려산, 환상계곡, 악몽의틈, 별의방, 샴발라, 검은상단, 천옥, 명왕
│   ├── 07_bosses_and_mythic.md   ← 4대 신수 · 4대 흉수 · 사천왕 · 명왕 · 지역 보스 색인
│   └── 08_special.md             ← 소환·이벤트·특수 개체
├── dungeons/
│   └── dungeon_directory.md      ← 던전별 위치 · 입장 조건 · 층수 · 서식 몬스터 · HP/EXP 범위
├── items/
│   └── key_drops.md              ← 드랍 아이템 역색인 (아이템 → 몬스터·출몰지)
├── data/
│   ├── monsters.json             ← 전체 정형 데이터 (기계 조회용, 906 레코드)
│   ├── verify_sample.tsv         ← 수치 검증용 제3출처 표본 11건
│   ├── monsters.csv              ← 같은 내용의 CSV (엑셀/스프레드시트용)
│   ├── dungeons.json             ← 던전 메타데이터 + 소속 몬스터 id
│   ├── drops_index.json          ← 아이템 역색인 JSON
│   ├── areas.tsv                 ← 공식 지역안내 원문 수집본
│   └── README.md                 ← 데이터 스키마 설명
├── assets/                       ← YOLO 학습용 원본 에셋 (스프라이트·아이템·배경)
├── test_images/                  ← 실제 사냥 화면 13장 (학습에 쓰지 않은 검수용)
├── notebooks/
│   └── gersang_yolo_training.ipynb  ← Colab 원클릭 학습 노트북
├── models/
│   ├── gersang_yolov8n_synth_baseline.pt    ← 합성 데이터로 학습한 기준 가중치
│   └── gersang_yolov8n_synth_baseline.onnx  ← 같은 모델의 ONNX(fp32, 640) — 앱/실시간 추론용
├── docs/
│   └── yolo_report.md            ← 데이터셋 구축·실화면 검수 리포트
└── tools/
    ├── curate_data.py            ← 원시 수집본 정리(중복 병합·출몰지 정규화)
    ├── build_docs.py             ← JSON → 마크다운 문서/색인 생성기
    ├── verify_sample.py          ← 표본 대조 검증
    ├── collect_assets.py         ← 거상 스프라이트·아이템·네거티브 수집
    ├── make_backgrounds.py       ← 실제 사냥 화면 크롭 + 절차적 지형 텍스처
    ├── generate_yolo_dataset.py  ← 합성 YOLO 데이터셋 생성기(정답 라벨 100%)
    └── eval_real.py              ← 실제 사냥 화면 검수(템플릿 매칭 대조)
```

---

## 거상 YOLO 객체탐지 (몬스터·드랍아이템)

[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/jhleee/gersang-db/blob/main/notebooks/gersang_yolo_training.ipynb)

인게임 스프라이트와 실제 사냥 화면을 합성해 **정답 라벨이 100% 맞는 학습 데이터**를 만들고,
YOLOv8로 몬스터·드랍아이템을 탐지하는 파이프라인이다. 자세한 결과와 한계는 [docs/yolo_report.md](docs/yolo_report.md).

| 클래스 ID | 이름 | 등장 | 스프라이트 |
|---|---|---|---|
| 0 | `imugi` 이무기 | 유명계 3층, 대관령 등 | 이무기, 사악한이무기, 연못이무기, 늪지이무기, 뿌리이무기, 이무기氷 (6종) |
| 1 | `yeomra` 염라대왕 | 유명계 3층 염라존 | 염라대왕 |
| 2 | `docheol` 어린도철 | 대둔산 은신처 | 어린도철, 도철, 흉포한도철, 잠식된도철, 태초의도철, 타락한도철 (6종) |
| 3 | `nue` 누에 | 일본 환수, 귀곡성 등 | 누에, 조련된누에, 얼음누에 (2종) |
| 4 | `sammun` 중독된삼문 | 검은상단 주둔지 | 중독된삼문, 삼문, 진보의삼문, 각성한삼문 (4종) |
| 5 | `icecrab` 얼음게 | 얼음성 | 얼음게, 용암게, 육지거대게 (3종) |
| 6 | `tuttleman` 거북궁사 | 얼음성, 계곡 등 | 거북궁사, 육지거북, 연못거북 (3종) |
| 7 | `item_drop` 드랍아이템 | 전 던전 | 유명계석·흉수/환수의혼·속성석·정수·상자·비늘 등 (49종) |

### Colab으로 거상 YOLO 모델 학습하기

1. 위 **Open in Colab** 배지를 누른다.
2. 셀 1( GPU 확인 ) → 셀 7(가중치·ONNX 다운로드)까지 **▶ 를 차례로** 누른다.
   - 셀 3에서 저장소 에셋으로 합성 데이터 1,000장을 자동 생성한다(CPU 2~3분).
   - 무료 T4 기준 학습(50 epoch, 640px)은 10~15분이다.
3. 마지막 셀에서 `best.pt`(재학습용)와 `best.onnx`(실시간 추론용)를 내려받는다.

### 로컬에서 직접 돌리기

```bash
python tools/collect_assets.py --out assets --negatives 150      # 스프라이트 수집
python tools/make_backgrounds.py --out assets/backgrounds         # 배경 패치
python tools/generate_yolo_dataset.py --out datasets/gersang_yolo --images 1000
yolo detect train data=datasets/gersang_yolo/data.yaml model=yolov8n.pt epochs=50 imgsz=640 batch=16
yolo detect predict model=runs/detect/train/weights/best.pt source=test_images conf=0.25 save=True
```

### 현재 성능 (요약)

| 검증 대상 | 결과 |
|---|---|
| 합성 검증셋 200장 (CPU 기준 모델) | mAP50 **0.887** / mAP50-95 **0.745** |
| 실제 사냥 화면 – 이무기 흩어진 무리 | 11마리 중 **9마리 검출**(신뢰도 0.7~0.95) |
| 실제 사냥 화면 – 이무기 밀집 | 15마리 중 10마리(겹침·이펙트 구간에서 누락) |
| 염라대왕 | 확보한 염라존 프레임이 전부 스킬 이펙트/사망 장면이라 **판정 보류** |

> 학습 데이터는 합성이라 **실사냥 화면을 라벨링해 val에 섞는 것**이 가장 효과가 큰 다음 단계다.
>
> 동봉한 `models/gersang_yolov8n_synth_baseline.pt` 로 바로 추론해 볼 수 있다:
> `yolo detect predict model=models/gersang_yolov8n_synth_baseline.pt source=test_images conf=0.25 save=True`

---

## 속성 상성

거상의 속성은 **불(火) · 물(水) · 바람(風) · 뇌전(雷) · 땅(地) · 무속성** 여섯 가지다.
사이클은 **불 → 바람 → 뇌전 → 물 → 불** 이며, 화살표 앞 속성이 뒤 속성에게 유리하다.

| 공격 속성 | 유리 (데미지 증가) | 불리 (데미지 감소) |
|---|---|---|
| 불(火) | 바람(風) | 물(水) |
| 바람(風) | 뇌전(雷) | 불(火) |
| 뇌전(雷) | 물(水) | 바람(風) |
| 물(水) | 불(火) | 뇌전(雷) |
| 땅(地) | 모든 속성에 +속성값% | 상성 없음 (땅을 칠 때는 +30% 고정) |

**데미지 규칙 요약**

- 유리한 속성으로 공격하면 **공격자 속성값%** 만큼 증가한다.
- 불리한 속성으로 공격하면 **상대 속성값%** 만큼 감소한다.
- 같은/무관 속성끼리는 공격자 속성값이 상대보다 **낮을 때만** `(상대−공격자)×1.5%` 만큼 감소한다.
- 한쪽이라도 무속성(속성 없음)이면 속성 데미지 자체가 적용되지 않는다.
- 감소 상한 90%, 증가 상한 없음(2023 패치 기준).

이 저장소의 몬스터 속성 분포: 불 91 · 바람 91 · 물 82 · 뇌전 34 · 땅 2 · 무속성 606.

**저항 → 데미지**는 별개 공식이다.

```
피해 감소율(%) = 0.16 × 저항 + 57        (상한 98.6% = 저항 260%)
```

- 저항 0 몬스터에게도 표기 데미지의 43%만 들어간다.
- 저항 260% 몬스터는 1.4%만 들어가며, 주박 51%를 걸면(→209%) 9.56%가 들어가 **약 6.8배**가 된다.
- 자세한 식과 저깍·중첩·상재 계산은 [`mechanics/combat_and_resist.md`](mechanics/combat_and_resist.md).

---

## 에이전트 사용 가이드

### 어떤 질문에 어느 파일을 보는가

| 질문 유형 | 먼저 볼 것 |
|---|---|
| "○○ 몬스터 스펙 알려줘" | `monsters/00_index.md` 로 위치 확인 → 해당 던전 문서 블록 |
| "이 던전 뭐가 나와?" | `dungeons/dungeon_directory.md` → 해당 던전 문서 |
| "△△템 어디서 떨어져?" | `items/key_drops.md` (또는 `data/drops_index.json`) |
| "○○ 잡으려면 저항 얼마?" | `data/monsters.json` 의 `hit_res`/`mag_res` → `mechanics/combat_and_resist.md` 식 |
| "무슨 속성으로 잡아?" | 몬스터 `element` → 위 상성표 |
| "어디서 사냥해야 빨리 크나" | `dungeons/dungeon_directory.md` 의 HP·EXP 범위와 `최고 EXP/HP` 열 |
| "던전 입장 조건은?" | `dungeons/dungeon_directory.md` (공식 지역안내 원문) |
| "보스만 모아줘" | `monsters/07_bosses_and_mythic.md` |

### 데이터 스키마 (`data/monsters.json`)

```jsonc
{
  "id": "M0254",
  "name": "구영",
  "name_key": "구영",              // 괄호 제거·공백 제거 정규화 키
  "element": "불",                  // 불/물/바람/뇌전/땅/null(무속성)
  "element_raw": "火",              // 원문 표기
  "grade": 10,                      // 1~10 등급, null이면 미상
  "category": "공중 보스",          // "", "보스", "공중", "공중 보스"
  "dungeon": "염마굴(火)·흑룡담(水)·신선곡(風雷)",
  "area": "염마굴",                 // 거상 공식 도감 표기 출몰지
  "stats": {"힘": 25000, "민첩": 10000, "생명력": 225000, "지력": 5000},
  "hp": 900000,                     // 인게임 HP (커뮤니티 도감 수치)
  "hit_res": 295, "mag_res": 295,   // 타격저항 / 마법저항 (%)
  "elem_value": 20,                 // 속성값 (무속성 몬스터는 null)
  "exp": 320000,
  "drops": ["정기의구슬조각(火)", "불의결정체", "..."],
  "counter_element": "물",          // 이 몬스터에게 유리한 공격 속성(공식 도감 표기)
  "variants": 1,                    // 같은 스펙으로 여러 마리 출현하는 경우
  "sources": ["gogolap", "kakao.gg"],
  "gogolap_id": "C_00061250",
  "kakao_url": "https://www.kakao.gg/games/gersang/monsters/..."
}
```

### 조회 예시

```bash
# 이름으로 찾기 (jq)
jq -r '.[] | select(.name_key=="구영") | [.name,.dungeon,.hp,.hit_res,.elem_value,.exp] | @tsv' data/monsters.json

# 특정 아이템을 주는 몬스터
jq -r '."정기의구슬조각(火)"[] | [.name,.dungeon] | @tsv' data/drops_index.json

# 저항 300 이상 몬스터
jq -r '.[] | select((.hit_res//0) >= 300) | [.name,.dungeon,.hit_res,.mag_res] | @tsv' data/monsters.json

# 특정 던전 몬스터를 HP 순으로
jq -r '.[] | select(.dungeon|test("수미산")) | [.name,.hp,.exp] | @tsv' data/monsters.json | sort -k2 -nr
```

```python
import json
m = json.load(open('data/monsters.json', encoding='utf-8'))
# 데미지 감소율과 실효 HP 계산
for r in m:
    if r['hit_res']:
        dmg_taken = 100 - (0.16 * r['hit_res'] + 57)   # %
        eff_hp = r['hp'] / (dmg_taken / 100)           # 저항 무시하고 때릴 때 필요한 원데미지
```

### 문서 블록 형식

각 몬스터는 던전 문서 안에서 다음 형태로 들어 있다. 같은 이름이 한 던전에 여럿이면 제목 뒤에 속성/HP를 붙여 구분한다.

```markdown
### 구영
- 속성 火(불) · 10등급 · 공중 보스
- HP 900,000 · 타격저항 295% · 마법저항 295% · 속성값 20 · EXP 320,000
- 기본 스탯: 힘 25,000 · 민첩 10,000 · 생명력 225,000 · 지력 5,000
- 드랍: 정기의구슬조각(火), 불의결정체, 찢어진 진법서, 축융부, 불의정령석
```

---

## 데이터 출처

| 필드 | 출처 | 성격 |
|---|---|---|
| 이름 · 등급 · 속성 · 출몰지 · 힘/민첩/생명력/지력 · 드랍 목록 | 거상 공식 홈페이지(gersang.co.kr) 「거상정보 > 몬스터」를 옮긴 [kakao.gg 거상 몬스터·드랍 도감](https://www.kakao.gg/games/gersang/monsters) | **공식 데이터** (게임사 제공 수치) |
| 던전 위치 · 입장 조건 · 층수 · 특징 · 서식 몬스터 | [거상 공식 홈페이지 지역안내](https://www.gersang.co.kr/info/area.gs) 원문 | **공식 안내문** |
| HP · 타격저항 · 마법저항 · 속성값 · EXP · 드랍 아이템 | [gogolap 거상 몬스터 도감](https://gogolap.com/gersang/db/monster) | 커뮤니티 도감 (인게임 정보 취합) |
| 저항 공식 · 속성값 공식 · 저깍 공식 · 상재 | 커뮤니티 정리 글(티스토리·네이버 블로그·DC 갤러리) 다수 교차 확인 | 커뮤니티 검증값 (개별 각주는 `mechanics/` 문서에) |

두 몬스터 출처는 이름 기준으로 병합했다. 674개 레코드는 양쪽에 모두 있고, 191개는 gogolap 단독, 41개는 공식 도감 단독이다.

### 데이터 한계

정확성을 위해 **비워 둔** 항목들이다. 필요하면 다른 자료로 채워야 한다.

- **공격력 · 방어력**: 두 출처의 몬스터 정보에 항목이 없다. (거상에서 방어력은 데미지 감소와 무관하다.)
- **드랍 확률**: 거상이 공식적으로 공개하지 않는다. 아이템 목록만 수록했다.
- **몬스터 사용 스킬**: 몬스터 도감에 없는 항목이라 넣지 않았다. (공략 글에 일부만 산발적으로 존재)
- **신규 콘텐츠 입장 조건**: 샴발라, 천옥 신장, 검은상단 암시장, 별의 방, 광려산 지하신전 등 공식 지역안내에 아직 실리지 않은 던전은 `미기재`다.
- 수치는 패치로 바뀐다. 본 저장소는 2026-11-09 본서버 기준이다.

## 검증

수치가 실제로 맞는지 확인하기 위해, 본 저장소와 무관한 제3의 커뮤니티 표와 표본 대조를 돌려 두었다.

```bash
python3 tools/verify_sample.py
# sample=11 match=11 diff=0 missing=0
```

- 표본: 지플릭스 「단풍석 드랍 몬스터 완전 정리」(2026-10-18 본서버 기준)의 11개 몬스터
- 대조 항목: HP · EXP · 타격저항 · 마법저항 → **11/11 일치**
- 표본 데이터: [`data/verify_sample.tsv`](data/verify_sample.tsv)

공식 도감(등급·속성·기초 스탯·드랍)과 gogolap(HP·저항·EXP)이 이름으로 연결되는 비율도 확인했다.
906개 레코드 중 674개가 두 출처에 모두 존재하고, 나머지는 한쪽에만 있는 신규·특수 개체다.

## 갱신 방법

```bash
python3 tools/curate_data.py   # 원시 수집본 정리 (data/monsters.json)
python3 tools/build_docs.py    # 마크다운 · 색인 · CSV 재생성
```

원시 수집본은 위 출처 페이지에서 받아 `data/monsters.json`(레코드 배열)과 `data/areas.tsv`(지역안내) 형태로 맞춰 두면 된다.

## 이용에 관하여

- 게임 데이터의 권리는 ㈜에이케이 인터렉티브 / 거상 운영진에게 있다. 이 저장소는 비공식 팬 자료이며 게임사와 무관하다.
- 수집 스크립트는 공개 페이지를 읽기만 하며, 게임 클라이언트를 열거나 인증을 우회하지 않는다.
- 오류를 발견하면 수정 PR 을 환영한다. 출처를 함께 적어 주면 검증이 빠르다.
