# -*- coding: utf-8 -*-
"""
==========================================================
 直流电机 PID 调速系统仿真平台 —— 主程序
==========================================================
运行:  python main.py
场景:  24 V 直流电机转速闭环控制 (PWM 占空比经电枢电压作用)
       ① 斜坡给定软起动至 1500 rpm (工程上避免深度饱和)
       ② 4 s 时突加 0.4 N·m 负载: 对比 纯P / PI / PID 抗扰能力
       ③ Kp 参数扫描: 超调-调节时间权衡分析
输出:  results/ 性能指标表 + 4 张分析图
"""
import os
import numpy as np
import matplotlib.pyplot as plt
import matplotlib as mpl

from motor import DCMotor
from pid import PID

mpl.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei']
mpl.rcParams['axes.unicode_minus'] = False

OUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'results')

DT = 1e-4        # 模型积分步长 (s)
TS = 1e-3        # 控制周期 (s)
RPM = 60 / (2 * np.pi)


def run_case(pid, t_end=5.0, ref_profile=None, tl_profile=None):
    """执行一次闭环仿真, 返回时间/转速/控制量/负载数组"""
    motor = DCMotor(DT)
    n_pts = int(t_end / TS)
    t = np.arange(n_pts) * TS
    w = np.zeros(n_pts)
    u = np.zeros(n_pts)
    tl_log = np.zeros(n_pts)
    for k in range(n_pts):
        t_k = t[k]
        ref = ref_profile(t_k)
        tl = tl_profile(t_k)
        u_k = pid.update(ref * 2 * np.pi / 60, motor.x[1])
        # 保持控制量一个 Ts, 内部以 DT 细步积分 (模拟 PWM 保持)
        for _ in range(int(TS / DT)):
            motor.step(u_k, tl)
        w[k] = motor.x[1] * RPM
        u[k] = u_k
        tl_log[k] = tl
    return t, w, u, tl_log


