# SPDX-FileCopyrightText: 2026 the saidby authors
# SPDX-License-Identifier: Apache-2.0

# SPDX-FileCopyrightText: 2021 Shuai Wang
# SPDX-FileCopyrightText: 2022 Zhengyang Chen
# SPDX-FileCopyrightText: 2023 Bing Han
# SPDX-FileCopyrightText: 2023 CNRS
# SPDX-License-Identifier: Apache-2.0

import torch
from torch import nn
from torch.nn import functional


class BasicBlock(nn.Module):
    expansion = 1

    def __init__(self, in_planes: int, planes: int, stride: int = 1) -> None:
        super().__init__()
        self.conv1 = nn.Conv2d(in_planes, planes, 3, stride=stride, padding=1, bias=False)
        self.bn1 = nn.BatchNorm2d(planes)
        self.conv2 = nn.Conv2d(planes, planes, 3, stride=1, padding=1, bias=False)
        self.bn2 = nn.BatchNorm2d(planes)
        self.shortcut = nn.Sequential()
        if stride != 1 or in_planes != planes:
            self.shortcut = nn.Sequential(
                nn.Conv2d(in_planes, planes, 1, stride=stride, bias=False),
                nn.BatchNorm2d(planes),
            )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        out = functional.relu(self.bn1(self.conv1(x)))
        out = self.bn2(self.conv2(out))
        return functional.relu(out + self.shortcut(x))


class ResNet34(nn.Module):
    def __init__(self, feat_dim: int = 80, embed_dim: int = 256, m_channels: int = 32) -> None:
        super().__init__()
        self.embed_dim = embed_dim
        self.in_planes = m_channels
        stats_dim = int(feat_dim / 8) * m_channels * 8
        self.conv1 = nn.Conv2d(1, m_channels, 3, stride=1, padding=1, bias=False)
        self.bn1 = nn.BatchNorm2d(m_channels)
        self.layer1 = self._make_layer(m_channels, 3, stride=1)
        self.layer2 = self._make_layer(m_channels * 2, 4, stride=2)
        self.layer3 = self._make_layer(m_channels * 4, 6, stride=2)
        self.layer4 = self._make_layer(m_channels * 8, 3, stride=2)
        self.seg_1 = nn.Linear(stats_dim * 2, embed_dim)

    def _make_layer(self, planes: int, blocks: int, stride: int) -> nn.Sequential:
        layers = []
        for s in [stride] + [1] * (blocks - 1):
            layers.append(BasicBlock(self.in_planes, planes, s))
            self.in_planes = planes
        return nn.Sequential(*layers)

    def forward(self, fbank: torch.Tensor) -> torch.Tensor:
        x = fbank.permute(0, 2, 1).unsqueeze(1)
        x = functional.relu(self.bn1(self.conv1(x)))
        x = self.layer4(self.layer3(self.layer2(self.layer1(x))))
        batch, dim, channels, frames = x.shape
        x = x.reshape(batch, dim * channels, frames)
        stats = torch.cat([x.mean(dim=-1), x.std(dim=-1, correction=1)], dim=-1)
        embedding: torch.Tensor = self.seg_1(stats)
        return embedding
