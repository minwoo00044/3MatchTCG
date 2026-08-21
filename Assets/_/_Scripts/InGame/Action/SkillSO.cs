using System;
using System.Collections.Generic;
using UnityEngine;

[Serializable]
public class SkillEffect
{
  public GameAction action;
  public ActionTarget target;
  public float value;
  public float threatMultiplier = 1f;

  public SkillEffect()
  {
  }

  public SkillEffect(GameAction action, ActionTarget target, float value, float threatMultiplier)
  {
    this.action = action;
    this.target = target;
    this.value = value;
    this.threatMultiplier = threatMultiplier;
  }
}

// 전투가 실행할 수 있는 스킬 한 건. 한 스킬은 독립된 SkillEffect 모듈을 하나 이상 가집니다.
// (GDD §2.3, §4.5, §4.6)
//
// 무엇을 하나(action), 누구에게(target), 얼마나(value), 어그로를 얼마나 끄나(threatMultiplier)는
// 효과마다 다르므로 SkillEffect가 들고, SkillSO는 그 조합과 이름만 소유합니다.
//
// 버블은 "보드에서 뽑히고 터지는 스킬"이라 여기에 스폰·시각 정보가 더 붙습니다(BubbleSO).
// 적 NPC의 스킬은 보드에 존재하지 않으므로 그것들이 필요 없습니다.
//
// 둘을 한 클래스로 두면 적 스킬 에셋에 chainWeights(연쇄 배율)가 딸려 옵니다.
// GDD §4.2는 적 데미지에 matchCount와 chainWeight를 곱하지 말라고 못박았는데,
// 에셋에는 그 값이 버젓이 있는 상태가 됩니다. **에셋이 코드와 다른 말을 하게 됩니다.**
// 지금은 ExecuteEnemyAttack이 곱하지 않아 무해하지만, 나중에 "값이 있는데 왜 안 쓰지"로
// 이어지면 조용히 틀어집니다. 그래서 층을 타입으로 갈랐습니다. (AGENTS.md §6, §10)
//
// 이제 타입 경계가 곧 "퍼즐 개념이 끝나는 지점"입니다.
// BattleManager.ExecuteSkill이 SkillSO를 받는 것은, 그 함수부터는 연쇄도 매치 개수도
// 이미 수치에 녹아 끝났다는 뜻입니다.
[CreateAssetMenu(fileName = "EmptySkillData", menuName = "ScriptableObject/SkillData")]
public class SkillSO : ScriptableObject
{
  [Header("Name")]
  public String SOName;
  [Header("Effects")]
  public List<SkillEffect> effects = new List<SkillEffect>();

  // 기존 에셋을 effects 목록으로 옮기는 동안만 유지하는 직렬화 호환 필드입니다.
  // 에디터 마이그레이션이 끝나기 전에 지우면 기존 9종 버블과 적 스킬 배선이 사라집니다.
  [HideInInspector]
  [SerializeReference]
  public GameAction action;
  [HideInInspector]
  [SerializeReference]
  public ActionTarget target;
  [HideInInspector]
  [Tooltip("기본 수치. 버블 스킬은 여기에 matchCount와 chainWeight가 곱해지고, 적 스킬은 이 값 그대로입니다 (GDD §4.2, §4.6)")]
  public float value;
  [HideInInspector]
  [Tooltip("이 스킬이 시전자에게 쌓는 위협도 배수. 누적량 = (딜 + 힐 + 실드부여) * 이 값 (GDD §2.2, §4.1)")]
  public float threatMultiplier = 1f;

  private SkillEffect legacyEffect;

  // 마이그레이션 전에도 기존 에셋이 그대로 동작하게 하는 임시 출구입니다.
  // 새 목록이 한 건이라도 있으면 레거시 필드는 절대 섞지 않습니다.
  public IReadOnlyList<SkillEffect> Effects
  {
    get
    {
      if (effects != null && effects.Count > 0) return effects;

      if (legacyEffect == null
          || legacyEffect.action != action
          || legacyEffect.target != target
          || !Mathf.Approximately(legacyEffect.value, value)
          || !Mathf.Approximately(legacyEffect.threatMultiplier, threatMultiplier))
      {
        legacyEffect = new SkillEffect(action, target, value, threatMultiplier);
      }

      return new[] { legacyEffect };
    }
  }

  // 여기서 스킬을 실행하는 함수는 두지 않습니다.
  // 실행 경로는 BattleManager 하나뿐이어야 합니다. 스킬은 멱등이 아니라
  // 경로가 둘이면 그중 하나가 이중 적용이 됩니다. (AGENTS.md §5)
}
