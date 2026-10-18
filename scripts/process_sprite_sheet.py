"""
AI 생성 스프라이트 시트 → 정렬된 아틀라스 + 매니페스트.

    python scripts/process_sprite_sheet.py --input RAW.png --name Archer_Dead_v1
    python scripts/process_sprite_sheet.py --input RAW.png --name Archer_Dead_v1 --analyze

출력
  Assets/_/Spirte/{캐릭터}/{이름}.png    정렬된 아틀라스 (폴더가 없으면 만든다)
  Assets/_/Spirte/{캐릭터}/{이름}.json   매니페스트 — Unity 쪽은 이 파일만 읽는다
  Temp/SpriteAnimationPipeline/{이름}_preview.png
      원본 분할선 / 아틀라스+접지선+pivot / 전 프레임 겹쳐보기(onion)

종료 코드: 0 성공(경고는 매니페스트 warnings와 RESULT 줄에), 1 실패.
마지막 줄은 항상 `RESULT {json}` 이다.

액션별 fps/loop/정렬 규칙은 ACTIONS 한 곳에만 둔다. Unity 쪽은 매니페스트로 받기만 한다.
"""
import argparse
import json
import math
import os
import re
import sys

import numpy as np
from PIL import Image, ImageDraw

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SHEET_ROOT = "Assets/_/Spirte"
PREVIEW_DIR = "Temp/SpriteAnimationPipeline"

NAME_PATTERN = re.compile(r"^([A-Z][A-Za-z0-9]*)_(Idle|Hit|Skill[1-9]|Dead)_v([1-9][0-9]*)$")

# align_x  feet       : 프레임마다 발 띠(바닥 근처 실루엣 전체) 중심을 pivot에 맞춘다 (제자리 모션의 좌우 흔들림 제거)
#          anchor     : 기준 프레임의 발 중심 하나로 전 프레임을 같은 양만큼 옮긴다 (원본의 이동을 보존)
#          mid        : 프레임마다 두 발 중심의 중점을 맞춘다 (발 띠 평균과 달리 발 사이에 걸친 활 끝에 끌리지 않는다)
#          left_foot  : 화면 왼쪽 발을 프레임마다 같은 자리에 둔다 — 그 발을 디딘 채 다른 발이 움직이는 동작
#          right_foot : 화면 오른쪽 발을 같은 자리에 둔다
#          both_feet  : 중점을 맞춘 뒤 두 발을 기준 프레임의 발 위치로 끌어당긴다(다리 아래쪽만 휘는 워프).
#                       AI가 프레임마다 보폭을 다르게 그려서 이동만으로는 두 발을 함께 고정할 수 없다
# 고정할 발은 시트 그림(보폭이 어떻게 변하는지)에 달려 있어서 {캐릭터}.character.json의 "align_x"가 액션 기본값을 덮는다.
# align_y  ground : 프레임마다 최하단을 접지선에 맞춘다 (서 있든 쓰러지든 몸 어딘가는 땅에 닿는다)
#          anchor : 기준 프레임 기준으로 일괄 이동 (점프처럼 공중에 뜨는 모션)
ACTIONS = {
    "Idle":  {"fps": 8,  "loop": True,  "align_x": "feet",   "align_y": "ground"},
    "Hit":   {"fps": 10, "loop": False, "align_x": "feet",   "align_y": "ground"},
    "Skill": {"fps": 10, "loop": False, "align_x": "feet",   "align_y": "ground"},
    "Dead":  {"fps": 8,  "loop": False, "align_x": "anchor", "align_y": "ground"},
}

ALPHA_THRESHOLD = 30
SEAM_MARGIN = 70          # 셀 경계 ±px 안에서 분할선을 찾는다
SEAM_OPAQUE_WARN = 40     # 분할선이 이만큼 불투명 픽셀을 지나가면 실제 겹침으로 본다
NOISE_MIN_AREA = 80
ALIGN_X = ["feet", "anchor", "mid", "left_foot", "right_foot", "both_feet"]
FOOT_BAND = 0.12          # 발을 찾는 바닥 띠 높이(프레임 키 대비). Archer 서 있는 시트 전부에서 부츠 색 마스크와 같은 발을 잡았다
SIZE_FIT_RANGE = (0.88, 1.12)  # 기준 시트 실루엣 맞춤 배율 탐색 범위
PART_EQ_MIN = 0.03        # 장별 얼굴 크기 차이가 이보다 작으면 건드리지 않는다
PART_EQ_MAX = 0.15        # 이보다 크면 측정 실패로 보고 건드리지 않는다
SIZE_FIT_MIN_IOU = 0.6   # 이보다 안 겹치면 기준 프레임이 준비 자세가 아닌 것 — 보정하지 않는다
FOOT_FILL = 0.4          # 띠에서 이 비율 이상 세로로 차 있는 열만 발(정강이+신발). 얇은 칼날·스미어 사선을 거른다
PIN_MAX = 0.06            # both_feet가 발을 옮기는 거리가 키의 이 비율을 넘으면 그려진 보폭 변화를 지우는 것일 수 있어 경고
PIN_FALLOFF = 0.45        # 워프는 바닥에서 1, 키의 이 비율 높이에서 0 — 가랑이 아래만 휜다
# 프레임 증강: 원본 프레임 사이마다 RIFE 보간 프레임을 이만큼 넣고 fps를 (n+1)배로 올린다.
# 원본 프레임은 원래 시각에 그대로 나온다 (루프 8장 → 24장, 비루프 8장 → 22장)
DEFAULT_INBETWEEN = 2
HAZE_CUT = 0.06           # 보간 번짐 지표(rife.interpolate.haze)가 이걸 넘으면 그 구간은 끊는다.
                          # Archer 전 구간의 최선값 ≤0.04, 안개가 눈에 띈 구간(활을 머리 위로, scale 1) 0.093
ATLAS_MAX = 4096
CELL_PAD = 12
GROUND_PAD = 4            # 접지선 아래 여백 (기존 규격 543-1-538 = 4 와 같음)


class PipelineError(Exception):
    pass


def action_rule(action):
    return ACTIONS["Skill" if action.startswith("Skill") else action]


# ---------------------------------------------------------------- 분할

def find_seam(cost):
    """cost(H, W)에서 위→아래로 한 줄씩 내려가며 x가 최대 1칸씩만 움직이는 최소 비용 경로."""
    h, w = cost.shape
    acc = cost[0].copy()
    back = np.zeros((h, w), dtype=np.int8)
    cols = np.arange(w)
    for y in range(1, h):
        left = np.concatenate(([np.inf], acc[:-1]))
        right = np.concatenate((acc[1:], [np.inf]))
        stack = np.vstack((left, acc, right))
        idx = np.argmin(stack, axis=0)
        back[y] = idx - 1
        acc = cost[y] + stack[idx, cols]
    seam = np.empty(h, dtype=np.int64)
    x = int(np.argmin(acc))
    for y in range(h - 1, -1, -1):
        seam[y] = x
        x += int(back[y, x])
    return seam


def seam_cost(alpha_window, center):
    w = alpha_window.shape[1]
    dist = (np.arange(w) - center) / max(1.0, w / 2.0)
    return alpha_window * 1000.0 + dist[None, :] ** 2


def split_rows(alpha, rows, row_splits):
    """행 경계선. 반환: (rows+1, W) — 각 x에서 행 r은 [b[r][x], b[r+1][x]) 구간."""
    h, w = alpha.shape
    nominal = h / rows
    bounds = [np.zeros(w, dtype=np.int64)]
    crossings = []
    for k in range(1, rows):
        if row_splits:
            seam = np.full(w, row_splits[k - 1], dtype=np.int64)
        else:
            lo = max(1, int(k * nominal) - SEAM_MARGIN)
            hi = min(h - 1, int(k * nominal) + SEAM_MARGIN)
            window = alpha[lo:hi, :].T  # (W, win): x를 따라 내려가며 y를 고른다
            seam = find_seam(seam_cost(window, k * nominal - lo)) + lo
        crossings.append(int((alpha[seam, np.arange(w)] > ALPHA_THRESHOLD / 255).sum()))
        bounds.append(seam)
    bounds.append(np.full(w, h, dtype=np.int64))
    return np.array(bounds), crossings


def split_cols(alpha, row_mask, cols, y0, y1):
    """한 행 띠 안의 열 경계선. 반환: (cols+1, y1-y0)."""
    band = alpha[y0:y1] * row_mask[y0:y1]
    bh, w = band.shape
    nominal = w / cols
    bounds = [np.zeros(bh, dtype=np.int64)]
    crossings = []
    for k in range(1, cols):
        lo = max(1, int(k * nominal) - SEAM_MARGIN)
        hi = min(w - 1, int(k * nominal) + SEAM_MARGIN)
        seam = find_seam(seam_cost(band[:, lo:hi], k * nominal - lo)) + lo
        crossings.append(int((band[np.arange(bh), seam] > ALPHA_THRESHOLD / 255).sum()))
        bounds.append(seam)
    bounds.append(np.full(bh, w, dtype=np.int64))
    return np.array(bounds), crossings


