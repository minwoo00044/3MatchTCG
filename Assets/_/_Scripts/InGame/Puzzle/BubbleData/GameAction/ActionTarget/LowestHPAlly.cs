using UnityEngine;

[CreateAssetMenu(fileName ="LowestHPAlly",menuName ="ScriptableObject/TargetData/LowestHPAlly")]
public class LowestHPAlly : ActionTarget
{
    // caster와 같은 팀 중 체력 비율이 가장 낮은 1인
    public override Actor[] FindTarget(Actor caster)
    {
        throw new System.NotImplementedException();
    }
}
