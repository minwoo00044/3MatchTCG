"""sprite-animation 스킬 스크립트 공용 도우미."""
import glob
import json
import os
import re
import sys

import numpy as np
from PIL import Image


def project_root():
    """scripts/process_sprite_sheet.py가 있는 상위 폴더 = Unity 프로젝트 루트."""
    d = os.path.abspath(os.path.dirname(__file__))
    while True:
        if os.path.exists(os.path.join(d, "scripts", "process_sprite_sheet.py")):
            return d
        parent = os.path.dirname(d)
        if parent == d:
            sys.exit("프로젝트 루트(scripts/process_sprite_sheet.py)를 찾지 못했다")
        d = parent


ROOT = project_root()
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import process_sprite_sheet as P  # noqa: E402  파이프라인과 같은 분할 규칙을 쓴다

SHEET_ROOT = os.path.normpath(os.path.join(ROOT, P.SHEET_ROOT))
REGEN_ROOT = os.path.join(ROOT, "SpriteRegen")
PREVIEW_DIR = os.path.normpath(os.path.join(ROOT, P.PREVIEW_DIR))


def utf8_stdout():
    sys.stdout.reconfigure(encoding="utf-8")


def load_frames(path, cols=None, rows=None, frames=None):
    """시트를 파이프라인과 같은 seam 분할로 자른다. 옆에 매니페스트가 있으면 그리드를 거기서 읽는다."""
    manifest = os.path.splitext(path)[0] + ".json"
    if cols is None and os.path.basename(os.path.dirname(os.path.abspath(path))) == "design":
        # 캐릭터 design/ 폴더의 인물 그림 한 장(예: design/Archer_apose.png) — 기준 모델로 쓴다.
        # 이름으로 가리면 Codex 결과 시트(result.png)까지 한 장으로 읽혀 검증이 전부 틀린다
        img = Image.open(path).convert("RGBA")
        a = np.array(img)
        a[a[:, :, 3] <= 30] = 0
        img = crop_frame(Image.fromarray(a))
        alpha = np.array(img)[:, :, 3] > 128
        ys, xs = np.where(alpha)
        band = ys >= ys.max() - max(4, (ys.max() - ys.min()) // 15)
        return [{"index": 0, "image": img, "left": 0, "right": img.width, "top": 0, "bottom": img.height,
                 "feet_x": float(xs[band].mean()), "feet": (float(xs[band].min()), float(xs[band].max()))}], []
    if os.path.exists(manifest) and cols is None:
        with open(manifest, encoding="utf-8") as fp:
            m = json.load(fp)
        cols, rows, frames = m["cols"], m["rows"], m["frames"]
    cols, rows = cols or 4, rows or 2
    frames = frames or cols * rows
    rgba = np.array(Image.open(path).convert("RGBA"))
    fr, _, warnings = P.extract_frames(rgba, cols, rows, frames, None, True)
    return fr, warnings


def latest_sheet(character, action):
    """Spirte/{캐릭터}/ 에서 해당 액션의 최신 버전 시트 (prev/ 제외)."""
    pat = re.compile(rf"^{character}_{action}_v(\d+)\.png$")
    best = None
    for p in glob.glob(os.path.join(SHEET_ROOT, character, "*.png")):
        m = pat.match(os.path.basename(p))
        if m and (best is None or int(m.group(1)) > best[0]):
            best = (int(m.group(1)), p)
    return best[1] if best else None


def resolve_original(character, action):
    """
    사용자가 그 액션의 첫 버전(보통 v1, prev/ 포함)으로 넣은 원본 파일 = 그 매니페스트의 source.
    없으면 원본이 없는 것이다 — 다른 곳(Downloads 등)을 찾지 않는다. 반환: (경로 또는 None, 사유)
    """
    pat = re.compile(rf"^{character}_{action}_v(\d+)\.json$")
    found = []
    for p in glob.glob(os.path.join(SHEET_ROOT, character, "**", "*.json"), recursive=True):
        m = pat.match(os.path.basename(p))
        if m:
            found.append((int(m.group(1)), p))
    if not found:
        return None, f"{character}_{action} 시트가 없다"
    version, manifest = min(found)
    with open(manifest, encoding="utf-8") as fp:
        src = json.load(fp).get("source")
    if src and not os.path.isabs(src):
        src = os.path.join(ROOT, src)  # 매니페스트는 프로젝트 루트 기준 상대 경로로 적는다(PC 간 공유)
    if not src or not os.path.exists(src):
        return None, f"{character}_{action}_v{version}로 넣은 원본 파일이 없다 ({src})"
    return src, None


def next_version_name(character, action):
    """prev/ 까지 포함한 최고 버전 + 1."""
    pat = re.compile(rf"^{character}_{action}_v(\d+)\.png$")
    top = 0
    for p in glob.glob(os.path.join(SHEET_ROOT, character, "**", "*.png"), recursive=True):
        m = pat.match(os.path.basename(p))
        if m:
            top = max(top, int(m.group(1)))
    return f"{character}_{action}_v{top + 1}"


def crop_frame(img):
    a = np.array(img)[:, :, 3] > 128
    ys, xs = np.where(a)
    return img.crop((xs.min(), ys.min(), xs.max() + 1, ys.max() + 1))


# ---------------------------------------------------------------- 크로마키
# Codex 편집 결과를 흰 배경으로 받아 '가장자리에서 이어진 흰색'만 지우면, 몸에 둘러싸인 배경(지팡이·팔·몸 사이, 다리 사이)이
# 흰색으로 남는다. 흰 옷이 넓은 캐릭터는 색 통계로도 못 가른다 — Priest v3 "누끼가 덜 따졌다"(2026-10-19).
# 그래서 캐릭터에 없는 색 배경으로 받아 그림 전체에서 지운다. 캐릭터별 색은 character.json design.key_color.
KEY_COLORS = {"green": (0, 255, 0), "magenta": (255, 0, 255)}
KEY_SOFT = (70.0, 150.0)  # 키 색과의 거리: 이 아래는 투명, 위는 불투명, 사이는 반투명(경계 섞임)


def key_color(character):
    """character.json design.key_color (green|magenta). 기본 green — 초록이 있는 캐릭터(Archer 머리카락)는 magenta."""
    p = os.path.join(SHEET_ROOT, character, f"{character}.character.json")
    name = "green"
    if os.path.exists(p):
        with open(p, encoding="utf-8") as fp:
            name = json.load(fp).get("design", {}).get("key_color", "green")
    if name not in KEY_COLORS:
        sys.exit(f"{character} design.key_color = '{name}' — {list(KEY_COLORS)} 중 하나")
    return name


def key_out(img, name="green"):
    """
    키 색 배경을 그림 전체에서 투명하게(갇힌 칸 포함), 경계는 거리에 따라 반투명, 키 색 번짐(spill)은 뺀다.
    green: G를 max(R, B)로 누른다. magenta: R·B를 G 쪽으로 누른다(둘 중 큰 쪽을 G + 나머지 차이까지만).
    """
    a = np.asarray(img.convert("RGB")).astype(np.float32)
    key = np.array(KEY_COLORS[name], np.float32)
    d = np.sqrt(((a - key) ** 2).sum(2))
    lo, hi = KEY_SOFT
    alpha = np.clip((d - lo) / (hi - lo), 0, 1)
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    if name == "green":
        g = np.minimum(g, np.maximum(r, b))
    else:
        cap = g + np.abs(r - b)
        r, b = np.minimum(r, cap), np.minimum(b, cap)
    out = np.dstack([r, g, b, alpha * 255]).clip(0, 255).astype(np.uint8)
    out[alpha <= 0] = 0
    return Image.fromarray(out, "RGBA")


def load_rgba(path, white_thr=240):
    """
    프레임 그림을 투명 배경 RGBA로. 이미 투명하면 그대로, 키 색 배경이면 key_out, 흰 배경(예전 pose_edit 결과)이면
    가장자리에서 이어진 흰색만 지운다(갇힌 칸이 남는다 — 예전 결과 호환용).
    """
    im = Image.open(path)
    rgba = np.asarray(im.convert("RGBA"))
    if rgba[..., 3].min() < 255:
        return im.convert("RGBA")
    corners = np.array([rgba[0, 0, :3], rgba[0, -1, :3], rgba[-1, 0, :3], rgba[-1, -1, :3]]).astype(int)
    for name, kc in KEY_COLORS.items():
        if (np.abs(corners - np.array(kc)).max(1) < 40).all():
            return key_out(im, name)
    a = rgba[..., :3].astype(int)
    white = a.min(axis=2) >= white_thr
    lab = P.label_components(white)
    lab = lab[0] if isinstance(lab, tuple) else lab
    border = set(np.unique(np.concatenate([lab[0], lab[-1], lab[:, 0], lab[:, -1]]))) - {0}
    out = rgba.copy()
    out[np.isin(lab, list(border)), 3] = 0
    return Image.fromarray(out, "RGBA")
