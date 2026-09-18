# -*- coding: utf-8 -*-
"""
上下位机通信协议 —— Python 端实现
====================================
与 firmware/protocol.c 逐字节兼容, 联调时两侧 CRC 结果必须一致。

帧格式 (小端序):
    AA 55 | LEN | TYPE | PAYLOAD(LEN 字节) | CRC8 | 0D
    CRC8: 多项式 0x07, 初值 0x00, 校验范围 LEN+TYPE+PAYLOAD
"""
import struct

FRAME_HEAD = b'\xAA\x55'
FRAME_TAIL = 0x0D

TYPE_ENV_DATA = 0x01
TYPE_ALARM = 0x02
TYPE_ACK = 0x03

ENV_PAYLOAD_FMT = '<BhhHHH'   # node, temp×10, humi×10, lux, smoke, batt_mv
ENV_PAYLOAD_LEN = struct.calcsize(ENV_PAYLOAD_FMT)


def crc8(data: bytes) -> int:
    """CRC-8 (poly=0x07, init=0x00) —— 与固件 crc8() 一致"""
    crc = 0
    for byte in data:
        crc ^= byte
        for _ in range(8):
            crc = ((crc << 1) ^ 0x07) & 0xFF if crc & 0x80 else (crc << 1) & 0xFF
    return crc


def build_frame(frame_type: int, payload: bytes) -> bytes:
    """封装一帧 (上位机下发 ACK 时使用)"""
    body = bytes([len(payload), frame_type]) + payload
    return FRAME_HEAD + body + bytes([crc8(body), FRAME_TAIL])


class FrameParser:
    """
    字节流解析状态机 (处理粘包/断包/噪声字节)
    用法: parser.feed(chunk) → 返回本批解析出的 (type, payload) 列表
    """

    def __init__(self):
        self._buf = bytearray()
        self.bad_frames = 0     # CRC 校验失败计数
        self.good_frames = 0

    def feed(self, chunk: bytes):
        self._buf.extend(chunk)
        frames = []
        while True:
            # 1. 找帧头
            idx = self._buf.find(FRAME_HEAD)
            if idx < 0:
                # 未找到: 丢弃噪声, 但保留末尾可能是帧头首字节的 0xAA
                # (否则跨块到达的帧头会被误删导致丢帧)
                if self._buf and self._buf[-1] == 0xAA:
                    del self._buf[:-1]
                else:
                    self._buf.clear()
                break
            if idx > 0:
                del self._buf[:idx]           # 丢弃帧头前的噪声字节
            if len(self._buf) < 4:
                break                          # 不足 LEN+TYPE, 等待
            length = self._buf[2]
            total = 2 + 1 + 1 + length + 1 + 1
            if len(self._buf) < total:
                break                          # 帧未接收完整
            frame = self._buf[:total]
            # 2. 帧尾与 CRC 校验
            if frame[-1] != FRAME_TAIL or crc8(bytes(frame[2:-2])) != frame[-2]:
                self.bad_frames += 1
                del self._buf[:2]              # 跳过本"帧头", 继续找下一个
                continue
            self.good_frames += 1
            frames.append((frame[3], bytes(frame[4:4 + length])))
            del self._buf[:total]
        return frames


def decode_env(payload: bytes) -> dict:
    """解码环境数据帧载荷"""
    node, temp_x10, humi_x10, lux, smoke, batt = struct.unpack(
        ENV_PAYLOAD_FMT, payload[:ENV_PAYLOAD_LEN])
    return {
        'node': node,
        'temp': temp_x10 / 10.0,
        'humi': humi_x10 / 10.0,
        'lux': lux,
        'smoke': smoke,
        'batt_mv': batt,
    }
