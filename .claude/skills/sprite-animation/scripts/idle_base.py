"""
새 캐릭터의 첫 Idle AI 시트(4x2) — 턴어라운드(D)와 반자동 Idle(E) 사이를 잇는다. 원본 시트가 없는 캐릭터용.
이 시트는 그대로 게임에 넣지 않는다. 쓰임은 셋이다:
  - procedural_idle.py의 몸(base)과 눈 감은 프레임(blink)
  - generate_action.py의 character.png(디자인·비율의 정답)
  - sheet_check.py set-height의 키 측정

  generate --character Knight [--pose "..."] [--motion-from Archer] [--fix "..."]
           [--previous P.png --previous-note "..." [--edit]] [--dry-run]
      턴어라운드 3/4·앞모습 + 다른 캐릭터의 Idle 원본 시트(타이밍·시점·칸 크기 참고)를 붙여 생성한다.
      --edit: 첫 --previous를 고치는 편집 방식(비율만 틀렸을 때. Knight 2차: 머리 15% 큼 → 편집 1회로 합격).
      작업 폴더 SpriteRegen/{캐릭터}_Idle/try{N}/. 수 분 걸린다 — 백그라운드로 돌린다.
  verify --character Knight RESULT.png
      8장으로 나뉘는지, 장마다 턱 높이(얼굴 피부 아래 끝 / 머리카락 포함 키)가 턴어라운드 3/4와 같은지(±5%),
      장끼리 키가 같은지(±4%). 0 합격 / 4 불합격. 눈 감은 장·디자인은 결과를 눈으로 본다.
  accept --character Knight RESULT.png --base 0 --blink 2
      character.json의 idle(source·base·blink·method)을 쓴다. 이후 set-height → procedural_idle.

Knight에서 손으로 했던 순서를 옮긴 것이다(2026-10-14, SpriteRegen/Knight_Idle/try1~2).
"""
import argparse
import json
import os
import shutil
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
import codex_image as CI  # noqa: E402
import common as C  # noqa: E402
import deform as D  # noqa: E402
import mannequin as M  # noqa: E402

CHIN_TOL = 0.05     # 턱 높이 상대 오차. Knight 1차 27.0% vs 턴어라운드 23.6%(+14%, 불합격), 2차 23.8%(+1%, 합격)
HEIGHT_TOL = 0.04   # 장끼리 키 차이

DEFAULT_POSE = ("standing in a calm ready stance, 3/4 view facing right like #1; feet about shoulder-width apart, "
                "firmly planted (the feet do not move); a hand-held weapon is held lowered in one hand; the other hand relaxed at the side")

PROMPT = """Use your image generation tool to create ONE new image and save it as a PNG at `./out/result.png` (create `out` if needed). Do nothing else.

Attached images:
1. character.png — THE character to draw (3/4 view facing right). Source of truth for the DESIGN and the BODY PROPORTIONS (head size, torso, leg length, shoe size).
2. character_front.png — the same character from the front, for extra design detail.
3. motion_reference.png — a 4x2 sprite sheet of ANOTHER character from the same game doing its idle animation. Use it ONLY for: the animation type and timing (a calm breathing idle loop, an eye blink), the camera angle (3/4 view facing right), the sheet layout and the character's size within each cell. Do NOT copy that character's design, proportions, hair, outfit, weapon or its stance.
{EXTRA_REFS}
Draw a 4x2 sprite sheet (8 frames, a seamless loop) of the character from #1 in an IDLE animation:
- Pose: {POSE}.
- Motion over the 8 frames: gentle breathing (chest and shoulders rise and fall slightly), a small head bob, one eye blink (eyes closed in one or two frames). Small movements only; frame 8 flows back into frame 1. The body, face and every detail stay the SAME drawing from frame to frame except for this small motion.
- Same character in every frame: exactly the design, colors and proportions of #1{REQUIRED}. Do not make the head bigger or the legs shorter than #1.
- Same art style as #1. No color grading, no glow, no lighting effects.
{FIXES}
Sheet layout (critical):
- Landscape canvas, exactly 4 columns x 2 rows, 8 frames, evenly spaced.
- Fully transparent background. No floor, shadow, glow, text, numbers or grid lines.
- Each figure stays fully inside its own cell with a transparent gap; nothing (hair, cape, weapon, feet) crosses into a neighboring cell or touches the canvas edge.
- All figures are the same scale; all feet on one baseline near the bottom of each cell.
"""

EDIT_PROMPT = """Use your image generation tool to create ONE new image and save it as a PNG at `./out/result.png` (create `out` if needed). Do nothing else.

Attached images:
1. character.png — THE canonical character (3/4 view facing right). Source of truth for the BODY PROPORTIONS and design.
2. character_front.png — the same character from the front.
3. previous.png — a 4x2 idle animation sheet of this character. {PREV_NOTE}

THIS IS AN EDIT of #3, NOT A REDRAW. Keep every frame's pose, motion, expression, weapon, hair, clothes, design, colors and the sheet layout exactly as in #3. Change ONLY:
{FIXES}
Sheet layout (critical): exactly 4 columns x 2 rows, 8 frames, fully transparent background, no floor, shadow, text or grid lines; nothing crosses into a neighboring cell or touches the canvas edge; all figures the same scale on one baseline.
"""


