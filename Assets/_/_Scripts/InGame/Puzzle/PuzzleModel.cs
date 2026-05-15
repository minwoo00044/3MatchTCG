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
    public void SetBubbles()
    {
        bubbles = new Bubble[Size][];
        for (int i = 0; i < Size; i++)
        {
            bubbles[i] = new Bubble[Size];
        }
        InitializeBoard();
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
        Bubble temp = bubbles[a.x][a.y];
        bubbles[a.x][a.y] = bubbles[b.x][b.y];
        bubbles[b.x][b.y] = temp;
    }
    private void ProcessChainReaction(MoveReceipt receipt)
    {
        bool hasMoreMatches = true;
        while (hasMoreMatches)
        {
            // 1. 매치된 버블 데이터 삭제 (null 처리)
            foreach (var pos in receipt.MatchPositions)
            {
                var target = bubbles[pos.x][pos.y];
                target.ReturnToPool(); // 스스로 풀로 귀환
                bubbles[pos.x][pos.y] = null;
            }
            ApplyGravity(receipt);
            FillEmptySlots(receipt);
            List<Vector2Int> newMatches = GetAllMatches();

            if (newMatches.Count > 0)
            {
                receipt.MatchPositions = newMatches; // 다음 루프에서 터뜨릴 위치 갱신
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
    }

    private void FillEmptySlots(MoveReceipt receipt)
    {
        for (int x = 0; x < Size; x++)
        {
            // 각 열의 위쪽부터 빈칸이 몇 개인지 카운트 (연출용 가상 y좌표 설정에 활용)
            int fillCount = 0;

            // 위에서부터 아래로 내려오며 빈칸 채우기 (y의 큰 값부터 0까지)
            for (int y = Size - 1; y >= 0; y--)
            {
                if (bubbles[x][y] == null)
                {
                    // 1. 팩토리로부터 가중치가 반영된 새 데이터 수신
                    // (매니저를 통해 팩토리에 접근하는 구조)
                    Bubble newData = puzzleManager.RequestNewBubbleData();

                    // 2. 모델 배열에 할당 (논리적 실체화)
                    bubbles[x][y] = newData;

                    // 3. 리필 연출을 위한 좌표 설정
                    // 시작점: 보드 바로 위 가상 좌표 (Size + fillCount)
                    // 도착점: 현재 빈칸 좌표 (x, y)
                    Vector2Int spawnPos = new Vector2Int(x, Size + fillCount);
                    Vector2Int targetPos = new Vector2Int(x, y);

                    // 4. 명세서에 기록
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
            // 1. 일단 보드를 터지는 곳 없게 채움
            for (int x = 0; x < Size; x++)
            {
                for (int y = 0; y < Size; y++)
                {
                    Bubble newData;
                    do
                    {
                        newData = puzzleManager.RequestNewBubbleData();
                        bubbles[x][y] = newData;
                    } while (CheckInitialMatch(x, y));
                }
            }

            // 2. [중요] 이 판이 유저가 풀 수 있는 판인지 검사
            if (CanAnyMatchExist())
            {
                isBoardPlayable = true;
            }
            // 만약 데드락이라면? while 루프에 의해 처음부터 다시 생성 (또는 셔플 호출)
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

        // 1. 현재 보드의 모든 데이터를 리스트에 수집
        for (int x = 0; x < Size; x++)
        {
            for (int y = 0; y < Size; y++)
            {
                if (bubbles[x][y] != null) allExistingBubbles.Add(bubbles[x][y]);
            }
        }

        // 2. 유효한 보드가 만들어질 때까지 셔플 반복
        bool isValid = false;
        while (!isValid)
        {
            // 리스트 셔플 (Fisher-Yates 알고리즘 등 사용)
            allExistingBubbles = allExistingBubbles.OrderBy(a => Guid.NewGuid()).ToList();

            // 보드에 재배치
            int index = 0;
            for (int x = 0; x < Size; x++)
            {
                for (int y = 0; y < Size; y++)
                {
                    // 셔플 결과 기록을 위해 이전 좌표 저장 가능 (연출용)
                    // Vector2Int oldPos = bubbles[x][y].CurrentPos; 
                    bubbles[x][y] = allExistingBubbles[index++];
                }
            }

            // 3. 셔플 후 즉시 터지는 게 없고, 매칭 가능한 수(Deadlock 아님)가 있는지 확인
            if (GetAllMatches().Count == 0 && CanAnyMatchExist())
            {
                isValid = true;
            }
        }

        // 4. 셔플 명세서 작성 (모든 버블의 ToPos를 갱신)
        // BoardView에서 전체가 섞이는 연출을 하도록 정보를 담아 보냅니다.
        for (int x = 0; x < Size; x++)
        {
            for (int y = 0; y < Size; y++)
            {
                ret.GravityMoves.Add(new MoveStep(bubbles[x][y], new Vector2Int(-1, -1), new Vector2Int(x, y)));
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
}