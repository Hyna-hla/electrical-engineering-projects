/**
 * @file    main.c
 * @brief   智能家居环境监测节点 —— 主程序 (STM32F103C8T6 + HAL)
 *
 * 功能:
 *   - 周期采集 DHT11 温湿度 / BH1750 光照 / MQ-2 烟雾
 *   - 按 1 帧/分钟 经 UART(115200) 上报环境数据
 *   - 烟雾或温湿度越限时立即主动上报告警帧
 *
 * 调度: 简单时间片轮转 (SysTick 1ms 计时), 各任务按周期执行。
 *       该结构便于后续迁移到 FreeRTOS (任务函数体可直接复用)。
 */
#include "stm32f1xx_hal.h"
#include <stdio.h>
#include <string.h>
#include "protocol.h"
#include "sensor_drivers.h"

/* ---------------- 外设句柄 (CubeMX 生成后由 main 关联) ---------------- */
UART_HandleTypeDef huart1;      /* PA9/PA10, 115200-8-N-1, 上位机通道 */
I2C_HandleTypeDef hi2c1;        /* PB6/PB7, BH1750 */
ADC_HandleTypeDef hadc1;       /* PA0, MQ-2 */

/* CubeMX 生成的初始化与时钟配置函数 */
extern void SystemClock_Config(void);
extern void MX_GPIO_Init(void);
extern void MX_USART1_UART_Init(void);
extern void MX_I2C1_Init(void);
extern void MX_ADC1_Init(void);

#define NODE_ID          0x01u
#define REPORT_PERIOD_MS 60000u   /* 环境数据上报周期: 1 分钟 */
#define SMOKE_TH         MQ2_ALARM_TH_ADC
#define TEMP_HI_TH       300      /* 30.0 °C (0.1°C 单位) */
#define TEMP_LO_TH       160      /* 16.0 °C */
#define HUMI_HI_TH       700      /* 70.0 %RH */
#define HUMI_LO_TH       300      /* 30.0 %RH */

static void send_frame(uint8_t type, const uint8_t *payload, uint8_t len)
{
    uint8_t buf[32];
    uint16_t n = protocol_pack(type, payload, len, buf);
    HAL_UART_Transmit(&huart1, buf, n, 100);
}

/** 环境采集 + 判限 + 上报 (周期任务, 也可被告警事件立即触发) */
static void task_env_report(void)
{
    dht11_data_t dht;
    env_payload_t p = {0};

    if (dht11_read(&dht) != 0) {
        /* 传感器失败: 发送全 0xFF 载荷示意, 上位机按缺测处理 */
        memset(&p, 0xFF, sizeof(p));
        p.node_id = NODE_ID;
        send_frame(TYPE_ENV_DATA, (const uint8_t *)&p, sizeof(p));
        return;
    }
    p.node_id   = NODE_ID;
    p.temp_x10  = (int16_t)(dht.temperature * 10);
    p.humi_x10  = (uint16_t)(dht.humidity * 10);
    p.lux       = bh1750_read(&hi2c1);
    p.smoke_adc = mq2_read_adc(&hadc1);
    p.batt_mv   = 3300;                     /* 示例: 电池电压检测省略 */

    send_frame(TYPE_ENV_DATA, (const uint8_t *)&p, sizeof(p));

    /* 越限判定 → 主动告警帧 (载荷: 节点号 + 告警码) */
    uint8_t alarm_code = 0;
    if (p.smoke_adc > SMOKE_TH)      alarm_code = 0x01;   /* 烟雾 */
    else if (p.temp_x10 > TEMP_HI_TH) alarm_code = 0x02;  /* 高温 */
    else if (p.temp_x10 < TEMP_LO_TH) alarm_code = 0x03;  /* 低温 */
    else if (p.humi_x10 > HUMI_HI_TH) alarm_code = 0x04;  /* 高湿 */
    else if (p.humi_x10 < HUMI_LO_TH) alarm_code = 0x05;  /* 低湿 */
    if (alarm_code) {
        uint8_t a[2] = { NODE_ID, alarm_code };
        send_frame(TYPE_ALARM, a, sizeof(a));
    }
}

int main(void)
{
    HAL_Init();
    SystemClock_Config();                   /* CubeMX 生成: 72MHz */
    MX_GPIO_Init();
    MX_USART1_UART_Init();
    MX_I2C1_Init();
    MX_ADC1_Init();

    /* DWT 使能: delay_us 需要 CYCCNT 计数器 */
    CoreDebug->DEMCR |= CoreDebug_DEMCR_TRCENA_Msk;
    DWT->CYCCNT = 0;
    DWT->CTRL |= DWT_CTRL_CYCCNTENA_Msk;

    bh1750_init(&hi2c1);
    HAL_ADCEx_Calibration_Start(&hadc1);    /* ADC 自校准 */

    uint32_t last_report = 0;
    for (;;) {
        if (HAL_GetTick() - last_report >= REPORT_PERIOD_MS) {
            last_report = HAL_GetTick();
            task_env_report();
        }
        /* 低功耗: 空闲期进入睡眠, UART/RTC 中断唤醒 (省略实现) */
    }
}
