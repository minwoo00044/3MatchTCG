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

    // ===================== 스킬 레시피 중계 =====================
    //
    // 하위 매니저끼리 직접 소통하지 않습니다. PuzzleManager는 위로 제출하고,
    // ActionManager는 GameActionState의 브로드캐스트를 받은 뒤 여기서 꺼내 갑니다.
    // 두 매니저는 서로를 모르며 흐름은 GameManager가 쥡니다.
    private readonly List<SkillRecipe> pendingSkillRecipes = new List<SkillRecipe>();

    // PuzzleManager 전용. 퍼즐 연출 완주 시 연쇄 차수 순서대로 평탄화해 제출합니다. (GDD §4.5)
    public void SubmitSkillRecipes(IReadOnlyList<SkillRecipe> recipes)
    {
        if (recipes == null) return;

        // 이전 것이 남아 있다면 아무도 가져가지 않았다는 뜻입니다. 섞이면 이중 적용이 됩니다.
        if (pendingSkillRecipes.Count > 0)
        {
            Debug.LogWarning($"[GameManager] 소비되지 않은 스킬 레시피 {pendingSkillRecipes.Count}건 위에 새 레시피가 제출됐습니다. 이전 것을 버립니다.");
            pendingSkillRecipes.Clear();
        }

        pendingSkillRecipes.AddRange(recipes);
    }

    // 꺼내 가면 보관소는 비워집니다. 스킬은 멱등이 아니라 두 번 꺼내면 두 번 맞습니다.
    // 소비 지점을 여기 하나로 두는 이유입니다. (AGENT.md §4의 반납 주체 규칙과 같은 이유)
    public IReadOnlyList<SkillRecipe> ConsumeSkillRecipes()
    {
        List<SkillRecipe> ret = new List<SkillRecipe>(pendingSkillRecipes);
        foreach (var recipe in ret) recipe.Consumed = true;
        pendingSkillRecipes.Clear();
        return ret;
    }

    // 불변식 검사용. 꺼내지 않고 개수만 봅니다.
    public int PeekSkillRecipeCount() => pendingSkillRecipes.Count;

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
