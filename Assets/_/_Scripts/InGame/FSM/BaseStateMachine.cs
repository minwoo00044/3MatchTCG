using System;
using System.Collections.Generic;
using UnityEngine;
public class BaseStateMachine<T,O> where T: struct,Enum where O:class
{
    protected Dictionary<T,IState> stateDict;
    protected IState current;
    protected bool isDirty;
    protected O owner;

    public Action<T>OnStateEnter;
    public BaseStateMachine(O owner)
    {
        isDirty = false;
        this.owner = owner;
        stateDict = new Dictionary<T, IState>();
    }
    public void InsertState(T stateName, IState state)
    {
        stateDict.Add(stateName,state);
    }
    public void OnUpdate()
    {
        current?.OnUpdate();
    }
    public void ChangeState(T stateName)
    {
        if (isDirty) return;
        if(stateDict[stateName] == current) return;        
        if (!stateDict.ContainsKey(stateName))
        {
            Debug.LogWarning($"{stateName} 상태가 Dictionary에 없습니다.");
            return;
        }
        try 
        {
            isDirty = true;
            current?.OnExit();
            
            current = stateDict[stateName];
            current.OnEnter();
            OnStateEnter?.Invoke(stateName);
            Debug.Log($"State change to {stateName}");
        }
        finally 
        {
            isDirty = false; 
        }
    }

}
