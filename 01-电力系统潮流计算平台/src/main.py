# -*- coding: utf-8 -*-
"""
==========================================================
 电力系统潮流计算与可视化分析平台 —— 主程序
==========================================================
运行:  python main.py
输出:  results/ 下的文本报告 + 4 张分析图
"""
import os
import time
import numpy as np

from network_data import BUS_DATA, BRANCH_DATA, SHUNT_DATA, BASE_MVA
from solver import newton_raphson, branch_power_flow
from visualize import plot_all

OUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'results')


def main():
    print('=' * 62)
    print('       IEEE 14 节点系统 牛顿-拉夫逊法潮流计算')
    print(f'       系统基准容量: {BASE_MVA:.0f} MVA')
    print('=' * 62)

    t0 = time.perf_counter()
    v, theta, hist, info = newton_raphson(BUS_DATA, BRANCH_DATA, SHUNT_DATA)
    t1 = time.perf_counter()
    branches, total_loss = branch_power_flow(v, theta, BRANCH_DATA, BASE_MVA)

    # ---------- 控制台输出 ----------
    print(f"\n[求解状态] {'收敛' if info['converged'] else '未收敛'}"
          f" | 迭代次数: {info['iterations']} | 耗时: {(t1 - t0) * 1000:.1f} ms")
    print('-' * 62)
    print(f"{'节点':<4}{'类型':<7}{'U (pu)':<9}{'δ (°)':<9}"
          f"{'P注入 (MW)':<12}{'Q注入 (Mvar)':<12}")
    print('-' * 62)
    for i, row in enumerate(BUS_DATA):
        print(f"{row[0]:<6}{row[1]:<7}{v[i]:<9.4f}{np.degrees(theta[i]):<9.3f}"
              f"{info['p_calc'][i] * BASE_MVA:<12.2f}{info['q_calc'][i] * BASE_MVA:<12.2f}")

    load_p = sum(r[2] for r in BUS_DATA) * BASE_MVA
    gen_p = (info['p_calc'][0] + sum(r[4] for r in BUS_DATA)) * BASE_MVA
    print('-' * 62)
    print(f"总负荷: {load_p:.2f} MW | 总发电: {gen_p:.2f} MW | 系统网损: {total_loss:.2f} MW"
          f" ({total_loss / gen_p * 100:.2f}%)")

    # ---------- 生成文本报告 ----------
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(os.path.join(OUT_DIR, '潮流计算报告.txt'), 'w', encoding='utf-8') as f:
        f.write('IEEE 14 节点系统潮流计算报告\n')
        f.write(f'(牛顿-拉夫逊法, 收敛精度 1e-8, 迭代 {info["iterations"]} 次)\n')
        f.write('=' * 70 + '\n\n[节点结果]\n')
        f.write(f"{'节点':<4}{'类型':<7}{'U (pu)':<10}{'δ (°)':<10}{'P (MW)':<10}{'Q (Mvar)':<10}\n")
        for i, row in enumerate(BUS_DATA):
            f.write(f"{row[0]:<6}{row[1]:<7}{v[i]:<10.4f}{np.degrees(theta[i]):<10.3f}"
                    f"{info['p_calc'][i] * BASE_MVA:<10.2f}{info['q_calc'][i] * BASE_MVA:<10.2f}\n")
        f.write('\n[支路潮流 (MW/Mvar)]\n')
        f.write(f"{'支路':<8}{'首端P':<9}{'首端Q':<9}{'末端P':<9}{'末端Q':<9}{'网损':<8}\n")
        for b in branches:
            f.write(f"{b['from']}→{b['to']:<5}{b['p_from']:<9.2f}{b['q_from']:<9.2f}"
                    f"{b['p_to']:<9.2f}{b['q_to']:<9.2f}{b['loss_p']:<8.3f}\n")
        f.write(f"\n总网损: {total_loss:.3f} MW\n")

    # ---------- 绘图 ----------
    plot_all(v, theta, hist, branches, OUT_DIR)
    print(f"\n[输出] 分析图与报告已保存至: {OUT_DIR}")


if __name__ == '__main__':
    main()
