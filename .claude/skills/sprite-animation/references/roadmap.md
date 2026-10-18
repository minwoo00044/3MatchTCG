# sprite-animation 고도화 로드맵 (3·2·1 완료, 2026-10-16 갱신)

사용자가 꼽은 부족한 기능 세 가지와, 세션에서 합의 전 단계로 제안한 접근이다.
**제안 순서: 3 → 2 → 1.** 시작 전에 아래 "정할 것"을 사용자에게 먼저 묻는다.

## 현재 상태
- main `77c5f5b`에 병합됨(브랜치 `feature/archer-idle-animation`, 로컬은 아직 이 브랜치).
- Archer 6개 액션: Idle_v4(기준, 키 541.5) / Hit_v4 / Skill1_v1 / Skill2_v2 / Skill3_v3 / Dead_v3. 전부 화살통·벨트 포함.
- 재생성 기록: `SpriteRegen/`(git 무시). Hit은 try1~10, 합격은 try9(→v4).
- 커밋 안 한 무관 파일: testscene.unity 수정, New Scene, TextMesh Pro, `_Prefab/test.prefab`(Idle_v4·Archer.controller로 바꿔 둠), `_AnimCon/tetsct.controller`, `.agents/`.

## 1. 진행 (2026-10-14)
- 사용자 지시: v1 생성 첫 단계 = HD 원화 → 데포르메. 그 전에 Archer 기반 체형 마네킹. 이후 단계는 사용자가 따로 지시한다.
- 결정: 마네킹 민머리, A포즈, 턴어라운드 4방향(앞·3/4·옆·뒤), 체형 힌트(normal/young/tall)로 허용 폭 조절.
- 완료: 마네킹(assets/mannequin/, 사용자 확정), deform.py(generate/verify/accept), SKILL.md D 갈래. codex 호출은 codex_image.py로 통합.
- Knight로 시험 완료(9차 확정 = hint tall, Assets/_/Spirte/Knight/design/). 기록은 SKILL.md D 끝. young 힌트는 아직 실물 시험 없음.
- 다음 단계(턴어라운드 → 시트)는 사용자가 지시한다. 시트 단계에서 Archer와 같은 자세로 신체 비율을 다시 비교하기로 함(발 크기 −15% 포함).
- 설정 키: Archer 160cm, Knight 170cm(×1.0625). character.json/design json의 height_cm. 시트 스케일은 지금 캐릭터마다 기준 키를 따로 맞추므로, 시트 단계에서 height_cm 비율과 '머리카락 제외 키'(두개골 꼭대기 기준)로 스케일을 정하도록 파이프라인을 고쳐야 한다. Knight 키 큰 비율 버전(hint tall)도 생성함.

## 2. 결과 (2026-10-14 완료)
- 엔진: RIFE v4.25 (사용자 선택, OpenCV 대신). `scripts/rife/` + 가중치 `SpriteRegen/models/rife425/` 자동 다운로드·해시 확인. CPU 장당 약 1초.
- 비루프는 22장(원본 보존, 사용자 선택), 루프 24장. fps ×3.
- 처음엔 잔상 큰 구간(Skill2 2→3, Dead 2→3)을 끊었으나 플레이에서 끊김이 눈에 띔(사용자). → 구간마다 흐름 해상도 1/0.5/0.25 중 번짐 최소를 고르고, 지표를 '워프 결과 차이'에서 '결과물 반투명 번짐'으로 교체. 두 구간 모두 깨끗해져 끊는 구간 0.
- 적용: Idle_v7 / Hit_v7 / Skill1_v4 / Skill2_v5 / Skill3_v6 / Dead_v5. 기준 Idle_v7(키 541.5 그대로).
- 남은 것: 아틀라스 무압축 장당 약 18MB → 압축 검토는 별도(사용자 "일단 진행, 압축은 따로"). 다음은 1(v1 생성, 동작 설명은 사용자가 준다).

