# 3MatchCCG - 게임 기획서 (Game Design Document)

## 1. 게임 정체성 및 장르 (Identity & Genre)

- **핵심 장르**: 미소녀 카드 수집형 게임 (CCG, Collectible Card Game) + 3-Match 퍼즐
- **게임 개요**:
  - 서브컬처 미소녀 캐릭터 카드를 수집(Collectible) 및 육성하여 자신만의 덱을 구성하고, 3-Match 퍼즐 조작을 통해 전투 및 스킬을 구동하는 수집형 퍼즐 CCG 게임.
  - **1차 MVP 스코프 외 항목**: 카드 가차/수집 UI, 카드 레벨업/육성 시스템은 1차 코어 전투 완성 후 구현.

---

## 2. 덱 및 캐릭터 구조 (Deck & Character System)

### 2.1 덱 편성
- **덱 구성**: 총 **3명의 캐릭터 카드**로 1개의 전투 덱을 편성한다.

### 2.2 캐릭터 스킬 및 시각 매핑 규칙 (AGENT.md §6 준수)
- **캐릭터별 스킬 수**: 캐릭터 1명당 **3개의 전용 스킬**을 보유한다. (덱 전체 총 9개 스킬)
- **1 스킬 ↔ 1 버블 매핑**: 캐릭터의 각 스킬은 인게임의 **전용 버블 1종류와 1:1로 대응**한다.
- **시각 매핑 규칙 (Single Source of Truth)**:
  - **캐릭터 1인**: 고유 메인 칼라(`CharacterSO.mainColor`)가 단일 원천이다 (`BubbleSO.bubbleColor` 필드 제거).
    - 캐릭터 A = Red 계열 (`#FF4444`)
    - 캐릭터 B = Green 계열 (`#44CC44`)
    - 캐릭터 C = Blue 계열 (`#4488FF`)
  - **스킬 3종**: 캐릭터 색상 바탕 위 고유 문양/아이콘(Icon 1, 2, 3)으로 구별.
- **스킬(버블) 가중치 및 위협도 배수**: 
  - `BubbleSO.spawnWeight` 필드를 통해 버블 생성 가중치를 부여한다.
  - `BubbleSO.threatMultiplier` 필드(기본값 1.0)를 통해 스킬별 위협도 누적 가중치를 부여한다.

### 2.3 캐릭터 및 덱 데이터 구조 명세 (Character & Deck SO)
- **`CharacterSO` 데이터 구조**:
  - `characterName`, `characterImage`, `mainColor` (시각 및 메타 정보)
  - `MaxHP`, `MaxShield`, `BaseThreat` (캐릭터 고유 기본 스탯)
  - `skills`: 해당 캐릭터의 전용 `BubbleSO` 3개 배열
- **덱(`DeckSO`) 데이터 구조**:
  - `CharacterSO` 3개 리스트로 1개의 플레이어 전투 덱을 편성한다.
- **계층 분리 및 시전자(`caster`) 역참조 규칙 (AGENT.md §1 준수)**:
  - `PuzzleManager`는 정적 파이프(`DeckSO` ↔ `BubbleSO`)와 스포닝 비율만 다루며, `Actor` 인스턴스를 직접 참조하지 않는다.
  - `ActionManager`가 전투 시작 시 `CharacterSO` ↔ `Actor` 런타임 매핑을 소유하고, 스킬 레시피 실행 시 `BubbleSO` 스냅샷을 바탕으로 시전자 `PlayerActor`를 역추적하여 `FindTarget(caster)`에 전달한다.

### 2.4 캐릭터 3인 기본 스탯 및 9종 스킬 밸런스 카탈로그
- **캐릭터 A (딜러 - Red)**:
  - 기본 스탯: `MaxHP`: 400, `MaxShield`: 100, `BaseThreat`: 100
  - Skill A1 (버블 A1): `AttackAction` / `LowestHPEnemy` / value: 20 / spawnWeight: 1.0 / threatMultiplier: 1.0
  - Skill A2 (버블 A2): `AttackAction` / `HighestThreatEnemy` / value: 30 / spawnWeight: 1.0 / threatMultiplier: 1.0
  - Skill A3 (버블 A3): `AttackAction` / `AllEnemies` / value: 15 / spawnWeight: 1.0 / threatMultiplier: 1.0
