using System;
using UnityEngine;

// 스킬이 대상에게 하는 일. 수치는 이미 계산되어 SkillContext에 담겨 옵니다.
//
// 액션은 계산하지 않고 적용만 합니다. 적용 결과는 대상마다 한 줄씩 영수증에 남겨야 하며,
// 남기지 않으면 연출이 그 타격을 보여줄 방법이 없습니다. (GDD §4.5)
public abstract class GameAction:ScriptableObject
{
    public abstract void OnExecute(SkillContext ctx);

    // 대상이 없는 배치 효과도 같은 모듈 경로를 탑니다. 에셋마다 선택하는 옵션이 아니라
    // 액션 종류의 의미가 답해야 같은 액션의 규칙이 갈리지 않습니다. (GDD §2.3, §4.6)
    public virtual bool RequiresTarget => true;

    // 공격/회복/실드는 매치 기본 파워를 쓰고, 증폭처럼 발동 1건당 고정인 액션은 쓰지 않습니다.
    public virtual bool UsesSkillPower => true;

    // 같은 연쇄 차수의 이후 스킬에 영향을 주는 액션인지. (GDD §4.5 선배치 실행 규칙)
    //
    // 증폭/버프는 반드시 먼저 발동해야 뒤따르는 스킬이 증폭된 수치로 계산됩니다.
    // "이후 스킬에 영향을 주는가"는 버블이 아니라 액션의 성질이므로 여기서 답합니다. (AGENTS.md §5)
    // 증폭 액션이 생기면 그 클래스에서 override 한 줄이면 켜집니다.
    public virtual bool IsPreemptive => false;
}
