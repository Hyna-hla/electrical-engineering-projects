# -*- coding: utf-8 -*-
"""
光伏阵列单二极管模型
======================
电池方程:
    I = Iph − I0·[exp((V + I·Rs)/a) − 1] − (V + I·Rs)/Rsh
    a = n·Ns·k·T/q   (二极管热电压常数)

光照/温度修正:
    Iph = (Isc + Ki·(T − 25)) · G/1000
    I0  随温度按硅带隙指数修正

参数以典型 200 W 多晶硅组件为基准 (STC: 1000 W/m², 25 °C):
    Isc = 8.21 A, Voc = 32.9 V, Vmp ≈ 26.3 V, Imp ≈ 7.6 A
10 块组件串联构成约 2 kW 光伏组串。
"""
import numpy as np

K_BOLTZ = 1.380649e-23   # 玻尔兹曼常数 (J/K)
Q_E = 1.602176634e-19    # 电子电荷 (C)
T_REF = 298.15           # 参考温度 25 °C (K)
G_REF = 1000.0           # 参考光照 (W/m²)
EG_SILICON = 1.12        # 硅带隙 (eV), 用于 I0 温度修正


class PVArray:
    """光伏组串: n_series 块组件串联, 每块 n_cells 片电池"""

    def __init__(self, n_series=10, n_cells=54, isc=8.21, voc=32.9,
                 rs=0.221, rsh=415.0, n_diode=1.3, ki=0.0032):
        self.n_modules = n_series
        self.n_cells_total = n_series * n_cells
        # 串联: 电压/串联电阻相加, 电流/并联电阻不变
        self.isc = isc                   # 组串短路电流 (A), 串联不变
        self.voc = voc * n_series        # 组串开路电压 (V)
        self.rs = rs * n_series          # 组串串联电阻 (Ω)
        self.rsh = rsh * n_series        # 组串并联电阻 (Ω)
        self.n_diode = n_diode
        self.ki = ki                     # Isc 温度系数 (A/°C)

    def _diode_a(self, temp_k):
        return self.n_diode * self.n_cells_total * K_BOLTZ * temp_k / Q_E

    def _i0(self, temp_k):
        """二极管反向饱和电流 (温度修正: 硅带隙指数项)"""
        a_ref = self._diode_a(T_REF)
        i0_ref = self.isc / (np.exp(self.voc / a_ref) - 1)
        return i0_ref * (temp_k / T_REF) ** 3 * np.exp(
            Q_E * EG_SILICON / (self.n_diode * K_BOLTZ) * (1 / T_REF - 1 / temp_k))

    def i_pv(self, v, g=1000.0, temp=25.0):
        """牛顿迭代求解给定电压下的电流 I(V)"""
        temp_k = temp + 273.15
        a = self._diode_a(temp_k)
        iph = (self.isc + self.ki * (temp - 25)) * g / G_REF   # 光生电流(A)
        i0 = self._i0(temp_k)
        v = np.asarray(v, dtype=float)
        i = np.full_like(v, iph)                     # 电流初值 = 光生电流
        for _ in range(80):
            vd = v + i * self.rs
            f = iph - i0 * (np.exp(np.clip(vd / a, 0, 700)) - 1) - vd / self.rsh - i
            dfdi = -i0 * np.exp(np.clip(vd / a, 0, 700)) * self.rs / a \
                - self.rs / self.rsh - 1
            di = f / dfdi
            i = i - di
            if np.max(np.abs(di)) < 1e-10:
                break
        return np.maximum(i, 0.0)

    def p_pv(self, v, g=1000.0, temp=25.0):
        return v * self.i_pv(v, g, temp)

    def find_mpp(self, g, temp):
        """扫描法求当前工况下最大功率点 (理论最大值, 用于追踪效率计算)"""
        vs = np.linspace(0.1, self.voc * 1.02, 1200)
        ps = self.p_pv(vs, g, temp)
        k = int(np.argmax(ps))
        return vs[k], ps[k]
