# -*- coding: utf-8 -*-
"""
他励直流电机数学模型
=====================
状态方程 (以电枢电流 i 与角速度 ω 为状态):

    di/dt = (u − Ra·i − Ke·ω) / La
    dω/dt = (Kt·i − B·ω − TL) / J

参数为典型 200W/24V 直流有刷电机:
    额定电压 24 V, 额定转速 ~2200 rpm, 额定转矩 ~0.6 N·m
"""
import numpy as np

# 电机参数
RA = 0.5      # 电枢电阻 (Ω)
LA = 0.01     # 电枢电感 (H)
KE = 0.1      # 反电动势系数 (V·s/rad)
KT = 0.1      # 转矩系数 (N·m/A)
J = 0.01      # 转动惯量 (kg·m²)
B = 0.0002    # 粘性摩擦系数 (N·m·s/rad)


def deriv(x, u, tl):
    """连续状态方程右端"""
    i, w = x
    di = (u - RA * i - KE * w) / LA
    dw = (KT * i - B * w - tl) / J
    return np.array([di, dw])


class DCMotor:
    def __init__(self, dt=1e-4):
        self.dt = dt
        self.x = np.array([0.0, 0.0])   # [i, ω]

    def reset(self):
        self.x = np.array([0.0, 0.0])

    def step(self, u, tl=0.0):
        """RK4 单步积分, 返回 (i, ω)"""
        dt = self.dt
        k1 = deriv(self.x, u, tl)
        k2 = deriv(self.x + dt / 2 * k1, u, tl)
        k3 = deriv(self.x + dt / 2 * k2, u, tl)
        k4 = deriv(self.x + dt * k3, u, tl)
        self.x = self.x + dt / 6 * (k1 + 2 * k2 + 2 * k3 + k4)
        return self.x[0], self.x[1]
