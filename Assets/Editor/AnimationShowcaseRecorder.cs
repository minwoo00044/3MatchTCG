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
/// 캐릭터 AnimatorController의 모든 상태(액션)를 한 번씩 재생하며 Unity Recorder로 MP4를 녹화한다.
///
///   unity cmd eval 'return AnimationShowcaseRecorder.Record("Archer");'
///   → Recordings/{캐릭터}_showcase.mp4, 끝나면 Temp/AnimShowcase/done.txt 에 결과 한 줄
///
/// 열려 있는 씬은 건드리지 않는다: 시연용 씬을 추가(additive)로 열고, 멀리 떨어진 곳에 캐릭터와 전용 카메라를 둔 뒤
/// 카메라 → 렌더텍스처만 녹화한다. 녹화가 끝나면 플레이를 멈추고 시연 씬을 닫는다.
/// Recorder는 플레이 모드에서만 돌고 플레이 진입 시 도메인 리로드가 일어나서, 진행 상태는 SessionState에 둔다.
/// </summary>
[InitializeOnLoad]
public static class AnimationShowcaseRecorder
{
    private const string ControllerRoot = "Assets/_/_AnimCon";
    private const string KeyCharacter = "AnimShowcase.Character";
    private const string KeyScene = "AnimShowcase.ScenePath";
    private const string DoneFile = "Temp/AnimShowcase/done.txt";
    private const string ActorName = "__ShowcaseActor";
    private static readonly Vector3 Stage = new Vector3(10000f, 10000f, 0f); // 열린 씬의 카메라에 잡히지 않는 위치
    private static readonly string[] Order = { "Idle", "Hit", "Skill1", "Skill2", "Skill3", "Skill4", "Skill5", "Dead" };
    private const float LoopSeconds = 2.5f;  // 루프 액션(Idle)을 보여 줄 시간
    private const float HoldSeconds = 0.7f;  // 비루프 액션이 끝난 뒤 마지막 프레임을 보여 줄 시간
    private const int Width = 1280, Height = 720;

    private static RecorderController _recorder;
    private static List<(string state, float seconds)> _plan;
    private static int _index;
    private static float _stepStart;
    private static Animator _animator;
    private static TextMesh _label;
    private static RenderTexture _rt;
    private static bool _snapped;

    static AnimationShowcaseRecorder()
    {
        EditorApplication.playModeStateChanged += OnPlayModeChanged;
    }

    public static string Record(string character)
    {
        if (EditorApplication.isPlayingOrWillChangePlaymode)
            return "플레이 중에는 시작할 수 없다";
        string controllerPath = $"{ControllerRoot}/{character}.controller";
        var controller = AssetDatabase.LoadAssetAtPath<AnimatorController>(controllerPath);
        if (controller == null)
            return $"컨트롤러가 없다: {controllerPath}";

        if (Directory.Exists(Path.GetDirectoryName(DoneFile)))
            Directory.Delete(Path.GetDirectoryName(DoneFile), true);
        Directory.CreateDirectory(Path.GetDirectoryName(DoneFile));

        var scene = EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Additive);
        var actor = new GameObject(ActorName);
        SceneManager.MoveGameObjectToScene(actor, scene);
        actor.transform.position = Stage;
        actor.AddComponent<SpriteRenderer>();
        actor.AddComponent<Animator>().runtimeAnimatorController = controller;

        var label = new GameObject("__ShowcaseLabel");
        SceneManager.MoveGameObjectToScene(label, scene);
        var text = label.AddComponent<TextMesh>();
        text.anchor = TextAnchor.UpperCenter;
        text.characterSize = 0.08f;
        text.fontSize = 64;
        text.color = Color.white;

        var cam = new GameObject("__ShowcaseCamera");
        SceneManager.MoveGameObjectToScene(cam, scene);
        var camera = cam.AddComponent<Camera>();
        camera.orthographic = true;
        camera.clearFlags = CameraClearFlags.SolidColor;
        camera.backgroundColor = new Color(0.22f, 0.24f, 0.28f);
        camera.depth = -100;
        FrameCamera(controller, camera, text);

