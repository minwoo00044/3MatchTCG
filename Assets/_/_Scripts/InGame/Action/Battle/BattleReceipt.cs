using System.Collections.Generic;

// 한 번의 GameActionState에서 일어난 전투 결과 전체. (GDD §4.5)
//
// 퍼즐의 MoveReceipt와 같은 구조입니다. 논리는 미리 끝내고 연출은 나중에 재생합니다.
// 담긴 순서가 곧 실행 순서이자 연출 순서이며, 연출이 "누가 먼저인가"를 다시 계산하지 않습니다.
//
// 재계산이 불가능한 이유: 타겟팅이 의존하는 상태(체력 순위, 위협도, 생존 여부)를
// 같은 배치의 스킬들이 바꿉니다. 실드 흡수 분해나 오버킬 초과분도 재계산으로는 얻을 수 없습니다.
public class BattleReceipt
{
    public List<BattleStep> Steps { get; } = new List<BattleStep>();

    public void Add(BattleStep step)
    {
        if (step != null) Steps.Add(step);
    }
}
