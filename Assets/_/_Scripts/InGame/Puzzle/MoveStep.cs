using UnityEngine;
public class MoveStep
{
    public Bubble Data { get; }          // 이동하는 데이터 객체
    public Vector2Int FromPos { get; }   // 시작 논리 좌표
    public Vector2Int ToPos { get; }     // 목표 논리 좌표

    public MoveStep(Bubble data, Vector2Int from, Vector2Int to)
    {
        Data = data;
        FromPos = from;
        ToPos = to;
    }
}