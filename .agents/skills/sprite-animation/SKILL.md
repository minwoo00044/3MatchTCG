---
name: sprite-animation
description: 이 프로젝트(3MatchTCG)의 캐릭터 스프라이트 시트를 Unity 애니메이션으로 만들고, 시트 간 체형·디자인을 맞추는 작업 전체. AI로 만든 스프라이트 시트를 Assets에 넣어 클립·AnimatorController까지 연결할 때, 시트 이름·폴더 규칙(Spirte/{캐릭터}, _Anim/{캐릭터}, prev/), 발 정렬·pivot·셀 잘림·스케일 문제, 시트끼리 캐릭터 비율(등신·머리 크기·부츠)이나 디자인(머리색·소품)이 다른지 감사할 때, Codex 이미지 생성으로 기준 시트의 체형에 맞춰 시트를 다시 그리고 검증·적용할 때 반드시 사용한다. "스프라이트 시트 적용", "애니메이션 클립 만들어", "Idle이랑 비율 달라", "체형 맞춰서 재생성", "새 캐릭터 애니메이션", "Hit/Skill/Dead 시트", "원화로 새 캐릭터 만들기", "데포르메", "턴어라운드", "체형 마네킹", "찌르기/베기 모션 만들어", "터프하게/어색해/스무드해", "이 부분만 고쳐", "애니메이션별로 크기가 달라", "칼이 순간이동", "정면을 봐" 같은 디렉팅이나, spritesheet png를 게임에 넣으려는 모든 경우에 해당한다.
---

# 스프라이트 시트 → 애니메이션 (3MatchTCG)

요청에 맞는 갈래만 따라간다. 셋은 이어진다: 감사(B)에서 벗어난 시트를 재생성(C)하고, 합격본을 적용(A)한다.
**HD 원화로 새 캐릭터를 처음부터 만들면** 갈래를 고르지 말고 아래 "새 캐릭터 전체 순서"를 따른다.

| 갈래 | 언제 |
|---|---|
| **A. 적용** | 시트(원본 png)를 게임에 넣는다 |
| **B. 감사** | 시트끼리 체형·디자인이 다른지 본다 |
| **C. 재생성** | 기준 체형에 맞춰 Codex로 다시 그리고, 검증해서 적용한다 |
| **D. 새 캐릭터** | 사용자가 준 HD 원화로 데포르메 턴어라운드를 만든다 (v1 생성의 첫 단계) |
| **E. 새 캐릭터 Idle** | 반자동 Idle |
| **F. 새 동작 (원본 없이)** | Hit·Skill·Dead를 레퍼런스 + 나눠 생성으로 만든다 |
| **G. 모호한 디렉팅** | "터프하게", "어색하다" 같은 말을 받았을 때 — 조사로 정의한 뒤 움직인다 |
| **H. 일부 구간만 다시** | "이 부분만 어색하다" — 마음에 든 장면은 두고 그 구간만 다시 그려 끼운다 |

파이프라인 자체(분할·정렬·스케일·매니페스트·Unity 적용)의 규칙은 `docs/SPRITE_ANIMATION_GUIDE.md`에 있다.

## 새 캐릭터 전체 순서 (HD 원화 → 게임 내 애니메이션)

Knight(2026-10-14~15)가 이 순서로 원화에서 6개 동작까지 갔다. **한 번에 끝까지 돌리지 않는다** — 원화 → 데포르메 → 애니메이팅은 사람 판단이 필요한 곳이 많아서,
**관문(★)마다 멈추고 사용자 입력·확정을 받은 뒤** 다음으로 간다. 각 단계는 앞 단계의 산출물이 있어야 돈다(스크립트가 없으면 멈춘다).

| # | 단계 | 명령 | 산출물 / 사용자 |
|---|---|---|---|
| ★1 | **설정 입력** | AskUserQuestion → `deform.py init` | `{캐릭터}.character.json`. 아래 "관문 1" |
| 2 | 턴어라운드 (D) | `deform.py generate` → `verify` | 비율·디자인 (지금처럼 결과마다 보고) |
| ★2 | **비교샷 검증** | `deform.py lineup` → 사용자 확정 → `deform.py accept` | `_lineup_{캐릭터}.png`. 아래 "관문 2" |
| 3 | Idle AI 시트 | `idle_base.py generate` → `verify` → `accept --base i --blink j` | 몸·눈 감은 프레임 |
| 4 | 게임 내 키 | `sheet_check.py set-height --character X --relative-to Archer --sheet <3의 시트>` | `ref_height` |
| 5 | 반자동 Idle (E) | 움직임 정하기 → `procedural_idle.py` → 처리 → Apply | `{캐릭터}_Idle_v1`. 움직임 폭은 사용자 확정 |
| 6 | 기준 시트 지정 | `sheet_check.py set-reference <Idle_v1> --keep-height --chin` | `reference`, `ref_chin_to_sole` (0절의 '기준 시트'가 여기서 생긴다) |
| ★3 | **동작별 디렉팅** | 동작마다 사용자 디렉팅 → `actions.{액션}` 기록 | 아래 "관문 3". 없으면 `generate_action.py`가 멈춘다 |
| 7 | 동작별 생성 (F) | 정의 → 레퍼런스 → spec → `generate_action.py` → 처리 → 검사 → 비교 녹화 → Apply | Hit·Skill1~3·Dead |
| 8 | 감사 (B) | `sheet_check.py audit --reference <Idle>` | 크기·디자인이 동작끼리 맞는지 |

### 적 캐릭터 (team: enemy)
순서는 위와 같다. 다른 점은 둘이고, 규칙은 `process_sprite_sheet.py`의 `TEAMS` 한 곳에 있다.
- **액션**: Idle(반자동, 대기용)·Hit·Skill1·Dead만. 다른 액션은 `generate_action`·`pose_edit`·`codex_generate`·파이프라인이 거부한다. 관문 3 디렉팅도 Hit·Skill1·Dead 셋.
- **방향**: 아군과 마주 보도록 왼쪽을 본다. **생성·검증은 아군과 똑같이 오른쪽으로** 하고(마네킹·참고 시트·프롬프트가 전부 오른쪽 기준, 왼쪽으로 그리게 하면 방향을 자주 틀린다),
  파이프라인이 출력 셀만 좌우 반전해 시트에 굽는다(매니페스트 `mirrored: true`). 게임 쪽 flipX는 쓰지 않는다.
  - 원화·턴어라운드·`body.png`·Codex 결과·`source~` 원본 프레임은 전부 오른쪽을 보는 그림이다. 처리된 시트(`Spirte/{캐릭터}/*.png`)만 왼쪽.
  - 비대칭 디자인(무기를 쥔 손, 한쪽 어깨 장식, 글자)도 같이 뒤집힌다. 손은 **그린 그림 기준**으로 `design.required`·spec에 적고, 게임에서는 반대 손이 된다고 관문 1에서 사용자에게 말한다. 글자·문양은 피한다.
  - `align_x`의 `left_foot`/`right_foot`과 `footSlide`는 **반전 전(그린 그림) 기준** 화면 왼쪽/오른쪽이다 — 미리보기 1칸(원본+분할선)을 보고 정한다. 아틀라스·겹쳐보기 칸은 반전된 모습이다.
  - 처리된 시트를 Codex 참고로 붙일 때(`codex_generate` 기준·소품 참고)는 `common.as_drawn`이 오른쪽으로 되돌려 붙인다. 측정(키·머리 비율·색·sizeFit)은 좌우 대칭이라 그대로.
  - **처리된(반전된) 시트를 다시 파이프라인 `--input`으로 넣지 않는다** — 두 번 뒤집혀 오른쪽을 보게 된다. 다시 만들 땐 원본(`source~`, `source_build.py`)에서.
- 설정: `deform.py init ... --team enemy` → `character.json` `"team": "enemy"`(없으면 ally). 키 비교(`lineup`·`set-height --relative-to`)는 아군과 같이 한다.

