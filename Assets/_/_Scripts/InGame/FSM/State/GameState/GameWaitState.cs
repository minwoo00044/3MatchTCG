using UnityEngine;

// 플레이어의 스왑을 기다리는 구간입니다. 동시에 전투 시계가 흐르는 유일한 구간입니다. (GDD §4.2)
//
// 여기서만 틱을 열기 때문에 퍼즐 연쇄 연출(GamePuzzleActionState)과 스킬 실행(GameActionState)
// 동안에는 적 타이머와 GameTime이 완전히 멈춥니다. Time Freeze를 별도 플래그로 끄고 켜지 않고
// 구조로 보장하는 것이 요점입니다. 플래그로 두면 켜고 끄는 지점이 상태 수만큼 늘어납니다.
public class GameWaitState : BaseState<EGameState, GameManager>, IReportableState
{
    public GameWaitState(BaseStateMachine<EGameState, GameManager> machine) : base(machine)
    {
    }


    public override void OnEnter()
    {

    }

    public override void OnExit()
    {

    }

    public override void OnUpdate()
    {
        var owner = machine.Owner;
        if (owner == null) return;

        // 승패가 예약된 채로 여기 있으면 시간을 더 흘리지 않습니다.
        // 정상 흐름에서는 GameActionState가 직접 End로 빠지므로 도달하지 않지만,
        // 도달했다면 예약이 있는데도 전투가 계속 도는 상태이므로 여기서 끊습니다.
        if (owner.HasPendingResult)
        {
            machine.ChangeState(EGameState.End);
            return;
        }

        // 유효 전투 시간을 흘려보냅니다. 구독자(BattleManager)가 GameTime을 전진시키고
        // 적 공격 타이머를 굴립니다. 이 상태는 누가 무엇을 하는지 알지 않습니다.
        owner.TickWait(Time.deltaTime);

        // 적 공격으로 아군이 죽어 패배가 결정될 수 있습니다.
        // 적 공격 자체는 상태를 전이시키지 않지만(Wait에서 나가는 길은 플레이어 스왑),
        // 승패는 예외입니다. (GDD §4.4)
        //
        // Wait 구간에는 아직 완주를 기다릴 연출이 없어 즉시 전이합니다.
        // [9]에서 피격 연출이 붙으면 그 완주 지점으로 이 확인을 옮겨야 합니다.
        if (owner.HasPendingResult)
        {
            machine.ChangeState(EGameState.End);
        }
    }

    public void ReceiveCompleteSignal()
    {
        OnAllTasksComplete();
    }
    public void OnAllTasksComplete()
    {
        machine.ChangeState(EGameState.PuzzleAction);
    }

}
