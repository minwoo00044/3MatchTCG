"""
반자동 Idle: AI가 그린 한 장을 몸으로 고정하고 숨쉬기는 코드로, 눈 깜빡임은 같은 몸으로 그려진 AI 프레임의 눈만 잘라 붙인다.

    python procedural_idle.py --input RAW_4x2.png --base 0 --blink 2 --out SpriteRegen/Knight_Idle/proc5/result.png
    → 6x4(24장) 원본 시트. 이어서: process_sprite_sheet.py --input OUT --name X --cols 6 --rows 4 --inbetween 0 --fps 24

왜: AI는 Idle 8장을 매번 새로 그려서 얼굴(눈·눈썹·시선)과 세부가 프레임마다 바뀌고, 부위가 따로 움직인다.
보간하면 그 차이가 녹아내리듯 이어져 'AI가 만든 듯한' 움직임이 된다(Knight Idle, 사용자 지적 2026-10-14).
한 장을 고정하면 얼굴이 절대 변하지 않고, 움직임은 물리적으로 일관된다(상체 한 덩어리, 무릎 아래로 갈수록 줄어듦, 발 고정).
큰 동작(Hit·Skill·Dead)에는 쓰지 않는다.

기본값 = Knight_Idle_v10 (사용자: "딱 좋다", 2026-10-14): 무릎 굽힘(엉덩이 키의 2% 하강, 무릎은 0.55배 하강 + 앞으로 0.35배)
+ 호흡(가슴·어깨 키의 0.4%, 머리 2프레임 지연) + 줄마다 정수 px 이동. 거쳐 온 것:
  bob(상체 통째 2.2%) → 스프링 인형 / chest 0.9% → 무릎 없이는 너무 큼 / chest 0.4% → 만족, 무릎을 더한 knee가 최종.
"""
import argparse
import json
import math
import os
import sys

import numpy as np
from PIL import Image, ImageFilter

sys.path.insert(0, os.path.dirname(__file__))
import common as C  # noqa: E402
import deform as D  # noqa: E402

P = C.P
FRAMES = 24
COLS, ROWS = 6, 4


