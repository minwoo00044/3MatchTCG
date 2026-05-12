using System;

public abstract class BaseState<T,O> : IState
    where T : struct, Enum
    where O:class
{
    protected BaseStateMachine<T,O> machine;
    public BaseState(BaseStateMachine<T,O> machine)
    {
        this.machine = machine;
    }
    public abstract void OnEnter();
    public abstract void OnUpdate();
    public abstract void OnExit();
}