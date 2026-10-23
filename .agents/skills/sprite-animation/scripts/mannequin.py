"""
체형 마네킹 — 새 캐릭터를 데포르메할 때 맞출 신체 비율의 기준. 기준 캐릭터(Archer)에서 만든다.

  bald --reference SHEET [--dry-run]
      M1: 기준 시트 0번 프레임을 '편집'해 같은 자세의 민머리 회색 마네킹으로 만든다.
      자세가 같아 기준 캐릭터와 기준선(턱·가랑이·발바닥)을 직접 비교할 수 있고, 머리카락에 가린 두개골 크기를 처음 잰다.
  turnaround --m1 M1.png [--dry-run]
      M2: M1의 비율로 A포즈 4방향(앞·3/4·옆·뒤) 턴어라운드를 그린다. 프롬프트에 M1에서 잰 기준선 %를 넣는다.
  verify --m1 M1.png TURNAROUND.png
      방향마다 세로 기준선(턱·어깨·가랑이)이 M1과 같은지, 키가 같은지, 앞·뒤 폭이 같은지. 0 합격 / 4 불합격.
  stretch-legs TURNAROUND.png --m1 M1.png --out OUT.png
      가랑이~발목 띠만 세로로 늘려 다리 비율을 M1에 맞춘다. 모델이 다리를 짧게 그리는 쪽으로 돌아가 지시로 안 고쳐질 때.
  save --m1 M1.png --turnaround T.png --source Archer_Idle_v7
      합격본을 assets/mannequin/ 에 저장(m1_reference_pose.png, turnaround.png, turnaround_guide.png, mannequin.json).
  measure IMG [--views N]
      실루엣 기준선 측정 (색을 쓰지 않는다 — 마네킹은 단색, 새 캐릭터는 팔레트를 모른다).
      턴어라운드처럼 한 장에 여러 명이면 투명한 세로 틈으로 나눠 각각 잰다.

모든 기준선은 '다리를 편 키'(발바닥 ~ 정수리, 파이프라인 standing_height와 같은 보정)에 대한 비율이다.
  chin      정수리~턱(목이 가장 좁은 줄) / 키   — 마네킹은 두개골, 캐릭터는 머리카락 포함이라 직접 비교하지 않는다
  shoulder  정수리~어깨선 / 키
  crotch    정수리~가랑이 / 키
  head_w    머리 최대 폭 / 키,  shoulder_w 어깨 폭 / 키,  foot_w 두 발 띠 폭 / 키

작업 폴더: SpriteRegen/Mannequin/try{N}/ (git 무시). 합격본은 assets/mannequin/ 에 둔다.

만든 기록 (2026-10-14, 기준 Archer_Idle_v7):
- M1(bald) 1회 합격. 발 폭으로 크기를 맞춰 Archer와 겹치면 턱·다리·발이 겹치고, 두개골이 머리카락 부피 안에 들어간다.
- 턴어라운드 1·2차 모두 가랑이 61%(M1 58%), 턱 25.7%(24.7%) — 모델이 다리 짧은 체형으로 돌아간다.
  2차에 1차를 붙이고 측정값으로 고치라 해도 거의 그대로였다 → stretch-legs(×1.32)로 맞추고 사용자가 확정.
- 실루엣 판정은 방향마다 믿을 수 있는 것만 본다(VIEW_CHECKS): 3/4는 다리가 겹쳐 가랑이를 낮게 잡고,
  옆모습은 가랑이가 안 보인다. 옷 입은 캐릭터는 머리카락·화살통 때문에 목이 안 좁아져 턱을 가슴에서 잡는다.
"""
import argparse
import json
import os
import sys

import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(__file__))
import codex_image as CI  # noqa: E402
import common as C  # noqa: E402
import sheet_check as SC  # noqa: E402

ASSET_DIR = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "assets", "mannequin"))

