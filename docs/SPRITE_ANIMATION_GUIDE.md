# 스프라이트 시트 → 애니메이션 파이프라인

AI가 만든 스프라이트 시트는 셀 경계를 지키지 않는다. 발이 아래 행으로, 활과 머리카락이 옆 셀로 넘어가고,
프레임마다 캐릭터 위치와 크기가 조금씩 다르다. 이 파이프라인은 그걸 정렬된 아틀라스로 바꾸고
Unity 클립과 컨트롤러까지 연결한다.

```
원본 시트 ──(1) scripts/process_sprite_sheet.py──▶ Assets/_/Spirte/{캐릭터}/{이름}.png + .json
                                                   Temp/SpriteAnimationPipeline/{이름}_preview.png
          ──(2) SpriteAnimationPipeline.Apply──▶ Assets/_/_Anim/{캐릭터}/{이름}.anim
                                                   Assets/_/_AnimCon/{캐릭터}.controller  (상태 = 액션)
```

**셀 크기, pivot, fps, loop는 (1)이 정해서 매니페스트(.json)에 쓴다. (2)는 그것만 읽는다.**
같은 값을 두 곳에서 정하지 않는다. 액션별 규칙은 `process_sprite_sheet.py`의 `ACTIONS` 한 곳에 있다.

## 사용법

```bash
# 0) 측정만 (에셋을 쓰지 않음). 미리보기를 열어 분할선과 정렬을 확인한다
python scripts/process_sprite_sheet.py --input "원본.png" --name Archer_Dead_v1 --analyze

# 1) 전처리
python scripts/process_sprite_sheet.py --input "원본.png" --name Archer_Dead_v1

# 2) Unity 적용 — 1)의 마지막 줄 RESULT의 "next"에 그대로 나온다
unity cmd eval 'AssetDatabase.Refresh(); return SpriteAnimationPipeline.Apply("Assets/_/Spirte/Archer/Archer_Dead_v1.png");'
```

에디터에서는 시트를 선택하고 `Tools > Sprite Animation > Apply Selected Sheets`로 실행한다.

### 종료 코드

| 단계 | 성공 | 실패 |
|---|---|---|
| Python | 0, 마지막 줄 `RESULT {"ok": true, ...}` | 1, `RESULT {"ok": false, "error": ...}` |
| Unity `Apply` | 결과 문자열을 반환 (eval 종료 코드 0) | 예외 (eval 종료 코드 ≠ 0) |

경고(원본에서 이미 잘린 프레임, 실제로 겹친 프레임 등)가 있어도 실패로 처리하지 않는다.
경고는 `RESULT`의 `warnings`, 매니페스트, `Apply` 반환 문자열에 남는다.

## 이름 규칙

```
{캐릭터}_{액션}_v{N}        예: Archer_Skill1_v1
```

- 캐릭터: 대문자로 시작하는 영숫자
- 액션: `Idle` `Hit` `Skill1`~`Skill9` `Dead`
- 버전: 소문자 `v` + 정수

규칙에 맞지 않는 이름은 Python 단계에서 거부한다. 스프라이트 이름은 `{이름}_{프레임번호}`다.

## 액션별 기본값

| 액션 | fps | loop | 가로 정렬 | 세로 정렬 |
|---|---|---|---|---|
| Idle | 8 | ✓ | feet | ground |
| Hit | 10 | | feet | ground |
| Skill1~9 | 10 | | feet | ground |
| Dead | 8 | | anchor | ground |

- **feet**: 프레임마다 발 중심을 pivot에 맞춘다. 제자리 모션에서 AI가 만든 좌우 흔들림을 없앤다.
- **anchor**: 기준 프레임(`--anchor`, 기본 0)의 발 중심 하나로 모든 프레임을 같은 양만큼 옮긴다. 원본에 그려진 이동을 보존한다.
- **ground**: 프레임마다 최하단을 접지선에 맞춘다. 서 있든 쓰러지든 몸 어딘가는 땅에 닿아 있다.
- **anchor(세로)**: 점프처럼 공중에 뜨는 모션에 쓴다. `--align_y anchor`

모든 값은 CLI로 덮어쓸 수 있다: `--fps` `--loop` `--align_x` `--align_y` `--anchor`

## 자동으로 처리하는 것

| 문제 | 처리 |
|---|---|
| 발이 아래 행으로 넘어감 | 행 경계를 직선 대신 **가로 seam**으로 찾는다. 투명한 곳을 따라 발 아래로 돌아 나간다 |
| 활/머리카락이 옆 셀로 넘어감 | 열 경계도 **세로 seam**으로 찾는다 |
| 시트마다 캐릭터 크기가 다름 | `Spirte/{캐릭터}/{캐릭터}.character.json`의 `ref_height` ÷ 기준 프레임의 **다리를 편 키**로 균일 스케일. 세로 키만 쓰면 다리를 넓게 벌린 시트일수록 키가 낮게 재져 더 확대된다(궁수 시트에서 1~3.5%). 기준 시트는 `sheet_check.py set-reference`로 지정하고, 파일이 없으면 처음 처리한 시트가 기준이 된다 → **Idle을 먼저 처리한다** |
| 셀이 좁아 잘림 | 셀 크기와 접지선은 전 프레임이 들어가도록 자동 결정. 직접 지정해서 모자라면 경고 |
| pivot | 가로 0.5(발 중심), 세로는 접지선. 클립마다 셀 크기가 달라도 캐릭터는 같은 곳에 선다 |
| 2048px 초과 아틀라스 | `maxTextureSize`를 올려서 조용히 축소되지 않게 한다 |
| 작은 부스러기 | 면적 80px 미만 연결 요소 제거 (`--keep_noise`로 끔) |

## 다시 적용해도 참조가 깨지지 않는다

- 기존 `.anim`은 지우지 않고 내용만 바꾼다 → GUID 유지
- 다시 슬라이스할 때 같은 프레임 번호는 같은 spriteID를 쓴다 → 프리팹과 씬의 스프라이트 참조 유지
- 시트가 캐릭터 폴더 밖에 있으면 `Apply`가 `MoveAsset`으로 옮긴다 (GUID 유지)
- 새 버전을 적용하면 같은 캐릭터·액션의 낮은 버전 시트(+매니페스트)와 클립을 각 폴더의 `prev/`로 옮긴다 (삭제하지 않음, GUID 유지)

## 미리보기 읽는 법

`Temp/SpriteAnimationPipeline/{이름}_preview.png` (에디터를 닫으면 지워진다)

1. **원본 + 분할선**: 분홍 = 행 경계, 하늘 = 열 경계. 신체를 가로지르면 분할이 잘못된 것이다
2. **아틀라스**: 빨강 = 접지선, 파랑 = pivot. 발이 빨간 선 위에 서 있어야 한다
3. **겹쳐보기**: 모든 프레임을 반투명으로 겹친 것. 발이 번져 보이면 그 방향으로 흔들린다는 뜻이다

## 한계

- 원본 시트 가장자리에서 이미 잘린 부분은 복구할 수 없다 (경고만 한다)
- 두 캐릭터가 실제로 겹쳐 그려졌으면 seam도 어딘가를 자를 수밖에 없다 (경고)
- 기준 프레임이 웅크린 자세면 키로 잰 스케일이 커진다. 미리보기에서 체급을 비교하고 필요하면 `--scale`로 지정한다
- 클립 간 전이(transition)는 만들지 않는다. 상태만 만든다