## 3. 결과 (2026-10-14 완료)
- 파이프라인 `align_x`에 mid / left_foot / right_foot / both_feet 추가, character.json `align_x`로 액션별 지정, 매니페스트 `footSlide`.
- 측정: 이동만으로는 두 발을 함께 못 고정한다(한 발 고정 시 다른 발 미끄러짐 2배). both_feet 워프로 Idle 3.8→1.0, Hit 10→2, Skill2 13→3px.
- Archer 최종: Idle·Hit·Skill2 = both_feet(Hit은 측정 후 뒷발→두 발로 변경), Skill1 = right_foot(뒷발 69px 빠짐 = 의도), Skill3 = mid, Dead = anchor.
- 적용: Idle_v5 / Hit_v5 / Skill1_v2 / Skill2_v3 / Skill3_v4 (그림 동일, 정렬만). 기준 시트도 Idle_v5로(키 541.5 그대로).
- `sheet_check.py jitter`: 상체 튐 보고. Idle 머리 세로 ±10px(키 2%) 불규칙 — 사용자 판단으로 보정 안 함. 큰 동작 액션은 8프레임이라 의도한 움직임도 걸려 지표로 못 쓴다.
- 남은 것: 다음은 2(프레임 증강 24).

## 3. 프레임 간 위치 보간 + 움직이면 안 되는 부위 고정 (먼저)
- 문제: 지금은 발 기준 정렬뿐이라 AI가 프레임마다 다르게 그린 상체·머리 위치 떨림이 남는다.
- 접근(생성 없이 픽셀 처리):
  1. 부위별(머리·몸통·발) 중심 궤적을 프레임마다 측정 → 튀는 프레임 검출. 검증 지표로도 쓴다.
  2. 튀는 프레임을 부드러운 궤적에 맞춰 위치 보정.
  3. 액션별 "고정 부위"(예: Idle의 발·부츠)는 기준 프레임의 그 부위를 모든 프레임에 같은 위치로.
- 위험: 부위 경계 이음새. 고정 부위를 액션별로 정해야 한다.

## 2. 프레임 증강 (8 → 12·16)
- (a) Codex 사이 프레임 생성: 편차 때문에 사이 프레임만 체형이 튀어 깜빡일 위험.
- (b) 픽셀 보간(모핑·광학 흐름): Idle처럼 작은 움직임엔 자연스럽고 큰 동작엔 잔상.
- (c) 프레임별 재생 시간 조정: 비용 거의 없음. 클립 생성(SpriteAnimationPipeline.WriteClip)만 고치면 된다.
- 제안: (b)+(c) 기본, (a)는 큰 동작에만.

## 1. v1 생성 (원본 시트 없이)
- 지금 `codex_generate.py`는 원본이 필수.
- 접근: 기준 시트 + 프레임별 동작 설명으로 생성하는 모드. Hit 재생성에서 프레임별 동작(충격→젖힘→복귀)을 구체적으로 적자 의도대로 나왔다(try9). 기준 시트에 체형·소품이 다 있으면 디자인도 맞는다.
- 판정: 원본이 없어 모션 보존 지표를 못 쓴다 → 프레임 간 변화량 하한(정지 화면 아님) + 동작 설명 대비 이미지 확인.

## 정한 것 (사용자 확인 2026-10-14)
- 순서: 3 → 2 → 1.
- 고정 부위(Archer): Idle·Skill2 = 두 발, Hit = 뒷발(화면 왼쪽, 측정 후 두 발로 변경), Skill1 = 앞발(화면 오른쪽), Skill3 = 두 발의 중점, Dead = 없음(궤적 평활만). 활 든 손은 고정하지 않는다(동작의 핵심이라).
- 고정 방식: 픽셀 이식이 아니라 프레임 전체 이동의 기준점으로 쓴다(이음새 회피). 상체만 튀는 프레임은 검출·보고만 하고 고칠지는 사례를 보고 정한다.
- 프레임 증강: 전 액션 24프레임(8장 사이에 2장씩). 잔상이 심한 구간은 미리보기로 보고하고, 그 구간만 Codex 사이 프레임이나 재생 시간 조정으로 대체할지 묻는다.
- v1 동작 설명: 사용자가 직접 준다.

## 이번 작업에서 이미 해결된 것 (다시 하지 않는다)
- 다리를 편 키 기준 스케일, seam 분할, 색 유지 판정, 무압축 임포트, 필수 디자인 요소(character.json design.required), 편집 방식 재생성(regeneration.md 6절), 사용량 85% 게이트, dry-run 번호 미사용, 동시 실행 번호 충돌 방지.

