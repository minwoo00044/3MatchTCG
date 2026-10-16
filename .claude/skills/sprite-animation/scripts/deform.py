"""
HD 원화 → 데포르메 턴어라운드(앞·3/4·옆·뒤, A포즈). 새 캐릭터 v1 생성의 첫 단계.
비율·자세는 체형 마네킹(assets/mannequin/), 디자인은 HD 원화, 화풍은 기준 캐릭터에서 가져온다.

  init --character Knight --height-cm 170 --hint tall --required "..." [--required ...] [--profile "..."]
      [관문 1: 설정 입력] 생성 전에 사용자에게 받은 설정으로 {캐릭터}.character.json을 만든다.
      키(cm)·체형 힌트·필수 디자인 요소·프로필(체격·성격·무기 쥐는 손). skull_over_L은 추정값.
  generate --character Knight --source HD.png [--hint normal|young|tall] [--design-note "..."]
           [--previous P.png --previous-note "..."] [--fix "..."] [--dry-run]
      힌트·필수 디자인 요소는 생략하면 character.json에서 읽는다(init이 먼저다).
      작업 폴더 SpriteRegen/{캐릭터}_Deform/try{N}/ (git 무시). 수 분 걸린다 — 백그라운드로 돌린다.
  verify --hint normal RESULT.png
      수치 판정: 4명으로 나뉘는지, 네 방향 세로 키가 같은지(±5%). 0 합격 / 4 불합격.
      가랑이는 참고만 한다 — 다리 틈이 닫히는 줄이라 치마·긴 머리카락이 가리면 그 높이를 잡는다.
      이미지: 마네킹 윤곽을 같은 바닥선·같은 키로 겹친 비교(Temp/SpriteAnimationPipeline/_deform_overlay.png).
      옷을 입은 캐릭터는 실루엣으로 턱을 못 잡는다(머리카락·옷깃이 목을 가린다) — 머리 크기는 비교 이미지로 본다.
  lineup --character Knight RESULT.png [--with Archer ...]
      [관문 2: 비교샷] 새 캐릭터 3/4와 기존 캐릭터들을 설정 키(cm) 비율대로 같은 바닥선에 세운 그림
      (Temp/SpriteAnimationPipeline/_lineup_{캐릭터}.png). 사용자가 이 그림을 보고 확정해야 accept한다.
  accept --character Knight RESULT.png
      합격본을 Assets/_/Spirte/{캐릭터}/design/{캐릭터}_turnaround.png 로, 원화를 {캐릭터}_source.png 로 둔다. 다음은 idle_base.py.

체형 힌트: 마네킹은 Archer 체형이다. 어리거나 키 큰 캐릭터는 완벽히 맞지 않으므로 목표·허용 폭을 바꾼다
(사용자 지정 2026-10-14: "최대한 따라간다"). 힌트는 원화를 보고 제안하고 사용자가 정한다.
"""
import argparse
import json
import os
import shutil
import sys

import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(__file__))
import codex_image as CI  # noqa: E402
import common as C  # noqa: E402
import mannequin as M  # noqa: E402

# 머리·다리 배율(마네킹 대비)과 허용 폭. 머리 배율은 프롬프트로만 전한다(턱을 실루엣으로 못 재서)
HINTS = {
    "normal": {"head": 1.00, "legs": 1.00, "tol": 0.06,
               "say": "Match the mannequin's proportions exactly."},
    "young": {"head": 1.10, "legs": 0.90, "tol": 0.08,
              "say": "This character is younger/smaller: head about 10% larger and legs about 10% shorter than the mannequin, "
                     "otherwise follow the mannequin as closely as possible."},
    "tall": {"head": 0.92, "legs": 1.08, "tol": 0.08,
             "say": "This character is taller/more mature: head about 8% smaller and legs about 8% longer than the mannequin, "
                    "otherwise follow the mannequin as closely as possible."},
}

LEG_SPLIT_TOL = 0.15  # 다리 갈라짐이 마네킹보다 이만큼 넘게 짧으면 불합격 (Archer는 마네킹 3/4 대비 -2%)

PROMPT = """Use your image generation tool to create ONE new image and save it as a PNG at `./out/result.png` (create `out` if needed). Do nothing else.

Attached images:
1. source.png — the ORIGINAL high-detail character design. Source of truth for the DESIGN: face, hairstyle and hair color, outfit, colors, materials, accessories, weapon. If it shows several views (e.g. front / side / back), use each view as the design truth for the matching view of your turnaround, and derive the 3/4 view from the front and side views. Ignore its body proportions (realistic adult proportions) and its background.
2. mannequin_turnaround.png — a gray mannequin turnaround (front, 3/4 facing right, side facing right, back) in a neutral A-pose. Source of truth for the BODY PROPORTIONS, POSE and LAYOUT.
3. style_reference.png — an existing character from the same game. Source of truth for the ART STYLE only (chibi deformation, line weight, painted shading, level of detail). Ignore its design, colors and pose.
{EXTRA_REFS}
Task: draw the character from #1 as a chibi game character TURNAROUND SHEET, built exactly on the mannequin #2:
- The same four views as #2, left to right: front, 3/4 view facing right, side view facing right (profile), back view.
- The same neutral A-pose as #2 in every view (standing straight, feet slightly apart, arms down angled away from the body, hands relaxed).
- The body inside the clothes follows #2: same head (skull) size, chin height, shoulder line, crotch height, leg length, and chunky chibi feet/shoes of the same size. Hair, clothes and accessories go ON TOP of this body — volumous hair or a long coat may extend beyond the mannequin outline, but the body underneath must not change.
- {HINT}
- Keep every design element of #1 recognisable and consistent across all four views (including the back): hairstyle, outfit pieces, colors, patterns, accessories. Simplify small details for chibi scale, do not invent new elements.
- A hand-held weapon is held loosely in one hand, pointing down, without changing the A-pose. Back-mounted items stay on the back.
- Colors: the same colors as #1 (same hue, saturation and brightness). No color grading, no glow, no rim light, no lighting effects.
- Neutral calm expression.
{FIXES}
Layout (critical): landscape canvas, the four figures side by side at the SAME scale and SAME height, all soles on ONE horizontal baseline near the bottom, evenly spaced with clear transparent gaps between figures; nothing touches the canvas edge. Fully transparent background. No floor, shadow, text, labels, numbers or guide lines.
"""