### 사람이 아닌 캐릭터·한 손 무기 (Goblin, 2026-10-22~23)
- **피부색**: 턱 찾기(`deform.face_chin`)는 사람 피부색 기준이다. 피부가 다른 캐릭터는 `character.json palette.skin`을 먼저 넣고 `sheet_check.py masks`로 확인한다 —
  없으면 천·붕대를 턱으로 잡아 키·배율·Idle 깜빡임 자리가 전부 틀렸다(Goblin Idle_v1은 눈을 한 번도 안 감았다). `skull_over_L` 추정도 비교샷 파랑 선으로 다시 잰다.
- **무기 손**: `generate_action`(처음부터 그림)은 휘두르기 전 동작을 **뒤쪽 팔**로 그리려는 편향이 강했다 — 손 지정 문구·편집으로도 안 고쳐짐(Skill1 4회).
  무기가 앞쪽 손이면 **Idle 몸을 `pose_edit`로 편집**해 시작한다(이미 그 손에 쥔 그림이라 바뀌지 않는다).
- **이어서 편집**: Idle 몸에서 매번 출발하면 팔다리를 최소로만 움직인다(Hit "단검 손이 휘청임에 맞지 않게 고정"). 앞 장 결과를 다음 장 `body`로 —
  `pose_chain.py`(생성 → `accept --match-color source~/body.png` → 다음 장). 장마다 색이 붉어지고 크기가 커지는 게 쌓이니
  색은 `--match-color`, 크기는 실루엣 면적으로 재서 `splice_frames.py --keep-canvas --scales`(발밑 고정)로 고친다.
- 사용자 지적으로 굳힌 동작 규칙: 무기 팔은 몸을 한 박자 늦게 따라가고, 몸이 뒤로 넘어가면 손목이 끌려 칼날이 뒤로 처진다. 큰 자세 변화(서 있음 → 젖혀짐, 기울어짐 → 누움) 사이에는 장면을 하나 더 그린다.
- 런지처럼 뒷발이 바닥에 납작하면 발 검출이 놓친다 → `splice_frames.py --pin-foot left` + `--align_x anchor`. 쓰러지며 이동하는 동작은 `--keep-canvas`.

### 관문 1 — 설정 입력 (생성 전에)
원화를 보고 후보를 제안하고, AskUserQuestion으로 받는다. 짐작으로 채우지 않는다.
- **이름**(영문, 대문자 시작), **키(cm)** — 기존 캐릭터를 함께 보여 준다(Archer 160, Knight 170). 키 차이는 게임 안에서 실제 크기 차이로 보인다.
- **체형 힌트** `normal`/`young`/`tall` — 원화의 인상(어림·성숙)으로 제안한다. 힌트는 **현재 마네킹 대비**다: 마네킹 v3 = Knight 9차 비율이라 `normal` = Knight와 같은 비율, `tall` = Knight보다 머리 −8%·다리 +8%.
  ("Knight가 tall로 확정됐다"는 옛 마네킹 기준이다 — 그렇게 설명하면 tall이 Knight 비율인 줄 안다. Priest 설정 때 실제로 헷갈렸다.)
- **필수 디자인 요소** — 원화에서 무기·장식·망토 같은 후보를 영어 짧은 문장으로 뽑아 고르게 한다. 원화에 오류로 보이는 것(Knight 하이힐)은 따로 묻는다.
- **프로필** — 체격·성격·무기와 쥐는 손. Idle 움직임(E)과 동작 디렉팅(관문 3)의 근거가 된다.
```bash
python $SK/deform.py init --character Knight --height-cm 170 --hint tall \
  --required "longsword with a gold cross-guard" --required "..." --profile "중갑 기사, 침착함, 검은 오른손"
```
`skull_over_L`(두개골/턱~발바닥)은 기준 캐릭터 값 × 힌트로 **추정**한다. 게임 내 키에만 쓰이고, 틀리면 키가 2~3% 어긋난다(관문 2 그림의 파랑 선으로 확인).

### 관문 2 — 비교샷 검증 (데포르메 후, accept 전)
```bash
python $SK/deform.py lineup --character Knight SpriteRegen/Knight_Deform/tryN/result.png   # 기본: 설정이 있는 다른 캐릭터 전부
```
새 캐릭터 3/4와 기존 캐릭터(턴어라운드 3/4 → A포즈 → 기준 시트 순)를 **설정 키 비율대로** 같은 바닥선에 세운다. 크기 잣대는 `set-height`와 같아서 게임 안 크기와 같다.
파랑 = 정수리(머리카락 제외), 회색 = 10cm. 그림을 Read로 직접 본 뒤 사용자에게 보여 주고 묻는다: 키 차이, 머리 크기, 화풍, 같은 게임 캐릭터로 보이는지.
`verify`의 마네킹 비교는 비율 검사이고, 이 그림은 **다른 캐릭터 옆에 섰을 때**를 본다 — 둘 다 본다. 사용자가 확정해야 `accept`한다. 지적이 나오면 2로 돌아가거나(디자인·비율) init 값을 고친다(키·힌트).

### 관문 3 — 동작별 디렉팅 (동작마다, 생성 전에)
동작 하나씩 사용자에게 받는다. GDD 기준 캐릭터마다 Idle·Hit·Skill1~3·Dead(스킬은 3개)다. 받을 것:
- **무엇을 하는 동작인가** — 사용자의 말 그대로 기록한다(예: "의장대처럼 칼을 돌리고 꽂는다").
- **느낌** — "터프하게", "가볍게" 같은 말이 나오면 G로 정의한다.
- 무기·손, 바닥에 박힌 발(`align_x` 후보), 장수(8/12), 참고 영상·이미지가 있는지.
`character.json`에 적는다(사용자 말은 한국어 그대로, 정리한 정의는 따로):
```json
"actions": {
  "Skill1": {"direction": "사용자의 말 그대로", "feel": ["터프", "빠름"], "definition": "motion.md 3절 형식으로 정리한 것", "confirmed": "2026-10-16"}
}
```
`definition`은 사용자에게 보여 주고 확인받는다. spec(F 3)은 이 정의를 영어로 옮긴 것이다. 디렉팅 없이 spec부터 쓰면 짐작으로 그리게 된다(Knight Skill3 "칼 휘두르기"는 두 번 퇴짜).
관문 이전에 만든 캐릭터(Knight·Archer)를 다시 뽑을 때만 `generate_action.py --skip-direction`.

### 그 밖에
- 3은 그대로 게임에 넣지 않는다. Knight에서 AI Idle 8장을 그대로 쓰면 얼굴이 프레임마다 다시 그려졌다(E 참고). 이 시트의 쓰임은 5의 몸, 7의 `character.png`, 4의 키 측정이다.
- 6 전에는 기준 시트가 없으므로 0절 질문을 하지 않는다. 6 이후 작업부터 0절을 따른다.
- 4를 하기 전에 시트를 처리하면 파이프라인이 "기준 키가 아직 없다"며 멈춘다(의도된 동작).

## 0. 시작 전에: 기준 시트를 사용자에게 지정받는다

모든 갈래는 **기준 시트** 하나에 맞춘다. 스케일(체급), 체형 비교, 재생성 레퍼런스가 전부 이 시트에서 나온다.
기준은 사용자가 정한다 — 어느 시트가 '맞는 모습'인지는 기획 판단이기 때문이다. 짐작해서 고르지 않는다.

1. 캐릭터의 현재 기준을 확인한다: `Assets/_/Spirte/{캐릭터}/{캐릭터}.character.json`의 `reference`.
2. 사용자에게 묻는다(AskUserQuestion). 후보는 그 캐릭터의 현재 시트들(`prev/` 제외)이고, 설정에 기준이 있으면 그것을 첫 번째로 둔다.
   새 캐릭터라 시트가 하나도 없으면 "새 캐릭터 전체 순서"의 1~6을 먼저 한다 — 6에서 Idle이 기준이 된다.
   (사용자가 원화 없이 시트를 바로 주면, 그 시트를 A로 넣는다 — 설정이 없으면 첫 시트가 기준이 된다.)
