using System.Collections.Generic;
using UnityEngine;

public class PuzzleFactory
{
    //임시 가중치 테이블
    int[] testTable = {100,100,100,100,100,100,100,100,100,100};
    private List<BubbleSO> bubbleSpecs;
    public void InjectBubbleSpecs(List<BubbleSO> bubbleSO)
    {
        bubbleSpecs = bubbleSO;
    }
    public Bubble PackBubble(Bubble emptyBubble)
    {
        int rand = Random.Range(0,1000);
        int cumulative = 0;
        for(int i = 0; i < testTable.Length; i++)
        {
            cumulative += testTable[i];

            if (rand < cumulative)
            {
                // 당첨! i번째 종류의 버블로 확정
                emptyBubble.Inject(bubbleSpecs[i]); // 이런 식으로 SO를 주입
                return emptyBubble;
            }
        }
        return emptyBubble;
    }
}