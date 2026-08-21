using UnityEngine;

// 스킬 1건을 실행하는 데 필요한 것 묶음.
//
// GameAction은 수치를 계산하지 않습니다. 계산은 BattleManager가 끝내고
// 여기 담아 넘기며, 액션은 "그 수치를 어떻게 쓰는가"(깎는다/회복한다/막는다)만 압니다.
public class SkillContext
{
    public Actor Caster { get; }
    // SkillSO입니다. 여기까지 오면 matchCount와 chainWeight는 이미 Amount에 녹아 끝났고,
    // 액션은 이 스킬이 버블에서 왔는지 적에게서 왔는지 알 필요가 없습니다.
    public SkillSO Spec { get; }
    public Actor[] Targets { get; }

    // 반올림 전 효과 값. 증폭처럼 소수 고정값을 쓰는 액션은 이 값을 소비합니다.
    public float Value { get; }

    // 이번 MoveReceipt 안에서만 살아 있는 배치 상태입니다.
    public SkillBatchContext Batch { get; }

    // 대상 1명당 적용할 최종 수치. value * matchCount * chainWeight까지 반영된 값입니다. (GDD §4.6)
    public int Amount => Mathf.RoundToInt(Value);

    // 실행 결과를 적을 곳. 액션이 대상마다 한 줄씩 남깁니다.
    public BattleReceipt Receipt { get; }

    public SkillContext(Actor caster, SkillSO spec, Actor[] targets, float value,
                        SkillBatchContext batch, BattleReceipt receipt)
    {
        Caster = caster;
        Spec = spec;
        Targets = targets;
        Value = value;
        Batch = batch;
        Receipt = receipt;
    }
}
