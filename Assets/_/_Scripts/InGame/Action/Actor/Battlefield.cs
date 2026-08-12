using System;
using System.Collections.Generic;

// 전장에 선 Actor 명단입니다. MonoBehaviour가 아닌 순수 클래스입니다. (AGENT.md §1)
//
// ActionTarget.FindTarget(Actor caster)는 시전자 하나만 받습니다. (GDD §4.3)
// AllEnemies나 LowestHPAlly는 전장 전체를 알아야 답할 수 있으므로,
// Actor가 자기 전장을 들고 있어 시전자를 통해 명단에 닿습니다.
// 정적 접근점을 두지 않은 이유는 씬을 넘나들 때 잔재가 남고 테스트가 불가능해지기 때문입니다.
public class Battlefield
{
    private readonly List<Actor> actors = new List<Actor>();

    // 유효 전투 시간. 프리즈 구간을 제외한 시계이며 DOTween이 쓰는 Time.time과 다릅니다.
    // 실제로 시간을 흘려보내는 것은 GameTime 작업([7])이며, 그전까지는 0에 머뭅니다.
    // 위협도 윈도우가 0에 고정되므로 그동안은 누적분이 만료되지 않습니다.
    public float GameTime { get; set; }

    public void Register(Actor actor)
    {
        if (actor == null || actors.Contains(actor)) return;
        actors.Add(actor);
    }

    // 사망자 제외 판정은 여기 한 곳에서만 합니다. (GDD §4.1)
    // 타깃 클래스마다 IsDead를 각자 거르면 같은 질문에 답이 여러 개가 됩니다. (AGENT.md §5)
    public Actor[] AliveActors() => Collect(null);
    public Actor[] AlliesOf(Actor caster) => Collect(a => a.IsAllyOf(caster));
    public Actor[] EnemiesOf(Actor caster) => Collect(a => a.IsEnemyOf(caster));

    private Actor[] Collect(Func<Actor, bool> match)
    {
        List<Actor> ret = new List<Actor>();
        foreach (var actor in actors)
        {
            if (actor == null || actor.IsDead) continue;
            if (match != null && !match(actor)) continue;
            ret.Add(actor);
        }
        return ret.ToArray();
    }
}
