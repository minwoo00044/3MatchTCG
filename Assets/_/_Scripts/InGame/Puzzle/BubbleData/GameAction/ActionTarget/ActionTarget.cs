using System;
using UnityEngine;

// 타겟팅은 모두 "시전자 상대 기준"입니다. (GDD §4.3)
// Ally = caster와 같은 팀, Enemy = caster와 반대 팀.
// 그래서 판정에는 반드시 caster가 필요하며, 인자 없는 조회는 존재하지 않습니다.
//
// 전장 명단에는 caster.Field로 닿습니다. 사망자 제외는 Battlefield가 이미 걸러줍니다.
public abstract class ActionTarget : ScriptableObject
{
    public abstract Actor[] FindTarget(Actor caster);

    // 대상이 없을 때 null이 아니라 빈 배열을 돌려줍니다.
    // 호출부가 null 검사를 잊으면 스킬 실행에서 터지는데, 전멸 직전에만 재현되는 버그가 됩니다.
    protected static readonly Actor[] None = new Actor[0];

    protected static Actor[] One(Actor actor) => actor == null ? None : new Actor[] { actor };

    // 시전자가 전장에 올라 있지 않으면 어떤 판정도 할 수 없습니다.
    protected static bool HasField(Actor caster) => caster != null && caster.Field != null;

    // LowestHPAlly와 LowestHPEnemy가 같은 질문을 합니다. 답하는 곳은 여기 하나입니다. (AGENT.md §5)
    // 절대 수치가 아니라 비율입니다. 최대 체력이 다른 캐릭터끼리 비교해야 하기 때문입니다. (GDD §4.3)
    protected static Actor LowestHP(Actor[] pool)
    {
        Actor found = null;
        foreach (var actor in pool)
        {
            if (found == null || actor.HPRatio < found.HPRatio) found = actor;
        }
        return found;
    }

    // 총 위협도 = BaseThreat + 최근 10초 누적. 시계는 전장이 들고 있습니다. (GDD §4.1)
    protected static Actor HighestThreat(Actor[] pool, float gameTime)
    {
        Actor found = null;
        float best = float.NegativeInfinity;

        foreach (var actor in pool)
        {
            float threat = actor.GetTotalThreat(gameTime);
            if (found != null && threat <= best) continue;

            found = actor;
            best = threat;
        }
        return found;
    }
}
