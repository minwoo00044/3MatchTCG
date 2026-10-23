"""
처리된 시트의 동작 경로 검사.

  once SHEET   한 번 찌르고 돌아오는지: 칼날(밝은 무채색) 가장 앞쪽 x와 상체 무게중심 x가 최대에 도달한 뒤
               3px 넘게 다시 앞으로 가는 구간을 찾는다. 모델이 "몸을 더 밀어붙인다"를 재찌르기로 그렸다(Knight Skill1).
               캐릭터가 오른쪽을 본다고 가정한다(--left면 반대). 종료 코드 0 통과 / 4 실패.
"""
import argparse
import json
import os
import sys

import numpy as np
from PIL import Image

MARGIN = 3


def cells(path):
    m = json.load(open(os.path.splitext(path)[0] + ".json", encoding="utf-8"))
    at = Image.open(path).convert("RGBA")
    cw, ch, c = m["cellWidth"], m["cellHeight"], m["cols"]
    return [np.asarray(at.crop(((i % c) * cw, (i // c) * ch, (i % c + 1) * cw, (i // c + 1) * ch))) for i in range(m["frames"])]


def paths(cs):
    tips, body = [], []
    for cell in cs:
        a = cell[:, :, 3] > 128
        rgb = cell[:, :, :3].astype(float)
        mx, mn = rgb.max(2), rgb.min(2)
        metal = a & (mx > 165) & ((mx - mn) < 0.12 * mx + 5)
        tips.append(int(np.where(metal.any(0))[0].max()) if metal.any() else None)
        ys = np.where(a.any(1))[0]
        top, bot = ys.min(), ys.max()
        band = a[int(top + 0.25 * (bot - top)):int(top + 0.55 * (bot - top))]
        body.append(float(np.where(band)[1].mean()))
    return tips, body


def again_forward(v):
    v = [x for x in v if x is not None]
    if not v:
        return []
    pk = int(np.argmax(v))
    return [i for i in range(pk, len(v) - 1) if v[i + 1] - v[i] > MARGIN]


def cmd_once(args):
    tips, body = paths(cells(args.sheet))
    if args.left:
        w = max(t for t in tips if t is not None)
        tips = [w - t if t is not None else None for t in tips]
        body = [-b for b in body]
    bt, bb = again_forward(tips), again_forward(body)
    print("칼끝", tips)
    print("몸통", [round(b) for b in body])
    ok = not bt and not bb
    print("판정:", "통과 — 최대 뻗음 이후 다시 앞으로 가지 않는다" if ok else f"실패 — 다시 앞으로: 칼끝 {bt}, 몸통 {bb} (그 원본 프레임을 빼거나 정렬 발을 바꾼다)")
    print(f"RESULT {json.dumps({'ok': True, 'pass': ok, 'tip_again': bt, 'body_again': bb}, ensure_ascii=False)}")
    sys.exit(0 if ok else 4)


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    o = sub.add_parser("once")
    o.add_argument("sheet")
    o.add_argument("--left", action="store_true", help="캐릭터가 왼쪽을 본다")
    args = p.parse_args()
    {"once": cmd_once}[args.cmd](args)


if __name__ == "__main__":
    main()
