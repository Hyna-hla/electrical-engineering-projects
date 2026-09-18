/**
 * @file    protocol.h
 * @brief   上下位机通信协议 —— 帧格式定义 (与上位机 protocol.py 保持一致)
 *
 * 帧格式 (小端序):
 * +--------+--------+--------+--------+---------+--------+--------+
 * | 0xAA   | 0x55   | LEN    | TYPE   | PAYLOAD | CRC8   | 0x0D   |
 * | 帧头1  | 帧头2  | 载荷长 | 帧类型 | LEN 字节 | 校验   | 帧尾   |
 * +--------+--------+--------+--------+---------+--------+--------+
 *
 * CRC8 多项式: x^8 + x^2 + x + 1 (0x07), 初值 0x00
 * CRC 校验范围: LEN + TYPE + PAYLOAD
 */
#ifndef PROTOCOL_H
#define PROTOCOL_H

#include <stdint.h>

#define FRAME_HEAD1   0xAAu
#define FRAME_HEAD2   0x55u
#define FRAME_TAIL    0x0Du

#define TYPE_ENV_DATA 0x01u   /* 环境数据帧 */
#define TYPE_ALARM    0x02u   /* 告警主动上报帧 */
#define TYPE_ACK      0x03u   /* 上位机应答帧 */

/* 环境数据帧载荷 (11 字节) */
#pragma pack(push, 1)
typedef struct {
    uint8_t  node_id;    /* 节点编号 */
    int16_t  temp_x10;   /* 温度, 0.1 °C */
    uint16_t humi_x10;   /* 湿度, 0.1 %RH */
    uint16_t lux;        /* 光照强度 */
    uint16_t smoke_adc;  /* MQ-2 烟雾 ADC 原始值 (12bit) */
    uint16_t batt_mv;    /* 电池电压 mV */
} env_payload_t;
#pragma pack(pop)

uint8_t crc8(const uint8_t *data, uint16_t len);
uint16_t protocol_pack(uint8_t type, const uint8_t *payload, uint8_t len,
                       uint8_t *out_buf);

#endif /* PROTOCOL_H */
