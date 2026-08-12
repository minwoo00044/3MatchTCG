public enum EGameState
{
    Init,
    Wait,
    PuzzleAction,
    // BaseStateMachine.AutoInsertStates()가 "{Owner}{State}State"로 클래스를 찾습니다.
    // GameManager -> "Game" 이므로 이 값은 반드시 End여야 GameEndState와 짝이 맞습니다.
    // (GameEnd로 두면 GameGameEndState를 찾게 됩니다)
    End,
}