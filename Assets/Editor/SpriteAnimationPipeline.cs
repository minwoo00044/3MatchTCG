using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using UnityEditor;
using UnityEditor.Animations;
using UnityEditor.U2D.Sprites;
using UnityEngine;

/// <summary>
/// scripts/process_sprite_sheet.py가 만든 아틀라스 + 매니페스트(.json)를 받아
/// 슬라이스 → 애니메이션 클립 → 캐릭터 AnimatorController 연결까지 한다.
///
/// 셀 크기, pivot, fps, loop는 전부 매니페스트에서 온다. 이 파일에서 다시 정하지 않는다.
///
///   unity cmd eval 'return SpriteAnimationPipeline.Apply("Assets/_/Spirte/Archer/Archer_Dead_v1.png");'
///
/// 실패하면 예외를 던진다 (eval 종료 코드 ≠ 0).
/// </summary>
public static class SpriteAnimationPipeline
{
    private const string SheetRoot = "Assets/_/Spirte";
    private const string AnimRoot = "Assets/_/_Anim";
    private const string ControllerRoot = "Assets/_/_AnimCon";
    private const float PixelsPerUnit = 100f;

    [Serializable]
    private class SheetManifest
    {
        public string name;
        public string character;
        public string action;
        public int cols;
        public int rows;
        public int frames;
        public int cellWidth;
        public int cellHeight;
        public float pivotX;
        public float pivotY;
        public int fps;
        public bool loop;
        public string[] warnings;
    }

    [MenuItem("Tools/Sprite Animation/Apply Selected Sheets")]
    private static void ApplySelected()
    {
        var paths = Selection.objects.OfType<Texture2D>().Select(AssetDatabase.GetAssetPath).ToArray();
        if (paths.Length == 0)
        {
            EditorUtility.DisplayDialog("Sprite Animation", "Project 창에서 스프라이트 시트를 선택한다.", "OK");
            return;
        }

        foreach (var path in paths)
        {
            try
            {
                Debug.Log($"[SpriteAnimationPipeline] {Apply(path)}");
            }
            catch (Exception e)
            {
                Debug.LogError($"[SpriteAnimationPipeline] {path}: {e.Message}");
            }
        }
    }

    public static string Apply(string sheetPath)
    {
        var manifest = LoadManifest(sheetPath);
        sheetPath = MoveIntoCharacterFolder(sheetPath, manifest);

        var sprites = Slice(sheetPath, manifest);
        string clipPath = WriteClip(sprites, manifest);
        string controllerPath = LinkController(clipPath, manifest);
        var archived = ArchivePreviousVersions(manifest);

        AssetDatabase.SaveAssets();

        string warn = manifest.warnings != null && manifest.warnings.Length > 0
            ? $" | 전처리 경고 {manifest.warnings.Length}건: {string.Join(" / ", manifest.warnings)}"
            : "";
        string prev = archived.Count > 0 ? $" | prev로 이동: {string.Join(", ", archived)}" : "";
        return $"{manifest.name}: {sprites.Length}프레임 {manifest.fps}fps loop={manifest.loop} → {clipPath}, {controllerPath} [{manifest.action}]{prev}{warn}";
    }

    /// <summary>
    /// 같은 캐릭터·액션의 낮은 버전 시트(+매니페스트)와 클립을 각 폴더의 prev/로 옮긴다.
    /// 지우지 않고 MoveAsset으로 옮기므로 GUID와 참조는 유지된다.
    /// </summary>
    private static List<string> ArchivePreviousVersions(SheetManifest m)
    {
        var moved = new List<string>();
        var pattern = new System.Text.RegularExpressions.Regex($"^{m.character}_{m.action}_v([0-9]+)$");
        int current = int.Parse(pattern.Match(m.name).Groups[1].Value);

        void ArchiveIn(string folder, string extension, bool withManifest)
        {
            foreach (string path in Directory.GetFiles(folder, "*" + extension))
            {
                string name = Path.GetFileNameWithoutExtension(path);
                var match = pattern.Match(name);
                if (!match.Success || int.Parse(match.Groups[1].Value) >= current)
                    continue;

                string prevFolder = EnsureFolder($"{folder}/prev");
                string from = $"{folder}/{name}{extension}";
                Move(from, $"{prevFolder}/{name}{extension}");
                if (withManifest && File.Exists(ManifestPathOf(from)))
                    Move(ManifestPathOf(from), ManifestPathOf($"{prevFolder}/{name}{extension}"));
                moved.Add(from);
            }
        }

        ArchiveIn($"{SheetRoot}/{m.character}", ".png", true);
        ArchiveIn($"{AnimRoot}/{m.character}", ".anim", false);
        return moved;
    }

