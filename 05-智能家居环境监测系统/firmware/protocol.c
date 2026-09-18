/**
 * @file    protocol.c
 * @brief   帧打包与 CRC8 校验实现 (与上位机 protocol.py 逐字节兼容)
 */
#include "protocol.h"

/**
 * @brief CRC-8 校验 (多项式 0x07, 初值 0x00)
 *        上位机 Python 侧有相同实现, 联调时用于交叉验证
 */
uint8_t crc8(const uint8_t *data, uint16_t len)
{
    uint8_t crc = 0x00;
    for (uint16_t i = 0; i < len; i++) {
        crc ^= data[i];
        for (uint8_t b = 0; b < 8; b++) {
            crc = (crc & 0x80u) ? (uint8_t)((crc << 1) ^ 0x07u)
                                : (uint8_t)(crc << 1);
        }
    }
    return crc;
}

/**
 * @brief  按协议封装一帧
 * @return 帧总长度 (字节); out_buf 需至少 len + 6 字节
 */
uint16_t protocol_pack(uint8_t type, const uint8_t *payload, uint8_t len,
                       uint8_t *out_buf)
{
    uint16_t idx = 0;

    out_buf[idx++] = FRAME_HEAD1;
    out_buf[idx++] = FRAME_HEAD2;
    out_buf[idx++] = len;              /* LEN */
    out_buf[idx++] = type;             /* TYPE */

    for (uint8_t i = 0; i < len; i++) {
        out_buf[idx++] = payload[i];
    }

    out_buf[idx++] = crc8(&out_buf[2], (uint16_t)(len + 2));  /* CRC: LEN+TYPE+PAYLOAD */
    out_buf[idx++] = FRAME_TAIL;
    return idx;
}
