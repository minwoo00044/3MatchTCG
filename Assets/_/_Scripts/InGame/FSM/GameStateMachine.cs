public class GameStateMachine : BaseStateMachine<EGameState, GameManager>
{
    public GameStateMachine(GameManager owner) : base(owner)
    {
        owner.OnUpdate += this.OnUpdate;
    }
}