    private static string ManifestPathOf(string sheetPath) => Path.ChangeExtension(sheetPath, ".json");

    private static SheetManifest LoadManifest(string sheetPath)
    {
        string manifestPath = ManifestPathOf(sheetPath);
        if (!File.Exists(manifestPath))
            throw new FileNotFoundException($"매니페스트가 없다: {manifestPath} — scripts/process_sprite_sheet.py로 먼저 만든다");

        var m = JsonUtility.FromJson<SheetManifest>(File.ReadAllText(manifestPath));
        if (string.IsNullOrEmpty(m.name) || string.IsNullOrEmpty(m.character) || string.IsNullOrEmpty(m.action))
            throw new InvalidDataException($"매니페스트 필드 누락: {manifestPath}");
        if (m.frames <= 0 || m.frames > m.cols * m.rows || m.fps <= 0 || m.cellWidth <= 0 || m.cellHeight <= 0)
            throw new InvalidDataException($"매니페스트 값이 잘못됐다: {manifestPath}");
        if (Path.GetFileNameWithoutExtension(sheetPath) != m.name)
            throw new InvalidDataException($"파일 이름 '{Path.GetFileNameWithoutExtension(sheetPath)}'과 매니페스트 이름 '{m.name}'이 다르다");
        return m;
    }

    /// <summary>시트와 매니페스트를 {SheetRoot}/{캐릭터}/ 로 옮긴다. MoveAsset이라 GUID는 유지된다.</summary>
    private static string MoveIntoCharacterFolder(string sheetPath, SheetManifest m)
    {
        string folder = EnsureFolder($"{SheetRoot}/{m.character}");
        string target = $"{folder}/{m.name}.png";
        if (sheetPath == target)
            return sheetPath;

        if (AssetDatabase.LoadMainAssetAtPath(target) != null)
            throw new IOException($"이동 대상에 이미 파일이 있다: {target}");

        string manifestPath = ManifestPathOf(sheetPath);
        Move(sheetPath, target);
        Move(manifestPath, ManifestPathOf(target));
        return target;
    }

    private static void Move(string from, string to)
    {
        string error = AssetDatabase.MoveAsset(from, to);
        if (!string.IsNullOrEmpty(error))
            throw new IOException($"{from} → {to} 이동 실패: {error}");
    }

    private static Sprite[] Slice(string sheetPath, SheetManifest m)
    {
        var importer = AssetImporter.GetAtPath(sheetPath) as TextureImporter
                       ?? throw new InvalidOperationException($"TextureImporter가 없다: {sheetPath}");

        int atlasW = m.cellWidth * m.cols;
        int atlasH = m.cellHeight * m.rows;

        importer.textureType = TextureImporterType.Sprite;
        importer.spriteImportMode = SpriteImportMode.Multiple;
        importer.spritePixelsPerUnit = PixelsPerUnit;
        importer.alphaIsTransparency = true;
        importer.mipmapEnabled = false;
        importer.isReadable = false;
        importer.filterMode = FilterMode.Bilinear;
        // 기본 2048을 넘는 아틀라스가 조용히 축소되지 않게 한다
        importer.maxTextureSize = Math.Max(2048, Mathf.NextPowerOfTwo(Math.Max(atlasW, atlasH)));

        var factory = new SpriteDataProviderFactories();
        factory.Init();
        var provider = factory.GetSpriteEditorDataProviderFromObject(importer);
        provider.InitSpriteEditorDataProvider();

        // 다시 슬라이스해도 프레임 번호가 같으면 같은 spriteID를 쓴다.
        // 이름이 바뀌어도(예: idle → Idle) 프리팹·씬의 스프라이트 참조가 끊기지 않는다.
        var previousIds = new Dictionary<int, GUID>();
        foreach (var old in provider.GetSpriteRects())
        {
            if (TryGetFrameIndex(old.name, out int i))
                previousIds[i] = old.spriteID;
        }

        var pivot = new Vector2(m.pivotX, m.pivotY);
        var rects = new SpriteRect[m.frames];
        for (int i = 0; i < m.frames; i++)
        {
            int col = i % m.cols;
            int row = i / m.cols;
            rects[i] = new SpriteRect
            {
                name = $"{m.name}_{i}",
                spriteID = previousIds.TryGetValue(i, out var id) ? id : GUID.Generate(),
                // 텍스처 좌표는 아래가 0 — 아틀라스 0행(맨 위)이 가장 큰 y
                rect = new Rect(col * m.cellWidth, (m.rows - 1 - row) * m.cellHeight, m.cellWidth, m.cellHeight),
                alignment = SpriteAlignment.Custom,
                pivot = pivot,
            };
        }

        provider.SetSpriteRects(rects);
        var nameIds = provider.GetDataProvider<ISpriteNameFileIdDataProvider>();
        nameIds?.SetNameFileIdPairs(rects.Select(r => new SpriteNameFileIdPair(r.name, r.spriteID)));
        provider.Apply();
        importer.SaveAndReimport();

        var tex = AssetDatabase.LoadAssetAtPath<Texture2D>(sheetPath);
        if (tex.width != atlasW || tex.height != atlasH)
            throw new InvalidDataException($"아틀라스 크기 {tex.width}x{tex.height}가 매니페스트 {atlasW}x{atlasH}와 다르다");

        var sprites = AssetDatabase.LoadAllAssetsAtPath(sheetPath)
            .OfType<Sprite>()
            .Where(s => s.name.StartsWith(m.name + "_") && TryGetFrameIndex(s.name, out _))
            .OrderBy(s => { TryGetFrameIndex(s.name, out int i); return i; })
            .ToArray();
        if (sprites.Length != m.frames)
            throw new InvalidDataException($"슬라이스 결과 {sprites.Length}장, 매니페스트 {m.frames}장");
        return sprites;
    }

