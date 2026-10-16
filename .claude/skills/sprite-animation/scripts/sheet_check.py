"""
스프라이트 시트 체형·디자인·모션 검사. 모든 비교의 기준은 사용자가 지정한 기준 시트(--reference)다.

  set-reference REF
      REF(Assets/_/Spirte/{캐릭터}/의 처리된 시트)를 캐릭터 기준으로 정한다.
      {캐릭터}.character.json 의 ref_height(다리를 편 키)를 다시 재서 쓴다. 이후 파이프라인 스케일의 기준.
  audit  --reference REF [SHEET ...]
      기준 대비 체형 비율 + 디자인(색) 일관성 표. SHEET 생략 시 같은 캐릭터의 최신 시트 전부.
  verify --reference REF --new NEW.png (--original ORIG.png | --action Hit)
      재생성 시트 합격 판정: 체형(0번 프레임) + 색 유지 + 모션 보존 + 분할 경고.
      색 차이는 경고 기준을 넘으면 경고, 그 1.5배(--color_fail)를 넘으면 불합격.
      종료 코드 0 합격 / 4 불합격 / 1 오류.
  masks  SHEET
      부위 색 마스크 디버그 이미지. 새 캐릭터는 이걸 보고 팔레트를 맞춘다.
  coherence --raw RAW.png
      몸 일관성: 머리·가슴·허리가 한 덩어리로, 무릎이 같은 방향으로 작게 움직이는지. 0 합격 / 4 불합격.
  set-height --character Knight --relative-to Archer --sheet RAW.png
      새 캐릭터 ref_height를 설정 키(height_cm) 비율로 정한다. 정수리~발바닥(머리카락 제외)으로 비교.
  jitter SHEET
      처리된 시트에서 부위(머리·몸통·발)가 이웃 프레임 평균에서 튀는 프레임을 보고한다. 판정이 아니라 보고.

비교·마스크 이미지는 Temp/SpriteAnimationPipeline/ 에 쓴다. 마지막 줄은 RESULT {json}.

체형 지표(모두 '다리를 편 키'에 대한 비율 — 스케일·보폭 무관. 키는 파이프라인 standing_height와 같다)
  head   정수리~턱 / 키   (1/등신. 머리카락 부피도 포함)          [판정]
  hair   머리카락 면적 / 키²                                      [판정]
  boot   발 영역 폭 / 키                                          [판정]
  leg    편 다리 길이 / 키 (실루엣 기하, 색 무관)                  [참고]
         무기가 허벅지 사이를 덮으면 가랑이를 낮게 잡아 짧게 나온다 — 비교 이미지의 분홍 선으로 확인한다.
옷 길이는 체형이 아니라 디자인이라 수치로 재지 않고 디자인 확인(소품·형태)에서 본다.
판정은 0번 프레임(서 있는 자세)으로 한다. 활을 머리 위로 들거나 누운 프레임은 '키'가 왜곡되어
전 프레임 중앙값은 원본·재생성 가릴 것 없이 +10% 안팎으로 부푼다.

디자인 지표(0번 프레임)
  부위별 평균 색: 색조 차(도), 채도 차, 명도 차      — 머리색이 밝아졌다, 옷이 붉어졌다
  전체 채도/명도: 실루엣 전체 평균 차              — 시트 전체가 밝아지거나 색이 바랬다
  palette        전체 색 분포 차이 (0=같음, 1=전혀 다름) — 소품 추가·재질 변화가 색으로 드러나는 경우
색으로 안 잡히는 차이(화살통·벨트 같은 소품 유무, 머리 모양)는 비교 이미지를 보고 판단한다.
"""
import argparse
import json
import os
import re
import sys

import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(__file__))
import common as C  # noqa: E402

# 기본 팔레트는 Archer(연두 머리 / 주황 코트 / 갈색 스타킹·부츠).
# 다른 캐릭터는 {캐릭터}.character.json 의 "palette" 또는 --palette로 덮어쓴다. HSV: h 0~360, s/v 0~1.
DEFAULT_PALETTE = {
    "hair": {"h": [[55, 150]], "s": [0.30, 1.0], "v": [0.30, 1.0]},
    "coat": {"h": [[0, 22], [340, 360]], "s": [0.60, 1.0], "v": [0.55, 1.0]},
    "skin": {"h": [[0, 35], [340, 360]], "s": [0.12, 0.45], "v": [0.75, 1.0]},
    "boot": {"h": [[5, 45]], "s": [0.35, 1.0], "v": [0.0, 0.45]},
}
THRESHOLDS = {"head": 8.0, "hair": 15.0, "boot": 15.0}
# overall_*: 실루엣 전체 평균. 부위 마스크는 밝아진 픽셀이 범위 밖으로 빠져 전체 밝기 변화를 놓친다
# (합격본 최대: 전체 명도 0.044, 채도 0.052 / 전체를 25% 밝힌 사본: 명도 +0.142)
DESIGN_WARN = {"hue": 12.0, "sat": 0.12, "val": 0.12, "palette": 0.25, "overall_sat": 0.06, "overall_val": 0.06}
COLOR_FAIL_FACTOR = 1.5  # 재생성 검증: 경고 기준의 1.5배를 넘는 색 차이는 불합격 (합격본 최대치: 색조 5°, 채도 0.07, 명도 0.11, 분포 0.06)
MOTION_MIN = 0.72
POSE_MIN = 0.68  # 원본과 프레임별 실루엣 겹침(IoU) 평균. 정상 편집 0.72~0.88, 다른 동작으로 바뀐 시트 0.63 (2026-10-14 Skill2)
JITTER_LIMIT = 1.5  # 부위가 이웃 프레임 평균에서 키의 이 %를 넘게 벗어나면 튐으로 보고
KEYS = ["head", "hair", "boot", "leg"]


# ---------------------------------------------------------------- 기준

def character_of(path):
    m = re.match(r"^([A-Z][A-Za-z0-9]*)_", os.path.basename(path))
    if not m:
        sys.exit(f"시트 이름에서 캐릭터를 알 수 없다: {path} — {{캐릭터}}_{{액션}}_v{{N}}.png 형식이어야 한다")
    return m.group(1)


def config_path(character):
    return os.path.join(C.SHEET_ROOT, character, f"{character}.character.json")


