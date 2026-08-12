using UnityEngine;

[CreateAssetMenu(fileName ="AllEnemies",menuName ="ScriptableObject/TargetData/AllEnemies")]
public class AllEnemies : ActionTarget
{
    // caster와 반대 팀 전체
    public override Actor[] FindTarget(Actor caster)
    {
        throw new System.NotImplementedException();
    }
}
