public class PuzzleWaitState : BaseState<EPuzzleState, PuzzleManager>
{
    public PuzzleWaitState(BaseStateMachine<EPuzzleState, PuzzleManager> machine) : base(machine)
    {
    }

    public void OnAllTasksComplete()
    {
        throw new System.NotImplementedException();
    }

    public override void OnEnter()
    {
        machine.Owner.IsFreeze = false;
    }

    public override void OnExit()
    {
    }

    public override void OnUpdate()
    {
    }


}