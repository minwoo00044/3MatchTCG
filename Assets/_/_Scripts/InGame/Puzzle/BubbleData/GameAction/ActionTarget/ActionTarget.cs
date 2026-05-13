using System;
using UnityEngine;

public abstract class ActionTarget : ScriptableObject
{
    public abstract Actor[] FindTarget();
}