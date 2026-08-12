using UnityEngine;

[CreateAssetMenu(fileName ="HealAction",menuName ="ScriptableObject/ActionData/HealAction")]
public class HealAction : GameAction
{
    public override void OnExecute(SkillContext ctx)
    {
        foreach (var target in ctx.Targets)
        {
            // 죽은 대상은 회복되지 않습니다. Actor.Heal이 0을 돌려주며, 부활은 없습니다. (GDD §3.2.1)
            int applied = target.Heal(ctx.Amount);

            ctx.Receipt.Add(new BattleStep(
                ctx.Caster, ctx.Spec, target, EBattleEffect.Heal,
                ctx.Amount, applied, target.CurrentHP, target.Shield, false));
        }
    }
}