## Archer 부츠 축소 재적용 (2026-10-14)
- 기준: design/Archer_apose.png(부츠를 Knight 9차 신발 크기로 축소). 6종 편집 → Idle_v8, Hit_v8, Skill1_v5, Skill2_v7, Skill3_v7, Dead_v6. 기준 시트 Idle_v8.
- Skill2_v6은 병렬 생성 중 Skill1 결과가 뒤바뀌어 들어간 잘못된 시트(prev/에 있음). v7이 원래의 위로 쏘는 동작. 원인·대책은 regeneration.md 7절.
- 남은 확인: 플레이 확인. 감사에서 Dead 머리 −11.8%·부츠 −17.9%, Skill3 부츠 −15.1%(Idle_v8 대비). Skill2 v7 3번 프레임 활 위끝 몇 px 잘림.
- 마네킹 v3 = Knight 9차 비율(사용자 확정). Archer는 자기 비율 유지(사용자 지시).

## Knight Idle v1 (2026-10-14) — v1 생성 첫 실행
- 동작: Archer Idle 모션을 타이밍 참고로 붙여 생성(Knight_Idle try1) → 머리가 15% 커져서 비율만 편집(try2, 턱 높이 23.8% = 턴어라운드 23.6%).
- 게임 내 키: sheet_check.py set-height (정수리~발바닥, 머리카락 제외, height_cm 비율). Knight ref_height 517.5. skull_over_L: Archer 0.312, Knight 0.304.
- 남은 것: Knight Hit/Skill/Dead, 녹화 도구 재녹화.
- Knight Idle v1 떨림(사용자 지적): 발 검출이 바닥까지 내려온 망토 끝을 왼발로 잡아 프레임마다 36px 튐 → both_feet 워프가 다리를 비틀고 정렬이 흔들림. foot_centers를 '가장 넓은 두 덩어리'로 고침(Archer 적용분 영향 없음). v2: 머리 흔들림 7.5→0.7px.
- '유휴 같지 않음': 원본 움직임이 작음(정수리 위아래 1.0% vs Archer 3.0%, 좌우 0.1% vs 0.8%). 움직임 키우는 편집(try3) 진행.
- 교훈: 새 캐릭터 시트는 처리 전후 jitter를 비교한다(원본은 안정적인데 처리본만 튀면 정렬 문제). 생성 직후 움직임 양도 Archer 같은 기준 액션과 비교한다.
- 남은 몸 전체 떨림(사용자 지적): 원본 8장의 상체 높이가 불규칙(0,+5,+4,+6,0,…)해 보간까지 따라감 + 보간 셀만 20% 흐려 3장 주기 선명도 맥동.
  → process_sprite_sheet.py --stabilize(상체 위치를 루프는 한 주기 사인으로 맞추고 허리 위만 워프) + match_sharpness(보간 셀 언샤프, 항상 적용).
  Knight_Idle_v4: 상체 튐 y 0.88→0.62(Archer 0.58), x 0.38→0.17, 선명도 비 0.80→0.97. 대가: 원본 셀이 워프 재표본화로 약간 흐려짐(선명도 14.9→11.7).
- Knight Idle v5(움직임 키운 AI 재생성)는 '더 심해짐'(사용자). 원인(연속 프레임 직접 확인): AI가 프레임마다 얼굴(눈·눈썹·시선)을 다시 그림 + 고개를 떨구는 조는 동작 + 보간이 그걸 녹이듯 이음. 몸 위치 지표(coherence)로는 안 잡혔다.
  → procedural_idle.py: AI 한 장을 몸으로 고정, 숨쉬기는 코드(상체 한 덩어리, 엉덩이~발 1→0), 깜빡임은 같은 몸 프레임의 눈만 합성. Knight_Idle_v6(24장, 보간 없음).
- v6(상체 통째 11px 오르내림) → '스프링 인형'. v7(다리 고정, 가슴·어깨 4px, 머리 2프레임 지연) → '그 폭이면 무릎이 움직여야, 아니면 호흡 수준으로'. 
  v9: 폭 0.4%(약 2px) + 줄마다 정수 px 이동(소수 이동은 쌍선형으로 흐려져 선명도가 13% 맥동 → 1.6%). procedural_idle.py 기본값으로 반영할지 사용자 확인 후.
