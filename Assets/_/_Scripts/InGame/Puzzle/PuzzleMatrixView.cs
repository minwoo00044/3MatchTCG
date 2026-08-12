using System;
using System.Collections.Generic;
using UnityEngine;
using DG.Tweening;

public class PuzzleMatrixView : MonoBehaviour
{
    private Dictionary<Bubble, PuzzleView> dataViewDict = new Dictionary<Bubble, PuzzleView>();
    private PuzzleManager puzzleManager;

    // ===================== 연출 타이밍 =====================
    [Header("TIMING")]
    [SerializeField] private float swapDuration = 0.15f;
    [SerializeField] private float matchDuration = 0.15f;
    [Tooltip("낙하 1칸당 소요 시간(초). 중력/리필은 이동 거리가 제각각이라 고정 시간을 쓰면 속도가 달라 보입니다.")]
    [SerializeField] private float fallSecondsPerCell = 0.07f;
    [Tooltip("아주 짧은 낙하도 이 시간 이상은 보장")]
    [SerializeField] private float fallMinDuration = 0.12f;
    [SerializeField] private float shuffleDuration = 0.45f;

    // 이동 거리에 비례한 낙하 시간. 1칸이든 6칸이든 체감 속도가 같아집니다.
    private float GetFallDuration(Vector2Int from, Vector2Int to)
    {
        float distance = Vector2Int.Distance(from, to);
        return Mathf.Max(fallMinDuration, distance * fallSecondsPerCell);
    }

    public Vector2 GetWorldPos(Vector2Int gridPos)
    {
        return new Vector2(gridPos.x * 1f, gridPos.y * 1f);
    }

    public void DrawingAllMatrix()
    {
        foreach (var pair in dataViewDict)
        {
            Vector2 worldPos = GetWorldPos(pair.Key.Pos);
            pair.Value.transform.SetPositionAndRotation(worldPos, transform.rotation);
            pair.Value.gameObject.SetActive(true);
        }
        puzzleManager.ReceiveCompleteSignal();
    }

    public void Init(PuzzleManager puzzleManager)
    {
        this.puzzleManager = puzzleManager;
    }

    // ===================== 하이라이트 상태 =====================
    // 우선순위: Selected > Hint > Hover
    // 힌트가 호버보다 위입니다. 호버가 힌트를 덮으면 그 버블만 펄스가 끊겨
    // 나머지 힌트 버블과 따로 노는 것처럼 보이기 때문입니다.
    private Bubble hoveredBubble;
    private Bubble selectedBubble;
    private readonly List<Bubble> hintBubbles = new List<Bubble>();

    public void SetHovered(Bubble data)
    {
        if (hoveredBubble == data) return;
        hoveredBubble = data;
        RefreshHighlights();
    }

    // 다른 버블에 Enter가 먼저 들어온 뒤 이전 버블의 Exit가 도착하는 순서 뒤바뀜을 방어합니다.
    public void ClearHoveredIf(Bubble data)
    {
        if (hoveredBubble != data) return;
        SetHovered(null);
    }

    public void SetSelected(Bubble data)
    {
        if (selectedBubble == data) return;
        selectedBubble = data;
        RefreshHighlights();
    }

    public void ShowHint(List<Bubble> cells)
    {
        hintBubbles.Clear();
        if (cells != null) hintBubbles.AddRange(cells);
        RefreshHighlights();
    }

    public void ClearHint()
    {
        if (hintBubbles.Count == 0) return;
        hintBubbles.Clear();
        RefreshHighlights();
    }

    // 연출 시작 등 상태 전환 시 모든 표시를 초기화합니다.
    public void ClearAllHighlights()
    {
        hoveredBubble = null;
        selectedBubble = null;
        hintBubbles.Clear();
        RefreshHighlights();
    }

    private void RefreshHighlights()
    {
        foreach (var pair in dataViewDict)
        {
            EBubbleHighlight state = EBubbleHighlight.None;

            if (pair.Key == hoveredBubble) state = EBubbleHighlight.Hover;
            if (hintBubbles.Count > 0 && hintBubbles.Contains(pair.Key)) state = EBubbleHighlight.Hint;
            if (pair.Key == selectedBubble) state = EBubbleHighlight.Selected;

            pair.Value.SetHighlight(state);
        }
    }

    public void RegistBubble(Bubble data, PuzzleView view)
    {
        dataViewDict.Add(data, view);
    }

