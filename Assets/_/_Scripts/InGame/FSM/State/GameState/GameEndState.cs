using System;
using UnityEngine;

// 승패가 확정된 뒤의 종착 상태입니다. (GDD §4.4)
//
// 클래스 이름 주의: AutoInsertStates()가 "{Owner}{State}State"로 찾습니다.
// GameManager -> "Game", EGameState.End -> GameEndState. 틀리면 컴파일은 되고
// 경고 한 줄 뒤 조용히 동작하지 않습니다. (AGENTS.md §2)
//
// 전투를 멈추기 위해 따로 끄는 것이 없습니다. GameTime과 적 타이머는 GameWaitState가
// 여는 틱으로만 흐르므로, 여기로 들어오는 순간 함께 멈춥니다.
//
// 결과 화면 · 리트라이 · 씬 전환은 GDD §D 미결이라 아직 없습니다.
// 이 상태는 "전투가 끝났고 결과가 무엇인가"까지만 책임집니다.
//
// IReportableState는 구현하지 않습니다. 종착 상태라 완수를 기다릴 다음 상태가 없습니다.
// 브로드캐스트는 "끝났다"를 알리기 위한 것이고 응답을 세지 않습니다.
public class GameEndState : BaseState<EGameState, GameManager>, IBroadcastableState
{
    private Action _cachedBroadCastAction;

    public GameEndState(BaseStateMachine<EGameState, GameManager> machine) : base(machine)
    {
    }

    public void InjectBroadCastTask(Action targetAction)
    {
        _cachedBroadCastAction = targetAction;
    }

    public override void OnEnter()
    {
        // 하위 매니저에게 전투 종료를 알립니다. PuzzleManager가 이 신호로 입력을 닫습니다.
        // 상태가 직접 PuzzleManager에 닿을 수 없으므로 기존 브로드캐스트 배선을 씁니다.
        _cachedBroadCastAction?.Invoke();

        var owner = machine.Owner;
        EGameResult result = owner != null ? owner.PendingResult : EGameResult.None;

        // 불변식: 결과가 예약되지 않은 채로 이 상태에 들어올 수 없다.
        // 들어왔다면 승패를 정하지 않고 전이한 것이고, 이 상태에서 나가는 길이 없으므로
        // 게임은 결과를 모르는 채 멈춥니다. (AGENTS.md §9)
        if (result == EGameResult.None)
        {
            Debug.LogWarning("[GameEndState] 승패가 예약되지 않은 채 종료 상태에 들어왔습니다.");
            return;
        }

        // 결과를 표시할 화면이 아직 없습니다. UIManager의 결과 화면이 붙으면 제거합니다. (AGENTS.md §9)
        Debug.Log($"[GameEndState] 전투 종료 - {(result == EGameResult.Victory ? "승리" : "패배")}");
    }

    public override void OnUpdate()
    {
    }

    public override void OnExit()
    {
    }
}
