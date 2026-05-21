using System;

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
        var owner = machine.Owner as PuzzleManager;
        owner.PuzzleInitialize();
        readyCount = 0;
        totalTargetCount = 2; //우선 퍼즐 매니저가 보고받을 대상은 모델과 뷰 단 둘로 본다.
        _cachedBroadCastAction?.Invoke();
        //if (totalTargetCount == 0) OnAllTasksComplete();
    }

    public override void OnExit()
    {
    }

    public override void OnUpdate()
    {
        throw new System.NotImplementedException();
    }

    public void ReceiveCompleteSignal()
    {
        readyCount++;
        if (readyCount >= totalTargetCount) OnAllTasksComplete();
    }
}