"""
여러 원본 시트에서 프레임을 골라 한 장의 원본 시트로 잇는다 — 동작 일부만 다시 그려 바꿀 때.

    python splice_frames.py --out SpriteRegen/Knight_Skill3/splice1.png \
        SpriteRegen/Knight_Skill3/try3/result.png:4x2:1 \
        SpriteRegen/Knight_Skill3/try8/result.png:2x2:1,2,3,4 \
        SpriteRegen/Knight_Skill3/try10/result.png:2x2:1,2,3,4 \
        SpriteRegen/Knight_Skill3/try3/result.png:4x2:5,6,7,8

항목 = 시트:열x행:프레임번호(1부터, 쉼표). 순서대로 한 줄(가로)로 놓는다.
배경이 불투명(흰색)인 시트는 가장자리에 닿은 흰 영역을 투명하게 바꾼 뒤 자른다(Codex 단독 호출 결과).
결과는 process_sprite_sheet.py --input OUT --cols N --rows 1 --frames N 으로 처리한다.

다시 그린 장은 인물 크기가 다르게 나온다(Knight Skill3: −5% ~ +50%). 크기 맞춤(--fit):
  silhouette (기본) 첫 항목과 같은 시트의 프레임을 기준으로, 무기를 깎아 낸(침식→팽창) 몸 실루엣을 IoU로 겹쳐 배율을 찾는다.
             무기가 가로로 뻗은 장은 덜 겹치니 장마다 IoU가 높은 두 프레임의 배율 중앙값을 쓴다.
             키만 맞추면 몸통·망토가 가는 그림이 작아 보였고, 얼굴 크기는 칼이 얼굴을 가리면 틀렸다(0.67 vs 실제 1.0).
  face       얼굴 피부 면적(칼·궤적이 얼굴을 가리지 않을 때만)
  none       맞추지 않음
--scales로 항목별 배율을 직접 주면 그것을 쓴다. 결과는 반드시 Idle 0번·기존 프레임과 나란히 놓고 눈으로 확인한다.
"""
import argparse
import json
import os
import sys

import numpy as np
from PIL import Image, ImageFilter

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import process_sprite_sheet as P  # noqa: E402
sys.path.insert(0, os.path.dirname(__file__))
import common as C  # noqa: E402

GAP = 60
FACE_RANGE = (0.6, 1.6)   # 얼굴 측정은 이 밖이면 틀린 것으로 본다
MIN_IOU = 0.6             # 실루엣이 이보다 안 겹치면 자세가 너무 달라 맞추지 않는다


def knockout(im):
    """가장자리에 닿은 거의 흰 영역을 투명하게 하고, 그 경계의 밝은 1px 테두리를 지운다."""
    a = np.asarray(im.convert("RGBA")).astype(float)
    white = a[..., :3].min(2) > 232
    lab = P.label_components(white)
    lab = lab[0] if isinstance(lab, tuple) else lab
    border = set(np.unique(np.concatenate([lab[0], lab[-1], lab[:, 0], lab[:, -1]]))) - {0}
    bg = np.isin(lab, list(border))
    out = a.copy()
    out[bg, 3] = 0
    edge = ~bg & (np.roll(bg, 1, 0) | np.roll(bg, -1, 0) | np.roll(bg, 1, 1) | np.roll(bg, -1, 1))
    out[edge & (a[..., :3].min(2) > 190), 3] = 0
    return Image.fromarray(out.astype(np.uint8))


def load(item):
    path, grid, idx = item.rsplit(":", 2)
    cols, rows = map(int, grid.lower().split("x"))
    want = [int(i) - 1 for i in idx.split(",")]
    im = Image.open(path).convert("RGBA")
    if np.asarray(im)[..., 3].min() == 255:
        im = knockout(im)
    frames, _, _ = P.extract_frames(np.array(im), cols, rows, cols * rows, None, True)
    return [frames[i]["image"] for i in want]