def load_config(character):
    p = config_path(character)
    if os.path.exists(p):
        with open(p, encoding="utf-8") as fp:
            return json.load(fp)
    return {}


def load_palette(character, path):
    if path:
        with open(path, encoding="utf-8") as fp:
            return json.load(fp)
    return load_config(character).get("palette", DEFAULT_PALETTE)


def check_reference(path):
    if not os.path.exists(path):
        sys.exit(f"기준 시트가 없다: {path}")
    cfg = load_config(character_of(path))
    configured = cfg.get("reference")
    name = os.path.splitext(os.path.basename(path))[0]
    if configured and configured != name:
        print(f"[주의] 캐릭터 설정의 기준은 {configured}인데 {name}을 기준으로 비교한다. "
              f"파이프라인 스케일도 바꾸려면 set-reference를 실행한다.")


# ---------------------------------------------------------------- 측정

def part_masks(img, palette):
    a = np.array(img)
    alpha = a[:, :, 3] > 128
    hsv = np.array(img.convert("RGB").convert("HSV")).astype(float)
    h, s, v = hsv[..., 0] * 360 / 255, hsv[..., 1] / 255, hsv[..., 2] / 255
    out = {"alpha": alpha, "_hsv": (h, s, v)}
    for part, rule in palette.items():
        hm = np.zeros_like(alpha)
        for lo, hi in rule["h"]:
            hm |= (h >= lo) & (h <= hi)
        out[part] = alpha & hm & (s >= rule["s"][0]) & (s <= rule["s"][1]) & (v >= rule["v"][0]) & (v <= rule["v"][1])
    return out


def bbox(mask):
    ys, xs = np.where(mask)
    return (ys.min(), ys.max(), xs.min(), xs.max()) if len(ys) else None


def body_metrics(img, palette):
    m = part_masks(img, palette)
    b = bbox(m["alpha"])
    hb = bbox(m["hair"])
    if b is None or hb is None:
        return None
    top, bottom = b[0], b[1]
    H = bottom - top + 1
    _, hbot, hl, hr = hb
    Hs, stance = C.P.standing_height(img)

    # 턱: 세로 키 상단 40% 안, 머리카락 가로 범위 안의 피부 최하단 (허벅지·손을 얼굴로 잡지 않게)
    face = m["skin"].copy()
    face[top + int(H * 0.40):] = False
    face[:, :hl] = False
    face[:, hr + 1:] = False
    rows = np.where(face.sum(1) > 3)[0]
    chin = rows.max() if len(rows) else hbot

    if stance["method"] == "standing":
        leg = float(np.hypot(stance["leg"], stance["spread"] / 2)) / Hs
        crotch = stance["crotch"] / H  # 그림용: 세로 키 기준 위치
    else:
        leg, crotch = float("nan"), float("nan")

    boot_band = m["boot"][bottom - int(H * 0.08):bottom + 1]
    return {
        "height": round(Hs, 1),
        "head": (chin - top) / Hs,
        "hair": m["hair"].sum() / Hs ** 2 * 100,
        "boot": boot_band.any(0).sum() / Hs,
        "leg": leg,
        "_chin": (chin - top) / H,
        "_crotch": crotch,
    }


def design_metrics(img, palette):
    """부위별 평균 색 + 전체 색조 분포. 색조 평균은 원형 평균(0°/360° 경계 처리)."""
    m = part_masks(img, palette)
    h, s, v = m["_hsv"]
    parts = {}
    for part in palette:
        mask = m[part]
        if mask.sum() < 50:
            continue
        rad = np.deg2rad(h[mask])
        hue = np.rad2deg(np.arctan2(np.sin(rad).mean(), np.cos(rad).mean())) % 360
        parts[part] = {"hue": float(hue), "sat": float(s[mask].mean()), "val": float(v[mask].mean())}
    # 전체 분포: 채도 있는 픽셀은 색조 18칸, 무채색은 명도 3칸
    alpha = m["alpha"]
    chroma = alpha & (s > 0.15)
    gray = alpha & (s <= 0.15)
    hist = np.concatenate([
        np.histogram(h[chroma], bins=18, range=(0, 360))[0],
        np.histogram(v[gray], bins=3, range=(0, 1))[0],
    ]).astype(float)
    overall = {"sat": float(s[alpha].mean()), "val": float(v[alpha].mean())}
    return {"parts": parts, "hist": hist / max(1.0, hist.sum()), "overall": overall}


def design_diff(d, ref):
    out = {}
    for part, r in ref["parts"].items():
        if part not in d["parts"]:
            out[part] = {"missing": True}
            continue
        x = d["parts"][part]
        dh = abs((x["hue"] - r["hue"] + 180) % 360 - 180)
        out[part] = {"hue": dh, "sat": x["sat"] - r["sat"], "val": x["val"] - r["val"]}
    out["palette"] = float(0.5 * np.abs(d["hist"] - ref["hist"]).sum())
    out["overall"] = {"sat": d["overall"]["sat"] - ref["overall"]["sat"], "val": d["overall"]["val"] - ref["overall"]["val"]}
    return out


def design_warnings(diff, factor=1.0):
    """factor=1 경고, factor=COLOR_FAIL_FACTOR 불합격 기준."""
    lim = {k: v * factor for k, v in DESIGN_WARN.items()}
    w = []
    for part, x in diff.items():
        if part in ("palette", "overall"):
            continue
        if x.get("missing"):
            w.append(f"{part}: 기준에 있는 색 영역이 거의 없다")
            continue
        if x["hue"] > lim["hue"]:
            w.append(f"{part} 색조 {x['hue']:.0f}° 차이")
        if abs(x["sat"]) > lim["sat"]:
            w.append(f"{part} 채도 {x['sat']:+.2f}")
        if abs(x["val"]) > lim["val"]:
            w.append(f"{part} 명도 {x['val']:+.2f}")
    if abs(diff["overall"]["val"]) > lim["overall_val"]:
        w.append(f"전체 명도 {diff['overall']['val']:+.2f}")
    if abs(diff["overall"]["sat"]) > lim["overall_sat"]:
        w.append(f"전체 채도 {diff['overall']['sat']:+.2f}")
    if diff["palette"] > lim["palette"]:
        w.append(f"전체 색 분포 차이 {diff['palette']:.2f}")
    return w


def summarize(frames, palette):
    ms = [body_metrics(f["image"], palette) for f in frames]
    valid = [x for x in ms if x]
    med = {k: float(np.nanmedian([x[k] for x in valid])) for k in KEYS} if valid else None
    return ms[0], med


