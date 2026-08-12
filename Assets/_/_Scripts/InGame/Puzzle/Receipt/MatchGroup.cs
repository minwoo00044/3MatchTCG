using System.Collections.Generic;

// 한 번에 터진 버블 덩어리 하나. 직선으로 연결된 3개 이상입니다.
//
// 퍼즐이 적는 것은 "무슨 버블이 어느 칸에서 터졌나"까지입니다.
// 이것이 전투에서 무슨 의미인지(스킬 1건, 시전자, 수치)는 ActionManager가 해석합니다.
public class MatchGroup
{
    // [중요] 버블이 아니라 스펙을 잡아둡니다.
    //
    // Bubble.ReturnToPool()이 _spec = null을 하고 그 호출이 팝 트윈의 OnComplete에
    // 걸려 있어, 연출이 끝난 뒤에는 Cells[i].Data.Spec이 이미 null입니다.
    // 터뜨리는 시점에 여기 적어두지 않으면 무슨 버블이었는지 되찾을 방법이 없습니다. (AGENT.md §3)
    public BubbleSO Spec { get; }

    // 터진 칸들. FromPos == ToPos입니다.
    public List<MoveStep> Cells { get; }

    public MatchGroup(BubbleSO spec, List<MoveStep> cells)
    {
        Spec = spec;
        Cells = cells;
    }
}
