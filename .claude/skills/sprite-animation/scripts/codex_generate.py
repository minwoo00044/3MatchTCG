"""
Codex(codex exec + 이미지 생성)로 스프라이트 시트를 기준 체형에 맞춰 다시 그린다.

  python codex_generate.py --reference Assets/_/Spirte/Archer/Archer_Idle_v3.png --action Hit \
      --action-desc "hit / damaged reaction animation" \
      --fix "Head is about 11% too large -> smaller head" \
      [--previous SpriteRegen/Archer_Hit/try2/result.png --previous-note "head and hair correct, boots 16% too big"] \
      [--original <파일>] [--dry-run]

- 실행 전에 Codex 5시간 사용량을 확인하고 --limit(기본 85%) 이상이면 생성하지 않는다 (종료 코드 3).
- 작업 폴더: SpriteRegen/{캐릭터}_{액션}/try{N}/  (N은 실제 생성만 센다, git 무시)
  --dry-run은 SpriteRegen/{캐릭터}_{액션}/dryrun/ 에 덮어쓰고 시도 번호를 쓰지 않는다.
    character_reference.png  사용자가 지정한 기준 시트(--reference)의 0번 프레임
    original.png             다시 그릴 원본 시트
    previous_*.png           이전 시도 (--previous)
    prompt.md, log.txt, result.png
- 원본을 생략하면 사용자가 그 액션의 첫 버전(보통 v1, prev/ 포함)으로 넣은 파일(매니페스트 source)을 쓴다.
  그 파일이 없으면 원본이 없는 것이다 — 다른 곳(Downloads 등)을 찾지 않고 종료한다.
- 종료 코드 0 생성 성공 / 1 실패 / 3 사용량 한도. 마지막 줄은 RESULT {json}.
오래 걸리므로(수 분) 백그라운드로 돌리고 끝나면 sheet_check.py verify로 검증한다.
"""
import argparse
import glob
import json
import os
import re
import shutil
import subprocess
import sys

from PIL import Image

sys.path.insert(0, os.path.dirname(__file__))
import common as C  # noqa: E402
import codex_usage  # noqa: E402
import sheet_check as SC  # noqa: E402

TEMPLATE = os.path.join(os.path.dirname(__file__), "..", "assets", "generate_prompt.md")


def slash(p):
    return p.replace("\\", "/")


def done(ok, code, **kw):
    print(f"RESULT {json.dumps({'ok': ok, **kw}, ensure_ascii=False)}")
    sys.exit(code)


def resolve_original(character, action, given):
    if given:
        if not os.path.exists(given):
            done(False, 1, error=f"--original 파일이 없다: {given}")
        return given
    src, why = C.resolve_original(character, action)
    if src is None:
        done(False, 1, error=f"{why} — 원본이 없으므로 재생성할 수 없다. 사용자에게 원본 파일을 받는다")
    return src


def grid_of(path):
    manifest = os.path.splitext(path)[0] + ".json"
    if os.path.exists(manifest):
        with open(manifest, encoding="utf-8") as fp:
            m = json.load(fp)
        return m["cols"], m["rows"], m["frames"]
    return 4, 2, 8


