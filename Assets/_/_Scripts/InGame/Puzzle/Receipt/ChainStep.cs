using System.Collections.Generic;

public class ChainStep
{
    // 1. 이번 콤보/연쇄 단계에서 터진 버블 참조 및 좌표 (FromPos == ToPos)
    //
    // 평면 목록이 아니라 "매치 그룹"별로 나눠 담습니다. (GDD §4.5)
    // 스킬 레시피 1건 = 매치 그룹 1개이므로, 여기서 경계를 잃으면 matchCount를 셀 수 없습니다.
    // (보드 양쪽에서 무관한 3매치가 동시에 성립하면 평면 목록에서는 6개로 뭉쳐 보입니다)
    public List<List<MoveStep>> MatchGroups { get; set; } = new List<List<MoveStep>>();

    // 2. 이번 콤보/연쇄 단계에서 중력으로 떨어진 이동들
    public List<MoveStep> GravityMoves { get; set; } = new List<MoveStep>();

    // 3. 이번 콤보/연쇄 단계에서 리필된 이동들
    public List<MoveStep> RefillMoves { get; set; } = new List<MoveStep>();

    // 4. 이번 단계에서 발동할 스킬 레시피. MatchGroups 1개당 1건입니다. (GDD §4.5)
    //
    // 선(先)배치 규칙의 정렬 범위는 "이 리스트 하나"입니다.
    // 증폭이 앞선 ChainStep으로 소급되면 이미 발동한 스킬의 수치가 뒤늦게 바뀌므로,
    // 스텝 경계를 넘겨 재배치하지 않습니다.
    public List<SkillRecipe> SkillRecipes { get; set; } = new List<SkillRecipe>();
}
