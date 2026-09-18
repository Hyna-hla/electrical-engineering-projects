# -*- coding: utf-8 -*-
"""
数字 PID 控制器 (位置式)
=========================
    u(k) = Kp·e + Ki·Σe·Ts + Kd·de/dt

工程化处理:
  ① 积分抗饱和 (clamping): 输出受限且误差同号时暂停积分累加, 抑制超调
  ② 微分项一阶低通滤波: 抑制测量噪声被微分放大的尖峰
  ③ 微分先行 (对测量值微分): 避免给定值阶跃时控制量冲击
"""
import numpy as np


class PID:
    def __init__(self, kp, ki, kd, ts, u_min=0.0, u_max=24.0,
                 d_filter=0.1, anti_windup=True):
        self.kp, self.ki, self.kd = kp, ki, kd
        self.ts = ts
        self.u_min, self.u_max = u_min, u_max
        self.alpha = d_filter            # 微分滤波系数 (0~1, 越小滤波越强)
        self.anti_windup = anti_windup
        self.y_prev = None
        self.reset()

    def reset(self):
        self.integral = 0.0
        self.y_prev = None
        self.d_filtered = 0.0

    def update(self, ref, y):
        """ref: 目标转速; y: 实测转速; 返回控制量 (电枢电压 V)"""
        e = ref - y
        # 微分先行: 对测量值微分 (d(e)/dt = −d(y)/dt)
        d_raw = -(y - self.y_prev) / self.ts if self.y_prev is not None else 0.0
        self.y_prev = y
        self.d_filtered += self.alpha * (d_raw - self.d_filtered)   # 低通滤波
        d_term = self.d_filtered if self.kd > 0 else 0.0

        p_term = self.kp * e
        i_candidate = self.integral + self.ki * e * self.ts
        u_unsat = p_term + i_candidate + self.kd * d_term
        u = float(np.clip(u_unsat, self.u_min, self.u_max))

        # 抗积分饱和
        if not self.anti_windup or not (
                (u_unsat > self.u_max and e > 0) or
                (u_unsat < self.u_min and e < 0)):
            self.integral = i_candidate
        return u
