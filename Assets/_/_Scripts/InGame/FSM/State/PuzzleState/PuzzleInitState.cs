using System;
using UnityEngine;
public class PuzzleInitState : BaseState<EPuzzleState, PuzzleManager>, IReportableState, IBroadcastableState
{
    private Action _cachedBroadCastAction;
    private int readyCount = 0;
    private int totalTargetCount = 0;

    public PuzzleInitState(BaseStateMachine<EPuzzleState, PuzzleManager> machine) : base(machine)
    {
    }
    public void InjectBroadCastTask(Action targetAction)
    {
        _cachedBroadCastAction = targetAction;
    }

    public void OnAllTasksComplete()
    {
        machine.Owner.ReportStateTaskComplete();
    }

    public override void OnEnter()
    {
        // 1. 카운터 세팅 및 규칙 장전 (준비 완료)
        readyCount = 0;
        totalTargetCount = 2;

        // 2. 일꾼들 출발 및 방송 개시
        var owner = machine.Owner as PuzzleManager;
        if (owner != null)
        {
            owner.PuzzleInitialize();
        }

        _cachedBroadCastAction?.Invoke();

        if (totalTargetCount == 0) OnAllTasksComplete();
    }

    public override void OnExit()
    {
    }

    public override void OnUpdate()
    {
    }

    public void ReceiveCompleteSignal()
    {
        readyCount++;
        Debug.Log($"{readyCount}:{totalTargetCount}");
        if (readyCount >= totalTargetCount) OnAllTasksComplete();
    }
}