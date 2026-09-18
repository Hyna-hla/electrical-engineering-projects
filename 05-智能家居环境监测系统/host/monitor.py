# -*- coding: utf-8 -*-
"""
==========================================================
 智能家居环境监测系统 —— 上位机监控软件
==========================================================
运行:  python monitor.py
功能:  从串口(仿真源)接收数据帧 → CRC 校验 → 解码 → 越限告警
       → CSV 记录 → 24h 趋势图与运行统计报告
真实部署: 将 SerialSimSource 换成 pyserial 打开的 COM 口即可。
"""
import os
import csv
import numpy as np
import matplotlib.pyplot as plt
import matplotlib as mpl

from protocol import FrameParser, decode_env
from simulator import SerialSimSource

mpl.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei']
mpl.rcParams['axes.unicode_minus'] = False

OUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'results')

# 告警阈值 (与固件侧一致)
TH = {'temp_hi': 30.0, 'temp_lo': 16.0,
      'humi_hi': 70.0, 'humi_lo': 30.0, 'smoke': 1000}

ALARM_NAMES = {'temp_hi': '高温', 'temp_lo': '低温', 'humi_hi': '高湿',
               'humi_lo': '低湿', 'smoke': '烟雾'}


def check_alarms(rec):
    """越限判定, 返回命中的告警码列表"""
    hits = []
    if rec['temp'] > TH['temp_hi']:
        hits.append('temp_hi')
    if rec['temp'] < TH['temp_lo']:
        hits.append('temp_lo')
    if rec['humi'] > TH['humi_hi']:
        hits.append('humi_hi')
    if rec['humi'] < TH['humi_lo']:
        hits.append('humi_lo')
    if rec['smoke'] > TH['smoke']:
        hits.append('smoke')
    return hits


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    src = SerialSimSource(hours=24.0)
    parser = FrameParser()

    records, alarms = [], []
    while not src.finished:
        chunk = src.read_chunk()
        for ftype, payload in parser.feed(chunk):
            if ftype != 1:
                continue
            rec = decode_env(payload)
            rec['minute'] = len(records)
            records.append(rec)
            for code in check_alarms(rec):
                alarms.append((rec['minute'], code, rec['temp'], rec['smoke']))

    t = np.array([r['minute'] / 60.0 for r in records])
    temp = np.array([r['temp'] for r in records])
    humi = np.array([r['humi'] for r in records])
    lux = np.array([r['lux'] for r in records])
    smoke = np.array([r['smoke'] for r in records])

    # ---------- 控制台统计 ----------
    n_bad = parser.bad_frames
    n_all = n_bad + parser.good_frames
    print('=' * 60)
    print('   智能家居环境监测系统 —— 24 小时运行统计')
    print('=' * 60)
    print(f"接收帧: {n_all} | CRC 校验通过: {parser.good_frames}"
          f" | 误码丢弃: {n_bad} ({n_bad / n_all * 100:.2f}%)")
    print(f"温度范围: {temp.min():.1f} ~ {temp.max():.1f} °C"
          f" | 湿度范围: {humi.min():.0f} ~ {humi.max():.0f} %RH")
    print(f"告警总数: {len(alarms)} 次")
    for code in ALARM_NAMES:
        cnt = sum(1 for a in alarms if a[1] == code)
        if cnt:
            print(f"  - {ALARM_NAMES[code]}: {cnt} 次")

    # ---------- CSV 记录 ----------
    csv_path = os.path.join(OUT_DIR, '环境监测记录.csv')
    with open(csv_path, 'w', newline='', encoding='utf-8-sig') as f:
        w = csv.writer(f)
        w.writerow(['时间(h)', '节点', '温度(°C)', '湿度(%RH)', '光照(lux)',
                    '烟雾(ADC)', '电池(mV)'])
        for r in records:
            w.writerow([f"{r['minute'] / 60:.2f}", r['node'], f"{r['temp']:.1f}",
                        f"{r['humi']:.1f}", int(r['lux']), int(r['smoke']),
                        r['batt_mv']])

    # ---------- 绘图 ----------
    alarm_t = [a[0] / 60.0 for a in alarms if a[1] == 'smoke']

    # 图1: 温湿度趋势
    fig, ax1 = plt.subplots(figsize=(11, 5))
    ax1.plot(t, temp, color='#d9534f', lw=1.3, label='温度 (°C)')
    ax1.set_xlabel('时间 (h)')
    ax1.set_ylabel('温度 (°C)', color='#d9534f')
    ax1.axhline(TH['temp_hi'], ls='--', color='#d9534f', lw=0.8, alpha=0.6)
    ax2 = ax1.twinx()
    ax2.plot(t, humi, color='#2b6cb0', lw=1.3, label='湿度 (%RH)')
    ax2.set_ylabel('湿度 (%RH)', color='#2b6cb0')
    ax2.axhline(TH['humi_lo'], ls='--', color='#2b6cb0', lw=0.8, alpha=0.6)
    h1, l1 = ax1.get_legend_handles_labels()
    h2, l2 = ax2.get_legend_handles_labels()
    ax1.legend(h1 + h2, l1 + l2, loc='upper left')
    ax1.set_title('24 小时温湿度监测趋势 (虚线为告警阈值)')
    ax1.grid(ls=':', alpha=0.4)
    fig.tight_layout()
    fig.savefig(os.path.join(OUT_DIR, '1_温湿度趋势.png'), dpi=160)
    plt.close(fig)

    # 图2: 光照昼夜曲线
    fig, ax = plt.subplots(figsize=(11, 4.5))
    ax.plot(t, lux, color='#e8964a', lw=1.1)
    ax.fill_between(t, 0, lux, color='#e8964a', alpha=0.2)
    ax.set_xlabel('时间 (h)')
    ax.set_ylabel('光照 (lux)')
    ax.set_title('24 小时光照强度曲线 (昼夜节律清晰, 夜间偶发开灯事件)')
    ax.grid(ls=':', alpha=0.4)
    fig.tight_layout()
    fig.savefig(os.path.join(OUT_DIR, '2_光照趋势.png'), dpi=160)
    plt.close(fig)

    # 图3: 烟雾与告警事件
    fig, ax = plt.subplots(figsize=(11, 4.5))
    ax.plot(t, smoke, color='#7a4ba6', lw=1.1, label='MQ-2 ADC 值')
    ax.axhline(TH['smoke'], ls='--', color='#d9534f', lw=1.4,
               label='烟雾告警阈值 (1000)')
    if alarm_t:
        ax.axvspan(min(alarm_t), max(alarm_t), color='#d9534f', alpha=0.15,
                   label=f'告警时段 ({len(alarm_t)} 分钟)')
    ax.set_xlabel('时间 (h)')
    ax.set_ylabel('ADC 原始值')
    ax.set_title('烟雾监测与告警事件 (14:10~14:35 消防演练)')
    ax.legend()
    ax.grid(ls=':', alpha=0.4)
    fig.tight_layout()
    fig.savefig(os.path.join(OUT_DIR, '3_烟雾告警事件.png'), dpi=160)
    plt.close(fig)

    # 图4: 电池电压与链路质量
    batt = np.array([r['batt_mv'] for r in records])
    fig, ax1 = plt.subplots(figsize=(11, 4.5))
    ax1.plot(t, batt, color='#3d8b3d', lw=1.3)
    ax1.set_xlabel('时间 (h)')
    ax1.set_ylabel('节点电池电压 (mV)', color='#3d8b3d')
    ax2 = ax1.twinx()
    ax2.axhline(n_bad / n_all * 100, color='#d9534f', ls='--',
                label=f'链路平均误帧率 {n_bad / n_all * 100:.2f}% (CRC 全部拦截)')
    ax2.set_ylabel('误帧率 (%)', color='#d9534f')
    ax2.legend(loc='upper right')
    ax1.set_title('节点电池电压趋势与通信链路质量')
    ax1.grid(ls=':', alpha=0.4)
    fig.tight_layout()
    fig.savefig(os.path.join(OUT_DIR, '4_电池与链路质量.png'), dpi=160)
    plt.close(fig)

    # ---------- 报告 ----------
    with open(os.path.join(OUT_DIR, '运行统计报告.txt'), 'w', encoding='utf-8') as f:
        f.write('智能家居环境监测系统 24h 运行报告\n' + '=' * 40 + '\n')
        f.write(f'接收帧总数: {n_all}, CRC 丢弃: {n_bad}, 有效率 '
                f'{parser.good_frames / n_all * 100:.2f}%\n')
        f.write(f'温度: {temp.min():.1f}~{temp.max():.1f} °C, '
                f'湿度: {humi.min():.0f}~{humi.max():.0f} %RH\n')
        f.write(f'告警: {len(alarms)} 次\n')
        for code in ALARM_NAMES:
            cnt = sum(1 for a in alarms if a[1] == code)
            if cnt:
                f.write(f'  {ALARM_NAMES[code]}: {cnt} 次\n')
        f.write(f'电池: {batt[0]} mV → {batt[-1]} mV\n')

    print(f"\n[输出] CSV/报告/图表已保存至: {OUT_DIR}")


if __name__ == '__main__':
    main()
