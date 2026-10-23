"""
pose_edit 포즈를 순서대로 '앞 장 결과에서 이어서' 편집한다 — 생성 → accept(--match-color) → 다음 장.
spec의 각 포즈 "body"가 앞 포즈의 source~ 결과를 가리키게 써 둔다(pose_edit.py 머리말).

    python pose_chain.py --character Goblin --action Dead --spec <spec> --poses d1 d2 d3 ... [--match-color Assets/_/Spirte/Goblin/source~/body.png]

왜: Idle 몸에서 매번 출발하면 Codex가 팔다리를 최소로만 움직였다(Goblin Hit, 2026-10-23 "단검 손이 휘청임에 맞지 않게 고정").
앞 장에서 이어 그리면 움직임이 이어지지만 색이 장마다 붉어져 쌓여서 받을 때마다 몸 기준 색 분포에 맞춘다.
한 장이 실패하면(시간 초과 등) 그 장을 한 번 더 시도하고, 그래도 실패하면 멈춘다 — 다음 장이 그 결과를 바탕으로 쓰기 때문.
"""
import argparse
import glob
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def run(args):
    return subprocess.run([sys.executable, os.path.join(HERE, "pose_edit.py"), *args], capture_output=True, text=True, encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--character", required=True)
    ap.add_argument("--action", required=True)
    ap.add_argument("--spec", required=True)
    ap.add_argument("--poses", nargs="+", required=True)
    ap.add_argument("--match-color")
    ap.add_argument("--retries", type=int, default=1)
    a = ap.parse_args()
    for pose in a.poses:
        for attempt in range(a.retries + 1):
            r = run(["generate", "--character", a.character, "--action", a.action, "--spec", a.spec, "--pose", pose])
            ok = '"ok": true' in r.stdout
            if ok:
                break
            print(f"{pose}: 실패(시도 {attempt + 1}) {r.stdout.strip().splitlines()[-1] if r.stdout.strip() else r.stderr[-300:]}", flush=True)
        if not ok:
            print(f"RESULT {{\"ok\": false, \"stopped_at\": \"{pose}\"}}")
            sys.exit(1)
        res = sorted(glob.glob(os.path.join("SpriteRegen", f"{a.character}_{a.action}E_{pose}", "try*", "result.png")),
                     key=os.path.getmtime)[-1]
        acc = ["accept", "--character", a.character, "--action", a.action, "--pose", pose, res]
        if a.match_color:
            acc += ["--match-color", a.match_color]
        r = run(acc)
        print(f"{pose}: {res.replace(os.sep, '/')} → {r.stdout.strip().splitlines()[-1]}", flush=True)
    print('RESULT {"ok": true}')


if __name__ == "__main__":
    main()