def slash(p):
    return p.replace("\\", "/")


def mannequin_spec():
    with open(os.path.join(M.ASSET_DIR, "mannequin.json"), encoding="utf-8") as fp:
        return json.load(fp)


def reference_name(spec):
    ref = spec.get("reference")
    return ref["name"] if ref else spec["source"]


def style_reference(spec):
    """
    기준 캐릭터 한 명(비율·얼굴형·화풍의 정답, 3/4 모습).
    mannequin.json "reference"가 있으면 그 턴어라운드의 한 방향(마네킹 v3부터: Knight 9차 3/4 — 사용자가 "옳게 된 비율"로 확정),
    없으면 마네킹을 만든 시트("source")의 0번 프레임(v1·v2: Archer Idle). 시트가 prev/로 갔으면 거기서 찾는다.
    """
    ref = spec.get("reference")
    if ref:
        return M.figures(os.path.join(C.ROOT, ref["turnaround"]), len(M.VIEWS))[ref.get("view", 1)]
    name = spec["source"]
    character = name.split("_")[0]
    for p in (os.path.join(C.SHEET_ROOT, character, name + ".png"), os.path.join(C.SHEET_ROOT, character, "prev", name + ".png")):
        if os.path.exists(p):
            frames, _ = C.load_frames(p)
            return C.crop_frame(frames[0]["image"])
    sys.exit(f"화풍 참고 시트가 없다: {name}")


def on_white(img):
    bg = Image.new("RGBA", img.size, (255, 255, 255, 255))
    bg.alpha_composite(img.convert("RGBA"))
    return bg.convert("RGB")


def done(ok, code, **kw):
    print(f"RESULT {json.dumps({'ok': ok, **kw}, ensure_ascii=False)}")
    sys.exit(code)


def cmd_generate(args):
    cfg = character_config(args.character)
    if cfg is None:
        done(False, 1, error=f"{args.character}.character.json이 없다 — 설정 입력(init)을 먼저 한다: 키·체형 힌트·필수 디자인 요소를 사용자에게 묻는다")
    args.hint = args.hint or cfg.get("hint", "normal")
    required = cfg.get("design", {}).get("required", [])
    if required and not args.design_note:
        args.design_note = "must keep: " + "; ".join(required)
    if not os.path.exists(args.source):
        done(False, 1, error=f"원화 파일이 없다: {args.source}")
    if len(args.previous_note) not in (0, len(args.previous)):
        done(False, 1, error="--previous-note 개수가 --previous와 다르다")
    spec = mannequin_spec()
    job = f"{args.character}_Deform"
    if args.dry_run:
        work, n = CI.dryrun_dir(job), None
    else:
        try:
            CI.check_usage(args.limit)
        except CI.CodexError as e:
            done(False, 3 if getattr(e, "over_limit", False) else 1, error=str(e))
        work, n = CI.new_try_dir(job)

    on_white(Image.open(args.source)).save(os.path.join(work, "source.png"))
    shutil.copy(os.path.join(M.ASSET_DIR, "turnaround.png"), os.path.join(work, "mannequin_turnaround.png"))
    on_white(style_reference(spec)).save(os.path.join(work, "style_reference.png"))
    images = ["source.png", "mannequin_turnaround.png", "style_reference.png"]
    extra = []
    for i, prev in enumerate(args.previous, start=len(images) + 1):
        name = f"previous_{i}.png"
        shutil.copy(prev, os.path.join(work, name))
        images.append(name)
        note = args.previous_note[i - 4] if args.previous_note else "an earlier attempt"
        extra.append(f"{i}. {name} — {note}")
    fixes = [f"- {f}" for f in args.fix]
    if args.design_note:
        fixes.insert(0, f"- Design notes from the user: {args.design_note}")
    prompt = (PROMPT.replace("{EXTRA_REFS}", "\n".join(extra) + ("\n" if extra else ""))
              .replace("{HINT}", HINTS[args.hint]["say"])
              .replace("{FIXES}", ("Corrections / notes:\n" + "\n".join(fixes) + "\n") if fixes else ""))
    info = {"try": n, "workdir": slash(work), "hint": args.hint}
    with open(os.path.join(work, "meta.json"), "w", encoding="utf-8") as fp:
        json.dump({"character": args.character, "source": os.path.abspath(args.source).replace("\\", "/"),
                   "hint": args.hint, "design_note": args.design_note}, fp, ensure_ascii=False, indent=2)
    if args.dry_run:
        with open(os.path.join(work, "prompt.md"), "w", encoding="utf-8") as fp:
            fp.write(prompt)
        done(True, 0, dry_run=True, **info)
    try:
        result = CI.run(work, prompt, images, args.timeout)
    except CI.CodexError as e:
        done(False, 1, error=str(e), **info)
    done(True, 0, image=slash(result), **info)


