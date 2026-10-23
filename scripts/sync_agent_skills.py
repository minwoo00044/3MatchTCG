"""
.claude/skills/ (원본) → .agents/skills/ (다른 에이전트용 사본) 동기화.

    python scripts/sync_agent_skills.py           # 사본을 원본과 똑같이 맞춘다 (바뀐 파일 복사, 원본에 없는 파일 삭제)
    python scripts/sync_agent_skills.py --check   # 차이만 보고. 다르면 종료 코드 1

배경 (2026-10-19): .agents/skills/sprite-animation이 예전 사본으로 남아 deform.py·motion.md 등이 빠져 있었다.
사본은 직접 고치지 않는다 — .claude/skills/를 고치고 이 스크립트를 돌린 뒤 둘을 같이 커밋한다.
"""
import argparse
import filecmp
import os
import shutil
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SRC = os.path.join(ROOT, ".claude", "skills")
DST = os.path.join(ROOT, ".agents", "skills")
SKIP_DIRS = {"__pycache__"}


def files(base):
    out = set()
    if not os.path.isdir(base):
        return out
    for d, dirs, fs in os.walk(base):
        dirs[:] = [x for x in dirs if x not in SKIP_DIRS]
        for f in fs:
            out.add(os.path.relpath(os.path.join(d, f), base))
    return out


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()

    src, dst = files(SRC), files(DST)
    added = sorted(src - dst)
    removed = sorted(dst - src)
    changed = sorted(p for p in src & dst if not filecmp.cmp(os.path.join(SRC, p), os.path.join(DST, p), shallow=False))
    for tag, items in (("+", added), ("~", changed), ("-", removed)):
        for p in items:
            print(f"  {tag} {p.replace(os.sep, '/')}")
    total = len(added) + len(changed) + len(removed)
    if args.check:
        print("같음" if total == 0 else f"다름 {total}건 — python scripts/sync_agent_skills.py 로 맞춘다")
        sys.exit(0 if total == 0 else 1)

    for p in added + changed:
        os.makedirs(os.path.dirname(os.path.join(DST, p)), exist_ok=True)
        shutil.copy2(os.path.join(SRC, p), os.path.join(DST, p))
    for p in removed:
        os.remove(os.path.join(DST, p))
    for d, dirs, fs in sorted(os.walk(DST), key=lambda t: -len(t[0])):  # 빈 폴더 정리
        if d != DST and not os.listdir(d):
            os.rmdir(d)
    print(f"동기화: 추가 {len(added)}, 변경 {len(changed)}, 삭제 {len(removed)}")


if __name__ == "__main__":
    main()
