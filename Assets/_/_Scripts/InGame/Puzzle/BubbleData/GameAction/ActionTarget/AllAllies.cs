using UnityEngine;

[CreateAssetMenu(fileName ="AllAllies",menuName ="ScriptableObject/TargetData/AllAllies")]
public class AllAllies : ActionTarget
{
    // caster와 같은 팀 전체
    public override Actor[] FindTarget(Actor caster)
    {
        throw new System.NotImplementedException();
    }
}
