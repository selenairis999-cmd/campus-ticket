# -*- coding: utf-8 -*-
"""重画论文图 4「数据库 E-R 图」——Chen 记法。

矩形 = 实体，菱形 = 联系，连线两端标 1 / N 基数；不画属性椭圆
（字段明细见论文表 6~表 10 与 docs/sql/schema.sql）。

版面（分层，交叉最少）：
  第 1 层  「用户」置顶居中 —— 它是 6 度枢纽；
  第 2 层  用户的 6 条联系菱形排成一行（发表 / 发布 / 产生 / 抢票 / 持有 / 核销），
           连线从用户底边呈扇形展开，扇形两端点都在同一水平带内，
           而该带内没有任何节点，因此几何上不可能压到框；
  第 3 层  6 个实体（评论 / 活动 / 抢票日志 / 订单 / 电子票 / 核销记录）；
  第 4 层  同层实体之间的联系菱形（评价 / 记录 / 出票 / 对应），只发生在相邻列之间；
  第 5/6 层「包含」菱形与「票种」实体，正对「活动」列垂直下挂。

框宽框高全部由 matplotlib 实测文字尺寸决定，不手工估算；字号从大到小搜索，
取第一个「节点互不重叠 + 没有任何线段穿过任何节点 + 不超 A4 版心」的档位。
"""
from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties
from matplotlib.lines import Line2D
from matplotlib.patches import Polygon, Rectangle

FONT_PATH = r"C:\Windows\Fonts\msyh.ttc"
OUT_DIR = Path(__file__).resolve().parent
OUT_NAME = "fig04_er_standard.png"

DPI = 300
PT = 72.0
WIDTH_IN = 6.2
MAX_H_IN = 9.4
W = WIDTH_IN * PT
MARGIN = 5.0

FS_MIN, FS_MAX, FS_STEP = 8.0, 14.0, 0.25
MIN_CLEAR = 4.0          # 任意两个节点之间的最小净距
MIN_GAP = 7.0            # 相邻两列之间的最小间距

PAD_X, PAD_Y = 7.0, 5.5
DIA_W_RATIO, DIA_H_RATIO = 2.15, 2.55   # 菱形外接框 = 文字外接框 × 系数
LW_BOX, LW_LINE = 1.3, 1.1
CARD_T = 0.42            # 1 / N 在连线上的位置比例（取中点附近，相邻线在此分离最开）
CARD_OFF = 7.0           # 1 / N 垂直于连线的偏移
MID_SHIFT = 9.0          # 同层联系菱形向两侧让开「包含」竖线的距离

Y_USER = 26.0
Y_DIA_TOP = 152.0
Y_ENT = 258.0
Y_DIA_MID = 368.0
Y_DIA_LOW = 462.0
Y_ENT_LOW = 558.0

HUB = "用户"
# 第 3 层的列序与各自上方的枢纽联系菱形
COL_SPEC = [
    ("评论", "发表"),
    ("活动", "发布"),
    ("抢票日志", "产生"),
    ("订单", "抢票"),
    ("电子票", "持有"),
    ("核销记录", "核销"),
]
# 同层联系：(实体 A, 实体 B, 联系名, A 端基数, B 端基数, 菱形横向偏移方向)
MID_SPEC = [
    ("活动", "评论", "评价", "1", "N", -1.0),
    ("活动", "抢票日志", "记录", "1", "N", +1.0),
    ("订单", "电子票", "出票", "1", "1", 0.0),
    ("电子票", "核销记录", "对应", "1", "1", 0.0),
]
# 跨层联系：父实体, 子实体, 联系名, 父端基数, 子端基数
LOW_SPEC = ("活动", "票种", "包含", "1", "N")


def all_links():
    hub = [(HUB, e, d, "1", "N") for e, d in COL_SPEC]
    mid = [(a, b, lab, ca, cb) for a, b, lab, ca, cb, _o in MID_SPEC]
    return hub + mid + [LOW_SPEC]


