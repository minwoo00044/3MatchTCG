using UnityEngine;
using System;
using System.Collections.Generic;
public class GameManager : MonoBehaviour, IReceivableMachineManager
{
    private GameStateMachine machine;
    public event Action OnUpdate;
    private StateReportHub<EGameState, GameManager> stateReportHub;

    // 🌟 핵심: 상태별 이벤트를 보관하는 중앙 딕셔너리
    private Dictionary<EGameState, Action> _eventTable = new Dictionary<EGameState, Action>();

    // 1. 이벤트 구독 (하위 매니저들이 호출)
    public void Subscribe(EGameState state, Action callback)
    {
        if (!_eventTable.ContainsKey(state))
        {
            _eventTable[state] = null;
        }
        _eventTable[state] += callback;
    }

    // 2. 이벤트 구독 해제
    public void Unsubscribe(EGameState state, Action callback)
    {
        if (_eventTable.ContainsKey(state))
        {
            _eventTable[state] -= callback;
        }
    }

    // 3. 특정 상태의 런타임 이벤트 가져오기 (State에 주입해 줄 용도)
    public Action GetStateEvent(EGameState state)
    {
        _eventTable.TryGetValue(state, out Action action);
        return action;
    }

    // ===================== 전투 덱 =====================
    //
    // 덱은 전투 전체의 데이터이고 소비자가 둘입니다.
    // PuzzleManager(버블 색 매핑, 스포닝 비율)와 BattleManager(Actor 3인 생성).
    // 각자 [SerializeField]로 들면 배선이 두 벌이 되고, 어긋나면 화면의 버블 색과
    // 실제 필드에 선 캐릭터가 다른 덱을 가리키게 됩니다. (AGENT.md §5)
    //
    // 소유는 여기, 파생(BubbleSO -> CharacterSO 매핑 등)은 각 매니저가 만듭니다. (GDD §2.3)
    // 하위 매니저는 아무 때나 읽지 않고 Init 브로드캐스트를 받은 OnInit 안에서만 읽습니다.
    [Header("BATTLE")]
    [SerializeField]
    private DeckSO deck;

    // DeckSO 타입이 아니라 목록으로 노출합니다. 나중에 공급원이 편성 UI의 세이브 데이터로
    // 바뀌어도 소비하는 쪽 코드는 그대로 둘 수 있습니다.
    public IReadOnlyList<CharacterSO> Characters => deck != null ? deck.characters : null;

    // ===================== 퍼즐 영수증 중계 =====================
    //
    // 하위 매니저끼리 직접 소통하지 않습니다. PuzzleManager는 연출을 마친 영수증을 위로
    // 제출하고, BattleManager는 GameActionState의 브로드캐스트를 받은 뒤 여기서 꺼내 갑니다.
    // 두 매니저는 서로를 모르며 흐름은 GameManager가 쥡니다.
    //
    // 영수증은 "무슨 버블이 몇 차에 몇 개 터졌나"까지만 담고 있습니다.
    // 스킬 해석은 꺼내 가는 쪽(BattleManager)의 몫입니다.
    private MoveReceipt pendingReceipt;

    public void SubmitMoveReceipt(MoveReceipt receipt)
    {
        if (receipt == null) return;

        // 이전 것이 남아 있다면 아무도 가져가지 않았다는 뜻입니다. 덮으면 그 턴의 스킬이 통째로 사라집니다.
        if (pendingReceipt != null)
        {
            Debug.LogWarning("[GameManager] 소비되지 않은 영수증 위에 새 영수증이 제출됐습니다. 이전 것을 버립니다.");
        }

        pendingReceipt = receipt;
    }

    // 꺼내 가면 보관소는 비워집니다. 스킬은 멱등이 아니라 두 번 꺼내면 두 번 맞습니다.
    // 소비 지점을 여기 하나로 두는 이유입니다. (AGENT.md §4의 반납 주체 규칙과 같은 이유)
    public MoveReceipt ConsumeMoveReceipt()
    {
        MoveReceipt ret = pendingReceipt;
        pendingReceipt = null;
        return ret;
    }

