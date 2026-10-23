"""
빠르게 도는 소품을 '원반(blur disc, smear)'으로 그리고, 원본 프레임 목록을 레시피로 조립한다.

    python smear.py assemble <recipe.json>        → 프레임 png들 + splice_frames 인자(RESULT.splice)
    python smear.py disc <몸.png> <out.png> --cx X --cy Y --rx RX --ry RY [--phase k] [--arc 180] [--alpha 0.85]

배경 (Priest Skill2, 2026-10-19): 지팡이를 각도별로 그리게 하니 부정확했고, 사용자가 "돌리지 말고 원반으로"를 제안.
조사(Wesnoth motion blur, smear frame): 도는 동안 소품은 그리지 않고 쓸고 지나가는 영역을 타원 원반으로 그린다.
  - 원반의 모양·크기·위치는 모든 장에서 같다. 안쪽 줄무늬·반짝임만 위상에 따라 돈다 (원반이 흔들리면 다시 '각도별 소품'처럼 보인다)
  - 손은 원반 중심에 고정 (사용자 결정). 뒤쪽 절반은 몸 뒤, 앞쪽 절반은 몸 앞에 놓아 손이 중심을 잡고 있게 보인다
  - 들어갈 때·나올 때는 반원(arc 180) 1장씩
원반 크기·색은 레시피 "disc"에서 바꾼다 (v3 피드백: 원반이 작고 너무 하얗다 — 소품은 흰 막대만이 아니다).

레시피(JSON, 확정되면 {캐릭터}/source~/{액션}/recipe.json):
  {"inputs": "Assets/_/Spirte/Priest/source~/Skill2",           # 프레임 그림 폴더 (pose_edit accept 결과, 흰 배경)
   "out": "SpriteRegen/Priest_Skill2D",                           # 조립 결과 (git 무시)
   "disc": {"cx": 530, "cy": 488, "rx": 280, "ry": 80, "phases": 3, "fill": [236,238,245], "rim": [222,170,72], "band": [80,150,240]},
   "frames": [{"copy": "lift1.png"},
              {"disc": "spin.png", "arc": 180, "alpha": 0.85},    # smear-in
              {"disc": "spin.png", "loop": 3},                      # 원반 phases장 × loop바퀴
              {"disc": "raise.png", "arc": 180, "alpha": 0.45, "cy": 470, "phase": 1},   # smear-out
              {"ghost": "slam.png", "behind": "raise.png"},          # 내려찍기 잔상(뒤 장의 '앞 장보다 위' 부분만 + 속도선)
              {"burst": "impact.png"},                                # 소품 끝에 빛 터짐
              {"copy": "settle.png"}]}
"""
import argparse
import json
import math
import os
import sys
from collections import deque

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

sys.path.insert(0, os.path.dirname(__file__))
import common as C  # noqa: E402

DEFAULT_DISC = {"phases": 3, "fill": [236, 238, 245], "rim": [222, 170, 72], "band": [80, 150, 240],
                "glint": [140, 200, 255], "fill_min": 25, "fill_max": 120,
                "band_w": 14, "band_a": 170, "white_a": 170}  # band_w·band_a: 소품 머리(구슬)가 그리는 바깥 띠, white_a: 안쪽 흰 테


def cut_white(img, thr=240):
    """가장자리에서 이어진 흰 배경만 투명으로 (옷의 흰색은 남긴다)."""
    a = np.asarray(img.convert("RGB")).astype(int)
    white = a.min(axis=2) >= thr
    h, w = white.shape
    bg = np.zeros_like(white)
    q = deque()
    for y, x in [(y, x) for y in (0, h - 1) for x in range(w)] + [(y, x) for x in (0, w - 1) for y in range(h)]:
        if white[y, x] and not bg[y, x]:
            bg[y, x] = True
            q.append((y, x))
    while q:
        y, x = q.popleft()
        for yy, xx in ((y + 1, x), (y - 1, x), (y, x + 1), (y, x - 1)):
            if 0 <= yy < h and 0 <= xx < w and white[yy, xx] and not bg[yy, xx]:
                bg[yy, xx] = True
                q.append((yy, xx))
    return Image.fromarray(np.dstack([a.astype(np.uint8), np.where(bg, 0, 255).astype(np.uint8)]), "RGBA")


def ellipse_pts(cx, cy, rx, ry, t0, t1, n=120, scale=1.0):
    return [(cx + rx * scale * math.cos(t), cy + ry * scale * math.sin(t))
            for t in np.linspace(math.radians(t0), math.radians(t1), n)]


