using System.Collections.Generic;
using UnityEngine;
using UnityEngine.InputSystem;
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
    private MoveReceipt cachedReceipt;

    [Header("INPUT")]
    [Tooltip("이 거리(월드 단위, 셀 1칸 = 1) 미만으로 끌면 제자리 탭으로 보고 무시합니다.")]
    [SerializeField]
    private float dragDeadZone = 0.25f;
    private Vector2 dragStartWorldPos;

    [Header("HINT")]
    [Tooltip("입력이 없을 때 몇 초 뒤에 힌트를 보여줄지")]
    [SerializeField]
    private float hintDelay = 5f;
    private float idleTimer;
    private bool hintShown;

    public MoveReceipt CachedReceipt { get => cachedReceipt; set => cachedReceipt = value; }

    protected override void Awake()
    {
        base.Awake();
        puzzleModel = new PuzzleModel(this, size);
        puzzleFactory = new PuzzleFactory();
        puzzlePool = new PuzzlePool(this, viewPrefab);
        puzzleStateMachine = new PuzzleStateMachine(this);
        puzzleMatrixView.Init(this);
        stateReportHub = new StateReportHub<EPuzzleState, PuzzleManager>(puzzleStateMachine);
        gameManager.Subscribe(EGameState.PuzzleAction, HandleOnPuzzleAction);
    }

    protected override void OnDestroy()
    {
        base.OnDestroy();
        if (gameManager != null)
        {
            gameManager.Unsubscribe(EGameState.PuzzleAction, HandleOnPuzzleAction);
        }
    }

    // GameManager의 OnPuzzleAction 이벤트를 수신받았을 때 실행되는 함수
    private void HandleOnPuzzleAction()
    {
        Debug.Log($"[PZ|f{Time.frameCount}] (2) HandleOnPuzzleAction 수신 -> IsFreeze=true, PuzzleState를 PuzzleAction으로 전환");
        IsFreeze = true; // 입력방지
        // 연출이 끝나고 다시 대기 상태가 되면 힌트 타이머가 처음부터 돌아야 합니다.
        ResetHintTimer();
        puzzleStateMachine.ChangeState(EPuzzleState.PuzzleAction);
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
        UpdateHintTimer();
    }
    public Bubble RequestNewBubbleData()
    {
        Bubble data = puzzleFactory.PackBubble(puzzlePool.RequestData());
        PuzzleView puzzleView = puzzlePool.RequestView();
        puzzleView.Injection(data, OnPuzzleViewClickDown, OnPuzzleViewClickUp, OnPuzzleViewHover);
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
        // 데이터와 짝지어진 PuzzleView까지 함께 풀로 회수합니다.
        puzzleMatrixView.ReleaseView(data);
    }

    public void ReceiveCompleteSignal()
    {
        stateReportHub.ReceiveCompleteSignal();
    }

    private Vector2 GetMouseWorldPos()
    {
        Vector2 screenPos = Mouse.current.position.ReadValue();
        return Camera.main.ScreenToWorldPoint(screenPos);
    }

    private void OnPuzzleViewHover(Bubble data, bool entered)
    {
        if (IsFreeze) return;

        if (entered) puzzleMatrixView.SetHovered(data);
        else puzzleMatrixView.ClearHoveredIf(data);
    }

    private void OnPuzzleViewClickDown(Bubble data)
    {
        if (IsFreeze) return;
        if (selected != null) return;

        selected = data;
        dragStartWorldPos = GetMouseWorldPos();
        puzzleMatrixView.SetSelected(data);
        ResetHintTimer();
    }

    // 유니티 EventSystem은 PointerUp을 "누르기 시작한 오브젝트"에게 보냅니다.
    // 따라서 손가락을 아무리 멀리 끌어도 이 콜백은 출발 버블에서 호출되며,
    // 놓은 지점의 레이캐스트가 아니라 '드래그 벡터'로 목적지를 판정합니다.
    // (보드 밖이나 버블 사이 빈 공간에 놓아도 의도대로 동작합니다)
    private void OnPuzzleViewClickUp(Bubble data)
    {
        if (selected == null) return;

        Bubble origin = selected;
        selected = null;
        puzzleMatrixView.SetSelected(null);

        if (IsFreeze) return;

        Vector2 dragDelta = GetMouseWorldPos() - dragStartWorldPos;
        if (dragDelta.magnitude < dragDeadZone) return; // 제자리 탭 - 아무 동작 없음

        // 우세한 축 하나만 골라 상/하/좌/우 중 한 방향으로 확정합니다.
        Vector2Int dir = Mathf.Abs(dragDelta.x) >= Mathf.Abs(dragDelta.y)
            ? new Vector2Int(dragDelta.x > 0 ? 1 : -1, 0)
            : new Vector2Int(0, dragDelta.y > 0 ? 1 : -1);

        Vector2Int targetPos = origin.Pos + dir;
        if (!puzzleModel.IsInBoardRange(targetPos)) return; // 보드 밖으로 미는 동작
        if (puzzleModel.GetBubbleAt(targetPos) == null) return;

        Debug.Log($"[PZ|f{Time.frameCount}] (1) Swap 실행: {origin.Pos} <-> {targetPos} (드래그 {dragDelta})");
        cachedReceipt = puzzleModel.Swap(origin.Pos, targetPos);
        Debug.Log($"[PZ|f{Time.frameCount}] (1) Swap 완료. 영수증 SwapMoves={cachedReceipt.SwapMoves.Count}, ChainSteps={cachedReceipt.ChainSteps.Count}");

        ResetHintTimer();
        gameManager.ReceiveCompleteSignal();
    }

    // ===================== 힌트 =====================

    private void UpdateHintTimer()
    {
        // 연출 중(IsFreeze)에는 타이머를 돌리지 않습니다.
        if (IsFreeze)
        {
            idleTimer = 0f;
            return;
        }
        if (hintShown) return;

        idleTimer += Time.deltaTime;
        if (idleTimer < hintDelay) return;

        hintShown = true; // 못 찾은 경우에도 매 프레임 재탐색하지 않도록 먼저 세웁니다.

        if (!puzzleModel.TryFindHint(out List<Vector2Int> cells)) return;

        List<Bubble> hintBubbles = new List<Bubble>();
        foreach (var pos in cells)
        {
            Bubble bubble = puzzleModel.GetBubbleAt(pos);
            if (bubble != null) hintBubbles.Add(bubble);
        }
        puzzleMatrixView.ShowHint(hintBubbles);
    }

    private void ResetHintTimer()
    {
        idleTimer = 0f;
        if (!hintShown) return;

        hintShown = false;
        puzzleMatrixView.ClearHint();
    }

    public void ExecutePuzzleAction()
    {
        puzzleStateMachine.ChangeState(EPuzzleState.PuzzleAction);
    }

    public void PlayPuzzleAnimateSequence()
    {
        Debug.Log($"[PZ|f{Time.frameCount}] (3) PlayPuzzleAnimateSequence 호출. cachedReceipt={(cachedReceipt == null ? "NULL" : "있음")}");

        if (cachedReceipt == null)
        {
            // 연출할 영수증이 없는데 그냥 return하면 PuzzlePuzzleActionState가
            // readyCount 0/1에서 영구 정지합니다. 즉시 완수 보고로 상태를 흘려보냅니다.
            ReceiveCompleteSignal();
            return;
        }

        // 한 번 소비한 영수증은 즉시 무효화합니다.
        // (재진입 시 이미 풀로 반납된 Bubble을 참조해 연출이 깨지는 것을 방지)
        MoveReceipt receipt = cachedReceipt;
        cachedReceipt = null;

        puzzleMatrixView.PuzzleActionStart(receipt);
    }

}