3. 사용자가 고른 시트가 설정의 기준과 다르면 기준을 바꾼다:
   ```bash
   python $SK/sheet_check.py set-reference Assets/_/Spirte/Archer/Archer_Idle_v3.png
   ```
   기준 키(다리를 편 키)가 다시 재진다. 설정에 `ref_chin_to_sole`이 있으면 그것도 새 기준에서 다시 잰다(원본 프레임 × 처리 배율).
   `set-height`로 게임 내 키를 정한 캐릭터는 `--keep-height`를 붙여 그 키를 유지한다. **기존 시트의 스케일은 자동으로 바뀌지 않는다** — 새 기준에 맞추려면 각 시트를 원본에서 다시 처리·적용한다(A). 사용자에게 그 범위를 알리고 진행 여부를 묻는다.

4. **필수 디자인 요소**도 확인한다. `character.json`의 `design.required`(예: 화살통, 벨트)를 보여 주고 맞는지 묻는다.
   기준 시트는 체형의 정답이지만, 소품은 기준 시트에 빠져 있을 수도 있다(Archer는 Idle_v3에 화살통·벨트가 없지만 모든 시트에 있어야 한다).
   목록이 없거나 바뀌면 `design.required`(영어 짧은 문장 목록)와, 그 요소가 잘 보이는 시트 이름 `design.props_reference`를 적는다.

이후 `--reference`에는 항상 기준 시트를 넘긴다.

## 공통 규칙

- **이름**: `{캐릭터}_{Idle|Hit|Skill1~9|Dead}_v{N}` (예: `Archer_Skill1_v2`). 규칙 밖 이름은 전처리기가 거부한다.
- **폴더**: 시트·매니페스트 `Assets/_/Spirte/{캐릭터}/`, 클립 `Assets/_/_Anim/{캐릭터}/`, 컨트롤러 `Assets/_/_AnimCon/{캐릭터}.controller`(상태 = 액션). 폴더 이름 `Spirte`는 오타지만 현행 경로다.
- **새 버전**은 덮어쓰지 않고 `_v{N+1}`로 올린다(`prev/`까지 포함한 최고 버전 + 1). `Apply`가 낮은 버전을 `prev/`로 옮긴다(GUID 유지).
- **원본**은 사용자가 그 액션의 첫 버전(보통 v1)으로 넣은 파일이다 — 매니페스트의 `source`. 그 파일이 없으면 원본은 없는 것이다. Downloads 같은 다른 곳을 뒤져 비슷한 파일을 찾지 않는다. 사용자가 새 파일을 주면 그걸 쓴다.
- **Unity 에디터**가 열려 있어야 적용할 수 있다. `unity status`가 `ready`인지 먼저 본다. 아니면 전처리까지만 하고 사람에게 알린다.
- 스크립트 경로 `$SK` = `.claude/skills/sprite-animation/scripts`. 프로젝트 루트에서 실행한다.
- 커밋은 사용자가 요청할 때만. 작업 트리에 무관한 변경(씬, 테스트 프리팹 등)이 섞여 있으면 이번 작업 파일만 스테이징한다.

### PC 간 공유 (2026-10-19 사용자 교훈: "PC 간 도구 공유가 안 된다")
사용자는 여러 PC에서 작업한다. `SpriteRegen/`(git 무시)과 세션 scratchpad에만 있는 것은 다른 PC에 없다.
- **도구는 처음부터 이 스킬의 `scripts/`에 만든다.** 결과물에 쓰인 스크립트를 scratchpad에 두지 않는다(Priest v3 때 원반·포즈 편집 도구가 그렇게 한 PC에만 남았다). 경로·캐릭터·포즈를 하드코딩하지 말고 인자·spec(JSON)으로 받는다.
- **확정된 입력은 `Assets/_/Spirte/{캐릭터}/source~/`에 커밋한다.** `~`로 끝나 Unity는 임포트하지 않는다.
  - `body.png`: 몸 기준 한 장(`character.json idle.body`) — `generate_action.py`·`pose_edit.py` 기본
  - `specs/{액션}.json`(generate_action), `pose/{액션}.json`(pose_edit)
  - `{액션}/`: 현재 적용 버전의 원본 프레임 + `process.json`(이은 순서·처리 옵션) + 필요하면 `recipe.json`(smear)
  - 시도별 결과(`tryN/`)는 SpriteRegen/에 남긴다. 사용자가 고른 것만 source~로 옮긴다(`pose_edit.py accept`, 또는 복사).
- **`character.json`이 git 무시 경로를 가리키지 않게 한다.** 파이프라인·generate_action·pose_edit가 경고하고, `sheet_check.py portable`이 전부 검사한다(있으면 종료 코드 4).
  작업을 이어받을 때 먼저 돌린다. 걸리면 그 파일이 있는 PC에서 source~로 옮겨 커밋해 달라고 사용자에게 말한다.
- 매니페스트(`{시트}.json`)의 `source`는 프로젝트 루트 기준 상대 경로로 적힌다(예전 시트는 다른 PC의 절대 경로일 수 있다).
- 다시 만들기: `python $SK/source_build.py --character Priest --action Skill3 --name Priest_Skill3_v4` — process.json대로 조립·처리. `--list`로 목록.
- `.agents/skills/`는 이 스킬의 사본이다. 직접 고치지 않는다 — 여기를 고친 뒤 `python scripts/sync_agent_skills.py`(차이만 보려면 `--check`)로 맞추고 같이 커밋한다.

### 도구 목록 (이 갈래들 밖에서 추가된 것)
| 스크립트 | 하는 일 |
|---|---|
| `pose_edit.py` | 몸 기준 한 장을 포즈마다 Codex로 편집 — 몸 크기·위치가 모든 장에서 같다. 몸은 그대로, 팔·소품·표정만 바뀌는 동작용(Priest Skill1·2·3).
  **초록 키 배경**(`design.key_color`)으로 받고 `accept`가 투명 PNG로 — 흰 배경은 몸에 둘러싸인 배경 칸이 남았다. 다리를 쓰는 장은 포즈별 `legs_keep`, 준비 장면은 `base`(몸 기준 그대로) |
| `smear.py` | 빠르게 도는 소품을 원반(smear)으로 그리고, 레시피(JSON)로 원본 프레임을 조립(잔상·빛 터짐 포함) |
| `source_build.py` | `source~/{액션}/process.json`대로 현재 버전을 다시 만든다 |
| `record_compare.py` | 적용(`--apply`) + 반복 재생 사본 + 기준 Idle과 나란히 녹화 (unity CLI) |
| `sheet_check.py frames` | 처리된 시트의 프레임별 소품 크기·몸통 x·이웃 차이 (크기 변화·앞뒤 이동·같은 장 반복 원인 찾기) |
| `sheet_check.py side-by-side` | 기준 시트 0번과 같은 접지선·배율로 나란히 (F 6) |
| `sheet_check.py portable` | 위 공유 검사 |
| `prop_split.py` | 몸 프레임을 몸·고정 소품·쥔 손 세 층으로 (반자동 Idle에서 지팡이 고정, 좌표는 spec) |

pose_edit 장으로 만드는 동작의 처리 규칙 (Priest v4, 2026-10-19~20):
- `process.json` `"keep_canvas": true` + `--align_x anchor`: 장을 자르지 않고 캔버스째 잇는다. 경계 상자 가운데 맞춤은 지팡이·원반 쪽으로 몸을 밀었다.
  다리를 내딛는 동작은 Codex가 몸 위치를 못 지켜 `--align_x left_foot`(고정 발) — Skill3.