def remove_small_components(mask, min_area):
    """4-연결 요소 중 min_area 미만을 지운다. 행 단위 run으로 union-find (scipy 없이)."""
    h = mask.shape[0]
    parent = []

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    runs = []  # (y, start, end, id)
    prev = []
    for y in range(h):
        row = mask[y].astype(np.int8)
        d = np.diff(np.concatenate(([0], row, [0])))
        starts, ends = np.where(d == 1)[0], np.where(d == -1)[0]
        cur = []
        j = 0
        for s, e in zip(starts, ends):
            rid = len(parent)
            parent.append(rid)
            while j < len(prev) and prev[j][1] <= s:
                j += 1
            k = j
            while k < len(prev) and prev[k][0] < e:
                ra, rb = find(rid), find(prev[k][2])
                if ra != rb:
                    parent[ra] = rb
                k += 1
            cur.append((s, e, rid))
            runs.append((y, s, e, rid))
        prev = cur

    area = {}
    for y, s, e, rid in runs:
        root = find(rid)
        area[root] = area.get(root, 0) + (e - s)
    out = mask.copy()
    removed = 0
    for y, s, e, rid in runs:
        if area[find(rid)] < min_area:
            out[y, s:e] = False
            removed += e - s
    return out, removed


def label_components(mask):
    """4-연결 요소 라벨 (행 단위 run + union-find, scipy 없이). 반환: (라벨 배열 int32, 0 = 배경)."""
    h = mask.shape[0]
    parent = []

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    runs, prev = [], []
    for y in range(h):
        d = np.diff(np.concatenate(([0], mask[y].astype(np.int8), [0])))
        cur, j = [], 0
        for s0, e0 in zip(np.where(d == 1)[0], np.where(d == -1)[0]):
            rid = len(parent)
            parent.append(rid)
            while j < len(prev) and prev[j][1] <= s0:
                j += 1
            k = j
            while k < len(prev) and prev[k][0] < e0:
                ra, rb = find(rid), find(prev[k][2])
                if ra != rb:
                    parent[ra] = rb
                k += 1
            cur.append((s0, e0, rid))
            runs.append((y, s0, e0, rid))
        prev = cur
    labels = np.zeros(mask.shape, np.int32)
    roots = {}
    for y, s0, e0, rid in runs:
        labels[y, s0:e0] = roots.setdefault(find(rid), len(roots) + 1)
    return labels


COMPONENT_SHARED = 0.15  # 한 덩어리가 두 칸에 이만큼 넘게 걸치면 실제로 붙어 그려진 것 — 그 덩어리만 경계선으로 자른다


