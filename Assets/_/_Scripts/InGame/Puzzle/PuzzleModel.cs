using System;
using UnityEngine;
using System.Collections.Generic;

using System.Linq;
using System.Text;

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
    }
    private void SetBubbleAt(int x, int y, Bubble bubble)
    {
        bubbles[x][y] = bubble;
        if (bubble != null)
        {
            bubble.Pos = new Vector2Int(x, y);
        }
    }
    public void SetBubbles(Action callback)
    {
        bubbles = new Bubble[Size][];
        for (int i = 0; i < Size; i++)
        {
            bubbles[i] = new Bubble[Size];
        }

        InitializeBoard();
        callback?.Invoke();
        // 디버깅 로그 출력
        StringBuilder sb = new StringBuilder();
        for (int i = 0; i < Size; i++)
        {
            for (int j = 0; j < Size; j++)
            {
                sb.Append(bubbles[i][j].Spec.SOName + "/");
            }
            sb.Append("\n");
        }
        Debug.Log(sb.ToString());
        puzzleManager.ReceiveCompleteSignal();
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
            ProcessChainReaction(ret);
        }
        return ret;
    }
    private void SwapData(Vector2Int a, Vector2Int b)
    {
        Bubble tempA = bubbles[a.x][a.y];
        Bubble tempB = bubbles[b.x][b.y];

        SetBubbleAt(a.x, a.y, tempB);
        SetBubbleAt(b.x, b.y, tempA);
    }
    private void ProcessChainReaction(MoveReceipt receipt)
    {
        bool hasMoreMatches = true;
        while (hasMoreMatches)
        {
            foreach (var pos in receipt.MatchPositions)
            {
                var target = bubbles[pos.x][pos.y];
                if (target != null)
                {
                    target.ReturnToPool();
                    SetBubbleAt(pos.x, pos.y, null); // null 대입 시에도 메서드 사용
                }
            }

            ApplyGravity(receipt);
            FillEmptySlots(receipt);

            List<Vector2Int> newMatches = GetAllMatches();
            if (newMatches.Count > 0)
            {
                receipt.MatchPositions = newMatches;
                hasMoreMatches = true;
            }
            else
            {
                hasMoreMatches = false;
            }
        }
    }
    private List<Vector2Int> GetAllMatches()
    {
        HashSet<Vector2Int> allMatches = new HashSet<Vector2Int>();
        HashSet<Vector2Int> visited = new HashSet<Vector2Int>();

        for (int x = 0; x < Size; x++)
        {
            for (int y = 0; y < Size; y++)
            {
                Vector2Int pos = new Vector2Int(x, y);
                if (visited.Contains(pos) || bubbles[x][y] == null) continue;

                // 이미 구현하신 GetConnectedBubbles 활용
                var connected = GetConnectedBubbles(pos, bubbles[x][y].Spec.SOName);

                // 방문 처리 (성능 최적화)
                foreach (var p in connected) visited.Add(p);

                if (connected.Count >= 3)
                {
                    allMatches.UnionWith(connected);
                }
            }
        }
        return allMatches.ToList();
    }
    private void ApplyGravity(MoveReceipt receipt)
    {
        for (int x = 0; x < Size; x++)
        {
            int emptyRow = -1;
            for (int y = 0; y < Size; y++)
            {
                if (bubbles[x][y] == null)
                {
                    if (emptyRow == -1) emptyRow = y;
                }
                else if (emptyRow != -1)
                {
                    Bubble data = bubbles[x][y];

                    SetBubbleAt(x, emptyRow, data); // 이동 및 위치 기록
                    SetBubbleAt(x, y, null);        // 이전 자리 비움

                    receipt.GravityMoves.Add(new MoveStep(data, new Vector2Int(x, y), new Vector2Int(x, emptyRow)));
                    emptyRow++;
                }
            }
        }
    }
    private void FillEmptySlots(MoveReceipt receipt)
    {
        for (int x = 0; x < Size; x++)
        {
            int fillCount = 0;
            for (int y = Size - 1; y >= 0; y--)
            {
                if (bubbles[x][y] == null)
                {
                    Bubble newData = puzzleManager.RequestNewBubbleData();

                    SetBubbleAt(x, y, newData); // 생성 및 위치 기록

                    Vector2Int spawnPos = new Vector2Int(x, Size + fillCount);
                    Vector2Int targetPos = new Vector2Int(x, y);
                    receipt.RefillMoves.Add(new MoveStep(newData, spawnPos, targetPos));
                    fillCount++;
                }
            }
        }
    }
    public void InitializeBoard()
    {
        bool isBoardPlayable = false;
        while (!isBoardPlayable)
        {
            // [수정] 다시 루프를 돌 때 기존에 배치했던 버블들을 싹 다 풀로 안전하게 반환
            ClearBoardAndPool();

            for (int x = 0; x < Size; x++)
            {
                for (int y = 0; y < Size; y++)
                {
                    Bubble newData;
                    // 초기 배치 시 3매치가 나지 않도록 계속 리롤치는 구간
                    // (이 구간에서 폐기되는 버블들도 풀에 돌려주어야 합니다)
                    do
                    {
                        // 만약 이전에 실패한 버블이 이 자리에 있다면 풀로 반환
                        if (bubbles[x][y] != null) bubbles[x][y].ReturnToPool();

                        newData = puzzleManager.RequestNewBubbleData();
                        SetBubbleAt(x, y, newData);
                    } while (CheckInitialMatch(x, y));
                }
            }

            if (CanAnyMatchExist()) isBoardPlayable = true;
        }
    }
    // 초기 배치용 간이 매치 체크 (왼쪽 2칸, 아래쪽 2칸만 확인)
    private bool CheckInitialMatch(int x, int y)
    {
        string currentName = bubbles[x][y].Spec.SOName;

        // 가로 체크 (왼쪽으로 2칸)
        if (x >= 2 &&
            bubbles[x - 1][y]?.Spec.SOName == currentName &&
            bubbles[x - 2][y]?.Spec.SOName == currentName) return true;

        // 세로 체크 (아래쪽으로 2칸)
        if (y >= 2 &&
            bubbles[x][y - 1]?.Spec.SOName == currentName &&
            bubbles[x][y - 2]?.Spec.SOName == currentName) return true;

        return false;
    }
    public MoveReceipt ShuffleBoard()
    {
        MoveReceipt ret = new MoveReceipt();
        List<Bubble> allExistingBubbles = new List<Bubble>();

        for (int x = 0; x < Size; x++)
        {
            for (int y = 0; y < Size; y++)
            {
                if (bubbles[x][y] != null) allExistingBubbles.Add(bubbles[x][y]);
            }
        }

        bool isValid = false;
        // [개선] 검증 단계에서는 실물 보드(bubbles)를 건드리지 않고 리스트 셔플만 돌립니다.
        while (!isValid)
        {
            allExistingBubbles = allExistingBubbles.OrderBy(a => Guid.NewGuid()).ToList();

            // 임시로 실물 보드에 배치해보고 검증
            int index = 0;
            for (int x = 0; x < Size; x++)
            {
                for (int y = 0; y < Size; y++)
                {
                    // 실제 주소값만 잠시 링크를 바꿔서 테스트
                    bubbles[x][y] = allExistingBubbles[index++];
                }
            }

            // 검증 통과하면 탈출, 실패하면 실물 버블 파괴 없이 리스트 순서만 다시 섞음
            if (GetAllMatches().Count == 0 && CanAnyMatchExist())
            {
                isValid = true;
            }
        }

        // [추가] 최종 확정된 배치 상태를 기반으로 포지션 값 동기화
        for (int x = 0; x < Size; x++)
        {
            for (int y = 0; y < Size; y++)
            {
                if (bubbles[x][y] != null)
                {
                    bubbles[x][y].Pos = new Vector2Int(x, y);
                    ret.GravityMoves.Add(new MoveStep(bubbles[x][y], new Vector2Int(-1, -1), new Vector2Int(x, y)));
                }
            }
        }

        return ret;
    }
    public bool CanAnyMatchExist()
    {
        for (int x = 0; x < Size; x++)
        {
            for (int y = 0; y < Size; y++)
            {
                Vector2Int current = new Vector2Int(x, y);

                // 인접한 상하좌우와 가상으로 바꿔보고 매치가 되는지 확인
                foreach (var dir in _directions)
                {
                    Vector2Int next = current + dir;
                    if (!IsInBounds(next)) continue;

                    // 가상 스왑
                    SwapData(current, next);
                    bool matchFound = IsMatchable(current) || IsMatchable(next);
                    // 원상 복구
                    SwapData(current, next);

                    if (matchFound) return true;
                }
            }
        }
        return false;
    }
    private void ClearBoardAndPool()
    {
        if (bubbles == null) return;

        for (int x = 0; x < Size; x++)
        {
            for (int y = 0; y < Size; y++)
            {
                if (bubbles[x][y] != null)
                {
                    bubbles[x][y].ReturnToPool();
                    SetBubbleAt(x, y, null);
                }
            }
        }
    }
        //변경사항 모델로 이관
    public bool IsAdjacent(Vector2Int posA, Vector2Int posB)
    {
        return (posA - posB).sqrMagnitude == 1;
    }
}