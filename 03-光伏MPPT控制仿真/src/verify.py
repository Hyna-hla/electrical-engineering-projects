# -*- coding: utf-8 -*-
"""
==========================================================
 光伏模型自验证脚本
==========================================================
运行:  python verify.py
校验项:
  ① STC 工况 (1000 W/m², 25 °C) 关键参数与典型 200 W 组件手册一致
  ② 物理规律: 光照↓→功率近似同比下降; 温度↑→Vmp/功率下降 (与负温度系数一致)
  ③ I-V 曲线单调性与短路/开路点边界条件
"""
import numpy as np

from pv_model import PVArray


def main():
    pv = PVArray()
    print('=' * 56)
    print('  光伏单二极管模型自验证')
    print('=' * 56)

    # ① STC 参数
    vmp, pmp = pv.find_mpp(1000, 25)
    imp = float(pv.i_pv(vmp, 1000, 25))
    isc = float(pv.i_pv(0.01, 1000, 25))
    assert abs(vmp - 263) / 263 < 0.02, f'Vmp 偏离: {vmp:.1f}'
    assert abs(imp - 7.6) / 7.6 < 0.03, f'Imp 偏离: {imp:.2f}'
    assert abs(pmp - 2000) / 2000 < 0.02, f'Pmp 偏离: {pmp:.0f}'
    assert abs(isc - 8.21) / 8.21 < 0.01, f'Isc 偏离: {isc:.2f}'
    print(f'[通过] ① STC: Vmp={vmp:.1f} V, Imp={imp:.2f} A, Pmp={pmp:.0f} W, '
          f'Isc={isc:.2f} A (对标手册 263/7.6/2000/8.21)')

    # ② 温度/光照响应
    _, p_600 = pv.find_mpp(600, 25)
    _, p_1000_t55 = pv.find_mpp(1000, 55)
    vmp_t55, _ = pv.find_mpp(1000, 55)
    assert abs(p_600 / pmp - 0.6) < 0.03, '光照-功率线性度异常'
    assert p_1000_t55 < pmp * 0.93, '高温降功率不符合负温度系数'
    assert vmp_t55 < vmp * 0.92, 'Vmp 未随温度下降'
    print(f'[通过] ② 600 W/m² 功率比 {p_600 / pmp:.3f} (≈0.6); '
          f'55 °C 功率 {p_1000_t55 / pmp * 100:.1f}% (降低 {100 - p_1000_t55 / pmp * 100:.1f}%), '
          f'Vmp 降幅 {(1 - vmp_t55 / vmp) * 100:.1f}%')

    # ③ I-V 曲线性质
    vs = np.linspace(0.01, pv.voc - 0.01, 300)
    ivs = pv.i_pv(vs, 800, 35)
    assert np.all(np.diff(ivs) <= 1e-6), 'I-V 曲线非单调'
    assert float(pv.i_pv(pv.voc + 1, 800, 35)) == 0.0, '超过 Voc 电流不为 0'
    print(f'[通过] ③ I-V 单调递减, Voc 处电流归零')
    print('-' * 56)
    print('全部校验通过 ✓')


if __name__ == '__main__':
    main()
