"""
처리된 시트를 Unity에 적용하고, 반복 재생 사본을 만들어 기준 클립(Idle)과 나란히 녹화한다 — unity CLI로 실행 중인 에디터를 부른다.

    python record_compare.py Assets/_/Spirte/Priest/Priest_Skill1_v3.png [...] [--apply] [--seconds 6] [--scene "Assets/Scenes/New Scene.unity"]
→ Recordings/{시트 이름}_compare.mp4 (git 무시). 비교 대상은 그 캐릭터의 기준 시트 클립(character.json reference).
    python record_compare.py --clips A.anim B.anim C.anim --labels Idle v3 v4 --name Priest_Skill2_v4    # 클립 여러 개를 한 영상에
    python record_compare.py --showcase Priest                                                          # 컨트롤러의 모든 동작을 한 번씩
→ Recordings/{name}_compare.mp4 / Recordings/{캐릭터}_showcase.mp4. 시트(.png)를 주면 반복 클립을 Assets/_/_Compare/에 만든다.

배운 것 (2026-10-18~19, Priest):
  - 에디터 메인 스레드 명령은 5초 제한이 있다. 여러 장 Apply·Refresh는 응답만 실패하고 작업은 계속된다 → 한 장씩, 매번 status ready를 기다린다
  - PowerShell에서 `unity cmd eval '<코드>'`는 따옴표가 깨진다 → 코드는 파일로 eval_file
  - 비루프 클립을 그대로 녹화하면 한 번 재생 후 멈춘다 → Assets/_/_Compare/에 loopTime 켠 사본 (커밋 대상 아님)
  - 저장 안 된 Untitled 씬이 열려 있으면 녹화용 씬을 추가로 못 연다 → --scene으로 실제 씬을 먼저 연다
  - (2026-10-21) 에디터 창이 다른 창 뒤에 있으면 Unity가 플레이 모드 갱신을 2초에 5프레임 정도로 낮춘다 → 녹화가 끝나지 않는 것처럼
    보였다(6시간 멈춤). Run In Background는 켜져 있었고 일시정지도 아니었다. 기다리는 동안 EditorApplication.QueuePlayerLoopUpdate를
    계속 불러 갱신을 밀어 넣는다(pump). 녹화는 프레임 단위라 영상 속도는 정상이다
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(__file__))
import common as C  # noqa: E402

TMP = os.path.join(C.ROOT, "Temp", "RecordCompare")
DONE = os.path.join(C.ROOT, "Temp", "AnimCompare", "done.txt")


def unity_exe():
    exe = shutil.which("unity") or os.path.join(os.environ.get("LOCALAPPDATA", ""), "Unity", "bin", "unity.exe")
    if not os.path.exists(exe) and not shutil.which("unity"):
        sys.exit("unity CLI가 없다 — com.unity.pipeline README의 설치 명령으로 설치한다")
    return exe


def unity(*args, timeout=300):
    r = subprocess.run([unity_exe(), *args], cwd=C.ROOT, capture_output=True, text=True, encoding="utf-8", timeout=timeout)
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def wait_ready(limit=300):
    t = time.time()
    while time.time() - t < limit:
        code, out = unity("status")
        if code == 0 and "ready" in out:
            return
        time.sleep(2)
    sys.exit("에디터가 ready가 아니다 — 에디터가 열려 있는지, 컴파일 중인지 본다")


def eval_code(name, code):
    os.makedirs(TMP, exist_ok=True)
    path = os.path.join(TMP, f"{name}.cs")
    with open(path, "w", encoding="utf-8") as fp:
        fp.write(code)
    wait_ready()
    code_, out = unity("cmd", "eval_file", "--file", path, "--timeout", "120000", "--result-only")
    return out.strip()


LOOP_COPY = """
if (!UnityEditor.AssetDatabase.IsValidFolder("Assets/_/_Compare")) UnityEditor.AssetDatabase.CreateFolder("Assets/_", "_Compare");
string dst = "Assets/_/_Compare/{name}_loop.anim";
UnityEditor.AssetDatabase.DeleteAsset(dst);
// 적용 안 한 시트(비교용 새 버전)는 클립이 없다 — 시트에서 바로 반복 클립을 만든다
if (UnityEditor.AssetDatabase.LoadAssetAtPath<UnityEngine.AnimationClip>("{src}") == null) {
    UnityEditor.AssetDatabase.Refresh();
    SpriteAnimationPipeline.BuildClipAt("{sheet}", dst, true);
} else if (!UnityEditor.AssetDatabase.CopyAsset("{src}", dst)) return "copy failed: {src}";
var clip = UnityEditor.AssetDatabase.LoadAssetAtPath<UnityEngine.AnimationClip>(dst);
var s = UnityEditor.AnimationUtility.GetAnimationClipSettings(clip);
s.loopTime = true;
UnityEditor.AnimationUtility.SetAnimationClipSettings(clip, s);
UnityEditor.AssetDatabase.SaveAssets();
return dst + " " + clip.length.ToString("F2") + "s";
"""


PUMP = "UnityEditor.EditorApplication.QueuePlayerLoopUpdate(); return UnityEngine.Time.frameCount;"


def pump_until(done_path, limit):
    """
    done_path가 생길 때까지 에디터 갱신을 밀어 넣는다(창이 뒤에 있으면 플레이 모드가 거의 멈춘다).
    limit초 안에 안 끝나면 False. 프레임이 limit/3초 동안 전혀 안 늘면 멈춘 것으로 보고 False.
    """
    t = time.time()
    last, last_change = None, time.time()
    while time.time() - t < limit:
        if os.path.exists(done_path):
            return True
        code, out = unity("cmd", "eval", PUMP, "--result-only", timeout=30)
        frame = out.strip()
        if frame != last:
            last, last_change = frame, time.time()
        elif time.time() - last_change > limit / 3:
            return False
    return os.path.exists(done_path)


def read_done(path):
    if not os.path.exists(path):
        return "녹화 완료 표시가 없다 — 플레이 모드가 멈췄다면 EditorApplication.isPlaying = false 후 다시"
    with open(path, encoding="utf-8") as fp:
        return fp.read().strip()


def loop_clip(path, tag):
    """.anim이면 그대로, 시트(.png)면 Assets/_/_Compare/{이름}_loop.anim 반복 클립을 만들어 그 경로를 돌려준다."""
    path = os.path.relpath(os.path.abspath(path), C.ROOT).replace(os.sep, "/")
    if path.endswith(".anim"):
        return path
    name = os.path.splitext(os.path.basename(path))[0]
    dst = f"Assets/_/_Compare/{name}_loop.anim"
    code = ('UnityEditor.AssetDatabase.Refresh();\n'
            'if (!UnityEditor.AssetDatabase.IsValidFolder("Assets/_/_Compare")) UnityEditor.AssetDatabase.CreateFolder("Assets/_", "_Compare");\n'
            f'return SpriteAnimationPipeline.BuildClipAt("{path}", "{dst}", true);')
    print(eval_code(f"clip_{tag}", code)[:200])
    return dst


def record_clips(name, clips, labels, seconds, scene):
    wait_ready()
    unity("cmd", "open_scene", "--path", scene, "--result-only")
    if os.path.exists(DONE):
        os.remove(DONE)
    arr = lambda xs: "new[]{" + ", ".join(f'"{x}"' for x in xs) + "}"
    print(eval_code(f"rec_{name}", f'return AnimationCompareRecorder.Record("{name}", {arr(clips)}, {arr(labels)}, {seconds}f);')[:200])
    pump_until(DONE, seconds + 600)
    return read_done(DONE)


def record_showcase(character, scene):
    done = os.path.join(C.ROOT, "Temp", "AnimShowcase", "done.txt")
    wait_ready()
    unity("cmd", "open_scene", "--path", scene, "--result-only")
    if os.path.exists(done):
        os.remove(done)
    print(eval_code(f"showcase_{character}", f'return AnimationShowcaseRecorder.Record("{character}");')[:200])
    pump_until(done, 900)
    return read_done(done)


def main():
    C.utf8_stdout()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("sheets", nargs="*", help="처리된 시트 (Assets/_/Spirte/{캐릭터}/{이름}.png) — 각각 기준 Idle과 나란히")
    ap.add_argument("--clips", nargs="+", help="한 영상에 나란히 놓을 클립(.anim) 또는 처리된 시트(.png)")
    ap.add_argument("--labels", nargs="+", help="--clips 이름표 (영문 — 한글은 영상에 안 그려진다)")
    ap.add_argument("--name", help="--clips 영상 이름 → Recordings/{name}_compare.mp4")
    ap.add_argument("--showcase", help="캐릭터 이름 — 컨트롤러의 모든 동작을 한 번씩 → Recordings/{캐릭터}_showcase.mp4")
    ap.add_argument("--apply", action="store_true", help="녹화 전에 SpriteAnimationPipeline.Apply")
    ap.add_argument("--seconds", type=float, default=6)
    ap.add_argument("--scene", default="Assets/Scenes/New Scene.unity")
    args = ap.parse_args()
    if args.showcase:
        res = record_showcase(args.showcase, args.scene)
        print(f"RESULT {json.dumps({'ok': res.startswith('ok'), 'result': res}, ensure_ascii=False)}")
        return
    if args.clips:
        labels = args.labels or [os.path.splitext(os.path.basename(c))[0] for c in args.clips]
        if len(labels) != len(args.clips) or not args.name:
            sys.exit("--clips에는 같은 개수의 --labels와 --name이 필요하다")
        clips = [loop_clip(c, f"{args.name}_{k}") for k, c in enumerate(args.clips)]
        res = record_clips(args.name, clips, labels, args.seconds, args.scene)
        print(f"RESULT {json.dumps({'ok': res.startswith('ok'), 'result': res}, ensure_ascii=False)}")
        return
    if not args.sheets:
        sys.exit("시트, --clips, --showcase 중 하나가 필요하다")

    if args.apply:
        print(eval_code("refresh", "UnityEditor.AssetDatabase.Refresh(); return 0;"))
    results = {}
    scene_opened = False
    for sheet in args.sheets:
        sheet = os.path.relpath(os.path.abspath(sheet), C.ROOT).replace(os.sep, "/")
        name = os.path.splitext(os.path.basename(sheet))[0]
        character = name.split("_")[0]
        if args.apply:
            print(eval_code(f"apply_{name}", f'return SpriteAnimationPipeline.Apply("{sheet}");')[:300])
        with open(os.path.join(C.SHEET_ROOT, character, f"{character}.character.json"), encoding="utf-8") as fp:
            ref = json.load(fp)["reference"]
        src = f"Assets/_/_Anim/{character}/{name}.anim"
        print(eval_code(f"loop_{name}", LOOP_COPY.replace("{name}", name).replace("{src}", src).replace("{sheet}", sheet)))
        if not scene_opened:
            wait_ready()
            unity("cmd", "open_scene", "--path", args.scene, "--result-only")
            scene_opened = True
        if os.path.exists(DONE):
            os.remove(DONE)
        rec = (f'return AnimationCompareRecorder.Record("{name}", new[]{{"Assets/_/_Anim/{character}/{ref}.anim", '
               f'"Assets/_/_Compare/{name}_loop.anim"}}, new[]{{"{ref}", "{name}"}}, {args.seconds}f);')
        print(eval_code(f"rec_{name}", rec)[:200])
        pump_until(DONE, args.seconds + 600)
        results[name] = read_done(DONE)
        print(f"  {name}: {results[name]}")
        time.sleep(3)  # 플레이 모드가 끝나고 씬이 정리될 시간
    print(f"RESULT {json.dumps({'ok': all(v.startswith('ok') for v in results.values()), 'results': results}, ensure_ascii=False)}")


if __name__ == "__main__":
    main()
