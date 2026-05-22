using System;
using UnityEngine;
using UnityEngine.EventSystems;

public class PuzzleView : MonoBehaviour, IPointerDownHandler, IPointerUpHandler, IPoolable<PuzzleView>
{
    [SerializeField]
    private SpriteRenderer bubbleShell;
    [SerializeField]
    private SpriteRenderer inBubble;

    private Action<PuzzleView> _returnAction;
    [SerializeField]
    private Bubble _data;

    private Action<PuzzleView> onPointerDownNotify;
    private Action<PuzzleView> onPointerUpNotify;
    void Awake()
    {
    }
    public void Injection(Bubble data, Action<PuzzleView> down, Action<PuzzleView> up)
    {
        _data = data;

        bubbleShell.color = _data.Spec.bubbleColor;
        inBubble.sprite = _data.Spec.bubbleImage;
    
        this.onPointerDownNotify = down;
        this.onPointerUpNotify = up;
    }
    
    public void OnPointerDown(PointerEventData eventData)
    {
        onPointerDownNotify?.Invoke(this);
    }

    public void OnPointerUp(PointerEventData eventData)
    {
        onPointerUpNotify?.Invoke(this);
    }
    public void ReturnToPool()
    {
        _returnAction?.Invoke(this); // 풀의 반납 로직 실행
    }

    public void Initialize(Action<PuzzleView> returnAction)
    {
        _returnAction = returnAction;
    }
}