def extract_frames(rgba, cols, rows, frames, row_splits, clean_noise):
    h, w = rgba.shape[:2]
    alpha = rgba[:, :, 3].astype(np.float64) / 255.0
    fg = rgba[:, :, 3] > ALPHA_THRESHOLD
    yy = np.arange(h)[:, None]
    xx = np.arange(w)[None, :]
    cell_w, cell_h = w / cols, h / rows

    # 열 경계선 비용: 칼날처럼 채도가 낮고 밝은 픽셀을 자르는 비용을 크게 — 뻗은 검끝이 옆 인물 머리카락에 닿아 그려지면
    # 경계선이 칼날 대신 머리카락을 지나가게 한다(Knight Skill1 런지, 검끝이 잘림)
    rgbf = rgba[:, :, :3].astype(np.float32) / 255
    mx, mn = rgbf.max(2), rgbf.min(2)
    metal = (mx > 0.65) & ((mx - mn) < 0.12 * mx + 0.02)
    seam_alpha = alpha * (1 + 8 * metal)
    row_bounds, row_cross = split_rows(alpha, rows, row_splits)
    warnings = []

    seams = {"rows": row_bounds, "cols": []}
    result = []
    cell_masks = {}
    for r in range(rows):
        row_mask = (yy >= row_bounds[r][None, :]) & (yy < row_bounds[r + 1][None, :])
        y0, y1 = int(row_bounds[r].min()), int(row_bounds[r + 1].max())
        col_bounds, col_cross = split_cols(seam_alpha, row_mask, cols, y0, y1)
        seams["cols"].append((y0, col_bounds))

        for c in range(cols):
            idx = r * cols + c
            if idx >= frames:
                break
            col_mask = np.zeros((h, w), dtype=bool)
            left = col_bounds[c][:, None]
            right = col_bounds[c + 1][:, None]
            col_mask[y0:y1] = (xx >= left) & (xx < right)
            cell_masks[idx] = (r, c, fg & row_mask & col_mask)

    # 덩어리 단위 배정: 경계선은 칸을 대략 나눌 뿐, 이어진 덩어리(캐릭터 + 손에 든 검 + 붙은 효과)는 가장 많이 걸친 칸에 통째로 준다.
    # 길게 뻗은 검·베기 궤적이 옆 칸으로 넘어가면 경계선이 잘라 검끝이 잘리고 조각이 옆 프레임에 붙었다(Knight Skill2, 사용자 지적 2026-10-15)
    labels = label_components(fg)
    n_lab = labels.max()
    share = np.zeros((n_lab + 1, frames), np.int64)
    for idx, (_, _, m) in cell_masks.items():
        share[:, idx] = np.bincount(labels[m], minlength=n_lab + 1)
    area = share.sum(1)
    owner = share.argmax(1)
    second = np.sort(share, 1)[:, -2] if frames > 1 else np.zeros(n_lab + 1, np.int64)
    split_lab = (second > COMPONENT_SHARED * np.maximum(area, 1)) & (area > 0)
    small = area < (NOISE_MIN_AREA if clean_noise else 0)
    for lab in np.where(split_lab & ~small)[0]:
        warnings.append(f"덩어리 {lab}가 프레임 {owner[lab]}와 다른 칸에 맞닿아 그려져 있다 — 경계선으로 잘랐다(칸이 좁아 검이 옆 인물에 닿음). "
                        f"생성 배치를 넓혀 다시 뽑는다")

    for idx, (r, c, seam_mask) in sorted(cell_masks.items()):
        mine = (owner == idx) & ~split_lab & ~small
        mine[0] = False
        mask = mine[labels] | (seam_mask & split_lab[labels] & ~small[labels])
        ys, xs = np.where(mask)
        if len(ys) == 0:
            raise PipelineError(f"프레임 {idx}: 비어 있다 (--frames를 확인)")

        x0, x1, top, bottom = xs.min(), xs.max(), ys.min(), ys.max()
        edges = [n for n, hit in (("왼쪽", c == 0 and x0 == 0), ("오른쪽", c == cols - 1 and x1 == w - 1),
                                   ("위", r == 0 and top == 0), ("아래", r == rows - 1 and bottom == h - 1)) if hit]
        if edges:
            warnings.append(f"프레임 {idx}: 원본 시트 {'/'.join(edges)} 가장자리에서 이미 잘려 있다")

        band = ys >= bottom - max(4, (bottom - top) // 15)
        img = rgba[top:bottom + 1, x0:x1 + 1].copy()
        img[~mask[top:bottom + 1, x0:x1 + 1]] = 0
        ox, oy = c * cell_w, r * cell_h  # 공칭 셀 원점 — 프레임 로컬 좌표의 기준
        left_c, right_c = foot_centers(img)
        result.append({
            "feet": (left_c + x0 - ox, right_c + x0 - ox),
            "index": idx,
            "image": Image.fromarray(img),
            "left": x0 - ox, "right": x1 + 1 - ox,
            "top": top - oy, "bottom": bottom + 1 - oy,
            "feet_x": float(xs[band].mean()) - ox,
        })
    return result, seams, warnings


def foot_centers(img):
    """
    바닥 띠에서 가장 왼쪽·오른쪽 덩어리의 중심 = 두 발 (이미지 로컬 x). 두 발이 붙어 한 덩어리면 둘 다 그 중심.
    """
    a = np.asarray(img)[:, :, 3] > 128
    ys, _ = np.where(a)
    top, bottom = ys.min(), ys.max()
    h = bottom - top + 1
    rows = a[bottom - max(4, int(h * FOOT_BAND)):bottom + 1]
    # 띠 높이의 FOOT_FILL 이상 차 있는 열만 발로 본다. 바닥까지 내려온 칼날·스미어는 띠 안에서 얇은 사선이라
    # any(0)로 잡으면 발 덩어리에 붙거나 발로 뽑혀 중점이 끌려갔다(Knight Skill2 내려 베기: 몸이 좌우로 194px 미끄러짐)
    band = rows.sum(0) >= rows.shape[0] * FOOT_FILL
    if not band.any():
        band = rows.any(0)
    d = np.diff(np.concatenate(([0], band.astype(np.int8), [0])))
    runs = [(s, e) for s, e in zip(np.where(d == 1)[0], np.where(d == -1)[0]) if e - s > h * 0.03]
    if not runs:
        c = float(np.where(band)[0].mean())
        return c, c
    # 가장 넓은 두 덩어리 = 두 발. 가장 왼쪽·오른쪽을 고르면 바닥까지 내려온 망토 끝·검 끝을 발로 잡는다
    # (Knight Idle: 망토 끝이 8프레임 중 7프레임에만 걸려 왼발이 36px 튀었고, both_feet 워프가 다리를 비틀었다)
    runs = sorted(sorted(runs, key=lambda r: r[1] - r[0], reverse=True)[:2])
    return (runs[0][0] + runs[0][1]) / 2.0, (runs[-1][0] + runs[-1][1]) / 2.0


# ---------------------------------------------------------------- 체급(스케일) 기준

def standing_height(image):
    """
    다리를 곧게 폈을 때의 키 추정. 세로 키만 쓰면 다리를 넓게 벌린 시트일수록 키가 낮게 재져
    더 크게 확대된다(궁수 시트에서 보폭 +9%~+46% 범위에서 1~3.5% 편향을 확인).
    두 발 중심 간격 d와 가랑이~바닥 높이 L로 다리 길이를 sqrt(L² + (d/2)²)로 바꿔 더한다.

    가랑이 = 바닥에서 위로 올라가며, 두 발 사이 가운데 절반 폭에서 다리 사이 틈(투명)이 사라진 상태가
    키의 8% 이상 이어지는 첫 행. 사이를 지나가는 가는 활은 양옆에 틈을 남겨 무시되고, 활 끝 장식처럼
    짧게 틈을 막는 것도 '이어짐' 조건으로 걸러진다. 다만 무기가 허벅지 사이를 길게 덮으면 가랑이를
    낮게(다리를 짧게) 잡는다 — 실루엣만으로는 구분할 수 없다. 이때 키 오차는 1% 미만이다.
    발이 하나로 붙어 있거나 가랑이를 못 찾으면 세로 키를 그대로 쓴다.
    반환: (키, 측정 정보 dict — leg는 세로 다리 길이, crotch는 위에서부터의 가랑이 행)
    """
    a = np.array(image)[:, :, 3] > 128
    ys, xs = np.where(a)
    top, bottom = ys.min(), ys.max()
    h = bottom - top + 1
    band = a[bottom - max(4, h // 16):bottom + 1].any(0)
    d = np.diff(np.concatenate(([0], band.astype(np.int8), [0])))
    runs = [(s, e) for s, e in zip(np.where(d == 1)[0], np.where(d == -1)[0]) if e - s > h * 0.03]
    if len(runs) < 2:
        return float(h), {"method": "vertical", "reason": "발이 하나로 보인다"}
    left_c = (runs[0][0] + runs[0][1]) / 2
    right_c = (runs[-1][0] + runs[-1][1]) / 2
    spread = right_c - left_c
    mid, quarter = (left_c + right_c) / 2, spread / 4
    x0, x1 = int(mid - quarter), int(mid + quarter) + 1
    min_gap, hold = max(3, int(h * 0.015)), max(3, int(h * 0.08))
    crotch, closed = None, 0
    for y in range(bottom, top, -1):
        gap = ~a[y, x0:x1]
        dd = np.diff(np.concatenate(([0], gap.astype(np.int8), [0])))
        widths = np.where(dd == -1)[0] - np.where(dd == 1)[0]
        if len(widths) and widths.max() >= min_gap:
            closed = 0
            continue
        closed += 1
        if closed >= hold:
            crotch = y + hold - 1
            break
    if crotch is None or crotch > bottom - h * 0.1:
        return float(h), {"method": "vertical", "reason": "가랑이를 못 찾았다"}
    leg = bottom - crotch
    corrected = (h - leg) + math.sqrt(leg ** 2 + (spread / 2) ** 2)
    return float(corrected), {"method": "standing", "vertical": int(h), "spread": round(float(spread), 1),
                              "leg": int(leg), "crotch": int(crotch - top)}


# ---------------------------------------------------------------- 배치

def reference_points(frames, anchor, align_x, align_y):
    a = frames[anchor]
    a_mid = (a["feet"][0] + a["feet"][1]) / 2
    refs = []
    for f in frames:
        # 한 발 고정도 기준 프레임에서는 두 발 중점이 pivot에 오게 한다. 발 자체를 pivot에 두면
        # 몸이 반 보폭만큼 옆으로 가서 다른 클립(중점 기준)으로 넘어갈 때 캐릭터가 순간이동한다
        rx = {
            "feet": f["feet_x"],
            "anchor": a["feet_x"],
            "mid": (f["feet"][0] + f["feet"][1]) / 2,
            "both_feet": (f["feet"][0] + f["feet"][1]) / 2,
            "left_foot": f["feet"][0] + (a_mid - a["feet"][0]),
            "right_foot": f["feet"][1] + (a_mid - a["feet"][1]),
        }[align_x]
        ry = f["bottom"] if align_y == "ground" else a["bottom"]
        refs.append((rx, ry))
    return refs


def warp_x(img, dx):
    """출력 (x, y)에 원본 (x - dx[y, x], y)를 쌍선형으로 가져온다. premultiplied alpha로 섞어 테두리가 어두워지지 않게."""
    arr = np.asarray(img).astype(np.float32)
    alpha = arr[:, :, 3:4] / 255.0
    pre = np.concatenate([arr[:, :, :3] * alpha, arr[:, :, 3:4]], axis=2)
    h, w = dx.shape
    sx = np.arange(w, dtype=np.float32)[None, :] - dx
    x0 = np.floor(sx).astype(np.int64)
    t = (sx - x0)[:, :, None]
    yy = np.arange(h)[:, None]

    def sample(xi):
        inside = (xi >= 0) & (xi < w)
        return pre[yy, np.clip(xi, 0, w - 1)] * inside[:, :, None]

    out = sample(x0) * (1 - t) + sample(x0 + 1) * t
    a = out[:, :, 3:4]
    rgb = np.where(a > 0, out[:, :, :3] / np.maximum(a, 1e-6) * 255.0, 0)
    return Image.fromarray(np.concatenate([rgb, a], axis=2).clip(0, 255).astype(np.uint8))


def pin_both_feet(frames, refs, anchor):
    """
    both_feet: 중점 정렬 뒤 남는 발별 어긋남을 다리 아래쪽 워프로 없앤다.
    가로 변위는 두 발 사이에서 선형으로 섞고, 세로로는 바닥 1 → 키의 PIN_FALLOFF 높이 0 (smoothstep).
    상체·머리는 움직이지 않는다. 프레임의 image/left/right/feet를 바꾼다. 반환: 경고 목록.
    """
    a, (arx, _) = frames[anchor], refs[anchor]
    target = (a["feet"][0] - arx, a["feet"][1] - arx)
    warnings = []
    for f, (rx, _) in zip(frames, refs):
        dl = target[0] - (f["feet"][0] - rx)
        dr = target[1] - (f["feet"][1] - rx)
        if max(abs(dl), abs(dr)) < 0.5:
            continue
        img = f["image"]
        h = img.height
        if max(abs(dl), abs(dr)) > h * PIN_MAX:
            warnings.append(f"프레임 {f['index']}: 발을 {dl:+.0f}/{dr:+.0f}px 옮긴다(키의 {PIN_MAX:.0%} 초과) — "
                            f"그려진 보폭 변화를 지우는 것일 수 있다. 미리보기로 확인한다")
        pad = int(math.ceil(max(abs(dl), abs(dr)))) + 1
        canvas = Image.new("RGBA", (img.width + 2 * pad, h))
        canvas.paste(img, (pad, 0))
        lx = f["feet"][0] - f["left"] + pad  # 캔버스 로컬 발 위치
        rx_local = f["feet"][1] - f["left"] + pad
        xs = np.arange(canvas.width, dtype=np.float32)
        t = np.clip((xs - lx) / (rx_local - lx), 0, 1) if rx_local > lx else np.full_like(xs, 0.5)
        horiz = (1 - t) * dl + t * dr
        u = np.clip((np.arange(h, dtype=np.float32) - (h - 1 - h * PIN_FALLOFF)) / (h * PIN_FALLOFF), 0, 1)
        vert = u * u * (3 - 2 * u)
        warped = warp_x(canvas, vert[:, None] * horiz[None, :])
        cols = np.where(np.asarray(warped)[:, :, 3].any(0))[0]
        x0, x1 = int(cols.min()), int(cols.max())
        f["image"] = warped.crop((x0, 0, x1 + 1, h))
        f["left"], f["right"] = f["left"] - pad + x0, f["left"] - pad + x1 + 1
        f["feet"] = (f["feet"][0] + dl, f["feet"][1] + dr)
    return warnings


def foot_slide(frames, refs, scale):
    """정렬 후 각 발이 프레임 사이에서 미끄러지는 폭(출력 px). 워프한 프레임도 발을 다시 재서 확인한다."""
    offs = []
    for f, (rx, _) in zip(frames, refs):
        left_c, right_c = foot_centers(f["image"])
        offs.append((left_c + f["left"] - rx, right_c + f["left"] - rx))
    o = np.array(offs) * scale
    return {"left": round(float(np.ptp(o[:, 0])), 1), "right": round(float(np.ptp(o[:, 1])), 1)}


def layout(frames, refs, scale, cell_w, cell_h, target_y):
    """pivot 기준 상대 범위로 셀 크기와 접지선을 정한다. 지정값이 모자라면 경고."""
    left = min(scale * (f["left"] - rx) for f, (rx, _) in zip(frames, refs))
    right = max(scale * (f["right"] - rx) for f, (rx, _) in zip(frames, refs))
    up = max(scale * (ry - f["top"]) for f, (_, ry) in zip(frames, refs))
    down = max(0.0, max(scale * (f["bottom"] - ry) for f, (_, ry) in zip(frames, refs)))

    half = math.ceil(max(-left, right))
    need_w = 2 * (half + CELL_PAD)
    need_up = math.ceil(up) + CELL_PAD
    need_down = math.ceil(down) + GROUND_PAD

    warnings = []
    if cell_w is None:
        cell_w = need_w
    elif cell_w < 2 * half:
        warnings.append(f"--cell_w {cell_w}이 좁아 좌우가 최대 {half - cell_w // 2}px 잘린다 (필요: {2 * half})")
    if target_y is None:
        target_y = need_up  # 접지선 = 발 아래 경계가 놓이는 행(위에서부터)
    elif target_y < math.ceil(up):
        warnings.append(f"--target_y {target_y}가 낮아 머리가 최대 {math.ceil(up) - target_y}px 잘린다")
    if cell_h is None:
        cell_h = target_y + need_down
    elif cell_h - target_y < math.ceil(down):
        warnings.append(f"--cell_h {cell_h}가 낮아 아래가 최대 {math.ceil(down) - (cell_h - target_y)}px 잘린다")
    return cell_w, cell_h, target_y, warnings


def render_cells(frames, refs, scale, cell_w, cell_h, target_y):
    px, py = cell_w / 2.0, float(target_y)
    cells = []
    for f, (rx, ry) in zip(frames, refs):
        img = f["image"]
        if scale != 1.0:
            img = img.resize((max(1, round(img.width * scale)), max(1, round(img.height * scale))), Image.LANCZOS)
        canvas = Image.new("RGBA", (cell_w, cell_h))
        canvas.paste(img, (round(px + scale * (f["left"] - rx)), round(py + scale * (f["top"] - ry))))
        cells.append(canvas)
    return cells


# ---------------------------------------------------------------- 프레임 증강

# ---------------------------------------------------------------- 상체 궤적 평활화

STAB_SEARCH = 10       # 상체 위치를 찾을 때 이동 탐색 범위(px)
STAB_TOP, STAB_BOTTOM = 0.08, 0.55   # 상체 비교 영역 (셀 안 인물 키 대비 세로 범위)
STAB_HIP = 0.55        # 이 높이(인물 위에서부터 키 대비)까지는 보정을 다 주고
STAB_FADE = 0.20       # 그 아래 이만큼에 걸쳐 0으로 줄인다 — 다리·발은 그대로


def _gray(cell):
    a = np.asarray(cell).astype(np.float32)
    return a[:, :, :3].mean(2) * (a[:, :, 3] / 255.0)


def upper_body_offsets(cells):
    """원본 셀마다 상체가 0번 셀 대비 얼마나 옮겨졌는지(dx, dy). 상체 영역의 회색조 차이가 최소인 정수 이동."""
    g0 = _gray(cells[0])
    rows = np.where((np.asarray(cells[0])[:, :, 3] > 128).any(1))[0]
    top, bot = rows.min(), rows.max()
    H = bot - top
    y0, y1 = int(top + STAB_TOP * H), int(top + STAB_BOTTOM * H)
    cols = np.where((np.asarray(cells[0])[y0:y1, :, 3] > 128).any(0))[0]
    x0, x1 = max(cols.min() - 4, STAB_SEARCH), min(cols.max() + 4, g0.shape[1] - STAB_SEARCH)
    ref = g0[y0:y1, x0:x1]
    out = []
    for c in cells:
        g = _gray(c)
        best = (1e18, 0, 0)
        for dy in range(-STAB_SEARCH, STAB_SEARCH + 1):
            for dx in range(-STAB_SEARCH, STAB_SEARCH + 1):
                d = float(np.abs(g[y0 + dy:y1 + dy, x0 + dx:x1 + dx] - ref).mean())
                if d < best[0]:
                    best = (d, dx, dy)
        out.append((best[1], best[2]))
    return np.array(out, dtype=np.float32), (top, bot)


def smooth_path(values, loop):
    """루프: 1차 푸리에(평균 + 한 주기 사인) — 숨쉬기처럼 한 번 오르내리는 곡선. 비루프: 앞뒤 1프레임 이동 평균(끝은 그대로)."""
    n = len(values)
    if loop:
        t = 2 * np.pi * np.arange(n) / n
        out = np.empty_like(values)
        for k in range(values.shape[1]):
            v = values[:, k]
            a, b = 2 * (v * np.cos(t)).mean(), 2 * (v * np.sin(t)).mean()
            out[:, k] = v.mean() + a * np.cos(t) + b * np.sin(t)
        return out
    out = values.copy()
    out[1:-1] = (values[:-2] + values[1:-1] + values[2:]) / 3
    return out


def warp_xy(img, dx_rows, dy_rows):
    """행마다 다른 (dx, dy)로 옮긴다: 출력 (x, y) ← 원본 (x - dx[y], y - dy[y]), premultiplied 쌍선형."""
    arr = np.asarray(img).astype(np.float32)
    alpha = arr[:, :, 3:4] / 255.0
    pre = np.concatenate([arr[:, :, :3] * alpha, arr[:, :, 3:4]], axis=2)
    h, w = arr.shape[:2]
    sx = np.arange(w, dtype=np.float32)[None, :] - dx_rows[:, None]
    sy = np.arange(h, dtype=np.float32)[:, None] - dy_rows[:, None] + np.zeros((1, w), np.float32)
    x0, y0 = np.floor(sx).astype(np.int64), np.floor(sy).astype(np.int64)
    tx, ty = (sx - x0)[:, :, None], (sy - y0)[:, :, None]

    def at(yy, xx):
        ok = (xx >= 0) & (xx < w) & (yy >= 0) & (yy < h)
        return pre[np.clip(yy, 0, h - 1), np.clip(xx, 0, w - 1)] * ok[:, :, None]

    out = (at(y0, x0) * (1 - tx) + at(y0, x0 + 1) * tx) * (1 - ty) + (at(y0 + 1, x0) * (1 - tx) + at(y0 + 1, x0 + 1) * tx) * ty
    a = out[:, :, 3:4]
    rgb = np.where(a > 0, out[:, :, :3] / np.maximum(a, 1e-6) * 255.0, 0)
    return Image.fromarray(np.concatenate([rgb, a], axis=2).clip(0, 255).astype(np.uint8))


def stabilize_upper_body(cells, loop):
    """
    AI가 프레임마다 상체를 불규칙한 위치에 그린 것을 부드러운 궤적으로 바로잡는다(발은 정렬로 이미 고정).
    Knight Idle: 원본 8장의 상체 높이가 0,+5,+4,+6,0,−1,−2,−5px로 튀어 보간본까지 떨렸다(사용자 지적 2026-10-14).
    허리 위는 보정량을 다 주고 허리~허벅지에서 0으로 줄인다. 반환: (셀들, 측정값, 보정량)
    """
    meas, (top, bot) = upper_body_offsets(cells)
    target = smooth_path(meas, loop)
    corr = target - meas
    H = bot - top
    ys = np.arange(cells[0].height, dtype=np.float32)
    u = np.clip((ys - (top + STAB_HIP * H)) / (STAB_FADE * H), 0, 1)
    weight = 1 - u * u * (3 - 2 * u)   # 허리 위 1 → 허벅지 0 (smoothstep)
    out = [warp_xy(c, weight * cx, weight * cy) if abs(cx) + abs(cy) >= 0.5 else c for c, (cx, cy) in zip(cells, corr)]
    return out, meas, corr


def match_sharpness(cells, keys):
    """
    보간 셀이 원본 셀보다 흐려 3장 주기로 선명도가 맥동하는 것(세밀한 그림일수록 떨림처럼 보인다)을 언샤프 마스크로 맞춘다.
    목표는 양옆 원본 셀 선명도의 평균.
    """
    from PIL import ImageFilter

    def sharp(c):
        g = _gray(c)
        return float(np.abs(4 * g[1:-1, 1:-1] - g[:-2, 1:-1] - g[2:, 1:-1] - g[1:-1, :-2] - g[1:-1, 2:]).mean())

    key_s = {k: sharp(cells[k]) for k in keys}
    out = list(cells)
    ks = sorted(keys)
    for i, c in enumerate(cells):
        if i in key_s:
            continue
        prev = max([k for k in ks if k < i], default=ks[-1])
        nxt = min([k for k in ks if k > i], default=ks[0])
        target = (key_s[prev] + key_s[nxt]) / 2
        best = c
        for pct in (40, 80, 120, 160, 200):
            s = c.filter(ImageFilter.UnsharpMask(radius=1.2, percent=pct, threshold=0))
            if abs(sharp(s) - target) < abs(sharp(best) - target):
                best = s
        out[i] = best
    return out


def silhouette_change(a, b):
    ma, mb = np.asarray(a)[:, :, 3] > 128, np.asarray(b)[:, :, 3] > 128
    return float((ma ^ mb).sum() / max(1, (ma | mb).sum()))


def adaptive_counts(cells, inbetween, loop):
    """
    원본 구간마다 보간 장수를 자세 변화량에 비례해 정한다(평균 = inbetween, 1~3배 범위).
    같은 장수를 넣으면 크게 움직이는 구간이 화면에서 빨라져 '뚝' 끊겨 보였다(Knight Skill1 런지: 최대 뻗음 → 회수가 3.3배 점프).
    """
    n = len(cells)
    gaps = n if loop else n - 1
    d = np.array([silhouette_change(cells[i], cells[(i + 1) % n]) for i in range(gaps)])
    w = d / max(1e-6, d.mean())
    return [int(np.clip(round(inbetween * x), 1, inbetween * 3)) for x in w]


def augment(cells, inbetween, loop, keep_haze=False, counts=None):
    """
    정렬이 끝난 셀 사이에 RIFE 보간 프레임을 넣는다. 정렬 뒤에 거는 이유: 정렬 전 흔들림까지 보간하면 안 되니까.
    구간마다 흐름 해상도를 바꿔 가며 번짐이 가장 적은 보간본을 쓰고, 그래도 HAZE_CUT을 넘으면 앞 프레임을 반복해
    원본처럼 끊는다(keep_haze면 보간본 유지). 끊김은 플레이에서 눈에 띈다(사용자 확인 2026-10-14) — 마지막 수단이다.
    반환: (셀 목록, 원본 프레임의 새 인덱스, 구간별 [번짐, scale], 끊은 구간의 보간본 {구간: [셀...]})
    """
    sys.path.insert(0, os.path.dirname(__file__))
    from rife.interpolate import Interpolator  # torch는 증강할 때만 불러온다

    rife = Interpolator()
    n = len(cells)
    gaps = n if loop else n - 1
    out, keys, hazes, cut = [], [], [], {}
    for i in range(n):
        keys.append(len(out))
        out.append(cells[i])
        if i >= gaps:
            break
        k = counts[i] if counts is not None else inbetween
        if k == 0:
            hazes.append([0.0, None])
            continue
        mids, scale, worst = rife.inbetweens(cells[i], cells[(i + 1) % n], k)
        if worst > HAZE_CUT and not keep_haze:
            cut[i] = mids
            mids = [cells[i]] * k
        out += mids
        hazes.append([round(worst, 3), scale])
        print(f"  보간 {i}→{(i + 1) % n}: 번짐 {worst:.3f} (흐름 해상도 {scale})" + (" → 끊음" if i in cut else ""))
    return out, keys, hazes, cut


def atlas_grid(frames, cell_w, cell_h):
    """긴 변이 가장 짧은(텍스처 크기가 작은) 열 수. 같으면 빈 칸이 적은 쪽."""
    best = None
    for cols in range(1, frames + 1):
        if cols * cell_w > ATLAS_MAX:
            break
        rows = math.ceil(frames / cols)
        key = (max(cols * cell_w, rows * cell_h), cols * rows - frames)
        if best is None or key < best[0]:
            best = (key, cols, rows)
    if best is None:
        raise PipelineError(f"셀 폭 {cell_w}px이 아틀라스 최대 {ATLAS_MAX}px을 넘는다")
    return best[1], best[2]


# ---------------------------------------------------------------- 미리보기

def fit_width(img, width):
    return img.resize((width, max(1, round(img.height * width / img.width))), Image.LANCZOS)


def checker(size, step=16):
    w, h = size
    yy, xx = np.mgrid[0:h, 0:w]
    tile = (((xx // step) + (yy // step)) % 2).astype(np.uint8)
    arr = np.where(tile[..., None] == 1, 200, 235).astype(np.uint8)
    return Image.fromarray(np.concatenate([arr.repeat(3, axis=2), np.full((h, w, 1), 255, np.uint8)], axis=2))


def build_preview(src, seams, cells, cols, rows, cell_w, cell_h, target_y, path, keys=None, strips=()):
    """keys: 원본 프레임의 셀 번호(증강 시 번호를 빨강으로). strips: [(제목, [셀...])] — 잔상 경고 구간을 크게 본다."""
    width = 1200

    # 1) 원본 + 분할선
    a = checker(src.size)
    a.alpha_composite(src)
    d = ImageDraw.Draw(a)
    row_bounds = seams["rows"]
    for k in range(1, len(row_bounds) - 1):
        d.line(list(zip(range(src.width), row_bounds[k].tolist())), fill=(255, 0, 255), width=3)
    for y0, cb in seams["cols"]:
        for k in range(1, len(cb) - 1):
            d.line([(int(x), y0 + i) for i, x in enumerate(cb[k].tolist())], fill=(0, 200, 255), width=3)

    # 2) 아틀라스 + 셀 경계(회색) + 접지선(빨강) + pivot(파랑)
    atlas = Image.new("RGBA", (cell_w * cols, cell_h * rows))
    for i, cell in enumerate(cells):
        atlas.paste(cell, ((i % cols) * cell_w, (i // cols) * cell_h))
    b = checker(atlas.size)
    b.alpha_composite(atlas)
    d = ImageDraw.Draw(b)
    for i in range(len(cells)):
        ox, oy = (i % cols) * cell_w, (i // cols) * cell_h
        d.rectangle([ox, oy, ox + cell_w - 1, oy + cell_h - 1], outline=(120, 120, 120), width=2)
        d.line([(ox, oy + target_y), (ox + cell_w, oy + target_y)], fill=(255, 0, 0), width=2)
        d.line([(ox + cell_w // 2, oy), (ox + cell_w // 2, oy + cell_h)], fill=(0, 80, 255), width=2)
        d.text((ox + 6, oy + 4), str(i), fill=(220, 0, 0) if keys and i in keys else (0, 0, 0))

    # 3) 겹쳐보기 — 좌우/상하로 튀는 프레임이 번져 보인다
    onion = checker((cell_w, cell_h))
    for cell in cells:
        arr = np.array(cell)
        arr[:, :, 3] = (arr[:, :, 3].astype(np.float32) * (1.6 / len(cells))).clip(0, 255).astype(np.uint8)
        onion.alpha_composite(Image.fromarray(arr))
    d = ImageDraw.Draw(onion)
    d.line([(0, target_y), (cell_w, target_y)], fill=(255, 0, 0), width=2)
    d.line([(cell_w // 2, 0), (cell_w // 2, cell_h)], fill=(0, 80, 255), width=2)

    panels = [fit_width(a, width), fit_width(b, width), onion]

    # 4) 잔상 경고 구간: 원본 A | 보간 ... | 원본 B
    for title, row in strips:
        strip = Image.new("RGBA", (cell_w * len(row), cell_h + 20), (255, 255, 255, 255))
        for k, cell in enumerate(row):
            bg = checker((cell_w, cell_h))
            bg.alpha_composite(cell)
            strip.paste(bg, (k * cell_w, 20))
        ImageDraw.Draw(strip).text((6, 4), title, fill=(200, 0, 0))
        panels.append(fit_width(strip, width) if strip.width > width else strip)
    out = Image.new("RGBA", (width, sum(p.height for p in panels) + 20 * len(panels)), (255, 255, 255, 255))
    y = 0
    for p in panels:
        out.paste(p, ((width - p.width) // 2, y))
        y += p.height + 20
    os.makedirs(os.path.dirname(path), exist_ok=True)
    out.convert("RGB").save(path)


# ---------------------------------------------------------------- 진입점

def character_config_path(character):
    return os.path.join(PROJECT_ROOT, SHEET_ROOT, character, f"{character}.character.json")


def character_align_x(character, action):
    p = character_config_path(character)
    if not os.path.exists(p):
        return None
    with open(p, encoding="utf-8") as fp:
        value = json.load(fp).get("align_x", {}).get(action)
    if value is not None and value not in ALIGN_X:
        raise PipelineError(f"{character}.character.json align_x.{action} = '{value}' — {ALIGN_X} 중 하나여야 한다")
    return value


def character_config(character):
    p = character_config_path(character)
    if not os.path.exists(p):
        return {}
    with open(p, encoding="utf-8") as fp:
        return json.load(fp)


# 캐릭터 폴더 안의 확정 생성 입력 폴더. '~'로 끝나 Unity는 임포트하지 않고 git에는 들어간다.
# 몸 기준 이미지·spec·현재 버전의 처리 입력처럼 다른 PC에서도 있어야 하는 것을 둔다(시도별 결과는 SpriteRegen/에 남긴다).
SOURCE_DIR = "source~"
PATH_SUFFIXES = (".png", ".jpg", ".json")


def _path_values(node, key=""):
    if isinstance(node, dict):
        for k, v in node.items():
            yield from _path_values(v, f"{key}.{k}" if key else k)
    elif isinstance(node, list):
        for i, v in enumerate(node):
            yield from _path_values(v, f"{key}[{i}]")
    elif (isinstance(node, str) and node.lower().endswith(PATH_SUFFIXES) and "/" in node.replace("\\", "/")
          and " " not in node.strip()):  # 경로가 든 설명 문장(note)은 빼고 경로 값만
        yield key, node


def _git_ignored(path):
    import subprocess
    try:
        return subprocess.run(["git", "check-ignore", "-q", path], cwd=PROJECT_ROOT).returncode == 0
    except OSError:
        return path.replace("\\", "/").startswith("SpriteRegen/")


def local_only_refs(character):
    """
    {캐릭터}.character.json이 가리키는 파일 중 다른 PC에는 없을 것 — git 무시 폴더(SpriteRegen/), 다른 PC의 절대 경로, 이 PC에도 없는 파일.
    2026-10-19: Priest의 idle.source(반전본)·지팡이 층이 다른 PC의 SpriteRegen/에만 있어 이 PC에서 대체품을 썼다(사용자: "PC 간 도구 공유가 안 된다").
    확정 입력은 {캐릭터}/source~/ 로 옮겨 커밋한다. 반환: [(키, 경로, 이유)]
    """
    out = []
    for key, p in _path_values(character_config(character)):
        full = p if os.path.isabs(p) else os.path.join(PROJECT_ROOT, p)
        if os.path.isabs(p):
            out.append((key, p, "절대 경로(다른 PC)"))
        elif not os.path.exists(full):
            out.append((key, p, "이 PC에 없음"))
        elif _git_ignored(p):
            out.append((key, p, "git 무시 폴더 — 다른 PC에 없다"))
    return out


def portable_path(path):
    """프로젝트 안 파일이면 루트 기준 상대 경로 — 절대 경로(C:/Users/SSAFY/...)는 다른 PC에서 못 찾는다."""
    full = os.path.abspath(path)
    rel = os.path.relpath(full, PROJECT_ROOT)
    return (full if rel.startswith("..") else rel).replace("\\", "/")


def warn_local_only(character):
    refs = local_only_refs(character)
    for key, p, why in refs:
        print(f"  [경고] {character}.character.json {key} = {p} — {why}. 확정 입력이면 {SHEET_ROOT}/{character}/{SOURCE_DIR}/ 로 옮겨 커밋한다")
    return refs


def chin_to_sole(img):
    """얼굴 피부 아래 끝(턱) ~ 발바닥(px). 스킬 스크립트의 deform.face_chin을 쓴다. 못 찾으면 None."""
    sys.path.insert(0, os.path.join(PROJECT_ROOT, ".claude", "skills", "sprite-animation", "scripts"))
    import deform
    chin = deform.face_chin(img)
    if chin is None:
        return None
    a = np.asarray(img)[:, :, 3] > 128
    return float(np.where(a.any(1))[0].max() - chin)


def face_size(img):
    """얼굴 피부 덩어리(정수리 쪽 첫 덩어리, 턱까지) 면적의 제곱근(px). 자세·키와 무관하게 그림 크기만 따라간다. 못 찾으면 None."""
    sys.path.insert(0, os.path.join(PROJECT_ROOT, ".claude", "skills", "sprite-animation", "scripts"))
    import deform
    chin = deform.face_chin(img)
    if chin is None:
        return None
    skin = deform.skin_mask(img)
    xs = np.where((np.asarray(img)[:, :, 3] > 128).any(0))[0]
    cx = int(xs.mean())
    band = skin[:chin + 1, max(0, cx - img.width // 6): cx + img.width // 6]
    rows = np.where(band.sum(1) > 8)[0]
    if not len(rows):
        return None
    return float(np.sqrt(band[rows[0]:].sum()))


def scale_frame(f, s):
    """프레임을 두 발 중점·바닥 기준으로 s배 한다(좌표는 그 기준으로 같이 옮긴다)."""
    cx = (f["feet"][0] + f["feet"][1]) / 2
    im = f["image"]
    f["image"] = im.resize((max(1, round(im.width * s)), max(1, round(im.height * s))), Image.LANCZOS)
    f["left"] = cx + (f["left"] - cx) * s
    f["right"] = f["left"] + f["image"].width
    f["top"] = f["bottom"] - f["image"].height
    f["feet"] = (cx + (f["feet"][0] - cx) * s, cx + (f["feet"][1] - cx) * s)
    f["feet_x"] = cx + (f["feet_x"] - cx) * s


def equalize_parts(frames, n_parts):
    """
    여러 장으로 나눠 생성하면 장마다 인물을 다른 크기로 그린다(Knight Hit: 둘째 장 머리가 첫 장보다 +15~20%,
    사용자 지적 2026-10-15). 장별 얼굴 크기 중앙값을 첫 장에 맞춰 그 장의 프레임을 키우거나 줄인다.
    반환: 장별 배율 목록
    """
    per = len(frames) // n_parts
    meds = []
    for k in range(n_parts):
        v = [x for x in (face_size(f["image"]) for f in frames[k * per:(k + 1) * per]) if x]
        meds.append(float(np.median(v)) if len(v) >= 2 else None)
    factors = [1.0 if (m is None or meds[0] is None) else meds[0] / m for m in meds]
    for k, s in enumerate(factors):
        # 얼굴이 거의 안 보이는 장(엎드림 등)은 얼굴 크기를 잘못 잰다(Knight Dead 셋째 장: 1.33배) — 큰 차이는 믿지 않는다
        if PART_EQ_MIN < abs(s - 1) <= PART_EQ_MAX:
            for f in frames[k * per:(k + 1) * per]:
                scale_frame(f, s)
        else:
            factors[k] = 1.0
    return [round(s, 3) for s in factors]


def _fit_mask(img, s, w, h, dx=0):
    im = img.resize((max(1, round(img.width * s)), max(1, round(img.height * s))), Image.BILINEAR)
    c = Image.new("L", (w, h))
    c.paste(im.split()[3], ((w - im.width) // 2 + dx, h - im.height))
    return np.asarray(c) > 128


def size_fit(img, scale, character, name):
    """
    턱~발바닥으로 맞춰도 AI가 시트마다 머리·몸통 부피를 다르게 그려 동작이 바뀔 때 크기가 튄다
    (Knight: 0번 준비 자세가 Idle보다 2~6% 크게 보였다, 사용자 지적 2026-10-15 "애니메이션별로 크기가 제각각").
    기준 프레임을 기준 시트(character.json reference) 0번 실루엣에 겹쳐 IoU가 가장 큰 배율을 곱한다.
    반환: (보정 배율, 정보 dict 또는 None)
    """
    ref_name = character_config(character).get("reference")
    if not ref_name or ref_name == name:
        return 1.0, None
    ref_png = os.path.join(PROJECT_ROOT, SHEET_ROOT, character, ref_name + ".png")
    if not os.path.exists(ref_png):
        return 1.0, None
    with open(ref_png[:-4] + ".json", encoding="utf-8") as fp:
        rm = json.load(fp)
    ref = Image.open(ref_png).convert("RGBA").crop((0, 0, rm["cellWidth"], rm["cellHeight"]))
    ref = ref.crop(ref.getbbox())
    half = 0.5  # 반 크기로 비교 (속도)
    W, H = round(max(ref.width, img.width * scale) * 1.4 * half), round(max(ref.height, img.height * scale) * 1.3 * half)
    rmask = _fit_mask(ref, half, W, H)
    best = (0.0, 1.0)
    for f in np.arange(SIZE_FIT_RANGE[0], SIZE_FIT_RANGE[1] + 1e-6, 0.01):
        for dx in range(-12, 13, 4):
            m = _fit_mask(img, scale * f * half, W, H, dx)
            iou = np.logical_and(rmask, m).sum() / max(1, np.logical_or(rmask, m).sum())
            if iou > best[0]:
                best = (float(iou), float(f))
    info = {"reference": ref_name, "factor": round(best[1], 3), "iou": round(best[0], 3)}
    if best[0] < SIZE_FIT_MIN_IOU:
        info["skipped"] = "기준 프레임 자세가 기준 시트와 너무 달라 보정하지 않았다"
        return 1.0, info
    return best[1], info


def resolve_scale(args, character, anchor_height, analyze):
    """
    캐릭터 기준 키(ref_height)를 한 곳에 둬서 시트마다 다른 AI 그림 크기를 같은 체급으로 맞춘다.
    ref_height는 기준 시트(보통 Idle) 0번 프레임의 standing_height이고, 출력(게임) 픽셀 단위다.
    """
    if args.scale is not None:
        return args.scale, None
    cfg_path = character_config_path(character)
    if os.path.exists(cfg_path):
        with open(cfg_path, encoding="utf-8") as fp:
            cfg = json.load(fp)
        if "ref_height" not in cfg:
            # deform.py accept가 만든 새 캐릭터 설정 — 게임 내 키(ref_height)를 정하기 전이다
            raise PipelineError(f"{character} 기준 키(ref_height)가 아직 없다 — "
                                f"sheet_check.py set-height --character {character} --relative-to <캐릭터> --sheet <Idle AI 시트>를 먼저 한다")
        if cfg.get("ref_method") != "standing":
            raise PipelineError(f"{character} 기준 키가 예전 측정 방식(세로 키)이다 — "
                                f"기준 시트를 지정해 다시 잰다: sheet_check.py set-reference <기준 시트>")
        return cfg["ref_height"] / anchor_height, None
    if not analyze:
        os.makedirs(os.path.dirname(cfg_path), exist_ok=True)
        with open(cfg_path, "w", encoding="utf-8") as fp:
            json.dump({"ref_height": round(anchor_height, 1), "ref_method": "standing", "reference": args.name}, fp, indent=2)
    return 1.0, f"{character} 기준 키가 없어 이 시트({args.name})를 기준으로 삼았다 (키 {anchor_height:.1f}px)"


def run(args):
    m = NAME_PATTERN.match(args.name)
    if not m:
        raise PipelineError(f"이름 규칙 위반: '{args.name}' — {{캐릭터}}_{{Idle|Hit|Skill1~9|Dead}}_v{{N}} (예: Archer_Skill1_v1)")
    character, action, version = m.group(1), m.group(2), int(m.group(3))
    warn_local_only(character)
    rule = action_rule(action)
    align_x = args.align_x or character_align_x(character, action) or rule["align_x"]
    align_y = args.align_y or rule["align_y"]
    frames_n = args.frames or args.cols * args.rows
    if not 1 <= frames_n <= args.cols * args.rows:
        raise PipelineError(f"--frames {frames_n}이 그리드 {args.cols}x{args.rows}와 맞지 않는다")
    if not 0 <= args.anchor < frames_n:
        raise PipelineError(f"--anchor {args.anchor}가 프레임 범위를 벗어난다")
    if args.row_split_y and len(args.row_split_y) != args.rows - 1:
        raise PipelineError(f"--row_split_y는 {args.rows - 1}개가 필요하다")
    inputs = args.input
    args.input = inputs[0]
    for f in inputs:
        if not os.path.exists(f):
            raise PipelineError(f"입력 파일이 없다: {f}")
    if not os.path.exists(args.input):
        raise PipelineError(f"입력 파일이 없다: {args.input}")

    src = Image.open(args.input).convert("RGBA")  # 입력과 출력이 같은 파일이어도 여기서 메모리로 다 읽는다
    if len(inputs) > 1:
        # 여러 장을 세로로 이어 한 시트로: 큰 동작은 칸이 넓어야 해서 6장씩 나눠 생성한다(Knight Skill1 런지, 검이 옆 칸에 닿음).
        # --rows는 이어 붙인 전체 행 수
        parts = [Image.open(f).convert("RGBA") for f in inputs]
        w = max(pt.width for pt in parts)
        joined = Image.new("RGBA", (w, sum(pt.height for pt in parts)))
        y = 0
        for pt in parts:
            joined.paste(pt.resize((w, round(pt.height * w / pt.width))) if pt.width != w else pt, (0, y))
            y += pt.height if pt.width == w else round(pt.height * w / pt.width)
        src = joined.crop((0, 0, w, y))
    rgba = np.array(src)
    frames, seams, warnings = extract_frames(rgba, args.cols, args.rows, frames_n, args.row_split_y, not args.keep_noise)
    part_scale = None
    if len(inputs) > 1 and frames_n % len(inputs) == 0 and not args.no_size_fit:
        part_scale = equalize_parts(frames, len(inputs))
        if any(s != 1.0 for s in part_scale):
            print("  장별 크기 맞춤:", part_scale)

    anchor_height, stance = standing_height(frames[args.anchor]["image"])
    scale, note = resolve_scale(args, character, anchor_height, args.analyze)
    chin_ref = character_config(character).get("ref_chin_to_sole")
    if args.scale is None and chin_ref:
        # 턱~발바닥으로 크기를 맞춘다: 다리를 편 키는 바닥까지 내려온 검을 발로 잡아 틀렸다(Knight Skill2: 게임 내 81%).
        # 턱~발바닥은 머리카락·검·보폭에 흔들리지 않는다. ref_chin_to_sole = 기준 Idle 출력 시트 0번 프레임의 값(px)
        chin_len = chin_to_sole(frames[args.anchor]["image"])
        if chin_len:
            scale = chin_ref / chin_len
    fit = None
    if args.scale is None and not args.no_size_fit:
        f, fit = size_fit(frames[args.anchor]["image"], scale, character, args.name)
        scale *= f
        if fit and "skipped" in fit:
            warnings.append(f"크기 보정 건너뜀 — 기준 프레임 {args.anchor}번이 {fit['reference']} 0번과 IoU {fit['iou']} (기준 {SIZE_FIT_MIN_IOU})")
    if note:
        warnings.append(note)

    refs = reference_points(frames, args.anchor, align_x, align_y)
    if align_x == "both_feet":
        warnings += pin_both_feet(frames, refs, args.anchor)
    slide = foot_slide(frames, refs, scale)
    cell_w, cell_h, target_y, layout_warn = layout(frames, refs, scale, args.cell_w, args.cell_h, args.target_y)
    warnings += layout_warn
    cells = render_cells(frames, refs, scale, cell_w, cell_h, target_y)

    loop = rule["loop"] if args.loop is None else args.loop == "true"
    stab = None
    if args.stabilize:
        cells, meas, corr = stabilize_upper_body(cells, loop)
        stab = {"measured": meas.round(1).tolist(), "correction": corr.round(1).tolist()}
        print("  상체 위치(dx,dy):", [tuple(m) for m in meas.round(1)], "→ 보정", [tuple(c) for c in corr.round(1)])
    keys, hazes, strips, cut = list(range(len(cells))), [], [], {}
    if args.inbetween > 0:
        counts = adaptive_counts(cells, args.inbetween, loop) if args.even_speed else None
        if args.gap_counts:
            # 완급: 구간마다 보간 장수를 직접 준다. 터프한 동작은 타격 구간을 0~1장으로 순식간에, 준비·회수는 여러 장으로.
            # 전 구간을 고르게 보간하면 발레처럼 부드러워 보였다(Knight Skill1, 사용자 지적 2026-10-15)
            n_gaps = frames_n if loop else frames_n - 1
            if len(args.gap_counts) != n_gaps:
                raise PipelineError(f"--gap_counts는 {n_gaps}개가 필요하다 (원본 프레임 사이 구간 수)")
            counts = args.gap_counts
        if counts:
            print("  구간별 보간 장수:", counts)
        cells, keys, hazes, cut = augment(cells, args.inbetween, loop, args.keep_haze, counts)
        cells = match_sharpness(cells, keys)
        for i, (g, _) in enumerate(hazes):
            if g > HAZE_CUT:
                j = (i + 1) % frames_n
                mids = cut.get(i, cells[keys[i] + 1:keys[i + 1] if i + 1 < len(keys) else len(cells)])
                if i in cut:
                    warnings.append(f"보간 {i}→{j} 번짐 {g:.3f} (기준 {HAZE_CUT}) — 보간하지 않고 원본처럼 끊었다. "
                                    f"버린 보간본은 미리보기 아래 칸에 있다 (쓰려면 --keep_haze)")
                else:
                    warnings.append(f"보간 {i}→{j} 번짐 {g:.3f} (기준 {HAZE_CUT}) — 미리보기 아래 칸에서 두 겹으로 보이는지 확인한다")
                strips.append((f"haze {i}->{j}  {g:.3f}" + ("  (cut)" if i in cut else ""),
                               [cells[keys[i]]] + mids + [cells[keys[j]]]))
    out_cols, out_rows = atlas_grid(len(cells), cell_w, cell_h)

    preview = os.path.join(PROJECT_ROOT, PREVIEW_DIR, f"{args.name}_preview.png")
    build_preview(src, seams, cells, out_cols, out_rows, cell_w, cell_h, target_y, preview,
                  keys if args.inbetween > 0 else None, strips)

    manifest = {
        "name": args.name,
        "character": character,
        "action": action,
        "version": version,
        "source": portable_path(args.input),
        "sources": [portable_path(f) for f in inputs] if len(inputs) > 1 else None,
        "cols": out_cols,   # 출력 아틀라스 그리드 (Unity가 이걸로 자른다)
        "rows": out_rows,
        "frames": len(cells),
        "sourceGrid": {"cols": args.cols, "rows": args.rows, "frames": frames_n},
        "inbetween": args.inbetween,
        "keyFrames": keys,  # 원본 프레임이 놓인 셀 번호. 나머지는 RIFE 보간
        "haze": hazes,     # 원본 구간별 [보간 번짐 지표, 고른 흐름 해상도] (번짐이 클수록 두 겹·안개로 보인다)
        "hazeCut": sorted(cut),
        "stabilize": stab,  # 상체 궤적 평활화: 원본 셀별 상체 위치(측정)와 보정량 (px, 0번 셀 기준)  # 번짐 기준을 넘어 보간 대신 앞 프레임을 반복한 구간 (구간 i = 원본 i→i+1)
        "cellWidth": cell_w,
        "cellHeight": cell_h,
        "pivotX": 0.5,
        "pivotY": (cell_h - target_y) / cell_h,  # 접지선은 발 아래 경계 — 아래에서 (cell_h - target_y) px
        "fps": (args.fps or rule["fps"]) * (args.inbetween + 1),  # 원본 프레임은 원래 시각에 나온다
        # 프레임별 표시 시간(초). 주면 Unity 클립이 균일 간격 대신 이 길이를 쓴다(완급 — 준비 자세 멈춤, 빠른 휘두름)
        "durations": [round(d, 4) for d in args.durations] if args.durations else None,
        "loop": loop,
        "scale": round(scale, 4),
        "sizeFit": fit,
        "partScale": part_scale,  # 여러 장 입력일 때 장별 얼굴 크기를 첫 장에 맞춘 배율  # 기준 시트 0번 실루엣에 맞춘 보정(factor는 scale에 이미 곱해짐)
        "anchorHeight": round(anchor_height, 1),  # 기준 프레임 standing_height (원본 픽셀)
        "stance": stance,
        "alignX": align_x,
        "alignY": align_y,
        "footSlide": slide,  # 정렬 후 발별 미끄러짐 폭(출력 px, 화면 왼쪽/오른쪽 발). 고정한 발은 0에 가까워야 한다
        "warnings": warnings,
    }

    for f in frames:
        print(f"  frame {f['index']}: x[{f['left']:.0f},{f['right']:.0f}) y[{f['top']:.0f},{f['bottom']:.0f}) feet_x={f['feet_x']:.0f}")
    for w in warnings:
        print(f"  [경고] {w}")

    if args.hold and not args.durations:
        # 원본 프레임 몇 장을 더 오래 보여 준다(준비 자세·임팩트 멈춤). 나머지는 1/fps
        base = 1.0 / ((args.fps or rule["fps"]) * (args.inbetween + 1))
        durs = [base] * len(cells)
        for h in args.hold:
            src_i, sec = h.split(":")
            durs[keys[int(src_i)]] = float(sec)
        args.durations = durs
        manifest["durations"] = [round(d, 4) for d in durs]
    if args.durations and len(args.durations) != len(cells):
        raise PipelineError(f"--durations {len(args.durations)}개, 프레임 {len(cells)}개")
    sheet_rel = f"{args.out_dir or SHEET_ROOT + '/' + character}/{args.name}.png"
    if not args.analyze:
        atlas = Image.new("RGBA", (cell_w * out_cols, cell_h * out_rows))
        for i, cell in enumerate(cells):
            atlas.paste(cell, ((i % out_cols) * cell_w, (i // out_cols) * cell_h))
        out_png = os.path.join(PROJECT_ROOT, sheet_rel)
        os.makedirs(os.path.dirname(out_png), exist_ok=True)
        atlas.save(out_png)
        with open(os.path.splitext(out_png)[0] + ".json", "w", encoding="utf-8") as fp:
            json.dump(manifest, fp, ensure_ascii=False, indent=2)

    return {
        "ok": True,
        "analyze": args.analyze,
        "sheet": None if args.analyze else sheet_rel,
        "preview": preview.replace("\\", "/"),
        "next": None if args.analyze else f"unity cmd eval 'return SpriteAnimationPipeline.Apply(\"{sheet_rel}\");'",
        **{k: manifest[k] for k in ("cellWidth", "cellHeight", "pivotX", "pivotY", "fps", "loop", "scale", "alignX", "alignY", "footSlide", "frames", "haze", "warnings")},
    }


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--input", required=True, nargs="+", help="원본 스프라이트 시트 (여러 장이면 세로로 이어 붙인다)")
    p.add_argument("--name", required=True, help="{캐릭터}_{액션}_v{N}")
    p.add_argument("--cols", type=int, default=4)
    p.add_argument("--rows", type=int, default=2)
    p.add_argument("--frames", type=int, default=None, help="기본 cols*rows")
    p.add_argument("--anchor", type=int, default=0, help="기준 프레임 (서 있는 프레임)")
    p.add_argument("--align_x", choices=ALIGN_X, default=None, help="기본값은 캐릭터 설정 align_x → 액션 규칙")
    p.add_argument("--align_y", choices=["ground", "anchor"], default=None, help="기본값은 액션 규칙")
    p.add_argument("--scale", type=float, default=None, help="기본값은 캐릭터 기준 키 / 기준 프레임 높이")
    p.add_argument("--cell_w", type=int, default=None, help="기본값은 자동")
    p.add_argument("--cell_h", type=int, default=None, help="기본값은 자동")
    p.add_argument("--target_y", type=int, default=None, help="접지선 (셀 위에서부터 px), 기본값은 자동")
    p.add_argument("--row_split_y", type=int, nargs="*", default=None, help="자동 분할 대신 직선 행 경계")
    p.add_argument("--fps", type=int, default=None, help="원본 프레임 기준. 증강하면 (inbetween+1)배가 된다")
    p.add_argument("--inbetween", type=int, default=DEFAULT_INBETWEEN, help="원본 프레임 사이 보간 장수 (0 = 증강 안 함)")
    p.add_argument("--stabilize", action="store_true", help="상체 위치를 부드러운 궤적으로 바로잡는다 (작게 움직이는 Idle용)")
    p.add_argument("--durations", type=float, nargs="+", help="프레임별 표시 시간(초). 출력 프레임 수와 같아야 한다")
    p.add_argument("--out_dir", help="캐릭터 폴더 대신 여기에 쓴다 (비교·시험용, 예: Assets/_/_Compare)")
    p.add_argument("--gap_counts", type=int, nargs="+", help="원본 구간별 보간 장수 (0 = 보간 없이 바로 다음 원본)")
    p.add_argument("--hold", nargs="+", help="원본프레임:초 — 그 원본 프레임을 이 시간만큼 보여 준다 (예: 2:0.15 6:0.2)")
    p.add_argument("--even_speed", action="store_true", help="구간별 보간 장수를 자세 변화량에 비례하게 (큰 동작의 끊김 방지)")
    p.add_argument("--keep_haze", action="store_true", help="번짐 기준을 넘는 구간도 끊지 않고 보간본을 쓴다")
    p.add_argument("--loop", choices=["true", "false"], default=None)
    p.add_argument("--keep_noise", action="store_true", help="작은 부스러기 제거를 끈다")
    p.add_argument("--no_size_fit", action="store_true", help="기준 시트 0번 실루엣에 맞추는 크기 보정을 끈다")
    p.add_argument("--analyze", action="store_true", help="측정과 미리보기만 하고 에셋은 쓰지 않는다")
    args = p.parse_args()

    try:
        result = run(args)
    except PipelineError as e:
        print(f"RESULT {json.dumps({'ok': False, 'error': str(e)}, ensure_ascii=False)}")
        sys.exit(1)
    print(f"RESULT {json.dumps(result, ensure_ascii=False)}")


if __name__ == "__main__":
    main()
