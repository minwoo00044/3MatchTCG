using System.Collections.Generic;

public class ChainStep
{
    // 1. 이번 콤보/연쇄 단계에서 터진 버블 덩어리들
    //
    // 평면 목록이 아니라 덩어리별로 나눠 담습니다. (GDD §4.5)
    // 스킬 1건 = 덩어리 1개이므로, 여기서 경계를 잃으면 개수를 셀 수 없습니다.
    // (보드 양쪽에서 무관한 3매치가 동시에 성립하면 평면 목록에서는 6개로 뭉쳐 보입니다)
    //
    // 여기까지가 퍼즐이 아는 전부입니다. 이 덩어리가 어떤 스킬이 되고 누가 시전하는지는
    // BattleManager가 해석합니다.
    public List<MatchGroup> MatchGroups { get; set; } = new List<MatchGroup>();

    // 2. 이번 콤보/연쇄 단계에서 중력으로 떨어진 이동들
    public List<MoveStep> GravityMoves { get; set; } = new List<MoveStep>();

    // 3. 이번 콤보/연쇄 단계에서 리필된 이동들
    public List<MoveStep> RefillMoves { get; set; } = new List<MoveStep>();
}
