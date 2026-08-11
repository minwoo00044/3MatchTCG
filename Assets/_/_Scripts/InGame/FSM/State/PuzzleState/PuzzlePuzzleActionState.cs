using System;
using UnityEngine;

public class PuzzlePuzzleActionState : BaseState<EPuzzleState, PuzzleManager>, IReportableState
{
    private int readyCount = 0;
    private int totalTargetCount = 0;
    private MoveReceipt cachedReceipt;
    public PuzzlePuzzleActionState(BaseStateMachine<EPuzzleState, PuzzleManager> machine) : base(machine)
    {
    }

    public override void OnEnter()
    {
        readyCount = 0;
        var owner = machine.Owner;
        totalTargetCount = 1; // 퍼즐 뷰 애니메이션 연출 1건 완료를 대기

        if (owner != null)
        {
            owner.PlayPuzzleAnimateSequence();
        }

        if (totalTargetCount == 0) OnAllTasksComplete();
    }

    public void ReceiveCompleteSignal()
    {
        readyCount++;
        Debug.Log($"PuzzlePuzzleActionState readyCount: {readyCount}/{totalTargetCount}");
        if (readyCount >= totalTargetCount) OnAllTasksComplete();
    }

    public void OnAllTasksComplete()
    {
        machine.Owner.ReportStateTaskComplete();
        machine.ChangeState(EPuzzleState.Wait);
    }

    public override void OnExit()
    {
    }

    public override void OnUpdate()
    {
    }
}