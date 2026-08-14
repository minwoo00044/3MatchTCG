using System;
using UnityEngine;

// 전투가 실행할 수 있는 것 한 건. (GDD §4.2, §4.6)
//
// 전투 층이 스킬에게 묻는 것은 넷뿐입니다 - 무엇을 하나(action), 누구에게(target),
// 얼마나(value), 어그로를 얼마나 끄나(threatMultiplier). 여기까지가 SkillSO입니다.
//
// 버블은 "보드에서 뽑히고 터지는 스킬"이라 여기에 스폰·시각 정보가 더 붙습니다(BubbleSO).
// 적 NPC의 스킬은 보드에 존재하지 않으므로 그것들이 필요 없습니다.
//
// 둘을 한 클래스로 두면 적 스킬 에셋에 chainWeights(연쇄 배율)가 딸려 옵니다.
// GDD §4.2는 적 데미지에 matchCount와 chainWeight를 곱하지 말라고 못박았는데,
// 에셋에는 그 값이 버젓이 있는 상태가 됩니다. **에셋이 코드와 다른 말을 하게 됩니다.**
// 지금은 ExecuteEnemyAttack이 곱하지 않아 무해하지만, 나중에 "값이 있는데 왜 안 쓰지"로
// 이어지면 조용히 틀어집니다. 그래서 층을 타입으로 갈랐습니다. (AGENT.md §6, §10)
//
// 이제 타입 경계가 곧 "퍼즐 개념이 끝나는 지점"입니다.
// BattleManager.ExecuteSkill이 SkillSO를 받는 것은, 그 함수부터는 연쇄도 매치 개수도
// 이미 수치에 녹아 끝났다는 뜻입니다.
[CreateAssetMenu(fileName = "EmptySkillData", menuName = "ScriptableObject/SkillData")]
public class SkillSO : ScriptableObject
{
  [Header("Name")]
  public String SOName;
  [Header("Module Sector")]
  [SerializeReference]
  public GameAction action;
  [SerializeReference]
  public ActionTarget target;
  [Header("DataParse Sector")]
  [Tooltip("기본 수치. 버블 스킬은 여기에 matchCount와 chainWeight가 곱해지고, 적 스킬은 이 값 그대로입니다 (GDD §4.2, §4.6)")]
  public float value;
  [Tooltip("이 스킬이 시전자에게 쌓는 위협도 배수. 누적량 = (딜 + 힐 + 실드부여) * 이 값 (GDD §2.2, §4.1)")]
  public float threatMultiplier = 1f;

  // 여기서 스킬을 실행하는 함수는 두지 않습니다.
  // 실행 경로는 BattleManager 하나뿐이어야 합니다. 스킬은 멱등이 아니라
  // 경로가 둘이면 그중 하나가 이중 적용이 됩니다. (AGENT.md §5)
}
