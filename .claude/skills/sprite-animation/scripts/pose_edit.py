"""
포즈마다 몸 기준 이미지 한 장을 Codex로 '편집'해 그린다 — 모든 장이 같은 몸이라 크기·위치가 고정된다.

    python pose_edit.py generate --character Priest --action Skill1 --spec <pose spec> [--pose peak raise3] [--body <png>] [--dry-run]
    python pose_edit.py accept   --character Priest --action Skill1 --pose peak SpriteRegen/Priest_Skill1E_peak/try2/result.png
    python pose_edit.py base     --character Priest --action Skill1 --spec <pose spec> [--pose base]   # 준비 장면 = 몸 기준 그대로

언제 쓰나 (2026-10-19 Priest Skill1·Skill2):
  generate_action.py로 4장씩 나눠 생성하면 장마다 몸 크기·위치가 달라 "부위 크기가 계속 변하고 앞뒤로 이동"(사용자 지적).
  몸은 그대로 두고 팔·소품·표정만 바뀌는 동작은 이쪽이 낫다. 다리를 크게 쓰는 동작(쓰러짐·도약)은 generate_action.py.

pose spec(JSON, 확정되면 {캐릭터}/source~/pose/{액션}.json 에 커밋):
  {"canvas": [1024, 1536], "figure_h": 900, "foot_margin": 60,      # 세로 캔버스, 위를 비워 머리 위 소품이 들어가게
   "common": "모든 포즈에 붙는 문장(손에 든 소품 규칙 등)",
   "poses": {"peak": {"hands": "소품을 어느 손에 드는지", "pose": "이 장에서 바꿀 것만",
                      "legs_keep": "(선택) 다리를 쓰는 장: 고정할 발만 — 예 'her RIGHT foot ... at the same pixels'"}}}
몸 기준: --body → character.json idle.body → idle.source의 base 프레임.
결과: SpriteRegen/{캐릭터}_{액션}E_{포즈}/try{N}/result.png (키 색 배경). 고른 장은 accept로 키 색을 지운 투명 PNG를 source~/{액션}/{포즈}.png 에 둔다.
배경: 캐릭터에 없는 키 색(character.json design.key_color, 기본 green). 예전엔 흰 배경이라 몸에 둘러싸인 배경(지팡이·몸 사이, 다리 사이)이
흰색으로 남았다 — Priest v3 "누끼가 덜 따졌다"(2026-10-19). 흰 옷이 넓으면 색으로도 못 가른다.
"""
import argparse
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor

from PIL import Image

sys.path.insert(0, os.path.dirname(__file__))
import codex_image as CI  # noqa: E402
import common as C  # noqa: E402