def eye_patch(base, blink):
    """두 프레임(같은 몸) 사이 얼굴에서 달라진 곳 = 눈. 부드러운 가장자리 마스크로 blink 쪽 눈을 base에 합친다."""
    chin = D.face_chin(base)
    H = base.height
    a, b = np.asarray(base).astype(int), np.asarray(blink).astype(int)
    diff = np.abs(a - b)[:, :, :3].sum(2) > 80
    sk = D.skin_mask(base)
    y0 = int(chin - 0.12 * H)
    y1 = int(chin - 0.035 * H)          # 입은 빼고 눈 높이까지만
    cols = np.where(sk[y0:chin].any(0))[0]
    box = np.zeros_like(diff)
    box[y0:y1, cols.min():cols.max() + 1] = True
    m = diff & box
    ys, xs = np.where(m)
    if not len(ys):
        raise SystemExit("두 프레임의 눈이 다르지 않다 — --blink 프레임을 확인한다")
    rect = np.zeros(diff.shape, np.uint8)
    pad = max(3, H // 120)
    rect[max(0, ys.min() - pad):ys.max() + pad, max(0, xs.min() - pad):xs.max() + pad] = 255
    mask = Image.fromarray(rect).filter(ImageFilter.GaussianBlur(pad))
    return Image.composite(blink, base, mask), (int(ys.min()), int(ys.max()), int(xs.min()), int(xs.max()))


FACE_SHIFT = 8  # 얼굴 정렬 탐색 폭(px)


def align_face(base, blink):
    """
    blink 프레임을 base와 같은 캔버스에 놓고, 얼굴(턱 위 머리 부분)이 가장 잘 겹치는 이동량으로 맞춘다.
    AI가 몸을 픽셀까지 같게 그리면(Knight Idle try2) 이동 0이다. Priest Idle try1은 장마다 1~2px씩 달라
    '위치·크기가 같아야 한다'는 조건으로는 쓸 짝이 없었다(2026-10-16). 반환: (base 크기의 blink 이미지, (dx, dy))
    """
    chin = D.face_chin(base)
    H = base.height
    y0, y1 = max(0, int(chin - 0.18 * H)), chin
    a = np.asarray(base).astype(np.float32)
    best = (1e18, 0, 0)
    for dy in range(-FACE_SHIFT, FACE_SHIFT + 1):
        for dx in range(-FACE_SHIFT, FACE_SHIFT + 1):
            c = Image.new("RGBA", base.size)
            c.paste(blink, (dx, dy + base.height - blink.height))
            b = np.asarray(c).astype(np.float32)
            d = float(np.abs(a[y0:y1] - b[y0:y1]).mean())
            if d < best[0]:
                best = (d, dx, dy)
    _, dx, dy = best
    out = Image.new("RGBA", base.size)
    out.paste(blink, (dx, dy + base.height - blink.height))
    return out, (dx, dy)


def breathe(img, s, hip_frac):
    """윗부분을 s px 아래로. 엉덩이(hip_frac)부터 발바닥까지 1→0으로 줄여 다리가 살짝 굽는 것처럼 — 발은 그대로."""
    a = np.asarray(img)[:, :, 3] > 128
    rows = np.where(a.any(1))[0]
    top, bot = rows.min(), rows.max()
    hip = top + hip_frac * (bot - top)
    ys = np.arange(img.height, dtype=np.float32)
    w = np.clip((bot - ys) / max(1.0, bot - hip), 0, 1)
    return P.warp_xy(img, np.zeros_like(w), w * s)


def breathe_chest(img, b_chest, b_head, waist_frac, shoulder_frac, neck_row):
    """
    실제 숨쉬기: 허리 아래(다리·엉덩이)는 고정, 허리→어깨 사이가 늘어나 어깨가 b_chest px 올라가고,
    목 위(머리)는 b_head만큼 올라간다(머리는 어깨보다 조금 늦게 따라오도록 위상을 다르게 준다).
    통째로 위아래로 움직이면 스프링 인형처럼 보였다(사용자 지적 2026-10-14, Knight Idle v6).
    """
    a = np.asarray(img)[:, :, 3] > 128
    rows = np.where(a.any(1))[0]
    top, bot = rows.min(), rows.max()
    Hh = bot - top
    waist, shoulder = top + waist_frac * Hh, top + shoulder_frac * Hh
    ys = np.arange(img.height, dtype=np.float32)
    up = np.where(ys >= waist, 0.0, np.clip((waist - ys) / max(1.0, waist - shoulder), 0, 1) * b_chest)
    # 목 위는 머리 값으로, 어깨~목 사이에서 섞는다
    t = np.clip((shoulder - ys) / max(1.0, shoulder - neck_row), 0, 1)
    up = np.where(ys < shoulder, (1 - t) * b_chest + t * b_head, up)
    # 줄마다 정수 px로 옮긴다: 소수 이동은 쌍선형 보간으로 흐려져 프레임마다 선명도가 오르내렸다(13%, 작은 숨쉬기에서 반짝임)
    return P.warp_xy(img, np.zeros_like(ys), -np.round(up))


def breathe_body(img, amp, phase, head_phase, shoulder_frac, neck_row, swell, knee_dx=None, knee_dy=None, ref=None):
    """
    몸 전체 숨쉬기: 경계선 없이 발목(0)→어깨(1)로 서서히 들리고(smoothstep), 머리는 head_phase로 따로(지연) 따라온다.
    가슴 높이에서는 몸통이 좌우로 swell(가로 비율, 숨 끝에서)만큼 부푼다 — 가운데에서 멀수록 더 밀린다.
    chest 모드는 허리 위 가로 띠를 통째로 밀어 "가슴만 사진으로 잘라 움직이는 것 같다"(사용자, Priest Idle v1, 2026-10-16).
    amp = 어깨가 오르는 최대 px, phase·head_phase = 0~1. 픽셀은 가장 가까운 원본 픽셀을 가져온다(소수 보간은 선명도가 오르내렸다).
    knee_dx·knee_dy(줄마다, knee_bend 반환값)를 주면 무릎 굽힘을 같은 워프에 더한다 — kneebody 모드.
    ref: 높이·가운데를 잴 그림(기본 img). 손 층처럼 일부만 있는 층을 몸과 똑같이 움직이려면 몸 그림을 넘긴다.
    """
    a = np.asarray(img)
    alpha = np.asarray(ref if ref is not None else img)[:, :, 3] > 128
    rows = np.where(alpha.any(1))[0]
    cols = np.where(alpha.any(0))[0]
    top, bot = rows.min(), rows.max()
    Hh = bot - top
    shoulder = top + shoulder_frac * Hh
    ankle = top + 0.93 * Hh
    ys = np.arange(img.height, dtype=np.float32)
    t = np.clip((ankle - ys) / max(1.0, ankle - shoulder), 0, 1)
    up = t * t * (3 - 2 * t) * amp * phase
    h = np.clip((shoulder - ys) / max(1.0, shoulder - neck_row), 0, 1)
    up = np.where(ys < shoulder, (1 - h) * amp * phase + h * amp * head_phase, up)
    chest_y = shoulder + 0.12 * Hh  # 가슴 높이. 종 모양으로 머리·다리는 부풀지 않는다
    bell = np.exp(-((ys - chest_y) / (0.10 * Hh)) ** 2)
    cx = (cols.min() + cols.max()) / 2
    yy, xx = np.mgrid[0:img.height, 0:img.width].astype(np.float32)
    k = swell * phase * bell[:, None]
    kdx = np.zeros_like(ys) if knee_dx is None else knee_dx
    kdy = np.zeros_like(ys) if knee_dy is None else knee_dy
    sx = np.round(xx - (xx - cx) * k - kdx[:, None]).astype(int)
    sy = np.round(yy + up[:, None] - kdy[:, None]).astype(int)
    ok = (sx >= 0) & (sx < img.width) & (sy >= 0) & (sy < img.height)
    out = np.zeros_like(a)
    out[ok] = a[sy[ok], sx[ok]]
    return Image.fromarray(out)


KNEE_RATIO = 0.55      # 무릎이 엉덩이를 따라 내려가는 비율 (Archer Idle 측정값)
KNEE_FORWARD = 0.35    # 무릎이 앞으로 나오는 양 (엉덩이 하강량 대비)


def knee_bend(img, s, hip_frac, knee_frac, ankle_frac, forward_sign, ratio=KNEE_RATIO, forward=KNEE_FORWARD):  # noqa: E501 — 반환은 줄마다라 손 층에도 그대로 쓴다
    """
    무릎을 굽혀 몸이 s px 내려간다: 엉덩이 위는 s, 무릎은 KNEE_RATIO*s만큼 내려가며 앞으로 나오고, 발목 아래는 고정.
    다리를 위아래로만 누르면 스프링 인형처럼 보였다(v6) — 무릎이 앞으로 나와야 굽힌 다리로 읽힌다.
    반환은 줄마다 (dx, dy) — 상체 호흡과 더해 한 번에 워프한다.
    """
    a = np.asarray(img)[:, :, 3] > 128
    rows = np.where(a.any(1))[0]
    top, bot = rows.min(), rows.max()
    Hh = bot - top
    hip, knee, ankle = (top + f * Hh for f in (hip_frac, knee_frac, ankle_frac))
    ys = np.arange(img.height, dtype=np.float32)
    k = ratio * s
    dy = np.interp(ys, [hip, knee, ankle], [s, k, 0.0])
    dx = np.interp(ys, [hip, knee, ankle], [0.0, forward_sign * forward * s, 0.0])
    return dx, dy


def breathe_rows(img, b_chest, b_head, waist_frac, shoulder_frac, neck_row):
    """breathe_chest의 줄별 위쪽 이동량(px, 위로 +)만 돌려준다."""
    a = np.asarray(img)[:, :, 3] > 128
    rows = np.where(a.any(1))[0]
    top, bot = rows.min(), rows.max()
    Hh = bot - top
    waist, shoulder = top + waist_frac * Hh, top + shoulder_frac * Hh
    ys = np.arange(img.height, dtype=np.float32)
    up = np.where(ys >= waist, 0.0, np.clip((waist - ys) / max(1.0, waist - shoulder), 0, 1) * b_chest)
    t = np.clip((shoulder - ys) / max(1.0, shoulder - neck_row), 0, 1)
    return np.where(ys < shoulder, (1 - t) * b_chest + t * b_head, up)


def main():
    C.utf8_stdout()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--character", help="{캐릭터}.character.json의 idle 설정을 기본값으로 쓴다 (명시한 인자가 우선)")
    ap.add_argument("--input", help="같은 몸으로 그려진 프레임이 있는 원본 4x2 시트")
    ap.add_argument("--base", type=int, default=None, help="몸으로 쓸 프레임 (기본 0)")
    ap.add_argument("--blink", type=int, default=None, help="눈을 감은 프레임 (base와 같은 위치·크기)")
    ap.add_argument("--mode", choices=["chest", "knee", "body", "kneebody", "bob"], default="knee",
                    help="chest: 다리 고정, 가슴·어깨가 오르내림(기본). bob: 상체 통째로 위아래(스프링 인형처럼 보였다)")
    ap.add_argument("--amp", type=float, default=None, help="폭 (키 대비). 기본 chest 0.009, bob 0.022")
    ap.add_argument("--body-image", help="소품을 지운 몸 (base 프레임과 같은 크기). --static-layer와 같이 쓴다")
    ap.add_argument("--static-layer", help="움직이지 않는 소품 층 (base 프레임과 같은 크기). 몸 앞에 깐다")
    ap.add_argument("--hand-layer", help="소품을 쥔 손 층 (base 프레임과 같은 크기). 소품 앞에, 몸과 같은 워프로 (kneebody만)")
    ap.add_argument("--swell", type=float, default=0.012, help="body: 숨 끝에서 가슴 높이 몸통이 좌우로 부푸는 비율")
    ap.add_argument("--knee-ratio", type=float, default=None, help="knee: 무릎 하강 / 엉덩이 하강 (기본 0.55)")
    ap.add_argument("--knee-forward", type=float, default=None, help="knee: 무릎 앞으로 / 엉덩이 하강 (기본 0.35)")
    ap.add_argument("--knee-amp", type=float, default=0.02, help="knee: 엉덩이가 내려가는 폭 (키 대비). Archer 약 0.023")
    ap.add_argument("--face", choices=["right", "left"], default="right", help="knee: 캐릭터가 보는 쪽 (무릎이 나오는 방향)")
    ap.add_argument("--head-lag", type=int, default=2, help="머리가 어깨보다 늦는 프레임 수 (chest)")
    ap.add_argument("--hip", type=float, default=0.55, help="이 높이(위에서부터 키 대비) 위는 한 덩어리로 움직인다")
    ap.add_argument("--blink-at", type=int, nargs="+", default=[15, 16], help="눈 감은 출력 프레임 번호")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    # 캐릭터마다 Idle에서 움직일 부분·폭이 다르다 — character.json "idle"에 기록하고 여기서 읽는다(사용자 지시 2026-10-14)
    if args.character:
        D.use_skin(args.character)
        cfg_path = os.path.join(C.SHEET_ROOT, args.character, f"{args.character}.character.json")
        with open(cfg_path, encoding="utf-8") as fp:
            idle = json.load(fp).get("idle", {})
        if idle.get("method") != "procedural":
            raise SystemExit(f"{args.character}의 idle.method가 procedural이 아니다 ({idle.get('method')})")
        defaults = {"input": idle.get("source"), "base": idle.get("base"), "blink": idle.get("blink"), "mode": idle.get("mode"),
                    "amp": idle.get("breath_amp"), "knee_amp": idle.get("knee_amp"), "knee_ratio": idle.get("knee_ratio"),
                    "knee_forward": idle.get("knee_forward"), "face": idle.get("face"), "head_lag": idle.get("head_lag"),
                    "hip": idle.get("hip"), "blink_at": idle.get("blink_at"), "swell": idle.get("swell"), "body_image": idle.get("body_image"), "static_layer": idle.get("static_layer"), "hand_layer": idle.get("hand_layer")}
        explicit = {a[2:].replace("-", "_") for a in sys.argv[1:] if a.startswith("--")}
        for k, v in defaults.items():
            if v is not None and k not in explicit:
                setattr(args, k, v)
    if args.input is None or args.blink is None:
        ap.error("--input, --blink가 필요하다 (또는 --character로 idle 설정에서)")
    args.base = args.base or 0
    args.knee_ratio = KNEE_RATIO if args.knee_ratio is None else args.knee_ratio
    args.knee_forward = KNEE_FORWARD if args.knee_forward is None else args.knee_forward

    rgba = np.array(Image.open(args.input).convert("RGBA"))
    frames, _, _ = P.extract_frames(rgba, 4, 2, 8, None, True)
    base, blink_src = frames[args.base], frames[args.blink]
    body = base["image"]
    static = hand = None
    if args.static_layer:
        # 땅에 짚은 단단한 소품(지팡이)은 몸과 함께 비틀면 휘고 늘어난다(Priest, 2026-10-16) —
        # 소품을 지운 몸(--body-image)만 숨쉬게 하고, 소품 층은 고정해 몸 뒤에 깐다. 둘 다 base 프레임과 같은 크기·좌표
        body = Image.open(args.body_image).convert("RGBA")
        static = Image.open(args.static_layer).convert("RGBA")
        hand = Image.open(args.hand_layer).convert("RGBA") if args.hand_layer else None
        if body.size != base["image"].size or static.size != base["image"].size:
            raise SystemExit(f"--body-image·--static-layer는 base 프레임과 같은 크기여야 한다 {base['image'].size}")
    blink_img, shift = align_face(body, blink_src["image"])
    blink, eye_box = eye_patch(body, blink_img)
    if shift != (0, 0):
        print(f"  blink 프레임을 얼굴 기준으로 {shift} px 옮겨 맞췄다")

    H = body.height
    amp = (args.amp if args.amp is not None else (0.004 if args.mode in ("chest", "knee", "body", "kneebody") else 0.022)) * H
    neck = D.face_chin(body)
    rows = np.where((np.asarray(body)[:, :, 3] > 128).any(1))[0]
    shoulder_frac = (neck + 0.04 * H - rows.min()) / (rows.max() - rows.min())
    cw, ch = body.width + 60, H + 60 + int(amp) + 10
    sheet = Image.new("RGBA", (cw * COLS, ch * ROWS))
    path = []
    for i in range(FRAMES):
        s = amp * (1 - math.cos(2 * math.pi * i / FRAMES)) / 2
        src = blink if i in args.blink_at else body
        if args.mode == "knee":
            sh = amp * (1 - math.cos(2 * math.pi * (i - args.head_lag) / FRAMES)) / 2
            up = breathe_rows(src, s, sh, args.hip - 0.10, shoulder_frac, neck)
            kd = args.knee_amp * H * (1 - math.cos(2 * math.pi * i / FRAMES)) / 2
            dx, dy = knee_bend(src, kd, args.hip, 0.76, 0.93, 1 if args.face == "right" else -1, args.knee_ratio, args.knee_forward)
            img = P.warp_xy(src, np.round(dx), np.round(dy - up))
        elif args.mode == "body":
            ph = (1 - math.cos(2 * math.pi * i / FRAMES)) / 2
            hph = (1 - math.cos(2 * math.pi * (i - args.head_lag) / FRAMES)) / 2
            img = breathe_body(src, amp, ph, hph, shoulder_frac, neck, args.swell)
        elif args.mode == "kneebody":
            # 무릎 굽힘 + 경계 없는 몸 전체 호흡. B(knee)는 상체 호흡이 허리선에서 끊겨 '오려낸' 느낌이었다(Priest, 2026-10-16)
            ph = (1 - math.cos(2 * math.pi * i / FRAMES)) / 2
            hph = (1 - math.cos(2 * math.pi * (i - args.head_lag) / FRAMES)) / 2
            kd = args.knee_amp * H * ph
            dx, dy = knee_bend(src, kd, args.hip, 0.76, 0.93, 1 if args.face == "right" else -1, args.knee_ratio, args.knee_forward)
            img = breathe_body(src, amp, ph, hph, shoulder_frac, neck, args.swell, dx, dy)
            if hand is not None:
                hand_img = breathe_body(hand, amp, ph, hph, shoulder_frac, neck, args.swell, dx, dy, ref=src)
        elif args.mode == "chest":
            sh = amp * (1 - math.cos(2 * math.pi * (i - args.head_lag) / FRAMES)) / 2
            img = breathe_chest(src, s, sh, args.hip - 0.10, shoulder_frac, neck)
        else:
            img = breathe(src, s, args.hip)
        if static is not None:
            # 원래 그림의 앞뒤 순서: 몸(맨 뒤) → 땅에 고정한 소품 → 소품을 쥔 손(맨 앞, 몸과 같은 워프)
            layer = img.copy()
            layer.alpha_composite(static)
            if hand is not None:
                layer.alpha_composite(hand_img)
            img = layer
        sheet.paste(img, ((i % COLS) * cw + 30, (i // COLS) * ch + ch - 20 - H))
        path.append(round(s, 2))
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    sheet.save(args.out)
    meta = {"mode": args.mode, "input": args.input, "base": args.base, "blink": args.blink, "eye_box": eye_box, "amp_px": round(amp, 1),
            "hip": args.hip, "blink_at": args.blink_at, "path": path}
    with open(os.path.splitext(args.out)[0] + ".json", "w", encoding="utf-8") as fp:
        json.dump(meta, fp, ensure_ascii=False, indent=2)
    print(f"RESULT {json.dumps({'ok': True, 'sheet': args.out, **meta}, ensure_ascii=False)}")


if __name__ == "__main__":
    main()
