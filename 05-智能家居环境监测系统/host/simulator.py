# -*- coding: utf-8 -*-
"""
节点数据仿真源
================
无硬件时替代串口输入: 按 1 帧/分钟模拟一个房间节点 24 小时的
温度/湿度/光照/烟雾数据, 并以 0.5% 概率注入误码帧 (考验 CRC)。

真实部署时, 将 monitor.py 中的 `SerialSimSource` 替换为
`pyserial` 读取即可, 其余代码不变。
"""
import struct
import numpy as np

from protocol import build_frame, TYPE_ENV_DATA, ENV_PAYLOAD_FMT


class SerialSimSource:
    """模拟串口字节流 (分块吐出, 还原真实粘包/分包场景)"""

    def __init__(self, hours=24.0, seed=7):
        self.hours = hours
        self.rng = np.random.default_rng(seed)
        self._frames = self._gen_all_frames()
        self._stream = b''.join(self._frames)
        self._pos = 0
        self._chunk_counter = 0

    # ---------- 环境模型 ----------
    def _env_at(self, minute):
        h = minute / 60.0
        day = np.sin((h - 8) / 24 * 2 * np.pi)     # 昼夜相位
        # 温度: 基值 24°C, 白天升高, 午后空调机房波动
        temp = 23.5 + 2.5 * day + self.rng.normal(0, 0.15)
        # 湿度: 与温度弱负相关
        humi = 52 - 8 * day + self.rng.normal(0, 1.2)
        # 光照: 白天 300~600 lux, 夜间 <2 lux, 偶尔夜间开灯
        daylight = max(0.0, day + 0.25)
        lux = daylight * 450 + self.rng.normal(0, 8)
        if self.rng.random() < 0.006:              # 夜间偶发开灯
            lux += 200
        # 烟雾: 基线 ~320 ADC, 14:10~14:35 模拟"消防演练烟雾事件"
        smoke = 320 + self.rng.normal(0, 15)
        if 14 * 60 + 10 <= minute <= 14 * 60 + 35:
            smoke += 1400 * np.exp(-((minute - (14 * 60 + 22)) / 6.0) ** 2)
        # 电池缓降: 3.9V → 3.6V
        batt = int(3900 - 300 * minute / (self.hours * 60))
        return (max(-10, min(50, temp)), max(15, min(90, humi)),
                max(0, lux), max(0, smoke), batt)

    def _gen_all_frames(self):
        n = int(self.hours * 60)
        frames = []
        for m in range(n):
            temp, humi, lux, smoke, batt = self._env_at(m)
            payload = struct.pack(
                ENV_PAYLOAD_FMT, 0x01,
                int(temp * 10), int(humi * 10), int(lux), int(smoke), batt)
            frame = build_frame(TYPE_ENV_DATA, payload)
            # 0.5% 概率随机翻转 1 字节 → 注入误码, 考验上位机 CRC
            if self.rng.random() < 0.005:
                pos = self.rng.integers(2, len(frame) - 2)
                frame = frame[:pos] + bytes([frame[pos] ^ 0x55]) + frame[pos + 1:]
            frames.append(frame)
        return frames

    # ---------- 串口式接口 ----------
    def read_chunk(self, max_bytes=64) -> bytes:
        """模拟串口 read: 一次返回不定的字节数 (形成分包)"""
        if self._pos >= len(self._stream):
            return b''
        self._chunk_counter += 1
        size = int(self.rng.integers(8, max_bytes))
        chunk = self._stream[self._pos:self._pos + size]
        self._pos += size
        return chunk

    @property
    def finished(self):
        return self._pos >= len(self._stream)
