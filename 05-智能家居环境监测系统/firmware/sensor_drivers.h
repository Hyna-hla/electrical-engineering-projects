/**
 * @file    sensor_drivers.h
 * @brief   传感器驱动接口 (STM32 HAL)
 *          DHT11 温湿度 / BH1750 光照(I2C) / MQ-2 烟雾(ADC)
 */
#ifndef SENSOR_DRIVERS_H
#define SENSOR_DRIVERS_H

#include "stm32f1xx_hal.h"
#include <stdint.h>

/* ---------------- DHT11 单总线温湿度 ---------------- */
#define DHT11_GPIO_PORT  GPIOB
#define DHT11_GPIO_PIN   GPIO_PIN_5

typedef struct {
    float temperature;   /* °C */
    float humidity;      /* %RH */
} dht11_data_t;

/**
 * @brief 读取 DHT11 (单总线时序: 主机拉低 18ms → 释放 → 读 40bit)
 * @return 0 成功; 1 无响应; 2 校验和错误
 */
int dht11_read(dht11_data_t *out);

/* ---------------- BH1750 光照 (I2C, 地址 0x23) ---------------- */
#define BH1750_ADDR       (0x23 << 1)
#define BH1750_CMD_CONT_H 0x10u   /* 连续高分辨率模式, 1 lux 分辨率 */

/**
 * @brief 初始化 BH1750 (发送测量模式命令)
 */
void bh1750_init(I2C_HandleTypeDef *hi2c);

/**
 * @brief 读取光照强度
 * @return lux 值; 通信失败返回 0xFFFF
 */
uint16_t bh1750_read(I2C_HandleTypeDef *hi2c);

/* ---------------- MQ-2 烟雾 (ADC 通道) ---------------- */
#define MQ2_ALARM_TH_ADC  1000u    /* 告警阈值 (12bit ADC 原始值) */

/**
 * @brief 读取 MQ-2 的 ADC 原始值 (内部完成 8 次采样中值滤波)
 */
uint16_t mq2_read_adc(ADC_HandleTypeDef *hadc);

#endif /* SENSOR_DRIVERS_H */
