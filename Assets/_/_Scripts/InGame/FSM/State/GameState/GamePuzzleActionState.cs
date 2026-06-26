using System;

public class GamePuzzleActionState : BaseState<EGameState, GameManager>, IBroadcastableState
{
    public GamePuzzleActionState(BaseStateMachine<EGameState, GameManager> machine) : base(machine)
    {
    }

    public void InjectBroadCastTask(Action targetAction)
    {
        throw new NotImplementedException();
    }

    public override void OnEnter()
    {
        throw new System.NotImplementedException();
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