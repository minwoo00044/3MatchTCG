"""
원본 시트 없이 새 동작 시트를 Codex로 생성한다 — 큰 동작은 4장씩 나눠(2x2, 넓은 칸) 이어 그린다.

    python generate_action.py --character Knight --action Skill1 --spec SpriteRegen/_specs/knight_skill1.json [--parts 3] [--dry-run]

spec(JSON):
    {"title": "a SPEEDY, TOUGH, FULL-BODY LUNGING THRUST to the right",
     "physics": "power from the back leg ... (references/motion.md 정의를 영어로)",
     "poses": ["Ready stance ...", "...", ...],            # 4 × parts 개
     "reference": "SpriteRegen/_refs/stab_ref_sheet.png",   # 자세 레퍼런스(선택, 회색 실루엣)
     "reference_note": "gray silhouette, black line = sword; ignore the scabbard",
     "rules": ["The back foot stays planted", ...]}         # 추가 규칙(선택)

같이 붙이는 것 (Knight Skill1에서 효과를 확인, 2026-10-15):
- character.png: 몸으로 쓴 Idle AI 프레임(character.json idle.source / base) — 디자인·비율의 정답
- size_guide.png: 그 Idle을 결과와 같은 2x2 칸에 같은 크기로 넣은 시트 — 없으면 머리 +30%, 신발 2배로 커졌다
- pose_reference.png: 사람이 만든 레퍼런스의 자세만
- part1.png …: 앞서 그린 장 — 뒷장이 이어 그리게
결과: SpriteRegen/{캐릭터}_{액션}/tryN/result.png 를 장마다. 마지막 줄 RESULT에 tryN 목록.
장마다 캔버스 크기가 같은지 확인한다(다르면 프레임 크기가 들쭉날쭉 — 그 세트는 버린다).
이어서 process_sprite_sheet.py --input A B C --cols 2 --rows {2*parts} --frames {4*parts} …
"""
import argparse
import json
import os
import shutil
import sys

from PIL import Image

sys.path.insert(0, os.path.dirname(__file__))
import codex_image as CI  # noqa: E402
import common as C  # noqa: E402
import deform as D  # noqa: E402

CELL_W, CELL_H = 768, 512   # Codex 기본 1536x1024 캔버스의 2x2 칸


def idle_body(character, override=None):
    """
    몸 기준: override → character.json idle.body(커밋된 한 장, {캐릭터}/source~/body.png) → idle.source의 base 프레임.
    idle.source(Idle AI 시트)는 SpriteRegen/(git 무시)에 있어 다른 PC에는 없다(Priest 2026-10-18) — 확정되면 body로 커밋한다.
    """
    if override:
        return Image.open(override).convert("RGBA")
    cfg = json.load(open(os.path.join(C.SHEET_ROOT, character, f"{character}.character.json"), encoding="utf-8"))
    idle = cfg.get("idle", {})
    if idle.get("body"):
        return Image.open(os.path.join(C.ROOT, idle["body"])).convert("RGBA")
    if not idle.get("source"):
        sys.exit(f"{character}.character.json에 idle.body·idle.source가 없다 — 몸으로 쓸 Idle 그림이 필요하다")
    fr, _ = C.load_frames(os.path.join(C.ROOT, idle["source"]), 4, 2, 8)
    return fr[idle.get("base", 0)]["image"]


def action_direction(character, action):
    """
    [관문 3] 사용자에게 받은 동작 디렉팅(character.json actions.{액션}.direction). 없으면 None.
    spec(영어 포즈 목록)은 이 디렉팅을 번역·구체화한 것이다 — 디렉팅 없이 spec부터 쓰면 짐작으로 그리게 된다
    (Knight Skill3 "칼 휘두르기"는 짐작으로 두 번 퇴짜, 실제 의장대 동작을 조사한 뒤 확정).
    """
    path = os.path.join(C.SHEET_ROOT, character, f"{character}.character.json")
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as fp:
        return json.load(fp).get("actions", {}).get(action, {}).get("direction")


FIGURE_SCALE = 0.86  # 크기 안내 그림에서 인물 키 / 칸 높이 (Knight)


