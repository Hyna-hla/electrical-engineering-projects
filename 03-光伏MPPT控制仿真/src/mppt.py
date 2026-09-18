# -*- coding: utf-8 -*-
"""
MPPT 最大功率点跟踪算法模块
=============================
实现三种经典算法, 统一接口:  update(v, i) -> v_ref (下一拍参考电压)

1. 定步长扰动观察法 (P&O)      —— 工程最常用, 结构简单, 但稳态有振荡
2. 变步长扰动观察法 (P&O-VS)   —— 步长随 |ΔP/ΔV| 自适应, 兼顾快响应与低振荡
3. 电导增量法 (INC)            —— 判断 dI/dV 与 −I/V 关系, 理论无振荡

工作原理 (以 Boost 变换器为执行机构): MPPT 输出电压参考 V_ref,
变换器电压环按一阶惯性跟踪 (时间常数 τ 模拟闭环动态)。
"""
import numpy as np


class BaseMPPT:
    def __init__(self, v_init, step=1.0, v_min=10.0, v_max=330.0):
        self.v_ref = v_init
        self.step = step
        self.v_min, self.v_max = v_min, v_max
        self.v_prev, self.i_prev, self.p_prev = v_init, None, None

    def _clip(self, v):
        return float(np.clip(v, self.v_min, self.v_max))

    def update(self, v, i):
        p = v * i
        v_ref_new = self._step(v, i, p)
        self.v_prev, self.i_prev, self.p_prev = v, i, p
        self.v_ref = self._clip(v_ref_new)
        return self.v_ref

    def _step(self, v, i, p):
        raise NotImplementedError


class PnO(BaseMPPT):
    """定步长扰动观察法: ΔP·ΔV > 0 保持方向, 否则反向"""

    def __init__(self, v_init, step=3.0, **kw):
        super().__init__(v_init, step=step, **kw)
        self.direction = 1

    def _step(self, v, i, p):
        if self.p_prev is None:
            return self.v_ref + self.step * self.direction
        if p > self.p_prev:                    # 功率增大 → 方向正确
            pass
        else:                                  # 功率减小 → 反向
            self.direction *= -1
        return self.v_ref + self.step * self.direction


class PnOVariable(BaseMPPT):
    """变步长 P&O: 步长 = k · |ΔP/ΔV|, 限幅于 [step_min, step_max]"""

    def __init__(self, v_init, k=6.0, step_min=0.5, step_max=8.0, **kw):
        super().__init__(v_init, **kw)
        self.k, self.step_min, self.step_max = k, step_min, step_max
        self.direction = 1

    def _step(self, v, i, p):
        if self.p_prev is None:
            return self.v_ref + self.step_min
        dp = p - self.p_prev
        dv = v - self.v_prev or 1e-6
        if dp <= 0:
            self.direction *= -1
        slope = abs(dp / dv)                   # P-V 曲线斜率: MPP 附近小
        step = float(np.clip(self.k * slope, self.step_min, self.step_max))
        return self.v_ref + self.direction * step


class INC(BaseMPPT):
    """电导增量法: dI/dV = −I/V 处即 MPP; 大于则升压至更接近 MPP…"""

    def __init__(self, v_init, step=2.0, **kw):
        super().__init__(v_init, step=step, **kw)

    def _step(self, v, i, p):
        if self.i_prev is None:
            return self.v_ref + self.step
        dv = v - self.v_prev
        di = i - self.i_prev
        if abs(dv) < 1e-6:
            cond = di
        else:
            cond = di / dv + i / v             # dI/dV + I/V = 0 即 MPP
        if cond > 1e-4:
            return self.v_ref + self.step      # 位于 MPP 左侧 → 增大电压
        elif cond < -1e-4:
            return self.v_ref - self.step      # 位于 MPP 右侧 → 减小电压
        return self.v_ref                      # 已在 MPP
