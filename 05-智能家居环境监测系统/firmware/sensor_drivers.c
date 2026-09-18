/**
 * @file    sensor_drivers.c
 * @brief   传感器驱动实现 (STM32F103 + HAL 库)
 */
#include "sensor_drivers.h"
#include <string.h>

/* ============================================================
 * DHT11 单总线驱动 —— GPIO 位操作实现 40bit 时序读取
 * ============================================================ */
static void dht11_mode_out(void)
{
    GPIO_InitTypeDef g = {0};
    g.Pin = DHT11_GPIO_PIN;
    g.Mode = GPIO_MODE_OUTPUT_PP;
    g.Speed = GPIO_SPEED_FREQ_HIGH;
    HAL_GPIO_Init(DHT11_GPIO_PORT, &g);
}

static void dht11_mode_in(void)
{
    GPIO_InitTypeDef g = {0};
    g.Pin = DHT11_GPIO_PIN;
    g.Mode = GPIO_MODE_INPUT;
    g.Pull = GPIO_PULLUP;
    HAL_GPIO_Init(DHT11_GPIO_PORT, &g);
}

/* 微秒延时: 基于 DWT 周期计数器 (72MHz 主频) */
static inline void delay_us(uint32_t us)
{
    uint32_t start = DWT->CYCCNT;
    uint32_t ticks = us * (SystemCoreClock / 1000000u);
    while ((DWT->CYCCNT - start) < ticks) {
        /* busy wait */
    }
}

int dht11_read(dht11_data_t *out)
{
    uint8_t raw[5] = {0};

    /* 1. 主机起始信号: 拉低 18ms 再释放 20~40us */
    dht11_mode_out();
    HAL_GPIO_WritePin(DHT11_GPIO_PORT, DHT11_GPIO_PIN, GPIO_PIN_RESET);
    HAL_Delay(18);
    HAL_GPIO_WritePin(DHT11_GPIO_PORT, DHT11_GPIO_PIN, GPIO_PIN_SET);
    delay_us(25);
    dht11_mode_in();

    /* 2. 等待 DHT11 响应: 80us 低 + 80us 高 */
    uint32_t timeout = 0;
    while (HAL_GPIO_ReadPin(DHT11_GPIO_PORT, DHT11_GPIO_PIN) == GPIO_PIN_SET) {
        if (++timeout > 100) {
            return 1;                       /* 无响应 */
        }
        delay_us(1);
    }
    timeout = 0;
    while (HAL_GPIO_ReadPin(DHT11_GPIO_PORT, DHT11_GPIO_PIN) == GPIO_PIN_RESET) {
        if (++timeout > 100) {
            return 1;
        }
        delay_us(1);
    }

    /* 3. 读 40bit: 每 bit 以 50us 低电平开始, 高电平 26~28us=0 / 70us=1 */
    for (int i = 0; i < 40; i++) {
        timeout = 0;
        while (HAL_GPIO_ReadPin(DHT11_GPIO_PORT, DHT11_GPIO_PIN) == GPIO_PIN_RESET) {
            delay_us(1);
            if (++timeout > 60) {
                return 1;
            }
        }
        delay_us(40);                        /* 40us 后采样 */
        if (HAL_GPIO_ReadPin(DHT11_GPIO_PORT, DHT11_GPIO_PIN) == GPIO_PIN_SET) {
            raw[i / 8] |= (uint8_t)(1u << (7 - (i % 8)));
            while (HAL_GPIO_ReadPin(DHT11_GPIO_PORT, DHT11_GPIO_PIN) == GPIO_PIN_SET) {
                delay_us(1);
            }
        }
    }

    /* 4. 校验和验证: 前 4 字节之和的低 8 位 == 第 5 字节 */
    if ((uint8_t)(raw[0] + raw[1] + raw[2] + raw[3]) != raw[4]) {
        return 2;
    }
    out->humidity = raw[0] + raw[1] * 0.1f;
    out->temperature = (int8_t)raw[2] + raw[3] * 0.1f;
    return 0;
}

/* ============================================================
 * BH1750 光照传感器 —— I2C 命令 + 2 字节读数
 * ============================================================ */
void bh1750_init(I2C_HandleTypeDef *hi2c)
{
    uint8_t cmd = BH1750_CMD_CONT_H;
    HAL_I2C_Master_Transmit(hi2c, BH1750_ADDR, &cmd, 1, 100);
    HAL_Delay(180);                          /* 首次测量时间 (最大 180ms) */
}

uint16_t bh1750_read(I2C_HandleTypeDef *hi2c)
{
    uint8_t buf[2];
    if (HAL_I2C_Master_Receive(hi2c, BH1750_ADDR, buf, 2, 100) != HAL_OK) {
        return 0xFFFF;
    }
    return (uint16_t)((buf[0] << 8) | buf[1]) / 2u;  /* 寄存器值 / 2 = lux */
}

/* ============================================================
 * MQ-2 烟雾传感器 —— ADC 采样 + 中值滤波
 * ============================================================ */
static void sort_u16(uint16_t *a, int n)
{
    for (int i = 0; i < n - 1; i++) {
        for (int j = 0; j < n - 1 - i; j++) {
            if (a[j] > a[j + 1]) {
                uint16_t t = a[j];
                a[j] = a[j + 1];
                a[j + 1] = t;
            }
        }
    }
}

uint16_t mq2_read_adc(ADC_HandleTypeDef *hadc)
{
    uint16_t samples[8];
    for (int i = 0; i < 8; i++) {
        HAL_ADC_Start(hadc);
        HAL_ADC_PollForConversion(hadc, 10);
        samples[i] = (uint16_t)HAL_ADC_GetValue(hadc);
        HAL_ADC_Stop(hadc);
        HAL_Delay(2);                        /* MQ-2 响应较慢, 间隔采样 */
    }
    sort_u16(samples, 8);
    return samples[4];                       /* 中值: 抗脉冲干扰 */
}
