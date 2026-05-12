public class GameInitState : BaseState<EGameState, GameManager>
{
    public GameInitState(BaseStateMachine<EGameState, GameManager> machine) : base(machine)
    {
    }

    public override void OnEnter()
    {
        
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