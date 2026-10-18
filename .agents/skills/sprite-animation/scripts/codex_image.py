"""
Codex(codex exec + 이미지 생성) 한 번 실행 — 작업 폴더, 사용량 확인, 결과 회수를 한 곳에서 한다.
codex_generate.py(시트 재생성)와 mannequin.py / deform.py(턴어라운드 생성)가 같이 쓴다.

    work = new_try_dir("Archer_Hit")                  # SpriteRegen/Archer_Hit/try{N}/ (동시 실행해도 번호가 안 겹친다)
    check_usage(85)                                    # 5시간 사용량이 한도 이상이면 RuntimeError
    result = run(work, prompt, ["a.png", "b.png"])     # 이미지는 work 안의 파일 이름. 반환: work/result.png
"""
import glob
import os
import shutil
import subprocess
import sys

sys.path.insert(0, os.path.dirname(__file__))
import common as C  # noqa: E402
import codex_usage  # noqa: E402


class CodexError(RuntimeError):
    pass


def check_usage(limit):
    """반환: 사용량 dict. 조회 실패면 CodexError, 한도 이상이면 CodexError(over_limit=True)."""
    usage, err = codex_usage.read_usage()
    if usage is None:
        raise CodexError(f"Codex 사용량 조회 실패: {err}")
    if usage["primary"] >= limit:
        e = CodexError(f"Codex 5시간 사용량 {usage['primary']}% ≥ {limit:g}% — 생성 중단")
        e.over_limit = True
        e.usage = usage
        raise e
    return usage


def new_try_dir(job):
    """SpriteRegen/{job}/try{N}/ — 폴더 생성에 성공한 번호를 써서 동시 실행에도 겹치지 않는다."""
    base = os.path.join(C.REGEN_ROOT, job)
    os.makedirs(base, exist_ok=True)
    n = len([d for d in glob.glob(os.path.join(base, "try*")) if os.path.isdir(d)]) + 1
    while True:
        work = os.path.join(base, f"try{n}")
        try:
            os.makedirs(work)
            return work, n
        except FileExistsError:
            n += 1


def dryrun_dir(job):
    work = os.path.join(C.REGEN_ROOT, job, "dryrun")
    shutil.rmtree(work, ignore_errors=True)
    os.makedirs(work)
    return work


def run(work, prompt, images, timeout=900):
    """프롬프트를 work/prompt.md에 남기고 Codex를 실행한다. 결과를 work/result.png로 모아 그 경로를 반환."""
    with open(os.path.join(work, "prompt.md"), "w", encoding="utf-8") as fp:
        fp.write(prompt)
    cmd = ["codex", "exec", "--skip-git-repo-check", "-s", "workspace-write", "-C", work]
    for img in images:
        cmd += ["-i", img]
    cmd += ["-"]
    with open(os.path.join(work, "log.txt"), "w", encoding="utf-8") as log:
        try:
            subprocess.run(cmd, cwd=work, input=prompt, text=True, encoding="utf-8",
                           stdout=log, stderr=subprocess.STDOUT, timeout=timeout)
        except subprocess.TimeoutExpired:
            raise CodexError(f"{timeout}초 안에 끝나지 않았다")
    # 결과는 이 실행의 세션 폴더(generated_images/<세션 ID>/)에서 직접 가져온다.
    # Codex는 out/에 복사할 때 공용 폴더의 '가장 최근 이미지'를 고르는데, 동시에 여러 개를 돌리면
    # 다른 세션의 이미지를 가져간다(2026-10-14: Archer Skill2가 Skill1 결과를 복사 → 이후 편집 4회가 엉뚱한 동작 베이스).
    produced = session_image(work)
    if produced is None:
        raise CodexError("이 세션이 만든 이미지가 없다 (log.txt 확인)")
    # Codex가 out/에 둔 파일은 배경 투명화 같은 후처리가 들어갔을 수 있어 해시가 아니라 그림으로 비교한다.
    # 이 세션 이미지와 같은 그림이면 그대로 쓰고, 다른 그림이면(다른 세션 것) 세션 이미지로 바꾼다
    copied = os.path.join(work, "out", "result.png")
    source = produced
    if os.path.exists(copied):
        if picture_diff(copied, produced) <= PICTURE_SAME:
            source = copied
        else:
            with open(os.path.join(work, "log.txt"), "a", encoding="utf-8") as log:
                log.write(f"\n[codex_image] out/result.png가 이 세션이 만든 그림이 아니다 — 세션 이미지로 바꿨다: {produced}\n")
    result = os.path.join(work, "result.png")
    shutil.copy(source, result)
    return result


PICTURE_SAME = 5.0  # 흰 배경 회색조 96x64 평균 차. 같은 그림(후처리 포함) 0~2.3, 뒤바뀐 그림 42 (2026-10-14 대조)


def picture_diff(a, b):
    import numpy as np
    from PIL import Image

    def thumb(p):
        im = Image.open(p).convert("RGBA")
        bg = Image.new("RGBA", im.size, (255, 255, 255, 255))
        bg.alpha_composite(im)
        return np.asarray(bg.convert("L").resize((96, 64))).astype(float)
    return float(np.abs(thumb(a) - thumb(b)).mean())


def codex_home():
    return os.environ.get("CODEX_HOME") or os.path.join(os.path.expanduser("~"), ".codex")


def session_id(work):
    with open(os.path.join(work, "log.txt"), encoding="utf-8", errors="replace") as fp:
        for line in fp:
            if line.startswith("session id:"):
                return line.split(":", 1)[1].strip()
    return None


def session_image(work):
    """이 실행의 세션이 생성한 이미지 중 가장 최근 것. 세션 ID나 폴더를 못 찾으면 None."""
    sid = session_id(work)
    if not sid:
        return None
    pngs = glob.glob(os.path.join(codex_home(), "generated_images", sid, "*.png"))
    return max(pngs, key=os.path.getmtime) if pngs else None

