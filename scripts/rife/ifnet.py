"""
RIFE v4.25 IFNet — 프레임 보간 모델 (추론 전용).

출처: Practical-RIFE (https://github.com/hzwer/Practical-RIFE) train_log/IFNet_HDv3.py, model/warplayer.py
라이선스: MIT, Copyright (c) 2021 hzwer. 학습 전용 코드를 빼고 warp를 이 파일로 옮긴 것 외에는 원본과 같다.
가중치(flownet.pkl)는 저장소에 넣지 않는다 — interpolate.py가 처음 쓸 때 받는다.
"""
import torch
import torch.nn as nn
import torch.nn.functional as F


def warp(x, flow):
    n, _, h, w = flow.shape
    gx = torch.linspace(-1.0, 1.0, w, device=flow.device).view(1, 1, 1, w).expand(n, -1, h, -1)
    gy = torch.linspace(-1.0, 1.0, h, device=flow.device).view(1, 1, h, 1).expand(n, -1, -1, w)
    grid = torch.cat([gx, gy], 1)
    flow = torch.cat([flow[:, 0:1] / ((w - 1.0) / 2.0), flow[:, 1:2] / ((h - 1.0) / 2.0)], 1)
    g = (grid + flow).permute(0, 2, 3, 1)
    return F.grid_sample(input=x, grid=g, mode="bilinear", padding_mode="border", align_corners=True)


def conv(in_planes, out_planes, kernel_size=3, stride=1, padding=1, dilation=1):
    return nn.Sequential(
        nn.Conv2d(in_planes, out_planes, kernel_size=kernel_size, stride=stride,
                  padding=padding, dilation=dilation, bias=True),
        nn.LeakyReLU(0.2, True),
    )


class Head(nn.Module):
    def __init__(self):
        super().__init__()
        self.cnn0 = nn.Conv2d(3, 16, 3, 2, 1)
        self.cnn1 = nn.Conv2d(16, 16, 3, 1, 1)
        self.cnn2 = nn.Conv2d(16, 16, 3, 1, 1)
        self.cnn3 = nn.ConvTranspose2d(16, 4, 4, 2, 1)
        self.relu = nn.LeakyReLU(0.2, True)

    def forward(self, x):
        x = self.relu(self.cnn0(x))
        x = self.relu(self.cnn1(x))
        x = self.relu(self.cnn2(x))
        return self.cnn3(x)


class ResConv(nn.Module):
    def __init__(self, c, dilation=1):
        super().__init__()
        self.conv = nn.Conv2d(c, c, 3, 1, dilation, dilation=dilation, groups=1)
        self.beta = nn.Parameter(torch.ones((1, c, 1, 1)), requires_grad=True)
        self.relu = nn.LeakyReLU(0.2, True)

    def forward(self, x):
        return self.relu(self.conv(x) * self.beta + x)


class IFBlock(nn.Module):
    def __init__(self, in_planes, c=64):
        super().__init__()
        self.conv0 = nn.Sequential(conv(in_planes, c // 2, 3, 2, 1), conv(c // 2, c, 3, 2, 1))
        self.convblock = nn.Sequential(*[ResConv(c) for _ in range(8)])
        self.lastconv = nn.Sequential(nn.ConvTranspose2d(c, 4 * 13, 4, 2, 1), nn.PixelShuffle(2))

    def forward(self, x, flow=None, scale=1):
        x = F.interpolate(x, scale_factor=1. / scale, mode="bilinear", align_corners=False)
        if flow is not None:
            flow = F.interpolate(flow, scale_factor=1. / scale, mode="bilinear", align_corners=False) * 1. / scale
            x = torch.cat((x, flow), 1)
        feat = self.conv0(x)
        feat = self.convblock(feat)
        tmp = self.lastconv(feat)
        tmp = F.interpolate(tmp, scale_factor=scale, mode="bilinear", align_corners=False)
        return tmp[:, :4] * scale, tmp[:, 4:5], tmp[:, 5:]


class IFNet(nn.Module):
    """
    입력 x = cat(img0, img1) — 각 C채널. 흐름은 앞 3채널(RGB)로만 계산하고 워프는 C채널 전부에 건다.
    그래서 RGB 뒤에 알파 등 채널을 더 붙이면 같은 움직임으로 함께 보간된다.
    반환: (최종 합성, 시점 t로 워프한 img0, 워프한 img1, 섞기 마스크)
    """

    def __init__(self):
        super().__init__()
        self.block0 = IFBlock(7 + 8, c=192)
        self.block1 = IFBlock(8 + 4 + 8 + 8, c=128)
        self.block2 = IFBlock(8 + 4 + 8 + 8, c=96)
        self.block3 = IFBlock(8 + 4 + 8 + 8, c=64)
        self.block4 = IFBlock(8 + 4 + 8 + 8, c=32)
        self.encode = Head()

    def forward(self, x, timestep=0.5, scale_list=(16, 8, 4, 2, 1)):
        channel = x.shape[1] // 2
        img0, img1 = x[:, :channel], x[:, channel:]
        timestep = (x[:, :1].clone() * 0 + 1) * timestep
        f0 = self.encode(img0[:, :3])
        f1 = self.encode(img1[:, :3])
        warped0, warped1 = img0, img1
        flow = mask = feat = None
        blocks = [self.block0, self.block1, self.block2, self.block3, self.block4]
        for i, block in enumerate(blocks):
            if flow is None:
                flow, mask, feat = block(torch.cat((img0[:, :3], img1[:, :3], f0, f1, timestep), 1), None, scale=scale_list[i])
            else:
                wf0 = warp(f0, flow[:, :2])
                wf1 = warp(f1, flow[:, 2:4])
                fd, mask, feat = block(torch.cat((warped0[:, :3], warped1[:, :3], wf0, wf1, timestep, mask, feat), 1),
                                       flow, scale=scale_list[i])
                flow = flow + fd
            warped0 = warp(img0, flow[:, :2])
            warped1 = warp(img1, flow[:, 2:4])
        mask = torch.sigmoid(mask)
        return warped0 * mask + warped1 * (1 - mask), warped0, warped1, mask
