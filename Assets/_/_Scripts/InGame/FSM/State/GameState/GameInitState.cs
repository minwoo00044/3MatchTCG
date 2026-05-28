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
        totalTargetCount = owner != null ? owner.GetMinorManager() : 0;
        _cachedBroadCastAction?.Invoke();
        if (totalTargetCount == 0) OnAllTasksComplete();
    }

    public void ReceiveCompleteSignal()
    {
        readyCount++;
        Debug.Log($"{readyCount}:{totalTargetCount}");
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