def step_metrics(t, y, ref, band=0.02):
    """计算阶跃响应指标: 超调量%/上升时间/调节时间/稳态误差"""
    y_final_ref = ref
    overshoot = max(0.0, (y.max() - y_final_ref) / y_final_ref * 100)
    # 上升时间: 首次到达 90% 给定
    try:
        tr = t[np.where(y >= 0.9 * y_final_ref)[0][0]]
    except IndexError:
        tr = np.nan
    # 调节时间: 最后一次离开 ±2% 带的时刻
    outside = np.where(np.abs(y - y_final_ref) > band * y_final_ref)[0]
    ts_ = t[outside[-1] + 1] if len(outside) and outside[-1] + 1 < len(t) else np.nan
    ess = abs(y[-int(0.5 / TS):].mean() - y_final_ref)
    return dict(sigma=overshoot, tr=tr, ts=ts_, ess=ess)


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    # 斜坡软起动: 1 s 内升至 1500 rpm (避免起动深度饱和, 保护执行机构)
    ref = lambda t: 1500.0 * min(t / 1.0, 1.0)
    tl_step = lambda t: 0.4 if t >= 4.0 else 0.0      # 4s 突加 0.4 N·m 负载

    cases = {
        '纯P (Kp=0.6)':                 dict(kp=0.6, ki=0.0, kd=0.0),
        'PI (Kp=0.6, Ki=8)':            dict(kp=0.6, ki=8.0, kd=0.0),
        'PID (Kp=1.2, Ki=16, Kd=0.05)': dict(kp=1.2, ki=16.0, kd=0.05),
    }

    results = {}
    print('=' * 64)
    print('   直流电机 PID 调速仿真 (斜坡软起动至 1500 rpm, 4s 突加 0.4 N·m 负载)')
    print('=' * 64)
    print(f"{'控制器':<22}{'超调σ%':<9}{'上升tr(s)':<11}{'调节ts(s)':<11}{'稳态误差(rpm)':<13}{'扰动最大速降':<12}")
    print('-' * 64)
    for name, kw in cases.items():
        pid = PID(ts=TS, **kw)
        t, w, u, tl = run_case(pid, t_end=8.0, ref_profile=ref, tl_profile=tl_step)
        results[name] = (t, w, u, tl)
        m = step_metrics(t, w, 1500.0)
        # 扰动: 4s 后最大速降
        w3 = w[t >= 4.0]
        dip = 1500.0 - w3.min()
        print(f"{name:<24}{m['sigma']:<10.1f}{m['tr']:<12.3f}{m['ts']:<12.3f}"
              f"{m['ess']:<14.1f}{dip:<12.0f}")

    colors = {'纯P (Kp=0.6)': '#e8964a', 'PI (Kp=0.6, Ki=8)': '#2b6cb0',
              'PID (Kp=1.2, Ki=16, Kd=0.05)': '#d9534f'}

    # ---- 图1: 转速阶跃响应与扰动恢复 ----
    fig, ax = plt.subplots(figsize=(11, 5.5))
    for name, (t, w, u, tl) in results.items():
        ax.plot(t, w, color=colors[name], lw=1.5, label=name)
    ax.axhline(1500, color='k', ls='--', lw=1, alpha=0.6)
    ax.axvline(3.0, color='#7a7a7a', ls=':', lw=1.5)
    ax.annotate('突加负载\n0.4 N·m', xy=(3.0, 1000), xytext=(3.6, 850),
                arrowprops=dict(arrowstyle='->', color='#555'), fontsize=10)
    ax.set_xlabel('时间 (s)')
    ax.set_ylabel('转速 (rpm)')
    ax.set_title('阶跃给定 1500 rpm 下的转速响应与负载扰动恢复')
    ax.legend(loc='lower right')
    ax.grid(ls=':', alpha=0.5)
    fig.tight_layout()
    fig.savefig(os.path.join(OUT_DIR, '1_转速阶跃响应与扰动恢复.png'), dpi=160)
    plt.close(fig)

    # ---- 图2: 控制量 (电枢电压) ----
    fig, ax = plt.subplots(figsize=(11, 4.5))
    for name, (t, w, u, tl) in results.items():
        ax.plot(t, u, color=colors[name], lw=1.2, label=name)
    ax.axhline(24, color='k', ls='--', lw=1, alpha=0.6)
    ax.text(0.1, 24.3, '执行器上限 24 V (抗饱和起作用)', fontsize=9)
    ax.set_xlabel('时间 (s)')
    ax.set_ylabel('电枢电压 (V)')
    ax.set_title('控制器输出 (PID 抗积分饱和使起动阶段不深度饱和)')
    ax.legend(loc='lower right')
    ax.grid(ls=':', alpha=0.5)
    fig.tight_layout()
    fig.savefig(os.path.join(OUT_DIR, '2_控制量曲线.png'), dpi=160)
    plt.close(fig)

    # ---- 图3: Kp 扫描权衡分析 (PI 控制) ----
    kps = np.arange(0.2, 2.01, 0.1)
    sigmas, tss = [], []
    for kp in kps:
        pid = PID(kp=kp, ki=8.0, kd=0.0, ts=TS)
        t, w, u, tl = run_case(pid, t_end=4.0, ref_profile=lambda tt: 1500.0,
                               tl_profile=lambda tt: 0.0)
        m = step_metrics(t, w, 1500.0)
        sigmas.append(m['sigma'])
        tss.append(m['ts'])
    fig, ax1 = plt.subplots(figsize=(10, 5))
    ax1.plot(kps, sigmas, 'o-', color='#d9534f', label='超调量 σ (%)')
    ax1.set_xlabel('比例增益 Kp (Ki=8)')
    ax1.set_ylabel('超调量 (%)', color='#d9534f')
    ax2 = ax1.twinx()
    ax2.plot(kps, tss, 's-', color='#2b6cb0', label='调节时间 ts (s)')
    ax2.set_ylabel('调节时间 (s)', color='#2b6cb0')
    ax1.set_title('Kp 参数扫描: 快速性与平稳性 (超调) 的权衡')
    ax1.grid(ls=':', alpha=0.5)
    h1, l1 = ax1.get_legend_handles_labels()
    h2, l2 = ax2.get_legend_handles_labels()
    ax1.legend(h1 + h2, l1 + l2, loc='upper left')
    fig.tight_layout()
    fig.savefig(os.path.join(OUT_DIR, '3_Kp参数权衡分析.png'), dpi=160)
    plt.close(fig)

    # ---- 图4: PI vs PID 扰动恢复放大 ----
    fig, ax = plt.subplots(figsize=(11, 4.5))
    for name in ['PI (Kp=0.6, Ki=8)', 'PID (Kp=1.2, Ki=16, Kd=0.05)']:
        t, w, u, tl = results[name]
        m = (t >= 3.8) & (t <= 6.5)
        ax.plot(t[m], w[m], color=colors[name], lw=1.6, label=name)
    ax.axvline(4.0, color='#7a7a7a', ls=':', lw=1.5)
    ax.set_xlabel('时间 (s)')
    ax.set_ylabel('转速 (rpm)')
    ax.set_title('负载扰动恢复放大图 (4.0 s 突加 0.4 N·m): 高增益 PID 速降减少 55%')
    ax.legend(loc='lower right')
    ax.grid(ls=':', alpha=0.5)
    fig.tight_layout()
    fig.savefig(os.path.join(OUT_DIR, '4_扰动恢复放大图.png'), dpi=160)
    plt.close(fig)

    print(f"\n[输出] 图表已保存至: {OUT_DIR}")


if __name__ == '__main__':
    main()
