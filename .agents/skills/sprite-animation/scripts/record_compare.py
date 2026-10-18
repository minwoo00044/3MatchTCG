"""
처리된 시트를 Unity에 적용하고, 반복 재생 사본을 만들어 기준 클립(Idle)과 나란히 녹화한다 — unity CLI로 실행 중인 에디터를 부른다.

    python record_compare.py Assets/_/Spirte/Priest/Priest_Skill1_v3.png [...] [--apply] [--seconds 6] [--scene "Assets/Scenes/New Scene.unity"]
→ Recordings/{시트 이름}_compare.mp4 (git 무시). 비교 대상은 그 캐릭터의 기준 시트 클립(character.json reference).

배운 것 (2026-10-18~19, Priest):
  - 에디터 메인 스레드 명령은 5초 제한이 있다. 여러 장 Apply·Refresh는 응답만 실패하고 작업은 계속된다 → 한 장씩, 매번 status ready를 기다린다
  - PowerShell에서 `unity cmd eval '<코드>'`는 따옴표가 깨진다 → 코드는 파일로 eval_file
  - 비루프 클립을 그대로 녹화하면 한 번 재생 후 멈춘다 → Assets/_/_Compare/에 loopTime 켠 사본 (커밋 대상 아님)
  - 저장 안 된 Untitled 씬이 열려 있으면 녹화용 씬을 추가로 못 연다 → --scene으로 실제 씬을 먼저 연다
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
if (!UnityEditor.AssetDatabase.CopyAsset("{src}", dst)) return "copy failed: {src}";
var clip = UnityEditor.AssetDatabase.LoadAssetAtPath<UnityEngine.AnimationClip>(dst);
var s = UnityEditor.AnimationUtility.GetAnimationClipSettings(clip);
s.loopTime = true;
UnityEditor.AnimationUtility.SetAnimationClipSettings(clip, s);
UnityEditor.AssetDatabase.SaveAssets();
return dst + " " + clip.length.ToString("F2") + "s";
"""


def main():
    C.utf8_stdout()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("sheets", nargs="+", help="처리된 시트 (Assets/_/Spirte/{캐릭터}/{이름}.png)")
    ap.add_argument("--apply", action="store_true", help="녹화 전에 SpriteAnimationPipeline.Apply")
    ap.add_argument("--seconds", type=float, default=6)
    ap.add_argument("--scene", default="Assets/Scenes/New Scene.unity")
    args = ap.parse_args()

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
        print(eval_code(f"loop_{name}", LOOP_COPY.replace("{name}", name).replace("{src}", src)))
        if not scene_opened:
            wait_ready()
            unity("cmd", "open_scene", "--path", args.scene, "--result-only")
            scene_opened = True
        if os.path.exists(DONE):
            os.remove(DONE)
        rec = (f'return AnimationCompareRecorder.Record("{name}", new[]{{"Assets/_/_Anim/{character}/{ref}.anim", '
               f'"Assets/_/_Compare/{name}_loop.anim"}}, new[]{{"{ref}", "{name}"}}, {args.seconds}f);')
        print(eval_code(f"rec_{name}", rec)[:200])
        t = time.time()
        while not os.path.exists(DONE) and time.time() - t < args.seconds + 120:
            time.sleep(2)
        with open(DONE, encoding="utf-8") if os.path.exists(DONE) else open(os.devnull) as fp:
            results[name] = fp.read().strip() or "녹화 완료 표시가 없다"
        print(f"  {name}: {results[name]}")
        time.sleep(3)  # 플레이 모드가 끝나고 씬이 정리될 시간
    print(f"RESULT {json.dumps({'ok': all(v.startswith('ok') for v in results.values()), 'results': results}, ensure_ascii=False)}")


if __name__ == "__main__":
    main()
