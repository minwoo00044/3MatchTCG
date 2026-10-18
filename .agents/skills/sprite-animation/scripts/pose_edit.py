"""
포즈마다 몸 기준 이미지 한 장을 Codex로 '편집'해 그린다 — 모든 장이 같은 몸이라 크기·위치가 고정된다.

    python pose_edit.py generate --character Priest --action Skill1 --spec <pose spec> [--pose peak raise3] [--body <png>] [--dry-run]
    python pose_edit.py accept   --character Priest --action Skill1 --pose peak SpriteRegen/Priest_Skill1E_peak/try2/result.png

언제 쓰나 (2026-10-19 Priest Skill1·Skill2):
  generate_action.py로 4장씩 나눠 생성하면 장마다 몸 크기·위치가 달라 "부위 크기가 계속 변하고 앞뒤로 이동"(사용자 지적).
  몸은 그대로 두고 팔·소품·표정만 바뀌는 동작은 이쪽이 낫다. 다리를 크게 쓰는 동작(쓰러짐·도약)은 generate_action.py.

pose spec(JSON, 확정되면 {캐릭터}/source~/pose/{액션}.json 에 커밋):
  {"canvas": [1024, 1536], "figure_h": 900, "foot_margin": 60,      # 세로 캔버스, 위를 비워 머리 위 소품이 들어가게
   "common": "모든 포즈에 붙는 문장(손에 든 소품 규칙 등)",
   "poses": {"peak": {"hands": "소품을 어느 손에 드는지", "pose": "이 장에서 바꿀 것만"}}}
몸 기준: --body → character.json idle.body → idle.source의 base 프레임.
결과: SpriteRegen/{캐릭터}_{액션}E_{포즈}/try{N}/result.png (흰 배경). 고른 장은 accept로 source~/{액션}/{포즈}.png 에 둔다.
"""
import argparse
import json
import os
import shutil
import sys
from concurrent.futures import ThreadPoolExecutor

from PIL import Image

sys.path.insert(0, os.path.dirname(__file__))
import codex_image as CI  # noqa: E402
import common as C  # noqa: E402

PROMPT = """Use your image generation tool to create ONE new image and save it as a PNG at `./out/result.png` (create `out` if needed). Do nothing else.

THIS IS AN EDIT of the attached image `base.png` (the character, 3/4 view facing right, white background).
Output canvas: exactly the same size as base.png ({w}x{h}), plain white background.

KEEP EXACTLY THE SAME as base.png (critical): the figure's size and position on the canvas, the head size and position, the face design,
the hair, the clothes and accessories, the legs, the stance and BOTH FEET at the same pixels, the art style and colors.
If a held prop is visible it keeps EXACTLY the same length, thickness and ornament size as in base.png — it never grows or shrinks.
The body stays in the 3/4 view facing right; it never turns toward the camera.

CHANGE ONLY what is written here (arms, hands, held props, face expression):
{common}
{hands}
{pose}

Everything must stay inside the canvas. No new objects, no effects, no text, no floor shadow."""


def config(character):
    with open(os.path.join(C.SHEET_ROOT, character, f"{character}.character.json"), encoding="utf-8") as fp:
        return json.load(fp)


def source_dir(character, *parts):
    return os.path.join(C.SHEET_ROOT, character, C.P.SOURCE_DIR, *parts)


def body_image(character, override=None):
    if override:
        return Image.open(override).convert("RGBA")
    idle = config(character).get("idle", {})
    if idle.get("body"):
        return Image.open(os.path.join(C.ROOT, idle["body"])).convert("RGBA")
    if idle.get("source"):
        fr, _ = C.load_frames(os.path.join(C.ROOT, idle["source"]), 4, 2, 8)
        return fr[idle.get("base", 0)]["image"]
    sys.exit(f"{character}: 몸 기준이 없다 — --body 또는 character.json idle.body")


def base_canvas(body, spec, path):
    w, h = spec.get("canvas", [1024, 1536])
    fig_h = spec.get("figure_h", 900)
    s = fig_h / body.height
    body = body.resize((round(body.width * s), fig_h), Image.LANCZOS)
    c = Image.new("RGBA", (w, h), (255, 255, 255, 255))
    c.alpha_composite(body, ((w - body.width) // 2, h - spec.get("foot_margin", 60) - body.height))
    c.convert("RGB").save(path)


def prompt_for(spec, key):
    w, h = spec.get("canvas", [1024, 1536])
    p = spec["poses"][key]
    return PROMPT.format(w=w, h=h, common=spec.get("common", ""), hands=p.get("hands", ""), pose=p["pose"])


def generate_one(character, action, spec, key, body, limit, dry_run):
    job = f"{character}_{action}E_{key}"
    if dry_run:
        work = CI.dryrun_dir(job)
    else:
        CI.check_usage(limit)
        work, _ = CI.new_try_dir(job)
    base_canvas(body, spec, os.path.join(work, "base.png"))
    prompt = prompt_for(spec, key)
    if dry_run:
        with open(os.path.join(work, "prompt.md"), "w", encoding="utf-8") as fp:
            fp.write(prompt)
        return key, work.replace(os.sep, "/")
    return key, CI.run(work, prompt, ["base.png"]).replace(os.sep, "/")


def cmd_generate(args):
    with open(args.spec, encoding="utf-8") as fp:
        spec = json.load(fp)
    keys = args.pose or list(spec["poses"])
    body = body_image(args.character, args.body)
    # 포즈마다 독립 호출이라 동시에 돌린다 (codex_image.run이 자기 세션 폴더의 그림만 가져온다 — regeneration.md 7절)
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futs = [ex.submit(generate_one, args.character, args.action, spec, k, body, args.limit, args.dry_run) for k in keys]
        results = dict(f.result() for f in futs)
    for k, v in results.items():
        print(f"  {k}: {v}")
    print(f"RESULT {json.dumps({'ok': True, 'dry_run': args.dry_run, 'results': results}, ensure_ascii=False)}")


def cmd_accept(args):
    dst = source_dir(args.character, args.action, f"{args.pose}.png")
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    shutil.copy(args.result, dst)
    print(f"RESULT {json.dumps({'ok': True, 'saved': os.path.relpath(dst, C.ROOT).replace(os.sep, '/')}, ensure_ascii=False)}")


def main():
    C.utf8_stdout()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("generate")
    g.add_argument("--character", required=True)
    g.add_argument("--action", required=True)
    g.add_argument("--spec", required=True)
    g.add_argument("--pose", nargs="*", help="생성할 포즈 키 (기본: spec의 전부)")
    g.add_argument("--body", help="몸 기준 이미지(인물 한 장, 투명 배경)")
    g.add_argument("--workers", type=int, default=8)
    g.add_argument("--limit", type=float, default=85)
    g.add_argument("--dry-run", action="store_true")
    a = sub.add_parser("accept")
    a.add_argument("--character", required=True)
    a.add_argument("--action", required=True)
    a.add_argument("--pose", required=True)
    a.add_argument("result")
    args = ap.parse_args()
    C.P.warn_local_only(args.character)
    {"generate": cmd_generate, "accept": cmd_accept}[args.cmd](args)


if __name__ == "__main__":
    main()
