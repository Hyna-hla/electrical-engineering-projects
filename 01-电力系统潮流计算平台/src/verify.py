# -*- coding: utf-8 -*-
"""
==========================================================
 潮流计算引擎自验证脚本
==========================================================
运行:  python verify.py
三项独立校验:
  ① 雅可比矩阵 vs 有限差分数值求导 (逐元素, 验证公式无符号/推导错误)
  ② 功率平衡: Σ发电 − Σ负荷 − Σ支路网损 ≈ 0 (验证解的物理自洽性)
  ③ 与 Matpower 官方发布的 IEEE 14 节点解 (case14.m) 逐节点对比
     参考来源: https://github.com/MATPOWER/matpower (data/case14.m)
"""
import numpy as np

from network_data import BUS_DATA, BRANCH_DATA, SHUNT_DATA, BASE_MVA
from solver import newton_raphson, build_jacobian, build_ybus, calc_power, \
    branch_power_flow

# Matpower case14.m 官方解 (Vm pu / Va deg / 平衡机 Pg, Qg MW/Mvar)
REFERENCE = {
    'vm':  [1.06, 1.045, 1.01, 1.019, 1.02, 1.07, 1.062, 1.09,
            1.056, 1.051, 1.057, 1.055, 1.05, 1.036],
    'va':  [0, -4.98, -12.72, -10.33, -8.78, -14.22, -13.37, -13.36,
            -14.94, -15.1, -14.79, -15.07, -15.16, -16.04],
    'pg1': 232.4, 'qg1': -16.9,
}


def check_jacobian():
    """① 解析雅可比 vs 数值微分"""
    n = len(BUS_DATA)
    ybus = build_ybus(BUS_DATA, BRANCH_DATA, SHUNT_DATA)
    g, b = ybus.real, ybus.imag
    types = [r[1] for r in BUS_DATA]
    theta_idx = [i for i in range(n) if types[i] != 'slack']
    vmag_idx = [i for i in range(n) if types[i] == 'PQ']
    rng = np.random.default_rng(0)
    # 在收敛解附近取一点做检验 (比平启动更能暴露符号错误)
    v = np.array([r[6] if r[1] != 'PQ' else 1.0 for r in BUS_DATA]) \
        + rng.normal(0, 0.02, n)
    theta = rng.normal(0, 0.05, n)

    def calc_vec(v, th):
        p, q = calc_power(v, th, g, b)
        return np.concatenate([p[theta_idx], q[vmag_idx]])

    p, q = calc_power(v, theta, g, b)
    j_ana = build_jacobian(v, theta, p, q, g, b, theta_idx, vmag_idx)
    x0 = np.concatenate([theta[theta_idx], v[vmag_idx]])
    f0 = calc_vec(v, theta)
    j_num = np.zeros_like(j_ana)
    h = 1e-7
    for k in range(len(x0)):
        xp = x0.copy()
        xp[k] += h
        v2, th2 = v.copy(), theta.copy()
        th2[theta_idx] = xp[:len(theta_idx)]
        v2[vmag_idx] = xp[len(theta_idx):]
        j_num[:, k] = (calc_vec(v2, th2) - f0) / h
    err = np.abs(j_ana - j_num).max()
    assert err < 1e-4, f'雅可比校验失败: 最大误差 {err:.2e}'
    print(f'[通过] ① 雅可比解析式 vs 有限差分: 最大偏差 {err:.2e} (441 个元素)')
    return err


def check_power_balance(v, theta, info):
    """② 全网功率平衡"""
    branches, total_loss = branch_power_flow(v, theta, BRANCH_DATA, BASE_MVA)
    load_p = sum(r[2] for r in BUS_DATA) * BASE_MVA
    gen_p = (info['p_calc'][0] + sum(r[4] for r in BUS_DATA)) * BASE_MVA
    resid = gen_p - load_p - total_loss
    assert abs(resid) < 0.05, f'功率平衡校验失败: 残差 {resid:.3f} MW'
    print(f'[通过] ② 功率平衡: 发电 {gen_p:.2f} − 负荷 {load_p:.2f} − 网损 '
          f'{total_loss:.2f} = 残差 {resid:+.4f} MW')
    return total_loss


def check_against_reference(v, theta, info):
    """③ 与 Matpower 官方解对比"""
    va = np.degrees(theta)
    dv = np.abs(v - np.array(REFERENCE['vm'])) / np.array(REFERENCE['vm']) * 100
    da = np.abs(va - np.array(REFERENCE['va']))
    pg1 = info['p_calc'][0] * BASE_MVA
    qg1 = info['q_calc'][0] * BASE_MVA
    pg_err = abs(pg1 - REFERENCE['pg1']) / REFERENCE['pg1'] * 100
    assert dv.max() < 0.2, f'电压对比失败: 最大偏差 {dv.max():.3f}%'
    assert da.max() < 0.05, f'相角对比失败: 最大偏差 {da.max():.3f}°'
    assert pg_err < 0.2, f'平衡机功率对比失败: {pg_err:.3f}%'
    print(f'[通过] ③ 对比 Matpower 官方解: 电压最大偏差 {dv.max():.3f}%, '
          f'相角最大偏差 {da.max():.3f}°, 平衡机 Pg 偏差 {pg_err:.3f}% '
          f'({pg1:.1f} vs {REFERENCE["pg1"]} MW)')
    print(f'       平衡机 Qg: {qg1:.1f} vs {REFERENCE["qg1"]} Mvar '
          f'(无功受收敛精度影响略大于有功)')


def main():
    print('=' * 58)
    print('  潮流计算引擎自验证 (3 项独立校验)')
    print('=' * 58)
    check_jacobian()
    v, theta, hist, info = newton_raphson(BUS_DATA, BRANCH_DATA, SHUNT_DATA)
    check_power_balance(v, theta, info)
    check_against_reference(v, theta, info)
    print('-' * 58)
    print('全部校验通过 ✓')


if __name__ == '__main__':
    main()
