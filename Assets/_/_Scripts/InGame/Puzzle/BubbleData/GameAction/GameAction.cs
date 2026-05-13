using System;
using UnityEngine;

public abstract class GameAction:ScriptableObject
{
    public abstract void OnExcute(Actor[] target);
}