    // 데이터와 뷰를 함께 해제하는 단일 창구.
    // Bubble.ReturnToPool() -> PuzzlePool 콜백 -> PuzzleManager.RemoveAtMatrix() -> 여기로 들어옵니다.
    // 뷰 반납 주체를 이곳 하나로 통일해야 모델 경로(InitializeBoard 리롤, ClearBoardAndPool)에서
    // PuzzleView가 회수되지 않고 새어나가는 것을 막을 수 있습니다.
    public void ReleaseView(Bubble data)
    {
        if (dataViewDict.TryGetValue(data, out PuzzleView view))
        {
            view.ReturnToPool();
        }
        else
        {
            Debug.LogWarning($"[PuzzleMatrixView] dict에 없는 Bubble 반납 시도 (이미 반납됨?) pos={data?.Pos}");
        }
        dataViewDict.Remove(data);
    }

    // 연출이 끝난 시점의 뷰는 언제나 모델(Bubble.Pos)과 일치해야 합니다.
    //
    // DOTween의 OnStart는 UpdateMode.Update로 진입할 때만 발화합니다. 한 프레임의 deltaTime이
    // 어떤 트윈 구간을 통째로 건너뛸 만큼 크면 그 트윈은 최종 상태로 바로 꽂히고 OnStart는 생략되는데,
    // 리필 버블은 SetActive(true)를 OnStart에서 하므로 영구히 비활성으로 남게 됩니다.
    // (일시적 글리치가 아니라 되돌릴 수 없는 손상입니다)
    //
    // 여기서 모델 기준으로 한 번 스냅해 주면 그 경우는 물론, 트윈 중단/프레임 드랍으로 생긴
    // 모든 어긋남이 함께 보정됩니다. 이미 반납된 버블은 dataViewDict에서 빠졌으므로 순회 대상이 아닙니다.
    private void ReconcileViewsToModel()
    {
        foreach (var pair in dataViewDict)
        {
            Bubble data = pair.Key;
            PuzzleView view = pair.Value;

            view.transform.position = GetWorldPos(data.Pos);
            view.transform.localScale = Vector3.one;

            if (!view.gameObject.activeSelf)
            {
                Debug.LogWarning($"[PuzzleMatrixView] 비활성으로 남은 뷰를 복구합니다. Pos={data.Pos} (OnStart 스킵 의심)");
                view.gameObject.SetActive(true);
            }
        }
    }

