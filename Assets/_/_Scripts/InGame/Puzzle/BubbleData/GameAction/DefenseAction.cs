using UnityEngine;

[CreateAssetMenu(fileName ="DefenseAction",menuName ="ScriptableObject/ActionData/DefenseAction")]
public class DefenseAction : GameAction
{
    public override void OnExecute(SkillContext ctx)
    {
        foreach (var target in ctx.Targets)
        {
            // MaxShield가 상한입니다. 넘긴 분은 버려지지만 위협도에는 부여량 전체가 잡힙니다.
            // 탱커가 방어 행위를 계속하는 한 어그로를 유지하는 게 의도입니다. (HANDOFF §7)
            int applied = target.AddShield(ctx.Amount);

            ctx.Receipt.Add(new BattleStep(
                ctx.Caster, ctx.Spec, target, EBattleEffect.Shield,
                ctx.Amount, applied, target.CurrentHP, target.Shield, false));
        }
    }
}
