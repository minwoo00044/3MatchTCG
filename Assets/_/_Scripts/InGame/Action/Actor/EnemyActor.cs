// 적 NPC. (GDD §4.2)
//
// 1차 MVP는 1마리입니다.
// 공격 주기를 세는 것은 EnemyController, 실행은 BattleManager입니다. 이 클래스는 스탯만 듭니다.
public class EnemyActor : Actor
{
    private readonly string displayName;

    // 적이 쓸 스킬. 적 공격은 버블 매치가 없으므로 최종 데미지 = value 고정입니다. (GDD §4.2)
    //
    // BubbleSO가 아니라 SkillSO입니다. 적 스킬은 보드에 존재하지 않으므로 스폰 가중치도
    // 연쇄 배율도 뜻이 없고, 특히 chainWeights를 들고 있으면 "곱하지 않는다"는 규칙과
    // 에셋이 서로 다른 말을 하게 됩니다.
    public SkillSO Skill { get; }

    public EnemyActor(Battlefield field, string displayName, int maxHP, int maxShield, float baseThreat, SkillSO skill)
        : base(field, ETeam.Enemy, maxHP, maxShield, baseThreat)
    {
        this.displayName = displayName;
        Skill = skill;
    }

    public override string ToString() => string.IsNullOrEmpty(displayName) ? "Enemy" : displayName;
}
