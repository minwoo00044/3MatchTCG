using UnityEngine;

[CreateAssetMenu(fileName ="RandomActor",menuName ="ScriptableObject/TargetData/RandomActor")]
public class RandomActor : ActionTarget
{
    // 유효 대상 중 무작위 1인
    public override Actor[] FindTarget(Actor caster)
    {
        throw new System.NotImplementedException();
    }
}
