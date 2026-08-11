# AGENT.md

이 저장소에서 작업하는 사람과 에이전트가 함께 지키는 규칙 문서.
대부분은 일반론이 아니라 **이 프로젝트에서 실제로 터진 버그에서 나온 규칙**이다.

---

## 0. 이 문서의 운용

### 모든 규칙은 예외를 가질 수 있다

이 문서의 어떤 항목도 절대 규칙이 아니다.
**최적화, 유지보수성, 확장성 등 합당한 이유가 있으면 예외로 처리할 수 있다.**

다만 예외에는 대가가 따르므로, 다음을 지킨다.

- **어기기 전에 이유를 말한다.** 사후 통보가 아니라 사전 합의.
- **왜 예외인지를 코드 주석에 남긴다.** 나중에 읽는 사람이 "실수인가 의도인가"를 판단할 수 있어야 한다.
- 같은 예외가 **세 번 이상 반복되면** 그건 예외가 아니라 규칙이 틀린 것이다. 규칙을 고친다.

규칙은 생각을 대체하려고 있는 게 아니라, **이미 한 번 물린 곳을 다시 물리지 않으려고** 있다.
근거가 사라진 규칙은 지킬 이유도 없다.

### 그 외

- 작업 중 **컨벤션으로 굳힐 만한 판단이 나오면 사용자에게 제안한다.** 임의로 이 문서에 추가하지 않는다.
- 규칙과 실제 코드가 어긋나 있으면 그것부터 보고한다.

---

## 1. 프로젝트 구조

```
Assets/_/_Scripts/InGame/
├── FSM/            상태 머신과 상태 클래스
├── Puzzle/         3매치 퍼즐 (Model / View / Manager)
├── Action/         전투 액션
├── UI/
└── Util/           BaseManager, GameManager
Assets/_/_SO/       ScriptableObject 에셋
docs/               이 문서
```

### 3층 분리

| 층 | 예 | 규칙 |
|---|---|---|
| **Model** | `PuzzleModel` | `MonoBehaviour` 아님. Unity API는 `Vector2Int` 정도만. 순수 로직과 데이터 |
| **View** | `PuzzleMatrixView`, `PuzzleView` | `MonoBehaviour`. 표현만. 게임 규칙을 판단하지 않는다 |
| **Manager** | `PuzzleManager` | 조율과 상태 전환. Model과 View를 잇는 유일한 지점 |

View가 규칙을 판단하기 시작하면 Model과 두 벌이 되고, 반드시 어긋난다.

---

## 2. 네이밍

| 대상 | 규칙 | 예 |
|---|---|---|
| enum | `E` 접두사 | `EGameState`, `EPuzzleState`, `EBubbleHighlight` |
| 인터페이스 | `I` 접두사 | `IState`, `IPoolable<T>`, `IReportableState` |
| ScriptableObject | `SO` 접미사 | `BubbleSO` |
| **FSM 상태 클래스** | **`{Owner}{State}State`** | `PuzzleManager` + `EPuzzleState.PuzzleAction` → `PuzzlePuzzleActionState` |

### FSM 상태 이름은 강제 규칙이다

`BaseStateMachine.AutoInsertStates()`가 리플렉션으로 이름을 맞춰 자동 등록한다.
**이름이 틀리면 컴파일은 되고 경고 한 줄만 뜬 뒤 조용히 동작하지 않는다.**
상태를 추가할 때는 enum 값과 클래스 이름을 반드시 함께 맞춘다.

---

## 3. 핵심 패턴 — 영수증(Receipt)

모델은 상태를 **즉시** 바꾸고, **무슨 일이 있었는지 기록**을 반환한다.
뷰는 그 기록만 보고 나중에 연출한다.

```
MoveReceipt
├── SwapMoves   List<MoveStep>    유저 스왑 (롤백이면 4개)
├── ChainSteps  List<ChainStep>   연쇄 1회분씩 = [Matches, GravityMoves, RefillMoves]
└── ShuffleMoves List<MoveStep>   데드락 해소 셔플
```

### 규칙: 영수증에는 좌표가 아니라 객체 참조와 from/to를 함께 담는다

모델과 뷰는 **시간이 어긋나 있다.** 뷰가 연출할 시점에 모델은 이미 여러 단계 앞서 있다.
그래서 **"나중에 현재 상태를 다시 조회"하면 반드시 틀린 값을 얻는다.**