def delta(v, ref):
    return {k: (v[k] / ref[k] - 1) * 100 if ref[k] and not np.isnan(ref[k]) else float("nan") for k in KEYS}


def reference(path, palette):
    frames, _ = C.load_frames(path)
    f0, med = summarize(frames, palette)
    if f0 is None:
        sys.exit(f"기준 시트 0번 프레임을 측정할 수 없다 (팔레트 확인: masks {path})")
    return frames, f0, med


def silhouettes(frames):
    """발 중심을 맞추고 키를 256으로 정규화한 실루엣."""
    out = []
    for f in frames:
        a = np.array(f["image"])[:, :, 3] > 128
        s = 256 / a.shape[0]
        im = Image.fromarray(a.astype(np.uint8) * 255).resize((max(1, round(a.shape[1] * s)), 256))
        canvas = Image.new("L", (512, 256))
        canvas.paste(im, (round(256 - (f["feet_x"] - f["left"]) * s), 0))
        out.append(np.array(canvas) > 128)
    return out


def boot_width(img):
    """
    부츠 한 짝의 최대 폭 / 다리를 편 키 (두 발 평균). 아래 15% 띠에서 바닥 근처 틈으로 두 발을 나눠 각자 최대 폭을 잰다.
    자세·시점에 따라 값이 달라서 기준 시트끼리가 아니라 '같은 시트의 원본 대비 배율'로만 쓴다(--boot-scale).
    """
    a = np.array(img)[:, :, 3] > 128
    ys = np.where(a.any(1))[0]
    top, sole = ys.min(), ys.max()
    H = sole - top + 1
    reg = a[int(sole - 0.15 * H):sole + 1]
    cols = reg[-max(3, int(0.05 * H)):].any(0)
    d = np.diff(np.concatenate(([0], cols.astype(np.int8), [0])))
    runs = sorted(sorted(zip(np.where(d == 1)[0], np.where(d == -1)[0]), key=lambda r: r[1] - r[0], reverse=True)[:2])
    if len(runs) < 2:
        return float("nan")
    split = (runs[0][1] + runs[1][0]) // 2
    ws = []
    for x0, x1 in ((0, split), (split, a.shape[1])):
        w = [(lambda xs: xs.max() - xs.min() + 1 if len(xs) else 0)(np.where(row)[0]) for row in reg[:, x0:x1]]
        ws.append(max(w))
    Hs, _ = C.P.standing_height(img)
    return float(np.mean(ws)) / Hs


def pose_match(new_frames, orig_frames):
    """원본과 같은 동작인지: 프레임마다 실루엣(발 중심·키 정규화) IoU의 평균. 모션 양(motion_amount)은 다른 동작이어도 비슷하게 나온다."""
    sa, sb = silhouettes(new_frames), silhouettes(orig_frames)
    return float(np.mean([(a & b).sum() / max(1, (a | b).sum()) for a, b in zip(sa, sb)]))


def motion_amount(frames):
    """연속 프레임 실루엣 변화량 (XOR / 합집합). 정지 포즈 시트는 작게 나온다."""
    s = silhouettes(frames)
    return float(np.mean([(a ^ b).sum() / max(1, (a | b).sum()) for a, b in zip(s, s[1:])]))


# ---------------------------------------------------------------- 출력

def compare_image(ref_name, ref_img, ref_f0, items, path, palette=None):
    """같은 세로 크기로 나란히. 가로 빨강 = 기준의 턱선, 타일마다 짧은 빨강 = 자기 턱, 분홍 = 자기 가랑이."""
    T, pad = 520, 24
    tiles = [("REF " + ref_name, ref_img)] + list(items)  # 기본 글꼴에 한글이 없어 그림 안 글자는 영문
    W = pad
    prepared = []
    for n, img in tiles:
        t = C.crop_frame(img)
        t = t.resize((round(t.width * T / t.height), T), Image.LANCZOS)
        m = body_metrics(img, palette or DEFAULT_PALETTE)
        prepared.append((n, t, m))
        W += t.width + pad
    out = Image.new("RGB", (W, T + 70), (236, 236, 236))
    d = ImageDraw.Draw(out)
    y = 25 + ref_f0["_chin"] * T
    d.line([(0, y), (W, y)], fill=(220, 0, 0), width=1)
    x = pad
    for n, t, m in prepared:
        out.paste(t, (x, 25), t)
        if m:
            d.line([(x, 25 + m["_chin"] * T), (x + t.width, 25 + m["_chin"] * T)], fill=(220, 0, 0), width=3)
            if not np.isnan(m["_crotch"]):
                d.line([(x, 25 + m["_crotch"] * T), (x + t.width, 25 + m["_crotch"] * T)], fill=(230, 0, 230), width=3)
        d.text((x, T + 40), n, fill=(0, 0, 0))
        x += t.width + pad
    os.makedirs(os.path.dirname(path), exist_ok=True)
    out.save(path)


def fmt_row(label, d, extra=""):
    return label.ljust(28) + "".join(f"{d[k]:+9.1f}%" for k in KEYS) + extra


def header():
    return "".ljust(28) + "".join(k.rjust(10) for k in KEYS)


def fmt_design(label, diff):
    cells = []
    for part, x in diff.items():
        if part in ("palette", "overall"):
            continue
        cells.append(f"{part}: 없음" if x.get("missing") else f"{part} {x['hue']:.0f}°/{x['sat']:+.2f}/{x['val']:+.2f}")
    o = diff["overall"]
    return f"{label.ljust(28)}{'  '.join(cells)}  전체 {o['sat']:+.2f}/{o['val']:+.2f}  분포 {diff['palette']:.2f}"


def slash(p):
    return p.replace("\\", "/")


# ---------------------------------------------------------------- 명령

