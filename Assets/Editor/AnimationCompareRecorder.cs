using System.Collections.Generic;
using System.IO;
using System.Linq;
using UnityEditor;
using UnityEditor.Animations;
using UnityEditor.Recorder;
using UnityEditor.Recorder.Encoder;
using UnityEditor.Recorder.Input;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.SceneManagement;

/// <summary>
/// 같은 동작의 여러 버전(클립)을 나란히 반복 재생하며 Unity Recorder로 한 영상에 녹화한다.
/// 사용자가 "어색하다"를 말로 짚기 어려울 때 "어느 쪽이 나은지"를 고르게 하려는 도구다(2026-10-15).
///
///   unity cmd eval 'return AnimationCompareRecorder.Record("Knight_Skill2", new[]{"Assets/_/_Compare/A.anim", ...}, new[]{"A 지금", ...}, 6f);'
///   → Recordings/{name}_compare.mp4, 끝나면 Temp/AnimCompare/done.txt
///
/// 열린 씬은 건드리지 않는다: 시연 씬을 추가로 열어 멀리 떨어진 곳에서 전용 카메라 → 렌더텍스처만 녹화하고, 끝나면 닫는다.
/// 클립마다 루프 컨트롤러를 Assets/_/_Compare/ 에 만든다(녹화가 끝나도 남겨 둔다 — 에디터에서 다시 볼 수 있게).
/// </summary>
[InitializeOnLoad]
public static class AnimationCompareRecorder
{
    private const string CompareRoot = "Assets/_/_Compare";
    private const string KeyName = "AnimCompare.Name";
    private const string KeySeconds = "AnimCompare.Seconds";
    private const string DoneFile = "Temp/AnimCompare/done.txt";
    private const string ActorPrefix = "__CompareActor";
    private static readonly Vector3 Stage = new Vector3(20000f, 20000f, 0f);
    private const int Width = 1920, Height = 720;

    private static RecorderController _recorder;
    private static float _start;

    static AnimationCompareRecorder()
    {
        EditorApplication.playModeStateChanged += OnPlayModeChanged;
    }

    public static string Record(string name, string[] clipPaths, string[] labels, float seconds)
    {
        if (EditorApplication.isPlayingOrWillChangePlaymode)
            return "플레이 중에는 시작할 수 없다";
        if (clipPaths.Length != labels.Length)
            return "clipPaths와 labels 개수가 다르다";
        Directory.CreateDirectory(Path.GetDirectoryName(DoneFile));
        File.Delete(DoneFile);

        var clips = clipPaths.Select(p => AssetDatabase.LoadAssetAtPath<AnimationClip>(p)).ToArray();
        for (int i = 0; i < clips.Length; i++)
            if (clips[i] == null)
                return $"클립이 없다: {clipPaths[i]}";

        // 칸 크기: 모든 클립 스프라이트 범위의 합집합 (pivot = 발)
        Bounds? all = null;
        foreach (var clip in clips)
            foreach (var b in AnimationUtility.GetObjectReferenceCurveBindings(clip))
                foreach (var k in AnimationUtility.GetObjectReferenceCurve(clip, b))
                    if (k.value is Sprite s)
                    {
                        if (all == null) all = s.bounds;
                        else { var u = all.Value; u.Encapsulate(s.bounds); all = u; }
                    }
        var bounds = all ?? new Bounds(Vector3.up * 2.5f, new Vector3(5f, 5f, 0f));
        float slot = bounds.size.x * 1.05f;

        // _Compare/는 커밋하지 않는 폴더라 새 PC에는 없다 — 없으면 CreateAnimatorControllerAtPath가 실패한다
        if (!AssetDatabase.IsValidFolder(CompareRoot))
            AssetDatabase.CreateFolder(Path.GetDirectoryName(CompareRoot).Replace('\\', '/'), Path.GetFileName(CompareRoot));

        var scene = EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Additive);
        for (int i = 0; i < clips.Length; i++)
        {
            string ctrlPath = $"{CompareRoot}/{Path.GetFileNameWithoutExtension(clipPaths[i])}.controller";
            var ctrl = AnimatorController.CreateAnimatorControllerAtPath(ctrlPath);
            ctrl.layers[0].stateMachine.AddState("Play").motion = clips[i];

            var go = new GameObject($"{ActorPrefix}{i}");
            SceneManager.MoveGameObjectToScene(go, scene);
            float x = (i - (clips.Length - 1) / 2f) * slot - bounds.center.x;
            go.transform.position = Stage + new Vector3(x, 0f, 0f);
            go.AddComponent<SpriteRenderer>();
            go.AddComponent<Animator>().runtimeAnimatorController = ctrl;

            var label = new GameObject($"__CompareLabel{i}");
            SceneManager.MoveGameObjectToScene(label, scene);
            var text = label.AddComponent<TextMesh>();
            text.text = labels[i];
            text.anchor = TextAnchor.UpperCenter;
            text.characterSize = 0.08f;
            text.fontSize = 64;
            text.color = Color.white;
            label.transform.position = Stage + new Vector3(x + bounds.center.x, bounds.max.y + 0.6f, 0f);
        }