def face_chin(fig):
    """
    얼굴 피부의 아래 끝 행(인물 이미지 좌표). 위에서 처음 나오는 '충분히 큰' 피부 덩어리(세로로 키의 3% 이상 이어짐)를
    얼굴로 본다 — 머리카락의 분홍빛 하이라이트 같은 잔점을 얼굴로 잡지 않게(Knight 5차: 턱을 키의 1%로 잡음).
    가슴·허벅지 피부는 그 아래 따로 나온다. 피부색 범위는 애니풍 밝은 피부 기준. 못 찾으면 None.
    """
    alpha = np.asarray(fig)[:, :, 3] > 128
    skin = skin_mask(fig)
    xs = np.where(alpha.any(0))[0]
    cx = int(xs.mean())
    band = skin[: int(fig.height * 0.6), max(0, cx - fig.width // 6): cx + fig.width // 6]
    count = band.sum(1)
    rows = np.where(count > 8)[0]
    blobs, cur = [], []
    for r in rows:
        if cur and r - cur[-1] > 3:
            blobs.append(cur)
            cur = []
        cur.append(r)
    if cur:
        blobs.append(cur)
    blobs = [b for b in blobs if b[-1] - b[0] >= fig.height * 0.03]
    if not blobs:
        return None
    start, end = blobs[0][0], blobs[0][-1]
    # 얼굴이 목·V넥 가슴 피부로 끊김 없이 이어지면 덩어리 끝은 목 아래다(Archer: 32.1%를 턱으로 잡음, 실제 30.6%).
    # 얼굴 폭이 가장 넓은 줄 아래에서 폭이 그 30% 밑으로 처음 떨어지는 줄을 턱으로 본다
    peak = start + int(np.argmax(count[start:end + 1]))
    narrow = np.where(count[peak:end + 1] < count[peak] * 0.3)[0]
    if len(narrow):
        end = peak + int(narrow[0]) - 1
    return int(end)


def overlay(fig, mann, s, label):
    """
    캐릭터 위에 마네킹 윤곽(빨강)을 바닥선을 맞춰 겹친다. 배율 s는 네 방향 공통(두 턴어라운드 모두 네 방향이 같은 크기).
    """
    mm = mann.resize((max(1, round(mann.width * s)), max(1, round(mann.height * s))), Image.LANCZOS)
    a = np.asarray(mm)[:, :, 3] > 128
    edge = a & ~(np.roll(a, 1, 0) & np.roll(a, -1, 0) & np.roll(a, 1, 1) & np.roll(a, -1, 1))
    W, H = max(fig.width, mm.width) + 20, max(fig.height, mm.height) + 30
    out = Image.new("RGBA", (W, H), (255, 255, 255, 255))
    out.alpha_composite(fig, ((W - fig.width) // 2, H - 10 - fig.height))
    ov = np.zeros((mm.height, mm.width, 4), np.uint8)
    ov[edge] = (230, 0, 0, 255)
    out.alpha_composite(Image.fromarray(ov), ((W - mm.width) // 2, H - 10 - mm.height))
    ImageDraw.Draw(out).text((4, 2), label, fill=(0, 0, 0))
    return out


def feet_center(fig):
    """바닥 띠에서 가장 넓은 두 덩어리(두 발)의 가운데 x. 바닥까지 내려온 검 끝 같은 좁은 덩어리는 거른다."""
    a = np.asarray(fig)[:, :, 3] > 128
    h = a.shape[0]
    band = a[h - max(4, int(h * 0.05)):].any(0)
    d = np.diff(np.concatenate(([0], band.astype(np.int8), [0])))
    runs = sorted(zip(np.where(d == 1)[0], np.where(d == -1)[0]), key=lambda r: r[1] - r[0], reverse=True)[:2]
    return float(np.mean([(a0 + b0) / 2 for a0, b0 in runs]))


CHEEK_INVALID = 0.60  # 이보다 넓으면 볼이 아니라 머리카락까지 잰 것 (Priest 1차 +142%)
CHEEK_TOL = 0.10  # 3/4 모습 아래 볼(눈~턱 75%) 폭이 기준 캐릭터보다 이만큼 넘게 넓으면 불합격 (Knight 4차 +13%: 사용자가 "볼이 빵빵"이라 지적)


def skin_mask(fig):
    hsv = np.asarray(fig.convert("RGB").convert("HSV")).astype(float)
    alpha = np.asarray(fig)[:, :, 3] > 128
    h, s, v = hsv[..., 0] * 360 / 255, hsv[..., 1] / 255, hsv[..., 2] / 255
    return alpha & ((h < 35) | (h > 345)) & (s > 0.12) & (s < 0.45) & (v > 0.75)


def face_profile(fig, eye_ratio):
    """
    얼굴 윤곽: 눈~턱 사이 줄마다 얼굴 피부(턱 위 한 덩어리)의 좌우 끝. 눈 높이는 기준 캐릭터 비율(eye_ratio)로 놓는다.
    반환: {"chin", "eye", "L", "cx"(턱 근처 얼굴 가운데), "rows": [(y, left, right)], "w": {50, 75, 90: 폭/L}} 또는 None.
    뺨 가장자리가 머리카락에 가리면 폭이 작게 잡힌다(Archer 왼쪽 볼) — 그래서 비교는 머리카락이 덜 가리는 아래쪽(50~90%)만 한다.
    """
    chin = face_chin(fig)
    if chin is None or not eye_ratio:
        return None
    L = fig.height - 1 - chin
    eye = int(chin - eye_ratio * L)
    sk = skin_mask(fig)
    mid = (eye + chin) // 2
    d = np.diff(np.concatenate(([0], sk[mid].astype(np.int8), [0])))
    runs = list(zip(np.where(d == 1)[0], np.where(d == -1)[0]))
    if not runs:
        return None
    a, b = max(runs, key=lambda r: r[1] - r[0])
    # 씨앗에서 이어진 피부만 (BFS). 턱 아래는 자른다
    face = np.zeros_like(sk)
    stack = [(mid, (a + b) // 2)]
    face[stack[0]] = True
    H, W = sk.shape
    while stack:
        y, x = stack.pop()
        for ny, nx in ((y + 1, x), (y - 1, x), (y, x + 1), (y, x - 1)):
            if 0 <= ny <= chin and 0 <= nx < W and sk[ny, nx] and not face[ny, nx]:
                face[ny, nx] = True
                stack.append((ny, nx))
    rows = []
    for y in range(eye, chin + 1):
        xs = np.where(face[y])[0]
        if len(xs):
            rows.append((y, int(xs.min()), int(xs.max())))
    if not rows:
        return None

    def width(t):
        y = int(eye + t * (chin - eye))
        xs = np.where(face[y])[0]
        return (xs.max() - xs.min() + 1) / L if len(xs) else float("nan")

    near = [r for r in rows if r[0] >= chin - max(3, (chin - eye) // 10)]
    cx = float(np.mean([(r[1] + r[2]) / 2 for r in near]))
    return {"chin": chin, "eye": eye, "L": L, "cx": cx, "rows": rows, "w": {k: width(k / 100) for k in (50, 75, 90)}}


def mannequin_head(mann):
    """마네킹 머리: 두개골·턱 윤곽(테두리 마스크, 턱 위만)과 턱 줄."""
    chin = M.landmarks(mann)["_rows"]["chin"]
    a = np.asarray(mann)[:, :, 3] > 128
    edge = a & ~(np.roll(a, 1, 0) & np.roll(a, -1, 0) & np.roll(a, 1, 1) & np.roll(a, -1, 1))
    edge[chin + 1:] = False
    return {"edge": edge, "chin": chin}


def face_tile(fig, mann, label, eye_ratio, ref_prof=None):
    """
    캐릭터 얼굴에 가상 얼굴형을 겹친 확대 그림: 빨강 = 마네킹 두개골·턱 윤곽, 초록 = 기준 캐릭터의 눈 높이, 파랑 = 턱,
    노랑 점 = 기준 캐릭터의 아래 얼굴 윤곽(눈~턱, 턱 끝에 맞춤 — 볼이 빵빵한지 본다).
    크기는 턱~발바닥, 가로는 두 발 중심에 맞춘다(마네킹 M1은 Archer와 발 위치가 같게 만들었다).
    앞머리·머리카락 부피와 무관하게 얼굴 크기와 눈 높이를 본다.
    눈선은 마네킹의 그려진 눈선이 아니라 기준 캐릭터에서 잰 값이다(마네킹 눈선은 Codex가 임의로 그어 Archer 눈보다 위였다).
    """
    chin = face_chin(fig)
    if chin is None:
        return None
    head = mannequin_head(mann)
    s = (fig.height - 1 - chin) / (mann.height - 1 - head["chin"])
    fx, mfx = feet_center(fig), feet_center(mann)
    out = fig.convert("RGBA").copy()
    bg = Image.new("RGBA", out.size, (255, 255, 255, 255))
    bg.alpha_composite(out)
    ov = np.zeros((fig.height, fig.width, 4), np.uint8)
    ys, xs2 = np.where(head["edge"])
    ty = np.round(chin + (ys - head["chin"]) * s).astype(int)
    tx = np.round(fx + (xs2 - mfx) * s).astype(int)
    ok = (ty >= 0) & (ty < fig.height) & (tx >= 0) & (tx < fig.width)
    for dy in (0, 1):
        for dx in (0, 1):
            yy, xx = np.clip(ty[ok] + dy, 0, fig.height - 1), np.clip(tx[ok] + dx, 0, fig.width - 1)
            ov[yy, xx] = (230, 0, 0, 255)
    img = Image.alpha_composite(bg, Image.fromarray(ov))
    d = ImageDraw.Draw(img)
    d.line([(0, chin), (fig.width, chin)], fill=(0, 90, 255), width=2)
    L = fig.height - 1 - chin
    if eye_ratio:
        ey = chin - eye_ratio * L
        d.line([(0, ey), (fig.width, ey)], fill=(0, 190, 0), width=2)
    prof = face_profile(fig, eye_ratio)
    if ref_prof and prof:
        k = L / ref_prof["L"]
        for y, left, right in ref_prof["rows"][::2]:
            ty = chin + (y - ref_prof["chin"]) * k
            if y < ref_prof["eye"] + (ref_prof["chin"] - ref_prof["eye"]) * 0.45:
                continue  # 위쪽은 머리카락에 가려 기준 윤곽이 믿을 수 없다
            for x in (left, right):
                tx = prof["cx"] + (x - ref_prof["cx"]) * k
                d.ellipse([tx - 2, ty - 2, tx + 2, ty + 2], fill=(255, 200, 0))
    hx = np.where(head["edge"].any(0))[0]
    cx = fx + ((hx.min() + hx.max()) / 2 - mfx) * s  # 확대 영역 가운데 = 두개골 가운데
    # 머리 부분만 잘라 같은 크기로
    top = int(max(0, chin - (head["chin"] - np.where(np.asarray(mann)[:, :, 3].any(1))[0].min()) * s * 1.35))
    crop = img.crop((int(max(0, cx - 0.45 * L)), top, int(min(fig.width, cx + 0.45 * L)), int(min(fig.height, chin + 0.12 * L))))
    k = 260 / max(1, chin - top)
    crop = crop.resize((max(1, round(crop.width * k)), max(1, round(crop.height * k))), Image.LANCZOS)
    tile = Image.new("RGB", (crop.width, crop.height + 18), "white")
    tile.paste(crop.convert("RGB"), (0, 18))
    ImageDraw.Draw(tile).text((4, 2), label, fill=(0, 0, 0))
    return tile


def face_layout_image(spec, figs, mfigs, path):
    """얼굴 확대 비교: 기준 캐릭터+자기 마네킹(M1) | 새 캐릭터 앞·3/4 + 마네킹 앞·3/4."""
    # 기준 캐릭터에 겹칠 마네킹: 기준이 턴어라운드면 같은 방향의 마네킹, 아니면 기준 자세로 만든 M1
    if spec.get("reference"):
        m1 = mfigs[spec["reference"].get("view", 1)]
    else:
        m1 = Image.open(os.path.join(M.ASSET_DIR, "m1_reference_pose.png")).convert("RGBA")
    eye = spec.get("reference_face", {}).get("eye_to_chin_over_L")
    ref = style_reference(spec)
    ref_prof = face_profile(ref, eye)
    tiles = [face_tile(ref, m1, "REF " + reference_name(spec) + " + mannequin", eye, ref_prof),
             face_tile(figs[0], mfigs[0], "front", eye, ref_prof), face_tile(figs[1], mfigs[1], "3/4", eye, ref_prof)]
    tiles = [t for t in tiles if t is not None]
    if not tiles:
        return None
    H = max(t.height for t in tiles)
    out = Image.new("RGB", (sum(t.width for t in tiles) + 10 * len(tiles), H), "white")
    x = 0
    for t in tiles:
        out.paste(t, (x, 0))
        x += t.width + 10
    out.save(path)
    return path


def compare_with_reference(spec, figs, path):
    """
    기준 캐릭터(마네킹을 만든 시트 0번 프레임)와 새 캐릭터 앞·3/4를 턱~발바닥 길이를 같게 맞춰 나란히 놓는다.
    빨강 = 턱, 회색 = 턱~발바닥의 1/4·1/2·3/4. 머리 크기가 같아도 허리가 낮거나 실루엣이 넓으면 짜리몽땅해 보인다 —
    Knight 1~3차에서 사용자가 지적한 차이(다리 시작 0.48 vs Archer 0.43, 폭 +6~19%)가 이 그림에서 보였다.
    """
    T = 420
    items = [("REF " + reference_name(spec), style_reference(spec)), ("front", figs[0]), ("3/4", figs[1])]
    tiles = []
    for name, fig in items:
        chin = face_chin(fig)
        if chin is None:
            chin = int(fig.height * 0.3)
        L = fig.height - 1 - chin
        s = T / L
        f = fig.resize((max(1, round(fig.width * s)), max(1, round(fig.height * s))), Image.LANCZOS)
        h = max(720, f.height + 20)
        c = Image.new("RGBA", (f.width + 10, h), (255, 255, 255, 255))
        y0 = h - 10 - f.height
        c.alpha_composite(f, (5, y0))
        d = ImageDraw.Draw(c)
        d.line([(0, y0 + chin * s), (c.width, y0 + chin * s)], fill=(220, 0, 0), width=2)
        for k in (0.25, 0.5, 0.75):
            y = y0 + (chin + k * L) * s
            d.line([(0, y), (c.width, y)], fill=(150, 150, 150), width=1)
        d.text((4, 4), f"{name}  w/L {fig.width / L:.2f}", fill=(0, 0, 0))
        tiles.append(c)
    H = max(t.height for t in tiles)
    out = Image.new("RGB", (sum(t.width for t in tiles), H), "white")
    x = 0
    for t in tiles:
        out.paste(t.convert("RGB"), (x, H - t.height))
        x += t.width
    os.makedirs(os.path.dirname(path), exist_ok=True)
    out.save(path)
    return path


def cmd_verify(args):
    spec = mannequin_spec()
    hint = HINTS[args.hint]
    figs = M.figures(args.image, len(M.VIEWS))
    mfigs = M.figures(os.path.join(M.ASSET_DIR, "turnaround.png"), len(M.VIEWS))
    fails, notes = [], []
    if len(figs) != len(M.VIEWS):
        done(True, 4, **{"pass": False, "fails": [f"인물 {len(figs)}명 (4명이어야 한다)"]})
    heights = []
    tiles = []
    # 크기는 앞모습 '턱~발바닥'으로 맞춘다. 머리카락·무기에 영향받지 않는 길이다.
    #   발 폭: 바닥까지 내려온 검 끝에 끌렸다(Knight 1차: 마네킹이 1.4배).
    #   키: 민머리 마네킹 정수리가 머리카락 꼭대기에 놓여 기준선이 키의 ~10%만큼 위로 밀렸다 — 머리가 25% 크다고
    #   잘못 판단했다. 실제로는 Knight 턱 32.4% = Archer 32.3%(둘 다 머리카락 포함 키 기준)로 같았다.
    chin = face_chin(figs[0])
    m_rows = M.landmarks(mfigs[0])["_rows"]
    if chin is not None:
        scale = (figs[0].height - chin) / (m_rows["bottom"] - m_rows["chin"])
        print(f"앞모습 턱(얼굴 피부 아래 끝) {chin / figs[0].height * 100:.1f}% — 턱~발바닥으로 마네킹 크기를 맞춘다")
    else:
        scale = figs[0].height / mfigs[0].height
        notes.append("얼굴 피부를 못 찾아 키로 크기를 맞췄다 — 머리카락만큼 마네킹 기준선이 위로 밀려 보인다")
    for view, fig, mann in zip(M.VIEWS, figs, mfigs):
        m = M.landmarks(fig)
        # 방향 비교는 세로 키로 한다. '다리를 편 키'는 보폭 보정이 앞(벌림)·옆(겹침)에서 달라 차이를 부풀린다(Knight 1차: 9%)
        heights.append(m["vertical"])
        line = f"{view:13} 세로 키 {m['vertical']}px"
        if view in ("front", "back"):
            ref = spec["turnaround"][view]["crotch"]
            # 다리 배율 → 정수리~가랑이 비율 목표: 가랑이 아래가 L배가 되고 키로 다시 나눈다
            legs = 1 - ref
            target = (1 - legs) / ((1 - legs) + legs * hint["legs"])
            # 가랑이는 참고만 한다: 다리 틈이 닫히는 줄이라 치마 밑단·긴 머리카락이 가리면 그 높이를 잡는다
            # (Knight 1차: 앞 70%·뒤 77%, 실제는 치마 속). 다리 길이는 비교 이미지로 판단한다
            if not np.isnan(m["crotch"]) and m["_stance"].get("method") == "standing":
                d = m["crotch"] / target - 1
                line += f"  (참고) 다리 틈이 닫히는 줄 {m['crotch'] * 100:.1f}% — 목표 가랑이 {target * 100:.1f}%"
                if abs(d) > hint["tol"]:
                    notes.append(f"{view}: 다리 틈이 목표 가랑이보다 {d * 100:+.0f}% — 치마·머리카락에 가렸거나 다리가 짧다. 비교 이미지로 본다")
        if view in ("front", "three_quarter"):
            # 다리 갈라짐: 두 다리가 떨어져 보이는 구간(다리 틈이 닫히는 줄~발바닥) ÷ 턱~발바닥. 머리카락·무기와 무관하다.
            # 허벅지가 붙은 굵은 다리를 잡는다 — Knight 1차 0.36/0.31 (Archer 0.48, 마네킹 0.55/0.49)이 '짜리몽땅'의 원인이었다
            fchin = face_chin(fig)
            gap = m["_stance"].get("crotch")
            mm = M.landmarks(mann)
            mgap = mm["_stance"].get("crotch")
            if fchin is not None and gap and mgap:
                split = (fig.height - 1 - gap) / (fig.height - 1 - fchin)
                msplit = (mann.height - 1 - mgap) / (mann.height - 1 - mm["_rows"]["chin"]) * hint["legs"]
                d = split / msplit - 1
                line += f"  다리 갈라짐 {split:.2f} (마네킹 {msplit:.2f}, {d * 100:+.0f}%)"
                if d < -LEG_SPLIT_TOL:
                    # 참고만 한다: 다리 뒤에 망토·긴 옷자락이 있으면 다리가 떨어져 있어도 투명한 틈이 없어 짧게 잡힌다
                    # (Knight 3차: 다리가 분명히 떨어졌는데 남색 망토 안감 때문에 -52%)
                    notes.append(f"{view}: 다리 갈라짐 {d * 100:+.0f}% — 허벅지가 붙었거나 다리 뒤에 망토가 보인다. 비교 이미지로 본다")
            else:
                notes.append(f"{view}: 다리 갈라짐을 못 쟀다(얼굴 또는 다리 틈을 못 찾음) — 비교 이미지로 본다")
        print(line)
        tiles.append(overlay(fig, mann, scale, view))
    spread = max(heights) / min(heights) - 1
    if spread > 0.05:
        fails.append(f"방향별 키 차이 {spread * 100:.1f}%")

    # 얼굴 윤곽: 기준 캐릭터(3/4)와 같은 방향인 3/4 모습끼리 아래 얼굴 폭을 비교한다 (턱~발바닥 비율)
    eye_ratio = spec.get("reference_face", {}).get("eye_to_chin_over_L")
    ref_prof = face_profile(style_reference(spec), eye_ratio)
    for view, fig in (("three_quarter", figs[1]), ("front", figs[0])):
        prof = face_profile(fig, eye_ratio)
        if not (prof and ref_prof) or any(np.isnan(v) for v in prof["w"].values()):
            # 못 재면 합격으로 두지 않는다(nan 비교는 거짓이라 그대로 두면 판정을 조용히 통과한다)
            if view == "three_quarter":
                fails.append("3/4 얼굴 윤곽을 못 쟀다 — 얼굴 비교 이미지로 직접 확인하고 사용자에게 알린다")
            else:
                notes.append(f"{view}: 얼굴 윤곽을 못 쟀다 — 얼굴 비교 이미지로 본다")
            continue
        cells = "  ".join(f"{k}% {prof['w'][k]:.3f}" for k in (50, 75, 90))
        if view == "three_quarter":
            d75 = prof["w"][75] / ref_prof["w"][75] - 1
            print(f"얼굴 폭/L (눈~턱 위치) 3/4 {cells}  — 기준 " + "  ".join(f"{k}% {ref_prof['w'][k]:.3f}" for k in (50, 75, 90))
                  + f"  아래 볼(75%) {d75 * 100:+.0f}%")
            if d75 > CHEEK_INVALID:
                # 피부와 머리카락 색이 같으면(Priest: 흰 피부·백금발, 둘 다 h≈20°·s≈0.2) 머리카락까지 얼굴로 잡혀 폭이 머리 전체가 된다.
                # 진짜 볼 불합격은 +13%(Knight 4차)였다 — 이만큼 크면 측정 실패로 보고 눈으로 판정한다
                notes.append(f"3/4 얼굴 폭 {d75 * 100:+.0f}% — 피부와 머리카락을 색으로 못 갈랐다(측정 무효). 얼굴 비교 이미지의 노랑 윤곽으로 직접 본다")
            elif d75 > CHEEK_TOL:
                fails.append(f"아래 볼 {d75 * 100:+.0f}% — 기준보다 볼이 빵빵하다(U자 턱선). 얼굴 비교 이미지의 노랑 윤곽 밖으로 나간다")
        else:
            print(f"얼굴 폭/L 앞 {cells}  (기준이 3/4라 참고)")

    out = Image.new("RGB", (sum(t.width for t in tiles), max(t.height for t in tiles)), "white")
    x = 0
    for t in tiles:
        out.paste(t.convert("RGB"), (x, 0))
        x += t.width
    path = os.path.join(C.PREVIEW_DIR, "_deform_overlay.png")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    out.save(path)
    vs = compare_with_reference(spec, figs, os.path.join(C.PREVIEW_DIR, "_deform_vs_reference.png"))
    face = face_layout_image(spec, figs, mfigs, os.path.join(C.PREVIEW_DIR, "_deform_face.png"))
    if face:
        print(f"얼굴 레이아웃(빨강 = 마네킹 두개골·턱, 초록 = 기준 캐릭터 눈 높이, 파랑 = 턱, 맨 왼쪽 = 기준 캐릭터와 자기 마네킹): {slash(face)}")
    for n in notes:
        print("  [참고]", n)
    print(f"기준 캐릭터와 나란히(턱~발바닥 동일, 회색 = 1/4·1/2·3/4): {slash(vs)} — 다리 시작 높이·실루엣 폭을 비교한다")
    print("판정:", "합격" if not fails else "불합격 — " + "; ".join(fails))
    print("머리 크기·몸이 마네킹을 따라가는지·디자인이 원화와 같은지는 비교 이미지와 결과를 눈으로 본다")
    done(True, 0 if not fails else 4, **{"pass": not fails, "fails": fails, "notes": notes, "overlay": slash(path)})




def cmd_accept(args):
    folder = os.path.join(C.SHEET_ROOT, args.character, "design")
    os.makedirs(folder, exist_ok=True)
    meta_path = os.path.join(os.path.dirname(args.image), "meta.json")
    dst = os.path.join(folder, f"{args.character}_turnaround.png")
    shutil.copy(args.image, dst)
    out = {"turnaround": slash(dst)}
    if os.path.exists(meta_path):
        with open(meta_path, encoding="utf-8") as fp:
            meta = json.load(fp)
        src = meta.get("source")
        char_dir = os.path.normcase(os.path.normpath(os.path.join(C.SHEET_ROOT, args.character)))
        if src and os.path.normcase(os.path.normpath(src)).startswith(char_dir):
            out["source"] = slash(src)  # 원화가 이미 캐릭터 폴더에 있으면 사본을 만들지 않는다
        elif src and os.path.exists(src):
            sdst = os.path.join(folder, f"{args.character}_source{os.path.splitext(src)[1].lower()}")
            shutil.copy(src, sdst)
            out["source"] = slash(sdst)
        with open(os.path.join(folder, f"{args.character}_turnaround.json"), "w", encoding="utf-8") as fp:
            json.dump(meta | {"accepted_from": slash(args.image)}, fp, ensure_ascii=False, indent=2)
    done(True, 0, **out)


def character_config(character):
    path = os.path.join(C.SHEET_ROOT, character, f"{character}.character.json")
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as fp:
        return json.load(fp)


def cmd_init(args):
    """
    [관문 1: 설정 입력] 새 캐릭터의 {캐릭터}.character.json. 생성 전에 사용자에게 받은 값으로 만든다.
    이후 단계(generate·lineup·idle_base·set-height·generate_action·파이프라인)가 읽는다.
    ref_height·reference는 set-height·set-reference가 쓴다(그 전에 시트를 처리하면 파이프라인이 멈춘다).
    skull_over_L(두개골/턱~발바닥)은 기준 캐릭터 값 × 체형 힌트의 머리 배율로 추정한다 — Knight는 마네킹을 겹쳐 손으로 쟀다(0.304).
    추정이 틀리면 게임 내 키가 2~3%쯤 어긋난다. 비교샷(lineup)의 파랑 정수리선으로 확인한다.
    """
    path = os.path.join(C.SHEET_ROOT, args.character, f"{args.character}.character.json")
    if os.path.exists(path):
        done(False, 1, error=f"{args.character}.character.json이 이미 있다 — 바꿀 값은 파일을 직접 고친다")
    spec = mannequin_spec()
    ref_char = reference_name(spec).split("_")[0]
    with open(os.path.join(C.SHEET_ROOT, ref_char, f"{ref_char}.character.json"), encoding="utf-8") as fp:
        ref_skull = json.load(fp)["skull_over_L"]
    if args.skull_over_l:
        skull, note = args.skull_over_l, "사용자/측정 지정"
    else:
        skull = round(ref_skull * HINTS[args.hint]["head"], 3)
        note = f"추정: {ref_char} {ref_skull} × hint {args.hint} 머리 배율 {HINTS[args.hint]['head']} (deform.py init)"
    cfg = {"height_cm": args.height_cm, "hint": args.hint, "profile": args.profile or "",
           "skull_over_L": skull, "skull_note": note,
           "design": {"required": args.required, "props_reference": None, "note": "deform.py init — 사용자 입력"},
           "align_x": {},
           "actions": {}}
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fp:
        json.dump(cfg, fp, ensure_ascii=False, indent=2)
    print(f"{args.character}.character.json 생성: 키 {args.height_cm}cm, 힌트 {args.hint}, skull_over_L {skull} ({note})")
    if not args.required:
        print("  [주의] design.required가 비었다 — 원화에서 꼭 있어야 할 요소를 사용자에게 묻고 적는다")
    done(True, 0, config=slash(path))


LINEUP_H = 600  # 가장 큰 캐릭터의 정수리~발바닥(px)


def lineup_figure(character, cfg):
    """
    기존 캐릭터를 비교샷에 세울 그림: 턴어라운드 3/4 → design/*_apose.png → 기준 시트 0번 프레임 순.
    A포즈끼리 세워야 자세 차이가 키 차이로 보이지 않는다.
    """
    d = os.path.join(C.SHEET_ROOT, character, "design")
    tp = os.path.join(d, f"{character}_turnaround.png")
    if os.path.exists(tp):
        return M.figures(tp, len(M.VIEWS))[1], "turnaround 3/4"
    ap = os.path.join(d, f"{character}_apose.png")
    if os.path.exists(ap):
        frames, _ = C.load_frames(ap)
        return frames[0]["image"], "A-pose"
    if cfg.get("reference"):
        frames, _ = C.load_frames(os.path.join(C.SHEET_ROOT, character, cfg["reference"] + ".png"))
        return C.crop_frame(frames[0]["image"]), cfg["reference"]
    return None, None


def cmd_lineup(args):
    """
    [관문 2: 비교샷] 새 캐릭터와 기존 캐릭터를 설정 키 비율대로 같은 바닥선에 세운다.
    키 차이는 비율이 아니라 실제 크기로 보여 준다(사용자 지정 2026-10-14).
    크기는 정수리(머리카락 제외)~발바닥으로 맞춘다 — sheet_check.py set-height와 같은 잣대라 게임 안 크기와 같다.
    """
    import sheet_check as SC
    me = character_config(args.character)
    if me is None:
        done(False, 1, error=f"{args.character}.character.json이 없다 — init을 먼저 한다")
    figs = M.figures(args.image, len(M.VIEWS))
    if len(figs) != len(M.VIEWS):
        done(False, 1, error=f"인물 {len(figs)}명 — 턴어라운드(4명)가 아니다")
    others = args.with_ or sorted(n for n in os.listdir(C.SHEET_ROOT)
                                  if n != args.character and os.path.exists(os.path.join(C.SHEET_ROOT, n, f"{n}.character.json")))
    entries = [(args.character, figs[1], "turnaround 3/4", me)]
    for n in others:
        cfg = character_config(n) or {}
        if not cfg.get("height_cm") or not cfg.get("skull_over_L"):
            print(f"  [건너뜀] {n}: height_cm·skull_over_L이 없다")
            continue
        fig, kind = lineup_figure(n, cfg)
        if fig is None:
            print(f"  [건너뜀] {n}: 세울 그림이 없다")
            continue
        entries.append((n, fig, kind, cfg))
    tallest = max(e[3]["height_cm"] for e in entries)
    tiles = []
    for name, fig, kind, cfg in entries:
        # 크기는 다리를 편 키로 보정한 값(set-height와 같음)으로, 정수리선은 그림 속 실제 두개골 꼭대기에 긋는다
        h, _ = SC.skull_height(fig, cfg["skull_over_L"])
        target = LINEUP_H * cfg["height_cm"] / tallest
        s = target / h
        f = fig.resize((max(1, round(fig.width * s)), max(1, round(fig.height * s))), Image.LANCZOS)
        chin = face_chin(fig)
        skull_px = (fig.height - 1 - chin) * (1 + cfg["skull_over_L"]) * s
        tiles.append((name, kind, cfg["height_cm"], f, skull_px))
        print(f"{name:10} {cfg['height_cm']}cm  {kind:16} 정수리~발 {h:.0f}px → {target:.0f}px")
    pad, floor_gap = 40, 30
    H = max(t[3].height for t in tiles) + 80
    W = sum(t[3].width for t in tiles) + pad * (len(tiles) + 1)
    out = Image.new("RGBA", (W, H), (255, 255, 255, 255))
    d = ImageDraw.Draw(out)
    floor = H - floor_gap
    for k in range(10, tallest + 1, 10):  # 10cm 눈금
        y = floor - LINEUP_H * k / tallest
        d.line([(0, y), (W, y)], fill=(235, 235, 235))
    x = pad
    for name, kind, cm, f, skull_px in tiles:
        out.alpha_composite(f, (x, floor - f.height))
        top = floor - skull_px
        d.line([(x - 10, top), (x + f.width + 10, top)], fill=(0, 120, 230), width=2)
        d.text((x, 6), f"{name} {cm}cm" + ("  NEW" if name == args.character else ""), fill=(0, 0, 0))
        d.text((x, 20), kind, fill=(110, 110, 110))
        x += f.width + pad
    d.line([(0, floor), (W, floor)], fill=(200, 0, 0), width=2)
    path = os.path.join(C.PREVIEW_DIR, f"_lineup_{args.character}.png")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    out.convert("RGB").save(path)
    print("파랑 = 정수리(머리카락 제외), 빨강 = 바닥, 회색 = 10cm. 새 캐릭터 정수리선이 실제 두개골 꼭대기에 오는지 본다(skull_over_L 추정)")
    print(f"비교샷: {slash(path)} — 사용자에게 보여 주고 확정받은 뒤 accept")
    done(True, 0, lineup=slash(path), characters=[t[0] for t in tiles])


def main():
    C.utf8_stdout()
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    i = sub.add_parser("init")
    i.add_argument("--character", required=True, help="캐릭터 이름 (영문, 대문자 시작)")
    i.add_argument("--height-cm", type=int, required=True, help="설정 키(cm). 예: Archer 160, Knight 170")
    i.add_argument("--hint", choices=list(HINTS), required=True)
    i.add_argument("--required", action="append", default=[], help="필수 디자인 요소 (영어 짧은 문장, 여러 번)")
    i.add_argument("--profile", help="체격·성격·무기와 쥐는 손 (사람이 읽는 메모 — Idle 움직임·동작 디렉팅의 근거)")
    i.add_argument("--skull-over-l", type=float, help="두개골/턱~발바닥. 생략하면 기준 캐릭터 값 × 힌트로 추정")
    g = sub.add_parser("generate")
    g.add_argument("--character", required=True, help="캐릭터 이름 (영문, 대문자 시작)")
    g.add_argument("--source", required=True, help="사용자가 준 HD 원화")
    g.add_argument("--hint", choices=list(HINTS), help="생략하면 character.json의 hint")
    g.add_argument("--design-note", help="원화에서 꼭 지킬 디자인 요소 (영어). 생략하면 character.json의 design.required")
    g.add_argument("--previous", action="append", default=[])
    g.add_argument("--previous-note", action="append", default=[])
    g.add_argument("--fix", action="append", default=[], help="고칠 점 (영어, 측정값 포함)")
    g.add_argument("--limit", type=float, default=85)
    g.add_argument("--timeout", type=int, default=900)
    g.add_argument("--dry-run", action="store_true")
    v = sub.add_parser("verify")
    v.add_argument("image")
    v.add_argument("--hint", choices=list(HINTS), default="normal")
    ln = sub.add_parser("lineup")
    ln.add_argument("image", help="턴어라운드 결과 (accept 전)")
    ln.add_argument("--character", required=True)
    ln.add_argument("--with", dest="with_", nargs="+", help="비교할 캐릭터 (기본: 설정이 있는 다른 캐릭터 전부)")
    a = sub.add_parser("accept")
    a.add_argument("image")
    a.add_argument("--character", required=True)
    args = p.parse_args()
    {"init": cmd_init, "generate": cmd_generate, "verify": cmd_verify, "lineup": cmd_lineup,
     "accept": cmd_accept}[args.cmd](args)


if __name__ == "__main__":
    main()
