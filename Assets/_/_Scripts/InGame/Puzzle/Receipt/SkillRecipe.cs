// 매치 그룹 1개로 발동하는 스킬 1건의 기록입니다. (GDD §4.5)
//
// Swap() 시점에 작성되고, 연출 중 팝 직후 콜백에서 소비됩니다.
public class SkillRecipe
{
    // [중요] Bubble이 아니라 BubbleSO를 잡습니다.
    //
    // Bubble.ReturnToPool()이 _spec = null을 하고 그 호출이 팝 트윈의 OnComplete에
    // 걸려 있습니다. 즉 콜백이 불리는 시점엔 Bubble.Spec이 이미 null입니다.
    // 연출 중에 조회하면 100% 실패하므로 작성 시점에 스냅샷으로 확보합니다. (AGENT.md §3)
    public BubbleSO Spec { get; }

    // 이 매치 그룹으로 터진 버블 개수. 최종 수치 = value * MatchCount * chainWeight (GDD §4.6)
    public int MatchCount { get; }

    // 발생한 연쇄 차수. 1-based입니다. (GDD §4.5)
    public int ChainIndex { get; }

    // 스킬 실행은 멱등이 아닙니다.
    //
    // 위치는 ReconcileViewsToModel()로 재보정해도 안전하지만 데미지는 아닙니다.
    // "콜백이 안 불렸을까 봐" 보조 경로를 두면 즉시 이중 적용이 됩니다.
    // 소비 주체는 PuzzleManager 한 곳뿐이며, 여기서만 이 플래그를 세웁니다. (AGENT.md §4의 반납 주체 규칙과 같은 이유)
    public bool Consumed { get; set; }

    public SkillRecipe(BubbleSO spec, int matchCount, int chainIndex)
    {
        Spec = spec;
        MatchCount = matchCount;
        ChainIndex = chainIndex;
    }
}
