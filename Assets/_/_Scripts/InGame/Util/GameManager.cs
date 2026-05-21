using UnityEngine;
using System;
public class GameManager : MonoBehaviour,IReceiverableMachineManager
{
GameStateMachine machine;
    public event Action OnInit;
    public event Action OnUpdate;
    private StateReportHub<EGameState,GameManager> stateReportHub;
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
        stateReportHub = new StateReportHub<EGameState, GameManager>(machine);
    }
    public void ReceiveCompleteSignal()=> stateReportHub.ReceiveCompleteSignal();
    public int GetMinorManager()
    {
        return OnInit?.GetInvocationList().Length ?? 0;
    }
}
