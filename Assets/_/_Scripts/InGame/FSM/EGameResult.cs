// 전투 결과. (GDD §4.4)
//
// EGameState와 달리 FSM 상태가 아닙니다. GameEndState는 하나뿐이고,
// 승리와 패배는 그 상태가 무엇을 보여줄지를 가르는 값입니다.
// 상태를 둘로 쪼개면 AutoInsertStates()가 찾는 클래스도 둘이 되고,
// "전투가 끝났다"는 같은 사실에 대한 출구가 두 개가 됩니다. (AGENTS.md §5)
//
// None은 "아직 결정되지 않음"입니다. 이 값으로 GameEndState에 들어오면 불변식 위반입니다.
public enum EGameResult
{
    None,
    Victory,
    Defeat,
}
