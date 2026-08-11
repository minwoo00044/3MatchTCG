using System;
using System.Collections.Generic;
using UnityEngine;
using DG.Tweening;

public class PuzzleMatrixView : MonoBehaviour
{
    private Dictionary<Bubble, PuzzleView> dataViewDict = new Dictionary<Bubble, PuzzleView>();
    private PuzzleManager puzzleManager;

    // ===================== 낙하 연출 타이밍 =====================
    // 중력/리필은 이동 거리가 제각각이므로 고정 시간이 아니라 "칸당 시간"으로 계산합니다.
    [Header("FALL TIMING")]
    [Tooltip("낙하 1칸당 소요 시간(초)")]
    [SerializeField] private float fallSecondsPerCell = 0.07f;
    [Tooltip("아주 짧은 낙하도 이 시간 이상은 보장")]
    [SerializeField] private float fallMinDuration = 0.12f;

    // 이동 거리에 비례한 낙하 시간. 1칸이든 6칸이든 체감 속도가 같아집니다.
    private float GetFallDuration(Vector2Int from, Vector2Int to)
    {
        float distance = Vector2Int.Distance(from, to);
        return Mathf.Max(fallMinDuration, distance * fallSecondsPerCell);
    }

    // ===================== 디버그 로그 =====================
    [Header("DEBUG")]
    [SerializeField] private bool enableAnimLog = true;

    private void PLog(string msg)
    {
        if (!enableAnimLog) return;
        Debug.Log($"[PZ|f{Time.frameCount}|t{Time.time:F3}] {msg}");
    }
    private void PWarn(string msg)
    {
        if (!enableAnimLog) return;
        Debug.LogWarning($"[PZ|f{Time.frameCount}|t{Time.time:F3}] {msg}");
    }
    // =====================================================

    public Vector2 GetWorldPos(Vector2Int gridPos)
    {
        return new Vector2(gridPos.x * 1f, gridPos.y * 1f);
    }

