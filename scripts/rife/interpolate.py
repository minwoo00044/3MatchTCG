"""
RGBA 스프라이트 프레임 사이를 RIFE로 보간한다.

    from rife.interpolate import Interpolator
    rife = Interpolator()
    img = rife.between(cell_a, cell_b, 1 / 3)               # PIL RGBA 두 장(같은 크기), 시점 0~1
    imgs, scale, haze = rife.inbetweens(cell_a, cell_b, 2)  # 사이 2장, 번짐이 가장 적은 흐름 해상도로

알파 처리: 모델 입력을 [회색 배경에 합성한 RGB | premultiplied RGB | 알파] 7채널로 넣는다.
흐름은 앞 3채널(배경이 일정한 그림)로 계산되고, 뒤 4채널이 같은 흐름으로 워프·합성된다.
투명 배경을 검정으로 두면 어두운 외곽선과 배경이 구분되지 않아 흐름이 외곽에서 흔들린다.

haze(번짐 지표): 보간본에서 반투명(알파 0.08~0.85) 픽셀이 불투명 면적 대비 얼마나 되는지에서, 두 원본의 같은 값 평균을 뺀 것.
보간 실패는 두 겹 잔상·안개처럼 반투명으로 나타난다. 원본 외곽선의 반투명은 빼서 그림마다 다른 기본값을 지운다.
(처음엔 '두 원본을 각각 워프한 결과의 차이'를 썼는데, 섞기 마스크가 한쪽을 고르면 결과가 깨끗해도 높게 나와 버렸다.)

흐름 해상도(scale): 큰 움직임은 낮은 해상도에서 흐름을 시작해야 잡힌다. inbetweens는 1, 0.5, 0.25로 모두 만들어
번짐이 가장 적은 쪽을 고른다 — Archer에서 활을 머리 위로 드는 구간은 0.25, 주저앉는 구간은 0.5가 가장 깨끗했다.
"""
import hashlib
import os
import urllib.request

import numpy as np
import torch
from PIL import Image

from .ifnet import IFNet

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
WEIGHTS = os.path.join(ROOT, "SpriteRegen", "models", "rife425", "flownet.pkl")  # git 무시 폴더
# Practical-RIFE README의 v4.25 링크 (MIT). zip 안의 train_log/flownet.pkl을 쓴다
WEIGHTS_URL = "https://drive.usercontent.google.com/download?id=1ZKjcbmt1hypiFprJPIKW0Tt0lr_2i7bg&export=download&confirm=t"
WEIGHTS_SHA256 = "6615790efd627772917205db291f51cd392528a157ecbb2ecaeec3bff8eb6de2"
BG = 0.5            # 흐름 계산용 배경 회색
PAD = 128           # 입력 크기 배수 (Practical-RIFE와 같음, scale=1)
ALPHA_FLOOR = 4     # 이 값(0~255) 이하 알파는 0 — 섞을 때 생기는 옅은 안개를 지운다
SCALES = (1.0, 0.5, 0.25)


def haze(img):
    a = np.asarray(img)[:, :, 3] / 255.0
    return float(((a > 0.08) & (a < 0.85)).sum() / max(1, (a > 0.5).sum()))


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fp:
        for chunk in iter(lambda: fp.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def ensure_weights():
    if os.path.exists(WEIGHTS):
        if sha256(WEIGHTS) != WEIGHTS_SHA256:
            raise RuntimeError(f"RIFE 가중치 해시가 다르다: {WEIGHTS} — 지우고 다시 받는다")
        return WEIGHTS
    import zipfile
    os.makedirs(os.path.dirname(WEIGHTS), exist_ok=True)
    zpath = WEIGHTS + ".zip"
    print(f"RIFE v4.25 가중치를 받는다 → {WEIGHTS}")
    urllib.request.urlretrieve(WEIGHTS_URL, zpath)
    with zipfile.ZipFile(zpath) as z, open(WEIGHTS, "wb") as out:
        out.write(z.read("train_log/flownet.pkl"))
    os.remove(zpath)
    if sha256(WEIGHTS) != WEIGHTS_SHA256:
        os.remove(WEIGHTS)
        raise RuntimeError("받은 RIFE 가중치 해시가 다르다 — 링크가 바뀌었을 수 있다")
    return WEIGHTS


class Interpolator:
    def __init__(self, threads=None):
        if threads:
            torch.set_num_threads(threads)
        self.net = IFNet()
        state = torch.load(ensure_weights(), map_location="cpu", weights_only=True)  # pickle 코드 실행 금지
        self.net.load_state_dict({k.replace("module.", ""): v for k, v in state.items()}, strict=False)
        self.net.eval()

    @staticmethod
    def _tensor(img):
        a = np.asarray(img.convert("RGBA")).astype(np.float32) / 255.0
        rgb, alpha = a[:, :, :3], a[:, :, 3:4]
        pre = rgb * alpha
        flat = pre + BG * (1 - alpha)
        x = np.concatenate([flat, pre, alpha], axis=2).transpose(2, 0, 1)
        return torch.from_numpy(x)[None]

    @torch.no_grad()
    def between(self, img0, img1, t, scale=1.0):
        """scale < 1이면 흐름을 더 낮은 해상도에서 시작해 큰 움직임을 잡는다 (Practical-RIFE의 --scale과 같음)."""
        if img0.size != img1.size:
            raise ValueError("두 프레임 크기가 다르다")
        w, h = img0.size
        x0, x1 = self._tensor(img0), self._tensor(img1)
        unit = max(PAD, int(PAD / scale))
        ph, pw = -(-h // unit) * unit, -(-w // unit) * unit
        pad = (0, pw - w, 0, ph - h)
        # 패딩은 '투명 + 회색 배경'과 같은 값으로 채운다
        fill = torch.tensor([BG, BG, BG, 0, 0, 0, 0]).view(1, 7, 1, 1)
        x0 = torch.nn.functional.pad(x0 - fill, pad) + fill
        x1 = torch.nn.functional.pad(x1 - fill, pad) + fill
        merged, _, _, _ = self.net(torch.cat([x0, x1], 1), t, [s / scale for s in (16, 8, 4, 2, 1)])
        out = merged[0, 3:, :h, :w].numpy().transpose(1, 2, 0).clip(0, 1)
        alpha = out[:, :, 3:4]
        rgb = np.where(alpha > 1e-4, out[:, :, :3] / np.maximum(alpha, 1e-4), 0).clip(0, 1)
        arr = (np.concatenate([rgb, alpha], axis=2) * 255 + 0.5).astype(np.uint8)
        arr[arr[:, :, 3] <= ALPHA_FLOOR] = 0
        return Image.fromarray(arr)

    def inbetweens(self, img0, img1, n):
        """사이 n장을 흐름 해상도별로 만들어 번짐(최대값)이 가장 적은 세트를 고른다. 반환: (이미지들, scale, 번짐)"""
        base = (haze(img0) + haze(img1)) / 2
        best = None
        for scale in SCALES:
            imgs = [self.between(img0, img1, k / (n + 1), scale) for k in range(1, n + 1)]
            score = max(haze(im) for im in imgs) - base
            if best is None or score < best[2]:
                best = (imgs, scale, score)
        return best