- `"lock_static": {"base": "base.png", "thr": 60}`: 장마다 몸 위치를 준비 장면에 맞추고(±8px) 거의 같은 픽셀은 준비 장면으로 — 장마다 다시 그린
  다리·코트가 반짝여 "AI 티"(사용자). 바뀐 곳(팔·소품·표정)만 새 그림.
- 휘두르는·도는 가는 소품 구간은 보간 0 대신 **장면을 더 그린다**. 세로로 든 소품이 위아래로만 움직이는 구간은 보간해도 녹지 않았다(Skill1 v5).
- 장면 높이가 순서대로 이어지는지 `sheet_check.py frames`의 `top`으로 본다 — Skill1 raise3가 정점보다 높게 그려져 올랐다 내렸다 했다.
- 발 미끄러짐(`footSlide`)은 소품 끝이 발 옆 바닥에 닿으면 소품을 발로 잡아 부풀려진다. 미리보기 겹쳐보기로 실제 발을 본다.
- 녹화는 `record_compare.py`로 한다(시트별 Idle 비교 / `--clips … --labels … --name …` 여러 클립 한 영상 / `--showcase 캐릭터` 전체 동작).
  에디터 창이 다른 창 뒤에 있으면 Unity가 플레이 모드 갱신을 2초에 5프레임 정도로 낮춰 녹화가 끝나지 않는 것처럼 보였다(6시간 멈춤, 2026-10-20).
  도구가 기다리는 동안 `EditorApplication.QueuePlayerLoopUpdate`를 계속 불러 밀어 넣는다(창이 뒤에 있어도 Priest 전체 녹화 약 5분).
  C#(`AnimationCompareRecorder`·`AnimationShowcaseRecorder`)를 직접 부르면 이 밀어 넣기가 없다. 이름표는 영문(한글이 안 그려진다).

## A. 적용

```bash
# 1) 측정만 — 에셋을 쓰지 않는다
python scripts/process_sprite_sheet.py --input "<사용자가 준 파일>" --name Archer_Hit_v2 --analyze
# 2) 미리보기를 Read로 열어 확인 (RESULT의 preview 경로)
# 3) 전처리
python scripts/process_sprite_sheet.py --input "<사용자가 준 파일>" --name Archer_Hit_v2
# 4) Unity 적용 — eval 한 번에 시트 한 장씩 (여러 장을 한 eval에 묶으면 실패한 적이 있다)
unity cmd eval 'AssetDatabase.Refresh(); return SpriteAnimationPipeline.Apply("Assets/_/Spirte/Archer/Archer_Hit_v2.png");' --result-only
```

미리보기는 서너 칸이다. 이걸 보지 않고 넘어가지 않는다 — 수치로는 안 보이는 실패가 여기서 보인다.
1. 원본 + 분할선(분홍 행, 하늘 열): 선이 몸을 가로지르면 분할 실패
2. 아틀라스 + 접지선(빨강)·pivot(파랑): 발이 빨간 선 위에 서야 한다
3. 겹쳐보기: 고정한 발이 번지면 흔들린다. 가로 정렬은 `{캐릭터}.character.json`의 `align_x`(액션별 고정 발)를 따른다 — 종류는 `docs/SPRITE_ANIMATION_GUIDE.md` 액션별 기본값. RESULT의 `footSlide`(발별 미끄러짐 px)로 숫자도 본다
4. 번짐 구간(있을 때만): 원본 A | 보간본 | 원본 B. 처리 단계는 기본으로 프레임 증강(원본 사이 2장, RIFE, 구간마다 번짐이 가장 적은 흐름 해상도)을 붙이고, 최선값도 기준을 넘는 구간만 끊는다(`(cut)`) — 가이드의 "프레임 증강". 끊김은 플레이에서 눈에 띄니 끊긴 구간이 있으면 사용자에게 알린다

새 캐릭터·새 액션이면 `align_x`가 없다. 시트를 보고 어느 발을 디디는 동작인지 사용자에게 묻고 적는다. 정하기 전에 `--analyze --align_x <방식>`으로 방식별 `footSlide`를 비교해 보여 준다.
Idle처럼 작게 움직이는 루프는 처리할 때 `--stabilize`를 붙인다(상체 위치를 부드러운 숨쉬기 궤적으로 보정, 허리 위만). 새 캐릭터 Idle은 기본으로 붙인다(Knight: 원본 상체가 프레임마다 ±6px 튀었다). 상체가 튀는지는 `python $SK/sheet_check.py jitter <처리된 시트>`로 본다(이웃 프레임 평균에서 벗어난 거리). Idle처럼 작게 움직이는 루프에서만 의미가 있다 — 큰 동작은 의도한 움직임도 걸린다.

- 시트를 여러 장 처리했으면 Apply 전에 `unity cmd eval 'AssetDatabase.Refresh(); return 0;'`을 따로 한 번 돌린다. 여러 장 임포트는 5초 제한에 걸려 응답만 실패할 수 있다 — 임포트는 계속되니 `unity status`가 ready인지 본 뒤 한 장씩 Apply하고, Apply가 실패로 오면 상태를 확인하고 재실행한다.
- RESULT의 `warnings`(원본 가장자리 잘림, 프레임 겹침, 번짐으로 끊은 구간)는 사용자에게 그대로 전한다. 원본에서 잘린 것은 복구할 수 없다.
- `scale`은 기준 키 ÷ 이 시트 0번 프레임의 '다리를 편 키'다(`ref_chin_to_sole`이 있으면 턱~발바닥). 1.1 이상이면 확대로 약간 흐려질 수 있다고 알린다.
  그 뒤 자동 보정이 두 번 붙는다(끄려면 `--no_size_fit`):
  - `sizeFit`: 0번 프레임 실루엣을 기준 시트(Idle) 0번에 IoU로 겹쳐 배율을 곱한다. 키·턱 길이가 같아도 AI가 머리·몸통 부피를 시트마다 달리 그려 동작이 바뀔 때 크기가 튀었다(Knight +2~6%, 사용자 "애니메이션별로 크기가 제각각").
  - `partScale`: `--input`이 여러 장이면 장별 얼굴 크기를 첫 장에 맞춘다(Knight Hit 둘째 장 머리 +15~20%). 3~15%만 고치고 얼굴이 안 보이는 장(엎드림)은 건너뛴다.
  처리 후 `Idle 대비 ±2%`를 넘는지 0번 프레임 실루엣으로 확인한다.
- 발 검출은 바닥 띠에서 세로로 두툼한 열만 발로 본다(`FOOT_FILL`). 바닥까지 내려온 칼날을 발로 잡아 몸이 좌우로 194px 미끄러진 적이 있다. 그래도 `footSlide`가 크면 원본 장마다 보폭이 다르게 그려진 것 — 정렬로는 못 고치니 생성 규칙("뒷발은 모든 프레임 같은 자리")으로 다시 그린다.
- 넣으려는 파일이 이미 들어간 버전의 원본과 같으면(매니페스트 `source`가 같은 경로) 새 버전이 v1과 똑같아질 뿐이라고 먼저 알린다.

## B. 감사 (체형 + 디자인)

```bash
python $SK/sheet_check.py audit --reference <기준 시트>            # 같은 캐릭터의 최신 시트 전부
python $SK/sheet_check.py audit --reference <기준 시트> a.png b.png # 특정 시트만
```

출력은 두 표와 비교 이미지(RESULT의 compare)다. **수치와 이미지를 둘 다 본다.** 색 마스크로 재는 지표라 엉뚱한 곳을 잡으면 숫자가 그럴듯하게 틀린다.

**체형** — 기준 대비 %. 분모는 '다리를 편 키'라 보폭이 달라도 비교된다. 0번 프레임으로 판정(머리 ±8%, 머리카락·부츠 ±15%). 중앙값은 활을 든 자세·누운 자세에서 키가 왜곡되어 참고만 한다.
`leg`(다리 길이)는 참고 지표다. 실루엣으로 가랑이를 찾는데, 무기가 허벅지 사이를 덮으면 가랑이를 낮게 잡아 짧게 나온다. 비교 이미지의 분홍 선이 실제 가랑이에 있는지 보고 믿을지 정한다. 옷 길이는 수치로 재지 않는다(디자인에서 본다).