def size_guide(body, scale=FIGURE_SCALE):
    """
    scale: 머리 위로 무기를 드는 동작은 위 여백이 모자라 "머리 크기 그대로"와 "칸 안에"가 부딪힌다(Priest Skill1 dry-run 점검) —
    spec "figure_scale"로 인물을 작게(예 0.72) 그려 여백을 둔다. 결과 크기는 파이프라인이 기준 시트에 다시 맞춘다(턱~발바닥, size_fit).
    """
    g = Image.new("RGBA", (CELL_W * 2, CELL_H * 2), (255, 255, 255, 255))
    s = (CELL_H * scale) / body.height
    im = body.resize((round(body.width * s), round(body.height * s)), Image.LANCZOS)
    for k in range(4):
        g.alpha_composite(im, ((k % 2) * CELL_W + 60, (k // 2) * CELL_H + CELL_H - 30 - im.height))
    return g.convert("RGB")


def prompt_for(spec, part, prev_count, has_ref):
    lo = part * 4
    lines = "\n".join(f"{k - lo + 1}. (animation frame {k + 1}) {spec['poses'][k]}" for k in range(lo, lo + 4))
    refs = ("3. pose_reference.png — a pose reference from a human-made animation "
            f"({spec.get('reference_note', 'gray silhouette')}). Use it ONLY for the poses.\n") if has_ref else ""
    n0 = 4 if has_ref else 3
    prev = "".join(f"{n0 + k}. part{k + 1}.png — frames {k * 4 + 1}-{k * 4 + 4} of THIS SAME animation, already drawn. "
                   "Continue directly from them with the same character size.\n" for k in range(prev_count))
    rules = "".join(f"- {r}\n" for r in spec.get("rules", []))
    return f"""Use your image generation tool to create ONE new image and save it as a PNG at `./out/result.png` (create `out` if needed). Do nothing else.

Attached images:
1. character.png — THE character (3/4 view facing right). Source of truth for design, colors, art style and BODY PROPORTIONS.
2. size_guide.png — a 2x2 sheet showing the character at the EXACT SIZE she must have in each cell of your sheet. Your output has the same canvas size and the same 2x2 cells. In every frame the head must be exactly this size, the shoes this size, the legs this long.
{refs}{prev}
The animation: {spec['title']}. {spec.get('physics', '')} Draw ONLY these 4 frames of it, as a 2x2 sheet (left-to-right, top-to-bottom):
{lines}

Proportions (critical, check every frame): the head (with hair) is NOT bigger than in #2; the legs are NOT shorter than in #2 (a wide low stance keeps each leg's full length); the shoes are NOT bigger than in #2. Anatomically correct limbs. The same face design in every frame (only the expression changes, as written for each frame).
{rules}
Sheet layout (critical): LANDSCAPE canvas, exactly 2 columns x 2 rows, 4 frames, evenly spaced (wide cells). Fully transparent background; no floor line, shadow, text or grid lines. Place the figure so that the whole figure including any extended weapon and effect stays inside its own cell with a clear transparent gap. Nothing touches a neighboring figure or the canvas edge. One baseline per row.
"""


def main():
    C.utf8_stdout()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--character", required=True)
    ap.add_argument("--action", required=True)
    ap.add_argument("--spec", required=True)
    ap.add_argument("--parts", type=int, default=None, help="4장씩 몇 장 (기본 poses 수 / 4)")
    ap.add_argument("--limit", type=float, default=85)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--body", default=None, help="몸 기준 이미지(인물 한 장). 없으면 character.json idle.source / base")
    ap.add_argument("--skip-direction", action="store_true",
                    help="디렉팅 기록 없이 생성 (디렉팅 관문 이전에 만든 캐릭터를 다시 뽑을 때만)")
    args = ap.parse_args()
    C.check_team_action(args.character, args.action)
    direction = action_direction(args.character, args.action)
    if direction is None and not args.skip_direction:
        print(f"{args.character}.character.json에 actions.{args.action}.direction이 없다 — "
              "[관문 3: 디렉팅] 사용자에게 이 동작의 디렉팅을 먼저 받는다 (SKILL.md F 0단계)")
        sys.exit(1)
    if direction:
        print(f"디렉팅({args.action}): {direction}")
    spec = json.load(open(args.spec, encoding="utf-8"))
    parts = args.parts or len(spec["poses"]) // 4
    if len(spec["poses"]) < parts * 4:
        sys.exit(f"poses가 {parts * 4}개 필요하다 ({len(spec['poses'])}개)")
    C.P.warn_local_only(args.character)
    body = idle_body(args.character, args.body)
    job = f"{args.character}_{args.action}"
    done_dirs = []
    work = CI.dryrun_dir(job) if args.dry_run else None
    for part in range(parts):
        if args.dry_run:
            pass  # 모든 장의 프롬프트를 한 폴더에 prompt_part{N}.md로 (앞 장 그림은 없으니 partN.png는 안 붙는다)
        else:
            CI.check_usage(args.limit)
            work, n = CI.new_try_dir(job)
        D.on_white(body).save(os.path.join(work, "character.png"))
        size_guide(body, spec.get("figure_scale", FIGURE_SCALE)).save(os.path.join(work, "size_guide.png"))
        images = ["character.png", "size_guide.png"]
        ref = spec.get("reference")
        if ref:
            shutil.copy(ref, os.path.join(work, "pose_reference.png"))
            images.append("pose_reference.png")
        for k, d in enumerate(done_dirs):
            shutil.copy(os.path.join(d, "result.png"), os.path.join(work, f"part{k + 1}.png"))
            images.append(f"part{k + 1}.png")
        prompt = prompt_for(spec, part, part if args.dry_run else len(done_dirs), bool(ref))
        if args.dry_run:
            open(os.path.join(work, f"prompt_part{part + 1}.md"), "w", encoding="utf-8").write(prompt)
            continue
        CI.run(work, prompt, images)
        done_dirs.append(work)
        print(f"  {part + 1}/{parts}: {work}")
    if args.dry_run:
        print(f"RESULT {json.dumps({'ok': True, 'dry_run': True, 'prompt': work.replace(os.sep, '/'), 'parts': parts}, ensure_ascii=False)}")
        return
    sizes = [Image.open(os.path.join(d, "result.png")).size for d in done_dirs]
    warn = [] if len(set(sizes)) == 1 else [f"장마다 캔버스 크기가 다르다 {sizes} — 프레임 크기가 들쭉날쭉해진다. 다시 뽑는다"]
    print(f"RESULT {json.dumps({'ok': not warn, 'parts': [d.replace(os.sep, '/') for d in done_dirs], 'sizes': sizes, 'warnings': warn}, ensure_ascii=False)}")


if __name__ == "__main__":
    main()