- **캐릭터 B (탱커 - Green)**:
  - 기본 스탯: `MaxHP`: 600, `MaxShield`: 200, `BaseThreat`: 300
  - Skill B1 (버블 B1): `DefenseAction` / `LowestHPAlly` / value: 25 / spawnWeight: 1.0 / threatMultiplier: 1.5
  - Skill B2 (버블 B2): `DefenseAction` / `AllAllies` / value: 15 / spawnWeight: 1.0 / threatMultiplier: 1.5
  - Skill B3 (버블 B3): `AttackAction` (도발/어그로) / `HighestThreatEnemy` / value: 10 / spawnWeight: 1.0 / **threatMultiplier: 5.0** (고위협도 어그로 유지)
- **캐릭터 C (힐러/지원 - Blue)**:
  - 기본 스탯: `MaxHP`: 350, `MaxShield`: 50, `BaseThreat`: 50
  - Skill C1 (버블 C1): `HealAction` / `LowestHPAlly` / value: 20 / spawnWeight: 1.0 / threatMultiplier: 1.0
  - Skill C2 (버블 C2): `HealAction` / `AllAllies` / value: 12 / spawnWeight: 1.0 / threatMultiplier: 1.0
  - Skill C3 (버블 C3): `DefenseAction` / `AllAllies` / value: 10 / spawnWeight: 1.0 / threatMultiplier: 1.0

---

## 3. 인게임 퍼즐 보드 메커니즘 (Board & Spawning)

### 3.1 보드 규격
- **보드 크기**: **8 x 8** 격자 보드 (`PuzzleManager.size = 8`).

### 3.2 2단계 추첨 방식 (2-Tier Weighted Spawn)
인게임 퍼즐 보드에 생성되는 버블은 **`3 : 3 : 3 : 1`** 비율로 2단계 추첨된다.

1. **1단계 추첨 (캐릭터 블록 선택)**: 
   - 캐릭터 1 (30%) / 캐릭터 2 (30%) / 캐릭터 3 (30%) / 공용 특수 버블 (10%)
2. **2단계 추첨 (스킬 버블 선택)**:
   - 선택된 캐릭터 내부 3개 스킬의 `spawnWeight` 비율에 따라 최종 버블 선택.

#### 3.2.1 캐릭터 사망 시 보드 & 스포닝 재정규화 규칙
- **스포닝 제외 및 재정규화**: 
  - 특수 버블(`T_O`) 10% 지분 고정.
  - 캐릭터 1인 사망 시, 남은 생존 캐릭터 2인 각 45% + 특수 버블 10% = 100% 비율로 재정규화하며, 45% 내에서는 해당 생존 캐릭터의 3개 스킬 `spawnWeight` 비율로 최종 추첨한다.
  - **적용 시점**: 사망 발생 후 **다음 스왑(Swap) 조작부터 적용**된다 (현재 조작으로 진행 중인 연쇄의 리필 버블은 이미 불변 영수증으로 확정된 상태임 - AGENT.md §3 준수).
  - **아키텍처 규칙 (AGENT.md §1 계층 분리 준수)**: `ActionManager`가 `Actor` 사망 이벤트를 처리하여 `CharacterSO` 단위 사망 이벤트(`OnCharacterDied`)를 재발행하고, `PuzzleManager`가 이를 구독하여 갱신된 비율을 순수 클래스인 `PuzzleFactory`에 주입한다.
- **보드 잔여 버블 처리 & 사망 무효화 판정**: 
  - 이미 보드에 배치되어 있던 사망 캐릭터의 버블은 3매치 조작 및 연쇄 팝(터짐)은 가능하지만, **스킬 효과는 발동하지 않고 단순 파괴 연출만 수행**한다.
  - **사망 스킬 무효화 판정 시점**: 레시피 작성 시점이 아닌 **스킬 실행 시점(시퀀스 콜백 발화 시점)**에 판단하여, 연쇄 진행 중 중간 사망 발생 시에도 안전하게 무효화한다.
