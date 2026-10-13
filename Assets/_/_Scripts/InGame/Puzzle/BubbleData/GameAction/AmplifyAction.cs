using UnityEngine;

[CreateAssetMenu(fileName = "AmplifyAction", menuName = "ScriptableObject/ActionData/AmplifyAction")]
public class AmplifyAction : GameAction
{
    [SerializeField, Min(1f)]
    private float maximumAmplification = 2f;

    public override bool RequiresTarget => false;
    public override bool UsesSkillPower => false;
    public override bool IsPreemptive => true;

    public override void OnExecute(SkillContext ctx)
    {
        ctx?.Batch?.AddAmplification(ctx.Value, maximumAmplification);
    }
}
