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

# align_x  feet   : 프레임마다 발 중심을 pivot에 맞춘다 (제자리 모션의 좌우 흔들림 제거)
#          anchor : 기준 프레임의 발 중심 하나로 전 프레임을 같은 양만큼 옮긴다 (원본의 이동을 보존)
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


def extract_frames(rgba, cols, rows, frames, row_splits, clean_noise):
    h, w = rgba.shape[:2]
    alpha = rgba[:, :, 3].astype(np.float64) / 255.0
    fg = rgba[:, :, 3] > ALPHA_THRESHOLD
    yy = np.arange(h)[:, None]
    xx = np.arange(w)[None, :]
    cell_w, cell_h = w / cols, h / rows

    row_bounds, row_cross = split_rows(alpha, rows, row_splits)
    warnings = []
    for k, n in enumerate(row_cross, start=1):
        if n > SEAM_OPAQUE_WARN:
            warnings.append(f"{k - 1}행↔{k}행 겹침: 경계선이 불투명 픽셀 {n}개를 자른다")

    seams = {"rows": row_bounds, "cols": []}
    result = []
    for r in range(rows):
        row_mask = (yy >= row_bounds[r][None, :]) & (yy < row_bounds[r + 1][None, :])
        y0, y1 = int(row_bounds[r].min()), int(row_bounds[r + 1].max())
        col_bounds, col_cross = split_cols(alpha, row_mask, cols, y0, y1)
        seams["cols"].append((y0, col_bounds))
        for k, n in enumerate(col_cross, start=1):
            if n > SEAM_OPAQUE_WARN and r * cols + k < frames:
                warnings.append(f"프레임 {r * cols + k - 1}↔{r * cols + k} 겹침: 경계선이 불투명 픽셀 {n}개를 자른다")

        for c in range(cols):
            idx = r * cols + c
            if idx >= frames:
                break
            col_mask = np.zeros((h, w), dtype=bool)
            left = col_bounds[c][:, None]
            right = col_bounds[c + 1][:, None]
            col_mask[y0:y1] = (xx >= left) & (xx < right)
            mask = fg & row_mask & col_mask
            if clean_noise:
                mask, _ = remove_small_components(mask, NOISE_MIN_AREA)
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
            result.append({
                "index": idx,
                "image": Image.fromarray(img),
                "left": x0 - ox, "right": x1 + 1 - ox,
                "top": top - oy, "bottom": bottom + 1 - oy,
                "feet_x": float(xs[band].mean()) - ox,
            })
    return result, seams, warnings


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
    refs = []
    for f in frames:
        rx = f["feet_x"] if align_x == "feet" else a["feet_x"]
        ry = f["bottom"] if align_y == "ground" else a["bottom"]
        refs.append((rx, ry))
    return refs


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


# ---------------------------------------------------------------- 미리보기

def fit_width(img, width):
    return img.resize((width, max(1, round(img.height * width / img.width))), Image.LANCZOS)


