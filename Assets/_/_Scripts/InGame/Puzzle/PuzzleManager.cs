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
    private PuzzleView viewPrefab;
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
        puzzlePool = new PuzzlePool(this,viewPrefab);
    }
    //게임매니저의 OnInit 이벤트에 맞춰서 호출됨
    protected override void Init()
    {
        base.Init();
        puzzleFactory.InJectBubbleSpecs(testTable);
        puzzleModel.SetBubbles(()=>puzzleMatrixView.DrawingAllMatrix());
    }
    protected override void OnUpdate()
    {
    }
    public Bubble RequestNewBubbleData()
    {
        Bubble data = puzzleFactory.PackBubble(puzzlePool.RequestData());
        PuzzleView puzzleView = puzzlePool.RequestView();
        puzzleView.Injection(data.Spec.bubbleColor, data.Spec.bubbleImage);


        return data;
    }
}