    // 불변식 검사용. 꺼내지 않고 남아 있는지만 봅니다.
    public bool HasPendingMoveReceipt => pendingReceipt != null;

    // ===================== Wait 구간 틱 =====================
    //
    // 적 공격 타이머와 GameTime을 굴리려면 매 프레임 신호가 하위 매니저까지 내려가야 합니다.
    // 그런데 GameWaitState는 적 Actor에 닿을 수 없습니다. Battlefield는 BattleManager가 소유하고
    // GameManager는 하위 매니저 참조를 들지 않기 때문입니다. 기존 배선은 상태 진입 시 1회
    // 브로드캐스트뿐이라 매 프레임을 실어 나를 길이 없었습니다.
    //
    // 그래서 Wait 전용 틱을 엽니다. 발동 지점은 여전히 GameWaitState.OnUpdate()이므로
    // GDD §4.2 문안 그대로이고, GameManager가 열어주지 않으면 시간이 흐르지 않으므로
    // Time Freeze가 구조로 보장됩니다. GameManager.OnUpdate(전 구간)와 구별해야 합니다.
    public event Action<float> OnWaitTick;

    public void TickWait(float delta) => OnWaitTick?.Invoke(delta);

    // ===================== 승패 예약 =====================
    //
    // 승패 판정은 전장을 소유한 BattleManager가 하지만, 전이 시점은 다릅니다.
    // 수치와 사망은 즉시 확정하되 상태 전이는 진행 중인 연출이 완주한 뒤로 미룹니다.
    // 즉시 전이하면 재생 중이던 시퀀스가 남고 ReturnToPool()이 안 불린 뷰가
    // dataViewDict에 남아 불변식이 깨집니다. (GDD §4.4, AGENT.md §9)
    //
    // 그래서 판정하는 쪽은 여기에 결과를 적어두기만 하고,
    // 연출이 끝나는 지점(GameActionState의 완수, GameWaitState의 틱)이 확인해 전이합니다.
    private EGameResult pendingResult = EGameResult.None;

    public EGameResult PendingResult => pendingResult;
    public bool HasPendingResult => pendingResult != EGameResult.None;

    // 먼저 들어온 결과만 채택합니다. 같은 연출 배치 안에서 아군 2인 사망과 적 사망이
    // 함께 일어날 수 있는데, 나중 것으로 덮으면 실행 순서에 따라 승패가 뒤집힙니다.
    public void RequestGameEnd(EGameResult result)
    {
        if (result == EGameResult.None) return;
        if (pendingResult != EGameResult.None) return;

        pendingResult = result;
    }

    // 전투 영수증(BattleReceipt)은 여기를 거치지 않습니다.
    //
    // MoveReceipt가 중계를 타는 건 생산자(PuzzleManager)와 소비자(BattleManager)가 다른
    // 매니저이기 때문입니다. 전투 영수증은 BattleManager가 만들고 아직 소비자가 없어
    // 중계할 이유가 없습니다. 연출 담당이 별도 매니저로 생기면 그때 같은 모양으로 놓습니다. (AGENT.md §10)

    // 4. 특정 상태를 기다리는 구독자(하위 매니저) 수 반환
    public int GetSubscriberCount(EGameState state)
    {
        if (_eventTable.TryGetValue(state, out Action action))
        {
            return action?.GetInvocationList().Length ?? 0;
        }
        return 0;
    }

    void Awake()
    {
        GMInit();
    }

    void Start()
    {
        machine.ChangeState(EGameState.Init);
    }

    void Update()
    {
        OnUpdate?.Invoke();
    }

    private void GMInit()
    {
        machine = new GameStateMachine(this);
        stateReportHub = new StateReportHub<EGameState, GameManager>(machine);
    }

    public void ReceiveCompleteSignal() => stateReportHub.ReceiveCompleteSignal();

    public int GetMinorManager()
    {
        return GetSubscriberCount(EGameState.Init);
    }
}
