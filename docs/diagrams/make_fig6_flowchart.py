# -*- coding: utf-8 -*-
"""
生成「核销流程图」——标准流程图符号（圆角矩形起止、矩形处理、菱形判断、箭头控制流）。

流程严格对应实现：
  AuthInterceptor + @RequireRole(CHECKER)  → Token 与角色校验
  CheckinServiceImpl#verify              → 动态码校验、票券查询、状态与时间窗校验、
                                            条件更新（status 0→1）、写核销记录

用法：python docs/diagrams/make_fig6_flowchart.py
输出：docs/diagrams/fig06_checkin_flow_standard.png
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from flowchart_lib import Flowchart  # noqa: E402

OUT = os.path.join(HERE, "fig06_checkin_flow_standard.png")

MAIN = [
    ("terminal", ["开始：核销员扫码提交动态码"], "n"),
    ("decision", ["动态码校验是否通过？", "（SHA-256 签名 + 3 秒时效）"], "d"),
    ("decision", ["Token 与核销员角色校验", "是否通过？"], "d"),
    ("process", ["按票号查询电子票"], "d"),
    ("decision", ["票券是否存在？"], "d"),
    ("decision", ["票券状态是否为未使用？"], "d"),
    ("decision", ["是否处于验票时间窗内？", "（开始前 1 小时 ～ 活动结束）"], "d"),
    ("process", ["条件更新票券状态", "（并发下仅一个请求成功）"], "n"),
    ("process", ["写入核销记录", "（核销员、票号、核销时间）"], "n"),
    ("terminal", ["结束：核销成功"], "n"),
]

FAIL = {
    1: ["拒绝：票号无效或动态码已过期"],
    2: ["拒绝请求（401 / 403）"],
    4: ["拒绝：票券不存在"],
    5: ["拒绝：该票已核销 / 已作废"],
    6: ["拒绝：活动未开始或已结束"],
}

VLAB = {1: "通过", 2: "通过", 4: "存在", 5: "未使用", 6: "是"}
HLAB = {1: "解析失败", 2: "校验失败", 4: "不存在", 5: "状态异常", 6: "否"}


def main():
    Flowchart(MAIN, FAIL, VLAB, HLAB).render(OUT)


if __name__ == "__main__":
    main()
