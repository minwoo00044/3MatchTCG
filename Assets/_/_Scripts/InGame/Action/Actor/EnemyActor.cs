// 적 NPC. (GDD §4.2)
//
// 1차 MVP는 1마리이고 스킬 컨테이너로 BubbleSO를 재사용합니다.
// 공격 주기를 세는 것은 EnemyController, 실행은 ActionManager입니다. 이 클래스는 스탯만 듭니다.
public class EnemyActor : Actor
{
    private readonly string displayName;

    // 적이 쓸 스킬. 적 공격은 버블 매치가 없으므로 최종 데미지 = value 고정입니다. (GDD §4.2)
    public BubbleSO Skill { get; }

    public EnemyActor(Battlefield field, string displayName, int maxHP, int maxShield, float baseThreat, BubbleSO skill)
        : base(field, ETeam.Enemy, maxHP, maxShield, baseThreat)
    {
        this.displayName = displayName;
        Skill = skill;
    }

    public override string ToString() => string.IsNullOrEmpty(displayName) ? "Enemy" : displayName;
}
