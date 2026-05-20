using UnityEngine;
using System;
public class GameManager : MonoBehaviour
{
    private GameStateMachine machine;
    public event Action OnInit;
    public event Action OnUpdate;
    void Awake()
    {
        GMInit();
    }
    void Start()
    {
        machine.ChangeState(EGameState.Init);
    }

    // Update is called once per frame
    void Update()
    {
        OnUpdate?.Invoke();
    }

    private void GMInit()
    {
        machine = new GameStateMachine(this);
    }
    public void ReceiveCompleteSignal()
    {
        // 1. 현재 머신의 활성화된 스테이트가 보고를 수집하는 인터페이스를 구현했는지 검사
        if (machine.CurrentState is IReportableState reportableState)
        {
            // 2. 자격이 있다면 해당 스테이트 객체에게 신호를 그대로 토스!
            reportableState.ReceiveCompleteSignal();
        }
        else
        {
            // 방어 코드: 보고를 받지 않는 상태(예: Idle 등)인데 신호가 들어왔을 때의 예외 처리
            Debug.LogWarning($"현재 상태는 보고를 받는 상태가 아닙니다.");
        }
    }
    public int GetMinorManager()
    {
        return OnInit?.GetInvocationList().Length ?? 0;
    }
}