def cmd_set_reference(args):
    path = args.sheet
    character = character_of(path)
    if os.path.normpath(os.path.dirname(os.path.abspath(path))) != os.path.normpath(os.path.join(C.SHEET_ROOT, character)):
        sys.exit(f"기준 시트는 처리된 시트여야 한다: Assets/_/Spirte/{character}/ 안의 파일")
    frames, _ = C.load_frames(path)
    height, stance = C.P.standing_height(frames[0]["image"])
    cfg = load_config(character)
    old = cfg.get("ref_height")
    cfg.update(ref_method="standing", reference=os.path.splitext(os.path.basename(path))[0])
    if args.keep_height and old:
        # set-height로 정한 게임 내 키를 그대로 둔다 — 그 키로 처리한 시트라 다시 재도 같고, 반올림만큼 흔들린다
        print(f"{character} 키 {old} 유지 (--keep-height)")
    else:
        cfg["ref_height"] = round(height, 1)
    if args.chin or "ref_chin_to_sole" in cfg:
        # 기준을 바꾸면 턱~발바닥도 새 기준에서 다시 잰다(남겨 두면 옛 기준 크기로 처리된다)
        chin = reference_chin_to_sole(path)
        print(f"턱~발바닥 {cfg.get('ref_chin_to_sole')} → {chin}")
        cfg["ref_chin_to_sole"] = chin
    with open(config_path(character), "w", encoding="utf-8") as fp:
        json.dump(cfg, fp, ensure_ascii=False, indent=2)
    print(f"{character} 기준 = {cfg['reference']}, 키 {old} → {cfg['ref_height']} ({stance['method']})")
    print("기존 시트의 스케일은 그대로다. 새 기준에 맞추려면 각 시트를 원본에서 다시 처리·적용한다.")
    print(f"RESULT {json.dumps({'ok': True, 'character': character, **cfg, 'stance': stance}, ensure_ascii=False)}")


def reference_chin_to_sole(path):
    """
    처리된 기준 시트의 턱~발바닥(출력 px) = 원본 기준 프레임의 턱~발바닥 × 처리 배율(매니페스트 scale).
    출력 프레임에서 바로 재면 축소된 그림에서 분홍빛 머리카락 하이라이트를 얼굴로 잡는다(Knight_Idle_v10: 턱을 키의 2%로 잡음).
    Knight_Idle_v10: 366 × 1.0541 = 386 (손으로 넣었던 값과 같다).
    """
    with open(os.path.splitext(path)[0] + ".json", encoding="utf-8") as fp:
        m = json.load(fp)
    g = m.get("sourceGrid") or {"cols": m["cols"], "rows": m["rows"], "frames": m["frames"]}
    if m.get("sources"):
        sys.exit("여러 장을 이어 붙인 시트는 기준으로 쓰지 않는다 — 기준은 보통 Idle 한 장이다")
    src = m["source"]
    if not os.path.exists(src):
        sys.exit(f"원본 시트가 없어 턱~발바닥을 못 잰다: {src}")
    fr, _ = C.load_frames(src, g["cols"], g["rows"], g["frames"])
    raw = C.P.chin_to_sole(fr[m.get("anchor", 0)]["image"])
    if raw is None:
        sys.exit("원본 기준 프레임에서 턱을 못 찾았다 — ref_chin_to_sole을 손으로 잰다")
    return round(raw * m["scale"])


def skull_height(img, skull_over_L):
    """
    정수리~발바닥 키(머리카락 제외, 다리를 벌린 만큼 보정). 정수리는 얼굴 턱에서 두개골 높이(턱~발바닥 × skull_over_L)만큼 위.
    skull_over_L은 캐릭터마다 잰 값(character.json): Archer 0.312(사용자가 그린 두개골 선), Knight 0.304(맞춰 겹친 마네킹 v3).
    """
    sys.path.insert(0, os.path.dirname(__file__))
    import deform as D
    a = np.array(img)[:, :, 3] > 128
    ys = np.where(a.any(1))[0]
    top, sole = ys.min(), ys.max()
    chin = D.face_chin(img)
    if chin is None:
        sys.exit("얼굴 턱을 못 찾았다 — 키를 잴 수 없다")
    L = sole - chin
    S, _ = C.P.standing_height(img)
    return (sole - (chin - skull_over_L * L)) + (S - (sole - top + 1)), S


def cmd_set_height(args):
    """
    새 캐릭터의 기준 키(ref_height)를 설정 키(height_cm) 비율로 정한다. 같은 크기에 비율만 다르게 그리지 않고
    실제 키 차이가 보이게 하려는 것(사용자 지정 2026-10-14). 비교 대상 캐릭터의 처리된 기준 시트에서 정수리~발바닥 키를 재고,
    새 캐릭터 원본 시트 0번 프레임을 그 키 × (내 height_cm / 그쪽 height_cm)로 맞추는 스케일을 ref_height로 쓴다.
    """
    me, other = load_config(args.character), load_config(args.relative_to)
    for name, cfg in ((args.character, me), (args.relative_to, other)):
        if not cfg.get("height_cm") or not cfg.get("skull_over_L"):
            sys.exit(f"{name}.character.json에 height_cm, skull_over_L이 필요하다")
    ref_sheet = os.path.join(C.SHEET_ROOT, args.relative_to, other["reference"] + ".png")
    of, _ = C.load_frames(ref_sheet)
    other_h, _ = skull_height(C.crop_frame(of[0]["image"]), other["skull_over_L"])
    mf, _ = C.load_frames(args.sheet, 4, 2, 8)
    my_h, my_s = skull_height(mf[0]["image"], me["skull_over_L"])
    target = other_h * me["height_cm"] / other["height_cm"]
    scale = target / my_h
    me.update(ref_height=round(scale * my_s, 1), ref_method="standing",
              ref_height_note=f"{args.relative_to}({other['reference']}) 정수리~발 {other_h:.1f}px × {me['height_cm']}/{other['height_cm']}cm 기준")
    with open(config_path(args.character), "w", encoding="utf-8") as fp:
        json.dump(me, fp, ensure_ascii=False, indent=2)
    print(f"{args.relative_to} 키 {other_h:.1f}px → {args.character} 목표 {target:.1f}px, 스케일 {scale:.4f}, ref_height {me['ref_height']}")
    print(f"RESULT {json.dumps({'ok': True, 'ref_height': me['ref_height'], 'scale': round(scale, 4)}, ensure_ascii=False)}")


BANDS = {"head": (0.03, 0.15), "chest": (0.30, 0.40), "waist": (0.42, 0.52), "knee": (0.66, 0.76)}
STRETCH_MAX = 3  # 머리·가슴·허리가 서로 어긋나는 최대 px(원본 키 ~500px 기준). Archer Idle 2, Knight Idle(AI 1차) 4~5