        SessionState.SetString(KeyCharacter, character);
        SessionState.SetString(KeyScene, scene.handle.ToString());
        EditorApplication.isPlaying = true;
        return $"{character} 녹화 시작 — 끝나면 {DoneFile}";
    }

    /// <summary>모든 클립의 모든 스프라이트 범위를 합쳐 카메라와 라벨 위치를 정한다(pivot = 발 위치 = Stage).</summary>
    private static void FrameCamera(AnimatorController controller, Camera camera, TextMesh label)
    {
        Bounds? all = null;
        foreach (var clip in controller.animationClips)
        {
            foreach (var binding in AnimationUtility.GetObjectReferenceCurveBindings(clip))
            {
                foreach (var key in AnimationUtility.GetObjectReferenceCurve(clip, binding))
                {
                    if (key.value is Sprite sprite)
                    {
                        var b = sprite.bounds;
                        if (all == null) all = b;
                        else { var u = all.Value; u.Encapsulate(b); all = u; }
                    }
                }
            }
        }
        var bounds = all ?? new Bounds(Vector3.up * 2.5f, new Vector3(5f, 5f, 0f));
        float aspect = (float)Width / Height;
        float half = Mathf.Max(bounds.extents.y, bounds.extents.x / aspect) * 1.15f + 0.6f; // 위쪽 라벨 자리
        camera.orthographicSize = half;
        camera.transform.position = Stage + new Vector3(bounds.center.x, bounds.center.y + 0.3f, -10f);
        label.transform.position = Stage + new Vector3(bounds.center.x, bounds.center.y + half + 0.15f, 0f);
    }

    private static void OnPlayModeChanged(PlayModeStateChange change)
    {
        string character = SessionState.GetString(KeyCharacter, "");
        if (string.IsNullOrEmpty(character))
            return;
        if (change == PlayModeStateChange.EnteredPlayMode)
            Begin(character);
        else if (change == PlayModeStateChange.EnteredEditMode)
            Cleanup();
    }

    private static void Begin(string character)
    {
        var actor = GameObject.Find(ActorName);
        var cam = GameObject.Find("__ShowcaseCamera");
        if (actor == null || cam == null)
        {
            Finish("시연 오브젝트를 찾지 못했다");
            return;
        }
        _animator = actor.GetComponent<Animator>();
        _label = GameObject.Find("__ShowcaseLabel").GetComponent<TextMesh>();
        var camera = cam.GetComponent<Camera>();
        var rt = _rt = new RenderTexture(Width, Height, 24);
        camera.targetTexture = rt;

        var controller = (AnimatorController)_animator.runtimeAnimatorController;
        var states = controller.layers[0].stateMachine.states.Select(s => s.state).ToList();
        _plan = new List<(string, float)>();
        foreach (var name in Order.Concat(states.Select(s => s.name).Where(n => !Order.Contains(n))))
        {
            var state = states.FirstOrDefault(s => s.name == name);
            if (state?.motion is AnimationClip clip)
                _plan.Add((name, clip.isLooping ? Mathf.Max(LoopSeconds, clip.length * 2) : clip.length + HoldSeconds));
        }

        var settings = ScriptableObject.CreateInstance<RecorderControllerSettings>();
        var movie = ScriptableObject.CreateInstance<MovieRecorderSettings>();
        movie.name = $"{character} showcase";
        movie.Enabled = true;
        movie.EncoderSettings = new CoreEncoderSettings
        {
            Codec = CoreEncoderSettings.OutputCodec.MP4,
            EncodingQuality = CoreEncoderSettings.VideoEncodingQuality.High,
        };
        movie.ImageInputSettings = new RenderTextureInputSettings { RenderTexture = rt };
        movie.AudioInputSettings.PreserveAudio = false;
        movie.OutputFile = Path.Combine(Path.GetFullPath("Recordings"), $"{character}_showcase").Replace('\\', '/');
        settings.AddRecorderSettings(movie);
        settings.SetRecordModeToManual();
        settings.FrameRate = 30;
        _recorder = new RecorderController(settings);
        _recorder.PrepareRecording();
        _recorder.StartRecording();

        _index = -1;
        Next();
        EditorApplication.update += Tick;
    }

    private static void Next()
    {
        _index++;
        if (_index >= _plan.Count)
        {
            _recorder.StopRecording();
            EditorApplication.update -= Tick;
            string file = $"Recordings/{SessionState.GetString(KeyCharacter, "")}_showcase.mp4";
            Finish($"ok {file} ({string.Join(", ", _plan.Select(p => $"{p.state} {p.seconds:0.0}s"))})");
            EditorApplication.isPlaying = false;
            return;
        }
        var (state, _) = _plan[_index];
        _label.text = state;
        _animator.Play(state, 0, 0f);
        _stepStart = Time.time;
        _snapped = false;
        Progress($"{_index} {state} 시작 t={Time.time:0.00}");
    }

    private static void Tick()
    {
        if (!EditorApplication.isPlaying || _plan == null)
            return;
        float elapsed = Time.time - _stepStart;
        if (!_snapped && elapsed >= _plan[_index].seconds * 0.45f)
        {
            Snapshot(_plan[_index].state);  // 확인용: 동작마다 중간 장면 한 장
            _snapped = true;
        }
        if (elapsed >= _plan[_index].seconds)
            Next();
    }

    private static void Snapshot(string state)
    {
        var prev = RenderTexture.active;
        RenderTexture.active = _rt;
        var tex = new Texture2D(Width, Height, TextureFormat.RGB24, false);
        tex.ReadPixels(new Rect(0, 0, Width, Height), 0, 0);
        tex.Apply();
        RenderTexture.active = prev;
        File.WriteAllBytes($"{Path.GetDirectoryName(DoneFile)}/{_index}_{state}.png", tex.EncodeToPNG());
        Object.DestroyImmediate(tex);
    }

    private static void Progress(string line)
    {
        File.AppendAllText($"{Path.GetDirectoryName(DoneFile)}/progress.txt", line + "\n");
    }

    private static void Finish(string message)
    {
        Directory.CreateDirectory(Path.GetDirectoryName(DoneFile));
        File.WriteAllText(DoneFile, message);
        Debug.Log($"[AnimationShowcaseRecorder] {message}");
    }

    /// <summary>플레이가 끝나면 시연용 씬을 닫는다. 열려 있던 씬과 그 미저장 변경은 그대로 둔다.</summary>
    private static void Cleanup()
    {
        Progress("플레이 종료 감지");
        SessionState.EraseString(KeyCharacter);
        SessionState.EraseString(KeyScene);
        for (int i = EditorSceneManager.sceneCount - 1; i >= 0; i--)
        {
            var s = EditorSceneManager.GetSceneAt(i);
            if (s.GetRootGameObjects().Any(g => g.name == ActorName))
                EditorSceneManager.CloseScene(s, true);
        }
        if (!File.Exists(DoneFile))
            Finish("플레이가 녹화 완료 전에 끝났다");
    }
}
