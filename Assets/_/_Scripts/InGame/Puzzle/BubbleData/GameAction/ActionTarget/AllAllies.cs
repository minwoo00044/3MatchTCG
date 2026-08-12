using UnityEngine;

[CreateAssetMenu(fileName ="AllAllies",menuName ="ScriptableObject/TargetData/AllAllies")]
public class AllAllies : ActionTarget
{
    // caster와 같은 팀 전체
    public override Actor[] FindTarget(Actor caster)
    {
        if (!HasField(caster)) return None;
        return caster.Field.AlliesOf(caster);
    }
}