BALD_PROMPT = """Use your image generation tool to create ONE new image and save it as a PNG at `./out/result.png` (create `out` if needed). Do nothing else.

Attached image:
1. character.png — a chibi game character, standing pose.

THIS IS AN EDIT, NOT A REDRAW. Turn the character in #1 into a plain artist's mannequin.

Keep EXACTLY as in #1:
- the pose, body angle (3/4 view facing right), the position of every limb, the stance and the feet positions;
- the body proportions: same height from chin to soles, same neck/chin height, same shoulder width, same crotch height, same leg length and thickness;
- the feet: the same size and shape as the boots in #1, as simple smooth rounded feet/shoes.

Change:
- Remove ALL hair. Show a smooth bald head with the TRUE skull shape that was hidden under the hair (the skull is smaller than the hair volume; the face, ears and chin stay where they are in #1).
- Remove all clothing, armor, belt, quiver, bow and accessories. Show a smooth neutral body with the same volumes as #1 underneath the clothes (no anatomy details).
- Hands: simple relaxed hands at the same position, holding nothing.
- Face: blank, with only a faint horizontal eye line.

Style: one flat light-gray color (#BDBDBD) with soft gray shading and a dark-gray outline. Fully transparent background. Only one figure. No floor, shadow, text, grid or guide lines.
"""


VIEWS = ["front", "three_quarter", "side", "back"]

TURNAROUND_PROMPT = """Use your image generation tool to create ONE new image and save it as a PNG at `./out/result.png` (create `out` if needed). Do nothing else.

Attached image:
1. mannequin.png — a gray artist's mannequin of a chibi game character (3/4 view). THE canonical body proportions.

Draw a CHARACTER TURNAROUND SHEET of exactly this mannequin: four full-body views in one row, left to right:
  1) front view, 2) 3/4 view facing right, 3) side view facing right (profile), 4) back view.

Pose in all four views — neutral A-pose:
- standing straight, legs straight, feet slightly apart (about one foot width between them), weight even;
- arms straight down and angled about 30 degrees away from the body, hands relaxed and open, not touching the body;
- head level, looking straight ahead in each view's direction.

Proportions — identical to #1 and identical across the four views (measured on #1, as % of the full height from the top of the skull to the soles):
- top of skull to chin (bottom of the head): {CHIN}%
- top of skull to shoulder line: {SHOULDER}%
- top of skull to crotch: {CROTCH}%
- same skull shape and size, same leg length and thickness, same chunky feet as #1 (same size).

{EXTRA}Style: same as #1 — one flat light-gray color with soft gray shading and a dark-gray outline; bald, blank face with a faint eye line; no clothes, no hair, no accessories.

Layout (critical): landscape canvas, the four figures side by side at the SAME scale, all soles on ONE horizontal baseline near the bottom, the same height, evenly spaced with clear transparent gaps between figures; nothing touches the canvas edge. Fully transparent background. No floor, shadow, text, labels, numbers or guide lines.
"""


RESKULL_PROMPT = """Use your image generation tool to create ONE new image and save it as a PNG at `./out/result.png` (create `out` if needed). Do nothing else.

Attached images:
1. mannequin.png — a gray artist's mannequin of a chibi game character.
2. guide.png — the same mannequin with a hand-drawn BLUE line showing the CORRECT outline of the head (skull, ear, face and jaw).

THIS IS AN EDIT of #1, NOT A REDRAW. Change ONLY the head so that its outline follows the blue line in #2.
{NOTES}
The blue line was drawn by hand with a mouse: follow its overall shape, size and position, but draw a smooth, natural skull outline — ignore small wobbles, jitter and any gaps in the line.

Keep EXACTLY as in #1: the face position, the ear, the chin position, the neck, the body, arms, hands, legs, feet, the pose, the colors (flat light gray with soft shading and a dark-gray outline), the style, the canvas size and the figure's position on the canvas.
Fully transparent background. No blue line, no guide lines, no text in the output.
"""