PROMPT = """Use your image generation tool to create ONE new image and save it as a PNG at `./out/result.png` (create `out` if needed). Do nothing else.

THIS IS AN EDIT of the attached image `base.png` (the character, 3/4 view facing right, on a solid {key_name} chroma-key background).
Output canvas: exactly the same size as base.png ({w}x{h}). Background (critical): the SAME flat solid pure {key_name} ({key_hex}) everywhere around the figure,
including every gap between the arms, the body, the legs and the held prop — no white, no gradient, no shadow, no glow on the background.
The character itself contains NO {key_name}.

KEEP EXACTLY THE SAME as base.png (critical): the figure's size and position on the canvas, the head size and position, the face design,
the hair, the clothes and accessories, {legs_keep}, the art style and colors.
If a held prop is visible it keeps EXACTLY the same length, thickness and ornament size as in base.png — it never grows or shrinks.
The body stays in the 3/4 view facing right; it never turns toward the camera.

CHANGE ONLY what is written here ({change_scope}):
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


def base_canvas(body, spec, path, key):
    w, h = spec.get("canvas", [1024, 1536])
    fig_h = spec.get("figure_h", 900)
    s = fig_h / body.height
    body = body.resize((round(body.width * s), fig_h), Image.LANCZOS)
    c = Image.new("RGBA", (w, h), C.KEY_COLORS[key] + (255,))
    c.alpha_composite(body, ((w - body.width) // 2, h - spec.get("foot_margin", 60) - body.height))
    c.convert("RGB").save(path)


def prompt_for(spec, key, key_name):
    w, h = spec.get("canvas", [1024, 1536])
    p = spec["poses"][key]
    hexv = "#%02X%02X%02X" % C.KEY_COLORS[key_name]
    # 다리를 쓰는 동작(내딛기)은 spec/포즈의 "legs_keep"으로 고정할 발만 적는다 — 기본은 두 발 고정
    legs_keep = p.get("legs_keep", spec.get("legs_keep", "the legs, the stance and BOTH FEET at the same pixels"))
    scope = "arms, hands, held props, face expression" + (", and the leg written below" if "legs_keep" in p or "legs_keep" in spec else "")
    return PROMPT.format(w=w, h=h, common=spec.get("common", ""), hands=p.get("hands", ""), pose=p["pose"],
                         key_name=key_name, key_hex=hexv, legs_keep=legs_keep, change_scope=scope)


def generate_one(character, action, spec, key, body, limit, dry_run):
    job = f"{character}_{action}E_{key}"
    if dry_run:
        work = CI.dryrun_dir(job)
    else:
        CI.check_usage(limit)
        work, _ = CI.new_try_dir(job)
    kc = C.key_color(character)
    base_canvas(body, spec, os.path.join(work, "base.png"), kc)
    prompt = prompt_for(spec, key, kc)
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
        results, failed = {}, {}
        for k, f in zip(keys, futs):
            try:
                results[k] = f.result()[1]
            except Exception as e:  # 한 장이 실패(시간 초과·용량 부족)해도 나머지 결과는 보고한다
                failed[k] = str(e)
    for k, v in results.items():
        print(f"  {k}: {v}")
    for k, v in failed.items():
        print(f"  {k}: 실패 — {v}")
    print(f"RESULT {json.dumps({'ok': not failed, 'dry_run': args.dry_run, 'results': results, 'failed': failed}, ensure_ascii=False)}")


def cmd_accept(args):
    dst = source_dir(args.character, args.action, f"{args.pose}.png")
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    # 키 색(또는 예전 흰 배경)을 지운 투명 PNG로 둔다 — 뒤 단계(smear·splice)는 투명 그대로 쓴다
    C.load_rgba(args.result).save(dst)
    print(f"RESULT {json.dumps({'ok': True, 'saved': os.path.relpath(dst, C.ROOT).replace(os.sep, '/')}, ensure_ascii=False)}")


def cmd_base(args):
    """준비 장면 = 몸 기준을 편집 없이 같은 캔버스·배치로 (투명). Codex로 '변화 없음'을 그리면 몸이 미세하게 달라진다."""
    with open(args.spec, encoding="utf-8") as fp:
        spec = json.load(fp)
    body = body_image(args.character, args.body)
    w, h = spec.get("canvas", [1024, 1536])
    fig_h = spec.get("figure_h", 900)
    s = fig_h / body.height
    body = body.resize((round(body.width * s), fig_h), Image.LANCZOS)
    c = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    c.alpha_composite(body, ((w - body.width) // 2, h - spec.get("foot_margin", 60) - body.height))
    dst = source_dir(args.character, args.action, f"{args.pose}.png")
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    c.save(dst)
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
    b = sub.add_parser("base", help="준비 장면(몸 기준 그대로)을 source~/{액션}/{포즈}.png로")
    b.add_argument("--character", required=True)
    b.add_argument("--action", required=True)
    b.add_argument("--spec", required=True)
    b.add_argument("--pose", default="base")
    b.add_argument("--body")
    args = ap.parse_args()
    C.P.warn_local_only(args.character)
    {"generate": cmd_generate, "accept": cmd_accept, "base": cmd_base}[args.cmd](args)


if __name__ == "__main__":
    main()
