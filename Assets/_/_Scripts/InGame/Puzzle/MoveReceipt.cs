using System.Collections.Generic;
using UnityEngine;
public class MoveReceipt
{
    // 1. 유저의 액션에 의한 직접적인 스왑 (교체 연출용)
    public List<MoveStep> SwapMoves { get; set; } = new List<MoveStep>();

    // 2. 이번 액션으로 인해 터진 좌표들 (파괴 연출용)
    public List<Vector2Int> MatchPositions { get; set; } = new List<Vector2Int>();

    // 3. 터진 후 공백을 채우기 위해 아래로 떨어진 버블들 (중력 연출용)
    public List<MoveStep> GravityMoves { get; set; } = new List<MoveStep>();

    // 4. 맨 위에서 새롭게 생성되어 들어온 버블들 (리필 연출용)
    public List<MoveStep> RefillMoves { get; set; } = new List<MoveStep>();

    // 연쇄가 일어났는지 여부
    public bool IsChainOccurred => MatchPositions.Count > 0;
}