**디자인** — 두 가지를 함께 본다.
1. 색 지표(자동): 부위별 색조·채도·명도 차와 전체 색 분포 차. 경고가 붙은 항목(부위 색조 12°·채도·명도 0.12, 전체 채도·명도 0.06, 분포 0.25 초과)은 이미지로 확인한다.
2. 소품·형태(눈으로): 정답은 **`design.required`(사용자 지정) + 기준 시트**다. 둘이 다르면 `design.required`가 우선한다.
   감사 출력의 [필수 디자인 요소]와, 기준 이미지에서 뽑은 나머지 요소 — 무기, 머리 모양(포니테일·바보털·앞머리), 옷의 구조와 길이(후드·가슴 보호대·옷자락) — 를 목록으로 만들고, 시트마다 0번 프레임에서 있음/없음/다름을 표로 적는다.
   - 필수 요소가 없으면 불일치다(기준 시트에도 없으면 기준 시트도 불일치다).
   - 목록에도 기준에도 없는 소품이 있으면 사용자에게 넣을지 묻는다. 짐작해서 지우거나 넣지 않는다.
   - 예: Archer는 화살통과 허리 벨트가 필수다 → Idle_v3·Hit_v2·Skill3_v2는 불일치.
   애니메이션이 바뀔 때 소품이 나타났다 사라지는 게 플레이 중에 가장 눈에 띈다. 필수 요소는 재생성 프롬프트에 자동으로 들어가고, `design.props_reference` 시트의 0번 프레임이 소품 참고 이미지로 붙는다. 그 밖의 차이는 `--fix`로 적는다.

보고할 때:
- 새 캐릭터이거나 숫자가 이상하면(턱이 키의 80% 같은) `sheet_check.py masks <시트>`로 마스크를 보고, 틀렸으면 `{캐릭터}.character.json`에 `"palette"`를 넣는다(형식은 `sheet_check.py`의 `DEFAULT_PALETTE`).
- **기준 자체가 튀는지**도 말한다. 나머지가 모두 같은 방향으로 벗어나면 기준이 이상치일 수 있다. 어느 쪽에 맞출지는 사용자가 정한다.

## C. 재생성 (Codex)

기준 체형·디자인에 맞춰 시트를 다시 그린다. 생성은 수 분씩 걸리고 결과 편차가 크므로 **백그라운드로 돌리고, 한 장 끝날 때마다 검증**한다. 시작 전에 `references/regeneration.md`를 읽는다 — 모델이 어떻게 빗나가는지와 재시도 요령이 있다.

### 루프 (시트마다)

1. **생성** — 백그라운드로 실행한다(`run_in_background`). 먼저 `--dry-run`으로 프롬프트를 보여 줘도 된다(시도 번호를 쓰지 않는다).
   ```bash
   python $SK/codex_generate.py --reference <기준 시트> --action Hit \
     --action-desc "hit / damaged reaction animation" \
     --fix "Head is about 11% too large -> smaller head" \
     --fix "Hair volume is about 22% too large -> reduce to match #1"
   ```
   - 필수 디자인 요소(`design.required`)는 프롬프트에 자동으로 들어가고 소품 참고 이미지가 붙는다(`--props-reference`로 바꿀 수 있다). 그 밖의 디자인 차이는 `--fix`에 적는다.
   - 프롬프트 템플릿이 기준 시트의 색(머리·옷·피부·부츠·무기)을 그대로 유지하고 색보정·글로우·조명 효과를 넣지 말라고 이미 요구한다. 색이 틀어졌던 시도를 다시 할 때는 `--fix`에 부위와 차이를 적는다(예: "Hair is too bright -> same brightness as #1").
   - `--fix`에는 감사(B)에서 나온 **측정값**을 넣는다. 소품 차이도 여기 적는다(예: "The quiver on the back is missing -> add the same quiver as #1").
   - 원본은 그 액션의 첫 버전으로 넣은 파일을 자동으로 쓴다. 없으면 스크립트가 멈춘다 — 사용자에게 원본이 없다고 알리고, 다른 파일을 원본으로 쓸지 묻는다.
   - 스크립트가 실행 전에 Codex 5시간 사용량을 확인해서 85% 이상이면 생성하지 않고 종료 코드 3을 낸다.
2. **검증** — 생성이 끝나면 바로.
   ```bash
   python $SK/sheet_check.py verify --reference <기준 시트> --new SpriteRegen/Archer_Hit/try1/result.png --action Hit
   ```
   원본은 `--action`으로 첫 버전의 원본을 자동으로 찾는다(한글 경로를 셸로 넘기면 깨질 수 있어서). 다른 원본이면 `--original`.
   합격 = 0번 프레임 머리 ±8%, 머리카락 ±15%, 부츠 ±15%, **색 유지**(부위별 색조 18°·채도/명도 0.18, 실루엣 전체 채도/명도 0.09, 색 분포 0.375 이내 = 경고 기준의 1.5배), 모션 보존 ≥0.72, 분할 경고 없음. 종료 코드 0 합격 / 4 불합격.
   필수 디자인 요소는 자동 판정이 없다. 결과 이미지에서 모든 프레임에 있는지 반드시 눈으로 보고, 빠지면 불합격으로 다룬다.
   색이 경고 기준만 넘은 정도는 합격이지만, 결과 이미지(`result.png`)와 비교 이미지를 Read로 열어 소품 목록과 대조한다. 포즈가 원본과 달라졌는지(정지 화면, 넘어지는 순서)도 여기서 본다.
3. **합격** → 바로 A의 3~4단계로 `_v{N+1}` 적용. 입력은 `result.png`.
4. **불합격** → 재시도. 체형은 맞는데 소품·색 같은 일부만 고치면 되는 경우는 **편집 방식**(현재 합격 시트를 `--original`로, "THIS IS AN EDIT" 명시)이 다시 그리기보다 잘 맞는다 — `references/regeneration.md` 6절. 불합격 항목이 가장 적은 시도를 `--previous`로 붙이고 `--previous-note`에 무엇이 맞고 틀렸는지 쓴다. 다른 항목이 원본 쪽으로 돌아가는 것을 막는다.
5. **시트당 최대 4회**(실제 생성만 센다). 끝까지 합격이 없으면 가장 가까운 시도와 원본을 비교해 보고한다. 원본이 이미 기준 안이면 원본 유지를 권한다. 기준 밖 결과를 적용할지는 사용자가 정한다.

여러 시트를 동시에 돌려도 된다(각각 백그라운드). 사용량만 따로 보려면 `python $SK/codex_usage.py`.
작업 폴더 `SpriteRegen/`(git 무시)에 시도별 프롬프트·로그·결과가 남는다. 정리는 사용자가 원할 때만 한다.

### 보고

진행 중에는 한 장 검증할 때마다 짧게: 무엇이 합격/불합격인지, 수치, 다음 행동. 끝나면 표로:

| 시트 | 시도 | 결과 | 적용 |
|---|---|---|---|
| Hit | 4 | 합격 없음 (최선: 2차, 부츠 +16%) | 사용자 판단 |

원본 대비 개선 수치(머리·머리카락·부츠·등신), 디자인 차이(소품), 확대 스케일(1.1 이상이면 흐려질 수 있음), 모션 보존, 플레이 확인 필요 여부를 함께 적는다.

## D. 새 캐릭터 — HD 원화 → 데포르메 턴어라운드

"새 캐릭터 전체 순서"의 ★1 → 2 → ★2다. 다음은 3(`idle_base.py`).
비율·자세는 **체형 마네킹**(`assets/mannequin/`), 디자인은 **원화**, 화풍은 **마네킹을 만든 기준 시트**(mannequin.json `source`)에서 온다.