def slash(p):
    return p.replace("\\", "/")


def done(ok, code, **kw):
    print(f"RESULT {json.dumps({'ok': ok, **kw}, ensure_ascii=False)}")
    sys.exit(code)


def config_path(character):
    return os.path.join(C.SHEET_ROOT, character, f"{character}.character.json")


def load_config(character):
    p = config_path(character)
    if not os.path.exists(p):
        done(False, 1, error=f"{character}.character.json이 없다 — 턴어라운드를 deform.py accept로 먼저 확정한다")
    with open(p, encoding="utf-8") as fp:
        return json.load(fp)


def turnaround_views(character):
    path = os.path.join(C.SHEET_ROOT, character, "design", f"{character}_turnaround.png")
    if not os.path.exists(path):
        done(False, 1, error=f"턴어라운드가 없다: {slash(path)} — D(deform.py accept)를 먼저 한다")
    figs = M.figures(path, len(M.VIEWS))
    if len(figs) != len(M.VIEWS):
        done(False, 1, error=f"턴어라운드에서 인물 {len(figs)}명을 찾았다 (4명이어야 한다)")
    return figs


def motion_reference(character):
    """다른 캐릭터 Idle의 원본 4x2 시트(기준 시트 매니페스트의 source). 처리된 24장 시트는 칸 배치가 달라 붙이지 않는다."""
    cfg = load_config(character)
    ref = cfg.get("reference")
    if not ref:
        done(False, 1, error=f"{character}에 기준 시트(reference)가 없다 — 모션 참고로 쓸 수 없다")
    with open(os.path.join(C.SHEET_ROOT, character, ref + ".json"), encoding="utf-8") as fp:
        src = json.load(fp).get("source")
    if src and not os.path.isabs(src):
        src = os.path.join(C.ROOT, src)  # 매니페스트는 프로젝트 루트 기준 상대 경로
    if not src or not os.path.exists(src):
        done(False, 1, error=f"{ref}의 원본 시트가 없다 ({src}) — --motion-reference로 4x2 Idle 시트를 직접 준다")
    return src


def chin_ratio(img):
    chin = D.face_chin(img)
    return None if chin is None else chin / img.height


def cmd_generate(args):
    cfg = load_config(args.character)
    figs = turnaround_views(args.character)
    if args.edit and not args.previous:
        done(False, 1, error="--edit에는 고칠 시트(--previous)가 필요하다")
    if len(args.previous_note) not in (0, len(args.previous)):
        done(False, 1, error="--previous-note 개수가 --previous와 다르다")
    motion = args.motion_reference or motion_reference(args.motion_from)
    job = f"{args.character}_Idle"
    if args.dry_run:
        work, n = CI.dryrun_dir(job), None
    else:
        try:
            CI.check_usage(args.limit)
        except CI.CodexError as e:
            done(False, 3 if getattr(e, "over_limit", False) else 1, error=str(e))
        work, n = CI.new_try_dir(job)

    D.on_white(figs[1]).save(os.path.join(work, "character.png"))
    D.on_white(figs[0]).save(os.path.join(work, "character_front.png"))
    images = ["character.png", "character_front.png"]
    fixes = [f"- {f}" for f in args.fix]
    if args.edit:
        shutil.copy(args.previous[0], os.path.join(work, "previous.png"))
        images.append("previous.png")
        note = args.previous_note[0] if args.previous_note else "Its poses, motion, layout and design are correct."
        if not fixes:
            done(False, 1, error="--edit에는 무엇을 바꿀지 --fix로 적는다(측정값 포함)")
        prompt = EDIT_PROMPT.replace("{PREV_NOTE}", note).replace("{FIXES}", "\n".join(fixes) + "\n")
    else:
        shutil.copy(motion, os.path.join(work, "motion_reference.png"))
        images.append("motion_reference.png")
        extra = []
        for i, prev in enumerate(args.previous, start=len(images) + 1):
            name = f"previous_{i}.png"
            shutil.copy(prev, os.path.join(work, name))
            images.append(name)
            note = args.previous_note[i - 4] if args.previous_note else "an earlier attempt"
            extra.append(f"{i}. {name} — {note}")
        required = cfg.get("design", {}).get("required", [])
        prompt = (PROMPT.replace("{EXTRA_REFS}", "\n".join(extra) + ("\n" if extra else ""))
                  .replace("{POSE}", args.pose or DEFAULT_POSE)
                  .replace("{REQUIRED}", f" ({'; '.join(required)})" if required else "")
                  .replace("{FIXES}", ("Corrections:\n" + "\n".join(fixes) + "\n") if fixes else ""))
    info = {"try": n, "workdir": slash(work), "edit": args.edit}
    if args.dry_run:
        with open(os.path.join(work, "prompt.md"), "w", encoding="utf-8") as fp:
            fp.write(prompt)
        done(True, 0, dry_run=True, **info)
    try:
        result = CI.run(work, prompt, images, args.timeout)
    except CI.CodexError as e:
        done(False, 1, error=str(e), **info)
    done(True, 0, image=slash(result), **info)


