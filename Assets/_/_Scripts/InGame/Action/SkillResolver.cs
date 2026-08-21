using System.Collections.Generic;
using System.Linq;

// 퍼즐 사실(MatchGroup)을 전투 레시피와 실행 순서로 번역하는 순수 클래스입니다. (GDD §4.5)
// 실행·타겟팅·수치 적용은 BattleManager 책임이며 여기서는 하지 않습니다.
public sealed class SkillResolver
{
    public List<SkillRecipe> BuildRecipes(MoveReceipt receipt)
    {
        List<SkillRecipe> ret = new List<SkillRecipe>();
        if (receipt == null) return ret;

        for (int i = 0; i < receipt.ChainSteps.Count; i++)
        {
            int chainIndex = i + 1;
            List<SkillRecipe> ofStep = new List<SkillRecipe>();

            foreach (var group in receipt.ChainSteps[i].MatchGroups)
            {
                if (group.Spec == null) continue;
                ofStep.Add(new SkillRecipe(group.Spec, group.Cells.Count, chainIndex));
            }

            if (ofStep.Count > 1)
            {
                // OrderByDescending은 안정 정렬이므로 일반 레시피끼리의 상대 순서를 보존합니다.
                ofStep = ofStep
                    .OrderByDescending(recipe => HasPreemptiveEffect(recipe.Spec))
                    .ToList();
            }

            ret.AddRange(ofStep);
        }

        return ret;
    }

    public List<SkillEffect> GetOrderedEffects(SkillSO spec)
    {
        if (spec == null) return new List<SkillEffect>();

        return spec.Effects
            .Where(effect => effect != null)
            .OrderByDescending(effect => effect.action != null && effect.action.IsPreemptive)
            .ToList();
    }

    private bool HasPreemptiveEffect(SkillSO spec)
    {
        if (spec == null) return false;

        foreach (var effect in spec.Effects)
        {
            if (effect?.action != null && effect.action.IsPreemptive) return true;
        }

        return false;
    }
}