### 체형 마네킹 (이미 있음 — 다시 만들 때만)
`assets/mannequin/`: `m1_reference_pose.png`(Archer Idle 0번을 편집한 민머리 마네킹), `turnaround.png`(A포즈 앞·3/4·옆·뒤), `turnaround_guide.png`(기준선), `mannequin.json`(방향별 비율).
만드는 순서와 겪은 일은 `scripts/mannequin.py` 머리말에 있다. 요약: M1은 편집 1회 합격. 턴어라운드는 모델이 다리를 7% 짧게 그리는 쪽으로 돌아가 보정 지시로도 안 고쳐져서
`stretch-legs`(가랑이~발목 띠만 세로로 늘림)로 맞췄다. 바꾸려면 사용자 확인이 필요하다 — 모든 캐릭터의 기준이다.

### 루프
1. **입력** = **관문 1(설정 입력)**: 이름·키·체형 힌트·필수 디자인 요소·프로필을 받아 `deform.py init`. 힌트는 원화를 보고 제안하고 사용자가 정한다:
   `normal`(마네킹 그대로), `young`(머리 +10%, 다리 −10%), `tall`(머리 −8%, 다리 +8%).
2. **생성** (백그라운드, 수 분). 힌트·필수 디자인 요소는 character.json에서 읽는다(인자로 덮을 수 있다):
   ```bash
   python $SK/deform.py generate --character Knight --source "<원화>"
   ```
3. **검증**:
   ```bash
   python $SK/deform.py verify --hint normal SpriteRegen/Knight_Deform/try1/result.png
   ```
   수치 판정은 4명으로 나뉘는지와 네 방향 세로 키 일치뿐이다. 가랑이는 참고(치마·긴 머리카락이 가리면 밑단을 잡는다), 턱은 옷 입은 실루엣으로 못 잡는다.
   **그래서 비율 판정은 비교 이미지가 본체다**: 마네킹은 앞모습 '턱(얼굴 피부 아래 끝)~발바닥'으로 크기를 맞춰 겹친다.
   두개골이 머리카락 안에 들어가는지, 마네킹 가랑이가 캐릭터 다리 시작점(치마 밑단 근처)에, 발이 신발 안에 오는지 본다.
   키나 발 폭으로 맞추면 틀린다 — 머리카락(정수리 위 ~10%)과 바닥까지 내려온 무기 때문에. Knight 1차를 키로 맞춰 보고
   "머리 25% 크다"고 잘못 판단해 2차에 틀린 지시를 넣었다. 실제 턱 높이는 Knight 32.4% = Archer 32.3%였다.
   **비교 이미지(`_deform_overlay.png`, 마네킹 윤곽 빨강)와 결과를 반드시 눈으로 본다**: 머리·몸이 마네킹을 따라가는지, 네 방향이 같은 디자인인지(뒷모습 포함), 원화의 디자인 요소가 빠지거나 새로 생기지 않았는지, 색이 같은지.
   비교 이미지는 셋이다. 셋 다 본다:
   - `_deform_overlay.png` — 몸 전체에 마네킹 윤곽
   - `_deform_vs_reference.png` — 기준 캐릭터와 나란히(턱~발바닥 동일, 회색 = 1/4·1/2·3/4). **다리 시작 높이와 실루엣 폭**을 본다
   - `_deform_face.png` — 가상 얼굴형: 빨강 = 마네킹 두개골·턱, 초록 = 기준 캐릭터 눈 높이(mannequin.json `reference_face`), 파랑 = 턱.
     맨 왼쪽이 기준 캐릭터와 자기 마네킹이라 '맞는 모습'의 예시다
4. **불합격·사용자 지적** → C의 재시도 요령(측정값을 넣은 `--fix`, 가장 가까운 시도를 `--previous`)을 따른다. 최대 4회.
   측정 이미지(비교 이미지)를 `--previous`로 붙이면 모델이 무엇을 고칠지 더 잘 알아듣는다(Knight 4차: 기준 캐릭터와 나란한 그림을 붙여 허리를 올림).
   **고치기 전에 측정이 맞는지부터 본다.** 사용자가 "크다/짜리몽땅하다"고 하면 마스크·기준선을 그린 이미지로 무엇을 쟀는지 확인하고 원인을 숫자로 좁힌다.
5. **합격** → **관문 2(비교샷)**: `deform.py lineup`으로 기존 캐릭터 옆에 세운 그림을 보여 주고 확정받은 뒤:
   ```bash
   python $SK/deform.py accept --character Knight SpriteRegen/Knight_Deform/tryN/result.png
   ```
   `Assets/_/Spirte/{캐릭터}/design/`에 턴어라운드·원화·메타(json)를 둔다.

### Knight 기록 (2026-10-14, 원화 3면도, hint normal)
| 시도 | 결과 |
|---|---|
| 1 | 디자인 합격. 사용자: "짜리몽땅" |
| 2 | 내 측정 오류(마네킹을 머리카락 포함 키로 맞춰 "머리 25% 큼")로 틀린 지시 — 버림 |
| 3 | 다리 가늘게·분리. 다리 지표는 망토 안감 때문에 오판 → 참고로 내림 |
| 4 | 허리를 올림(치마 밑단 0.48 → 0.43 L, Archer와 같음) |
| 5 | 4차 얼굴 편집(아래 볼 +13% → +4%). 사용자: 4·5 사이 |
| — | 사용자가 마네킹 두개골이 Archer와 다르다고 지적 → 마네킹 v2(손으로 그린 두개골·귀 선으로 M1 편집, 턴어라운드 머리 교체) |
| 6 | 새 마네킹 기준 신규 생성. 아래 볼 +23% |
| 7·8 | 6차 얼굴 편집 +13% → −2% |
| 9 | 8차 베이스 + hint tall(설정 키 170cm, Archer 160cm). 머리(머리카락 포함)/L 0.39 → 0.31. **사용자: "저게 옳게 된 비율" — 확정** |

- 편집 결과끼리 RIFE로 중간을 만드는 건 두 그림이 거의 같을 때만 된다(4·5차 OK, 7·8차는 전체가 달라 흐려지고 중간값도 안 나옴).
- 사용자가 "신체 비율이 확연히 다르다"고 했을 때 단계별(Archer→M1→턴어라운드→Knight)로 같은 자세끼리 재 보니 길이 비율은 모두 맞았다.
  차이는 자세(Archer는 다리를 벌린 Idle, 턴어라운드는 A포즈)와 옷·머리 부피, 그리고 발 크기(마네킹 발이 Archer 부츠보다 −15%, M1 제작 때 폭을 검증하지 않음).
  사용자 판단: 그대로 두고 시트 단계에서 같은 자세로 다시 비교한다.
- 측정 함정 추가: 실루엣 단면 폭은 활·망토·검이 붙으면 틀린다 — 단면을 잴 땐 무엇을 잡았는지 그림으로 확인한다.

- 머리 크기는 Archer와 같았다(두개골 틀·눈 높이·얼굴 폭·눈동자). 사용자가 느낀 "얼굴이 큼"은 머리카락 부피(머리 포함 0.40 vs 0.43 L)와
  드러난 이마(보이는 얼굴 세로 1.5배) 때문이었다 — 원화 디자인을 따른 것이라 그대로 두었다.
- 측정 함정: 피부가 얼굴→목→V넥 가슴으로 이어지면 턱을 목 아래로 잡는다(face_chin 고침). 실루엣 다리 틈은 다리 뒤 망토가 막는다.
  키·발 폭으로 크기를 맞추면 머리카락·바닥까지 내려온 무기에 끌린다 — 턱~발바닥으로 맞춘다.

## E. 새 캐릭터 Idle (원본 시트 없이)

