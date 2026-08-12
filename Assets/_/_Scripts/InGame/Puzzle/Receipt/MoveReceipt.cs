using System.Collections.Generic;
using UnityEngine;
public class MoveReceipt
{
    // 1. 유저의 액션에 의한 직접적인 스왑 (교체 연출용)
    public List<MoveStep> SwapMoves { get; set; } = new List<MoveStep>();

    // 2. 1차 연쇄, 2차 연쇄, 3차 연쇄... 단계별 연쇄 목록!
    public List<ChainStep> ChainSteps { get; set; } = new List<ChainStep>();

    // 3. 연쇄가 모두 끝난 뒤 둘 수 있는 수가 없어(데드락) 보드를 다시 섞은 경우의 이동들.
    //    연쇄와는 성격이 다르므로 ChainStep에 섞지 않고 별도로 보관합니다.
    public List<MoveStep> ShuffleMoves { get; set; } = new List<MoveStep>();

    // 연쇄가 일어났는지 여부
    public bool IsChainOccurred => ChainSteps.Count > 0;

    // 연출할 거리가 하나라도 있는지 (스왑 이후 단계가 존재하는지)
    public bool HasPostSwapAction => ChainSteps.Count > 0 || ShuffleMoves.Count > 0;
}