def aligned_cells(frames):
    """원본 프레임을 발 중심·바닥선이 같도록 같은 캔버스에 놓는다(파이프라인 feet 정렬과 같은 기준)."""
    W = int(max(f["image"].width for f in frames) * 1.6)
    H = int(max(f["image"].height for f in frames) * 1.2)
    out = []
    for f in frames:
        c = Image.new("RGBA", (W, H))
        img = f["image"]
        c.paste(img, (round(W / 2 - (f["feet_x"] - f["left"])), H - 10 - img.height))
        out.append(np.asarray(c).astype(np.float32))
    return out


def band_motion(frames):
    """
    몸 높이대별(머리·가슴·허리·무릎) 세로 이동(0번 프레임 대비, px). 실제 몸은 머리·가슴·허리가 한 덩어리로 같이 움직이고
    무릎은 같은 방향으로 그보다 작게 따라간다. 부위끼리 어긋나면 목·허벅지가 고무처럼 늘었다 줄었다 해서 'AI 같은' 움직임이 된다
    (사용자 지적 2026-10-14, Knight Idle). 반환: {부위: [프레임별 dy]}
    """
    cs = aligned_cells(frames)

    def g(a):
        return a[:, :, :3].mean(2) * (a[:, :, 3] / 255)

    g0 = g(cs[0])
    al = cs[0][:, :, 3] > 128
    rows = np.where(al.any(1))[0]
    top, bot = rows.min(), rows.max()
    Hh = bot - top
    cols = np.where(al.any(0))[0]
    x0, x1 = cols.min() + 20, cols.max() - 20
    # 무릎은 두 발 사이 폭만 본다 — 망토·검처럼 다리 옆에서 안 움직이는 것이 띠를 채우면 무릎이 멈춘 것으로 잡힌다(Knight)
    lf, rf = C.P.foot_centers(Image.fromarray(cs[0].astype(np.uint8)))
    leg_pad = 0.06 * Hh
    out = {k: [] for k in BANDS}
    for c in cs:
        gc = g(c)
        for k, (a, b) in BANDS.items():
            y0, y1 = int(top + a * Hh), int(top + b * Hh)
            bx0, bx1 = (int(lf - leg_pad), int(rf + leg_pad)) if k == "knee" else (x0, x1)
            ref = g0[y0:y1, bx0:bx1]
            best = (1e18, 0)
            for dy in range(-14, 15):
                for dx in range(-6, 7):
                    d = float(np.abs(gc[y0 + dy:y1 + dy, bx0 + dx:bx1 + dx] - ref).mean())
                    if d < best[0]:
                        best = (d, dy)
            out[k].append(best[1])
    return out


def cmd_coherence(args):
    frames, _ = C.load_frames(args.sheet, 4, 2, 8) if args.raw else C.load_frames(args.sheet)
    if not args.raw:
        sys.exit("처리된 시트는 아직 지원하지 않는다 — 원본 시트에 --raw")
    bm = band_motion(frames)
    for k, v in bm.items():
        print(f"  {k:6} " + " ".join(f"{x:+3d}" for x in v) + f"   범위 {max(v) - min(v)}")
    upper = np.array([bm["head"], bm["chest"], bm["waist"]])
    stretch = int((upper.max(0) - upper.min(0)).max())
    waist, knee = np.array(bm["waist"]), np.array(bm["knee"])
    opposite = int(((waist * knee) < 0).sum() + ((np.abs(knee) > np.abs(waist) + 1) & (np.abs(knee) > 1)).sum())
    amp = int(np.ptp(bm["chest"]))
    fails = []
    if stretch > STRETCH_MAX:
        fails.append(f"상체가 따로 움직인다(머리·가슴·허리 어긋남 최대 {stretch}px > {STRETCH_MAX})")
    if opposite:
        fails.append(f"무릎이 허리와 반대로/더 크게 움직이는 프레임 {opposite}개")
    wr, kr = int(np.ptp(waist)), int(np.ptp(knee))
    if wr >= 6 and kr < 0.25 * wr:
        fails.append(f"무릎이 거의 안 따라온다(허리 {wr}px, 무릎 {kr}px) — 허벅지가 늘었다 줄었다 한다(Archer는 무릎이 허리의 약 0.55배)")
    if amp < args.min_amp:
        fails.append(f"숨쉬기 폭 {amp}px < {args.min_amp} (Archer Idle 12px) — 정지 화면처럼 보인다")
    if len(set(bm["chest"])) < 4:
        fails.append(f"자세가 {len(set(bm['chest']))}가지뿐 — 한 번 툭 움직이는 동작이 된다")
    print(f"상체 어긋남 최대 {stretch}px, 무릎 역행 {opposite}프레임, 숨쉬기 폭(가슴) {amp}px")
    print("판정:", "합격" if not fails else "불합격 — " + "; ".join(fails))
    print(f"RESULT {json.dumps({'ok': True, 'pass': not fails, 'fails': fails, 'stretch': stretch, 'amplitude': amp, 'bands': bm}, ensure_ascii=False)}")
    sys.exit(0 if not fails else 4)


PROPORTION_TOL = 0.10  # 프레임별 머리·신발 크기가 기준 프레임과 이만큼 넘게 다르면 불합격


def shoe_height(img):
    """두 발 중 큰 쪽의 신발 높이(px): 발 중심 ±폭에서 바닥부터 띠 폭이 신발 최대폭의 55% 아래로 줄어드는 높이."""
    a = np.array(img)[:, :, 3] > 128
    sole = np.where(a.any(1))[0].max()
    out = []
    for fx in C.P.foot_centers(img):
        x0 = max(0, int(fx - 60))
        widths = [a[y, x0:int(fx + 60)].sum() for y in range(sole, max(0, sole - 260), -1)]
        mx = max(widths[:25]) if widths else 0
        h = next((i for i, w in enumerate(widths) if i > 8 and w < 0.55 * mx), None)
        if h:
            out.append(h)
    return min(out) if out else None


