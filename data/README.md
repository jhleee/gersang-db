# data/ 스키마

기계 조회용 데이터. 문서(`monsters/`, `dungeons/`, `items/`)는 전부 이 파일들에서 생성된다.

## monsters.json

몬스터 1개체(= 이름 + 출몰지 + 스펙)당 한 레코드. 배열.

| 필드 | 타입 | 설명 |
|---|---|---|
| `id` | string | `M0001` 형식 고유 id |
| `name` | string | 몬스터 이름 (게임 표기) |
| `name_key` | string | 괄호·공백 제거 소문자 정규화 키 (이름 매칭용) |
| `element` | string\|null | `불` `물` `바람` `뇌전` `땅` `null`(무속성) |
| `element_raw` | string\|null | 원문 표기 `火` `水` `風` `雷` `地` |
| `grade` | int\|null | 1~10 등급 |
| `category` | string | `""` / `보스` / `공중` / `공중 보스` |
| `dungeon` | string | 출몰 던전 라벨 (문서의 섹션 이름) |
| `area` | string\|null | 거상 공식 도감의 출몰지 표기 |
| `stats` | object | `힘` `민첩` `생명력` `지력` — 공식 도감 기초 스탯 |
| `hp` | int\|null | 인게임 HP |
| `hit_res` | int\|null | 타격저항 (%) |
| `mag_res` | int\|null | 마법저항 (%) |
| `elem_value` | int\|null | 속성값 (무속성 몬스터는 null) |
| `exp` | int\|null | 처치 경험치 |
| `drops` | string[] | 드랍 아이템 이름 (확률 없음) |
| `counter_element` | string\|null | 이 몬스터에게 유리한 공격 속성 (공식 도감 표기) |
| `variants` | int | 같은 이름·스펙으로 여러 마리 출현할 때의 수 |
| `sources` | string[] | `gogolap` / `kakao.gg` |
| `gogolap_id` | string\|null | gogolap 내부 카드 id |
| `kakao_url` | string\|null | 공식 도감 원문 링크 |

`null` 은 "확인된 자료 없음"이다. 0 이나 추정값으로 채우지 않았다.

## dungeons.json

| 필드 | 설명 |
|---|---|
| `name` | 던전/지역 이름 |
| `nation` | `조선` `일본` `대만` `중국` `인도` `몽골` (공식 지역안내 기준), 신규 콘텐츠는 null |
| `location` `entry` `floors` `feature` | 공식 지역안내 원문 (위치 / 입장 조건 / 규모 / 특징) |
| `official_monsters` | 공식 안내문의 서식 몬스터 설명 |
| `labels` | 이 지역으로 묶은 원본 던전 라벨 목록 |
| `monster_count` | 수록 몬스터 레코드 수 |
| `monster_ids` | `monsters.json` 의 id 배열 |
| `hp_min` `hp_max` `exp_min` `exp_max` | 집계 범위 |
| `elements` | 등장 속성 |

## drops_index.json

`{ "아이템 이름": [ {"name": 몬스터, "dungeon": 출몰지}, … ] }` 형태의 역색인.

## areas.tsv

공식 지역안내(https://www.gersang.co.kr/info/area.gs) 수집본. 탭 구분, 컬럼 순서:
`국가 · 던전명 · 위치 · 입장조건 · 규모 · 특징 · 서식몬스터설명`
