// 스킬 1건을 실행하는 데 필요한 것 묶음.
//
// GameAction은 수치를 계산하지 않습니다. 계산은 ActionManager가 끝내고
// 여기 담아 넘기며, 액션은 "그 수치를 어떻게 쓰는가"(깎는다/회복한다/막는다)만 압니다.
public class SkillContext
{
    public Actor Caster { get; }
    public BubbleSO Spec { get; }
    public Actor[] Targets { get; }

    // 대상 1명당 적용할 최종 수치. value * matchCount * chainWeight까지 반영된 값입니다. (GDD §4.6)
    public int Amount { get; }

    // 실행 결과를 적을 곳. 액션이 대상마다 한 줄씩 남깁니다.
    public BattleReceipt Receipt { get; }

    public SkillContext(Actor caster, BubbleSO spec, Actor[] targets, int amount, BattleReceipt receipt)
    {
        Caster = caster;
        Spec = spec;
        Targets = targets;
        Amount = amount;
        Receipt = receipt;
    }
}