def body(im):
    """무기·궤적처럼 가는 것을 깎아 낸 몸 실루엣(키의 약 2% 침식 후 팽창)."""
    a = Image.fromarray(((np.asarray(im)[..., 3] > 128) * 255).astype(np.uint8))
    k = max(5, int(im.height * 0.02) | 1)
    m = a.filter(ImageFilter.MinFilter(k)).filter(ImageFilter.MaxFilter(k))
    out = Image.new("RGBA", im.size)
    out.putalpha(m)
    return out.crop(out.getbbox())


def fit_scale(img, refs):
    """img 몸 실루엣을 refs 각각에 겹쳐 (IoU, 배율) 중 가장 좋은 것."""
    b = body(img)
    best = (0.0, 1.0)
    for r in refs:
        s0 = r.height / b.height
        W, H = int(max(r.width, b.width * s0) * 1.6), int(max(r.height, b.height * s0) * 1.3)
        rm = P._fit_mask(r, 1, W, H)
        for s in np.arange(s0 * 0.85, s0 * 1.15, s0 * 0.01):
            for dx in range(-16, 17, 4):
                m = P._fit_mask(b, s, W, H, dx)
                iou = float((rm & m).sum() / max(1, (rm | m).sum()))
                if iou > best[0]:
                    best = (iou, float(s))
    return best


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", required=True)
    ap.add_argument("--fit", choices=["silhouette", "face", "none"], default="silhouette")
    ap.add_argument("--scales", type=float, nargs="+", default=None, help="항목별 배율을 직접 준다(--fit보다 우선)")
    ap.add_argument("--keep-canvas", action="store_true", help="자르지 않고 캔버스째 잇는다(모든 장의 몸이 같은 자리일 때, 처리는 --align_x anchor)")
    ap.add_argument("--pin-foot", choices=["left", "right"],
                    help="장마다 바닥 띠(키의 6%%)의 가장 왼쪽/오른쪽 픽셀(디딘 뒷발 끝)을 같은 x에 놓는다. 처리는 --align_x anchor")
    ap.add_argument("items", nargs="+")
    args = ap.parse_args()
    if args.keep_canvas:
        # 포즈 편집(pose_edit)·원반 조립처럼 모든 장의 몸이 같은 캔버스의 같은 자리에 그려진 경우: 자르지 않고 캔버스째 잇는다.
        # 경계 상자를 칸 가운데에 맞추면 지팡이·원반이 뻗은 장마다 몸이 반대로 밀렸다(Priest Skill2 v4, 발 미끄러짐 48px).
        # 처리는 --align_x anchor (기준 장의 발 위치 하나로 — 칸 좌표가 그대로라 캔버스 위치가 유지된다)
        ims = []
        for it in args.items:
            path, grid, _ = it.rsplit(":", 2)
            if grid.lower() != "1x1":
                sys.exit(f"--keep-canvas는 한 장짜리(1x1) 항목만: {it}")
            ims.append(C.load_rgba(path))
        if len({im.size for im in ims}) != 1:
            sys.exit(f"--keep-canvas: 캔버스 크기가 다르다 {sorted({im.size for im in ims})}")
        if args.scales:
            # 캔버스째 이으면서 장별 크기만 고친다 — 발밑(실루엣 바닥 가운데)을 고정점으로 줄이고 키워 캔버스 위치(쓰러지며 이동한 거리)를 지킨다.
            # 앞 장에서 이어서 편집하면 누운 장면이 서 있는 장보다 ~10% 커졌다(Goblin Dead 2026-10-23)
            if len(args.scales) != len(ims):
                sys.exit(f"--scales {len(args.scales)}개, 항목 {len(ims)}개")
            fixed = []
            for im, s in zip(ims, args.scales):
                if abs(s - 1) < 0.005:
                    fixed.append(im)
                    continue
                a = np.asarray(im)[:, :, 3] > 128
                ys, xs = np.where(a)
                px, py = (xs.min() + xs.max()) / 2, ys.max()
                sm = im.resize((round(im.width * s), round(im.height * s)), Image.LANCZOS)
                c = Image.new("RGBA", im.size)
                c.alpha_composite(sm, (round(px - px * s), round(py - py * s)))
                fixed.append(c)
            ims = fixed
        cw, ch = ims[0].width + GAP, ims[0].height
        out = Image.new("RGBA", (cw * len(ims), ch))
        for k, im in enumerate(ims):
            out.alpha_composite(im, (k * cw + GAP // 2, 0))
        os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
        out.save(args.out)
        print(f"RESULT {json.dumps({'ok': True, 'out': args.out, 'frames': len(ims), 'keep_canvas': True}, ensure_ascii=False)}")
        return
    groups = [load(it) for it in args.items]
    paths = [it.rsplit(":", 2)[0] for it in args.items]
    base = [im for g, p in zip(groups, paths) if p == paths[0] for im in g]
    factors, detail = [], []
    if args.fit == "face":
        meds = []
        for g in groups:
            v = [x for x in (P.face_size(im) for im in g) if x]
            meds.append(float(np.median(v)) if v else None)
    if args.fit == "silhouette":
        refs = [body(im) for im in base]
    for k, (g, p) in enumerate(zip(groups, paths)):
        s = 1.0
        if args.scales:
            s = args.scales[k]
        elif p != paths[0] and args.fit == "silhouette":
            fits = sorted((fit_scale(im, refs) for im in g), reverse=True)[:2]
            s = float(np.median([f[1] for f in fits]))
            detail.append({"item": k, "iou": [round(f[0], 3) for f in fits]})
            if fits[0][0] < MIN_IOU:
                detail[-1]["skipped"] = round(s, 3)
                s = 1.0
        elif args.fit == "face" and meds[k] and meds[0]:
            s = meds[0] / meds[k]
            if not (FACE_RANGE[0] <= s <= FACE_RANGE[1]):
                detail.append({"item": k, "skipped": round(s, 3)})
                s = 1.0
        factors.append(round(s, 3))
        if abs(s - 1) > 0.005:
            g[:] = [im.resize((round(im.width * s), round(im.height * s)), Image.LANCZOS) for im in g]
    ims = [im for g in groups for im in g]
    if args.pin_foot:
        # 런지처럼 뒷발이 바닥에 납작하게 깔리면 파이프라인의 발 검출(세로로 두툼한 열만)이 그 발을 놓쳐
        # 궤적·앞발에 맞춰 몸이 반 칸씩 밀렸다(Goblin Skill1 2026-10-23: 베기·임팩트 장). 디딘 발 끝을 직접 맞춘다
        def foot_x(im):
            a = np.asarray(im)[:, :, 3] > 128
            ys = np.where(a.any(1))[0]
            band = a[ys.max() - max(3, int((ys.max() - ys.min()) * 0.06)):ys.max() + 1]
            xs = np.where(band.any(0))[0]
            return xs.min() if args.pin_foot == "left" else xs.max()
        fx = [foot_x(im) for im in ims]
        left = max(fx) if args.pin_foot == "left" else max(f for f in fx)
        right = max(im.width - f for im, f in zip(ims, fx))
        cw = left + right + GAP
        ch = max(im.height for im in ims) + GAP
        out = Image.new("RGBA", (cw * len(ims), ch))
        for k, (im, f) in enumerate(zip(ims, fx)):
            out.alpha_composite(im, (k * cw + GAP // 2 + left - f, ch - GAP // 2 - im.height))
        os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
        out.save(args.out)
        print(f"RESULT {json.dumps({'ok': True, 'out': args.out, 'frames': len(ims), 'scales': factors, 'pin_foot': args.pin_foot}, ensure_ascii=False)}")
        return
    cw = max(im.width for im in ims) + GAP
    ch = max(im.height for im in ims) + GAP
    out = Image.new("RGBA", (cw * len(ims), ch))
    for k, im in enumerate(ims):
        out.alpha_composite(im, (k * cw + (cw - im.width) // 2, ch - GAP // 2 - im.height))
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    out.save(args.out)
    print(f"RESULT {json.dumps({'ok': True, 'out': args.out, 'frames': len(ims), 'scales': factors, 'fit': detail}, ensure_ascii=False)}")


if __name__ == "__main__":
    main()
