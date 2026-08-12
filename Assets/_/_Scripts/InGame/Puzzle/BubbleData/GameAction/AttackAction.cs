using UnityEngine;

[CreateAssetMenu(fileName ="AttackAction",menuName ="ScriptableObject/ActionData/AttackAction")]
public class AttackAction : GameAction
{
    public override void OnExecute(SkillContext ctx)
    {
        foreach (var target in ctx.Targets)
        {
            // 죽는 순간을 잡으려면 때리기 "전에" 확인해야 합니다. 맞고 나서 IsDead를 보면
            // 이미 죽어 있던 대상과 이번에 죽은 대상을 구별할 수 없습니다.
            bool wasDead = target.IsDead;

            int applied = target.TakeDamage(ctx.Amount);

            ctx.Receipt.Add(new BattleStep(
                ctx.Caster, ctx.Spec, target, EBattleEffect.Damage,
                ctx.Amount, applied, target.CurrentHP, target.Shield, !wasDead && target.IsDead));
        }
    }
}