def cmd_verify(args):
    figs = turnaround_views(args.character)
    target = chin_ratio(figs[1])
    if target is None:
        done(False, 1, error="턴어라운드 3/4에서 턱을 못 찾았다")
    frames, warnings = C.load_frames(args.image, 4, 2, 8)
    fails, notes = [], list(warnings)
    if len(frames) != 8:
        done(True, 4, **{"pass": False, "fails": [f"{len(frames)}장 (8장이어야 한다)"]})
    heights = [f["image"].height for f in frames]
    print(f"턴어라운드 3/4 턱 높이 {target * 100:.1f}% (머리카락 포함 키 대비)")
    worst = 0.0
    for i, f in enumerate(frames):
        r = chin_ratio(f["image"])
        if r is None:
            notes.append(f"{i}번: 턱을 못 찾았다 — 눈으로 본다")
            print(f"  {i}번 키 {heights[i]}px  턱 ?")
            continue
        d = r / target - 1
        worst = max(worst, abs(d))
        print(f"  {i}번 키 {heights[i]}px  턱 {r * 100:.1f}% ({d * 100:+.0f}%)")
        if abs(d) > CHIN_TOL:
            fails.append(f"{i}번 턱 {r * 100:.1f}% (목표 {target * 100:.1f}%) — " + ("머리가 크거나 다리가 짧다" if d > 0 else "머리가 작거나 다리가 길다"))
    spread = max(heights) / min(heights) - 1
    if spread > HEIGHT_TOL:
        fails.append(f"장끼리 키 차이 {spread * 100:.1f}%")
    for n in notes:
        print("  [참고]", n)
    print("눈으로 볼 것: 눈 감은 장(blink)이 있는지, 모든 장이 같은 얼굴·디자인인지, 필수 디자인 요소, 3/4 오른쪽 시점")
    print("판정:", "합격" if not fails else "불합격 — " + "; ".join(fails))
    done(True, 0 if not fails else 4, **{"pass": not fails, "fails": fails, "notes": notes,
                                        "target_chin": round(target, 4), "worst_chin_diff": round(worst, 3)})


def cmd_accept(args):
    cfg = load_config(args.character)
    if not os.path.exists(args.image):
        done(False, 1, error=f"파일이 없다: {args.image}")
    idle = cfg.get("idle", {})
    idle.update(method="procedural", source=slash(os.path.relpath(args.image, C.ROOT)), base=args.base, blink=args.blink)
    cfg["idle"] = idle
    if not cfg.get("design", {}).get("props_reference"):
        # 필수 디자인 요소가 보이는 그림. 처리된 시트가 생기기 전까지는 이 AI 시트를 쓴다
        cfg.setdefault("design", {})["props_reference"] = idle["source"]
    with open(config_path(args.character), "w", encoding="utf-8") as fp:
        json.dump(cfg, fp, ensure_ascii=False, indent=2)
    print(f"{args.character} idle.source = {idle['source']} (base {args.base}, blink {args.blink})")
    print(f"다음: sheet_check.py set-height --character {args.character} --relative-to <비교 캐릭터> --sheet {idle['source']}")
    done(True, 0, idle=idle)


def main():
    C.utf8_stdout()
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("generate")
    g.add_argument("--character", required=True)
    g.add_argument("--pose", help="Idle 자세 (영어, 무기를 어떻게 드는지까지). 생략하면 일반 준비 자세")
    g.add_argument("--motion-from", default="Archer", help="모션 참고로 쓸 캐릭터 — 그 기준 Idle의 원본 4x2 시트")
    g.add_argument("--motion-reference", help="모션 참고 4x2 시트를 직접 준다")
    g.add_argument("--previous", action="append", default=[])
    g.add_argument("--previous-note", action="append", default=[])
    g.add_argument("--edit", action="store_true", help="첫 --previous를 편집한다(비율만 고칠 때)")
    g.add_argument("--fix", action="append", default=[], help="고칠 점 (영어, 측정값 포함)")
    g.add_argument("--limit", type=float, default=85)
    g.add_argument("--timeout", type=int, default=900)
    g.add_argument("--dry-run", action="store_true")
    v = sub.add_parser("verify")
    v.add_argument("image")
    v.add_argument("--character", required=True)
    a = sub.add_parser("accept")
    a.add_argument("image")
    a.add_argument("--character", required=True)
    a.add_argument("--base", type=int, required=True, help="몸으로 쓸 프레임 (눈 뜬 장)")
    a.add_argument("--blink", type=int, required=True, help="같은 몸으로 그려진 눈 감은 프레임")
    args = p.parse_args()
    {"generate": cmd_generate, "verify": cmd_verify, "accept": cmd_accept}[args.cmd](args)


if __name__ == "__main__":
    main()
