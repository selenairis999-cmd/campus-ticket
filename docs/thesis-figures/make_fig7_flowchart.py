# -*- coding: utf-8 -*-
"""
生成论文图 7「情感分析流程图」——标准流程图符号。

流程严格对应实现：
  CommentServiceImpl#addComment      → 发评论前置校验（已核销票数、追评次数）
  CommentAnalyzeTask#scheduledAnalyze → 每 60 秒调用 predict_new.py 增量回填
  sentiment/predict_new.py           → 无效评论直接判 9，有效评论走模型
  CommentServiceImpl#stats           → 管理端聚合统计（9 不计入情感分布）

用法：python docs/thesis-figures/make_fig7_flowchart.py
输出：docs/thesis-figures/fig07_sentiment_flow_standard.png
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from flowchart_lib import Flowchart  # noqa: E402

OUT = os.path.join(HERE, "fig07_sentiment_flow_standard.png")

MAIN = [
    ("terminal", ["开始：学生发表评论"], "n"),
    ("decision", ["是否持有已核销票？"], "d"),
    ("process", ["保存评论，sentiment 置空"], "n"),
    ("process", ["定时任务每 60 秒触发", "（或管理员点击「立即分析」）"], "n"),
    ("process", ["调用 predict_new.py", "（TF-IDF 字符 1-2gram + LinearSVC）"], "d"),
    ("decision", ["评论是否为有效文本？", "（非纯标点且长度 ≥ 2）"], "d"),
    ("process", ["回写 sentiment 标签", "（0 差评 / 1 中评 / 2 好评）"], "n"),
    ("process", ["管理端聚合统计", "（无意义评论不计入情感分布）"], "n"),
    ("terminal", ["结束：展示情感分布与好评率"], "n"),
]

FAIL = {
    1: ["拒绝评论（未到场不能评价）"],
    5: {"lines": ["直接标记为无意义（9）", "不参与模型预测"], "merge": True},
}

VLAB = {1: "是", 5: "是", 6: "回填完成"}
HLAB = {1: "否", 5: "否"}


def main():
    Flowchart(MAIN, FAIL, VLAB, HLAB).render(OUT)


if __name__ == "__main__":
    main()
