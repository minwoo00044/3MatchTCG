using UnityEngine;

[CreateAssetMenu(fileName ="RandomActor",menuName ="ScriptableObject/TargetData/RandomActor")]
public class RandomActor : ActionTarget
{
    // 유효 대상 중 무작위 1인. 아군/적군을 가리지 않습니다.
    public override Actor[] FindTarget(Actor caster)
    {
        if (!HasField(caster)) return None;

        Actor[] pool = caster.Field.AliveActors();
        if (pool.Length == 0) return None;

        return One(pool[Random.Range(0, pool.Length)]);
    }
}
