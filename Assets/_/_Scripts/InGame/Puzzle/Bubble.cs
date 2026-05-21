using System;
using UnityEngine;
[Serializable]
public class Bubble : IPoolable<Bubble>
{
// 프로퍼티 대신 [SerializeField] 필드로 변경
    [SerializeField] private BubbleSO _spec;
    public BubbleSO Spec => _spec; // 외부에서는 프로퍼티로 읽기 전용 유지

    [SerializeField] private Vector2Int _pos;
    public Vector2Int Pos 
    { 
        get => _pos; 
        set => _pos = value; 
    }
    private Action<Bubble> _returnAction;
    public void Initialize(Action<Bubble> returnAction)
    {
        _returnAction = returnAction;

    }

    public void Inject(BubbleSO so)
    {
        _spec = so;
    }

    public void Reset()
    {
        _spec = null;
    }

    public void ReturnToPool()
    {
        _spec = null; // 여기서 리셋 수행
        _returnAction?.Invoke(this); // 풀의 반납 로직 실행
    }
}

