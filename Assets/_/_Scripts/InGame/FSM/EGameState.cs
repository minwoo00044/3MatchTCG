public enum EGameState
{
    Init,
    Wait,
    PuzzleAction,
    // 퍼즐 연출이 전부 끝난 뒤 스킬을 일괄 실행하는 구간. (GDD §4.5)
    // 이 값은 GameActionState와 짝이 맞아야 합니다.
    Action,
    // BaseStateMachine.AutoInsertStates()가 "{Owner}{State}State"로 클래스를 찾습니다.
    // GameManager -> "Game" 이므로 이 값은 반드시 End여야 GameEndState와 짝이 맞습니다.
    // (GameEnd로 두면 GameGameEndState를 찾게 됩니다)
    End,
}