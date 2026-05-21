using System.Collections.Generic;
using UnityEngine;
public class PuzzlePool
{
    private Queue<Bubble> dataPool;
    private Queue<PuzzleView> viewPool;
    private PuzzleManager puzzleManager;

    // 프리팹 정보나 생성 시 부모 객체가 필요할 수 있습니다.
    private PuzzleView viewPrefab; 
    private Transform poolParent;

    public PuzzlePool(PuzzleManager puzzleManager, PuzzleView viewPrefab)
    {
        this.puzzleManager = puzzleManager;
        this.viewPrefab = viewPrefab;
        dataPool = new Queue<Bubble>();
        viewPool = new Queue<PuzzleView>();
    }

    // --- 데이터 풀 로직 ---
    public Bubble RequestData()
    {
        Bubble ret = null;
        if(dataPool.Count > 0)
        {
            ret = dataPool.Dequeue();
        }
        else
        {
            ret = new Bubble();
            ret.Initialize((T) =>
            {
                ReturnData(T);
                puzzleManager.RemoveAtMatrix(T);
            });
        }
        return ret;
    }

    public void ReturnData(Bubble data)
    {
        dataPool.Enqueue(data);
    }

    // --- 뷰 풀 로직 (중요) ---
    public PuzzleView RequestView()
    {
        PuzzleView view;
        if (viewPool.Count > 0)
        {
            view = viewPool.Dequeue();
        }
        else
        {
            // 풀에 없으면 매니저에게 요청하거나 직접 Instantiate
            view = GameObject.Instantiate(viewPrefab,poolParent);
        }

        view.gameObject.SetActive(false);
        view.Initialize(ReturnView);
        return view;
    }

    public void ReturnView(PuzzleView view)
    {
        view.gameObject.SetActive(false);
        // 위치를 보이지 않는 곳으로 옮겨두기도 합니다.
        viewPool.Enqueue(view);
    }
}