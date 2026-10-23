"""
처리된 시트(아틀라스)의 연속 프레임 변화량 — 한 구간만 크게 바뀌면 그 지점이 '뚝' 끊겨 보인다(사용자 지적 2026-10-15, Knight Skill1).

    python smoothness.py Assets/_/Spirte/Knight/Knight_Skill1_v2.png [...]

변화량 = 실루엣이 달라진 픽셀 / 합집합 (연속 프레임). 정지 구간(변화 0에 가까움)도 따로 센다 — 멈췄다 튀는 것도 끊김으로 보인다.
점프 = 가장 큰 변화 / 중앙값. Archer 시트(사용자가 마음에 들어 함)와 비교한다.
"""
import json
import os
import sys

import numpy as np
from PIL import Image


def cells(path):
    m = json.load(open(os.path.splitext(path)[0] + ".json", encoding="utf-8"))
    at = Image.open(path).convert("RGBA")
    cw, ch, c = m["cellWidth"], m["cellHeight"], m["cols"]
    return [np.asarray(at.crop(((i % c) * cw, (i // c) * ch, (i % c + 1) * cw, (i // c + 1) * ch)))[:, :, 3] > 128
            for i in range(m["frames"])], m


def report(path):
    cs, m = cells(path)
    d = np.array([(a ^ b).sum() / max(1, (a | b).sum()) for a, b in zip(cs, cs[1:])])
    med = float(np.median(d))
    jump = float(d.max() / max(med, 1e-6))
    stalls = int((d < 0.1 * med).sum())
    worst = int(d.argmax())
    keys = m.get("keyFrames") or list(range(m["frames"]))
    src = max([i for i, k in enumerate(keys) if k <= worst], default=0)
    return {"sheet": os.path.basename(path), "steps": len(d), "median": round(med, 3), "max": round(float(d.max()), 3),
            "jump": round(jump, 2), "worst_step": f"{worst}->{worst + 1} (원본 {src}->{src + 1} 사이)", "stalls": stalls,
            "curve": [round(float(x), 3) for x in d]}


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    for p in sys.argv[1:]:
        r = report(p)
        print(f"{r['sheet']:24} 점프 {r['jump']:5.2f}x (최대 {r['max']} / 중앙 {r['median']}) 최악 {r['worst_step']} 정지 {r['stalls']}")
        print("   " + " ".join(f"{x:.2f}" for x in r["curve"]))
