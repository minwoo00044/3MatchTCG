using System;
using UnityEngine;

public class Bubble : IPoolable<Bubble>
{
    public BubbleSO Spec { get; private set; }
    public Vector2Int Pos { get;  set; }
    private Action<Bubble> _returnAction;
    public void Initialize(Action<Bubble> returnAction)
    {
        _returnAction = returnAction;

    }

    public void Inject(BubbleSO so)
    {
        Spec = so;
    }

    public void Reset()
    {
        Spec = null;
    }

    public void ReturnToPool()
    {
        Spec = null; // 여기서 리셋 수행
        _returnAction?.Invoke(this); // 풀의 반납 로직 실행
    }
}

