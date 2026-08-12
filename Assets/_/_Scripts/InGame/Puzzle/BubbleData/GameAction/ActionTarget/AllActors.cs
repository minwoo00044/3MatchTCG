using UnityEngine;

[CreateAssetMenu(fileName ="AllActors",menuName ="ScriptableObject/TargetData/AllActors")]
public class AllActors : ActionTarget
{
    // 전장 전체 (아군 + 적군)
    public override Actor[] FindTarget(Actor caster)
    {
        if (!HasField(caster)) return None;
        return caster.Field.AliveActors();
    }
}
