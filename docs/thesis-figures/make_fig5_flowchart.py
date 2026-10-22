# -*- coding: utf-8 -*-
"""
生成论文图 5「抢票流程图」——标准流程图符号：
  圆角矩形 = 起止框，矩形 = 处理框，菱形 = 判断框，箭头 = 控制流。纯黑白。

上一版的两个毛病在这里修掉：
  1. 文字溢出框 —— 框宽/框高改由 matplotlib 实际渲染的文字尺寸测量得到（measure()），
     不再手工估算，因此中文永远不会顶到框线；
  2. 箭头被挡 —— 节点间距改为按类型给足（判断框之间 24pt），
     且箭头标签让开菱形顶点。

菱形按「文字块须落在菱形内接矩形内」的约束自动放大：w/DW + h/DH <= 0.94。
画布逻辑单位就是 pt，设计宽度 = 论文中的插入宽度，图内字号即论文实际字号。

流程与失败分支严格对应：
  ActivityController#grabTicket（风控在线校验 + 版本冲突有限次重试）
  ActivityServiceImpl#grabTicket（业务校验 + 双重乐观锁扣减）

用法：python docs/thesis-figures/make_fig5_flowchart.py
输出：docs/thesis-figures/fig05_grab_flow_standard.png
"""
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties
from matplotlib.patches import FancyBboxPatch, Polygon, Rectangle
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "fig05_grab_flow_standard.png")

FONT = FontProperties()
for _f in (r"C:\Windows\Fonts\msyh.ttc", r"C:\Windows\Fonts\simhei.ttf",
           r"C:\Windows\Fonts\simsun.ttc"):
    if os.path.exists(_f):
        FONT = FontProperties(fname=_f)
        break

# ---------------------------------------------------------------- 版面参数（单位 pt）
TARGET_W_IN = 6.2               # 论文中的插入宽度（A4 版心宽 6.3in 之内）
MAX_H_IN = 9.4                  # 单页版心高 9.73in，留出题注空间
DPI = 300
PT = 72.0
W = TARGET_W_IN * PT            # 画布逻辑宽度

MARGIN_X, MARGIN_TOP, MARGIN_BOTTOM = 5.0, 8.0, 8.0
PAD_X, PAD_Y = 10.0, 7.0        # 文字与框边的最小间距
GAP_N, GAP_D = 16.0, 24.0       # 节点垂直间距：普通 / 含判断框
GAP_H = 26.0                    # 主列到失败列的横向间距
LW = 1.2                        # 线宽
LS = 1.45                       # 行距倍数
FS_MIN, FS_MAX = 7.0, 9.5

# ---------------------------------------------------------------- 流程内容
# (类型, 文字行, 到下一节点的间距类型)
MAIN = [
    ("terminal", ["开始：学生发起抢票请求"], "n"),
    ("process", ["风控在线校验", "（R0 黑名单 / R1 限频 / R2 同 IP 检测）"], "n"),
    ("decision", ["活动是否存在？"], "d"),
    ("decision", ["活动状态与抢票时间窗", "是否合法？"], "d"),
    ("decision", ["该用户是否已购买", "本活动门票？"], "d"),
    ("process", ["定位票种（未指定则取第一个票种）"], "d"),
    ("decision", ["票种剩余库存 > 0？"], "d"),
    ("decision", ["活动剩余库存 > 0？"], "d"),
    ("process", ["同一事务内双重乐观锁扣减库存", "（先扣票种，再扣活动）"], "n"),
    ("process", ["生成订单与电子票，写入 SUCCESS 日志"], "n"),
    ("terminal", ["结束：返回抢票成功"], "n"),
]

# 主流程节点下标 -> 右侧失败分支文字
FAIL = {
    1: ["拒绝：命中风控规则（RISK_BLOCKED）"],
    2: ["拒绝：活动不存在（ERROR）"],
    3: ["拒绝：抢票未开始或已结束", "（TIME_WINDOW / ACTIVITY_ENDED）"],
    4: ["拒绝：每人限购一张（DUPLICATE）"],
    6: ["拒绝：该票种已抢完（STOCK_EMPTY）"],
    7: ["拒绝：门票已抢完（STOCK_EMPTY）"],
    8: ["抛出异常，事务整体回滚", "（VERSION_CONFLICT，控制层有限次重试）"],
}

VLAB = {0: "", 1: "未命中", 2: "是", 3: "是", 4: "否",
        5: "", 6: "是", 7: "是", 8: "扣减成功", 9: ""}
HLAB = {1: "命中", 2: "否", 3: "否", 4: "是", 6: "否", 7: "否", 8: "失败"}

# ---------------------------------------------------------------- 文字测量
_mfig = plt.figure(figsize=(6, 6), dpi=DPI)
_max = _mfig.add_axes([0, 0, 1, 1])
_max.set_xlim(0, 6 * DPI)
_max.set_ylim(0, 6 * DPI)       # 1 数据单位 = 1 像素
_max.axis("off")
_mrenderer = _mfig.canvas.get_renderer()


def measure(lines, fs):
    """返回文本块在 pt 单位下的 (宽, 高)。"""
    t = _max.text(0.01, 0.5, "\n".join(lines), fontproperties=FONT,
                  fontsize=fs, linespacing=LS)
    bb = t.get_window_extent(renderer=_mrenderer)
    t.remove()
    return bb.width * PT / DPI, bb.height * PT / DPI


def diamond_size(tw, th, fs):
    """按内接矩形约束求菱形外框尺寸，保证文字不被边线切到。"""
    dw = max(2.4 * tw, 10.0 * fs)
    dh = max(2.4 * th, 2.4 * fs)
    while tw / dw + th / dh > 0.94:
        dw *= 1.05
        dh *= 1.05
    return dw, dh


