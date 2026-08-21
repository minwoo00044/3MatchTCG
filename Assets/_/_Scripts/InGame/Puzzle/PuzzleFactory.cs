using System.Collections.Generic;
using UnityEngine;

public class PuzzleFactory
{
    private sealed class CharacterBubbleGroup
    {
        public readonly List<BubbleSO> Specs;
        public readonly float TotalWeight;

        public CharacterBubbleGroup(List<BubbleSO> specs, float totalWeight)
        {
            Specs = specs;
            TotalWeight = totalWeight;
        }
    }

    private readonly List<CharacterBubbleGroup> characterGroups = new List<CharacterBubbleGroup>();
    private BubbleSO commonSpec;

    // 캐릭터-스킬 소유 관계와 생존 판정은 PuzzleManager가 끝낸 뒤 그룹만 넘깁니다.
    // Factory는 Actor나 CharacterSO를 모르고 전달받은 후보의 가중 추첨만 담당합니다. (GDD §3.2)
    public void InjectSpawnCandidates(List<List<BubbleSO>> characterSpecs, List<BubbleSO> commonSpecs)
    {
        characterGroups.Clear();
        commonSpec = null;

        if (characterSpecs != null)
        {
            foreach (var specs in characterSpecs)
            {
                CharacterBubbleGroup group = BuildCharacterGroup(specs);
                if (group != null) characterGroups.Add(group);
            }
        }

        int commonCount = 0;
        if (commonSpecs != null)
        {
            foreach (var spec in commonSpecs)
            {
                if (spec == null) continue;

                commonCount++;
                if (commonSpec == null) commonSpec = spec;
            }
        }

        // GDD §3.2는 공용 특수 버블 T_O 하나를 전제로 합니다.
        // 여러 후보의 비율 규칙은 정해지지 않았으므로 임의 추첨 규칙을 만들지 않고 첫 유효 후보만 씁니다.
        if (commonCount != 1)
        {
            Debug.LogWarning($"[PuzzleFactory] 공용 특수 버블은 1개여야 합니다. 현재 {commonCount}개");
        }
    }

    public Bubble PackBubble(Bubble emptyBubble)
    {
        if (emptyBubble == null) return null;

        BubbleSO selected = PickSpec();
        if (selected == null)
        {
            Debug.LogWarning("[PuzzleFactory] 뽑을 버블 후보가 없습니다.");
            return emptyBubble;
        }

        emptyBubble.Inject(selected);

        return emptyBubble;
    }

    private CharacterBubbleGroup BuildCharacterGroup(List<BubbleSO> specs)
    {
        if (specs == null) return null;

        List<BubbleSO> validSpecs = new List<BubbleSO>();
        float totalWeight = 0f;

        foreach (var spec in specs)
        {
            if (spec == null || spec.spawnWeight <= 0f) continue;

            validSpecs.Add(spec);
            totalWeight += spec.spawnWeight;
        }

        if (validSpecs.Count == 0 || totalWeight <= 0f)
        {
            Debug.LogWarning("[PuzzleFactory] 양수 spawnWeight를 가진 스킬이 없는 캐릭터 그룹을 제외합니다.");
            return null;
        }

        return new CharacterBubbleGroup(validSpecs, totalWeight);
    }

    // 1단계: 공용 10, 생존 캐릭터 전체 90. 캐릭터 몫은 생존 인원끼리 균등 분배합니다.
    private BubbleSO PickSpec()
    {
        float characterShare = characterGroups.Count > 0 ? 90f / characterGroups.Count : 0f;
        float commonShare = commonSpec != null ? 10f : 0f;
        float totalShare = characterShare * characterGroups.Count + commonShare;
        if (totalShare <= 0f) return null;

        float roll = Random.Range(0f, totalShare);
        foreach (var group in characterGroups)
        {
            if (roll < characterShare) return PickCharacterSpec(group);
            roll -= characterShare;
        }

        // 부동소수점 경계까지 포함해 유효 후보 하나를 반드시 돌려줍니다.
        if (commonSpec != null) return commonSpec;
        return PickCharacterSpec(characterGroups[characterGroups.Count - 1]);
    }

    // 2단계: 선택된 캐릭터 안에서 BubbleSO.spawnWeight 비율로 뽑습니다.
    private BubbleSO PickCharacterSpec(CharacterBubbleGroup group)
    {
        float roll = Random.Range(0f, group.TotalWeight);
        foreach (var spec in group.Specs)
        {
            if (roll < spec.spawnWeight) return spec;
            roll -= spec.spawnWeight;
        }

        return group.Specs[group.Specs.Count - 1];
    }
}