AI에게 Idle 8장을 그리게 하면 얼굴·세부가 프레임마다 다시 그려지고 부위가 따로 움직여 'AI가 만든 듯한' 움직임이 된다(Knight Idle v1~v5, 지표로는 안 잡혔고 사용자가 지적).
그래서 Idle은 **반자동**으로 만든다:
1. AI로 Idle 시트를 한 번 생성한다(디자인·비율 확인용). 같은 몸으로 그려진 '눈 뜬 프레임'과 '눈 감은 프레임'이 필요하다(위치·크기가 같은 두 프레임).
   ```bash
   python $SK/idle_base.py generate --character Knight --pose "standing in a calm ready stance ...; the longsword held in the right hand, lowered, tip pointing down ..."   # 백그라운드
   python $SK/idle_base.py verify --character Knight SpriteRegen/Knight_Idle/tryN/result.png
   ```
   - 턴어라운드 3/4·앞모습을 몸·디자인으로, 다른 캐릭터(`--motion-from`, 기본 Archer) 기준 Idle의 원본 4x2 시트를 타이밍·시점·칸 크기 참고로 붙인다. `--pose`는 무기를 어떻게 드는지까지 원화를 보고 쓴다.
   - 판정: 장마다 턱 높이(얼굴 아래 끝 / 머리카락 포함 키)가 턴어라운드 3/4와 ±5%, 장끼리 키 ±4%. 눈 감은 장·디자인·필수 요소·시점은 눈으로 본다.
   - 비율만 틀리면 편집으로 고친다: `--previous <그 결과> --edit --fix "the chin is at 27% of the figure height, in #1 it is at 23.6% -> head about 13% smaller, legs about 7% longer"`.
     Knight는 1차 머리 +16% → 편집 2차 +1%로 합격했다.
   - 합격이면 사용자에게 보여 주고 몸·눈 감은 프레임을 고른 뒤: `idle_base.py accept --character Knight <result.png> --base 0 --blink 2` (character.json `idle.source`·`base`·`blink`).
   - 이어서 게임 내 키(전체 순서 4): `sheet_check.py set-height ... --sheet <result.png>`.
2. **캐릭터별로 Idle에서 무엇이 움직일지 정한다** — 체격·장비·성격에 따라 다르다. 사용자에게 묻고 `{캐릭터}.character.json`의 `idle`에 적는다:
   - `mode`: `kneebody`(무릎 굽힘 + 경계 없는 몸 전체 호흡 + 가슴 좌우 부풂, Priest 확정) / `knee`(무릎 굽힘 + 허리에서 끊기는 호흡, Knight) /
     `body`(무릎 없이 몸 전체) / `chest`(쓰지 않는다 — 허리 위 가로 띠만 들려 "가슴만 사진으로 잘라 움직이는 것 같다", Priest) / `bob`(쓰지 않는다 — 스프링 인형)
     Priest에서 "숨쉬기는 무릎까지 움직여야 어색하지 않다"(사용자). 늘어진 것(긴 머리·코트·소품)이 많은 캐릭터일수록 한 덩어리 워프가 '오려낸' 느낌으로 보인다.
   - **땅에 짚은 단단한 소품**(지팡이 등)은 몸과 같이 워프하면 휘고 늘어난다. 층으로 나눠 `body_image`(소품 뺀 몸)·`static_layer`(고정 소품)·`hand_layer`(쥔 손)를 쓴다 —
     앞뒤 순서는 원래 그림대로 몸 → 소품 → 손. 소품 뒤 빈칸은 확산 채우기 말고 옆 픽셀 늘리기(소품이 앞에서 덮는다). 층 나누기는 `prop_split.py --spec <캐릭터>/source~/idle/{소품}_split.json`(좌표 spec). Priest는 좌표로 나눴다(`Priest/source~/idle/staff_split.json`, Codex 지우기 편집은 용량 부족으로 실패).
   - AI Idle 8장의 눈 감은 장이 둘 이상이어도 깜빡임은 한 번(`blink_at`). 1초 루프에 두 번은 잦다.
   - 폭: `knee_amp`(엉덩이 하강, 키 대비), `knee_ratio`·`knee_forward`(무릎이 따라 내려가는/앞으로 나오는 비율), `breath_amp`(가슴·어깨)
   - `head_lag`(머리가 몇 프레임 늦는지), `hip`(이 위는 한 덩어리), `face`(무릎이 나오는 방향), `blink_at`
   - `moves`: 부위별로 무엇이 어떻게 움직이는지 사람이 읽는 설명(머리카락·망토·무기가 따로 흔들리는지 포함)
   - `source`·`base`·`blink`: 몸으로 쓸 AI 프레임과 눈 감은 프레임
   예: Knight(중갑, 검을 내려 듦) = knee 2% + 호흡 0.4%, 머리카락·망토·검은 몸과 함께만. Archer는 AI 8장(`method: ai_sheet`).
   다음 캐릭터가 Knight와 다르게 움직여야 하는데(가벼운 체격은 더 통통 튀게, 거대한 캐릭터는 더 느리고 작게, 긴 머리·망토가 따로 흔들려야 함 등)
   지금 도구로 안 되면 기능을 추가한다 — 머리카락·망토의 지연 흔들림은 아직 없다.
3. `python $SK/procedural_idle.py --character <캐릭터> --out SpriteRegen/<캐릭터>_Idle/procN/result.png`
   (인자를 주면 character.json보다 우선. 폭을 바꿔 보고 사용자가 확정하면 character.json에 적는다)
4. `process_sprite_sheet.py --input <위 결과> --name <캐릭터>_Idle_vN --cols 6 --rows 4 --inbetween 0 --fps 24` 후 Apply.
5. 처음 캐릭터면 적용한 Idle을 기준 시트로 지정한다: `sheet_check.py set-reference Assets/_/Spirte/<캐릭터>/<캐릭터>_Idle_v1.png --keep-height --chin`.
   `--chin`은 턱~발바닥(`ref_chin_to_sole`)으로 이후 시트 크기를 맞추게 한다 — 다리를 편 키는 바닥까지 내려온 무기를 발로 잡아 틀린 적이 있다(Knight Skill2: 게임 내 81%).

## F. 새 동작 (원본 시트 없이) — Hit·Skill·Dead

글로만 지시하면 팔이 꼬이고(Knight Skill1 4회), 한 장에 8~12장을 몰아 그리면 칸이 좁아 칼끝이 잘리고 비율이 무너졌다.
이 순서로 한다 (Knight Skill1 확정본, 2026-10-15):

시작 전에: 생성은 **사용자가 시작하라고 한 동작만**, 사용자가 정한 순서로 한다(정의가 확정돼 있어도 묻는다 — Priest 2026-10-16 "아직 작업시작하지마셈").
0절(기준 시트·`design.required`)도 이 시점에 확인한다. 인계 상태는 `references/roadmap.md` 마지막 절.