def build(fs):
    """按字号 fs 计算整套布局。"""
    main = []
    for kind, lines, gap in MAIN:
        tw, th = measure(lines, fs)
        if kind == "decision":
            bw, bh = diamond_size(tw, th, fs)
        else:
            extra = 14.0 if kind == "terminal" else 0.0
            bw, bh = tw + 2 * PAD_X + extra, th + 2 * PAD_Y
        main.append({"kind": kind, "lines": lines, "gap": gap,
                     "w": bw, "h": bh, "tw": tw, "th": th})

    fail = {}
    for idx, lines in FAIL.items():
        tw, th = measure(lines, fs)
        fail[idx] = {"lines": lines, "w": tw + 2 * PAD_X, "h": th + 2 * PAD_Y,
                     "tw": tw, "th": th}

    mw = max(n["w"] for n in main)
    fw = max(v["w"] for v in fail.values())

    y = MARGIN_TOP
    for n in main:
        n["cy"] = y + n["h"] / 2.0
        y = n["cy"] + n["h"] / 2.0
        if n is not main[-1]:
            y += GAP_D if n["gap"] == "d" else GAP_N
    total_h = y + MARGIN_BOTTOM
    return main, fail, mw + GAP_H + fw, total_h, mw, fw


# 自动选字号：从大到小，取第一个宽高都放得下的
fs = FS_MIN
for cand in [FS_MAX - 0.25 * i for i in range(int((FS_MAX - FS_MIN) / 0.25) + 1)]:
    m, f, total_w, total_h, mw, fw = build(cand)
    if total_w <= W - 2 * MARGIN_X and total_h <= MAX_H_IN * PT:
        fs, main, fail, total_w, total_h = cand, m, f, total_w, total_h
        break

CX = MARGIN_X + mw / 2.0                        # 主列中轴
RX = MARGIN_X + mw + GAP_H + fw / 2.0           # 失败列中轴

fig = plt.figure(figsize=(TARGET_W_IN, total_h / PT), dpi=DPI)
ax = fig.add_axes([0, 0, 1, 1])
ax.set_xlim(0, W)
ax.set_ylim(total_h, 0)                         # y 轴向下，按阅读顺序排布
ax.axis("off")

STROKE = dict(edgecolor="black", linewidth=LW, facecolor="white")


def put_text(cx, cy, lines):
    ax.text(cx, cy, "\n".join(lines), fontproperties=FONT, fontsize=fs,
            ha="center", va="center", color="black", linespacing=LS, zorder=3)


def draw_node(kind, lines, w, h, cx, cy):
    if kind == "decision":
        ax.add_patch(Polygon([(cx, cy - h / 2), (cx + w / 2, cy),
                              (cx, cy + h / 2), (cx - w / 2, cy)],
                             closed=True, zorder=2, **STROKE))
    elif kind == "terminal":
        ax.add_patch(FancyBboxPatch((cx - w / 2, cy - h / 2), w, h,
                                    boxstyle="round,pad=0,rounding_size=%f" % (h / 2.2),
                                    zorder=2, **STROKE))
    else:
        ax.add_patch(Rectangle((cx - w / 2, cy - h / 2), w, h, zorder=2, **STROKE))
    put_text(cx, cy, lines)


for n in main:
    draw_node(n["kind"], n["lines"], n["w"], n["h"], CX, n["cy"])
for idx, v in fail.items():
    draw_node("process", v["lines"], v["w"], v["h"], RX, main[idx]["cy"])


def arrow(x1, y1, x2, y2):
    ax.annotate("", xy=(x2, y2), xytext=(x1, y1), zorder=1,
                arrowprops=dict(arrowstyle="-|>", color="black", linewidth=LW,
                                mutation_scale=13, shrinkA=0, shrinkB=0))


def top(n):
    return n["cy"] - n["h"] / 2.0


def bottom(n):
    return n["cy"] + n["h"] / 2.0


def right(n):
    return CX + n["w"] / 2.0


for i in range(len(main) - 1):
    a, b = main[i], main[i + 1]
    arrow(CX, bottom(a), CX, top(b))
    lab = VLAB.get(i, "")
    if lab:
        ax.text(CX + 5, (bottom(a) + top(b)) / 2.0, lab, fontproperties=FONT,
                fontsize=fs - 0.5, ha="left", va="center", color="black", zorder=3)

for idx in FAIL:
    n = main[idx]
    x1, x2 = right(n), RX - fail[idx]["w"] / 2.0
    arrow(x1, n["cy"], x2, n["cy"])
    lab = HLAB.get(idx, "")
    if lab:
        ax.text((x1 + x2) / 2.0, n["cy"] - 3, lab, fontproperties=FONT,
                fontsize=fs - 0.5, ha="center", va="bottom", color="black", zorder=3)

fig.savefig(OUT, dpi=DPI, facecolor="white")
px = Image.open(OUT).size
print("saved   :", OUT)
print("bytes   :", os.path.getsize(OUT))
print("字号    : %.2f pt（论文中即为实际字号）" % fs)
print("像素    : %d x %d @ %d dpi" % (px[0], px[1], DPI))
print("插入尺寸: %.2f in x %.2f in  （版心 6.30 x 9.73 in）"
      % (TARGET_W_IN, TARGET_W_IN * total_h / W))
print("宽度校验: 主列 %.1f + 间距 %.1f + 失败列 %.1f = %.1f pt（可用 %.1f）"
      % (mw, GAP_H, fw, mw + GAP_H + fw, W - 2 * MARGIN_X))
print("高度校验: 内容 %.1f pt / 可用 %.1f pt" % (total_h, MAX_H_IN * PT))
print("最小间隙: 判断框之间 %.1f pt" % GAP_D)
