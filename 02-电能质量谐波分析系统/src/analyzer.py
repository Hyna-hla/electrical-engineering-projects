# -*- coding: utf-8 -*-
"""
谐波分析核心模块
==================
算法流程 (三级, 模拟真实电能质量监测装置的信号处理链):

  ① 加汉宁窗 FFT + 对数谱抛物线插值  → 精确估计基波频率 f1
     (电网频率偏离 50 Hz 时谱线不对准频点, 直接取峰会引入误差)
  ② 软件准同步重采样                → 按 f1 对信号重采样,
     保证整周期采样 (每周波 128 点 × 8 个周波)
  ③ 整周期 FFT                      → 谱线精确落在各次谐波频点上,
     幅值/相位无需再修正

THD 与谐波含有率定义 (GB/T 14549-1993):
    THD_u = √(Σ_{h=2}^{50} U_h²) / U_1 × 100%
    HRU_h = U_h / U_1 × 100%
"""
import numpy as np
from scipy.interpolate import CubicSpline

# 电压总谐波畸变率限值 (GB/T 14549-1993, 按电网标称电压 kV 分级)
THD_LIMITS = {0.38: 5.0, 10: 4.0, 35: 3.0, 110: 2.0}
# 谐波电压含有率限值: 奇次 / 偶次分开规定 (标准典型值)
HRU_LIMITS_ODD = {0.38: 4.0, 10: 3.2, 35: 2.4, 110: 1.6}
HRU_LIMITS_EVEN = {0.38: 2.0, 10: 1.6, 35: 1.2, 110: 0.8}


def estimate_freq(x, fs, f_guess=50.0):
    """① 汉宁窗 FFT + 对数谱抛物线插值, 估计实际基波频率"""
    n = len(x)
    win = np.hanning(n)
    amp = np.abs(np.fft.rfft(x * win)) * 2 / win.sum()
    k = max(int(round(f_guess * n / fs)), 1)
    k = k - 1 if amp[k - 1] > amp[k] else k
    # 对数谱三点抛物线插值 (对加窗谱线形状匹配度高)
    la, lm, lr = np.log(amp[k - 1] + 1e-12), np.log(amp[k]), np.log(amp[k + 1] + 1e-12)
    delta = 0.5 * (la - lr) / (la - 2 * lm + lr)
    return (k + delta) * fs / n


def synchronized_spectrum(x, fs, f1, cycles=8, pts_per_cycle=128):
    """
    ② + ③ 准同步重采样后整周期 FFT
    返回: (复数谱, 频率数组); 第 k 个 bin 频率 = k·f1/cycles
    """
    n_res = cycles * pts_per_cycle
    t_old = np.arange(len(x)) / fs
    t_new = np.arange(n_res) / (pts_per_cycle * f1)   # 恰好覆盖 cycles 个周波
    x_res = CubicSpline(t_old, x)(t_new)
    spec = np.fft.rfft(x_res) / n_res
    freqs = np.fft.rfftfreq(n_res, 1 / (pts_per_cycle * f1))
    return spec, freqs


def harmonic_analysis(x, fs, f0_nominal=50.0, max_h=25):
    """谐波全参数分析: 基波频率/幅值、各次谐波幅值、THD"""
    f1 = estimate_freq(x, fs, f0_nominal)
    cycles = 8
    spec, _ = synchronized_spectrum(x, fs, f1, cycles=cycles)
    amp = np.abs(spec) * 2
    u1 = amp[cycles]                        # 基波恰好落在第 cycles 个 bin
    res = {'f1': f1, 'u1': u1, 'harmonics': {}, 'ph1': np.angle(spec[cycles])}
    for h in range(2, max_h + 1):
        if h * cycles >= len(amp):
            break
        res['harmonics'][h] = amp[h * cycles]
    u_h_sq = sum(u ** 2 for u in res['harmonics'].values())
    res['thd'] = np.sqrt(u_h_sq) / u1 * 100.0
    return res


def assess(res, kv=10):
    """
    依据 GB/T 14549-1993 判定 (默认 10 kV 电网)
    谐波含有率限值: 奇次与偶次分开规定
    """
    thd_limit = THD_LIMITS.get(kv, 4.0)
    limits = {h: (HRU_LIMITS_ODD if h % 2 == 1 else HRU_LIMITS_EVEN).get(kv, 3.2)
              for h in res['harmonics']}
    violations = []
    for h, uh in res['harmonics'].items():
        hru = uh / res['u1'] * 100
        if hru > limits[h]:
            violations.append((h, hru, limits[h]))
    ok = res['thd'] <= thd_limit and not violations
    return ('合格' if ok else '超标'), violations, thd_limit, limits
