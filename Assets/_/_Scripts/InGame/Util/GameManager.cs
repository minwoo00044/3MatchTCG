using UnityEngine;
using System;
using System.Collections.Generic;
public class GameManager : MonoBehaviour, IReceiverableMachineManager
{
    private GameStateMachine machine;
    public event Action OnUpdate;
    private StateReportHub<EGameState, GameManager> stateReportHub;

    // 🌟 핵심: 상태별 이벤트를 보관하는 중앙 딕셔너리
    private Dictionary<EGameState, Action> _eventTable = new Dictionary<EGameState, Action>();

    // 1. 이벤트 구독 (하위 매니저들이 호출)
    public void Subscribe(EGameState state, Action callback)
    {
        if (!_eventTable.ContainsKey(state))
        {
            _eventTable[state] = null;
        }
        _eventTable[state] += callback;
    }

    // 2. 이벤트 구독 해제
    public void Unsubscribe(EGameState state, Action callback)
    {
        if (_eventTable.ContainsKey(state))
        {
            _eventTable[state] -= callback;
        }
    }

    // 3. 특정 상태의 런타임 이벤트 가져오기 (State에 주입해 줄 용도)
    public Action GetStateEvent(EGameState state)
    {
        _eventTable.TryGetValue(state, out Action action);
        return action;
    }

    // 4. 특정 상태를 기다리는 구독자(하위 매니저) 수 반환
    public int GetSubscriberCount(EGameState state)
    {
        if (_eventTable.TryGetValue(state, out Action action))
        {
            return action?.GetInvocationList().Length ?? 0;
        }
        return 0;
    }

    void Awake()
    {
        GMInit();
    }

    void Start()
    {
        machine.ChangeState(EGameState.Init);
    }

    void Update()
    {
        OnUpdate?.Invoke();
    }

    private void GMInit()
    {
        machine = new GameStateMachine(this);
        stateReportHub = new StateReportHub<EGameState, GameManager>(machine);
    }

    public void ReceiveCompleteSignal() => stateReportHub.ReceiveCompleteSignal();

    public int GetMinorManager()
    {
        return GetSubscriberCount(EGameState.Init);
    }
}
