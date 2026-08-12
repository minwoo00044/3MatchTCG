using System.Collections.Generic;
using UnityEngine;
using UnityEngine.InputSystem;
public class PuzzleManager : BaseManager, IReceivableMachineManager
{
    [Header("TEST")]
    [SerializeField]
    private List<BubbleSO> testTable;

    [Header("BUBBLE COLOR")]
    [Tooltip("소속 캐릭터가 없는 공용 특수 버블(T_O)의 색. 목업 값입니다")]
    [SerializeField]
    private Color commonBubbleColor = Color.yellow;

    // BubbleSO -> 소속 CharacterSO. 정적 파이프이므로 PuzzleManager가 소유합니다. (GDD §2.3)
    private readonly Dictionary<BubbleSO, CharacterSO> skillOwners = new Dictionary<BubbleSO, CharacterSO>();
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

    // 연출이 도는 동안의 영수증. cachedReceipt는 소비 즉시 비우므로 별도로 들고 있습니다.
    // (재진입 방지와 콜백 조회는 목적이 달라 같은 필드를 겸하게 하지 않습니다)
    private MoveReceipt playingReceipt;


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
        puzzleView.Injection(data, ResolveBubbleColor(data.Spec), OnPuzzleViewClickDown, OnPuzzleViewClickUp, OnPuzzleViewHover);
        puzzleMatrixView.RegistBubble(data, puzzleView);
        return data;
    }
    // ===================== 버블 색 =====================
    //
    // 색을 묻는 곳이 여럿 생기므로 답하는 함수는 여기 하나만 둡니다. (AGENT.md §5)
    private void BuildSkillOwnerMap()
    {
        skillOwners.Clear();

        // 덱의 소유자는 GameManager입니다. 읽는 시점은 Init 브로드캐스트 안으로 한정합니다.
        IReadOnlyList<CharacterSO> characters = gameManager != null ? gameManager.Characters : null;
        if (characters == null)
        {
            Debug.LogWarning("[PuzzleManager] 덱이 배정되지 않아 모든 버블이 공용 색으로 그려집니다.");
            return;
        }

        foreach (var character in characters)
        {
            if (character == null || character.skills == null) continue;

            foreach (var skill in character.skills)
            {
                if (skill == null) continue;

                // 한 버블이 두 캐릭터에 걸려 있으면 색이 스왑 때마다 달라 보입니다.
                if (skillOwners.ContainsKey(skill))
                {
                    Debug.LogWarning($"[PuzzleManager] {skill.SOName}이(가) 캐릭터 둘 이상에 배정돼 있습니다.");
                    continue;
                }
                skillOwners.Add(skill, character);
            }
        }
    }

    public Color ResolveBubbleColor(BubbleSO spec)
    {
        // 소속 캐릭터가 없는 공용 버블(T_O)은 폴백 색을 씁니다.
        if (spec == null) return commonBubbleColor;
        if (!skillOwners.TryGetValue(spec, out CharacterSO owner)) return commonBubbleColor;

        return owner.mainColor;
    }

    public void PuzzleInitialize()
    {
        // 보드를 채우기 전에 색 매핑이 서 있어야 합니다. 순서가 뒤집히면 첫 보드가 전부 공용 색이 됩니다.
        BuildSkillOwnerMap();
        puzzleFactory.InjectBubbleSpecs(testTable);
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
        // 퍼즐 연출이 끝나는 유일한 지점입니다. 완수 보고로 상태를 넘기기 "전에"
        // 레시피를 제출해야 GameActionState가 진입 시점에 바로 집어갈 수 있습니다.
        SubmitSkillRecipes();

        // 영수증의 수명도 여기서 끝납니다. 남겨두면 다음 연출이 지난 레시피를 다시 제출합니다.
        playingReceipt = null;

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

        cachedReceipt = puzzleModel.Swap(origin.Pos, targetPos);

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
        playingReceipt = receipt;

        puzzleMatrixView.PuzzleActionStart(receipt);
    }

    // ===================== 스킬 레시피 =====================

    // 연출이 끝난 영수증에서 스킬 레시피를 걷어 GameManager에 제출합니다. (GDD §4.5)
    //
    // 평탄화 순서가 곧 실행 순서입니다. 연쇄 차수 순으로 돌고, 한 ChainStep 안에서는
    // 이미 선배치 정렬이 끝난 리스트 순서를 그대로 따릅니다.
    // 하위 매니저끼리 직접 넘기지 않고 GameManager를 거칩니다.
    private void SubmitSkillRecipes()
    {
        if (playingReceipt == null) return;

        List<SkillRecipe> flattened = new List<SkillRecipe>();
        foreach (var step in playingReceipt.ChainSteps)
        {
            flattened.AddRange(step.SkillRecipes);
        }

        if (flattened.Count > 0) gameManager.SubmitSkillRecipes(flattened);
    }

}