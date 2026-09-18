# -*- coding: utf-8 -*-
"""
牛顿-拉夫逊法潮流计算核心模块
==============================
极坐标形式, 数学模型:

    节点功率方程:
        ΔP_i = P_is - Vi·Σ(Vj·(Gij·cosθij + Bij·sinθij))
        ΔQ_i = Qis - Vi·Σ(Vj·(Gij·sinθij - Bij·cosθij))

    雅可比矩阵由 H, N, J, L 四个子块构成, 每次迭代重新形成并求解
    修正方程:  [ΔP; ΔQ] = [H N; J L]·[Δθ; ΔV/V]

收敛判据: 全部节点功率不平衡量最大值 |ΔS|max < eps (默认 1e-8)
"""
import numpy as np


def build_ybus(bus_data, branch_data, shunt_data):
    """形成节点导纳矩阵 Y = G + jB (含变压器非标准变比与并联电容)"""
    n = len(bus_data)
    ybus = np.zeros((n, n), dtype=complex)
    for i, j, r, x, bc, k in branch_data:
        # 支路阻抗 -> 导纳
        y_series = 1.0 / complex(r, x)
        i_idx, j_idx = i - 1, j - 1
        # 非标准变比变压器采用 π 型等值电路
        b_half = bc / 2.0  # bc 为全线充电容纳, π 型等值每端 B/2
        ybus[i_idx, i_idx] += y_series / (k * k) + 1j * b_half
        ybus[j_idx, j_idx] += y_series + 1j * b_half
        ybus[i_idx, j_idx] -= y_series / k
        ybus[j_idx, i_idx] -= y_series / k
    for bus, b in shunt_data.items():  # 并联电容
        ybus[bus - 1, bus - 1] += 1j * b
    return ybus


def calc_power(v, theta, g, b):
    """计算各节点注入功率 P(i), Q(i)"""
    n = len(v)
    p = np.zeros(n)
    q = np.zeros(n)
    for i in range(n):
        for j in range(n):
            ang = theta[i] - theta[j]
            p[i] += v[i] * v[j] * (g[i, j] * np.cos(ang) + b[i, j] * np.sin(ang))
            q[i] += v[i] * v[j] * (g[i, j] * np.sin(ang) - b[i, j] * np.cos(ang))
    return p, q


def build_jacobian(v, theta, p, q, g, b, theta_idx, vmag_idx):
    """
    形成雅可比矩阵 J = ∂[P_calc; Q_calc] / ∂[θ; V]  (四个子块 H N / J L)
    修正方程:  J · Δx = [P_sp − P_calc; Q_sp − Q_calc]
    """
    n_theta, n_v = len(theta_idx), len(vmag_idx)
    jac = np.zeros((n_theta + n_v, n_theta + n_v))
    for a, i in enumerate(theta_idx):
        for bidx, j in enumerate(theta_idx):
            ang = theta[i] - theta[j]
            if i != j:
                jac[a, bidx] = v[i] * v[j] * (g[i, j] * np.sin(ang)
                                               - b[i, j] * np.cos(ang))
            else:
                jac[a, bidx] = -q[i] - b[i, i] * v[i] ** 2
        for c, j in enumerate(vmag_idx):
            ang = theta[i] - theta[j]
            if i != j:
                jac[a, n_theta + c] = v[i] * (g[i, j] * np.cos(ang)
                                              + b[i, j] * np.sin(ang))
            else:
                jac[a, n_theta + c] = p[i] / v[i] + g[i, i] * v[i]
    for a, i in enumerate(vmag_idx):
        for bidx, j in enumerate(theta_idx):
            ang = theta[i] - theta[j]
            if i != j:
                jac[n_theta + a, bidx] = -v[i] * v[j] * (g[i, j] * np.cos(ang)
                                                         + b[i, j] * np.sin(ang))
            else:
                jac[n_theta + a, bidx] = p[i] - g[i, i] * v[i] ** 2
        for c, j in enumerate(vmag_idx):
            ang = theta[i] - theta[j]
            if i != j:
                jac[n_theta + a, n_theta + c] = v[i] * (g[i, j] * np.sin(ang)
                                                        - b[i, j] * np.cos(ang))
            else:
                jac[n_theta + a, n_theta + c] = q[i] / v[i] - b[i, i] * v[i]
    return jac


