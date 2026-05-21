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

    void Awake()
    {
    }
    public void Injection(Bubble data)
    {
        _data = data;

        bubbleShell.color = _data.Spec.bubbleColor;
        inBubble.sprite = _data.Spec.bubbleImage;
    }
    
    public void OnPointerDown(PointerEventData eventData)
    {
        throw new System.NotImplementedException();
    }

    public void OnPointerUp(PointerEventData eventData)
    {
        throw new System.NotImplementedException();
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