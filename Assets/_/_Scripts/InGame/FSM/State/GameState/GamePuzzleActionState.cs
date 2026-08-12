using System;
using UnityEngine;

public class GamePuzzleActionState : BaseState<EGameState, GameManager>, IBroadcastableState, IReportableState
{
    private Action _cachedBroadCastAction;
    private int readyCount = 0;
    private int totalTargetCount = 0;

    public GamePuzzleActionState(BaseStateMachine<EGameState, GameManager> machine) : base(machine)
    {
    }

    public void InjectBroadCastTask(Action targetAction)
    {
        _cachedBroadCastAction = targetAction;
    }

    public override void OnEnter()
    {
        readyCount = 0;
        var owner = machine.Owner as GameManager;
        totalTargetCount = owner != null ? owner.GetSubscriberCount(EGameState.PuzzleAction) : 0;

        _cachedBroadCastAction?.Invoke();

        if (totalTargetCount == 0) OnAllTasksComplete();
    }

    public void ReceiveCompleteSignal()
    {
        readyCount++;

        // 불변식: 완수 보고는 기다리는 수만큼만 온다.
        // 초과분은 같은 작업이 두 번 보고했다는 뜻이고, 그대로 두면 다음 상태를 조기에 끝냅니다.
        if (readyCount > totalTargetCount)
        {
            Debug.LogWarning($"[GamePuzzleActionState] 완수 보고가 초과했습니다. {readyCount}/{totalTargetCount}");
        }

        if (readyCount >= totalTargetCount) OnAllTasksComplete();
    }

    public void OnAllTasksComplete()
    {
        // 퍼즐 연출이 끝나도 곧바로 대기로 돌아가지 않고 스킬 실행 구간을 거칩니다. (GDD §4.5)
        machine.ChangeState(EGameState.Action);
    }

    public override void OnExit()
    {
    }

    public override void OnUpdate()
    {
    }
}