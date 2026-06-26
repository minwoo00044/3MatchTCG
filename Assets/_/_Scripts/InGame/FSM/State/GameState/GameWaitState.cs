public class GameWaitState : BaseState<EGameState, GameManager>,IReportableState
{
    public GameWaitState(BaseStateMachine<EGameState, GameManager> machine) : base(machine)
    {
    }


    public override void OnEnter()
    {

    }

    public override void OnExit()
    {

    }

    public override void OnUpdate()
    {

    }

    public void ReceiveCompleteSignal()
    {
        OnAllTasksComplete();
    }
    public void OnAllTasksComplete()
    {
        machine.ChangeState(EGameState.PuzzleAction);
    }

}