LINKS = all_links()
DIAMONDS = [l[2] for l in LINKS]
ENTITIES = sorted({l[0] for l in LINKS} | {l[1] for l in LINKS})


class Measurer:
    """用 matplotlib 自己量文字尺寸（dpi=72 时 1px = 1pt）。"""

    def __init__(self) -> None:
        self.fig = plt.figure(figsize=(2, 2), dpi=72)
        self.renderer = self.fig.canvas.get_renderer()

    def size(self, text: str, fs: float, fp: FontProperties):
        t = self.fig.text(0, 0, text, fontproperties=fp, fontsize=fs)
        bb = t.get_window_extent(renderer=self.renderer)
        t.remove()
        return float(bb.width), float(bb.height)


def rect_of(node):
    cx, cy, w, h = node
    return cx - w / 2.0, cy - h / 2.0, cx + w / 2.0, cy + h / 2.0


def clash(a, b, clear=MIN_CLEAR):
    ax0, ay0, ax1, ay1 = a
    bx0, by0, bx1, by1 = b
    gx = max(bx0 - ax1, ax0 - bx1)
    gy = max(by0 - ay1, ay0 - by1)
    return gx < clear and gy < clear


def rect_edge(cx, cy, w, h, tx, ty):
    """从矩形中心朝 (tx,ty) 的射线与矩形边界的交点。"""
    dx, dy = tx - cx, ty - cy
    if dx == 0.0 and dy == 0.0:
        return cx, cy
    sx = (w / 2.0) / abs(dx) if dx else float("inf")
    sy = (h / 2.0) / abs(dy) if dy else float("inf")
    s = min(sx, sy)
    return cx + dx * s, cy + dy * s


def dia_edge(cx, cy, dw, dh, tx, ty):
    """从菱形中心朝 (tx,ty) 的射线与菱形边界的交点。"""
    dx, dy = tx - cx, ty - cy
    if dx == 0.0 and dy == 0.0:
        return cx, cy
    s = 1.0 / (abs(dx) / (dw / 2.0) + abs(dy) / (dh / 2.0))
    return cx + dx * s, cy + dy * s


def seg_hits_rect(p1, p2, r, pad=0.0):
    """Liang-Barsky：线段 p1→p2 是否与矩形相交（矩形外扩 pad）。"""
    x0, y0, x1, y1 = r[0] - pad, r[1] - pad, r[2] + pad, r[3] + pad
    dx, dy = p2[0] - p1[0], p2[1] - p1[1]
    t0, t1 = 0.0, 1.0
    for p, q in ((-dx, p1[0] - x0), (dx, x1 - p1[0]),
                 (-dy, p1[1] - y0), (dy, y1 - p1[1])):
        if p == 0.0:
            if q < 0.0:
                return False
        else:
            r_ = q / p
            if p < 0.0:
                if r_ > t1:
                    return False
                if r_ > t0:
                    t0 = r_
            else:
                if r_ < t0:
                    return False
                if r_ < t1:
                    t1 = r_
    return t1 > 1e-9 and t0 < 1.0 - 1e-9


def seg_hits_diamond(p1, p2, cx, cy, dw, dh):
    """线段是否穿过菱形 |u| + |v| <= 1（u,v 为归一化坐标）。"""
    a, b = dw / 2.0, dh / 2.0
    u1, v1 = (p1[0] - cx) / a, (p1[1] - cy) / b
    u2, v2 = (p2[0] - cx) / a, (p2[1] - cy) / b
    du, dv = u2 - u1, v2 - v1
    t0, t1 = 0.0, 1.0
    for A, B in ((1, 1), (1, -1), (-1, 1), (-1, -1)):
        c0 = A * u1 + B * v1 - 1.0
        c1 = A * du + B * dv
        if abs(c1) < 1e-12:
            if c0 > 0.0:
                return False
        elif c1 > 0.0:
            t1 = min(t1, -c0 / c1)
        else:
            t0 = max(t0, -c0 / c1)
        if t0 > t1:
            return False
    return t1 > 1e-9 and t0 < 1.0 - 1e-9


