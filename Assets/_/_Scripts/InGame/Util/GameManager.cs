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
        machine.InsertState(EGameState.Init, new GameInitState(machine));
        machine.OnStateEnter += ProcessStateEnter;
    }
    private void ProcessStateEnter(EGameState stateName)
    {
        switch (stateName)
        {
            case EGameState.Init:
                OnInit?.Invoke();
                break;
        }
    }
}