이 규칙을 어겨서 같은 원인으로 세 번 물렸다.

- `Swap()`이 `SwapData()` **뒤에** `bubbles[]`를 다시 읽음 → Data와 from/to가 엇갈려 **이동거리 0짜리 트윈**
- 뷰가 연출 시점에 좌표로 버블을 조회 → 이미 연쇄가 끝난 **엉뚱한 버블**
- `ShuffleBoard`가 `CanAnyMatchExist()` **뒤에** `Bubble.Pos`를 읽음 → `SetBubbleAt`이 Pos를 덮어써서 **출발지 소실**

> 상태를 바꾸는 함수를 부르기 **전에** 필요한 참조를 확보하라.

---

## 4. 오브젝트 풀링

- `IPoolable<T>`: `Initialize(returnAction)`로 반납 경로를 주입받고 `ReturnToPool()`로 스스로 돌아간다.
- **반납 시점 = 연출 종료 시점.** 모델 연산 중에 풀로 돌려보내면 뷰가 연출할 대상이 사라진다.
- **반납 주체는 한 곳.** 데이터와 뷰의 반납 창구가 둘이면 반드시 한쪽이 샌다.
  현재는 `Bubble.ReturnToPool()` → `PuzzlePool` 콜백 → `PuzzleManager.RemoveAtMatrix()` → `PuzzleMatrixView.ReleaseView()` 한 줄기.
- 풀에서 꺼낼 때 **변형(scale/rotation)과 트윈 잔재를 초기화**한다. `DOScale(0)`으로 사라진 뷰가 그대로 재사용되면 투명 오브젝트가 된다.

---

## 5. 판정 규칙은 한 곳에만 둔다

**같은 질문에 답하는 함수를 두 개 만들지 않는다.**

`CheckInitialMatch`(직선 3개만 검사)와 `GetConnectedBubbles`(4방향 연결)가 서로 다른 규칙이었다.
결과는 **시작하자마자 "터지지 않는 매치"가 보드에 박힌 채로 시작.**
지금은 둘 다 `GetLineMatchesAt` 하나를 쓴다.

### 현재 매치 규칙

**가로 또는 세로 직선 3개 이상만 매치.** ㄱ/ㄴ자 3연결은 매치가 아니다.
단, 가로 런과 세로 런이 각각 3개 이상이면서 한 칸을 공유하는 T/L자는 양쪽 모두 터진다.

---

## 6. 데이터 규칙 — 판정 키와 시각 키는 1:1

매치 판정은 `BubbleSO.SOName`, 유저 인식은 `(bubbleColor, bubbleImage)`다.
**둘이 어긋나면 게임이 거짓말을 한다.**

실제로 `T_B_3`와 `T_C_3`가 같은 색·같은 스프라이트라서, 화면상 동일한 버블 3개가 나란히 있는데도 터지지 않았다.

> 겉모습이 같은데 `SOName`이 다른 조합을 만들지 않는다.

---

## 7. 연출 (DOTween)

**연출은 특별한 사유가 없는 한 DOTween으로 통일한다.**
코루틴, `Animator`, `Update` 수동 보간을 섞지 않는다. 다른 수단을 써야 한다면 이유를 먼저 밝힌다.

### DOTween 사용 규칙

**시작값은 `Startup()`에서 캡처되고, `OnStart` 콜백은 그 다음에 불린다.**

```csharp
// 위치/스케일은 트윈 "생성 전"에 확정
view.transform.position = spawnPos;
view.transform.localScale = Vector3.one;

// 시작값과 무관한 것(화면 노출)만 OnStart로 미룬다
seq.Join(view.transform.DOMove(target, dur)
    .OnStart(() => view.gameObject.SetActive(true)));
```

`OnStart` 안에서 위치를 잡으면 이미 늦다. DOTween이 그 직전 위치를 시작값으로 확정한 뒤다.

**비활성 오브젝트의 트윈은 죽지 않는다.** 보이지 않을 뿐 정상적으로 돈다.
DOTween이 자동으로 죽이는 건 대상이 **Destroy되어 null이 됐을 때**뿐이다.

**반복 애니메이션은 트윈 루프 대신 `Time.time`으로 계산한다.**
`SetLoops(-1, Yoyo)`는 상태가 바뀔 때 죽고 다시 처음부터 시작해서, 그 오브젝트만 박자가 어긋난다.

