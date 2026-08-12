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
    private bool IsInBounds(Vector2Int next)
    {
        return next.x >= 0 && next.x < Size && next.y >= 0 && next.y < Size;
    }

    // 보드 밖이거나 빈 칸이면 null을 돌려주는 안전 조회.
    // null은 어떤 이름과도 같지 않으므로 런(run) 계산에서 자연스럽게 경계 역할을 합니다.
    private string NameAt(int x, int y)
    {
        if (x < 0 || x >= Size || y < 0 || y >= Size) return null;
        return bubbles[x][y]?.Spec?.SOName;
    }

    // [기획 규칙] 매치는 "가로 또는 세로 직선 3개 이상"만 인정합니다.
    // ㄱ/ㄴ/T자 같은 꺾인 연결은 매치가 아닙니다.
    // 단, 가로 런과 세로 런이 각각 3개 이상이면서 한 칸을 공유하는 경우(T/L자)는
    // 양쪽 직선이 모두 성립한 것이므로 둘 다 포함합니다.
    private HashSet<Vector2Int> GetLineMatchesAt(Vector2Int pos)
    {
        HashSet<Vector2Int> result = new HashSet<Vector2Int>();
        if (!IsInBounds(pos)) return result;

        string name = NameAt(pos.x, pos.y);
        if (string.IsNullOrEmpty(name)) return result;

        // 가로 런
        int left = pos.x;
        while (NameAt(left - 1, pos.y) == name) left--;
        int right = pos.x;
        while (NameAt(right + 1, pos.y) == name) right++;
        if (right - left + 1 >= 3)
        {
            for (int x = left; x <= right; x++) result.Add(new Vector2Int(x, pos.y));
        }

        // 세로 런
        int down = pos.y;
        while (NameAt(pos.x, down - 1) == name) down--;
        int up = pos.y;
        while (NameAt(pos.x, up + 1) == name) up++;
        if (up - down + 1 >= 3)
        {
            for (int y = down; y <= up; y++) result.Add(new Vector2Int(pos.x, y));
        }

        return result;
    }

    // 시작 칸에서 성립한 직선 매치를 기점으로, 그 안의 칸들이 가진 직교 방향 직선까지
    // 더 이상 늘지 않을 때까지 확장합니다. (T/L자 매치의 팔 전체를 한 번에 처리)
    private HashSet<Vector2Int> GetLineMatchGroup(Vector2Int start)
    {
        HashSet<Vector2Int> group = GetLineMatchesAt(start);
        if (group.Count == 0) return group;

        Stack<Vector2Int> pending = new Stack<Vector2Int>(group);
        while (pending.Count > 0)
        {
            Vector2Int current = pending.Pop();
            foreach (var p in GetLineMatchesAt(current))
            {
                if (group.Add(p)) pending.Push(p);
            }
        }
        return group;
    }

    public bool IsInBoardRange(Vector2Int pos) => IsInBounds(pos);

    public Bubble GetBubbleAt(Vector2Int pos)
    {
        return IsInBounds(pos) ? bubbles[pos.x][pos.y] : null;
    }

    // 유저에게 보여줄 힌트를 한 건 찾습니다.
    //
    // 반환 좌표는 "실제로 터질 버블들이 지금 있는 자리"입니다.
    // 스왑 후 좌표를 그대로 주면 안 됩니다. 매치가 성립하는 칸 중 하나에는
    // 아직 밀려날 무관한 버블이 앉아 있어서, 그 버블까지 강조되어 버립니다.
    // 따라서 [매치 칸들] 에서 [스왑으로 채워질 칸]을 빼고, 그 자리를 채울 버블의
    // 현재 위치(moveFrom)를 대신 넣습니다.
    public bool TryFindHint(out List<Vector2Int> hintCells)
    {
        hintCells = new List<Vector2Int>();

        for (int x = 0; x < Size; x++)
        {
            for (int y = 0; y < Size; y++)
            {
                Vector2Int current = new Vector2Int(x, y);
                if (bubbles[x][y] == null) continue;

                foreach (var dir in _directions)
                {
                    Vector2Int next = current + dir;
                    if (!IsInBounds(next) || bubbles[next.x][next.y] == null) continue;

                    // 가상 스왑 -> 판정 -> 원상 복구
                    SwapData(current, next);

                    HashSet<Vector2Int> matched = GetLineMatchGroup(current);
                    Vector2Int origin = current;
                    if (matched.Count == 0)
                    {
                        matched = GetLineMatchGroup(next);
                        origin = next;
                    }

                    SwapData(current, next);

                    if (matched.Count > 0)
                    {
                        // origin = 스왑으로 채워질 칸. 지금 저기 있는 버블은 밀려날 버블이므로 제외합니다.
                        // 그 자리를 채울 버블은 반대편(moveFrom)에 있으니 그쪽을 대신 넣습니다.
                        Vector2Int moveFrom = (origin == current) ? next : current;

                        foreach (var cell in matched)
                        {
                            if (cell == origin) continue;
                            hintCells.Add(cell);
                        }
                        hintCells.Add(moveFrom);
                        return true;
                    }
                }
            }
        }
        return false;
    }

    public bool IsMatchable(Vector2Int start)
    {
        return GetLineMatchesAt(start).Count >= 3;
    }
    public List<Vector2Int> GetMatchList(Vector2Int start)
    {
        return GetLineMatchGroup(start).ToList();
    }
    public MoveReceipt Swap(Vector2Int selectedBubblesPos, Vector2Int targetBubblesPos)
    {
        MoveReceipt ret = new MoveReceipt();

        // [중요] 스왑을 수행하기 "전에" 각 좌표의 버블 참조를 확보합니다.
        // SwapData() 이후에 bubbles[]를 다시 읽으면 이미 자리를 맞바꾼 상대편 버블이 잡히고,
        // 그 결과 Data와 From/To의 짝이 엇갈려 "이동 거리 0"짜리 트윈이 만들어집니다.
        Bubble bubbleAtSelected = bubbles[selectedBubblesPos.x][selectedBubblesPos.y];
        Bubble bubbleAtTarget = bubbles[targetBubblesPos.x][targetBubblesPos.y];

        SwapData(selectedBubblesPos, targetBubblesPos);
        ret.SwapMoves.Add(new MoveStep(bubbleAtSelected, selectedBubblesPos, targetBubblesPos));
        ret.SwapMoves.Add(new MoveStep(bubbleAtTarget, targetBubblesPos, selectedBubblesPos));

        List<Vector2Int> selectedPosList = GetMatchList(selectedBubblesPos);
        List<Vector2Int> targetPosList = GetMatchList(targetBubblesPos);

        if (selectedPosList.Count < 1 && targetPosList.Count < 1)
        {
            SwapData(selectedBubblesPos, targetBubblesPos);

            // 롤백은 각자 "원래 자리"로 되돌아가는 이동입니다.
            // 뷰는 SwapMoves[2]를 [0]과 동일한 버블로 간주하므로 순서를 맞춰야 합니다.
            ret.SwapMoves.Add(new MoveStep(bubbleAtSelected, targetBubblesPos, selectedBubblesPos));
            ret.SwapMoves.Add(new MoveStep(bubbleAtTarget, selectedBubblesPos, targetBubblesPos));
        }
        else
        {
            // 5. 연쇄 로직 시작 (성립 중인 매치는 ProcessChainReaction이 직접 조회합니다)
            ProcessChainReaction(ret);

            // 6. 연쇄가 끝난 보드에 둘 수 있는 수가 하나도 없으면(데드락) 자동으로 다시 섞습니다.
            //    롤백된 스왑은 보드를 바꾸지 않으므로 검사할 필요가 없습니다.
            if (!CanAnyMatchExist())
            {
                Debug.Log("[Deadlock] 둘 수 있는 수가 없어 보드를 다시 섞습니다.");
                ShuffleBoard(ret);
            }
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
        // 스왑 직후 보드에 성립해 있는 매치가 곧 1차 연쇄입니다.
        // 시드 좌표를 넘겨받지 않고 여기서 직접 조회합니다. 스왑한 두 칸의 그룹을 합쳐서
        // 넘기면, 두 칸이 같은 그룹에 속한 경우(같은 SOName을 서로 맞바꾼 경우) 같은 그룹이
        // 두 번 담겨 스킬이 두 번 발동합니다.
        List<HashSet<Vector2Int>> currentGroups = GetAllMatchGroups();

        while (currentGroups.Count > 0)
        {
            ChainStep currentStep = new ChainStep();

            // 연쇄 차수는 1-based입니다. (GDD §4.5) 아직 이번 스텝을 담기 전이므로 +1.
            int chainIndex = receipt.ChainSteps.Count + 1;

            // 1. 이번 연쇄 단계에서 터진 버블을 매치 그룹 단위로 기록
            //    (ReturnToPool은 호출하지 않음 - 뷰 연출 완료 시점으로 미룸)
            foreach (var group in currentGroups)
            {
                List<MoveStep> groupMoves = new List<MoveStep>();
                BubbleSO groupSpec = null;

                foreach (var pos in group)
                {
                    var targetBubble = bubbles[pos.x][pos.y];
                    if (targetBubble == null) continue;

                    // [중요] 스펙은 지금 확보합니다. 연출 중에는 Bubble.Spec이 이미 null입니다.
                    // 같은 그룹은 매치 규칙상 SOName이 모두 같으므로 하나만 잡으면 됩니다. (AGENT.md §3)
                    if (groupSpec == null) groupSpec = targetBubble.Spec;

                    groupMoves.Add(new MoveStep(targetBubble, pos, pos));
                    SetBubbleAt(pos.x, pos.y, null);
                }

                if (groupMoves.Count == 0) continue;

                currentStep.MatchGroups.Add(groupMoves);

                // 매치 그룹 1개 = 스킬 레시피 1건. 평면으로 세면 보드 양쪽의 무관한 3매치가
                // 6개짜리 하나로 뭉쳐 데미지가 두 배가 됩니다. (GDD §4.5)
                if (groupSpec != null)
                {
                    currentStep.SkillRecipes.Add(new SkillRecipe(groupSpec, groupMoves.Count, chainIndex));
                }
            }

            // 선(先)배치 실행 규칙 - 증폭/버프를 이 스텝의 가장 앞으로 당깁니다. (GDD §4.5)
            //
            // 정렬 범위는 이 ChainStep의 리스트 하나뿐입니다. 앞선 스텝으로 소급되면
            // 이미 발동이 끝난 스킬의 수치가 뒤늦게 바뀝니다.
            // OrderBy는 안정 정렬이라 증폭이 아닌 것들끼리의 순서는 보존됩니다.
            if (currentStep.SkillRecipes.Count > 1)
            {
                currentStep.SkillRecipes = currentStep.SkillRecipes
                    .OrderByDescending(r => r.Spec != null && r.Spec.action != null && r.Spec.action.IsPreemptive)
                    .ToList();
            }

            // 2. 중력 및 리필 기록 (currentStep에 기록)
            ApplyGravity(currentStep);
            FillEmptySlots(currentStep);

            // 3. 이번 단계 연쇄 영수증을 메인 영수증에 추가
            receipt.ChainSteps.Add(currentStep);

            // 4. 다음 연쇄 매치 탐색
            currentGroups = GetAllMatchGroups();
        }
    }
    // 보드 전체에서 성립 중인 매치를 "그룹 단위"로 수집합니다.
    //
    // 예전에는 여기서 가로/세로 런을 따로 스캔했는데, 그건 GetLineMatchGroup과
    // 같은 질문("무엇이 매치인가")에 답하는 두 번째 구현이었습니다. (AGENT.md §5)
    // 지금은 GetLineMatchGroup 하나만 쓰고, 덤으로 그룹 경계가 보존됩니다.
    private List<HashSet<Vector2Int>> GetAllMatchGroups()
    {
        List<HashSet<Vector2Int>> groups = new List<HashSet<Vector2Int>>();
        HashSet<Vector2Int> visited = new HashSet<Vector2Int>();

        for (int x = 0; x < Size; x++)
        {
            for (int y = 0; y < Size; y++)
            {
                Vector2Int pos = new Vector2Int(x, y);
                if (visited.Contains(pos)) continue;

                HashSet<Vector2Int> group = GetLineMatchGroup(pos);
                if (group.Count == 0) continue;

                // 같은 그룹의 나머지 칸을 다시 시작점으로 삼으면 그룹이 중복 생성됩니다.
                foreach (var p in group) visited.Add(p);
                groups.Add(group);
            }
        }

        return groups;
    }
    private void ApplyGravity(ChainStep step)
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

                    step.GravityMoves.Add(new MoveStep(data, new Vector2Int(x, y), new Vector2Int(x, emptyRow)));
                    emptyRow++;
                }
            }
        }
    }
    private void FillEmptySlots(ChainStep step)
    {
        for (int x = 0; x < Size; x++)
        {
            int fillCount = 0;
            // 버그 수정: 아래(y = 0)부터 위(y = Size - 1)로 스캔하여 스폰 높이 역전 방지
            for (int y = 0; y < Size; y++)
            {
                if (bubbles[x][y] == null)
                {
                    Bubble newData = puzzleManager.RequestNewBubbleData();

                    SetBubbleAt(x, y, newData); // 생성 및 위치 기록

                    Vector2Int spawnPos = new Vector2Int(x, Size + fillCount);
                    Vector2Int targetPos = new Vector2Int(x, y);
                    step.RefillMoves.Add(new MoveStep(newData, spawnPos, targetPos));
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

            // 최종 안전망: 성립중인 매치가 0개이면서, 둘 수 있는 수가 존재해야 합니다.
            // (배치 로직이 어떤 이유로든 매치를 남기면 여기서 잡아 통째로 다시 깝니다)
            int standing = GetAllMatchGroups().Count;
            if (standing > 0)
            {
                Debug.LogWarning($"[InitializeBoard] 성립중인 매치 그룹이 {standing}개 남아 재생성합니다.");
                continue;
            }

            if (CanAnyMatchExist()) isBoardPlayable = true;
        }
    }
    // 초기 배치용 매치 체크.
    // [중요] 실제 매치 판정과 반드시 동일한 규칙(직선 3개 이상)을 써야 합니다.
    // 두 규칙이 어긋나면 "터지지 않는 매치"나 "시작하자마자 터지는 보드"가 생깁니다.
    // 아직 배치되지 않은 칸은 null이라 런 계산에서 자동으로 경계 처리됩니다.
    private bool CheckInitialMatch(int x, int y)
    {
        return GetLineMatchesAt(new Vector2Int(x, y)).Count > 0;
    }
    private const int ShuffleMaxAttempts = 500;

    // 보드의 버블을 파괴하지 않고 자리만 다시 섞습니다.
    // 결과 이동은 receipt.ShuffleMoves에 담깁니다.
    public void ShuffleBoard(MoveReceipt receipt)
    {
        List<Bubble> allExistingBubbles = new List<Bubble>();

        // [중요] 셔플 "전" 좌표를 미리 스냅샷으로 떠 둡니다.
        // 아래 검증에서 호출하는 CanAnyMatchExist()가 내부적으로 SwapData -> SetBubbleAt을 돌려
        // Bubble.Pos를 현재 보드 좌표로 덮어쓰기 때문에, Pos를 나중에 읽으면 출발지를 잃습니다.
        Dictionary<Bubble, Vector2Int> originPos = new Dictionary<Bubble, Vector2Int>();

        for (int x = 0; x < Size; x++)
        {
            for (int y = 0; y < Size; y++)
            {
                Bubble b = bubbles[x][y];
                if (b == null) continue;
                allExistingBubbles.Add(b);
                originPos[b] = new Vector2Int(x, y);
            }
        }

        bool isValid = false;
        int attempts = 0;
        // 검증 단계에서는 버블을 파괴하지 않고 배열 링크만 바꿔가며 시도합니다.
        while (!isValid && attempts < ShuffleMaxAttempts)
        {
            attempts++;
            allExistingBubbles = allExistingBubbles.OrderBy(a => Guid.NewGuid()).ToList();

            int index = 0;
            for (int x = 0; x < Size; x++)
            {
                for (int y = 0; y < Size; y++)
                {
                    bubbles[x][y] = allExistingBubbles[index++];
                }
            }

            // 이미 터진 상태로 시작하면 안 되고(매치 0), 둘 수 있는 수는 있어야 합니다.
            if (GetAllMatchGroups().Count == 0 && CanAnyMatchExist()) isValid = true;
        }

        if (!isValid)
        {
            // 현재 버블 구성으로는 조건을 만족하는 배치를 못 찾은 경우.
            // 무한 루프로 에디터를 얼리지 않도록 빠져나오되, 눈에 띄게 알립니다.
            Debug.LogError($"[ShuffleBoard] {ShuffleMaxAttempts}회 시도했지만 유효한 배치를 찾지 못했습니다. " +
                           $"버블 종류 수가 너무 적거나 보드 구성이 편향되었을 수 있습니다.");
        }

        // 확정된 배치로 Pos를 동기화하면서, 실제로 자리가 바뀐 버블만 이동으로 기록합니다.
        for (int x = 0; x < Size; x++)
        {
            for (int y = 0; y < Size; y++)
            {
                Bubble b = bubbles[x][y];
                if (b == null) continue;

                Vector2Int to = new Vector2Int(x, y);
                b.Pos = to;

                if (originPos.TryGetValue(b, out Vector2Int from) && from != to)
                {
                    receipt.ShuffleMoves.Add(new MoveStep(b, from, to));
                }
            }
        }
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