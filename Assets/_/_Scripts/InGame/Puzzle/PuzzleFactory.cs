using System.Collections.Generic;
using UnityEngine;

public class PuzzleFactory
{
    private List<BubbleSO> bubbleSpecs;

    // 뽑을 후보는 게임 시작 시점에 덱에서 받아옵니다. 여기서 목록을 만들지 않습니다.
    public void InjectBubbleSpecs(List<BubbleSO> bubbleSO)
    {
        bubbleSpecs = bubbleSO;
    }

    public Bubble PackBubble(Bubble emptyBubble)
    {
        if (bubbleSpecs == null || bubbleSpecs.Count == 0)
        {
            Debug.LogWarning("[PuzzleFactory] 뽑을 버블 후보가 없습니다.");
            return emptyBubble;
        }

        // 지금은 후보 전체에서 균등 추첨입니다.
        // 캐릭터 3인 30%씩 + 공용 10%의 2단계 가중 추첨은 다음 작업([6])에서 붙입니다. (GDD §3.2)
        //
        // 이전에는 길이 10짜리 가중치 배열이 코드에 박혀 있었는데, 후보 수가 10이 아니면
        // 조용히 일부가 안 뽑히거나 인덱스를 벗어납니다. 후보 목록을 덱에서 받게 되면서
        // 개수가 고정이 아니게 되어 목록 길이 기준으로 바꿉니다. (가중치가 전부 동일했으므로 결과는 같습니다)
        int index = Random.Range(0, bubbleSpecs.Count);
        emptyBubble.Inject(bubbleSpecs[index]);

        return emptyBubble;
    }
}
