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
    private PuzzleStateMachine puzzleStateMachine;
    protected override void Awake()
    {
        base.Awake();
        puzzleModel = new PuzzleModel(this, size);
        puzzleFactory = new PuzzleFactory();
        puzzlePool = new PuzzlePool(this, viewPrefab);
        puzzleStateMachine = new PuzzleStateMachine(this);
    }
    //게임매니저의 OnInit 이벤트에 맞춰서 호출됨
    protected override void OnInit()
    {
        base.OnInit();
        puzzleStateMachine.ChangeState(EPuzzleState.Init);
    }
    protected override void OnUpdate()
    {
    }
    public Bubble RequestNewBubbleData()
    {
        Bubble data = puzzleFactory.PackBubble(puzzlePool.RequestData());
        PuzzleView puzzleView = puzzlePool.RequestView();
        puzzleView.Injection(data);
        puzzleMatrixView.RegistBubble(data,puzzleView);
        return data;
    }
    public void PuzzleInitialize()
    {
        puzzleFactory.InJectBubbleSpecs(testTable);
        puzzleModel.SetBubbles(() =>
        {
            puzzleMatrixView.DrawingAllMatrix();
            ReportStateTaskComplete();
        });
    }
    private void ReportStateTaskComplete()
    {
        gameManager.ReceiveCompleteSignal();
    }
    public void RemoveAtMatrix(Bubble data)
    {
        puzzleMatrixView.RemoveView(data);
    }
}