    public void DrawingAllMatrix()
    {
        Debug.Log("drawStart");
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
                PWarn($"[RECONCILE] 비활성으로 남은 뷰를 복구합니다. Pos={data.Pos} (OnStart 스킵 의심)");
                view.gameObject.SetActive(true);
            }
        }
    }

    public void ReleaseView(Bubble data)
    {
        if (dataViewDict.TryGetValue(data, out PuzzleView view))
        {
            PLog($"  [ReleaseView] 뷰 반납 '{view.name}' (dict {dataViewDict.Count} -> {dataViewDict.Count - 1})");
            view.ReturnToPool();
        }
        else
        {
            PWarn($"  [ReleaseView] dict에 없는 Bubble 반납 시도 (이미 반납됨?) pos={data?.Pos}");
        }
        dataViewDict.Remove(data);
    }

    public void PuzzleActionStart(MoveReceipt receipt)
    {
        // 연출이 도는 동안 선택/호버/힌트 표시는 모두 내립니다.
        ClearAllHighlights();

        // ===== [진입] 환경 및 영수증 상태 덤프 =====
        PLog("========== PuzzleActionStart 진입 ==========");
        PLog($"[ENV] timeScale={Time.timeScale} / DOTween 재생중 트윈={DOTween.TotalPlayingTweens()} / dataViewDict={dataViewDict.Count}개");
        PLog($"[RECEIPT] SwapMoves={receipt.SwapMoves.Count} / ChainSteps={receipt.ChainSteps.Count} / " +
             $"ShuffleMoves={receipt.ShuffleMoves.Count} / IsChainOccurred={receipt.IsChainOccurred}");
        for (int i = 0; i < receipt.ChainSteps.Count; i++)
        {
            var s = receipt.ChainSteps[i];
            PLog($"[RECEIPT]   Step{i}: Matches={s.Matches.Count}, Gravity={s.GravityMoves.Count}, Refill={s.RefillMoves.Count}");
        }

        Sequence mainSeq = DOTween.Sequence();

        // -------------------------------------------------------------
        // [1단계] 스왑 및 롤백 연출 (SwapMoves)
        // -------------------------------------------------------------
        bool swapA = receipt.SwapMoves.Count >= 2 && dataViewDict.ContainsKey(receipt.SwapMoves[0].Data);
        bool swapB = receipt.SwapMoves.Count >= 2 && dataViewDict.ContainsKey(receipt.SwapMoves[1].Data);
        PLog($"[SWAP] 조회결과 A={swapA}, B={swapB} (둘 다 true여야 스왑 연출이 붙습니다)");

        if (receipt.SwapMoves.Count >= 2
            && dataViewDict.TryGetValue(receipt.SwapMoves[0].Data, out PuzzleView viewA)
            && dataViewDict.TryGetValue(receipt.SwapMoves[1].Data, out PuzzleView viewB))
        {
            Vector2 targetPosA = GetWorldPos(receipt.SwapMoves[0].ToPos);
            Vector2 targetPosB = GetWorldPos(receipt.SwapMoves[1].ToPos);

            PLog($"[SWAP] A '{viewA.name}' active={viewA.gameObject.activeInHierarchy} scale={viewA.transform.localScale} " +
                 $"현재pos={(Vector2)viewA.transform.position} -> 목표={targetPosA}");
            PLog($"[SWAP] B '{viewB.name}' active={viewB.gameObject.activeInHierarchy} scale={viewB.transform.localScale} " +
                 $"현재pos={(Vector2)viewB.transform.position} -> 목표={targetPosB}");

            Transform trA = viewA.transform;
            mainSeq.Append(trA.DOMove(targetPosA, 0.15f)
                .OnStart(() => PLog($"[SWAP-A] 트윈 시작. from={(Vector2)trA.position} -> {targetPosA}"))
                .OnComplete(() => PLog($"[SWAP-A] 트윈 완료. pos={(Vector2)trA.position}")));
            mainSeq.Join(viewB.transform.DOMove(targetPosB, 0.15f));

            // SwapMoves가 4개인 경우 롤백이므로 제자리로 복귀하는 2차 이동 추가
            if (receipt.SwapMoves.Count == 4)
            {
                Vector2 originPosA = GetWorldPos(receipt.SwapMoves[2].ToPos);
                Vector2 originPosB = GetWorldPos(receipt.SwapMoves[3].ToPos);
                PLog($"[SWAP] 롤백 구간 추가. A->{originPosA}, B->{originPosB}");

                mainSeq.Append(viewA.transform.DOMove(originPosA, 0.15f));
                mainSeq.Join(viewB.transform.DOMove(originPosB, 0.15f));
            }
        }
        else
        {
            PWarn("[SWAP] 스왑 연출이 통째로 스킵되었습니다! (SwapMoves 부족 또는 dict 조회 실패)");
        }

        // 스왑 이후에 연출할 것이 아무것도 없는 경우(= 롤백)에는 여기서 완수 보고 후 종료
        if (!receipt.HasPostSwapAction)
        {
            PLog($"[EXIT-ROLLBACK] 연쇄 없음. mainSeq duration={mainSeq.Duration():F3}s, active={mainSeq.IsActive()}, playing={mainSeq.IsPlaying()}");
            mainSeq.OnComplete(() =>
            {
                PLog("[EXIT-ROLLBACK] mainSeq OnComplete -> ReceiveCompleteSignal()");
                ReconcileViewsToModel();
                puzzleManager.ReceiveCompleteSignal();
            });
            return;
        }

        // -------------------------------------------------------------
        // [2단계] 단계별 콤보/연쇄 연출 루프 (1차 -> 2차 -> 3차...)
        // -------------------------------------------------------------
        int stepIndex = -1;
        foreach (var step in receipt.ChainSteps)
        {
            stepIndex++;
            int si = stepIndex; // 클로저 캡처용
            PLog($"--- [BUILD] Step{si} 조립 시작 (누적 duration={mainSeq.Duration():F3}s) ---");

            // A. 이번 콤보 터짐 연출
            if (step.Matches.Count > 0)
            {
                Sequence matchSeq = DOTween.Sequence();
                int hit = 0, miss = 0;
                foreach (var move in step.Matches)
                {
                    if (dataViewDict.TryGetValue(move.Data, out PuzzleView view))
                    {
                        hit++;
                        Bubble targetBubble = move.Data;
                        Vector2Int at = move.ToPos;
                        matchSeq.Join(view.transform.DOScale(Vector3.zero, 0.15f)
                            .OnStart(() => PLog($"[S{si}-MATCH] 터짐 시작 {at} '{view.name}' active={view.gameObject.activeInHierarchy}"))
                            .OnComplete(() =>
                            {
                                PLog($"[S{si}-MATCH] 터짐 완료 {at} -> ReturnToPool");
                                targetBubble.ReturnToPool();
                            }));
                    }
                    else
                    {
                        miss++;
                        PWarn($"[S{si}-MATCH] dict 조회 실패! pos={move.ToPos} (연출 누락)");
                    }
                }
                PLog($"[S{si}-MATCH] 조립완료 hit={hit} miss={miss} matchSeq.duration={matchSeq.Duration():F3}s");
                mainSeq.Append(matchSeq);
            }

            // B. 이번 콤보 중력 낙하 연출
            if (step.GravityMoves.Count > 0)
            {
                Sequence gravitySeq = DOTween.Sequence();
                int hit = 0, miss = 0;
                foreach (var move in step.GravityMoves)
                {
                    if (dataViewDict.TryGetValue(move.Data, out PuzzleView view))
                    {
                        hit++;
                        Vector2 targetPos = GetWorldPos(move.ToPos);
                        Transform tr = view.transform;
                        Vector2Int from = move.FromPos, to = move.ToPos;
                        gravitySeq.Join(tr.DOMove(targetPos, GetFallDuration(from, to)).SetEase(Ease.InQuad)
                            .OnStart(() => PLog($"[S{si}-GRAV] 낙하 시작 {from}->{to} 실제pos={(Vector2)tr.position} active={tr.gameObject.activeInHierarchy}"))
                            .OnComplete(() => PLog($"[S{si}-GRAV] 낙하 완료 {to} 실제pos={(Vector2)tr.position}")));
                    }
                    else
                    {
                        miss++;
                        PWarn($"[S{si}-GRAV] dict 조회 실패! {move.FromPos}->{move.ToPos} (연출 누락)");
                    }
                }
                PLog($"[S{si}-GRAV] 조립완료 hit={hit} miss={miss} gravitySeq.duration={gravitySeq.Duration():F3}s");
                mainSeq.Append(gravitySeq);
            }

            // C. 이번 콤보 리필 낙하 연출 (중력 낙하와 자연스럽게 병합/연동)
            if (step.RefillMoves.Count > 0)
            {
                Sequence refillSeq = DOTween.Sequence();
                int hit = 0, miss = 0;
                foreach (var move in step.RefillMoves)
                {
                    if (dataViewDict.TryGetValue(move.Data, out PuzzleView view))
                    {
                        hit++;
                        Vector2 spawnPos = GetWorldPos(move.FromPos);
                        Vector2 targetPos = GetWorldPos(move.ToPos);
                        PuzzleView captured = view;

                        // 1. 위치와 스케일은 DOMove 생성 전 확정 (Startup이 spawnPos를 시작값으로 캡처)
                        captured.transform.position = spawnPos;
                        captured.transform.localScale = Vector3.one;

                        // 2. 화면 노출(SetActive)만 실제 트윈 재생 시점(OnStart)으로 이관하여 유령 버블 방지
                        //    리필도 컬럼마다 낙하 거리가 달라지므로 거리 비례 시간을 씁니다.
                        refillSeq.Join(captured.transform.DOMove(targetPos, GetFallDuration(move.FromPos, move.ToPos))
                            .SetEase(Ease.OutBounce)
                            .OnStart(() =>
                            {
                                PLog($"[S{si}-REFILL] 등장 {spawnPos}->{targetPos} '{captured.name}' 실제pos={(Vector2)captured.transform.position}");
                                captured.gameObject.SetActive(true);
                            })
                            .OnComplete(() => PLog($"[S{si}-REFILL] 착지 {targetPos} 실제pos={(Vector2)captured.transform.position}")));
                    }
                    else
                    {
                        miss++;
                        PWarn($"[S{si}-REFILL] dict 조회 실패! ->{move.ToPos} (연출 누락, 버블이 영영 안 보임)");
                    }
                }
                PLog($"[S{si}-REFILL] 조립완료 hit={hit} miss={miss} refillSeq.duration={refillSeq.Duration():F3}s");

                // 중력 낙하가 있었다면 중력과 리필을 함께/이어서 병합 연출
                if (step.GravityMoves.Count > 0)
                {
                    mainSeq.Join(refillSeq);
                    PLog($"[S{si}-REFILL] 중력과 Join 병합");
                }
                else
                {
                    mainSeq.Append(refillSeq);
                    PLog($"[S{si}-REFILL] 중력 없음 -> Append");
                }
            }
        }

        // -------------------------------------------------------------
        // [3단계] 데드락 해소용 보드 셔플 연출
        // -------------------------------------------------------------
        if (receipt.ShuffleMoves.Count > 0)
        {
            PLog($"[SHUFFLE] 데드락 셔플 {receipt.ShuffleMoves.Count}개 이동 조립");

            Sequence shuffleSeq = DOTween.Sequence();
            int hit = 0, miss = 0;
            foreach (var move in receipt.ShuffleMoves)
            {
                if (dataViewDict.TryGetValue(move.Data, out PuzzleView view))
                {
                    hit++;
                    Vector2 targetPos = GetWorldPos(move.ToPos);
                    shuffleSeq.Join(view.transform.DOMove(targetPos, 0.45f).SetEase(Ease.InOutQuad));
                }
                else
                {
                    miss++;
                    PWarn($"[SHUFFLE] dict 조회 실패! {move.FromPos}->{move.ToPos}");
                }
            }
            PLog($"[SHUFFLE] 조립완료 hit={hit} miss={miss} duration={shuffleSeq.Duration():F3}s");
            mainSeq.Append(shuffleSeq);
        }

        // ===== [조립 완료] 최종 시퀀스 상태 점검 =====
        PLog($"========== 조립 완료: mainSeq duration={mainSeq.Duration():F3}s / active={mainSeq.IsActive()} / playing={mainSeq.IsPlaying()} / DOTween 재생중={DOTween.TotalPlayingTweens()} ==========");
        if (mainSeq.Duration() <= 0f)
        {
            PWarn("!!! mainSeq의 duration이 0입니다. 트윈이 하나도 안 붙었다는 뜻이며, 다음 프레임에 즉시 완료 처리됩니다 !!!");
        }

        int updateTicks = 0;
        mainSeq.OnPlay(() => PLog(">>> mainSeq OnPlay (재생 시작)"))
               .OnUpdate(() =>
               {
                   // 실제로 프레임이 흐르며 갱신되는지 확인 (앞 8틱만 출력)
                   if (updateTicks < 8)
                   {
                       updateTicks++;
                       PLog($"    mainSeq OnUpdate #{updateTicks} elapsed={mainSeq.Elapsed():F3}/{mainSeq.Duration():F3}");
                   }
               })
               .OnKill(() => PLog("<<< mainSeq OnKill (시퀀스 파기)"))
               .OnComplete(() =>
               {
                   PLog($"<<< mainSeq OnComplete. 총 OnUpdate 틱 수={updateTicks} (이 값이 0~1이면 애니메이션이 한 프레임에 씹힌 것입니다)");
                   ReconcileViewsToModel();
                   puzzleManager.ReceiveCompleteSignal();
               });
    }
}