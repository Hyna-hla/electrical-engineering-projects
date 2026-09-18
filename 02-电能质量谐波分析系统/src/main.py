# -*- coding: utf-8 -*-
"""
==========================================================
 电能质量在线监测与谐波分析系统 —— 主程序
==========================================================
运行:  python main.py
场景:  10 kV 配电母线, 背景谐波源为整流型负荷,
       电网频率存在 49.8 Hz 偏差 (考验算法抗泄漏能力)
输出:  results/ 评估报告 + 4 张分析图
"""
import os
import numpy as np
import matplotlib.pyplot as plt
import matplotlib as mpl

from signal_source import FS, make_waveform, day_load_profile
from analyzer import harmonic_analysis, assess

mpl.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei']
mpl.rcParams['axes.unicode_minus'] = False

OUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'results')


def main():
    os.makedirs(OUT_DIR, exist_ok=True)

    # ============ 第 1 部分: 单次采集分析 (10 个周波) ============
    duration = 0.2                       # 10 个工频周波
    t = np.arange(0, duration, 1 / FS)
    x = make_waveform(t, f0=49.8, load_factor=1.0, seed=42)

    res = harmonic_analysis(x, FS)
    verdict, violations, thd_limit, limits = assess(res, kv=10)

    print('=' * 60)
    print('   10 kV 母线电压电能质量分析 (加窗插值 FFT)')
    print('=' * 60)
    print(f"基波频率测量值: {res['f1']:.3f} Hz  (真实 49.800 Hz)")
    print(f"基波电压幅值  : {res['u1']:.1f} V")
    print(f"电压总谐波畸变率 THD: {res['thd']:.2f} %  (限值 {thd_limit} %)")
    print('-' * 60)
    print(f"{'次数':<6}{'实测含有率':<12}{'国标限值':<10}{'判定':<6}")
    for h in sorted(res['harmonics']):
        hru = res['harmonics'][h] / res['u1'] * 100
        if hru < 0.05:
            continue
        flag = '超标' if any(v[0] == h for v in violations) else '合格'
        print(f"{h:<8}{hru:<12.2f}{limits[h]:<10.1f}{flag:<6}")
    print('-' * 60)
    print(f"综合判定: {verdict}")
    if violations:
        print("越限明细: " + ', '.join(f"{h}次({r:.2f}%)" for h, r, _ in violations))

    # ============ 第 2 部分: 24 小时 THD 趋势监测 ============
    hours, thds = [], []
    for hh in np.arange(0, 24, 0.5):
        t2 = np.arange(0, 0.2, 1 / FS) + hh * 3600
        lf = day_load_profile(hh)
        x2 = make_waveform(t2, f0=49.8, load_factor=lf, seed=int(hh * 10) + 1)
        r2 = harmonic_analysis(x2, FS)
        hours.append(hh)
        thds.append(r2['thd'])
    hours, thds = np.array(hours), np.array(thds)

    # ============ 绘图 ============
    # 图1: 时域波形 + 基波分量 (用测量得到的 f1/U1/相位重构基波)
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.plot(t[:448] * 1000, x[:448], lw=0.9, color='#3b6fb6', label='实测波形(含谐波)')
    f1, a1, ph1 = res['f1'], res['u1'], res['ph1']
    ax.plot(t[:448] * 1000, a1 * np.sin(2 * np.pi * f1 * t[:448] + ph1),
            lw=1.4, color='#d9544f', ls='--', label='提取的基波分量')
    ax.set_xlabel('时间 (ms)')
    ax.set_ylabel('电压 (V)')
    ax.set_title('10 kV 母线电压波形与基波提取 (基波 49.8 Hz, 含 3~13 次谐波)')
    ax.legend()
    ax.grid(ls=':', alpha=0.5)
    fig.tight_layout()
    fig.savefig(os.path.join(OUT_DIR, '1_时域波形与基波提取.png'), dpi=160)
    plt.close(fig)

    # 图2: 谐波频谱 vs 国标限值 (奇次/偶次限值分开)
    fig, ax = plt.subplots(figsize=(10, 5))
    hs = sorted(h for h in res['harmonics'] if h <= 13)
    hrus = [res['harmonics'][h] / res['u1'] * 100 for h in hs]
    colors = ['#d9534f' if res['harmonics'][h] / res['u1'] * 100 > limits[h] else '#5cb85c'
              for h in hs]
    bars = ax.bar([str(h) for h in hs], hrus, color=colors, edgecolor='k', lw=0.5)
    for b, v in zip(bars, hrus):
        ax.text(b.get_x() + b.get_width() / 2, v + 0.05, f'{v:.2f}', ha='center', fontsize=9)
    ax.axhline(limits[3], ls='--', color='#d9534f', lw=1.5,
               label=f'GB/T 14549 奇次限值 {limits[3]}%')
    ax.axhline(limits[2], ls=':', color='#8a5b2b', lw=1.5,
               label=f'GB/T 14549 偶次限值 {limits[2]}%')
    ax.text(0.02, 0.965, '注: 奇次/偶次谐波按各自限值分别判定',
            transform=ax.transAxes, fontsize=8.5, color='#666')
    ax.set_xlabel('谐波次数')
    ax.set_ylabel('谐波电压含有率 HRU (%)')
    ax.set_title(f'谐波频谱分析 (THD = {res["thd"]:.2f}%, 限值 {thd_limit}%) —— 红色为越限谐波')
    ax.legend()
    ax.grid(axis='y', ls=':', alpha=0.5)
    fig.tight_layout()
    fig.savefig(os.path.join(OUT_DIR, '2_谐波频谱与国标限值.png'), dpi=160)
    plt.close(fig)

    # 图3: 24 小时 THD 趋势
    fig, ax = plt.subplots(figsize=(11, 5))
    over = thds > thd_limit
    ax.plot(hours, thds, '-', color='#3b6fb6', lw=1.5, label='THD 实测趋势')
    ax.fill_between(hours, thds, thd_limit, where=over, color='#d9534f', alpha=0.35,
                    label='超标时段')
    ax.axhline(thd_limit, ls='--', color='#d9534f', lw=1.5, label=f'国标限值 {thd_limit}%')
    ax.axhline(thd_limit * 0.8, ls=':', color='#e8964a', lw=1.2, label='预警线 (限值80%)')
    ax.set_xlabel('时刻 (h)')
    ax.set_ylabel('电压总谐波畸变率 THD (%)')
    ax.set_title('24 小时电压 THD 在线监测趋势 (谐波随日负荷波动, 晚高峰超标)')
    ax.set_xticks(range(0, 25, 2))
    ax.legend(loc='upper left', fontsize=9)
    ax.grid(ls=':', alpha=0.5)
    fig.tight_layout()
    fig.savefig(os.path.join(OUT_DIR, '3_24小时THD监测趋势.png'), dpi=160)
    plt.close(fig)

    # 图4: 日负荷曲线与 THD 对比 (相关性)
    loads = [day_load_profile(h) for h in hours]
    fig, ax1 = plt.subplots(figsize=(11, 5))
    ax1.plot(hours, loads, '-', color='#e8964a', lw=2, label='日负荷率')
    ax1.set_xlabel('时刻 (h)')
    ax1.set_ylabel('负荷率', color='#c06a1a')
    ax2 = ax1.twinx()
    ax2.plot(hours, thds, '-', color='#3b6fb6', lw=1.2, label='THD')
    ax2.set_ylabel('THD (%)', color='#3b6fb6')
    corr = np.corrcoef(loads, thds)[0, 1]
    ax1.set_title(f'日负荷曲线与 THD 相关性分析 (相关系数 r = {corr:.3f})')
    h1, l1 = ax1.get_legend_handles_labels()
    h2, l2 = ax2.get_legend_handles_labels()
    ax1.legend(h1 + h2, l1 + l2, loc='upper left', fontsize=9)
    ax1.grid(ls=':', alpha=0.5)
    fig.tight_layout()
    fig.savefig(os.path.join(OUT_DIR, '4_负荷与THD相关性.png'), dpi=160)
    plt.close(fig)

    # ============ 报告 ============
    with open(os.path.join(OUT_DIR, '电能质量评估报告.txt'), 'w', encoding='utf-8') as f:
        f.write('10 kV 母线电能质量评估报告 (依据 GB/T 14549-1993)\n')
        f.write('=' * 56 + '\n')
        f.write(f"基波频率: {res['f1']:.3f} Hz | 基波幅值: {res['u1']:.1f} V\n")
        f.write(f"电压 THD: {res['thd']:.2f} % (限值 {thd_limit} %)\n")
        f.write('各次谐波含有率:\n')
        for h in sorted(res['harmonics']):
            hru = res['harmonics'][h] / res['u1'] * 100
            if hru >= 0.05:
                f.write(f"  {h:>2} 次: {hru:.2f} %\n")
        f.write(f"\n越限小时数: {over.sum() * 0.5:.1f} h / 24 h\n")
        f.write(f"综合判定: {verdict}\n")
        f.write("治理建议: 晚高峰投运 SVG/APF 有源滤波装置, 优先滤除 5、7 次谐波\n")

    print(f"\n[输出] 报告与分析图已保存至: {OUT_DIR}")


if __name__ == '__main__':
    main()
