using UnityEngine;

// 보드에서 뽑히고 터지는 스킬. (GDD §2.2, §3.2)
//
// 전투가 쓰는 부분(SOName, effects)은 SkillSO에 있습니다.
// 여기 남은 것은 **보드에 존재하기 때문에 생기는 것들**뿐입니다 - 어떻게 보이나,
// 얼마나 자주 뽑히나, 몇 차 연쇄에 터졌나.
//
// 적 NPC 스킬은 보드에 없으므로 SkillSO를 직접 씁니다. (GDD §4.2)
//
// 필드 이름을 그대로 두고 SkillSO로 올렸기 때문에 기존 .asset의 값은 유지됩니다.
// 유니티는 선언 클래스가 아니라 이름으로 직렬화합니다.
[CreateAssetMenu(fileName = "EmptyBubbleData", menuName = "ScriptableObject/BubbleData")]
public class BubbleSO : SkillSO
{
  [Header("View Sector")]
  public Sprite bubbleImage;
  // 색은 여기 없습니다. 소속 캐릭터의 CharacterSO.mainColor가 단일 원천입니다. (GDD §2.2)
  // 겉모습과 판정 키가 두 벌이 되면 게임이 거짓말을 하므로 버블이 색을 스스로 들지 않습니다. (AGENTS.md §6)
  // 소속 캐릭터가 없는 공용 버블(T_O)의 색은 PuzzleManager가 폴백으로 답합니다.
  //연출효과 등등
  [Header("Spawn Sector")]
  [Tooltip("소속 캐릭터에게 배정된 지분 안에서 이 스킬 버블이 뽑힐 상대 가중치 (GDD §3.2 2단계 추첨)")]
  public float spawnWeight = 1f;
  [Header("Chain Sector")]
  [Tooltip("연쇄 차수별 배율. index 0 = 1차 연쇄. 비어 있거나 범위를 넘으면 1.0 (마지막 값 유지)")]
  public float[] chainWeights;

  // 연쇄 배율을 묻는 곳이 여러 군데 생기므로 답하는 함수는 여기 하나만 둡니다. (AGENTS.md §5)
  // chainIndex는 1-based입니다.
  //
  // SkillSO에 두지 않은 이유: 연쇄는 보드에서만 일어납니다. 적 스킬이 이 함수를 가지면
  // 부를 수 있게 되고, 부르는 순간 GDD §4.2("적 데미지는 value 고정")가 깨집니다.
  public float GetChainWeight(int chainIndex)
  {
    if (chainWeights == null || chainWeights.Length == 0) return 1f;
    int i = Mathf.Clamp(chainIndex - 1, 0, chainWeights.Length - 1);
    return chainWeights[i];
  }
}
