# -*- coding: utf-8 -*-
"""
信号源仿真模块
================
模拟 10 kV 配电母线电压/电流信号（相当于数采装置 AD 采样前的模拟量）：
- 基波 50 Hz，允许电网频率实际偏差（如 49.8 Hz）
- 含 3/5/7/9/11/13 次特征谐波（模拟整流型负荷）
- 含白噪声与幅值缓变（模拟负荷波动）

真实项目中该模块由电压/电流互感器 + NI/嵌入式 AD 采集替代,
接口保持一致即可无缝对接。
"""
import numpy as np

FS = 6400          # 采样率 (Hz), 50Hz 下每周波 128 点
F0_NOMINAL = 50.0  # 标称基波频率

# 谐波源特征: 次数 -> 电压含有率(相对基波百分比)
HARMONICS = {3: 1.8, 5: 3.6, 7: 2.2, 9: 0.6, 11: 1.4, 13: 0.8}


def make_waveform(t, f0=49.8, v_amp=8165.0, load_factor=1.0,
                  harmonics=None, noise=0.003, seed=0):
    """
    生成一段母线电压波形 (10 kV 系统, 相电压幅值 8165 V ≈ 10kV/√3·√2)

    参数:
        t            : 时间轴 (s)
        f0           : 实际基波频率 (Hz), 模拟电网频率偏差
        v_amp        : 基波幅值 (V)
        load_factor  : 负荷率 [0~1], 谐波幅值随负荷波动
        harmonics    : {次数: 含有率%} 字典
        noise        : 白噪声 (相对基波)
    返回:
        波形数组 (V)
    """
    if harmonics is None:
        harmonics = HARMONICS
    rng = np.random.default_rng(seed)
    v = v_amp * np.sin(2 * np.pi * f0 * t)
    # 谐波电压: 幅值 = 基波 × 含有率 × 负荷影响因子; 相位随机但固定
    for h, pct in harmonics.items():
        ph = rng.uniform(0, 2 * np.pi)
        v += v_amp * (pct / 100.0) * (0.55 + 0.45 * load_factor) \
            * np.sin(2 * np.pi * f0 * h * t + ph)
    v += rng.normal(0, noise * v_amp, len(t))
    return v


def day_load_profile(hour):
    """典型日负荷曲线: 早高峰 9-11 时, 晚高峰 18-21 时"""
    base = 0.45 + 0.25 * np.exp(-((hour - 10) / 2.2) ** 2) \
        + 0.35 * np.exp(-((hour - 19.5) / 2.5) ** 2)
    return float(np.clip(base, 0.1, 1.0))
