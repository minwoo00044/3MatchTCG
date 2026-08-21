// 스킬 1건의 발동 지시서. (GDD §4.5)
//
// 퍼즐은 "무슨 버블이 몇 차에 몇 개 터졌나"까지만 적습니다(MatchGroup).
// 그것을 스킬로 해석해 이 목록을 만드는 것은 BattleManager의 몫입니다.
// 그래서 이 타입은 Action 층에 있고, PuzzleModel은 이런 것이 있는 줄도 모릅니다.
public class SkillRecipe
{
    // 터진 버블의 스펙. MatchGroup이 터뜨리는 시점에 잡아둔 스냅샷입니다.
    // 연출이 끝난 뒤에는 Bubble.Spec이 이미 null이라 여기서만 얻을 수 있습니다. (AGENTS.md §3)
    public BubbleSO Spec { get; }

    // 이 덩어리로 터진 버블 개수. 최종 수치 = value * MatchCount * chainWeight (GDD §4.6)
    public int MatchCount { get; }

    // 발생한 연쇄 차수. 1-based입니다.
    public int ChainIndex { get; }

    public SkillRecipe(BubbleSO spec, int matchCount, int chainIndex)
    {
        Spec = spec;
        MatchCount = matchCount;
        ChainIndex = chainIndex;
    }
}
