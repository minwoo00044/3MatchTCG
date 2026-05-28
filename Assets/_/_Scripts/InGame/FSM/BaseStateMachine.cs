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

    // [추가] 상태(Enum)에 따른 이벤트(Action) 리모컨을 미리 구워둘 보관함
    private Dictionary<T, FieldInfo> _eventFieldCache = new Dictionary<T, FieldInfo>();
    public BaseStateMachine(O owner)
    {
        this.Owner = owner;
        AutoInsertStates();
        CacheOwnerEventFields(); // 생성과 동시에 (오너의 Awake 시점) 캐싱 시작
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
    // [핵심] 오너의 모든 이벤트를 싹 긁어서 미리 딕셔너리에 구워둡니다.
    private void CacheOwnerEventFields()
    {
        Type ownerType = typeof(O);
        foreach (T state in Enum.GetValues(typeof(T)))
        {
            string stateName = state.ToString();

            FieldInfo field = ownerType.GetField("On" + stateName,
                BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic);

            if (field == null)
            {
                field = ownerType.GetField(stateName,
                    BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic);
            }

            if (field != null)
            {
                // [수정] 값 대신 필드 정보 자체를 저장
                _eventFieldCache[state] = field;
            }
        }
    }

    public void ChangeState(T newState)
    {
        CurrentState?.OnExit();
        IState nextState = null;
        _stateTable.TryGetValue(newState, out nextState);
        if(nextState is null)
        {
            Debug.Log("null state change");
            return;
        }
        if (nextState is IBroadcastableState broadcastable)
        {
            // 딕셔너리에서 필드 정보를 가져옴
            if (_eventFieldCache.TryGetValue(newState, out FieldInfo field))
            {
                // [핵심] 상태 전환 시점에 오너의 실시간 이벤트 인스턴스(Action)를 추출!
                // 하위 매니저들이 += 등록을 마친 상태이므로 더 이상 null이 아닙니다.
                Action currentRuntimeEvent = field.GetValue(Owner) as Action;

                // 런타임 이벤트가 null이 아닐 때만 주입 (구독자가 아무도 없으면 null일 수 있음)
                if (currentRuntimeEvent != null)
                {
                    broadcastable.InjectBroadCastTask(currentRuntimeEvent);
                }
            }
        }

        CurrentState = nextState;
        CurrentState?.OnEnter();
        Debug.Log($"{this},{CurrentState} init");
    }
    public void OnUpdate()
    {
        CurrentState?.OnUpdate();
    }
}