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
