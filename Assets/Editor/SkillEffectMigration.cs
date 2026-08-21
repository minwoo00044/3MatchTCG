using System.Collections.Generic;
using UnityEditor;
using UnityEngine;

public static class SkillEffectMigration
{
    private const string AmplifyActionPath = "Assets/_/_SO/ActionData/AmplifyAction.asset";
    private const string GrayscaleMaterialFolder = "Assets/_/_Material";
    private const string GrayscaleMaterialPath = GrayscaleMaterialFolder + "/PuzzleGrayscale.mat";
    private const string PuzzleViewPrefabPath = "Assets/_/_Prefab/shell.prefab";

    [MenuItem("Tools/3MatchTCG/Migrate Skill Effects")]
    public static void Migrate()
    {
        AmplifyAction amplifyAction = GetOrCreateAmplifyAction();
        string[] guids = AssetDatabase.FindAssets("t:SkillSO");
        int migrated = 0;

        foreach (string guid in guids)
        {
            string path = AssetDatabase.GUIDToAssetPath(guid);
            SkillSO skill = AssetDatabase.LoadAssetAtPath<SkillSO>(path);
            if (skill == null) continue;

            if (skill.effects == null) skill.effects = new List<SkillEffect>();

            if (skill.effects.Count == 0)
            {
                skill.effects.Add(new SkillEffect(
                    skill.action, skill.target, skill.value, skill.threatMultiplier));
                migrated++;
            }

            if (skill is BubbleSO && skill.SOName == "T_O" && amplifyAction != null
                && !ContainsAmplifyEffect(skill.effects))
            {
                skill.effects.Insert(0, new SkillEffect(amplifyAction, null, 0.2f, 0f));
            }

            EditorUtility.SetDirty(skill);
        }

        AssetDatabase.SaveAssets();
        AssetDatabase.Refresh();
        Debug.Log($"[SkillEffectMigration] {migrated}개 스킬의 레거시 효과를 마이그레이션했습니다.");
    }

    [MenuItem("Tools/3MatchTCG/Validate Skill Effects")]
    public static void Validate()
    {
        string[] guids = AssetDatabase.FindAssets("t:SkillSO");
        int invalid = 0;

        foreach (string guid in guids)
        {
            string path = AssetDatabase.GUIDToAssetPath(guid);
            SkillSO skill = AssetDatabase.LoadAssetAtPath<SkillSO>(path);
            if (skill == null) continue;

            if (skill.effects == null || skill.effects.Count == 0)
            {
                Debug.LogWarning($"[SkillEffectMigration] effects가 비었습니다: {path}", skill);
                invalid++;
                continue;
            }

            for (int i = 0; i < skill.effects.Count; i++)
            {
                SkillEffect effect = skill.effects[i];
                if (effect == null || effect.action == null
                    || (effect.action.RequiresTarget && effect.target == null)
                    || effect.value <= 0f)
                {
                    Debug.LogWarning($"[SkillEffectMigration] effects[{i}] 배선 오류: {path}", skill);
                    invalid++;
                }
            }
        }

        Debug.Log($"[SkillEffectMigration] 검증 완료. 오류 {invalid}건");
    }

    [MenuItem("Tools/3MatchTCG/Setup Puzzle Grayscale Material")]
    public static void SetupPuzzleGrayscaleMaterial()
    {
        Shader shader = Shader.Find("3MatchTCG/PuzzleGrayscale");
        if (shader == null)
        {
            Debug.LogWarning("[SkillEffectMigration] PuzzleGrayscale 셰이더를 찾지 못했습니다. 임포트 완료 후 다시 실행하세요.");
            return;
        }

        if (!AssetDatabase.IsValidFolder(GrayscaleMaterialFolder))
        {
            AssetDatabase.CreateFolder("Assets/_", "_Material");
        }

        Material material = AssetDatabase.LoadAssetAtPath<Material>(GrayscaleMaterialPath);
        if (material == null)
        {
            material = new Material(shader);
            AssetDatabase.CreateAsset(material, GrayscaleMaterialPath);
        }

        GameObject root = PrefabUtility.LoadPrefabContents(PuzzleViewPrefabPath);
        if (root == null)
        {
            Debug.LogWarning($"[SkillEffectMigration] PuzzleView 프리팹을 찾지 못했습니다: {PuzzleViewPrefabPath}");
            return;
        }

        foreach (SpriteRenderer renderer in root.GetComponentsInChildren<SpriteRenderer>(true))
        {
            renderer.sharedMaterial = material;
        }

        PrefabUtility.SaveAsPrefabAsset(root, PuzzleViewPrefabPath);
        PrefabUtility.UnloadPrefabContents(root);
        AssetDatabase.SaveAssets();
        Debug.Log("[SkillEffectMigration] PuzzleView 회색조 Material 배선을 완료했습니다.");
    }

    private static AmplifyAction GetOrCreateAmplifyAction()
    {
        AmplifyAction found = AssetDatabase.LoadAssetAtPath<AmplifyAction>(AmplifyActionPath);
        if (found != null) return found;

        found = ScriptableObject.CreateInstance<AmplifyAction>();
        AssetDatabase.CreateAsset(found, AmplifyActionPath);
        return found;
    }

    private static bool ContainsAmplifyEffect(List<SkillEffect> effects)
    {
        foreach (var effect in effects)
        {
            if (effect?.action is AmplifyAction) return true;
        }
        return false;
    }
}