- **시각적 구별**: 사망 이벤트 발생 시 보드에 남아 있는 해당 사망 캐릭터의 버블은 화면에서 즉시 **회색조(Grayscale)** 시각 효과를 적용한다.
- **부활 불가 규칙**: 전투 중 한번 사망한 캐릭터는 영구 사망 처리되며, 부활 메커니즘은 존재하지 않는다.

### 3.3 공용 특수 버블 (`T_O`) 규칙
- **설정 방식 & 슬롯**: T_O 특수 버블은 **전용 1개 슬롯** (10% 스포닝 지분)을 사용한다.
- **T_O 스킬 효과 및 수치 연산 공식**:
  - **증폭 배율**: 개수와 무관하게 고정 **1.2배 증폭** (동일 스왑 퍼즐 연쇄 조작 구간 내 2개 이상 파괴 시 합연산 1.4배, 최대 상한 2.0배).
  - **회복량**: `50 × matchCount` (1버블당 50 기본 수치 공식을 따름). 체력 비율이 가장 낮은 아군 1인 회복.
- **지속 범위**: 증폭 효과는 플레이어가 퍼즐을 조작하여 발생한 **해당 1회 스왑(MoveReceipt 전체) 퍼즐 연쇄 조작 구간** 동안 유지된다 (`PuzzleWaitState` 복귀 시 리셋).
- **시전자(Caster) 자동 지정**: T_O 버블 발동 시 타겟팅 연산을 위한 시전자(`caster`)는 **현재 생존 아군 캐릭터 중 `BaseThreat`가 가장 높은 캐릭터**로 자동 지정된다.

---

## 4. 실시간 전투 및 엔티티 메커니즘 (Real-time Combat & Actor Mechanics)

### 4.1 엔티티(Actor) 구조 및 스탯
- **대상**: 플레이어 덱 3인 캐릭터 + 적 NPC 전원 `Actor` 상속 구조 사용.
- **소속 팀 구별 (`ETeam`)**: `ETeam.Player` (플레이어 캐릭터 팀), `ETeam.Enemy` (적 NPC 팀).
- **주요 스탯**:
  - `MaxHP` / `CurrentHP`: 개별 체력 (플레이어 캐릭터 3인 각각 개별 HP 보유).
  - `MaxShield` / `Shield`: 캐릭터/NPC별 최대 한도(`MaxShield`)를 갖는 흡수형 방어막. 피격 시 방어막 우선 차감, 초과 데미지만 HP 차감되며 공격받아 제거되지 않는 한 무한 유지.
  - `BaseThreat` (기본 위협도): 캐릭터별 고유 상시 고정 기본 위협도.
  - `Threat` (실시간 누적 위협도): 최근 10초 유효 전투 시간(`GameTime`) 동안의 `(딜량 + 힐량 + 쉴드부여량) × threatMultiplier` 누적 수치.
  - **총 위협도 (Total Threat) 산출 공식**: `총 위협도 = BaseThreat + 실시간 누적 Threat`
    - 이를 통해 탱커 B는 기본 Baseline(`BaseThreat: 300`)과 쉴드부여/도발 스킬(`threatMultiplier: 1.5~5.0`)을 통해 딜러 A(`BaseThreat: 100`, 평균 위협도) 대비 상시 및 전투 진행 중 우위의 어그로를 안정적으로 유지한다.
- **타겟팅 생존자 전용 필터**: 사망한 대상(`IsDead == true`)은 모든 타겟팅 룰의 기본 대상 검색에서 즉시 제외된다.
- **모델 진실 및 이벤트 수치 적용 (AGENT.md §3 준수)**: 
  - 모델의 스탯(`CurrentHP`, `IsDead`) 및 이벤트(`OnHPChanged`, `OnDeath`)는 계산 및 영수증 작성 시점에 **즉시 변경 및 발화**한다.
  - UI(HP바)는 모델을 조급하게 직접 읽지 않고 영수증 타임라인(DOTween `InsertCallback`)을 순차적으로 소비하여 연출 타격 시점에 맞춰 체력바 감소를 시각화한다 (AGENT.md §3 준수).

