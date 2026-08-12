using UnityEngine;

// 캐릭터 1인의 정적 데이터입니다. (GDD §2.3)
//
// 런타임 Actor 인스턴스와의 매핑(CharacterSO <-> Actor)은 ActionManager가 소유합니다.
// PuzzleManager는 이 SO를 정적 파이프(스포닝 비율, 버블 색)로만 읽고 Actor를 참조하지 않습니다.
// (GDD §2.3, GDD-TODO A-2)
[CreateAssetMenu(fileName = "EmptyCharacterData", menuName = "ScriptableObject/CharacterData")]
public class CharacterSO : ScriptableObject
{
    public const int SkillCount = 3;

    [Header("Name")]
    public string characterName;

    [Header("Visual Sector")]
    public Sprite characterImage;
    [Tooltip("이 캐릭터의 스킬 버블이 사용하는 색. 버블 색의 단일 원천입니다 (GDD §2.2)")]
    public Color mainColor = Color.white;

    [Header("Stat Sector")]
    public int maxHP;
    [Tooltip("흡수형 방어막의 상한. 전투 시작 시 실드는 0이고 DefenseAction으로 채웁니다")]
    public int maxShield;
    [Tooltip("상시 고정 기본 위협도. 총 위협도 = baseThreat + 최근 10초 누적 (GDD §4.1)")]
    public float baseThreat;

    [Header("Skill Sector")]
    [Tooltip("이 캐릭터 전용 스킬 버블 3종. 1 스킬 <-> 1 버블 (GDD §2.2)")]
    public BubbleSO[] skills;

#if UNITY_EDITOR
    // 인스펙터 배선 실수는 컴파일로 잡히지 않습니다. 값이 아니라 불변식을 찍습니다. (AGENT.md §9)
    private void OnValidate()
    {
        if (skills == null) return;

        if (skills.Length != SkillCount)
        {
            Debug.LogWarning($"[CharacterSO] {name}: 스킬은 {SkillCount}개여야 합니다. 현재 {skills.Length}개", this);
        }

        for (int i = 0; i < skills.Length; i++)
        {
            if (skills[i] == null)
            {
                Debug.LogWarning($"[CharacterSO] {name}: skills[{i}]가 비어 있습니다", this);
            }
        }
    }
#endif
}