def build(fs: float, m: Measurer, fp: FontProperties):
    esz, dsz = {}, {}
    for name in ENTITIES:
        w, h = m.size(name, fs, fp)
        esz[name] = (w + 2 * PAD_X, h + 2 * PAD_Y)
    for lab in DIAMONDS:
        w, h = m.size(lab, fs, fp)
        dsz[lab] = (w * DIA_W_RATIO, h * DIA_H_RATIO)

    colw = [max(esz[e][0], dsz[d][0]) for e, d in COL_SPEC]
    iact = [e for e, _d in COL_SPEC].index(LOW_SPEC[0])
    colw[iact] = max(colw[iact], dsz[LOW_SPEC[2]][0], esz[LOW_SPEC[1]][0])

    avail = W - 2 * MARGIN
    n = len(colw)
    if sum(colw) + MIN_GAP * (n - 1) > avail:
        return None
    gap = (avail - sum(colw)) / (n - 1)
    xs, cur = [], MARGIN
    for w in colw:
        xs.append(cur + w / 2.0)
        cur += w + gap
    idx = {e: i for i, (e, _d) in enumerate(COL_SPEC)}

    nodes = {}
    for i, (e, d) in enumerate(COL_SPEC):
        nodes[e] = (xs[i], Y_ENT, esz[e][0], esz[e][1])
        nodes[d] = (xs[i], Y_DIA_TOP, dsz[d][0], dsz[d][1])
    nodes[HUB] = ((xs[0] + xs[-1]) / 2.0, Y_USER, esz[HUB][0], esz[HUB][1])
    for a, b, lab, _ca, _cb, off in MID_SPEC:
        mx = (xs[idx[a]] + xs[idx[b]]) / 2.0 + off * MID_SHIFT
        nodes[lab] = (mx, Y_DIA_MID, dsz[lab][0], dsz[lab][1])
    nodes[LOW_SPEC[2]] = (xs[iact], Y_DIA_LOW, dsz[LOW_SPEC[2]][0], dsz[LOW_SPEC[2]][1])
    nodes[LOW_SPEC[1]] = (xs[iact], Y_ENT_LOW, esz[LOW_SPEC[1]][0], esz[LOW_SPEC[1]][1])

    keys = list(nodes)
    for i in range(len(keys)):
        for j in range(i + 1, len(keys)):
            if clash(rect_of(nodes[keys[i]]), rect_of(nodes[keys[j]])):
                return None
    rects = {k: rect_of(nodes[k]) for k in keys}

    # ---- 走线 ----
    hub_cx, hub_cy, hub_w, hub_h = nodes[HUB]
    hub_bot = hub_cy + hub_h / 2.0
    dia_top_v = min(nodes[d][1] - nodes[d][3] / 2.0 for _e, d in COL_SPEC)
    if dia_top_v - hub_bot < 30.0:
        return None

    routes = []
    # 1) 枢纽扇形：起点沿用户底边均匀铺开，终点为各菱形上顶点；
    #    起点与终点同序排列，因此线段之间不会交叉。
    order = sorted(range(n), key=lambda i: xs[i])
    for k, i in enumerate(order):
        e, d = COL_SPEC[i]
        sx = hub_cx - hub_w / 2.0 + hub_w * (k + 0.5) / n
        dx_, dy_, dw_, dh_ = nodes[d]
        routes.append({"link": (HUB, e, d, "1", "N"), "kind": "fan",
                       "segs": [((sx, hub_bot), (dx_, dy_ - dh_ / 2.0), {HUB, d})]})
    # 2) 菱形下顶点 → 实体顶边
    for e, d in COL_SPEC:
        dx_, dy_, dw_, dh_ = nodes[d]
        ex, ey, ew, eh = nodes[e]
        routes.append({"link": (HUB, e, d, "1", "N"), "kind": "drop",
                       "segs": [((dx_, dy_ + dh_ / 2.0), (ex, ey - eh / 2.0), {d, e})]})
    # 3) 同层联系：实体边 ↔ 菱形侧顶点
    for a, b, lab, ca, cb, _off in MID_SPEC:
        dx_, dy_, dw_, dh_ = nodes[lab]
        segs = []
        for ent in (a, b):
            ex, ey, ew, eh = nodes[ent]
            p1 = rect_edge(ex, ey, ew, eh, dx_, dy_)
            p2 = dia_edge(dx_, dy_, dw_, dh_, ex, ey)
            segs.append((p1, p2, {ent, lab}))
        routes.append({"link": (a, b, lab, ca, cb), "kind": "mid", "segs": segs})
    # 4) 跨层联系：垂直下挂
    a, b, lab, ca, cb = LOW_SPEC
    ax, ay, aw, ah = nodes[a]
    bx, by, bw, bh = nodes[b]
    dx_, dy_, dw_, dh_ = nodes[lab]
    routes.append({"link": LOW_SPEC, "kind": "low", "segs": [
        ((ax, ay + ah / 2.0), (dx_, dy_ - dh_ / 2.0), {a, lab}),
        ((dx_, dy_ + dh_ / 2.0), (bx, by - bh / 2.0), {lab, b}),
    ]})

    # 5) 校验：没有任何线段穿过任何节点（端点所属节点除外）
    for r in routes:
        for p1, p2, excl in r["segs"]:
            for k, nd in nodes.items():
                if k in excl:
                    continue
                if k in DIAMONDS:
                    if seg_hits_diamond(p1, p2, nd[0], nd[1], nd[2], nd[3]):
                        return None
                elif seg_hits_rect(p1, p2, rects[k]):
                    return None

    xs0 = min(r[0] for r in rects.values())
    ys0 = min(r[1] for r in rects.values())
    xs1 = max(r[2] for r in rects.values())
    ys1 = max(r[3] for r in rects.values())
    if xs1 - xs0 > avail or ys1 - ys0 > MAX_H_IN * PT - 2 * MARGIN:
        return None
    return {"fs": fs, "nodes": nodes, "rects": rects, "routes": routes,
            "bbox": (xs0, ys0, xs1, ys1), "gap": gap}