### 4.2 적 NPC 규격 및 실시간 적 공격 제어
- **적 NPC 기본 스탯 및 수치 연산**:
  - `MaxHP`: 3,000 / `MaxShield`: 0 / 공격 주기: 3.0초
  - 기본 스킬: `AttackAction` / `HighestThreatEnemy` / value: 50
  - **적 데미지 계산**: 적 공격은 버블 매치가 없으므로 `최종 데미지 = skillValue` (50) 고정 수치를 적용한다.
  - MVP 적 스킬 정의는 당분간 `BubbleSO` 컨테이너를 재사용한다.
- **Wait 상태 적 타이머 공격**: 게임 상태가 `GameWaitState`일 때, `GameWaitState.OnUpdate()`에서 시간 기반(타이머)으로 적 NPC 공격이 발동한다. 적 NPC의 스킬 연출에 의한 시간 정지(Time Freeze)는 발생하지 않는다.
- **조작/액션 일시정지 (Time Freeze)**: 플레이어의 퍼즐 스왑 ➡️ 연쇄 연출(`GamePuzzleActionState`) 진행 동안에는 적 NPC의 공격 타이머가 완전 정지한다.
- **적 데미지 확정 시점 (모델 선확정 영수증 패턴)**: 적 스킬 발동(연출 시작) 시점에 모델에서 데미지 및 피격 결과를 영수증으로 선확정하며, 연출은 그 결과를 표현한다.
- **유효 전투 시간 시계 (`GameTime`)**: 적 공격 타이머 및 위협도 10초 윈도우 시계는 Time Freeze 구간을 제외한 **실제 유효 전투 시간(`GameTime`)**을 공용 시계로 사용한다.

### 4.3 ScriptableObject 기반 자동 타겟팅 (ActionTarget System)
- **원칙 (AGENT.md §1, §5 준수)**: 타겟팅 로직은 기존 `ActionTarget` ScriptableObject 계층 구조를 단일 원천(Single Source of Truth)으로 유지한다.
- **시전자 상대 기준 통일**: 모든 타겟팅 로직은 **시전자(Caster) 상대 기준**으로 적용된다 (`ActionTarget.FindTarget(Actor caster)`).
  - **아군 (`caster.Team` 동일)**: 플레이어 스킬 기준 플레이어 캐릭터 3인, 적 NPC 스킬 기준 적 NPC 팀.
  - **적군 (`caster.Team` 반대)**: 플레이어 스킬 기준 적 NPC 팀, 적 NPC 스킬 기준 플레이어 캐릭터 3인.
- **계층 분리 (AGENT.md §1)**: 뷰(`PuzzleMatrixView`)는 콜백 시 ChainStep 인덱스만 전달하고, 스킬 해석 및 타깃 연산은 `PuzzleManager`와 `ActionManager`가 담당한다.
- **`ActionTarget` 에셋 및 클래스 목록 (7종 확정)**:
  - `HighestThreatEnemy`: 위협도가 가장 높은 적 대상 (적 NPC 공격의 기본 타겟팅 규칙)
  - `LowestHPAlly`: 체력 비율이 가장 낮은 아군 대상
  - `LowestHPEnemy`: 체력 비율이 가장 낮은 적 대상
  - `AllEnemies`: 적 전체 대상
  - `AllAllies`: 아군 전체 대상
  - `AllActors`: 전장 전체 (적 + 아군) 대상
  - `RandomActor`: 유효 대상 중 무작위 1인 대상

