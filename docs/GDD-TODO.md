# GDD 미결 항목 (결정 완료 및 GDD.md 반영 완료)

`docs/GDD-TODO.md`에 정의되었던 모든 미결 항목(Category A, B, C)은 **기획 결정이 완료되어 [docs/GDD.md](file:///c:/Users/SSAFY/Desktop/prj/3MatchTCG/docs/GDD.md) 본문에 모두 반영**되었습니다.

---

## 📌 결정 완료 및 반영 내역 요약

### A. 구조 결정 (Category A)
- **A-1. 버블 색의 Single Source of Truth**:
  - `CharacterSO.mainColor`를 단일 원천으로 확정하고 `BubbleSO.bubbleColor` 필드는 완전 제거.
- **A-2. 역참조 매핑 소유자 (AGENT.md §1 준수)**:
  - 정적 파이프(`DeckSO` ↔ `BubbleSO`) 및 비율 계산은 `PuzzleManager`가 전담.
  - 런타임 역참조 매핑(`CharacterSO` ↔ `Actor`)은 `BattleManager`가 소유하고, `PuzzleManager`는 `Actor`를 직접 참조하지 않고 `BubbleSO` 스냅샷만 레시피로 전달.

### B. 적 전투 규격 (Category B)
- **B-1. 적 NPC 기본 규격**:
  - 1마리, `MaxHP`: 3,000, `MaxShield`: 0, 공격 주기 3.0초. 기본 스킬: `AttackAction` / `HighestThreatEnemy` / value: 50.
- **B-2. 적 스킬 컨테이너**:
  - ~~1차 MVP에서는 `BubbleSO` 컨테이너를 재사용.~~
  - **변경(승인 완료)**: `SkillSO`를 신설하고 `BubbleSO : SkillSO`로 갈랐다. 적 스킬은 `SkillSO`를 직접 쓴다.
  - **사유**: `BubbleSO`를 재사용하면 적 스킬 에셋이 `chainWeights`를 들고 있게 되는데, GDD §4.2는 적 데미지에 `chainWeight`를 곱하지 않는다고 규정한다. 에셋과 규칙이 서로 다른 말을 하는 상태였다. GDD §2.3·§4.2·§4.5 반영 완료.
- **B-3. `T_O` 스킬 효과 확정**:
  - 파괴 시 해당 연쇄 턴 동안 모든 아군 스킬 수치 1.2배 증폭 + 체력 비율 최저 아군 1인 HP 50 회복 (중첩 시 합연산 1.4배, 최대 상한 2.0배).

### C. 밸런스 및 수치 프리셋 (Category C)
- **C-1. 캐릭터 3인 스탯 프리셋**:
  - 캐릭터 A (딜러/Red): HP 400 / Shield 100 / Threat 100
  - 캐릭터 B (탱커/Green): HP 600 / Shield 200 / Threat 300
  - 캐릭터 C (힐러/Blue): HP 350 / Shield 50 / Threat 50
- **C-2. 9종 전용 스킬 카탈로그**:
  - A1/A2/A3 (공격 계열), B1/B2/B3 (방어/어그로 계열), C1/C2/C3 (힐/방어 계열) 스킬 배치 표 완비.
- **C-3. Threat (위협도) 계산공식**:
  - 딜 1당 Threat +1.0 / 힐 1당 Threat +1.0, 최근 10초 유효 전투 시간(`GameTime`) 누적 윈도우.

---

## D. MVP 이후 / 향후 논의 항목 (Category D)

- **스테이지 구조**: 웨이브 구성 및 리트라이 규칙
- **전투 승패 후 처리**: 스테이지 클리어/실패 UI 및 씬 전환 시퀀스
- **가챠·수집 UI 및 캐릭터 육성**: 코어 전투 완성 후 구현 (GDD §1 명시)
