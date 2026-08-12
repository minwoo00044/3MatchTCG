using System;
using System.Reflection;
using System.Collections.Generic;
using UnityEngine;

public class BaseStateMachine<T, O>
    where T : struct, Enum
    where O : class
{
    public O Owner { get; private set; }
    public IState CurrentState { get; private set; }
    protected Dictionary<T, IState> _stateTable = new Dictionary<T, IState>();

    public BaseStateMachine(O owner)
    {
        this.Owner = owner;
        AutoInsertStates();
    }
    private void AutoInsertStates()
    {
        string ownerName = typeof(O).Name.Replace("Manager", ""); // 예: "GameManager" -> "Game"
        Type enumType = typeof(T);

        // 현재 프로젝트(Assembly)에 존재하는 모든 클래스 타입을 가져옵니다.
        Type[] allTypes = Assembly.GetExecutingAssembly().GetTypes();

        foreach (T state in Enum.GetValues(enumType))
        {
            string stateName = state.ToString();
            // 규칙 조합: "Game" + "Init" + "State" = "GameInitState"
            string targetClassName = $"{ownerName}{stateName}State";

            // 전수 조사 대상 중 이름이 일치하는 타입 검색
            Type targetType = Array.Find(allTypes, t => t.Name == targetClassName);

            if (targetType != null)
            {
                // 생성자 매개변수로 이 머신(this)을 넘겨주며 동적 인스턴스 생성 (Activator 사용)
                // new GameInitState(this)를 실행하는 것과 같습니다.
                object stateInstance = Activator.CreateInstance(targetType, this);

                if (stateInstance is IState validState)
                {
                    _stateTable[state] = validState;
                }
            }
            else
            {
                Debug.LogWarning($"[{typeof(O).Name}] 규칙에 맞는 상태 클래스를 찾지 못했습니다: {targetClassName}");
            }
        }

        Debug.Log($"[{typeof(O).Name}] 상태 머신 세팅 완료. 총 {_stateTable.Count}개의 상태가 자동 등록됨.");
    }

    public void ChangeState(T newState)
    {
        CurrentState?.OnExit();
        IState nextState = null;
        _stateTable.TryGetValue(newState, out nextState);
        if (nextState is null)
        {
            // 등록되지 않은 상태로 전이하려 한 것입니다. 이전 상태는 이미 OnExit을 마쳤으므로
            // 여기서 돌아가면 어느 상태에도 속하지 않은 채로 멈춥니다. (AGENT.md §8)
            Debug.LogWarning($"[{typeof(O).Name}] 등록되지 않은 상태로 전이를 시도했습니다: {newState}");
            return;
        }
        if (nextState is IBroadcastableState broadcastable)
        {
            if (Owner is GameManager gameManager && newState is EGameState gameState)
            {
                Action currentRuntimeEvent = gameManager.GetStateEvent(gameState);

                if (currentRuntimeEvent != null)
                {
                    broadcastable.InjectBroadCastTask(currentRuntimeEvent);
                }
            }
        }
        CurrentState = nextState;
        CurrentState?.OnEnter();
    }
    public void OnUpdate()
    {
        CurrentState?.OnUpdate();
    }
}