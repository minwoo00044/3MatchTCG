using System;
using UnityEngine;

public abstract class GameAction:ScriptableObject
{
    public abstract void OnExecute(Actor[] target);

    // 같은 ChainStep의 이후 스킬에 영향을 주는 액션인지. (GDD §4.5 선배치 실행 규칙)
    //
    // 증폭/버프는 반드시 먼저 발동해야 뒤따르는 스킬이 증폭된 수치로 계산됩니다.
    // "이후 스킬에 영향을 주는가"는 버블이 아니라 액션의 성질이므로 여기서 답합니다. (AGENT.md §5)
    // 증폭 액션이 생기면 그 클래스에서 override 한 줄이면 켜집니다.
    public virtual bool IsPreemptive => false;
}