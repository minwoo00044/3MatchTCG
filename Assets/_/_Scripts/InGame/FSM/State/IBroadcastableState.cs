using System;

public interface IBroadcastableState
{
    void InjectBroadCastTask(Action targetAction);
}