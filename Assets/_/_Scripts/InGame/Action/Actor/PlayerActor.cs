// 플레이어 덱의 캐릭터 1인. (GDD §2.3, §4.1)
//
// CharacterSO는 값의 출처일 뿐 실행 중에 다시 읽지 않습니다.
// 나중에 육성이 붙으면 maxHP는 1레벨 기준값이 되고 성장치가 더해지는데,
// Actor가 값으로만 받아두면 그때도 Actor는 고치지 않아도 됩니다.
public class PlayerActor : Actor
{
    // 어느 캐릭터인지 되짚을 때 씁니다 (버블 -> 시전자 역추적, 사망 시 스포닝 재정규화).
    public CharacterSO Origin { get; }

    public PlayerActor(Battlefield field, CharacterSO origin)
        : base(field, ETeam.Player, origin.maxHP, origin.maxShield, origin.baseThreat)
    {
        Origin = origin;
    }

    public override string ToString() => Origin != null ? Origin.characterName : "Player";
}