def cmd_proportions(args):
    """
    원본 시트의 프레임마다 머리(정수리~턱)와 신발 높이를 기준(같은 시트의 0번 프레임 = 준비 자세, 또는 --ref 그림)과 비교한다.
    같은 생성물 안의 크기 비교라 스케일과 무관하다. 큰 동작에서 AI가 머리를 키우고 신발을 부풀리는 것을 잡는다(Knight Skill1 런지:
    머리 +11~+30%, 신발 2배). 정수리는 머리카락 꼭대기라 머리카락이 크게 날리는 프레임은 약간 크게 나온다 — 이미지로 같이 본다.
    """
    sys.path.insert(0, os.path.dirname(__file__))
    if len(args.sheets) > 1:
        parts = [Image.open(p).convert("RGBA") for p in args.sheets]
        w = parts[0].width
        src = Image.new("RGBA", (w, sum(p.height for p in parts)))
        y = 0
        for p in parts:
            src.paste(p, (0, y))
            y += p.height
    else:
        src = Image.open(args.sheets[0]).convert("RGBA")
    frames, _, _ = C.P.extract_frames(np.array(src), args.cols, args.rows, args.frames or args.cols * args.rows, None, True)
    ref_img = C.crop_frame(Image.open(args.ref).convert("RGBA")) if args.ref else frames[0]["image"]

    def meas(img):
        # 머리 = 정수리 ~ 어깨 갑옷(가장 위의 금색) — 피부색 턱 검출은 은분홍 머리카락을 피부로 잡아 틀렸다(Knight)
        a = np.array(img)[:, :, 3] > 128
        top = np.where(a.any(1))[0].min()
        hsv = np.array(img.convert("RGB").convert("HSV")).astype(float)
        h, sat, v = hsv[..., 0] * 360 / 255, hsv[..., 1] / 255, hsv[..., 2] / 255
        gold = a & (h >= 30) & (h <= 50) & (sat > 0.45) & (v > 0.55)
        rows = np.where(gold.sum(1) > 6)[0]
        shoulder = rows.min() if len(rows) else None
        return (shoulder - top) if shoulder is not None else None, shoe_height(img)

    rh, rs = meas(ref_img)
    if not rh or not rs:
        sys.exit("기준 프레임에서 머리·신발을 못 쟀다")
    fails = []
    rows = []
    for f in frames:
        h, s = meas(f["image"])
        dh = (h / rh - 1) if h else float("nan")
        ds = (s / rs - 1) if s else float("nan")
        rows.append((f["index"], dh, ds))
        if not np.isnan(dh) and abs(dh) > args.tol:
            fails.append(f"프레임 {f['index']} 머리 {dh * 100:+.0f}%")
        if not np.isnan(ds) and ds > args.tol * 2:
            fails.append(f"프레임 {f['index']} 신발 {ds * 100:+.0f}%")
    print("프레임  " + " ".join(f"{i:>5}" for i, _, _ in rows))
    print("머리    " + " ".join(f"{d * 100:+5.0f}" if not np.isnan(d) else "    -" for _, d, _ in rows))
    print("신발    " + " ".join(f"{d * 100:+5.0f}" if not np.isnan(d) else "    -" for _, _, d in rows))
    print("판정:", "합격" if not fails else "불합격 — " + "; ".join(fails))
    print(f"RESULT {json.dumps({'ok': True, 'pass': not fails, 'fails': fails}, ensure_ascii=False)}")
    sys.exit(0 if not fails else 4)


def cmd_audit(args):
    check_reference(args.reference)
    character = character_of(args.reference)
    palette = load_palette(character, args.palette)
    ref_frames, ref_f0, ref_med = reference(args.reference, palette)
    ref_design = design_metrics(ref_frames[0]["image"], palette)
    ref_name = os.path.basename(args.reference)

    if args.sheets:
        sheets = args.sheets
    else:
        actions = ("Idle", "Hit", *[f"Skill{i}" for i in range(1, 10)], "Dead")
        sheets = [p for p in (C.latest_sheet(character, a) for a in actions)
                  if p and os.path.basename(p) != ref_name]

    print(f"기준: {ref_name}  {1 / ref_f0['head']:.2f}등신")
    print("[체형] 기준 대비 %, 0번 프레임으로 판정 (head·hair·boot). leg는 참고 — 무기가 가랑이를 가리면 짧게 나온다")
    print(header() + "   등신")
    result, items, design_lines = {}, [], []
    for s in sheets:
        frames, _ = C.load_frames(s)
        f0, med = summarize(frames, palette)
        name = os.path.basename(s)
        if f0 is None:
            print(f"{name}: 0번 프레임 측정 불가 (팔레트 확인: masks 명령)")
            continue
        d0 = delta(f0, ref_f0)
        bad = [k for k, t in THRESHOLDS.items() if abs(d0[k]) > t]
        print(fmt_row(f"{name[:22]} f0", d0, f"{1 / f0['head']:7.2f}  " + ("OK" if not bad else "벗어남:" + ",".join(bad))))
        if med:
            print(fmt_row("  (전 프레임 중앙값)", delta(med, ref_med)))
        dd = design_diff(design_metrics(frames[0]["image"], palette), ref_design)
        dw = design_warnings(dd)
        design_lines.append(fmt_design(name[:26], dd) + ("" if not dw else "  ← " + ", ".join(dw)))
        result[name] = {"f0": d0, "outside": bad, "design": dd, "design_warnings": dw}
        items.append((name, frames[0]["image"]))

    print("\n[디자인] 부위별 색조차°/채도차/명도차, 전체 색 분포 차이(0~1)")
    for line in design_lines:
        print(line)
    print("색으로 안 잡히는 소품·머리 모양 차이는 비교 이미지에서 확인한다.")
    design = load_config(character).get("design", {})
    if design.get("required"):
        print()
        print("[필수 디자인 요소] 사용자 지정 — 기준 시트보다 우선한다. 모든 시트의 0번 프레임에서 눈으로 확인:")
        for item in design["required"]:
            print(f"  - {item}")
        if design.get("note"):
            print(f"  ({design['note']})")

    img = os.path.join(C.PREVIEW_DIR, f"_audit_{character}.png")
    compare_image(ref_name, ref_frames[0]["image"], ref_f0, items, img, palette)
    print(f"RESULT {json.dumps({'ok': True, 'reference': slash(args.reference), 'compare': slash(img), 'required_design': design.get('required', []), 'sheets': result}, ensure_ascii=False)}")


