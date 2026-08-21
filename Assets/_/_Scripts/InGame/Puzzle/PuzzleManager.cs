using System.Collections.Generic;
using UnityEngine;
using UnityEngine.InputSystem;
public class PuzzleManager : BaseManager, IReceivableMachineManager
{
    [Header("COMMON BUBBLE")]
    [Tooltip("어느 캐릭터에도 속하지 않는 공용 특수 버블(T_O). 스포닝 지분 10% (GDD §3.2)")]
    [SerializeField]
    private List<BubbleSO> commonBubbles;
    [Tooltip("공용 버블의 색. 소속 캐릭터가 없어 mainColor를 물려받을 수 없습니다. 목업 값")]
    [SerializeField]
    private Color commonBubbleColor = Color.yellow;

    // BubbleSO -> 소속 CharacterSO. 정적 파이프이므로 PuzzleManager가 소유합니다. (GDD §2.3)
    private readonly Dictionary<BubbleSO, CharacterSO> skillOwners = new Dictionary<BubbleSO, CharacterSO>();
    // 스포닝 재정규화의 기준. Actor를 직접 참조하지 않고 CharacterSO 사망 신호로만 갱신합니다. (GDD §3.2.1)
    private readonly List<CharacterSO> aliveCharacters = new List<CharacterSO>();
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

    // 전투 종료 여부. IsFreeze와 겸하지 않는 이유는 수명이 다르기 때문입니다.
    //
    // IsFreeze는 연출 중 일시 차단이고 PuzzleWaitState.OnEnter가 매번 되돌립니다.
    // 그런데 승패는 GameActionState에서 확정되고, 그 뒤 PuzzlePuzzleActionState가
    // EPuzzleState.Wait로 넘어가며 IsFreeze를 다시 풉니다. 종료를 IsFreeze로 표현하면
    // 바로 그 지점에서 조용히 풀려 게임 오버 후에도 스왑이 됩니다.
    private bool isGameOver;

    // 입력을 받아도 되는가. 묻는 곳이 넷이므로 답하는 곳은 여기 하나만 둡니다. (AGENTS.md §5)
    private bool CanAcceptInput => !IsFreeze && !isGameOver;

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
        gameManager.Subscribe(EGameState.End, HandleOnGameEnd);
        gameManager.OnCharacterDied += HandleCharacterDied;
    }

    protected override void OnDestroy()
    {
        base.OnDestroy();
        if (gameManager != null)
        {
            gameManager.Unsubscribe(EGameState.PuzzleAction, HandleOnPuzzleAction);
            gameManager.Unsubscribe(EGameState.End, HandleOnGameEnd);
            gameManager.OnCharacterDied -= HandleCharacterDied;
        }
    }

    // 전투가 끝나면 보드는 더 이상 입력을 받지 않습니다. (GDD §4.4)
    //
    // GameEndState는 완수 보고를 세지 않으므로 여기서 보고하지 않습니다.
    // 보고하면 "완수 보고를 받지 않는 상태"라는 경고만 남습니다. (AGENTS.md §8)
    private void HandleOnGameEnd()
    {
        isGameOver = true;
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
    // 색을 묻는 곳이 여럿 생기므로 답하는 함수는 여기 하나만 둡니다. (AGENTS.md §5)
    private void BuildSkillOwnerMap()
    {
        skillOwners.Clear();
        aliveCharacters.Clear();

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

            aliveCharacters.Add(character);

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

    // 생존 캐릭터별 스킬 후보. skillOwners가 색과 소유 관계의 단일 원천이고,
    // Factory에는 그룹만 넘겨 Actor/CharacterSO 의존성을 만들지 않습니다. (GDD §2.3, §3.2)
    private List<List<BubbleSO>> BuildCharacterSpawnGroups()
    {
        List<List<BubbleSO>> ret = new List<List<BubbleSO>>();

        foreach (var character in aliveCharacters)
        {
            List<BubbleSO> specs = new List<BubbleSO>();
            foreach (var pair in skillOwners)
            {
                if (pair.Value == character) specs.Add(pair.Key);
            }
            ret.Add(specs);
        }

        return ret;
    }

    private void RefreshSpawnCandidates()
    {
        puzzleFactory.InjectSpawnCandidates(BuildCharacterSpawnGroups(), commonBubbles);
    }

    private void HandleCharacterDied(CharacterSO character)
    {
        if (character == null) return;

        // Actor.OnDeath는 한 번만 발화하지만 중계가 중복돼도 결과가 달라지지 않게 합니다.
        if (!aliveCharacters.Remove(character)) return;

        // 현재 스왑의 리필은 MoveReceipt에 이미 확정돼 있습니다. 전투 실행 중 들어온 이 갱신은
        // 다음 스왑이 새 버블을 요청할 때부터 적용됩니다. (GDD §3.2.1, AGENTS.md §3)
        RefreshSpawnCandidates();
    }

    public void PuzzleInitialize()
    {
        // 보드를 채우기 전에 색 매핑이 서 있어야 합니다.
        // 스폰 후보도 이 매핑에서 나오므로 순서가 뒤집히면 보드가 공용 버블로만 채워집니다.
        BuildSkillOwnerMap();
        RefreshSpawnCandidates();
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
        // 영수증을 올려야 GameActionState가 진입 시점에 바로 집어갈 수 있습니다.
        //
        // 퍼즐이 하는 일은 여기까지입니다. 이 영수증이 무슨 스킬이 되는지는 모릅니다.
        if (playingReceipt != null) gameManager.SubmitMoveReceipt(playingReceipt);

        // 영수증의 수명도 여기서 끝납니다. 남겨두면 다음 연출이 지난 것을 다시 제출합니다.
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
        if (!CanAcceptInput) return;

        if (entered) puzzleMatrixView.SetHovered(data);
        else puzzleMatrixView.ClearHoveredIf(data);
    }

    private void OnPuzzleViewClickDown(Bubble data)
    {
        if (!CanAcceptInput) return;
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

        if (!CanAcceptInput) return;

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
        // 연출 중이거나 전투가 끝났으면 타이머를 돌리지 않습니다.
        // 스왑할 수 없는 상태에서 "여기를 스왑하라"고 알려주면 안 됩니다.
        if (!CanAcceptInput)
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

}
