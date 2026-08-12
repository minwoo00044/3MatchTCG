using UnityEngine;

[CreateAssetMenu(fileName ="LowestHPEnemy",menuName ="ScriptableObject/TargetData/LowestHPEnemy")]
public class LowestHPEnemy : ActionTarget
{
    // caster와 반대 팀 중 체력 비율이 가장 낮은 1인
    public override Actor[] FindTarget(Actor caster)
    {
        throw new System.NotImplementedException();
    }
}