def cmd_verify(args):
    check_reference(args.reference)
    character = character_of(args.reference)
    palette = load_palette(character, args.palette)
    ref_frames, ref_f0, ref_med = reference(args.reference, palette)
    if not args.original:
        if not args.action:
            sys.exit("--original 또는 --action이 필요하다")
        args.original, why = C.resolve_original(character, args.action)
        if args.original is None:
            sys.exit(f"{why} — 원본이 없으면 모션 비교를 할 수 없다")
    new_frames, new_warn = C.load_frames(args.new, args.cols, args.rows, args.frames)
    orig_frames, _ = C.load_frames(args.original, args.cols, args.rows, args.frames)
    f0, med = summarize(new_frames, palette)
    of0, _ = summarize(orig_frames, palette)

    fails = []
    d0 = None
    if f0 is None:
        fails.append("0번 프레임 측정 불가")
    else:
        d0 = delta(f0, ref_f0)
        # --boot-scale: 부츠는 기준 모델과 자세가 달라 직접 비교하지 않고 아래에서 원본 대비 배율로 본다
        fails += [f"{k} {d0[k]:+.1f}% (±{t:g})" for k, t in THRESHOLDS.items()
                  if abs(d0[k]) > t and not (args.boot_scale and k == "boot")]
    boot_line = None
    if args.boot_scale:
        bn, bo = boot_width(new_frames[0]["image"]), boot_width(orig_frames[0]["image"])
        ratio = bn / bo if bo else float("nan")
        boot_line = f"부츠 한 짝 폭: 원본 대비 {ratio:.2f}배 (목표 {args.boot_scale:g} ±12%)"
        if np.isnan(ratio) or abs(ratio / args.boot_scale - 1) > 0.12:
            fails.append(f"부츠 배율 {ratio:.2f} (목표 {args.boot_scale:g})")
    motion = motion_amount(new_frames) / max(1e-6, motion_amount(orig_frames))
    if motion < args.motion_min:
        fails.append(f"모션 {motion:.2f} (≥{args.motion_min})")
    pose = pose_match(new_frames, orig_frames)
    if pose < POSE_MIN:
        fails.append(f"포즈 일치 {pose:.2f} (≥{POSE_MIN}) — 원본과 다른 동작일 수 있다")
    fails += [f"분할: {w}" for w in new_warn if "기준 키" not in w]

    ref_design = design_metrics(ref_frames[0]["image"], palette)
    dd = design_diff(design_metrics(new_frames[0]["image"], palette), ref_design)
    dw = design_warnings(dd)
    fails += [f"색: {w}" for w in design_warnings(dd, args.color_fail)]

    print(f"기준: {os.path.basename(args.reference)}  {1 / ref_f0['head']:.2f}등신")
    print(header() + "   등신")
    if d0:
        print(fmt_row("재생성 f0", d0, f"{1 / f0['head']:7.2f}"))
    if of0:
        print(fmt_row("원본 f0", delta(of0, ref_f0), f"{1 / of0['head']:7.2f}"))
    if med:
        print(fmt_row("재생성 중앙값(참고)", delta(med, ref_med)))
    print(f"모션 보존 {motion:.2f}  포즈 일치 {pose:.2f} (0.75 미만이면 결과 이미지로 동작이 같은지 본다)")
    if boot_line:
        print(boot_line)
    print(fmt_design("디자인(색)", dd))
    if dw:
        print("디자인 경고:", ", ".join(dw), "— 이미지로 확인한다")
    print("판정:", "합격" if not fails else "불합격 — " + "; ".join(fails))

    img = os.path.join(C.PREVIEW_DIR, f"_verify_{os.path.splitext(os.path.basename(args.new))[0]}.png")
    compare_image(os.path.basename(args.reference), ref_frames[0]["image"], ref_f0,
                  [("NEW", new_frames[0]["image"]), ("ORIGINAL", orig_frames[0]["image"])], img, palette)
    print(f"RESULT {json.dumps({'ok': True, 'pass': not fails, 'fails': fails, 'design_warnings': dw, 'f0': d0, 'motion': round(motion, 3), 'compare': slash(img)}, ensure_ascii=False)}")
    sys.exit(0 if not fails else 4)


def part_track(frames, palette):
    """
    프레임별 부위 위치(셀 좌표 px): 머리 = 머리카락 무게중심, 몸통 = 옷 무게중심, 발 = 파이프라인과 같은 foot_centers.
    처리된 시트는 셀마다 pivot이 같은 곳이라 셀 좌표끼리 그대로 비교된다.
    """
    out = []
    for f in frames:
        m = part_masks(f["image"], palette)
        row = {}
        for part in ("hair", "coat"):
            ys, xs = np.where(m[part])
            row[part] = (xs.mean() + f["left"], ys.mean() + f["top"]) if len(ys) else (np.nan, np.nan)
        left_c, right_c = C.P.foot_centers(f["image"])
        row["foot_l"] = (left_c + f["left"], np.nan)
        row["foot_r"] = (right_c + f["left"], np.nan)
        out.append(row)
    return out


def cmd_jitter(args):
    """
    프레임 간 부위 궤적에서 '튀는' 프레임을 찾는다. 튐 = 이웃 두 프레임 평균에서 벗어난 거리(2차 차분).
    루프 클립은 마지막↔첫 프레임도 이웃이다. 의도한 급동작(피격 순간 등)도 걸리므로 판정이 아니라 보고다 —
    걸린 프레임은 시트를 보고 의도인지 AI 편차인지 가린다.
    """
    sheet = args.sheet
    manifest = os.path.splitext(sheet)[0] + ".json"
    loop = args.loop
    if loop is None and os.path.exists(manifest):
        with open(manifest, encoding="utf-8") as fp:
            loop = json.load(fp).get("loop", False)
    frames, _ = C.load_frames(sheet)
    palette = load_palette(character_of(sheet), args.palette)
    track = part_track(frames, palette)
    H = float(np.median([f["bottom"] - f["top"] for f in frames]))
    n = len(frames)
    labels = {"hair": "머리", "coat": "몸통", "foot_l": "왼발", "foot_r": "오른발"}
    print(f"{os.path.basename(sheet)}  loop={bool(loop)}  키(중앙값) {H:.0f}px  튐 기준 {args.limit:g}% (키 대비)")
    print("프레임".ljust(6) + "".join(f"{labels[p]:>16}" for p in labels))
    flagged = []
    report = {}
    for p in labels:
        pts = np.array([t[p] for t in track], dtype=float)
        res = np.full((n, 2), np.nan)
        for i in range(n):
            if not loop and i in (0, n - 1):
                continue
            prev, nxt = pts[(i - 1) % n], pts[(i + 1) % n]
            res[i] = pts[i] - (prev + nxt) / 2
        report[p] = res
    for i in range(n):
        cells = []
        for p in labels:
            dx, dy = report[p][i]
            if np.isnan(dx):
                cells.append(f"{'-':>16}")
                continue
            dist = float(np.hypot(dx, 0 if np.isnan(dy) else dy)) / H * 100
            mark = "*" if dist > args.limit else " "
            cells.append(f"{dx:+6.1f},{(0 if np.isnan(dy) else dy):+6.1f}{mark}  ")
            if dist > args.limit:
                flagged.append({"frame": i, "part": p, "dx": round(float(dx), 1),
                                "dy": None if np.isnan(dy) else round(float(dy), 1), "pct": round(dist, 2)})
        print(f"f{i}".ljust(6) + "".join(cells))
    print("값 = 이웃 평균에서 벗어난 px (x, y). * = 기준 초과")
    for fl in flagged:
        print(f"  [튐] 프레임 {fl['frame']} {labels[fl['part']]} {fl['pct']:.1f}%")
    print(f"RESULT {json.dumps({'ok': True, 'sheet': slash(sheet), 'loop': bool(loop), 'height': H, 'flagged': flagged}, ensure_ascii=False)}")