### 4.4 승패 조건 및 FSM 상태 네이밍 (Win / Loss Conditions & FSM Naming)
- **승리 조건**: 적 NPC HP <= 0 ➡️ 스테이지 클리어 (`GameEndState`)
- **패배 조건**: 플레이어 캐릭터 3인 중 **2명 사망** (생존자 1명 이하) ➡️ 게임 오버 (`GameEndState`)
- **FSM 상태 자동 등록 규칙 준수 (AGENT.md §2)**: 
  - enum 값을 `EGameState.End`로 명시하여 `GameManager`(owner = "Game")와 결합 시 상태 클래스명이 **`GameEndState`**로 정확히 일치하도록 등록한다.
  - 미사용 `EGameState.CharacterAction` 상태는 1차 MVP 스코프에서 완전 삭제.
- **연출 완주 및 전이 연기 (Overkill 방지)**: 오버킬 또는 사망 상황이 발생하더라도 수치 및 영수증은 즉시 반영하되, **승패 상태 전이는 진행 중인 퍼즐 연출 시퀀스가 완전히 종료(완주)된 뒤에 수행**한다 (뷰/오브젝트 풀 누수 및 불변식 깨짐 방지 - AGENT.md §9 준수).

### 4.5 영수증(Skill Recipe) 동시 생성 및 시퀀스 콜백 실행 규칙
- **생성 시점 및 단품 정의**:
  - `PuzzleModel.Swap()` 시점에 전체 연출 레시피(`MoveReceipt`)를 생성할 때, 각 연쇄 단계(`ChainStep`)별 **스킬 레시피(Skill Recipe)**를 동시에 작성한다.
  - **스킬 레시피 1건의 정의**: 1개의 연결된 **매치 그룹(Match Group - 직선 연결 덩어리)**을 스킬 레시피 1건으로 산정하여 독립 기록한다.
- **시퀀스 콜백 발동 규칙**: 
  - 스킬 실행은 각 `ChainStep`의 **팝 연출 직후 시퀀스 콜백(`mainSeq.AppendCallback`)으로 발동하며, FSM 상태 전이를 동반하지 않는다.**
  - 뷰(`PuzzleMatrixView`)는 팝 완료 시점에 `ChainStep` 인덱스를 콜백으로 전달하고, `PuzzleManager`가 레시피를 소비하여 `ActionManager`로 전달/실행한다.
- **선(先)배치 실행 규칙**: 하나의 `ChainStep` 내에 이후 스킬에 영향을 주는 효과(증폭/버프 등)가 포함된 경우, **해당 레시피 생성 시 반드시 레시피의 가장 앞(0번 인덱스)에 우선 담아 선발동**하도록 보장한다.
- **기록 데이터 항목 (Null Safety)**:
  - `BubbleSO` 스펙 참조 (스냅샷 복사: 풀 반납 후 `_spec` null 방지 - AGENT.md §3 준수)
  - `matchCount`: 해당 매치 그룹으로 터진 버블 개수
  - `chainIndex`: 발생한 체인(연쇄) 순서 (1-based index)

### 4.6 스킬 수치 계산 공식
- **최종 수치 공식**: `최종 수치 = value × matchCount × chainWeight(chainIndex)`
  - `value`: 1버블당 기본 수치 (`addPerBubble` 필드는 제거)
  - `matchCount`: 해당 매치 그룹으로 터진 버블 개수
  - `chainWeight(chainIndex)`: 체인 횟수에 따른 가중치 배율 (기본값 1.0, `BubbleSO` 내 설정)

### 4.7 연출 속도 BM 방어선 및 QoL 배속 구분 (AGENT.md §10 연계)
- **Gameplay 고정 요소**: Time Freeze(연출 중 적 타이머 정지)는 큰 연쇄일수록 데미지와 시간 이득을 동시에 주는 핵심 플레이 보상 메커니즘이다. 따라서 퍼즐/스킬 연출 속도(Animation Speed)는 게임 플레이 밸런스(Gameplay)의 핵심 고정 파라미터이며, 코스메틱 상품(스킨 등)으로 변경될 수 없다.
- **QoL 게임 배속**: 편의 기능을 위한 게임 전체 배속(1x, 2x 등 QoL)은 적 타이머와 연출 속도를 동등한 비율로 스케일링하므로 전투 밸런스 구조를 해치지 않는 정당한 편의 기능으로 허용된다.