def draw(p, fp: FontProperties, out_path: Path) -> None:
    xs0, ys0, xs1, ys1 = p["bbox"]
    fs = p["fs"]
    nodes = p["nodes"]
    fig = plt.figure(figsize=(WIDTH_IN, (ys1 - ys0 + 2 * MARGIN) / PT), dpi=DPI)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(xs0 - MARGIN, xs1 + MARGIN)
    ax.set_ylim(ys1 + MARGIN, ys0 - MARGIN)          # y 轴向下
    ax.axis("off")

    # 1) 连线
    for r in p["routes"]:
        for p1, p2 in ((s[0], s[1]) for s in r["segs"]):
            ax.add_line(Line2D([p1[0], p2[0]], [p1[1], p2[1]], color="black",
                               linewidth=LW_LINE, zorder=1))
    # 2) 基数：按 Chen 记法，1 标在「实体—菱形」连线上、N 标在「菱形—实体」连线上。
    #    标签放在线段全长的 CARD_T 处（而非距端点固定距离），相邻连线在该处
    #    横向分离得最开，避免多个 1 挤在一起。
    for r in p["routes"]:
        a, b, lab, ca, cb = r["link"]
        if r["kind"] == "fan":
            p1, p2 = r["segs"][0][0], r["segs"][0][1]
            _mark(ax, fp, fs, p1, p2, ca, None)
        elif r["kind"] == "drop":
            p1, p2 = r["segs"][0][0], r["segs"][0][1]
            _mark(ax, fp, fs, p2, p1, cb, None)
        elif r["kind"] == "mid":
            for (p1, p2, _e), card in zip(r["segs"], (ca, cb)):
                _mark(ax, fp, fs, p1, p2, card, None)
        else:
            (p1, p2, _e1), (p3, p4, _e2) = r["segs"]
            _mark(ax, fp, fs, p1, p2, ca, None)
            _mark(ax, fp, fs, p4, p3, cb, None)

    # 3) 实体（矩形）
    for e, _d in COL_SPEC:
        _rect(ax, fp, fs, nodes[e], e)
    _rect(ax, fp, fs, nodes[HUB], HUB)
    _rect(ax, fp, fs, nodes[LOW_SPEC[1]], LOW_SPEC[1])

    # 4) 联系（菱形，白底盖住连线）
    for lab in DIAMONDS:
        _dia(ax, fp, fs, nodes[lab], lab)

    fig.savefig(out_path, dpi=DPI, facecolor="white")
    plt.close(fig)


