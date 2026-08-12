using System;
using UnityEngine;

// 타겟팅은 모두 "시전자 상대 기준"입니다. (GDD §4.3)
// Ally = caster와 같은 팀, Enemy = caster와 반대 팀.
// 그래서 판정에는 반드시 caster가 필요하며, 인자 없는 조회는 존재하지 않습니다.
public abstract class ActionTarget : ScriptableObject
{
    public abstract Actor[] FindTarget(Actor caster);
}
