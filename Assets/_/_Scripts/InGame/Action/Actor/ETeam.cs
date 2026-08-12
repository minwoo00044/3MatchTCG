// 전투 엔티티의 소속 팀. (GDD §4.1)
//
// 모든 타겟팅은 caster.Team을 기준으로 한 "상대" 판정입니다. (GDD §4.3)
// Ally = caster와 같은 팀, Enemy = caster와 반대 팀이므로
// Player/Enemy는 진영 이름일 뿐 타겟팅 규칙에 직접 등장하지 않습니다.
public enum ETeam
{
    Player,
    Enemy,
}