def _mark(ax, fp, fs, p1, p2, text, dist):
    """在 p1→p2 上标注基数。dist 为 None 时取线段中点（相邻连线在此处分离最开）。"""
    dx, dy = p2[0] - p1[0], p2[1] - p1[1]
    ln = (dx * dx + dy * dy) ** 0.5 or 1.0
    t = CARD_T if dist is None else min(dist / ln, 0.5)
    lx, ly = p1[0] + dx * t, p1[1] + dy * t
    ax.text(lx + dy / ln * CARD_OFF, ly - dx / ln * CARD_OFF, text,
            ha="center", va="center", fontproperties=fp, fontsize=fs * 0.95,
            zorder=6, bbox=dict(boxstyle="square,pad=0.06",
                                facecolor="white", edgecolor="none"))


def _rect(ax, fp, fs, node, name):
    cx, cy, w, h = node
    ax.add_patch(Rectangle((cx - w / 2.0, cy - h / 2.0), w, h, facecolor="white",
                           edgecolor="black", linewidth=LW_BOX, zorder=3))
    ax.text(cx, cy, name, ha="center", va="center", fontproperties=fp,
            fontsize=fs, zorder=5)


def _dia(ax, fp, fs, node, name):
    cx, cy, dw, dh = node
    ax.add_patch(Polygon([(cx - dw / 2.0, cy), (cx, cy - dh / 2.0),
                          (cx + dw / 2.0, cy), (cx, cy + dh / 2.0)],
                         closed=True, facecolor="white", edgecolor="black",
                         linewidth=LW_BOX, zorder=4))
    ax.text(cx, cy, name, ha="center", va="center", fontproperties=fp,
            fontsize=fs, zorder=5)


def main() -> None:
    fp = FontProperties(fname=FONT_PATH)
    m = Measurer()
    best = None
    fs = FS_MAX
    while fs >= FS_MIN - 1e-9:
        best = build(round(fs, 2), m, fp)
        if best is not None:
            break
        fs -= FS_STEP
    if best is None:
        raise SystemExit("字号降到 %.2fpt 仍放不下，请调整层间距或列序" % FS_MIN)

    out = OUT_DIR / OUT_NAME
    draw(best, fp, out)
    xs0, ys0, xs1, ys1 = best["bbox"]
    h_in = (ys1 - ys0 + 2 * MARGIN) / PT
    print("字号 %.2fpt；列间距 %.1fpt；内容 %.1f x %.1f pt；插入 %.2f x %.2f in；像素 %d x %d"
          % (best["fs"], best["gap"], xs1 - xs0, ys1 - ys0, WIDTH_IN, h_in,
             round(WIDTH_IN * DPI), round(h_in * DPI)))
    print("实体 %d 个，联系 %d 条；%s" % (len(ENTITIES), len(LINKS), out))


if __name__ == "__main__":
    main()
