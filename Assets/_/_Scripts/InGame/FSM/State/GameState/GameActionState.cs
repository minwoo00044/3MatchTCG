using System;
using UnityEngine;

// 퍼즐 연출이 전부 끝난 뒤 스킬을 일괄 실행하는 구간입니다. (GDD §4.5)
//
// 흐름: GameWaitState -> (스왑) -> GamePuzzleActionState -> [여기] -> GameWaitState
//
// 스킬 실행을 DOTween 시퀀스 내부가 아니라 전용 상태로 뺀 이유는 두 가지입니다.
// 하나는 전투 흐름의 주도권을 GameManager가 갖게 하기 위함이고,
// 다른 하나는 캐릭터 공격 모션 같은 스킬 연출을 놓을 시간축을 확보하기 위함입니다.
//
// 클래스 이름 주의: AutoInsertStates()가 "{Owner}{State}State"로 찾습니다.
// GameManager -> "Game", EGameState.Action -> GameActionState. (AGENT.md §2)
public class GameActionState : BaseState<EGameState, GameManager>, IBroadcastableState, IReportableState
{
    private Action _cachedBroadCastAction;
    private int readyCount = 0;
    private int totalTargetCount = 0;

    public GameActionState(BaseStateMachine<EGameState, GameManager> machine) : base(machine)
    {
    }

    public void InjectBroadCastTask(Action targetAction)
    {
        _cachedBroadCastAction = targetAction;
    }

    public override void OnEnter()
    {
        readyCount = 0;
        var owner = machine.Owner;
        totalTargetCount = owner != null ? owner.GetSubscriberCount(EGameState.Action) : 0;

        // 구독자(ActionManager)는 이 브로드캐스트를 받고 GameManager에서 영수증을 꺼내 갑니다.
        _cachedBroadCastAction?.Invoke();

        if (totalTargetCount == 0)
        {
            // 스킬을 해석할 구독자가 없다는 뜻입니다. 이 턴의 전투가 통째로 사라집니다.
            // 상태에서 나가는 길은 확보해야 하므로 흘려보내되 조용히 넘기지는 않습니다. (AGENT.md §8)
            if (owner != null && owner.HasPendingMoveReceipt)
            {
                Debug.LogWarning("[GameActionState] 스킬을 해석할 구독자가 없어 이번 턴의 영수증을 버립니다.");
            }
            OnAllTasksComplete();
        }
    }

    public void ReceiveCompleteSignal()
    {
        readyCount++;
        if (readyCount >= totalTargetCount) OnAllTasksComplete();
    }

    public void OnAllTasksComplete()
    {
        // 퍼즐 연쇄와 스킬 실행이 모두 끝난 지점입니다.
        // 사망과 수치는 실행 도중 이미 확정됐지만 승패 전이는 여기까지 미뤄 둔 것입니다.
        // 오버킬로 즉시 전이하면 재생 중인 시퀀스가 남고 뷰가 누수됩니다. (GDD §4.4, AGENT.md §9)
        var owner = machine.Owner;
        if (owner != null && owner.HasPendingResult)
        {
            machine.ChangeState(EGameState.End);
            return;
        }

        machine.ChangeState(EGameState.Wait);
    }

    public override void OnExit()
    {
        // 불변식: 이 상태를 나갈 때 제출된 영수증은 남아 있으면 안 된다.
        // 남아 있다는 건 구독자가 꺼내 가지 않았다는 뜻이고, 다음 턴 제출과 섞입니다. (AGENT.md §9)
        var owner = machine.Owner;
        if (owner == null || !owner.HasPendingMoveReceipt) return;

        Debug.LogWarning("[GameActionState] 소비되지 않은 영수증이 남은 채 상태를 벗어납니다.");
        owner.ConsumeMoveReceipt();
    }

    public override void OnUpdate()
    {
    }
}
