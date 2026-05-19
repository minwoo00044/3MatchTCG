public class PuzzleStateMachine : BaseStateMachine<EPuzzleState, PuzzleManager>
{
    public PuzzleStateMachine(PuzzleManager owner) : base(owner)
    {
    }
}