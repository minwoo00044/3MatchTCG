using System.Collections.Generic;
using UnityEngine;
public class PuzzleManager : BaseManager, IReceiverableMachineManager
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
    private StateReportHub<EPuzzleState, PuzzleManager> stateReportHub;
    private Bubble selected;
    protected override void Awake()
    {
        base.Awake();
        puzzleModel = new PuzzleModel(this, size);
        puzzleFactory = new PuzzleFactory();
        puzzlePool = new PuzzlePool(this, viewPrefab);
        puzzleStateMachine = new PuzzleStateMachine(this);
        puzzleMatrixView.Init(this);
        stateReportHub = new StateReportHub<EPuzzleState, PuzzleManager>(puzzleStateMachine);
    }
    //게임매니저의 OnInit 이벤트에 맞춰서 호출됨
    protected override void OnInit()
    {
        base.OnInit();
        puzzleStateMachine.ChangeState(EPuzzleState.Init);
    }
    protected override void OnUpdate()
    {
        base.OnUpdate();
        puzzleStateMachine.OnUpdate();
    }
    public Bubble RequestNewBubbleData()
    {
        Bubble data = puzzleFactory.PackBubble(puzzlePool.RequestData());
        PuzzleView puzzleView = puzzlePool.RequestView();
        puzzleView.Injection(data,OnPuzzleViewClickDown,OnPuzzleViewClickUp);
        puzzleMatrixView.RegistBubble(data, puzzleView);
        return data;
    }
    public void PuzzleInitialize()
    {
        puzzleFactory.InJectBubbleSpecs(testTable);
        puzzleModel.SetBubbles(() =>
        {
            puzzleMatrixView.DrawingAllMatrix();
            
        });
    }
    public void ReportStateTaskComplete()
    {
        gameManager.ReceiveCompleteSignal();
    }
    public void RemoveAtMatrix(Bubble data)
    {
        puzzleMatrixView.RemoveView(data);
    }

    public void ReceiveCompleteSignal()
    {
        stateReportHub.ReceiveCompleteSignal();
    }

    private void OnPuzzleViewClickDown(Bubble data)
    {
        if (selected is null) 
        {
            selected = data;
        }
    }
    private void OnPuzzleViewClickUp(Bubble data)
    {
        // 방어 코드: 누른 적이 없는데 떼졌다면 예외 처리
        if (selected == null) return;

        // 1. 마우스가 떼어진 현재 스크린 위치를 유니티 월드 좌표로 변환
        Vector2 mouseWorldPos = Camera.main.ScreenToWorldPoint(Input.mousePosition);

        // 2. 해당 위치에 있는 2D 콜라이더를 레이캐스트로 검출
        RaycastHit2D hit = Physics2D.Raycast(mouseWorldPos, Vector2.zero);

        if (hit.collider != null)
        {
            // 3. 부딪힌 오브젝트에서 PuzzleView 컴포넌트를 획득
            PuzzleView targetView = hit.collider.GetComponent<PuzzleView>();

            if (targetView != null)
            {
                // 뷰가 가진 진짜 타겟 데이터 추출
                Bubble targetData = targetView.Data; // PuzzleView에 public Bubble Data => _data; 프로퍼티 필요

                // 4. 누른 데이터와 뗀 데이터가 다르고, 서로 인접해 있다면 스왑 실행!
                if (selected != targetData && puzzleModel.IsAdjacent(selected.Pos, targetData.Pos))
                {
                    // 변경사항 > 스테이트를 퍼즐액션 상태로 변경
                    //게임 매니저 상태를 퍼즐액션 상태로 변경(추가 클릭 및 게임 진행 정지)
                    // 게임매니저의 이벤트에 따라 모델에 스왑명령
                    // 이후 퍼즐 머신을 연출/연쇄 상태(Animate)로 전환하여 뷰에게 그리라고 지시
                    // puzzleMachine.ChangeState(EPuzzleState.Animate, receipt);
                }
            }
        }

        // 한 사이클이 끝났으므로 선택 데이터 초기화
        selected = null;
    }

}