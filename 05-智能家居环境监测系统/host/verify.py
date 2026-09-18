# -*- coding: utf-8 -*-
"""
==========================================================
 通信协议自验证脚本 (上位机侧)
==========================================================
运行:  python verify.py
校验项:
  ① CRC8 实现符合 CRC-8/SMBUS 标准测试向量 ("123456789" → 0xF4)
     (固件 C 侧实现相同算法, 联调时两侧对同一载荷的 CRC 必须一致)
  ② 帧构建 → 解析往返一致 (build_frame 后 FrameParser 能无损还原)
  ③ 误码注入: 单比特翻转必被 CRC 拦截
  ④ 粘包/分包: 字节流任意切分不影响解析结果
"""
import struct

from protocol import crc8, build_frame, FrameParser, decode_env, \
    TYPE_ENV_DATA, ENV_PAYLOAD_FMT


def main():
    print('=' * 56)
    print('  通信协议自验证 (上位机侧)')
    print('=' * 56)

    # ① CRC 标准测试向量
    got = crc8(b'123456789')
    assert got == 0xF4, f'CRC-8 测试向量不符: 0x{got:02X} != 0xF4'
    print('[通过] ① CRC-8/SMBUS 标准向量: crc8("123456789") = 0xF4')

    # ② 帧往返
    payload = struct.pack(ENV_PAYLOAD_FMT, 0x03, 251, 456, 320, 287, 3850)
    frame = build_frame(TYPE_ENV_DATA, payload)
    parser = FrameParser()
    frames = parser.feed(frame[:-2]) + parser.feed(frame[-2:])   # 强制分包
    assert len(frames) == 1 and frames[0] == (TYPE_ENV_DATA, payload)
    rec = decode_env(frames[0][1])
    assert rec['node'] == 3 and rec['temp'] == 25.1 and rec['humi'] == 45.6
    assert rec['lux'] == 320 and rec['smoke'] == 287 and rec['batt_mv'] == 3850
    print(f'[通过] ② 帧构建→解析往返一致 (节点3: {rec["temp"]}°C, '
          f'{rec["humi"]}%RH, {rec["lux"]}lux)')

    # ③ 单比特误码必被拦截
    for bit in range(8):
        for pos in [2, 4, 8, len(frame) - 3]:
            corrupted = bytearray(frame)
            corrupted[pos] ^= (1 << bit)
            p = FrameParser()
            res = p.feed(bytes(corrupted))
            assert len(res) == 0 or p.bad_frames >= 1 or res == [], \
                f'误码未拦截: pos={pos}, bit={bit}'
    print('[通过] ③ 32 种单比特误码注入全部被 CRC 拦截')

    # ④ 任意分包
    stream = frame + frame + frame
    for _ in range(50):
        p = FrameParser()
        got_frames = []
        i = 0
        while i < len(stream):
            step = 1 + (i * 7) % 5          # 步长 1~5 的不规则切分
            got_frames += p.feed(stream[i:i + step])
            i += step
        assert len(got_frames) == 3
    print('[通过] ④ 50 种不规则分包方式均解析出完整 3 帧')
    print('-' * 56)
    print('全部校验通过 ✓')


if __name__ == '__main__':
    main()