    private static bool TryGetFrameIndex(string spriteName, out int index)
    {
        int underscore = spriteName.LastIndexOf('_');
        index = -1;
        return underscore >= 0 && int.TryParse(spriteName.Substring(underscore + 1), out index);
    }

    /// <summary>기존 클립이 있으면 내용만 바꾼다. 지우고 새로 만들면 GUID가 바뀌어 다른 참조가 끊긴다.</summary>
    private static string WriteClip(Sprite[] sprites, SheetManifest m)
    {
        string clipPath = $"{EnsureFolder($"{AnimRoot}/{m.character}")}/{m.name}.anim";
        var clip = AssetDatabase.LoadAssetAtPath<AnimationClip>(clipPath);
        bool created = clip == null;
        if (created)
            clip = new AnimationClip();

        clip.ClearCurves();
        foreach (var b in AnimationUtility.GetObjectReferenceCurveBindings(clip))
            AnimationUtility.SetObjectReferenceCurve(clip, b, null);

        clip.frameRate = m.fps;
        var binding = EditorCurveBinding.PPtrCurve("", typeof(SpriteRenderer), "m_Sprite");
        var keys = sprites
            .Select((s, i) => new ObjectReferenceKeyframe { time = i / (float)m.fps, value = s })
            .ToArray();
        AnimationUtility.SetObjectReferenceCurve(clip, binding, keys);

        var settings = AnimationUtility.GetAnimationClipSettings(clip);
        settings.loopTime = m.loop;
        AnimationUtility.SetAnimationClipSettings(clip, settings);

        if (created)
            AssetDatabase.CreateAsset(clip, clipPath);
        else
            EditorUtility.SetDirty(clip);
        return clipPath;
    }

    /// <summary>캐릭터당 컨트롤러 하나, 액션당 상태 하나. 같은 액션의 새 버전을 적용하면 그 상태의 클립이 바뀐다.</summary>
    private static string LinkController(string clipPath, SheetManifest m)
    {
        string controllerPath = $"{EnsureFolder(ControllerRoot)}/{m.character}.controller";
        var controller = AssetDatabase.LoadAssetAtPath<AnimatorController>(controllerPath)
                         ?? AnimatorController.CreateAnimatorControllerAtPath(controllerPath);

        var machine = controller.layers[0].stateMachine;
        var state = machine.states.Select(s => s.state).FirstOrDefault(s => s.name == m.action)
                    ?? machine.AddState(m.action);
        state.motion = AssetDatabase.LoadAssetAtPath<AnimationClip>(clipPath);

        if (m.action == "Idle")
            machine.defaultState = state;

        EditorUtility.SetDirty(controller);
        return controllerPath;
    }

    private static string EnsureFolder(string path)
    {
        if (AssetDatabase.IsValidFolder(path))
            return path;
        string parent = Path.GetDirectoryName(path).Replace('\\', '/');
        EnsureFolder(parent);
        AssetDatabase.CreateFolder(parent, Path.GetFileName(path));
        return path;
    }
}
