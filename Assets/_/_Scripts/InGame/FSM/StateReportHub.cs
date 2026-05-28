using System;
using UnityEngine;

public class StateReportHub<T, O> 
    where T : struct, Enum 
    where O : class
{
    private BaseStateMachine<T, O> _targetMachine;

    public StateReportHub(BaseStateMachine<T, O> machine)
    {
        _targetMachine = machine;
    }

    // [핵심] 기존에 GameManager나 PuzzleManager에 중복으로 들어가던 그 코드입니다.
    public void ReceiveCompleteSignal()
    {
        // 1. 현재 머신의 활성화된 스테이트가 보고를 수집하는 인터페이스를 구현했는지 검사
        if (_targetMachine.CurrentState is IReportableState reportableState)
        {
            Debug.Log(reportableState.GetType());
            // 2. 자격이 있다면 해당 스테이트 객체에게 신호를 그대로 토스!
            reportableState.ReceiveCompleteSignal();
        }
        else
        {
            // 방어 코드: 보고를 받지 않는 상태(예: Idle 등)인데 신호가 들어왔을 때의 예외 처리
            Debug.LogWarning($"현재 상태는 보고를 받는 상태가 아닙니다.");
        }
    }
}