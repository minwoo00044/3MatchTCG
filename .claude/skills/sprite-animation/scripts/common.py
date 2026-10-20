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


# ---------------------------------------------------------------- 정지 영역 고정
# pose_edit은 장마다 그림 전체를 새로 그려서 움직이지 않는 곳(다리·코트·모자)도 선·무늬가 1~2px씩 달라진다 →
# 재생하면 픽셀이 반짝거려 "AI 티"가 난다(Priest Skill1, 사용자 2026-10-20). 기준 장(준비 자세)에 위치를 맞춘 뒤
# 기준과 거의 같은 곳은 기준 픽셀로 바꾸고, 실제로 바뀐 곳(팔·소품·표정)만 새 그림을 쓴다.

def lock_static(frame, base, thr=60, max_shift=8, grow=6, legs_from=0.62, max_legs_diff=30.0):
    """
    반환: (고정한 그림, 정보 dict). 다리 띠(키의 legs_from 아래)로 ±max_shift px 이동을 찾아 맞춘 뒤 비교한다.
    맞춰도 다리 차이가 max_legs_diff보다 크면(다리를 크게 움직인 장) 고정하지 않는다. 기준과 '거의 같은' 픽셀만 바꾸므로
    어긋난 곳은 새 그림 그대로 남아 경계가 생기지 않는다 — 12로 두었더니 가장 반짝이는 장(차이 15~18)을 건너뛰었다.
    """
    from PIL import ImageFilter
    B = np.asarray(base).astype(int)
    F0 = np.asarray(frame).astype(int)
    al = B[..., 3] > 128
    ys = np.where(al.any(1))[0]
    top, bot = ys.min(), ys.max()
    legs = slice(int(top + legs_from * (bot - top)), bot + 1)
    best = (1e18, 0, 0)
    for dy in range(-max_shift, max_shift + 1):
        for dx in range(-max_shift, max_shift + 1):
            d = np.abs(np.roll(np.roll(F0, dy, 0), dx, 1)[legs] - B[legs]).mean()
            if d < best[0]:
                best = (d, dx, dy)
    d0, dx, dy = best
    info = {"shift": [dx, dy], "legs_diff": round(float(d0), 1)}
    if d0 > max_legs_diff:
        info["skipped"] = True
        return frame, info
    fr = Image.fromarray(np.roll(np.roll(F0, dy, 0), dx, 1).astype(np.uint8), "RGBA")
    a = np.asarray(base.filter(ImageFilter.GaussianBlur(1.5))).astype(int)
    f = np.asarray(fr.filter(ImageFilter.GaussianBlur(1.5))).astype(int)
    d = np.maximum(np.abs(a[..., :3] - f[..., :3]).max(2), np.abs(a[..., 3] - f[..., 3]))
    m = Image.fromarray(((d > thr) * 255).astype(np.uint8))
    m = m.filter(ImageFilter.MinFilter(5)).filter(ImageFilter.MaxFilter(5))          # 다시 그린 잡음 점은 버린다
    m = m.filter(ImageFilter.MaxFilter(2 * grow + 1)).filter(ImageFilter.GaussianBlur(3))  # 바뀐 곳 둘레 여유 + 부드러운 경계
    M = np.asarray(m)
    fig = (np.asarray(fr)[..., 3] > 128) | al
    info["changed"] = round(float((M > 128)[fig].mean()), 3)
    return Image.composite(fr, base, m), info