def checker(size, step=16):
    w, h = size
    yy, xx = np.mgrid[0:h, 0:w]
    tile = (((xx // step) + (yy // step)) % 2).astype(np.uint8)
    arr = np.where(tile[..., None] == 1, 200, 235).astype(np.uint8)
    return Image.fromarray(np.concatenate([arr.repeat(3, axis=2), np.full((h, w, 1), 255, np.uint8)], axis=2))


def build_preview(src, seams, cells, cols, rows, cell_w, cell_h, target_y, path):
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
        d.text((ox + 6, oy + 4), str(i), fill=(0, 0, 0))

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
    rule = action_rule(action)
    align_x = args.align_x or rule["align_x"]
    align_y = args.align_y or rule["align_y"]
    frames_n = args.frames or args.cols * args.rows
    if not 1 <= frames_n <= args.cols * args.rows:
        raise PipelineError(f"--frames {frames_n}이 그리드 {args.cols}x{args.rows}와 맞지 않는다")
    if not 0 <= args.anchor < frames_n:
        raise PipelineError(f"--anchor {args.anchor}가 프레임 범위를 벗어난다")
    if args.row_split_y and len(args.row_split_y) != args.rows - 1:
        raise PipelineError(f"--row_split_y는 {args.rows - 1}개가 필요하다")
    if not os.path.exists(args.input):
        raise PipelineError(f"입력 파일이 없다: {args.input}")

    src = Image.open(args.input).convert("RGBA")  # 입력과 출력이 같은 파일이어도 여기서 메모리로 다 읽는다
    rgba = np.array(src)
    frames, seams, warnings = extract_frames(rgba, args.cols, args.rows, frames_n, args.row_split_y, not args.keep_noise)

    anchor_height, stance = standing_height(frames[args.anchor]["image"])
    scale, note = resolve_scale(args, character, anchor_height, args.analyze)
    if note:
        warnings.append(note)

    refs = reference_points(frames, args.anchor, align_x, align_y)
    cell_w, cell_h, target_y, layout_warn = layout(frames, refs, scale, args.cell_w, args.cell_h, args.target_y)
    warnings += layout_warn
    cells = render_cells(frames, refs, scale, cell_w, cell_h, target_y)

    preview = os.path.join(PROJECT_ROOT, PREVIEW_DIR, f"{args.name}_preview.png")
    build_preview(src, seams, cells, args.cols, args.rows, cell_w, cell_h, target_y, preview)

    manifest = {
        "name": args.name,
        "character": character,
        "action": action,
        "version": version,
        "source": os.path.abspath(args.input).replace("\\", "/"),
        "cols": args.cols,
        "rows": args.rows,
        "frames": frames_n,
        "cellWidth": cell_w,
        "cellHeight": cell_h,
        "pivotX": 0.5,
        "pivotY": (cell_h - target_y) / cell_h,  # 접지선은 발 아래 경계 — 아래에서 (cell_h - target_y) px
        "fps": args.fps or rule["fps"],
        "loop": rule["loop"] if args.loop is None else args.loop == "true",
        "scale": round(scale, 4),
        "anchorHeight": round(anchor_height, 1),  # 기준 프레임 standing_height (원본 픽셀)
        "stance": stance,
        "alignX": align_x,
        "alignY": align_y,
        "warnings": warnings,
    }

    for f in frames:
        print(f"  frame {f['index']}: x[{f['left']:.0f},{f['right']:.0f}) y[{f['top']:.0f},{f['bottom']:.0f}) feet_x={f['feet_x']:.0f}")
    for w in warnings:
        print(f"  [경고] {w}")

    sheet_rel = f"{SHEET_ROOT}/{character}/{args.name}.png"
    if not args.analyze:
        atlas = Image.new("RGBA", (cell_w * args.cols, cell_h * args.rows))
        for i, cell in enumerate(cells):
            atlas.paste(cell, ((i % args.cols) * cell_w, (i // args.cols) * cell_h))
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
        **{k: manifest[k] for k in ("cellWidth", "cellHeight", "pivotX", "pivotY", "fps", "loop", "scale", "alignX", "alignY", "warnings")},
    }


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--input", required=True, help="원본 스프라이트 시트")
    p.add_argument("--name", required=True, help="{캐릭터}_{액션}_v{N}")
    p.add_argument("--cols", type=int, default=4)
    p.add_argument("--rows", type=int, default=2)
    p.add_argument("--frames", type=int, default=None, help="기본 cols*rows")
    p.add_argument("--anchor", type=int, default=0, help="기준 프레임 (서 있는 프레임)")
    p.add_argument("--align_x", choices=["feet", "anchor"], default=None, help="기본값은 액션 규칙")
    p.add_argument("--align_y", choices=["ground", "anchor"], default=None, help="기본값은 액션 규칙")
    p.add_argument("--scale", type=float, default=None, help="기본값은 캐릭터 기준 키 / 기준 프레임 높이")
    p.add_argument("--cell_w", type=int, default=None, help="기본값은 자동")
    p.add_argument("--cell_h", type=int, default=None, help="기본값은 자동")
    p.add_argument("--target_y", type=int, default=None, help="접지선 (셀 위에서부터 px), 기본값은 자동")
    p.add_argument("--row_split_y", type=int, nargs="*", default=None, help="자동 분할 대신 직선 행 경계")
    p.add_argument("--fps", type=int, default=None)
    p.add_argument("--loop", choices=["true", "false"], default=None)
    p.add_argument("--keep_noise", action="store_true", help="작은 부스러기 제거를 끈다")
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
