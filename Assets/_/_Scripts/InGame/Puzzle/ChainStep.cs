using System.Collections.Generic;

public class ChainStep
{
    // 1. 이번 콤보/연쇄 단계에서 터진 버블 참조 및 좌표 (FromPos == ToPos)
    public List<MoveStep> Matches { get; set; } = new List<MoveStep>();

    // 2. 이번 콤보/연쇄 단계에서 중력으로 떨어진 이동들
    public List<MoveStep> GravityMoves { get; set; } = new List<MoveStep>();

    // 3. 이번 콤보/연쇄 단계에서 리필된 이동들
    public List<MoveStep> RefillMoves { get; set; } = new List<MoveStep>();
}