    public void PuzzleActionStart(MoveReceipt receipt)
    {
        // 연출이 도는 동안 선택/호버/힌트 표시는 모두 내립니다.
        ClearAllHighlights();

        Sequence mainSeq = DOTween.Sequence();

        // -------------------------------------------------------------
        // [1단계] 스왑 및 롤백 연출
        // -------------------------------------------------------------
        if (receipt.SwapMoves.Count >= 2
            && dataViewDict.TryGetValue(receipt.SwapMoves[0].Data, out PuzzleView viewA)
            && dataViewDict.TryGetValue(receipt.SwapMoves[1].Data, out PuzzleView viewB))
        {
            mainSeq.Append(viewA.transform.DOMove(GetWorldPos(receipt.SwapMoves[0].ToPos), swapDuration));
            mainSeq.Join(viewB.transform.DOMove(GetWorldPos(receipt.SwapMoves[1].ToPos), swapDuration));

            // SwapMoves가 4개면 롤백이므로 제자리로 복귀하는 2차 이동을 잇습니다.
            if (receipt.SwapMoves.Count == 4)
            {
                mainSeq.Append(viewA.transform.DOMove(GetWorldPos(receipt.SwapMoves[2].ToPos), swapDuration));
                mainSeq.Join(viewB.transform.DOMove(GetWorldPos(receipt.SwapMoves[3].ToPos), swapDuration));
            }
        }

        // 스왑 이후에 연출할 것이 없는 경우(= 롤백)에는 여기서 완수 보고 후 종료
        if (!receipt.HasPostSwapAction)
        {
            mainSeq.OnComplete(() =>
            {
                ReconcileViewsToModel();
                puzzleManager.ReceiveCompleteSignal();
            });
            return;
        }

        // -------------------------------------------------------------
        // [2단계] 단계별 연쇄 연출 (1차 -> 2차 -> 3차...)
        // -------------------------------------------------------------
        // 뷰는 연출만 합니다. 스킬 발동에는 관여하지 않습니다. (GDD §4.5)
        // 연출이 완주하면 PuzzleManager가 영수증에서 레시피를 걷어 올려보냅니다.
        foreach (var step in receipt.ChainSteps)
        {
            // A. 이번 단계에서 터지는 버블
            // 매치 그룹별로 나뉘어 있지만 팝 연출은 한 번에 함께 터집니다.
            // (그룹 경계는 스킬 발동 단위이지 연출 단위가 아닙니다 - GDD §4.5)
            if (step.MatchGroups.Count > 0)
            {
                Sequence matchSeq = DOTween.Sequence();
                foreach (var group in step.MatchGroups)
                {
                    foreach (var move in group)
                    {
                        if (!dataViewDict.TryGetValue(move.Data, out PuzzleView view))
                        {
                            Debug.LogWarning($"[PuzzleMatrixView] 터짐 연출 대상 뷰를 찾지 못했습니다. pos={move.ToPos}");
                            continue;
                        }

                        // ReturnToPool() 한 번이면 ReleaseView()를 타고 뷰까지 함께 회수됩니다.
                        Bubble targetBubble = move.Data;
                        matchSeq.Join(view.transform.DOScale(Vector3.zero, matchDuration)
                            .OnComplete(() => targetBubble.ReturnToPool()));
                    }
                }
                mainSeq.Append(matchSeq);
            }

            // B. 중력 낙하
            if (step.GravityMoves.Count > 0)
            {
                Sequence gravitySeq = DOTween.Sequence();
                foreach (var move in step.GravityMoves)
                {
                    if (!dataViewDict.TryGetValue(move.Data, out PuzzleView view))
                    {
                        Debug.LogWarning($"[PuzzleMatrixView] 낙하 연출 대상 뷰를 찾지 못했습니다. {move.FromPos}->{move.ToPos}");
                        continue;
                    }

                    gravitySeq.Join(view.transform
                        .DOMove(GetWorldPos(move.ToPos), GetFallDuration(move.FromPos, move.ToPos))
                        .SetEase(Ease.InQuad));
                }
                mainSeq.Append(gravitySeq);
            }

            // C. 리필 낙하 (중력과 같은 시점에 시작해 함께 쏟아지도록 병합)
            if (step.RefillMoves.Count > 0)
            {
                Sequence refillSeq = DOTween.Sequence();
                foreach (var move in step.RefillMoves)
                {
                    if (!dataViewDict.TryGetValue(move.Data, out PuzzleView view))
                    {
                        Debug.LogWarning($"[PuzzleMatrixView] 리필 연출 대상 뷰를 찾지 못했습니다. ->{move.ToPos}");
                        continue;
                    }

                    Vector2 spawnPos = GetWorldPos(move.FromPos);
                    PuzzleView captured = view;

                    // 위치/스케일은 트윈 생성 "전"에 확정해야 합니다.
                    // DOTween은 Startup()에서 시작값을 캡처하고 그 뒤에 OnStart를 부르므로,
                    // OnStart 안에서 위치를 잡으면 이미 늦습니다.
                    captured.transform.position = spawnPos;
                    captured.transform.localScale = Vector3.one;

                    // 반면 화면 노출은 시작값과 무관하므로 재생 시점으로 미룹니다.
                    // 그러지 않으면 2·3차 연쇄용 버블까지 0프레임에 보드 위로 튀어나옵니다.
                    refillSeq.Join(captured.transform
                        .DOMove(GetWorldPos(move.ToPos), GetFallDuration(move.FromPos, move.ToPos))
                        .SetEase(Ease.OutBounce)
                        .OnStart(() => captured.gameObject.SetActive(true)));
                }

                if (step.GravityMoves.Count > 0) mainSeq.Join(refillSeq);
                else mainSeq.Append(refillSeq);
            }
        }

        // -------------------------------------------------------------
        // [3단계] 데드락 해소용 보드 셔플 연출
        // -------------------------------------------------------------
        if (receipt.ShuffleMoves.Count > 0)
        {
            Sequence shuffleSeq = DOTween.Sequence();
            foreach (var move in receipt.ShuffleMoves)
            {
                if (!dataViewDict.TryGetValue(move.Data, out PuzzleView view))
                {
                    Debug.LogWarning($"[PuzzleMatrixView] 셔플 연출 대상 뷰를 찾지 못했습니다. {move.FromPos}->{move.ToPos}");
                    continue;
                }

                shuffleSeq.Join(view.transform
                    .DOMove(GetWorldPos(move.ToPos), shuffleDuration)
                    .SetEase(Ease.InOutQuad));
            }
            mainSeq.Append(shuffleSeq);
        }

        mainSeq.OnComplete(() =>
        {
            ReconcileViewsToModel();
            puzzleManager.ReceiveCompleteSignal();
        });
    }
}