def cmd_masks(args):
    palette = load_palette(character_of(args.sheet), args.palette)
    frames, _ = C.load_frames(args.sheet)
    img = frames[0]["image"]
    m = part_masks(img, palette)
    vis = np.full(m["alpha"].shape + (3,), 40, np.uint8)
    vis[m["alpha"]] = 90
    colors = {"hair": (0, 220, 0), "coat": (255, 120, 0), "skin": (255, 200, 200), "boot": (120, 60, 255)}
    for part, col in colors.items():
        if part in m:
            vis[m[part]] = col
    out = Image.fromarray(np.concatenate([np.array(img.convert("RGB")), vis], 1))
    path = os.path.join(C.PREVIEW_DIR, f"_masks_{os.path.splitext(os.path.basename(args.sheet))[0]}.png")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    out.save(path)
    print("초록=머리카락 주황=옷 분홍=피부 보라=스타킹·부츠. 엉뚱한 곳이 칠해지면 팔레트를 고친다.")
    print(f"RESULT {json.dumps({'ok': True, 'image': slash(path)}, ensure_ascii=False)}")


def main():
    C.utf8_stdout()
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("set-reference")
    r.add_argument("sheet")
    r.add_argument("--keep-height", action="store_true", help="ref_height를 다시 재지 않는다 (set-height로 정한 새 캐릭터)")
    r.add_argument("--chin", action="store_true", help="ref_chin_to_sole도 쓴다 (이미 있으면 항상 다시 잰다)")

    a = sub.add_parser("audit")
    a.add_argument("--reference", required=True, help="사용자가 지정한 기준 시트")
    a.add_argument("sheets", nargs="*")

    v = sub.add_parser("verify")
    v.add_argument("--reference", required=True, help="사용자가 지정한 기준 시트")
    v.add_argument("--new", required=True)
    v.add_argument("--original", help="원본 시트. 생략하면 --action의 첫 버전으로 넣은 파일(매니페스트 source)")
    v.add_argument("--action", help="--original 생략 시 원본을 찾을 액션 (Hit, Skill1 ...)")
    v.add_argument("--motion_min", type=float, default=MOTION_MIN)
    v.add_argument("--color_fail", type=float, default=COLOR_FAIL_FACTOR, help="색 불합격 = 경고 기준 × 이 값")
    v.add_argument("--head", type=float, default=THRESHOLDS["head"])
    v.add_argument("--hair", type=float, default=THRESHOLDS["hair"])
    v.add_argument("--boot", type=float, default=THRESHOLDS["boot"])
    v.add_argument("--boot-scale", type=float, help="부츠 한 짝 폭의 원본 대비 목표 배율 (예: 0.68). 주면 부츠는 기준 모델과 직접 비교하지 않는다")
    v.add_argument("--cols", type=int)
    v.add_argument("--rows", type=int)
    v.add_argument("--frames", type=int)

    m = sub.add_parser("masks")
    m.add_argument("sheet")

    pr = sub.add_parser("proportions")
    pr.add_argument("sheets", nargs="+", help="원본 시트 (여러 장이면 세로로 이어 붙인다)")
    pr.add_argument("--cols", type=int, default=4)
    pr.add_argument("--rows", type=int, default=2)
    pr.add_argument("--frames", type=int)
    pr.add_argument("--ref", help="기준 인물 그림(예: Idle 0번). 생략하면 같은 시트의 0번 프레임")
    pr.add_argument("--tol", type=float, default=PROPORTION_TOL)

    co = sub.add_parser("coherence")
    co.add_argument("sheet")
    co.add_argument("--raw", action="store_true", help="원본(4x2) 시트")
    co.add_argument("--min-amp", type=int, default=6, help="가슴 위아래 최소 폭 px (Idle)")

    h = sub.add_parser("set-height")
    h.add_argument("--character", required=True)
    h.add_argument("--relative-to", required=True, help="키를 비교할 캐릭터 (예: Archer)")
    h.add_argument("--sheet", required=True, help="새 캐릭터 기준 액션의 원본 시트(4x2)")

    j = sub.add_parser("jitter")
    j.add_argument("sheet", help="처리된 시트 (Assets/_/Spirte/{캐릭터}/)")
    j.add_argument("--limit", type=float, default=JITTER_LIMIT, help="튐 기준 (키 대비 %%)")
    j.add_argument("--loop", type=lambda s: s == "true", default=None, help="true/false. 생략하면 매니페스트")

    for sp in (a, v, m, j):
        sp.add_argument("--palette", help="팔레트 JSON 경로 (기본: character.json의 palette → Archer 기본값)")

    args = p.parse_args()
    if args.cmd == "verify":
        THRESHOLDS.update(head=args.head, hair=args.hair, boot=args.boot)
    {"set-reference": cmd_set_reference, "audit": cmd_audit, "verify": cmd_verify, "masks": cmd_masks,
     "jitter": cmd_jitter, "set-height": cmd_set_height, "coherence": cmd_coherence, "proportions": cmd_proportions}[args.cmd](args)


if __name__ == "__main__":
    main()
