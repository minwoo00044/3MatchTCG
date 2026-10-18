"""
{캐릭터}/source~/{액션}/process.json 대로 원본 프레임을 조립·처리한다 — 어느 PC에서든 현재 버전을 다시 만들 수 있게.

    python source_build.py --character Priest --action Skill3 --name Priest_Skill3_v4 [--out_dir SpriteRegen/_cand] [--analyze]
    python source_build.py --character Priest --list

배경 (2026-10-19 사용자 교훈 "PC 간 도구 공유가 안 된다"): 적용 시트의 처리 입력과 옵션이 git 무시 SpriteRegen/ 와
대화 기록에만 있어, 다른 PC에서는 같은 결과를 다시 만들거나 일부만 고칠 수 없었다.
확정된 입력은 source~/ (Unity 미임포트, git 포함)에 두고, 처리 방법은 process.json에 남긴다.

process.json (경로는 이 액션 폴더 기준):
  {"applied": "Priest_Skill3_v3",                    # 이 설정으로 만든 적용 버전 (기록)
   "assemble": "recipe.json",                         # (선택) smear.py 레시피 — 조립 결과가 splice 앞에 온다
   "splice": ["try1.png:2x2:1,2,3", "try2.png:2x2:1,2,3,4"],   # (선택) splice_frames 항목
   "inputs": ["try5.png", "try6.png"],                # splice가 없을 때 process_sprite_sheet --input
   "process": ["--cols", "7", "--rows", "1", ...]}    # --input/--name/--out_dir 를 뺀 처리 옵션
"""
import argparse
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(__file__))
import common as C  # noqa: E402
import smear  # noqa: E402

SK = os.path.dirname(os.path.abspath(__file__))


def action_dir(character, action):
    return os.path.join(C.SHEET_ROOT, character, C.P.SOURCE_DIR, action)


def rel(p):
    return os.path.relpath(p, C.ROOT).replace(os.sep, "/")


def run(cmd):
    print("  $", " ".join(cmd))
    r = subprocess.run(cmd, cwd=C.ROOT, capture_output=True, text=True, encoding="utf-8")
    sys.stdout.write("".join(l + "\n" for l in r.stdout.splitlines() if l.startswith(("RESULT", "  [경고]"))))
    if r.returncode != 0:
        sys.stdout.write(r.stdout[-2000:] + r.stderr[-2000:])
        sys.exit(r.returncode)
    return r.stdout


def build(args):
    d = action_dir(args.character, args.action)
    with open(os.path.join(d, "process.json"), encoding="utf-8") as fp:
        spec = json.load(fp)
    entries = []
    if spec.get("assemble"):
        entries += smear.assemble(os.path.join(d, spec["assemble"]))
    entries += [f"{rel(os.path.join(d, e.split(':', 1)[0]))}:{e.split(':', 1)[1]}" for e in spec.get("splice", [])]
    if entries:
        joined = os.path.join(C.REGEN_ROOT, f"{args.character}_{args.action}", "source_splice.png")
        os.makedirs(os.path.dirname(joined), exist_ok=True)
        run([sys.executable, os.path.join(SK, "splice_frames.py"), "--fit", "none", "--out", rel(joined), *entries])
        inputs = [rel(joined)]
    else:
        inputs = [rel(os.path.join(d, p)) for p in spec["inputs"]]
    cmd = [sys.executable, os.path.join("scripts", "process_sprite_sheet.py"), "--input", *inputs, "--name", args.name, *spec["process"]]
    if args.out_dir:
        cmd += ["--out_dir", args.out_dir]
    if args.analyze:
        cmd.append("--analyze")
    run(cmd)


def main():
    C.utf8_stdout()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--character", required=True)
    ap.add_argument("--action")
    ap.add_argument("--name", help="{캐릭터}_{액션}_v{N}")
    ap.add_argument("--out_dir")
    ap.add_argument("--analyze", action="store_true")
    ap.add_argument("--list", action="store_true")
    args = ap.parse_args()
    if args.list:
        root = os.path.join(C.SHEET_ROOT, args.character, C.P.SOURCE_DIR)
        for a in sorted(os.listdir(root)) if os.path.isdir(root) else []:
            p = os.path.join(root, a, "process.json")
            if os.path.exists(p):
                with open(p, encoding="utf-8") as fp:
                    print(f"{a}: {json.load(fp).get('applied')}")
        return
    if not (args.action and args.name):
        ap.error("--action과 --name이 필요하다")
    build(args)


if __name__ == "__main__":
    main()