def draw_disc(size, d_, phase, arc, half):
    """half: back(위쪽 반 = 화면에서 먼 쪽) / front(아래쪽 반) / all."""
    S = 2  # 2배로 그려 줄여서 매끄럽게
    W, H = size[0] * S, size[1] * S
    cx, cy, rx, ry = d_["cx"] * S, d_["cy"] * S, d_["rx"] * S, d_["ry"] * S
    fill, rim, band, glint = (tuple(d_[k]) for k in ("fill", "rim", "band", "glint"))
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    # 몸체: 손 가까운 안쪽은 거의 투명, 바깥(소품 끝이 빨리 도는 곳)일수록 진하게
    for k in range(12, 0, -1):
        f = k / 12
        d.ellipse([cx - rx * f, cy - ry * f, cx + rx * f, cy + ry * f],
                  fill=fill + (int(d_["fill_min"] + (d_["fill_max"] - d_["fill_min"]) * f ** 2),))
    # 소품 마디가 그리는 얇은 동심원
    for f, a in ((0.38, 150), (0.58, 170), (0.76, 190)):
        d.ellipse([cx - rx * f, cy - ry * f, cx + rx * f, cy + ry * f], outline=rim + (a,), width=3 * S)
    # 바깥 띠: 소품 머리(구슬·장식)가 그리는 굵은 띠
    d.ellipse([cx - rx, cy - ry, cx + rx, cy + ry], outline=band + (d_.get("band_a", 170),), width=d_.get("band_w", 14) * S)
    d.ellipse([cx - rx, cy - ry, cx + rx, cy + ry], outline=rim + (235,), width=6 * S)
    d.ellipse([cx - rx * 0.9, cy - ry * 0.9, cx + rx * 0.9, cy + ry * 0.9], outline=(255, 248, 225, d_.get("white_a", 170)), width=3 * S)
    # 위상만큼 돌아가는 하이라이트 호 + 반짝임 (모양은 고정, 이것만 돈다)
    off = 360 / d_["phases"] * phase
    for j, (sc, ln, wd, col) in enumerate([(0.95, 80, 6, (255, 255, 255, 235)), (0.68, 60, 4, (255, 255, 255, 200)),
                                           (0.48, 45, 3, rim + (190,))]):
        for rep in (0, 180):
            t0 = off + rep + j * 35
            d.line(ellipse_pts(cx, cy, rx, ry, t0, t0 + ln, scale=sc), fill=col, width=wd * S, joint="curve")
    for ang, r in ((off + 30, 18), (off + 210, 12)):
        gx, gy = ellipse_pts(cx, cy, rx, ry, ang, ang, n=1)[0]
        d.ellipse([gx - r * S, gy - r * 0.55 * S, gx + r * S, gy + r * 0.55 * S], fill=glint + (240,))
    layer = layer.filter(ImageFilter.GaussianBlur(1.2 * S))
    masks = []
    if arc < 360:  # smear-in/out: 반원만
        m = Image.new("L", (W, H), 0)
        ImageDraw.Draw(m).pieslice([cx - rx * 1.1, cy - ry * 1.1, cx + rx * 1.1, cy + ry * 1.1], 180, 180 + arc, fill=255)
        masks.append(m)
    if half != "all":  # 타원 중심선 기준 앞/뒤
        m = Image.new("L", (W, H), 0)
        ImageDraw.Draw(m).rectangle([0, 0, W, cy] if half == "back" else [0, cy, W, H], fill=255)
        masks.append(m)
    for m in masks:
        layer.putalpha(Image.fromarray(np.minimum(np.asarray(layer.split()[3]), np.asarray(m))))
    return layer.resize(size, Image.LANCZOS)


def compose_disc(body_path, out, d_, phase=0, arc=360, alpha=1.0):
    body = C.load_rgba(body_path)
    back = draw_disc(body.size, d_, phase, arc, "back")
    front = draw_disc(body.size, d_, phase, arc, "front")
    if alpha < 1.0:
        for lay in (back, front):
            lay.putalpha(lay.split()[3].point(lambda v: int(v * alpha)))
    c = Image.new("RGBA", body.size, (0, 0, 0, 0))
    c.alpha_composite(back)
    c.alpha_composite(body)
    c.alpha_composite(front)
    c.save(out)  # 투명 그대로 (흰 캔버스에 합성하면 splice가 흰색을 다시 지우며 갇힌 칸이 남았다)


def ghost(front_path, back_path, out, alpha=0.3):
    """멀티플 스미어: 앞 장 뒤에 이전 장의 '앞 장 꼭대기보다 위' 부분만 흐리게 + 이어지는 속도선 (몸까지 겹치면 흰 덩어리, 끊기면 따로 떠 보였다)."""
    f = C.load_rgba(front_path)
    b = C.load_rgba(back_path)
    fa = np.asarray(f.split()[3]) > 128
    cut = int(np.where(fa)[0].min())
    keep = np.zeros(fa.shape, bool)
    keep[:cut] = True
    ba = np.asarray(b.split()[3]).astype(float) * alpha * keep
    b.putalpha(Image.fromarray(ba.astype(np.uint8)))
    ys, xs = np.where(ba > 20)
    if len(xs):
        x0, y0 = float(np.median(xs)), int(ys.max())
        x1 = float(np.where(fa[cut + 5])[0].mean())   # 앞 장 소품 꼭대기 x
        lines = Image.new("RGBA", f.size, (0, 0, 0, 0))
        d = ImageDraw.Draw(lines)
        for dx, a in ((-14, 120), (0, 170), (14, 120)):
            d.line([(x0 + dx, y0 - 120), (x1 + dx, cut + 30)], fill=(255, 250, 235, a), width=4)
        b.alpha_composite(lines.filter(ImageFilter.GaussianBlur(1.5)))
    c = Image.new("RGBA", f.size, (0, 0, 0, 0))
    c.alpha_composite(b.filter(ImageFilter.GaussianBlur(2)))
    c.alpha_composite(f)
    c.save(out)  # 투명 그대로 (흰 캔버스에 합성하면 splice가 흰색을 다시 지우며 갇힌 칸이 남았다)


