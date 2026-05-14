using System.Collections.Generic;

public class PuzzlePool
{
    private Queue<Bubble> pool;
    private PuzzleManager puzzleManager;

    public PuzzlePool(PuzzleManager puzzleManager)
    {
        this.puzzleManager = puzzleManager;
    }
}