def newton_raphson(bus_data, branch_data, shunt_data, eps=1e-8, max_iter=30):
    """
    牛顿-拉夫逊法潮流求解主函数

    返回:
        v, theta : 节点电压幅值/相角
        hist     : 每次迭代的最大功率不平衡量 (用于收敛特性分析)
        info     : 求解统计信息 dict
    """
    n = len(bus_data)
    ybus = build_ybus(bus_data, branch_data, shunt_data)
    g, b = ybus.real, ybus.imag

    types = [row[1] for row in bus_data]
    pq = [i for i in range(n) if types[i] == 'PQ']
    pv = [i for i in range(n) if types[i] == 'PV']
    # 待求状态量: 平衡节点以外的相角 + PQ 节点电压幅值
    theta_idx = [i for i in range(n) if types[i] != 'slack']
    vmag_idx = pq

    # 节点给定注入功率 Psp = Pg - Pd, Qsp = Qg(-0) - Qd
    p_sp = np.array([row[4] - row[2] for row in bus_data])
    q_sp = np.array([-row[3] for row in bus_data])

    # 初值: 平启动 (V=1.0, θ=0), PV/平衡节点取给定电压
    v = np.array([row[6] if row[1] != 'PQ' else 1.0 for row in bus_data])
    theta = np.zeros(n)

    hist = []
    converged = False
    for it in range(1, max_iter + 1):
        p, q = calc_power(v, theta, g, b)
        # 功率不平衡量向量
        dp = p_sp[theta_idx] - p[theta_idx]
        dq = q_sp[vmag_idx] - q[vmag_idx]
        mism = np.concatenate([dp, dq])
        max_mism = np.max(np.abs(mism))
        hist.append(max_mism)
        if max_mism < eps:
            converged = True
            break

        # ---- 形成雅可比矩阵并求解修正方程 ----
        jac = build_jacobian(v, theta, p, q, g, b, theta_idx, vmag_idx)
        dx = np.linalg.solve(jac, mism)
        theta[theta_idx] += dx[:len(theta_idx)]
        v[vmag_idx] += dx[len(theta_idx):]

    p_final, q_final = calc_power(v, theta, g, b)
    info = {
        'iterations': len(hist),
        'converged': converged,
        'ybus': ybus,
        'p_calc': p_final,
        'q_calc': q_final,
        'p_sp': p_sp,
        'q_sp': q_sp,
        'pq': pq,
        'pv': pv,
    }
    return v, theta, hist, info


def branch_power_flow(v, theta, branch_data, base_mva):
    """计算各支路首末端潮流功率与网损 (返回 pu)"""
    results = []
    total_loss = 0.0
    for i, j, r, x, bc, k in branch_data:
        vi, vj = v[i - 1], v[j - 1]
        ang = theta[i - 1] - theta[j - 1]
        y_series = 1.0 / complex(r, x)
        # 首端注入 π 型等值电路的功率
        s_from = (vi ** 2 / (k * k)) * np.conj(y_series) + 1j * bc * vi ** 2 \
            - (vi * vj / k) * np.conj(y_series) * np.exp(1j * ang)
        s_to = (vj ** 2) * np.conj(y_series) + 1j * bc * vj ** 2 \
            - (vi * vj / k) * np.conj(y_series) * np.exp(-1j * ang)
        loss = s_from + s_to
        total_loss += loss.real
        results.append({
            'from': i, 'to': j,
            'p_from': s_from.real * base_mva, 'q_from': s_from.imag * base_mva,
            'p_to': s_to.real * base_mva, 'q_to': s_to.imag * base_mva,
            'loss_p': loss.real * base_mva,
            'loading': abs(s_from) * base_mva,
        })
    return results, total_loss * base_mva