- Knight_Idle_v10(knee 모드) 사용자 확정 '딱 좋다'. procedural_idle.py 기본값으로, SKILL.md E 갈래로 반영. 다음: Knight Hit/Skill/Dead.

## 원화 → 애니메이션 한 줄로 잇기 (2026-10-16)
- 점검 결과: 단계(D·E·F·A)는 다 있었지만 사이가 끊겨 있었다 — D→E의 Idle AI 시트 생성이 손으로 쓴 프롬프트였고, character.json을 손으로 만들었고, 문서 순서가 어긋났다(0절 기준 시트, E-5 set-height, D의 "이후는 사용자가 지시").
- 추가: `idle_base.py`(generate/verify/accept — Knight_Idle try1·2를 옮김. verify가 try1 +16% 불합격, try2 +1% 합격을 재현), `deform.py accept --height-cm --required`(설정 뼈대, skull_over_L 추정), `set-reference --keep-height --chin`(ref_chin_to_sole을 원본 × 배율로 — Knight 386 재현. 출력 프레임에서 재면 머리카락 하이라이트를 턱으로 잡음), 파이프라인이 ref_height 없는 설정에서 set-height를 안내.
- SKILL.md에 "새 캐릭터 전체 순서" 표.
- 남은 것: 새 캐릭터로 처음부터 한 번 돌려 보기(실제 Codex 생성은 아직 이 순서로 안 돌림). skull_over_L 추정이 맞는지 그때 _deform_face.png로 확인. `.agents/skills/sprite-animation/`는 예전 사본(deform.py 없음) — 동기화 여부는 사용자 판단.

## 사용자 관문 3개 (2026-10-16, 사용자 제안)
- 사용자 판단: 원화 → 데포르메 → 애니메이팅 원큐는 현실적으로 어렵다. 관문마다 멈추고 사용자 입력·확정을 받는다.
- 관문 1 설정 입력: `deform.py init`(키·힌트·필수 디자인 요소·프로필). generate가 init 없이는 멈추고, 힌트·필수 요소를 설정에서 읽는다. 설정 뼈대 생성은 accept에서 init으로 옮겼다.
- 관문 2 비교샷: `deform.py lineup` — 설정 키 비율대로 기존 캐릭터와 같은 바닥선에(set-height와 같은 잣대). Knight 턴어라운드 vs Archer A포즈로 확인(600:565 = 170:160). 확정 후 accept.
- 관문 3 동작별 디렉팅: character.json `actions.{액션}`(direction 원문·feel·definition·confirmed). 없으면 generate_action.py가 멈춤(`--skip-direction`은 관문 이전 캐릭터용).
- Knight·Archer에는 actions 기록이 없다 — 다시 뽑을 때 받거나 --skip-direction.

## Priest — 원화부터 Idle까지 첫 실행 (2026-10-16), 다음: 동작 5개
- 완료: ★1 설정(174cm, 필수 요소 7개) → 턴어라운드 4회 중 3차 채택(tall이 안 나와 hint normal로) → ★2 비교샷 → **3/4 모습이 왼쪽을 향해 생성되어 좌우 반전**(지팡이 왼손·책 오른손) →
  Idle AI 시트 1차(반전본 `SpriteRegen/Priest_Idle/try1_flip/`, 몸 0번·눈 감은 2번) → set-height(정수리~발 목표 526.7px → ref_height 552.4 = 다리 편 키) → Idle_v2(kneebody + 지팡이 고정 층) 적용·기준 시트 → ★3 디렉팅·정의 확정.
- 씬: `Assets/Scenes/New Scene.unity`에 Priest(Knight 왼쪽, 같은 바닥선).
- **다음 작업 = 동작 제작(SKILL.md F)**. 사용자 지시 전에는 시작하지 않는다(2026-10-16 "아직 작업시작하지마셈").
  - 디렉팅 원문·확정 정의·align_x: `Assets/_/Spirte/Priest/Priest.character.json` `actions`. 정의 전문·근거: `references/motion.md` 3절 "Priest 동작 정의".
  - 손: Skill2는 두 손(책은 사라져도 됨), Skill3는 한 손. Dead 끝 = 앞으로 쓰러짐.
  - 순서는 사용자에게 묻는다(제안: Skill1 → Hit → Skill3 → Dead → Skill2).
  - 몸 기준(generate_action의 character.png) = `idle.source` 0번 = 반전본. `SpriteRegen/`는 git 무시 — **이 PC에만 있다**. 다른 PC면 Idle AI 시트부터 다시.
  - 레퍼런스 후보: `SpriteRegen/_refs/priest_candidates/`(SOURCES.txt, 머이브리지 PD·LPC CC0). 실루엣으로 바꿔 사용자가 고른다(F 2).
