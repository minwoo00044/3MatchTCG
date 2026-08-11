using System;
using UnityEngine;
using UnityEngine.EventSystems;
using DG.Tweening;

// 버블 하이라이트 상태. 우선순위는 Selected > Hover > Hint 순으로 뷰 매트릭스가 결정합니다.
public enum EBubbleHighlight
{
    None,
    Hover,
    Selected,
    Hint,
}

public class PuzzleView : MonoBehaviour,
    IPointerDownHandler, IPointerUpHandler, IPointerEnterHandler, IPointerExitHandler, IPoolable<PuzzleView>
{
    [SerializeField]
    private SpriteRenderer bubbleShell;
    [SerializeField]
    private SpriteRenderer inBubble;

    [Header("Highlight")]
    [Tooltip("선택/호버/힌트 표시용 링. 비워두면 쉘 색을 밝게 하는 방식으로 대체됩니다.")]
    [SerializeField]
    private SpriteRenderer highlightRing;

    [Header("Highlight - 호버")]
    [SerializeField] private float hoverScale = 1.05f;
    [SerializeField, Range(0f, 1f)] private float hoverGlow = 0.25f;

    [Header("Highlight - 선택")]
    [SerializeField] private float selectedScaleMin = 1.08f;
    [SerializeField] private float selectedScaleMax = 1.20f;
    [SerializeField, Range(0f, 1f)] private float selectedGlowMin = 0.35f;
    [SerializeField, Range(0f, 1f)] private float selectedGlowMax = 0.95f;
    [SerializeField] private float selectedPulseDuration = 0.35f;
    [Tooltip("선택된 버블을 다른 버블 위로 끌어올리는 정렬 순서 가산값")]
    [SerializeField] private int selectedSortingBump = 10;

    [Header("Highlight - 힌트")]
    [SerializeField] private float hintScaleMin = 1.0f;
    [SerializeField] private float hintScaleMax = 1.13f;
    [SerializeField, Range(0f, 1f)] private float hintGlowMin = 0.1f;
    [SerializeField, Range(0f, 1f)] private float hintGlowMax = 0.8f;
    [SerializeField] private float hintPulseDuration = 0.55f;

    private Action<PuzzleView> _returnAction;
    [SerializeField]
    private Bubble _data;

    private Action<Bubble> onPointerDownNotify;
    private Action<Bubble> onPointerUpNotify;
    private Action<Bubble, bool> onPointerHoverNotify;

    private Color baseShellColor;
    private int baseShellOrder;
    private int baseInBubbleOrder;
    private int baseRingOrder;
    private bool sortingCaptured;
    private EBubbleHighlight highlight = EBubbleHighlight.None;

    public Bubble Data { get => _data; set => _data = value; }

    void Awake()
    {
        CaptureBaseSorting();
    }

    // 정렬 순서 기준값을 한 번만 저장합니다. (선택 시 위로 끌어올렸다가 되돌리기 위함)
    // Awake에만 의존하면, 프리팹이 비활성 상태라 Awake가 늦게 도는 경우
    // 그 전에 정렬을 건드리면서 프리팹에 지정된 값을 0으로 덮어쓸 수 있어 지연 캡처합니다.
    private void CaptureBaseSorting()
    {
        if (sortingCaptured) return;
        sortingCaptured = true;

        if (bubbleShell != null) baseShellOrder = bubbleShell.sortingOrder;
        if (inBubble != null) baseInBubbleOrder = inBubble.sortingOrder;
        if (highlightRing != null) baseRingOrder = highlightRing.sortingOrder;
    }
    public void Injection(Bubble data, Action<Bubble> down, Action<Bubble> up, Action<Bubble, bool> hover)
    {
        _data = data;

        baseShellColor = _data.Spec.bubbleColor;
        bubbleShell.color = baseShellColor;
        inBubble.sprite = _data.Spec.bubbleImage;

        // 🌟 항상 inBubble이 쉘 중앙에 깔끔하게 배치되도록 정렬 및 크기 정규화
        AdjustInBubbleLayout();

        this.onPointerDownNotify = down;
        this.onPointerUpNotify = up;
        this.onPointerHoverNotify = hover;

        // 풀에서 재사용된 뷰가 이전 하이라이트를 물고 오지 않도록 초기화
        ForceClearHighlight();
    }

    // ===================== 하이라이트 =====================

    // 하이라이트는 대기 상태에서만 켜지고 PuzzleActionStart에서 전부 꺼지므로,
    // 터짐/낙하 트윈과 transform.localScale을 두고 다툴 일이 없습니다.
    public void SetHighlight(EBubbleHighlight state)
    {
        if (highlight == state) return;
        highlight = state;

        switch (state)
        {
            case EBubbleHighlight.None:
                SetSortingBump(0);
                ShowRing(false);
                ApplyHighlight(1f, 0f);
                break;

            case EBubbleHighlight.Hover:
                SetSortingBump(0);
                ShowRing(true);
                ApplyHighlight(hoverScale, hoverGlow);
                break;

            case EBubbleHighlight.Selected:
                SetSortingBump(selectedSortingBump);
                ShowRing(true);
                UpdatePulse(); // 첫 프레임부터 어긋나 보이지 않도록 즉시 한 번 적용
                break;

            case EBubbleHighlight.Hint:
                SetSortingBump(0);
                ShowRing(true);
                UpdatePulse();
                break;
        }
    }

    void Update()
    {
        if (highlight != EBubbleHighlight.Selected && highlight != EBubbleHighlight.Hint) return;
        UpdatePulse();
    }

    // 펄스를 트윈이 아니라 Time.time에서 직접 계산합니다.
    //
    // 루프 트윈으로 하면 상태가 바뀔 때마다(예: 힌트 중인 버블에 호버) 트윈이 죽고
    // 다시 처음부터 시작해서, 그 버블만 다른 버블들과 박자가 어긋납니다.
    // 전역 시간으로 계산하면 같은 상태의 버블은 항상 같은 위상으로 뛰고,
    // 상태가 오갔다 돌아와도 박자가 그대로 이어집니다.
    private void UpdatePulse()
    {
        float scaleMin, scaleMax, glowMin, glowMax, duration;

        if (highlight == EBubbleHighlight.Selected)
        {
            scaleMin = selectedScaleMin; scaleMax = selectedScaleMax;
            glowMin = selectedGlowMin; glowMax = selectedGlowMax;
            duration = selectedPulseDuration;
        }
        else
        {
            scaleMin = hintScaleMin; scaleMax = hintScaleMax;
            glowMin = hintGlowMin; glowMax = hintGlowMax;
            duration = hintPulseDuration;
        }

        // duration = 최소->최대까지 걸리는 시간(왕복 주기의 절반)
        float t = 0.5f * (1f - Mathf.Cos(Time.time * Mathf.PI / Mathf.Max(0.01f, duration)));
        ApplyHighlight(Mathf.Lerp(scaleMin, scaleMax, t), Mathf.Lerp(glowMin, glowMax, t));
    }

    private void ForceClearHighlight()
    {
        highlight = EBubbleHighlight.None;
        SetSortingBump(0);
        ShowRing(false);
        ApplyHighlight(1f, 0f);
    }

    private void ShowRing(bool visible)
    {
        if (highlightRing != null) highlightRing.gameObject.SetActive(visible);
    }

    private void SetSortingBump(int bump)
    {
        CaptureBaseSorting();

        if (bubbleShell != null) bubbleShell.sortingOrder = baseShellOrder + bump;
        if (inBubble != null) inBubble.sortingOrder = baseInBubbleOrder + bump;
        if (highlightRing != null) highlightRing.sortingOrder = baseRingOrder + bump;
    }

    // scale: 버블 전체 크기 배율 / glow: 강조 세기(0~1)
    // 링이 배정돼 있으면 링의 알파로, 없으면 쉘을 밝게 해서 표현합니다.
    // 쉘의 '색상(hue)'은 버블 종류를 나타내므로 절대 바꾸지 않고 밝기만 올립니다.
    private void ApplyHighlight(float scale, float glow)
    {
        transform.localScale = Vector3.one * scale;

        if (highlightRing != null)
        {
            Color ringColor = highlightRing.color;
            ringColor.a = glow;
            highlightRing.color = ringColor;
            return;
        }

        if (bubbleShell != null)
        {
            bubbleShell.color = Color.Lerp(baseShellColor, Color.white, glow * 0.6f);
        }
    }

    private void AdjustInBubbleLayout()
    {
        if (inBubble == null || inBubble.sprite == null || bubbleShell == null || bubbleShell.sprite == null)
            return;

        // 1. 쉘과의 로컬 좌표 중심 일치
        inBubble.transform.localPosition = Vector3.zero;

        // 2. 이미지 크기가 제각각이어도 쉘 크기의 60% 비율로 깔끔하게 중앙 정규화 스케일링
        Vector2 shellSize = bubbleShell.sprite.bounds.size;
        Vector2 inBubbleSpriteSize = inBubble.sprite.bounds.size;

        if (inBubbleSpriteSize.x > 0 && inBubbleSpriteSize.y > 0)
        {
            float targetDiameter = Mathf.Min(shellSize.x, shellSize.y) * 0.6f; // 쉘 크기의 60% 지름
            float maxSpriteDim = Mathf.Max(inBubbleSpriteSize.x, inBubbleSpriteSize.y);
            float scaleRatio = targetDiameter / maxSpriteDim;

            inBubble.transform.localScale = new Vector3(scaleRatio, scaleRatio, 1f);
        }
    }
    
    public void OnPointerDown(PointerEventData eventData)
    {
        onPointerDownNotify?.Invoke(this._data);
    }

    public void OnPointerUp(PointerEventData eventData)
    {
        onPointerUpNotify?.Invoke(this._data);
    }

    public void OnPointerEnter(PointerEventData eventData)
    {
        onPointerHoverNotify?.Invoke(this._data, true);
    }

    public void OnPointerExit(PointerEventData eventData)
    {
        onPointerHoverNotify?.Invoke(this._data, false);
    }

    public void ReturnToPool()
    {
        // 무한 루프 하이라이트 트윈이 풀에 살아 남으면 재사용된 뷰에서 계속 돕니다.
        ForceClearHighlight();
        _returnAction?.Invoke(this); // 풀의 반납 로직 실행
    }

    public void Initialize(Action<PuzzleView> returnAction)
    {
        _returnAction = returnAction;
    }
}