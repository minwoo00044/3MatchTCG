"""
몸 프레임 한 장을 세 층으로 나눈다 — 땅에 짚은 단단한 소품(지팡이 등)을 반자동 Idle에서 고정하려고.
원래 그림의 앞뒤 순서 그대로: 몸(맨 뒤) → 소품(고정) → 소품을 쥔 손(맨 앞, 몸과 같은 워프).
procedural_idle.py의 --body-image / --static-layer / --hand-layer(character.json idle.body_image·static_layer·hand_layer)에 쓴다.

    python prop_split.py --spec Assets/_/Spirte/Priest/source~/idle/staff_split.json [--out DIR]

spec(JSON, 좌표는 몸 프레임(잘라 낸 인물) 기준 px, 양끝 포함, null = 끝까지):
    {"sheet": "Assets/_/Spirte/Priest/source~/idle/ai_sheet.png", "grid": [4, 2, 8], "frame": 0,
     "prop": [{"y": [null, 183], "x": [214, null]}, ...],   # 소품 영역(사각형 합집합) — 알파가 있는 픽셀만
     "hand": {"y": [184, 213], "x": [222, 250]},              # 쥔 손 — 소품에서 빼고 손 층으로
     "pole_x": [231, 246],                                     # 손에 가려진 막대: 손 위·아래 줄을 섞어 채울 가로 범위
     "out": {"body": "...png", "prop": "...png", "hand": "...png"}}

몸 층의 소품 뒤 빈칸은 바로 왼쪽 픽셀을 늘려 채운다(양옆이 몸일 때만) — 소품이 앞에서 덮어 거의 안 보인다.
확산 채우기(이웃 평균 반복)는 네모 얼룩이 남았다(Knight Skill3, Priest Idle 2026-10-16).
Codex에 "같은 그림에서 소품만 지워라"로 받는 방법(IoU 0.98, Knight)이 더 깨끗하지만 Priest 때는 모델 용량 부족으로 실패해 좌표로 나눴다.
좌표는 격자를 그린 확대 그림(sheet_check.py 등)과 손 주변 색 표본에서 읽는다.
"""
import argparse
import json
import os
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(__file__))
import common as C  # noqa: E402

ALPHA = 30


def rect_mask(shape, r):
    H, W = shape
    yy, xx = np.mgrid[0:H, 0:W]
    y0, y1 = r.get("y", [None, None])
    x0, x1 = r.get("x", [None, None])
    m = np.ones(shape, bool)
    if y0 is not None:
        m &= yy >= y0
    if y1 is not None:
        m &= yy <= y1
    if x0 is not None:
        m &= xx >= x0
    if x1 is not None:
        m &= xx <= x1
    return m


def split(img, spec):
    H, W = img.shape[:2]
    alpha = img[..., 3] > ALPHA
    hand = alpha & rect_mask((H, W), spec["hand"])
    prop_area = np.zeros((H, W), bool)
    for r in spec["prop"]:
        prop_area |= rect_mask((H, W), r)
    prop = alpha & prop_area & ~hand

    layer = np.zeros_like(img)
    layer[prop] = img[prop]
    (hy0, hy1), (px0, px1) = spec["hand"]["y"], spec["pole_x"]
    above, below = hy0 - 2, hy1 + 3
    for y in range(hy0, hy1 + 1):  # 손에 가려진 막대 줄
        t = (y - above) / (below - above)
        seg = (1 - t) * img[above, px0:px1 + 1].astype(np.float32) + t * img[below, px0:px1 + 1]
        layer[y, px0:px1 + 1] = seg.astype(np.uint8)

    hand_img = np.zeros_like(img)
    hand_img[hand] = img[hand]

    body = img.copy()
    body[prop | hand] = 0
    for y in range(H):
        xs = np.where(prop[y])[0]
        if not len(xs):
            continue
        x0, x1 = xs.min(), xs.max()
        if x0 > 0 and alpha[y, x0 - 1] and x1 + 1 < W and alpha[y, x1 + 1:min(W, x1 + 4)].any():
            body[y, x0:x1 + 1] = body[y, x0 - 1]
    return body, layer, hand_img, int(prop.sum()), int(hand.sum())


def main():
    C.utf8_stdout()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--spec", required=True)
    ap.add_argument("--out", help="출력 폴더 (생략하면 spec의 out 경로 그대로)")
    args = ap.parse_args()
    with open(args.spec, encoding="utf-8") as fp:
        spec = json.load(fp)
    cols, rows, n = spec.get("grid", [4, 2, 8])
    rgba = np.array(Image.open(os.path.join(C.ROOT, spec["sheet"])).convert("RGBA"))
    frames, _, _ = C.P.extract_frames(rgba, cols, rows, n, None, True)
    img = np.asarray(frames[spec.get("frame", 0)]["image"]).astype(np.uint8)
    body, layer, hand_img, n_prop, n_hand = split(img, spec)
    out = {}
    for key, arr in (("body", body), ("prop", layer), ("hand", hand_img)):
        path = spec["out"][key]
        if args.out:
            path = os.path.join(args.out, os.path.basename(path))
        path = os.path.join(C.ROOT, path)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        Image.fromarray(arr).save(path)
        out[key] = path.replace("\\", "/")
    # 다시 합치면 원본과 같아야 한다(차이 = 막대 가장자리 반투명 픽셀 몇 개)
    comp = Image.fromarray(body)
    comp.alpha_composite(Image.fromarray(layer))
    comp.alpha_composite(Image.fromarray(hand_img))
    diff = int((np.abs(np.asarray(comp).astype(int) - img.astype(int)).max(2) > 30).sum())
    print(f"소품 {n_prop}px, 손 {n_hand}px, 다시 합친 그림과 원본이 다른 픽셀 {diff}")
    print(f"RESULT {json.dumps({'ok': True, **out, 'recompose_diff_px': diff}, ensure_ascii=False)}")


if __name__ == "__main__":
    main()