- 이번에 드러난 도구 빈칸(아직 안 고침): deform verify에 **향하는 방향**·**머리 크기** 검사 없음(2차 실사 비율·3/4 좌우 반전을 못 잡음), 금발·흰 피부는 색으로 못 갈라 얼굴 지표 무효, 비교 녹화 이름표에 한글이 안 나옴(영문으로), 손에 쥔 고정 소품 층 나누기는 좌표 수작업(`staff_split`).

## Priest 동작 v1 → v3 (2026-10-18~19), 다음: v3 피드백 반영
- 적용 현황: Skill1_v3 / Skill2_v3 / Skill3_v3 / Hit_v2 / Dead_v3 (Idle_v2). 비교 녹화 `Recordings/Priest_*_v3_compare.mp4`(git 무시).
- 몸 기준: SSAFY PC의 `idle.source`(반전본)가 이 PC에 없어 `Priest_Idle_v2` 0번을 썼다(`generate_action.py --body`).
- v1→v2: `--fps`에 최종 fps(24·30)를 넣어 클립이 3배 빨랐다. `--fps`는 보간 전 원본 기준 — 최종 24면 `--fps 8`(보간 2장일 때).
- v2 사용자 지적과 원인:
  - Skill1 "부위 크기가 변하고 앞뒤로 이동": 4장씩 나눠 생성해 장마다 몸 크기·위치가 다름 + `partScale`이 금발 얼굴을 잘못 재 4장을 13% 확대.
    → **Idle 0번을 포즈마다 편집**(모든 장이 같은 몸)으로 해결. 큰 동작 외에 '몸은 그대로, 팔·소품만'인 동작은 이 방식이 낫다.
  - Skill2 "부정확, 원반으로": 조사 결과 smear / blur disc. 사용자 결정: 손은 원반 중심 고정, 원반은 코드.
  - Skill3 "지팡이 부자연": 가는 지팡이 회전 구간 RIFE 보간으로 지팡이가 녹음 + 한 장에서 지팡이가 아래로 꺾였다 올라옴.
  - Dead "같은 프레임 반복": 첫 장이 이미 무릎을 꿇었는데 둘째 장이 다시 높은 자세에서 시작 → 높이가 계속 내려가는 장만 다시 이음.
- 임시 도구(이 PC `SpriteRegen/_tools/`, 생성 데이터와 함께만 의미 있음): `pose_edit.py`(Idle 편집 생성), `disc.py`(원반), `build_skill2.py`(Skill2 조립),
  `diag.py`(구슬 크기·몸통 x·이웃 차이), `vs_idle.py`(Idle 0번과 나란히), `priest_v3.ps1`(적용+녹화). 스킬 스크립트로 옮길지는 사용자 판단.
- **v3 사용자 피드백 (2026-10-19, 아직 반영 안 함)**:
  - 전반: **누끼(배경 제거)가 덜 따진 부분**이 있다. Idle 편집본은 흰 배경 결과라 `splice_frames`/`disc.cut_white`의 흰색 제거가 가장자리·틈에 흰 테를 남긴 것으로 추정 — 확인 필요.
  - Skill1: **너무 높이 든다** — 팔이 기괴하게 늘어난 것처럼 보인다(정점 장 `peak`·`raise3`).
  - Skill2: **원반이 너무 작다**(지금 rx 280 = 가로로 든 지팡이 길이의 절반 근처), **너무 하얗다**(지팡이는 흰 막대만이 아니다 — 금 마디·파란 구슬·은색),
    **내려찍기가 보간 없이 뚝 떨어진다**(raise → slam_smear → impact가 각 1장).
  - Skill3: **보간을 더**, **왼다리를 앞으로 뻗는 동작** 추가, **표정 변화(작은 함성)** 추가.