def prop_foot(path):
    """소품 끝 = 가장 아래 금색 픽셀 중 몸 오른쪽."""
    a = np.asarray(Image.open(path).convert("RGB")).astype(int)
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    ys, xs = np.where((r > 170) & (g > 110) & (b < 120) & (r - b > 80))
    k = np.argmax(np.where(xs > np.median(xs), ys, -1))
    return int(xs[k]), int(ys[k])


def burst(path, out):
    im = C.load_rgba(path)
    x, y = prop_foot(path)
    S = 2
    lay = Image.new("RGBA", (im.width * S, im.height * S), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    cx, cy = x * S, y * S
    for k in range(9):
        t = math.radians(180 + 22.5 * k)          # 위쪽 반원으로 퍼지는 빛줄기
        ln = (90 if k % 2 == 0 else 55) * S
        d.line([(cx, cy), (cx + ln * math.cos(t), cy + ln * 0.6 * math.sin(t))], fill=(255, 230, 150, 230), width=6 * S)
    d.ellipse([cx - 40 * S, cy - 14 * S, cx + 40 * S, cy + 14 * S], fill=(255, 245, 210, 200))
    lay = lay.filter(ImageFilter.GaussianBlur(2 * S)).resize(im.size, Image.LANCZOS)
    c = Image.new("RGBA", im.size, (0, 0, 0, 0))
    c.alpha_composite(im)
    c.alpha_composite(lay)
    c.save(out)  # 투명 그대로 (흰 캔버스에 합성하면 splice가 흰색을 다시 지우며 갇힌 칸이 남았다)


def rel(p):
    return os.path.relpath(p, C.ROOT).replace(os.sep, "/")


def assemble(recipe_path):
    with open(recipe_path, encoding="utf-8") as fp:
        r = json.load(fp)
    src = os.path.join(C.ROOT, r["inputs"])
    out = os.path.join(C.ROOT, r["out"])
    os.makedirs(out, exist_ok=True)
    disc = {**DEFAULT_DISC, **r.get("disc", {})}
    seq = []

    def emit(make):
        dst = os.path.join(out, f"f{len(seq):02d}.png")
        make(dst)
        seq.append(dst)

    for st in r["frames"]:
        if "copy" in st:
            emit(lambda dst, s=st: C.load_rgba(os.path.join(src, s["copy"])).save(dst))
        elif "disc" in st:
            d_ = {**disc, **{k: st[k] for k in ("cx", "cy", "rx", "ry") if k in st}}
            if st.get("arc", 360) < 360:
                emit(lambda dst, s=st, d_=d_: compose_disc(os.path.join(src, s["disc"]), dst, d_, s.get("phase", 0),
                                                           s["arc"], s.get("alpha", 1.0)))
            else:
                for _ in range(st.get("loop", 1)):
                    for ph in range(d_["phases"]):
                        emit(lambda dst, s=st, d_=d_, ph=ph: compose_disc(os.path.join(src, s["disc"]), dst, d_, ph,
                                                                          360, s.get("alpha", 1.0)))
        elif "ghost" in st:
            emit(lambda dst, s=st: ghost(os.path.join(src, s["ghost"]), os.path.join(src, s["behind"]), dst, s.get("alpha", 0.3)))
        elif "burst" in st:
            emit(lambda dst, s=st: burst(os.path.join(src, s["burst"]), dst))
        else:
            sys.exit(f"레시피 단계를 모른다: {st}")
    splice = [f"{rel(p)}:1x1:1" for p in seq]
    print(f"  {len(seq)}장 → {rel(out)}")
    print(f"RESULT {json.dumps({'ok': True, 'frames': len(seq), 'splice': splice}, ensure_ascii=False)}")
    return splice


def main():
    C.utf8_stdout()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("assemble")
    a.add_argument("recipe")
    d = sub.add_parser("disc")
    d.add_argument("body")
    d.add_argument("out")
    for k in ("cx", "cy", "rx", "ry"):
        d.add_argument(f"--{k}", type=float, required=True)
    d.add_argument("--phase", type=int, default=0)
    d.add_argument("--phases", type=int, default=3)
    d.add_argument("--arc", type=float, default=360)
    d.add_argument("--alpha", type=float, default=1.0)
    args = ap.parse_args()
    if args.cmd == "assemble":
        assemble(args.recipe)
    else:
        d_ = {**DEFAULT_DISC, "cx": args.cx, "cy": args.cy, "rx": args.rx, "ry": args.ry, "phases": args.phases}
        compose_disc(args.body, args.out, d_, args.phase, args.arc, args.alpha)


if __name__ == "__main__":
    main()