0. **디렉팅** — "새 캐릭터 전체 순서"의 관문 3. 사용자에게 이 동작의 디렉팅을 받아 `character.json` `actions.{액션}`에 적는다. 없으면 `generate_action.py`가 멈춘다.
1. **정의** — 동작 설명이 모호하면 G부터. 정의는 `references/motion.md` 3절 형식(구간·포즈·금지·검사)으로 쓰고 `actions.{액션}.definition`에 남긴다.
2. **레퍼런스** — 무료(CC0) 자료를 먼저 찾는다(motion.md 4절). 자세만 회색 실루엣으로 바꿔 `SpriteRegen/_refs/`에 두고, 후보를 보여 사용자가 고른다.
3. **spec 작성** — `SpriteRegen/_specs/{캐릭터}_{액션}.json`: title, physics(정의를 영어로), poses(4의 배수 — 8 또는 12), reference, rules.
   포즈 문장에 "더 밀어붙인다"처럼 다시 앞으로 가는 말을 쓰지 않는다 — 모델이 재찌르기로 그렸다.
   rules에 거의 항상 넣는 것 (빠지면 실제로 깨졌다):
   - 무기 연속성: "the sword stays in her RIGHT hand, pointing down, moving only a little from frame to frame" — 없으면 칼이 장마다 순간이동했다(Knight Hit).
     **손은 캐릭터마다 다르다** — `character.json` `design.required`에 적힌 손을 쓴다(Priest는 좌우 반전으로 지팡이 = LEFT hand, 책 = RIGHT hand). 예문을 그대로 옮기지 않는다
   - rules는 4장마다 같은 문장이 들어간다 — "frames 3-6"처럼 전체 번호를 쓰지 말고 포즈 이름으로 적는다(장 안 번호와 섞인다)
   - 무기를 머리 위로 드는 동작은 spec에 `"figure_scale": 0.72` — 크기 안내 그림의 위 여백(기본 0.86이면 머리 위 지팡이가 칸에 안 들어간다)
   - 발: "the back foot / both feet stay at exactly the same spot" — 없으면 장마다 보폭이 달라 좌우로 흔들렸다(Skill2 174px)
   - 시점: "3/4 view facing right like #1, never toward the camera" — 없으면 일부 장이 정면을 봤다(Skill3)
   - 감정이 있는 동작은 표정을 명시: Hit = "PAIN … no blush" (처음 Hit가 "부끄러워하는" 지시로 만들어져 어색했다)
   - 레퍼런스가 작은 픽셀 아트나 2등신이라 실루엣으로 자세가 안 읽히면 붙이지 않는다 — 글 정의만으로 생성한다
4. **생성** — 먼저 `--dry-run`으로 모든 장의 프롬프트(`SpriteRegen/{캐릭터}_{액션}/dryrun/prompt_partN.md`)와 `character.png`(오른쪽을 보는지, 무기 손)를 확인한다.
   `python $SK/generate_action.py --character Knight --action Skill1 --spec <spec>` (백그라운드, 4장씩 3장을 이어 그림, 수십 분).
   세트를 두 개 동시에 돌려 고른다. 결과 RESULT의 `sizes`가 다르면 그 세트는 버린다.
5. **처리** — `process_sprite_sheet.py --input A B C --cols 2 --rows 6 --frames 12 --gap_counts ... --align_x <바닥에 박힌 발>`
   - `--gap_counts`: 구간별 보간 장수. 발사·타격 구간은 0, 회복은 2. 멈춤(`--hold`)은 터프한 동작에 쓰지 않는다
   - 정렬은 그 동작에서 **실제로 바닥에 붙어 있는 발**. 움직이는 발을 고정하면 몸이 앞뒤로 흔들린다
6. **검사** — `motion_check.py once`(찌르기: 한 번만), `smoothness.py`(끊김), 미리보기(칼끝·비율). 걸리면 그 원본 프레임을 빼고 다시 처리한다
   (`once_*.png`처럼 남길 프레임만 모은 시트를 만들어 `--input`).
   **보여 주기 전에 반드시 Idle 0번과 나란히 놓고** 시점(몸·얼굴이 3/4로 오른쪽을 보는지)과 크기를 본다. 새 장끼리만 비교하면 전부 같이 틀어진 것을 놓친다
   (Skill3: 8장이 모두 정면으로 돌았는데 장끼리 비교해서 놓쳤고 사용자가 찾았다). 프레임마다 피벗 세로선을 그어 좌우 흔들림도 본다.
   칼날·궤적은 흰 갑옷과 색이 같아 자동 측정이 안 된다 — 무기 위치는 눈으로 본다.
7. **비교** — `Assets/_/_Compare/`에 `BuildClipAt`으로 클립을 만들고 `AnimationCompareRecorder.Record`로 이전 것과 나란히 녹화해 사용자가 고른다.
8. **적용** — 고른 처리 설정 그대로 `_v{N+1}`로 처리 후 Apply. 정렬 발이 바뀌었으면 character.json `align_x`도 고친다.

## H. 일부 구간만 다시 그리기

사용자가 동작의 한 구간만 지적하면("칼 휘두르는 부분만 어색하다") 전체를 다시 뽑지 않는다 — 마음에 든 장면이 사라진다.
(Knight Skill3, 2026-10-15: 경례·꽂기·마무리는 원본 그대로, 회전 구간만 4번 갈아 끼웠다.)

1. 바꿀 구간만 spec으로 생성한다. 원본 시트를 `reference`로 붙이고 "frame N 직전·직후 사이를 그린다"고 쓴다. 4장이 넘으면 generate_action이 앞 장을 이어 붙인다.
   몸은 그대로 두고 손·무기만 바뀌는 동작이면 몸 기준을 Idle(character.png)로 둔다 — "똑바로 선 몸"을 따로 그려 기준으로 쓰면 그 몸이 정면으로 돌아 전부 따라갔다.
2. 잇기: `python $SK/splice_frames.py --out SpriteRegen/{캐릭터}_{액션}/splice.png 원본:4x2:1,2 새것:2x2:1,2,3,4 원본:4x2:5,6,7,8`
   - 흰 배경 결과는 자동으로 투명하게 바꾼다. 크기는 무기를 깎은 몸 실루엣을 원본 프레임에 겹쳐 맞춘다(`--fit silhouette`, 기본). 얼굴 기준(`--fit face`)은 칼·궤적이 얼굴을 가리면 틀린다.
   - 같은 장면을 두 번 쓰면(경례 → 회전 → 경례로 정지) 정지 박자가 생긴다.
3. `process_sprite_sheet.py --input splice.png --cols N --rows 1 --frames N --gap_counts … --hold i:초 …`
   - **도는 가는 무기 구간은 보간 0** — RIFE가 칼날을 못 따라가 중간 그림에서 칼이 사라졌다.
4. F의 6~8(Idle과 나란히 확인 → 비교 녹화 → 적용).

시도했다가 버린 것: 칼 그림 한 장을 프로그램으로 돌리기(손이 멈춰 있고 광택까지 같이 돌아 "장난감 칼"), 생성 장에서 손·칼만 떼어 고정 몸에 얹기(장마다 정렬이 어긋나 이중으로 보임).
무기를 지운 깨끗한 몸이 필요하면 손으로 메우지 말고 Codex에 "같은 그림에서 칼만 지워라"로 받는다(원본과 IoU 0.98) — 확산 채우기는 뺨·머리카락에 네모 얼룩이 남았다.

## G. 모호한 디렉팅

사용자가 정량적이지 않은 말로 지시하거나("터프하게", "스무드해", "AI 같아") 원인을 못 짚는 피드백("어색한데 뭐라 할지 모르겠다")을 하면
**바로 생성하거나 고치지 않는다.** `references/motion.md` 1절 절차를 따른다:
사전 확인 → (없으면) 애니메이션 원칙·게임 공격 구조·신체 역학·레퍼런스를 WebSearch로 동시에 조사 → 측정 가능한 정의로 번역해 출처와 함께 사용자 확인 →
비교 영상으로 고르게 → 확정되면 motion.md 사전에 추가.
"어색하다"만 들었으면 원인 후보마다 한 버전씩 만들어 비교 영상으로 보여 준다 — 사용자에게 설명을 요구하지 않는다.
조사·레퍼런스 수집은 서브에이전트(general-purpose, 백그라운드)에 맡기고 그동안 다른 작업을 한다. 받은 자료는 `SpriteRegen/_refs/{주제}_candidates/`에 출처·라이선스와 함께 두게 한다.
"의장대처럼", "맞고 아파하는" 같은 실제 동작 비유는 실제 동작부터 조사한다(교범·공공저작물 사진·영상) — 짐작으로 그린 "칼 휘두르기"는 두 번 다 퇴짜였다.
결정이 사용자 몫이면(회전 면처럼 실제와 2D 가독성이 갈릴 때) 미리보기 그림을 붙여 묻는다.
지표가 합격이어도 사용자 판단이 우선이다.

