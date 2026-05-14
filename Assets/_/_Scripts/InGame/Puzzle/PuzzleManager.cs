using UnityEngine;
public class PuzzleManager : BaseManager
{
    private PuzzleFactory puzzleFactory;
    private PuzzlePool puzzlePool;
    protected override void Awake()
    {
        base.Awake();
        puzzleFactory = new PuzzleFactory();
        puzzlePool = new PuzzlePool(this);
    }
    public override void OnUpdate()
    {
    }
}