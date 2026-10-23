"""
Codex 사용량(5시간 창 / 주간)을 app-server RPC로 읽는다.

  python codex_usage.py [--limit 85]
종료 코드 0 = 한도 미만, 3 = 5시간 사용량이 한도 이상, 2 = 조회 실패.
"""
import argparse
import json
import os
import subprocess
import sys
import threading
import time


def read_usage(timeout=20):
    """{'primary': %, 'secondary': %} 또는 실패 시 None과 사유."""
    p = subprocess.Popen(["codex", "app-server"], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                         stderr=subprocess.DEVNULL, text=True, encoding="utf-8",
                         cwd=os.environ.get("TEMP", "."))
    lines = []
    threading.Thread(target=lambda: [lines.append(l) for l in p.stdout], daemon=True).start()

    def send(obj):
        p.stdin.write(json.dumps(obj) + "\n")
        p.stdin.flush()

    try:
        send({"jsonrpc": "2.0", "id": 1, "method": "initialize",
              "params": {"clientInfo": {"name": "sprite-animation-skill", "version": "1"}}})
        deadline = time.time() + timeout
        while time.time() < deadline and not any('"id":1' in l for l in lines):
            time.sleep(0.1)
        send({"jsonrpc": "2.0", "method": "initialized"})
        send({"jsonrpc": "2.0", "id": 2, "method": "account/rateLimits/read"})
        while time.time() < deadline:
            hit = [l for l in lines if '"id":2' in l]
            if hit:
                resp = json.loads(hit[0])
                if "result" not in resp:
                    return None, hit[0][:300]
                rl = resp["result"]["rateLimits"]
                return {"primary": rl["primary"]["usedPercent"], "secondary": rl["secondary"]["usedPercent"]}, None
            time.sleep(0.1)
        return None, "응답 시간 초과"
    finally:
        p.kill()


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=float, default=85)
    args = ap.parse_args()
    usage, err = read_usage()
    if usage is None:
        print(f"RESULT {json.dumps({'ok': False, 'error': err}, ensure_ascii=False)}")
        sys.exit(2)
    over = usage["primary"] >= args.limit
    print(f"codex 5시간 {usage['primary']}% / 주간 {usage['secondary']}% (한도 {args.limit:g}%)")
    print(f"RESULT {json.dumps({'ok': True, **usage, 'over_limit': over})}")
    sys.exit(3 if over else 0)


if __name__ == "__main__":
    main()
