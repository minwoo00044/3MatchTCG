using UnityEngine;

// 한 MoveReceipt의 스킬 실행 동안만 유지되는 전투 배치 상태입니다. (GDD §3.3, §4.6)
//
// BattleManager의 영구 필드로 두면 End 전이나 예외 경로에서 리셋을 놓쳐 다음 스왑으로
// 증폭이 샐 수 있습니다. 지역 객체 수명으로 리셋 규칙을 구조적으로 보장합니다.
public sealed class SkillBatchContext
{
    public float Amplification { get; private set; } = 1f;

    public void AddAmplification(float amount, float maximum)
    {
        if (amount <= 0f) return;
        Amplification = Mathf.Min(Mathf.Max(1f, maximum), Amplification + amount);
    }
}
