# -*- coding: utf-8 -*-
"""潮流结果可视化模块: 网络接线图 / 电压分布 / 收敛特性 / 网损排行"""
import os
import numpy as np
import matplotlib.pyplot as plt
import matplotlib as mpl

from network_data import BUS_POS

mpl.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei']
mpl.rcParams['axes.unicode_minus'] = False


def plot_all(v, theta, hist, branches, out_dir):
    os.makedirs(out_dir, exist_ok=True)

    # ---------- 图1: 网络接线图 + 支路潮流 ----------
    fig, ax = plt.subplots(figsize=(11, 7.5))
    for br in branches:
        x1, y1 = BUS_POS[br['from']]
        x2, y2 = BUS_POS[br['to']]
        lw = 0.8 + br['loading'] / 90
        ax.plot([x1, x2], [y1, y2], '-', color='#5b7fb9', lw=lw, zorder=1)
        mx, my = (x1 + x2) / 2, (y1 + y2) / 2
        ax.text(mx, my + 0.05, f"{br['p_from']:.0f}",
                fontsize=7, color='#8a5b2b', ha='center')
    # 个别密集区域节点的标注方向微调, 避免与邻线/邻标注拥挤
    label_offset = {6: (0.0, 0.18), 11: (-0.42, -0.16), 12: (-0.05, -0.2),
                    13: (-0.55, -0.05)}
    for bus_id, (x, y) in BUS_POS.items():
        vm = v[bus_id - 1]
        color = plt.cm.RdYlGn(0.5 + (vm - 1.0) * 4)  # 电压越低越红
        ax.scatter([x], [y], s=650, c=[color], edgecolors='k',
                   linewidths=1.4, zorder=3)
        ax.text(x, y - 0.008, str(bus_id), ha='center', va='center',
                fontsize=12, fontweight='bold', zorder=4)
        dx, dy = label_offset.get(bus_id, (0.08, 0.14))
        ax.text(x + dx, y + dy, f"{vm:.3f}∠{np.degrees(theta[bus_id-1]):.1f}°",
                fontsize=8, color='#333',
                bbox=dict(fc='w', ec='none', alpha=0.65, pad=1))
    # 图例
    from matplotlib.lines import Line2D
    from matplotlib.patches import Patch
    legend_elems = [
        Patch(fc=plt.cm.RdYlGn(0.85), ec='k', label='节点颜色 = 电压水平 (红低绿高)'),
        Line2D([0], [0], color='#5b7fb9', lw=3.5, label='线宽 ∝ 支路传输功率'),
        Line2D([0], [0], marker='o', color='w', markerfacecolor='w',
               markeredgecolor='k', markersize=12, label='节点编号'),
    ]
    ax.legend(handles=legend_elems, loc='lower left', fontsize=9, framealpha=0.9)
    ax.set_title('IEEE 14节点系统潮流分布图\n(节点旁标注 U∠δ, 线路旁为有功 MW, 线宽示意传输功率)',
                 fontsize=13)
    ax.set_xlim(-0.35, 3.3)
    ax.set_ylim(-0.15, 3.0)
    ax.axis('off')
    fig.tight_layout()
    fig.savefig(os.path.join(out_dir, '1_网络潮流分布图.png'), dpi=160)
    plt.close(fig)

    # ---------- 图2: 节点电压幅值 ----------
    fig, ax = plt.subplots(figsize=(10, 5))
    ids = list(range(1, len(v) + 1))
    colors = ['#d9534f' if vm < 0.95 or vm > 1.05 else '#5cb85c' for vm in v]
    bars = ax.bar(ids, v, color=colors, edgecolor='k', linewidth=0.6)
    for b, vm in zip(bars, v):
        ax.text(b.get_x() + b.get_width() / 2, vm + 0.004, f'{vm:.3f}',
                ha='center', fontsize=8)
    ax.axhline(0.95, ls='--', color='#d9534f', lw=1)
    ax.axhline(1.05, ls='--', color='#d9534f', lw=1)
    ax.axhspan(0.95, 1.05, color='#5cb85c', alpha=0.07)
    ax.set_xlim(0.5, len(v) + 2.4)            # 右侧留白放置注释文字
    ax.text(len(v) + 0.6, 1.0, '合格区间\n0.95~1.05 pu', fontsize=9,
            color='#3d8b3d', va='center')
    ax.set_xlabel('节点编号')
    ax.set_ylabel('电压幅值 (pu)')
    ax.set_title('潮流计算后节点电压水平 (绿色=合格, 红色=越限)')
    ax.set_xticks(ids)
    ax.set_ylim(min(0.98, v.min() - 0.02), max(v) + 0.02)
    ax.grid(axis='y', ls=':', alpha=0.5)
    fig.tight_layout()
    fig.savefig(os.path.join(out_dir, '2_节点电压分布.png'), dpi=160)
    plt.close(fig)

    # ---------- 图3: 收敛特性 ----------
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.semilogy(range(1, len(hist) + 1), hist, 'o-', color='#2b6cb0',
                lw=2, markersize=8)
    ax.set_xlabel('迭代次数')
    ax.set_ylabel('最大功率不平衡量 |ΔS|max (pu)')
    ax.set_title(f'牛顿-拉夫逊法二次收敛特性 ({len(hist)} 次迭代收敛至 1e-8)')
    ax.grid(ls=':', alpha=0.5)
    for i, h in enumerate(hist):
        ax.annotate(f'{h:.1e}', (i + 1, h), textcoords='offset points',
                    xytext=(8, 4), fontsize=8)
    fig.tight_layout()
    fig.savefig(os.path.join(out_dir, '3_收敛特性曲线.png'), dpi=160)
    plt.close(fig)

    # ---------- 图4: 支路网损排行 ----------
    fig, ax = plt.subplots(figsize=(10, 5.5))
    loss_sorted = sorted(branches, key=lambda b: -b['loss_p'])[:10]
    labels = [f"{b['from']}→{b['to']}" for b in loss_sorted]
    vals = [b['loss_p'] for b in loss_sorted]
    ax.barh(range(len(vals)), vals, color='#e8964a', edgecolor='k', lw=0.5)
    ax.set_yticks(range(len(vals)))
    ax.set_yticklabels(labels)
    for i, vv in enumerate(vals):
        ax.text(vv + max(vals) * 0.01, i, f'{vv:.2f} MW', va='center', fontsize=9)
    ax.invert_yaxis()
    ax.set_xlabel('有功网损 (MW)')
    ax.set_title('全网网损最大的前 10 条支路 —— 降损改造优先级参考')
    ax.grid(axis='x', ls=':', alpha=0.5)
    fig.tight_layout()
    fig.savefig(os.path.join(out_dir, '4_支路网损排行.png'), dpi=160)
    plt.close(fig)