def slash(p):
    return p.replace("\\", "/")


# ---------------------------------------------------------------- 측정

def split_figures(alpha, n=None):
    """투명한 세로 틈으로 인물을 나눈다. 반환: [(x0, x1)]. n을 주면 가장 넓은 틈부터 n-1개로 자른다."""
    cols = alpha.any(0)
    d = np.diff(np.concatenate(([0], cols.astype(np.int8), [0])))
    runs = [(s, e) for s, e in zip(np.where(d == 1)[0], np.where(d == -1)[0])]
    # 작은 부스러기는 이웃에 붙인다
    runs = [r for r in runs if r[1] - r[0] > alpha.shape[1] * 0.02]
    if n and len(runs) > n:
        gaps = sorted(range(len(runs) - 1), key=lambda i: runs[i + 1][0] - runs[i][1], reverse=True)[:n - 1]
        merged, start = [], runs[0][0]
        for i in range(len(runs) - 1):
            if i in gaps:
                merged.append((start, runs[i][1]))
                start = runs[i + 1][0]
        merged.append((start, runs[-1][1]))
        runs = merged
    return runs


def landmarks(img):
    """한 인물의 실루엣 기준선. img: RGBA (인물 하나, 여백 포함 가능)."""
    a = np.asarray(img)[:, :, 3] > 128
    ys, xs = np.where(a)
    top, bottom = ys.min(), ys.max()
    a = a[top:bottom + 1, xs.min():xs.max() + 1]
    h = a.shape[0]
    Hs, stance = C.P.standing_height(crop_alpha_image(img))
    width = a.sum(1).astype(float)
    # 턱 = 상단 15~55% 구간에서 폭이 가장 좁은 줄 (머리 아래 목)
    lo, hi = int(h * 0.15), int(h * 0.55)
    smooth = np.convolve(width, np.ones(5) / 5, mode="same")
    chin = lo + int(np.argmin(smooth[lo:hi]))
    head_w = float(width[:chin].max())
    # 어깨 = 목 아래에서 폭이 빠르게 넓어지다(목→어깨 경사) 완만해지는 줄. 폭 임계값은 목이 짧은 데포르메에서
    # 경사 중간에 걸렸다 (M1: 턱 바로 아래 26%로 잡힘, 실제 29%)
    step = max(3, h // 150)
    end = min(h - step, hi + int(h * 0.1))
    grow = np.array([smooth[y + step] - smooth[y] for y in range(chin, end)])
    shoulder = None
    if len(grow) and grow.max() > 0:
        peak = int(np.argmax(grow))
        flat = np.where(grow[peak:] < grow[peak] * 0.3)[0]
        if len(flat):
            shoulder = chin + peak + int(flat[0])
    shoulder_w = float(width[shoulder:shoulder + max(3, h // 40)].max()) if shoulder is not None else float("nan")
    band = a[h - max(4, int(h * 0.06)):].any(0)
    fx = np.where(band)[0]
    foot_w = float(fx.max() - fx.min() + 1) if len(fx) else float("nan")
    crotch = stance.get("crotch")
    # 정수리 기준 비율. 키는 '다리를 편 키'로 나눈다 (보폭 보정). 위쪽 기준선은 세로 좌표 그대로다
    return {
        "height": round(Hs, 1),
        "vertical": int(h),
        "chin": chin / Hs,
        "shoulder": (shoulder / Hs) if shoulder is not None else float("nan"),
        "crotch": (crotch / Hs) if crotch is not None else float("nan"),
        "head_w": head_w / Hs,
        "shoulder_w": shoulder_w / Hs,
        "foot_w": foot_w / Hs,
        "_rows": {"chin": chin, "shoulder": shoulder, "crotch": crotch, "bottom": h - 1},
        "_stance": stance,
    }


def crop_alpha_image(img):
    a = np.asarray(img)[:, :, 3] > 128
    ys, xs = np.where(a)
    return img.crop((xs.min(), ys.min(), xs.max() + 1, ys.max() + 1))


def figures(path, n=None):
    """
    한 장에 있는 인물들. n을 알면 파이프라인과 같은 seam 분할(1행 n열)로 자른다 — 망토·무기가 옆 인물에 닿아
    투명한 세로 틈이 없어도 투명한 곳을 따라 굽어서 나눈다(Knight 1차: 틈으로 나누면 4명이 2명으로 잡혔다).
    """
    img = Image.open(path).convert("RGBA")
    arr = np.asarray(img).copy()
    arr[arr[:, :, 3] <= 30] = 0
    if n and n > 1:
        frames, _, _ = C.P.extract_frames(arr, n, 1, n, None, True)
        return [f["image"] for f in frames]
    img = Image.fromarray(arr)
    alpha = arr[:, :, 3] > 30
    return [crop_alpha_image(img.crop((x0, 0, x1, img.height))) for x0, x1 in split_figures(alpha, n)]


KEYS = ["chin", "shoulder", "crotch", "head_w", "shoulder_w", "foot_w"]


def fmt(m):
    return "  ".join(f"{k} {m[k] * 100:5.1f}%" for k in KEYS) + f"  (키 {m['height']:.0f}px)"


def guide_image(fig, m, path, label=""):
    """인물 + 기준선(빨강 턱, 주황 어깨, 분홍 가랑이, 파랑 발바닥)."""
    out = Image.new("RGBA", (fig.width + 160, fig.height + 20), (255, 255, 255, 255))
    out.alpha_composite(fig, (10, 10))
    d = ImageDraw.Draw(out)
    for key, col in (("chin", (220, 0, 0)), ("shoulder", (255, 140, 0)), ("crotch", (230, 0, 230)), ("bottom", (0, 80, 255))):
        y = m["_rows"].get(key)
        if y is None:
            continue
        d.line([(0, y + 10), (fig.width + 20, y + 10)], fill=col, width=2)
        d.text((fig.width + 24, y + 4), key, fill=col)
    d.text((4, 0), label, fill=(0, 0, 0))
    out.convert("RGB").save(path)


# ---------------------------------------------------------------- 명령

def cmd_bald(args):
    character = SC.character_of(args.reference)
    frames, _ = C.load_frames(args.reference)
    ref = C.crop_frame(frames[0]["image"])
    job = "Mannequin"
    if args.dry_run:
        work, n = CI.dryrun_dir(job), None
    else:
        try:
            CI.check_usage(args.limit)
        except CI.CodexError as e:
            print(f"RESULT {json.dumps({'ok': False, 'error': str(e)}, ensure_ascii=False)}")
            sys.exit(3 if getattr(e, "over_limit", False) else 1)
        work, n = CI.new_try_dir(job)
    ref.save(os.path.join(work, "character.png"))
    if args.dry_run:
        with open(os.path.join(work, "prompt.md"), "w", encoding="utf-8") as fp:
            fp.write(BALD_PROMPT)
        print(f"RESULT {json.dumps({'ok': True, 'dry_run': True, 'workdir': slash(work)}, ensure_ascii=False)}")
        return
    try:
        result = CI.run(work, BALD_PROMPT, ["character.png"], args.timeout)
    except CI.CodexError as e:
        print(f"RESULT {json.dumps({'ok': False, 'error': str(e), 'workdir': slash(work)}, ensure_ascii=False)}")
        sys.exit(1)
    print(f"RESULT {json.dumps({'ok': True, 'try': n, 'image': slash(result), 'character': character}, ensure_ascii=False)}")


TURN_TOL = 0.05  # 턴어라운드 세로 기준선: M1 대비 ±5%(상대) / 앞·뒤 폭 차이 ±8%
# 방향별로 실루엣에서 믿을 수 있는 기준선만 판정한다 (M2 1차에서 확인):
#   3/4는 다리가 겹쳐 가랑이를 낮게 잡고(67%), 옆모습은 가랑이가 안 보이고 턱이 옆얼굴 윤곽에 걸린다.
#   어깨는 팔 자세에 따라 검출 위치가 달라 M1(팔 굽힘)과 A포즈 사이에 ±8%까지 흔들린다.
VIEW_CHECKS = {
    "front": {"chin": TURN_TOL, "crotch": TURN_TOL, "shoulder": 0.10},
    "three_quarter": {"chin": TURN_TOL},
    "side": {},
    "back": {"chin": TURN_TOL, "crotch": TURN_TOL, "shoulder": 0.10},
}


def cmd_turnaround(args):
    figs = figures(args.m1, 1)
    m1 = landmarks(figs[0])
    if any(np.isnan(m1[k]) for k in ("chin", "shoulder", "crotch")):
        sys.exit(f"M1에서 기준선을 못 쟀다: {fmt(m1)} — measure로 확인한다")
    job = "Mannequin_Turnaround"
    images = ["mannequin.png"]
    extra = ""
    if args.previous:
        images.append("previous.png")
        extra = ("2. previous.png — an earlier turnaround of this mannequin. "
                 + (args.previous_note or "Use it as the base.") + "\n")
    fixes = "".join(f"- {f}\n" for f in args.fix)
    prompt = (TURNAROUND_PROMPT.replace("{CHIN}", f"{m1['chin'] * 100:.0f}")
              .replace("{SHOULDER}", f"{m1['shoulder'] * 100:.0f}").replace("{CROTCH}", f"{m1['crotch'] * 100:.0f}")
              .replace("Attached image:\n1. mannequin.png", "Attached images:\n1. mannequin.png")
              .replace("{EXTRA}", (f"Other reference:\n{extra}\n" if extra else "")
                       + (f"Corrections measured on the previous attempt (apply them):\n{fixes}\n" if fixes else "")))
    if args.dry_run:
        work, n = CI.dryrun_dir(job), None
    else:
        try:
            CI.check_usage(args.limit)
        except CI.CodexError as e:
            print(f"RESULT {json.dumps({'ok': False, 'error': str(e)}, ensure_ascii=False)}")
            sys.exit(3 if getattr(e, "over_limit", False) else 1)
        work, n = CI.new_try_dir(job)
    figs[0].save(os.path.join(work, "mannequin.png"))
    if args.previous:
        Image.open(args.previous).save(os.path.join(work, "previous.png"))
    if args.dry_run:
        with open(os.path.join(work, "prompt.md"), "w", encoding="utf-8") as fp:
            fp.write(prompt)
        print(f"RESULT {json.dumps({'ok': True, 'dry_run': True, 'workdir': slash(work)}, ensure_ascii=False)}")
        return
    try:
        result = CI.run(work, prompt, images, args.timeout)
    except CI.CodexError as e:
        print(f"RESULT {json.dumps({'ok': False, 'error': str(e), 'workdir': slash(work)}, ensure_ascii=False)}")
        sys.exit(1)
    print(f"RESULT {json.dumps({'ok': True, 'try': n, 'image': slash(result)}, ensure_ascii=False)}")


def cmd_verify(args):
    """턴어라운드(4방향)를 M1과 비교. 종료 코드 0 합격 / 4 불합격."""
    m1 = landmarks(figures(args.m1, 1)[0])
    figs = figures(args.image, len(VIEWS))
    fails = []
    if len(figs) != len(VIEWS):
        fails.append(f"인물 {len(figs)}명 (4명이어야 한다)")
    print(f"M1        {fmt(m1)}")
    ms = []
    for view, fig in zip(VIEWS, figs):
        m = landmarks(fig)
        ms.append(m)
        print(f"{view:13} {fmt(m)}")
        for k, tol in VIEW_CHECKS[view].items():
            d = m[k] / m1[k] - 1 if not np.isnan(m[k]) else float("nan")
            if np.isnan(d) or abs(d) > tol:
                fails.append(f"{view} {k} {d * 100:+.1f}%")
        path = os.path.join(C.PREVIEW_DIR, f"_turnaround_{view}.png")
        guide_image(fig, m, path, view)
    if len(ms) == 4:
        heights = [m["height"] for m in ms]
        if max(heights) / min(heights) - 1 > TURN_TOL:
            fails.append(f"방향별 키가 다르다 {heights}")
        for k in ("head_w", "shoulder_w", "foot_w"):
            d = ms[3][k] / ms[0][k] - 1
            if abs(d) > 0.08:
                fails.append(f"앞·뒤 {k} {d * 100:+.1f}%")
    print("판정:", "합격" if not fails else "불합격 — " + "; ".join(fails))
    print("옆모습과 방향 간 일관성(같은 몸인지)은 수치로 보지 않는다 — 결과 이미지를 눈으로 본다")
    print(f"RESULT {json.dumps({'ok': True, 'pass': not fails, 'fails': fails}, ensure_ascii=False)}")
    sys.exit(0 if not fails else 4)


FOOT_TOP = 0.86  # 발목(발 윗선) 높이 — 마네킹의 뭉툭한 발은 아래 14% 안에 있다. 다리 보정은 이 위만 늘린다


def figure_box(path, index, n):
    """시트 좌표에서 index번째 인물의 (x0, top, x1, bottom)."""
    arr = np.asarray(Image.open(path).convert("RGBA"))
    alpha = arr[:, :, 3] > 30
    x0, x1 = split_figures(alpha, n)[index]
    ys = np.where(alpha[:, x0:x1].any(1))[0]
    return x0, int(ys.min()), x1, int(ys.max())


def cmd_stretch_legs(args):
    """
    턴어라운드 전체에서 가랑이~발목 띠만 세로로 늘려 가랑이 비율을 목표값에 맞춘다(발 모양은 그대로).
    네 방향이 같은 크기·같은 바닥선이라 앞모습에서 잰 행으로 모두 함께 맞는다.
    모델이 다리를 짧게 그리는 쪽으로 돌아가 지시로는 안 고쳐졌다(M2 1·2차 모두 가랑이 61%, 목표 58%).
    """
    target = args.target
    if target is None:
        target = landmarks(figures(args.m1, 1)[0])["crotch"]
    src = Image.open(args.image).convert("RGBA")
    arr = np.asarray(src).copy()
    arr[arr[:, :, 3] <= 30] = 0
    src = Image.fromarray(arr)
    _, top, _, _ = figure_box(args.image, 0, len(VIEWS))
    m = landmarks(figures(args.image, len(VIEWS))[0])
    C, H = m["_rows"]["crotch"], m["vertical"]
    if C is None:
        sys.exit("앞모습에서 가랑이를 못 찾았다")
    F = int(H * FOOT_TOP)
    # 키를 '세로 키'로 근사한다 (A포즈는 보폭이 작아 standing_height와 1~2% 차이)
    k = ((C / target) - C - (H - F)) / (F - C)
    if k < 1:
        sys.exit(f"다리가 이미 목표보다 길다 (늘림 {k:.3f}) — 줄이는 보정은 하지 않는다")
    y0, y1 = top + C, top + F
    band = src.crop((0, y0, src.width, y1)).resize((src.width, round((y1 - y0) * k)), Image.LANCZOS)
    out = Image.new("RGBA", (src.width, src.height + band.height - (y1 - y0)))
    out.paste(src.crop((0, 0, src.width, y0)), (0, 0))
    out.paste(band, (0, y0))
    out.paste(src.crop((0, y1, src.width, src.height)), (0, y0 + band.height))
    out.save(args.out)
    print(f"가랑이 {m['crotch'] * 100:.1f}% → 목표 {target * 100:.1f}%, 가랑이~발목 {k:.3f}배")
    print(f"RESULT {json.dumps({'ok': True, 'image': slash(args.out), 'stretch': round(k, 3)}, ensure_ascii=False)}")


def cmd_save(args):
    """합격한 M1·턴어라운드를 assets/mannequin/ 에 기준으로 저장하고 방향별 기준선을 mannequin.json에 쓴다."""
    os.makedirs(ASSET_DIR, exist_ok=True)
    m1_fig = figures(args.m1, 1)[0]
    m1_fig.save(os.path.join(ASSET_DIR, "m1_reference_pose.png"))
    turn = Image.open(args.turnaround).convert("RGBA")
    arr = np.asarray(turn).copy()
    arr[arr[:, :, 3] <= 30] = 0
    Image.fromarray(arr).save(os.path.join(ASSET_DIR, "turnaround.png"))
    figs = figures(args.turnaround, len(VIEWS))
    views, guides = {}, []
    for view, fig in zip(VIEWS, figs):
        m = landmarks(fig)
        views[view] = {k: (None if np.isnan(m[k]) else round(m[k], 4)) for k in KEYS}
        g = os.path.join(C.PREVIEW_DIR, f"_mannequin_guide_{view}.png")
        guide_image(fig, m, g, view)
        guides.append(Image.open(g))
    sheet = Image.new("RGB", (sum(g.width for g in guides), max(g.height for g in guides)), "white")
    x = 0
    for g in guides:
        sheet.paste(g, (x, 0))
        x += g.width
    sheet.save(os.path.join(ASSET_DIR, "turnaround_guide.png"))
    m1 = landmarks(m1_fig)
    # 기준 캐릭터에서 잰 값(reference_face 등)은 마네킹을 바꿔도 유지한다
    spec_path = os.path.join(ASSET_DIR, "mannequin.json")
    kept = {}
    if os.path.exists(spec_path):
        with open(spec_path, encoding="utf-8") as fp:
            kept = {k: v for k, v in json.load(fp).items() if k.startswith("reference_")}
    spec = kept | {
        "source": args.source,
        "note": args.note,
        "views": VIEWS,
        "m1": {k: (None if np.isnan(m1[k]) else round(m1[k], 4)) for k in KEYS},
        "turnaround": views,
        "checks": VIEW_CHECKS,
    }
    with open(os.path.join(ASSET_DIR, "mannequin.json"), "w", encoding="utf-8") as fp:
        json.dump(spec, fp, ensure_ascii=False, indent=2)
    print(f"RESULT {json.dumps({'ok': True, 'dir': slash(ASSET_DIR)}, ensure_ascii=False)}")


def cmd_reskull(args):
    """
    사용자가 손으로 그린 두개골 선(가이드 이미지의 파란 선)에 맞춰 M1의 머리만 편집한다.
    Knight 검증 중 사용자가 '기준 캐릭터 두개골과 마네킹 두개골이 다르다'며 얼굴 비교 그림 위에 파란 선을 그려 줬다(2026-10-14).
    """
    job = "Mannequin_Reskull"
    try:
        CI.check_usage(args.limit)
    except CI.CodexError as e:
        print(f"RESULT {json.dumps({'ok': False, 'error': str(e)}, ensure_ascii=False)}")
        sys.exit(3 if getattr(e, "over_limit", False) else 1)
    work, n = CI.new_try_dir(job)
    Image.open(args.m1).convert("RGBA").save(os.path.join(work, "mannequin.png"))
    Image.open(args.guide).convert("RGB").save(os.path.join(work, "guide.png"))
    images = ["mannequin.png", "guide.png"]
    if args.previous:
        Image.open(args.previous).convert("RGBA").save(os.path.join(work, "previous.png"))
        images.append("previous.png")
    notes = "".join(f"- {x}\n" for x in args.note)
    if args.previous:
        notes += f"- previous.png is an earlier edit: {args.previous_note or 'use it as the base'}\n"
    prompt = RESKULL_PROMPT.replace("{NOTES}", notes)
    try:
        result = CI.run(work, prompt, images, args.timeout)
    except CI.CodexError as e:
        print(f"RESULT {json.dumps({'ok': False, 'error': str(e), 'workdir': slash(work)}, ensure_ascii=False)}")
        sys.exit(1)
    print(f"RESULT {json.dumps({'ok': True, 'try': n, 'image': slash(result)}, ensure_ascii=False)}")


def cmd_measure(args):
    figs = figures(args.image, args.views)
    out = []
    for i, fig in enumerate(figs):
        m = landmarks(fig)
        print(f"[{i}] {fmt(m)}")
        path = os.path.join(C.PREVIEW_DIR, f"_mannequin_{os.path.splitext(os.path.basename(args.image))[0]}_{i}.png")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        guide_image(fig, m, path, str(i))
        out.append({k: (None if np.isnan(m[k]) else round(m[k], 4)) for k in KEYS} | {"height": m["height"], "guide": slash(path)})
    print(f"RESULT {json.dumps({'ok': True, 'figures': out}, ensure_ascii=False)}")


def main():
    C.utf8_stdout()
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("bald")
    b.add_argument("--reference", required=True, help="기준 시트 (사용자가 지정)")
    b.add_argument("--limit", type=float, default=85)
    b.add_argument("--timeout", type=int, default=900)
    b.add_argument("--dry-run", action="store_true")
    m = sub.add_parser("measure")
    m.add_argument("image")
    m.add_argument("--views", type=int, help="한 장에 있는 인물 수 (턴어라운드)")
    t = sub.add_parser("turnaround")
    t.add_argument("--m1", required=True, help="합격한 M1(민머리 마네킹) 이미지")
    t.add_argument("--limit", type=float, default=85)
    t.add_argument("--timeout", type=int, default=900)
    t.add_argument("--dry-run", action="store_true")
    t.add_argument("--previous", help="베이스로 삼을 이전 턴어라운드")
    t.add_argument("--previous-note", help="이전 시도에서 무엇이 맞고 틀렸는지 (영어)")
    t.add_argument("--fix", action="append", default=[], help="고칠 점 (영어, 측정값 포함)")
    v = sub.add_parser("verify")
    v.add_argument("--m1", required=True)
    v.add_argument("image", help="턴어라운드 결과")
    s = sub.add_parser("stretch-legs")
    s.add_argument("image", help="턴어라운드")
    s.add_argument("--m1", help="목표 가랑이 비율을 잴 M1 (--target 생략 시)")
    s.add_argument("--target", type=float, help="정수리~가랑이 / 키 (0~1)")
    s.add_argument("--out", required=True)
    sv = sub.add_parser("save")
    sv.add_argument("--m1", required=True)
    sv.add_argument("--turnaround", required=True)
    sv.add_argument("--source", required=True, help="기준 시트 이름 (예: Archer_Idle_v7)")
    sv.add_argument("--note", default="")
    r2 = sub.add_parser("reskull")
    r2.add_argument("--m1", required=True)
    r2.add_argument("--guide", required=True, help="M1 위에 올바른 머리 윤곽을 파란 선으로 그린 이미지")
    r2.add_argument("--note", action="append", default=[], help="가이드에서 읽은 차이 (영어)")
    r2.add_argument("--previous")
    r2.add_argument("--previous-note")
    r2.add_argument("--limit", type=float, default=85)
    r2.add_argument("--timeout", type=int, default=900)
    args = p.parse_args()
    if args.cmd == "stretch-legs" and args.target is None and not args.m1:
        p.error("--m1 또는 --target이 필요하다")
    {"bald": cmd_bald, "measure": cmd_measure, "turnaround": cmd_turnaround, "verify": cmd_verify,
     "stretch-legs": cmd_stretch_legs, "save": cmd_save, "reskull": cmd_reskull}[args.cmd](args)


if __name__ == "__main__":
    main()
