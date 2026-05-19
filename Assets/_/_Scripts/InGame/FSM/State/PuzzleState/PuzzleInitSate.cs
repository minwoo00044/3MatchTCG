public class PuzzleInitState : BaseState<EPuzzleState, PuzzleManager>
{
    public PuzzleInitState(BaseStateMachine<EPuzzleState, PuzzleManager> machine) : base(machine)
    {
    }

    public override void OnEnter()
    {
        var owner = machine.Owner as PuzzleManager;
        owner.PuzzleInitialize();
    }

    public override void OnExit()
    {
        throw new System.NotImplementedException();
    }

    public override void OnUpdate()
    {
        throw new System.NotImplementedException();
    }

}