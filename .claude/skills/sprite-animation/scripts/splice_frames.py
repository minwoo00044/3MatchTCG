"""
여러 원본 시트에서 프레임을 골라 한 장의 원본 시트로 잇는다 — 동작 일부만 다시 그려 바꿀 때.

    python splice_frames.py --out SpriteRegen/Knight_Skill3/splice1.png \
        SpriteRegen/Knight_Skill3/try3/result.png:4x2:1,2 \
        SpriteRegen/Knight_Skill3/try5/result.png:2x2:1,2,3,4 \
        SpriteRegen/Knight_Skill3/try3/result.png:4x2:5,6,7,8

항목 = 시트:열x행:프레임번호(1부터, 쉼표). 순서대로 한 줄(가로)로 놓는다.
다시 그린 장은 인물 크기가 다르게 나온다 — 얼굴 크기(process_sprite_sheet.face_size)를 첫 항목 중앙값에 맞춘다(±3%~--max).
결과는 process_sprite_sheet.py --input OUT --cols N --rows 1 --frames N 으로 처리한다.
Knight Skill3 회전 구간의 궤적이 칼에 비해 작아(사용자 지적 2026-10-15) 그 4장만 다시 그려 끼웠다.
"""
import argparse
import json
import os
import sys

import numpy as np
from PIL import Image

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import process_sprite_sheet as P  # noqa: E402

GAP = 60


def load(item):
    path, grid, idx = item.rsplit(":", 2)
    cols, rows = map(int, grid.lower().split("x"))
    want = [int(i) - 1 for i in idx.split(",")]
    rgba = np.array(Image.open(path).convert("RGBA"))
    frames, _, _ = P.extract_frames(rgba, cols, rows, cols * rows, None, True)
    return [frames[i]["image"] for i in want]


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", required=True)
    ap.add_argument("--max", type=float, default=0.6, help="보정 배율 상한(1±max). 다시 그린 장은 +40%%까지 커졌다(Knight Skill3 회전)")
    ap.add_argument("--scales", type=float, nargs="+", default=None,
                    help="항목별 배율을 직접 준다. 궤적·흩날린 머리카락이 많은 장은 얼굴 측정이 틀린다(Knight Skill3 회전: 얼굴 0.67배 vs 턱~발 1.0배 → 눈으로 0.93)")
    ap.add_argument("items", nargs="+")
    args = ap.parse_args()
    groups = [load(it) for it in args.items]
    meds = []
    for g in groups:
        v = [x for x in (P.face_size(im) for im in g) if x]
        meds.append(float(np.median(v)) if v else None)
    factors = []
    for k, (g, m) in enumerate(zip(groups, meds)):
        s = meds[0] / m if (m and meds[0]) else 1.0
        if not (P.PART_EQ_MIN < abs(s - 1) <= args.max):
            s = 1.0
        if args.scales:
            s = args.scales[k]
        factors.append(round(s, 3))
        if s != 1.0:
            g[:] = [im.resize((round(im.width * s), round(im.height * s)), Image.LANCZOS) for im in g]
    ims = [im for g in groups for im in g]
    cw = max(im.width for im in ims) + GAP
    ch = max(im.height for im in ims) + GAP
    out = Image.new("RGBA", (cw * len(ims), ch))
    for k, im in enumerate(ims):
        out.alpha_composite(im, (k * cw + (cw - im.width) // 2, ch - GAP // 2 - im.height))
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    out.save(args.out)
    print(f"RESULT {json.dumps({'ok': True, 'out': args.out, 'frames': len(ims), 'scales': factors}, ensure_ascii=False)}")


if __name__ == "__main__":
    main()
