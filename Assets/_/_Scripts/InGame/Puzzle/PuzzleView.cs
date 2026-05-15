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

    void Awake()
    {
    }
    public void Injection(Color color, Sprite sprite)
    {
        bubbleShell.color = color;
        inBubble.sprite = sprite;
    }
    
    public void OnPointerDown(PointerEventData eventData)
    {
        throw new System.NotImplementedException();
    }

    public void OnPointerUp(PointerEventData eventData)
    {
        throw new System.NotImplementedException();
    }

    public void Initialize(Action<PuzzleView> returnAction)
    {
        _returnAction = returnAction;
    }

    public void ReturnToPool()
    {
        _returnAction?.Invoke(this); // 풀의 반납 로직 실행
    }
}