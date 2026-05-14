using System;
using UnityEngine;
using System.Collections.Generic;

using System.Linq;

public class PuzzleModel
{
    private Bubble[][] bubbles;
    private PuzzleManager puzzleManager;
    static readonly private Vector2Int[] _directions = { Vector2Int.up, Vector2Int.down, Vector2Int.left, Vector2Int.right };
    public int Size { get; private set; }

    public PuzzleModel(PuzzleManager puzzleManager, int size)
    {
        this.puzzleManager = puzzleManager;
        this.Size = size;
        SetBubbles(size);
    }
    private void SetBubbles(int size)
    {
        Size = size;
        bubbles = new Bubble[size][];
        for (int i = 0; i < size; i++)
        {
            bubbles[i] = new Bubble[size];
        }
    }
    private HashSet<Vector2Int> GetConnectedBubbles(Vector2Int start, string soName)
    {
        HashSet<Vector2Int> connected = new HashSet<Vector2Int>();
        Stack<Vector2Int> stack = new Stack<Vector2Int>();

        stack.Push(start);
        connected.Add(start);

        while (stack.Count > 0)
        {
            Vector2Int current = stack.Pop();

            // 상하좌우 4방향 체크
            foreach (Vector2Int dir in _directions) // {Up, Down, Left, Right}
            {
                Vector2Int next = current + dir;

                // 1. 보드 범위 안인지 2. 이미 체크했는지 3. 동일한 SO 인지 확인
                if (IsInBounds(next) && !connected.Contains(next) &&
                    bubbles[next.x][next.y]?.Spec.SOName == soName)
                {
                    connected.Add(next);
                    stack.Push(next);
                }
            }
        }
        return connected;
    }
    private bool IsInBounds(Vector2Int next)
    {
        return next.x >= 0 && next.x < Size && next.y >= 0 && next.y < Size;
    }

    public bool IsMatchable(Vector2Int start)
    {
        var bubble = bubbles[start.x][start.y];
        if (bubble == null) return false;

        // 연결된 개수가 3개 이상인지 확인
        return GetConnectedBubbles(start, bubble.Spec.SOName).Count >= 3;
    }
    public List<Vector2Int> GetMatchList(Vector2Int start)
    {
        var bubble = bubbles[start.x][start.y];
        if (bubble == null) return new List<Vector2Int>();

        var connected = GetConnectedBubbles(start, bubble.Spec.SOName);

        // 3개 이상일 때만 리스트 반환, 아니면 빈 리스트
        return connected.Count >= 3 ? connected.ToList() : new List<Vector2Int>();
    }
    public MoveReceipt Swap(Vector2Int selectedBubblesPos, Vector2Int targetBubblesPos)
    {
        MoveReceipt ret = new MoveReceipt();
        SwapData(selectedBubblesPos, targetBubblesPos);
        ret.SwapMoves.Add(new MoveStep(bubbles[selectedBubblesPos.x][selectedBubblesPos.y], selectedBubblesPos, targetBubblesPos));
        ret.SwapMoves.Add(new MoveStep(bubbles[targetBubblesPos.x][targetBubblesPos.y], targetBubblesPos, selectedBubblesPos));


        List<Vector2Int> selectedPosList = GetMatchList(selectedBubblesPos);
        List<Vector2Int> targetPosList = GetMatchList(targetBubblesPos);
        if (selectedPosList.Count < 1 && targetPosList.Count < 1)
        {
            SwapData(selectedBubblesPos, targetBubblesPos);
            ret.SwapMoves.Add(new MoveStep(bubbles[selectedBubblesPos.x][selectedBubblesPos.y], selectedBubblesPos, targetBubblesPos));
            ret.SwapMoves.Add(new MoveStep(bubbles[targetBubblesPos.x][targetBubblesPos.y], targetBubblesPos, selectedBubblesPos));
        }
        else
        {
            HashSet<Vector2Int> allMatchPos = new HashSet<Vector2Int>(selectedPosList);
            allMatchPos.UnionWith(targetPosList);
            ret.MatchPositions = allMatchPos.ToList();

            // 5. 연쇄 로직 시작: 데이터 삭제 -> 중력 -> 리필 (재귀 또는 반복)
            //ProcessChainReaction(ret);
        }
        return ret;
    }
    private void SwapData(Vector2Int a, Vector2Int b)
    {
        Bubble temp = bubbles[a.x][a.y];
        bubbles[a.x][a.y] = bubbles[b.x][b.y];
        bubbles[b.x][b.y] = temp;
    }
    private void ProcessChainReaction(MoveReceipt receipt)
    {
        // 1. 매치된 버블 데이터 삭제 (null 처리)
        foreach (var pos in receipt.MatchPositions)
        {
            bubbles[pos.x][pos.y] = null;
            //데이터 비워서 풀로 돌려보내는 작동 추가
        }

        // 2. 중력 작용 (아래로 떨어뜨리기)
        // bubbles[x][y] 구조이므로 x(열) 단위로 처리하면 매우 쉽습니다.
        for (int x = 0; x < Size; x++)
        {
            int emptyRow = -1;
            for (int y = 0; y < Size; y++)
            {
                if (bubbles[x][y] == null)
                {
                    if (emptyRow == -1) emptyRow = y; // 가장 낮은 빈칸 위치 저장
                }
                else if (emptyRow != -1)
                {
                    // 빈칸 위로 데이터가 발견되면 아래로 이동
                    Bubble data = bubbles[x][y];
                    bubbles[x][emptyRow] = data;
                    bubbles[x][y] = null;

                    receipt.GravityMoves.Add(new MoveStep(data, new Vector2Int(x, y), new Vector2Int(x, emptyRow)));
                    
                    // 다시 가장 낮은 빈칸 찾기 (현재 y가 null이 되었으므로 순차적으로 올라감)
                    emptyRow++;
                }
            }
        }

        // 3. 리필 (새로운 버블 생성 요청)
        // 이 부분에서 이전에 설계한 팩토리와 풀을 통해 데이터를 채웁니다.
        //FillEmptySlots(receipt);
    }
}