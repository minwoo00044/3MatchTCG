using System.Collections.Generic;
using UnityEngine;

// 전투 덱 1개 = 캐릭터 3인. (GDD §2.1)
//
// 2단계 추첨의 1단계(캐릭터 블록 선택)가 이 목록 위에서 돌아갑니다. (GDD §3.2)
[CreateAssetMenu(fileName = "EmptyDeckData", menuName = "ScriptableObject/DeckData")]
public class DeckSO : ScriptableObject
{
    public const int CharacterCount = 3;

    [Tooltip("전투에 편성할 캐릭터 3인 (GDD §2.1)")]
    public List<CharacterSO> characters = new List<CharacterSO>();

#if UNITY_EDITOR
    // 인스펙터 배선 실수는 컴파일로 잡히지 않습니다. (AGENTS.md §9)
    private void OnValidate()
    {
        if (characters == null) return;

        if (characters.Count != CharacterCount)
        {
            Debug.LogWarning($"[DeckSO] {name}: 캐릭터는 {CharacterCount}명이어야 합니다. 현재 {characters.Count}명", this);
        }

        for (int i = 0; i < characters.Count; i++)
        {
            if (characters[i] == null)
            {
                Debug.LogWarning($"[DeckSO] {name}: characters[{i}]가 비어 있습니다", this);
            }
        }
    }
#endif
}