```csharp
float t = 0.5f * (1f - Mathf.Cos(Time.time * Mathf.PI / duration));
```

**이동 시간은 거리에 비례시킨다.** 1칸과 6칸이 같은 시간에 떨어지면 속도가 달라 보인다.

**연출이 끝나면 모델 기준으로 스냅한다.** (`ReconcileViewsToModel`)
프레임 스파이크로 트윈 구간이 통째로 스킵되면 `OnStart`가 발화하지 않고, `SetActive(true)`를 거기서 하던 오브젝트는 영구히 비활성으로 남는다. 일시적 글리치가 아니라 되돌릴 수 없는 손상이다.

**매직넘버는 `[SerializeField]`로 뺀다.** 연출 시간과 강도는 코드에 박지 않는다.

---

## 8. FSM 완료 보고

`ReceiveCompleteSignal()` → `readyCount / totalTargetCount` → `OnAllTasksComplete()` 흐름.

> **상태에 들어갔으면 나오는 길이 반드시 하나 있어야 한다.**

early return 하기 전에 **"이 상태를 누가 끝내주나"**를 확인한다.
`PlayPuzzleAnimateSequence`가 영수증이 없을 때 그냥 `return`하면 `readyCount 0/1`에서 영구 정지한다.
지금은 즉시 완수 보고로 흘려보낸다.

---

## 9. 디버깅 — 값이 아니라 불변식을 찍는다

흐름 추적 로그를 잔뜩 심었을 때는 원인을 못 찾았다.
**불변식 검사를 넣자 한 줄로 나왔다** — `현재 성립중인 매치=6개`.

> 값을 나열하지 말고, **불변식을 적고 위반을 찍어라.**

### 이 프로젝트의 불변식

| 불변식 | 깨지면 생기는 일 |
|---|---|
| 연쇄 종료 후 `GetAllMatches().Count == 0` | 안 터지는 매치가 보드에 박힘 |
| 항상 `CanAnyMatchExist() == true` | 데드락 |
| `bubbles[x][y].Pos == (x, y)` | 클릭하면 엉뚱한 칸이 스왑됨 |
| 같은 `Bubble` 인스턴스가 보드에 두 번 없음 | 풀 이중 반납 |
| 연출 종료 시 뷰 좌표 `== GetWorldPos(Bubble.Pos)` | 화면과 모델 불일치 |
| `dataViewDict.Count == Size * Size` | 뷰 누수 |

### 로그 정책

- 상시 로그는 **실제 이상 상황에서만** 뜨게 한다. 정상 흐름을 매 프레임 찍지 않는다.
- 조사용 로그와 감사(audit) 코드는 원인을 잡은 뒤 **제거한다.**
- 남길 가치가 있는 건 "무슨 값이었나"가 아니라 "무엇이 깨졌나"다.

---

## 10. 구조를 언제 도입할지

**ScriptableObject 설정 층은 셋 중 하나가 실제로 생겼을 때만 도입한다.**

1. 프리셋을 여러 개 두고 비교해야 한다
2. 프로그래머가 아닌 사람이 튜닝한다
3. 런타임에 교체해야 한다

그 전까지는 `[SerializeField]`로 충분하다. 간접 층이 하나 늘면 다음 버그를 쫓을 때 확인할 지점이 하나 늘어난다.

값들을 `[Serializable]` 클래스로 **한 덩어리로 묶어두면** 나중에 SO로 옮기는 게 한 줄이다.

### BM이 붙을 때의 분리 축

**판매되는 에셋은 게임 규칙에 영향을 주면 안 된다.**

| 구분 | 내용 |
|---|---|
| Cosmetic (판매 가능) | 스프라이트, 색, 파티클, 사운드 |
| Gameplay (고정) | 매치 규칙, 보드 크기, 연출 타이밍, 스폰 확률 |

현재 `BubbleSO`는 `bubbleImage`/`bubbleColor`(코스메틱)와 `action`/`value`/`addPerBubble`(게임플레이)을 한 클래스에 들고 있다. 스킨을 붙일 때 첫 작업은 여기를 가르는 것이다.

---

## 11. Git

- 커밋 메시지는 한국어. 제목 한 줄 + 빈 줄 + 본문에 **왜** 그렇게 했는지.
- 버그 수정은 증상이 아니라 **원인**을 적는다.
