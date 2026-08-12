using UnityEngine;

[CreateAssetMenu(fileName ="HighestThreatEnemy",menuName ="ScriptableObject/TargetData/HighestThreatEnemy")]
public class HighestThreatEnemy : ActionTarget
{
    // caster와 반대 팀 중 위협도가 가장 높은 1인 (적 NPC 공격의 기본 규칙)
    public override Actor[] FindTarget(Actor caster)
    {
        throw new System.NotImplementedException();
    }
}
