using System.Collections.Generic;
using UnityEngine;
public class PuzzleManager : BaseManager
{
    [Header("TEST")]
    [SerializeField]
    private List<BubbleSO> testTable;
    [SerializeField]
    private int size;
    [SerializeField]
    private PuzzleMatrixView puzzleMatrixView;
    private PuzzleModel puzzleModel;
    private PuzzleFactory puzzleFactory;
    private PuzzlePool puzzlePool;
    protected override void Awake()
    {
        base.Awake();
        puzzleModel = new PuzzleModel(this,size);
        puzzleFactory = new PuzzleFactory();
        puzzlePool = new PuzzlePool(this);
    }
    //게임매니저의 OnInit 이벤트에 맞춰서 호출됨
    protected override void Init()
    {
        base.Init();
        puzzleFactory.InJectBubbleSpecs(testTable);
        puzzleModel.SetBubbles();
    }
    protected override void OnUpdate()
    {
    }
    public Bubble RequestNewBubbleData()
    {
        return puzzleFactory.PackBubble(puzzlePool.RequestData()) ;
    }
}