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
        Debug.Log($"GamePuzzleActionState readyCount: {readyCount}/{totalTargetCount}");
        if (readyCount >= totalTargetCount) OnAllTasksComplete();
    }

    public void OnAllTasksComplete()
    {
        machine.ChangeState(EGameState.Wait);
    }

    public override void OnExit()
    {
    }

    public override void OnUpdate()
    {
    }
}