        var cam = new GameObject("__CompareCamera");
        SceneManager.MoveGameObjectToScene(cam, scene);
        var camera = cam.AddComponent<Camera>();
        camera.orthographic = true;
        camera.clearFlags = CameraClearFlags.SolidColor;
        camera.backgroundColor = new Color(0.22f, 0.24f, 0.28f);
        camera.depth = -100;
        float width = slot * clips.Length;
        float height = bounds.size.y + 1.2f;
        camera.orthographicSize = Mathf.Max(height, width * Height / Width) / 2f * 1.05f;
        camera.transform.position = Stage + new Vector3(0f, bounds.center.y + 0.3f, -10f);

        AssetDatabase.SaveAssets();
        SessionState.SetString(KeyName, name);
        SessionState.SetFloat(KeySeconds, seconds);
        EditorApplication.isPlaying = true;
        return $"{name} 비교 녹화 시작 ({clips.Length}개) — 끝나면 {DoneFile}";
    }

    private static void OnPlayModeChanged(PlayModeStateChange change)
    {
        string name = SessionState.GetString(KeyName, "");
        if (string.IsNullOrEmpty(name))
            return;
        if (change == PlayModeStateChange.EnteredPlayMode)
            Begin(name);
        else if (change == PlayModeStateChange.EnteredEditMode)
            Cleanup();
    }

    private static void Begin(string name)
    {
        var cam = GameObject.Find("__CompareCamera")?.GetComponent<Camera>();
        if (cam == null)
        {
            Finish("시연 오브젝트를 찾지 못했다");
            return;
        }
        var rt = new RenderTexture(Width, Height, 24);
        cam.targetTexture = rt;

        var settings = ScriptableObject.CreateInstance<RecorderControllerSettings>();
        var movie = ScriptableObject.CreateInstance<MovieRecorderSettings>();
        movie.name = $"{name} compare";
        movie.Enabled = true;
        movie.EncoderSettings = new CoreEncoderSettings
        {
            Codec = CoreEncoderSettings.OutputCodec.MP4,
            EncodingQuality = CoreEncoderSettings.VideoEncodingQuality.High,
        };
        movie.ImageInputSettings = new RenderTextureInputSettings { RenderTexture = rt };
        movie.AudioInputSettings.PreserveAudio = false;
        movie.OutputFile = Path.Combine(Path.GetFullPath("Recordings"), $"{name}_compare").Replace('\\', '/');
        settings.AddRecorderSettings(movie);
        settings.SetRecordModeToManual();
        settings.FrameRate = 30;
        _recorder = new RecorderController(settings);
        _recorder.PrepareRecording();
        _recorder.StartRecording();
        _start = Time.time;
        EditorApplication.update += Tick;
    }

    private static void Tick()
    {
        if (!EditorApplication.isPlaying)
            return;
        if (Time.time - _start < SessionState.GetFloat(KeySeconds, 6f))
            return;
        EditorApplication.update -= Tick;
        _recorder.StopRecording();
        Finish($"ok Recordings/{SessionState.GetString(KeyName, "")}_compare.mp4");
        EditorApplication.isPlaying = false;
    }

    private static void Finish(string message)
    {
        Directory.CreateDirectory(Path.GetDirectoryName(DoneFile));
        File.WriteAllText(DoneFile, message);
        Debug.Log($"[AnimationCompareRecorder] {message}");
    }

    private static void Cleanup()
    {
        SessionState.EraseString(KeyName);
        for (int i = EditorSceneManager.sceneCount - 1; i >= 0; i--)
        {
            var s = EditorSceneManager.GetSceneAt(i);
            if (s.GetRootGameObjects().Any(g => g.name.StartsWith(ActorPrefix)))
                EditorSceneManager.CloseScene(s, true);
        }
        if (!File.Exists(DoneFile))
            Finish("플레이가 녹화 완료 전에 끝났다");
    }
}
