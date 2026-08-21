// 제네릭 베이스는 그대로 유지하면서, 보고 능력만 추가(구현)
using System;
using UnityEngine;


public class GameInitState : BaseState<EGameState, GameManager>, IReportableState,IBroadcastableState
{
    private int readyCount = 0;
    private int totalTargetCount = 0;
    private Action _cachedBroadCastAction;
    public GameInitState(BaseStateMachine<EGameState, GameManager> machine) : base(machine) { }

    public override void OnEnter()
    {
        readyCount = 0;
        var owner = machine.Owner as GameManager;
        totalTargetCount = owner != null ? owner.GetSubscriberCount(EGameState.Init) : 0;
        _cachedBroadCastAction?.Invoke();
        if (totalTargetCount == 0) OnAllTasksComplete();
    }

    public void ReceiveCompleteSignal()
    {
        readyCount++;

        // 불변식: 완수 보고는 기다리는 수만큼만 온다. (AGENTS.md §9)
        if (readyCount > totalTargetCount)
        {
            Debug.LogWarning($"[GameInitState] 완수 보고가 초과했습니다. {readyCount}/{totalTargetCount}");
        }

        if (readyCount >= totalTargetCount) OnAllTasksComplete();
    }

    public void OnAllTasksComplete() => machine.ChangeState(EGameState.Wait);
    public override void OnUpdate() { }
    public override void OnExit() { }

    public void InjectBroadCastTask(Action targetAction)
    {
        _cachedBroadCastAction = targetAction;
    }
}