def main():
    C.utf8_stdout()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--reference", required=True, help="사용자가 지정한 기준 시트 (Assets/_/Spirte/{캐릭터}/...)")
    ap.add_argument("--action", required=True, help="Idle | Hit | Skill1~9 | Dead")
    ap.add_argument("--action-desc", required=True, help="영어로 동작 설명. 프레임 흐름의 핵심(예: frame 1 stands upright)도 적는다")
    ap.add_argument("--fix", action="append", default=[], help="고칠 점 (영어, 측정값 포함). 여러 번 지정")
    ap.add_argument("--previous", action="append", default=[], help="이전 시도 이미지")
    ap.add_argument("--previous-note", action="append", default=[], help="--previous 순서대로 무엇이 맞고 틀렸는지 (영어)")
    ap.add_argument("--original")
    ap.add_argument("--limit", type=float, default=85)
    ap.add_argument("--timeout", type=int, default=900)
    ap.add_argument("--dry-run", action="store_true", help="dryrun/ 폴더에 프롬프트만 만들고 Codex는 호출하지 않는다")
    args = ap.parse_args()

    if len(args.previous_note) not in (0, len(args.previous)):
        done(False, 1, error="--previous-note 개수가 --previous와 다르다")
    if not os.path.exists(args.reference):
        done(False, 1, error=f"기준 시트가 없다: {args.reference}")

    if not args.dry_run:
        usage, err = codex_usage.read_usage()
        if usage is None:
            done(False, 1, error=f"Codex 사용량 조회 실패: {err}")
        if usage["primary"] >= args.limit:
            done(False, 3, error=f"Codex 5시간 사용량 {usage['primary']}% ≥ {args.limit:g}% — 생성 중단", usage=usage)

    character = SC.character_of(args.reference)
    original = resolve_original(character, args.action, args.original)
    cols, rows, frames = grid_of(original)

    base = os.path.join(C.REGEN_ROOT, f"{character}_{args.action}")
    if args.dry_run:
        n = None
        work = os.path.join(base, "dryrun")
        shutil.rmtree(work, ignore_errors=True)
    else:
        n = len([d for d in glob.glob(os.path.join(base, "try*")) if os.path.isdir(d)]) + 1
        work = os.path.join(base, f"try{n}")
    os.makedirs(work)

    SC.check_reference(args.reference)
    palette = SC.load_palette(character, None)
    ref_frames, ref_f0, _ = SC.reference(args.reference, palette)
    ref = C.crop_frame(ref_frames[0]["image"])
    bg = Image.new("RGBA", ref.size, (255, 255, 255, 255))
    bg.alpha_composite(ref)
    bg.convert("RGB").save(os.path.join(work, "character_reference.png"))
    shutil.copy(original, os.path.join(work, "original.png"))

    images = ["character_reference.png", "original.png"]
    extra = []
    for i, prev in enumerate(args.previous, start=3):
        name = f"previous_{i}.png"
        shutil.copy(prev, os.path.join(work, name))
        images.append(name)
        note = args.previous_note[i - 3] if args.previous_note else "an earlier redraw"
        extra.append(f"{i}. {name} — {note}")

    with open(TEMPLATE, encoding="utf-8") as fp:
        prompt = fp.read()
    prompt = (prompt.replace("{GRID}", f"{cols}x{rows}").replace("{COLS}", str(cols)).replace("{ROWS}", str(rows))
              .replace("{FRAMES}", str(frames)).replace("{ACTION}", args.action_desc)
              .replace("{HEAD_PCT}", str(round(ref_f0["head"] * 100)))
              .replace("{EXTRA_REFS}", "\n".join(extra) + ("\n" if extra else ""))
              .replace("{FIXES}", "\n".join(f"- {f}" for f in args.fix) or "- (none measured; match #1)"))
    with open(os.path.join(work, "prompt.md"), "w", encoding="utf-8") as fp:
        fp.write(prompt)

    info = {"try": n, "workdir": slash(work), "original": slash(original), "reference": slash(args.reference)}
    if args.dry_run:
        done(True, 0, dry_run=True, prompt=slash(os.path.join(work, "prompt.md")), **info)

    cmd = ["codex", "exec", "--skip-git-repo-check", "-s", "workspace-write", "-C", work]
    for img in images:
        cmd += ["-i", img]
    cmd += ["-"]
    with open(os.path.join(work, "log.txt"), "w", encoding="utf-8") as log:
        try:
            subprocess.run(cmd, cwd=work, input=prompt, text=True, encoding="utf-8",
                           stdout=log, stderr=subprocess.STDOUT, timeout=args.timeout)
        except subprocess.TimeoutExpired:
            done(False, 1, error=f"{args.timeout}초 안에 끝나지 않았다", **info)

    produced = os.path.join(work, "out", "result.png")
    if not os.path.exists(produced):
        pngs = glob.glob(os.path.join(work, "out", "*.png"))
        produced = pngs[0] if pngs else None
    if not produced:
        done(False, 1, error="Codex가 이미지를 저장하지 않았다 (log.txt 확인)", **info)
    result = os.path.join(work, "result.png")
    shutil.copy(produced, result)
    im = Image.open(result)
    done(True, 0, image=slash(result), size=list(im.size), mode=im.mode, **info)


if __name__ == "__main__":
    main()
