# -*- coding: utf-8 -*-
"""
图 1 系统功能结构图：标准「根节点 → 模块 → 功能点」树形，按 A4 版心宽 6.2in 排版。

为什么要重画：原图是 3572x595 的极扁横图（宽高比 6:1），按 A4 版心宽度插入后只有 1.88in 高，
文字被压到约 5pt 无法辨认，且 6.44in 宽已超出 6.3in 版心。改为「模块三列栅格 +
功能点纵向排列」后把 A4 的高度用起来，字号可放大到 10~12pt（正文同级）。

排版要点：
  1. 字号由「宽度 + 高度」双重约束自动从大到小搜索，取第一个放得下的档位；
  2. 框宽框高由 matplotlib 实测文字尺寸决定，机制上不可能顶破框线；
  3. 功能点框采用两段式：功能名（fs）+ 技术标注（0.85fs，可选），
     这样「一键抢票 / 时间窗·一人一票」这类带标注的功能点不必折成难看的长行；
  4. 折行遵守中文排版惯例：括号内容、英文单词、数字为原子单元，
     不在「（」后或「）」前断行（见 atoms()），折行时选最均衡的断点；
  5. 纯黑白、无底纹；图内字号即导出后的实际字号。

用法：
  python docs/diagrams/make_fig1_function_tree.py
"""
import os
import re
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties
from matplotlib.patches import FancyBboxPatch, Rectangle

FONT_CANDIDATES = (r"C:\Windows\Fonts\msyh.ttc",
                   r"C:\Windows\Fonts\simhei.ttf",
                   r"C:\Windows\Fonts\simsun.ttc")

DPI = 300
PT = 72.0

WIDTH_IN = 6.2          # A4 版心宽 6.3in 之内
MAX_H_IN = 9.0          # 上限：一页（版心高 9.73in）能放下且留出题注位置
FS_MIN, FS_MAX = 7.0, 12.0
ANN_RATIO = 0.85        # 技术标注相对功能名的字号比例

OUT = Path(__file__).resolve().parent

ROOT_TEXT = "校园票务系统"

# 3+2+2 栅格：(模块名, [(功能名, 技术标注 or None), ...])
ROWS = [
    [
        ("用户管理", [("注册登录", "找回密码"),
                      ("JWT 认证", None),
                      ("密码加密", "BCrypt")]),
        ("活动管理", [("活动发布 / 编辑", None),
                      ("活动搜索 / 删除", None),
                      ("多票种管理", "独立库存")]),
        ("抢票模块", [("活动浏览", None),
                      ("一键抢票", "时间窗 · 一人一票"),
                      ("双重乐观锁防超卖", None)]),
    ],
    [
        ("核销模块", [("动态二维码", "3 秒 SHA-256 签名"),
                      ("扫码核销", "验签 · 更新状态"),
                      ("核销记录查询", None)]),
        ("评论互动", [("发表评论", "已核销可评"),
                      ("追评", "每条主评 ≤ 2 次"),
                      ("情感分析", "60 秒增量回填")]),
    ],
    [
        ("监控与统计", [("活动统计", None),
                        ("出勤统计", None),
                        ("情感聚合分析", None),
                        ("电子证书", None)]),
        ("风控模块", [("在线拦截", "R0 / R1 / R2"),
                      ("离线检测", "孤立森林 · 3σ 对照"),
                      ("分级处置", "30 秒 / 限时 / 永久")]),
    ],
]


def load_font():
    for path in FONT_CANDIDATES:
        if os.path.exists(path):
            return FontProperties(fname=path)
    return FontProperties()


class Measurer:
    """用 matplotlib 真实渲染测量文字宽度（dpi=72 时 1 像素 = 1 pt）。"""

    def __init__(self, fp):
        self.fig = plt.figure(figsize=(8, 8), dpi=72)
        self.ax = self.fig.add_axes([0, 0, 1, 1])
        self.ax.set_xlim(0, 8 * 72)
        self.ax.set_ylim(0, 8 * 72)
        self.ax.axis("off")
        self.fp = fp
        self.fig.canvas.draw()
        self.renderer = self.fig.canvas.get_renderer()

    def width(self, s, fs):
        t = self.ax.text(0, 0, s, fontproperties=self.fp, fontsize=fs)
        w = t.get_window_extent(renderer=self.renderer).width
        t.remove()
        return w


OPEN_BR = "（(【《"
CLOSE_BR = "）)】》"
LATIN = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789")
LATIN_EXTRA = set("._-+%>=")


def atoms(text):
    """
    把标签切成排版原子（不在原子内部断行）：
      · 连续的英文/数字为一个原子（BCrypt、SHA-256、3σ 中的 3）；
      · 空格粘在前一个原子尾部，使「时间窗 · 一人一票」可在「·」后断行；
      · 中文单字成原子，但「（」粘住后一个原子、「）」粘住前一个原子，
        保证不会出现「（」结尾或「）」开头的行。
    """
    text = re.sub(r"\s+", " ", text).strip()
    units, i, n = [], 0, len(text)
    while i < n:
        ch = text[i]
        if ch in LATIN or ch in LATIN_EXTRA:
            j = i
            while j < n and (text[j] in LATIN or text[j] in LATIN_EXTRA):
                j += 1
            units.append(text[i:j])
            i = j
        elif ch == " ":
            if units:
                units[-1] += " "
            i += 1
        else:
            units.append(ch)
            i += 1

    merged = []
    for u in units:
        if merged and (u in CLOSE_BR or merged[-1][-1] in OPEN_BR):
            merged[-1] += u
        else:
            merged.append(u)
    return merged


def split_lines(text, max_w, fs, m):
    """
    把 text 排进宽度 max_w：能一行放下就一行；否则在所有原子边界里挑
    最均衡的两行断点（行宽尽量接近、避免孤字）；再放不下返回 None，
    由字号搜索继续缩小字号。
    """
    if m.width(text, fs) <= max_w:
        return [text]

    units = atoms(text)
    best = None
    for k in range(1, len(units)):
        l1 = "".join(units[:k]).rstrip()
        l2 = "".join(units[k:]).lstrip()
        if not l1 or not l2:
            continue
        w1, w2 = m.width(l1, fs), m.width(l2, fs)
        if w1 > max_w or w2 > max_w:
            continue
        score = max(w1, w2) + 0.6 * abs(w1 - w2) + (40.0 if len(l2) <= 1 else 0.0)
        if best is None or score < best[0]:
            best = (score, [l1, l2])
    return best[1] if best else None


# 几何常量（pt）
MARGIN_X = 4.0          # 画布左右留白
TRUNK_X = 8.0           # 左侧干线 x
COLS_X0 = 22.0          # 第一列起点
COL_GAP = 12.0
ROW_BUS_GAP = 15.0      # 行总线到该行模块顶边的距离
CHILD_START_GAP = 15.0  # 模块底边到第一个功能点顶边的距离
CHILD_GAP = 7.0
CHILD_BUS = 5.0         # 支线总线相对模块左边的位置
CHILD_INDENT = 16.0     # 功能点相对模块左边的缩进
MARGIN_TOP = 8.0
MARGIN_BOTTOM = 6.0
GAP_ROOT = 26.0
ROW_GAP = 26.0
PAD_X = 7.0
PAD_Y = 5.0
LINE = 1.42
LW_BOX, LW_KID, LW_LINE = 1.4, 1.2, 1.0


def build(fs, m):
    """按给定字号算出整套几何；任何文字放不下或总高超限则返回 None。"""
    root_fs = fs * 1.15
    root_w = m.width(ROOT_TEXT, root_fs) + 34
    root_h = root_fs * LINE + 16
    ann_fs = fs * ANN_RATIO

    ncol = max(len(r) for r in ROWS)
    col_w = (WIDTH_IN * PT - COLS_X0 - MARGIN_X - (ncol - 1) * COL_GAP) / ncol
    kid_w = col_w - CHILD_INDENT
    lim_m, lim_k = col_w - 2 * PAD_X, kid_w - 2 * PAD_X

    plan_rows = []
    for row in ROWS:
        cells = []
        for name, children in row:
            mlines = split_lines(name, lim_m, fs, m)
            if mlines is None:
                return None
            kids = []
            for cname, cann in children:
                nlines = split_lines(cname, lim_k, fs, m)
                if nlines is None:
                    return None
                alines = split_lines(cann, lim_k, ann_fs, m) if cann else []
                if cann and alines is None:
                    return None
                h = (len(nlines) * fs + len(alines) * ann_fs) * LINE + 2 * PAD_Y
                kids.append({"name": nlines, "ann": alines, "h": h})
            mh = len(mlines) * fs * LINE + 2 * PAD_Y
            cells.append({"name": mlines, "mh": mh, "kids": kids})
        row_h = max(c["mh"] + CHILD_START_GAP
                    + sum(k["h"] for k in c["kids"]) + (len(c["kids"]) - 1) * CHILD_GAP
                    for c in cells)
        plan_rows.append({"cells": cells, "h": row_h, "n": len(row), "col_w": col_w})

    H = (MARGIN_TOP + root_h + GAP_ROOT
         + sum(r["h"] for r in plan_rows) + (len(plan_rows) - 1) * ROW_GAP
         + MARGIN_BOTTOM)
    if H > MAX_H_IN * PT:
        return None
    return {"fs": fs, "ann_fs": ann_fs, "root_fs": root_fs, "root_w": root_w,
            "root_h": root_h, "rows": plan_rows, "H": H, "col_w": col_w,
            "kid_w": kid_w, "ncol": ncol}


def draw(p, fp):
    W, H = WIDTH_IN * PT, p["H"]
    fs, ann_fs, col_w, kid_w = p["fs"], p["ann_fs"], p["col_w"], p["kid_w"]

    fig = plt.figure(figsize=(WIDTH_IN, H / PT), dpi=DPI)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, W)
    ax.set_ylim(H, 0)
    ax.axis("off")

    def stacked(cx, cy, blocks):
        """blocks = [(lines, fontsize), ...]，整体垂直居中于 cy。"""
        hs = [len(l) * f * LINE for l, f in blocks]
        y = cy - sum(hs) / 2
        for (lines, f), h in zip(blocks, hs):
            ax.text(cx, y + h / 2, "\n".join(lines), ha="center", va="center",
                    fontproperties=fp, fontsize=f, linespacing=LINE, color="black")
            y += h

    def box(x, y, w, h, blocks, rounded=False, lw=LW_KID):
        if rounded:
            ax.add_patch(FancyBboxPatch((x, y), w, h,
                                        boxstyle="round,pad=0,rounding_size=6",
                                        facecolor="white", edgecolor="black",
                                        linewidth=lw))
        else:
            ax.add_patch(Rectangle((x, y), w, h, facecolor="white",
                                   edgecolor="black", linewidth=lw))
        stacked(x + w / 2, y + h / 2, blocks)

    def arrow(x1, y1, x2, y2):
        ax.annotate("", xy=(x2, y2), xytext=(x1, y1),
                    arrowprops=dict(arrowstyle="-|>", color="black",
                                    linewidth=LW_LINE, mutation_scale=9,
                                    shrinkA=0, shrinkB=0))

    def seg(pts):
        ax.plot([q[0] for q in pts], [q[1] for q in pts],
                color="black", linewidth=LW_LINE, solid_capstyle="butt")

    # ---- 根节点 ----
    ry = MARGIN_TOP
    box((W - p["root_w"]) / 2, ry, p["root_w"], p["root_h"],
        [([ROOT_TEXT], p["root_fs"])], rounded=True, lw=LW_BOX)
    y_elbow = ry + p["root_h"] + GAP_ROOT * 0.45
    seg([(W / 2, ry + p["root_h"]), (W / 2, y_elbow), (TRUNK_X, y_elbow)])

    # ---- 各行模块列位置（不足一行的居中）----
    y = MARGIN_TOP + p["root_h"] + GAP_ROOT
    geoms = []
    for r in p["rows"]:
        span = r["n"] * col_w + (r["n"] - 1) * COL_GAP
        x0 = COLS_X0 + (W - MARGIN_X - COLS_X0 - span) / 2
        centers = [(x0 + k * (col_w + COL_GAP), x0 + k * (col_w + COL_GAP) + col_w)
                   for k in range(r["n"])]
        geoms.append({"top": y, "bus_y": y - ROW_BUS_GAP, "centers": centers, "row": r})
        y += r["h"] + ROW_GAP

    seg([(TRUNK_X, y_elbow), (TRUNK_X, geoms[-1]["bus_y"])])   # 左侧干线

    for g in geoms:
        r, top, bus_y = g["row"], g["top"], g["bus_y"]
        last_cx = (g["centers"][-1][0] + g["centers"][-1][1]) / 2
        seg([(TRUNK_X, bus_y), (last_cx, bus_y)])               # 行总线
        for cx0, cx1 in g["centers"]:
            arrow((cx0 + cx1) / 2, bus_y, (cx0 + cx1) / 2, top)

        for (cx0, cx1), c in zip(g["centers"], r["cells"]):
            mh = c["mh"]
            box(cx0, top, col_w, mh, [(c["name"], fs)], rounded=True, lw=LW_BOX)

            ccx = cx0 + col_w / 2
            y0 = top + mh + CHILD_START_GAP * 0.5
            bx, kx = cx0 + CHILD_BUS, cx0 + CHILD_INDENT

            ky, kcenters = top + mh + CHILD_START_GAP, []
            for k in c["kids"]:
                kcenters.append(ky + k["h"] / 2)
                ky += k["h"] + CHILD_GAP

            seg([(ccx, top + mh), (ccx, y0), (bx, y0)])         # 模块底边 → 左折
            seg([(bx, y0), (bx, kcenters[-1])])                 # 支线总线
            ky = top + mh + CHILD_START_GAP
            for k, kcy in zip(c["kids"], kcenters):
                arrow(bx, kcy, kx, kcy)
                blocks = [(k["name"], fs)]
                if k["ann"]:
                    blocks.append((k["ann"], ann_fs))
                box(kx, ky, kid_w, k["h"], blocks, rounded=False, lw=LW_KID)
                ky += k["h"] + CHILD_GAP

    fig.savefig(OUT / "fig01_function_tree_standard.png", dpi=DPI,
                facecolor="white")
    plt.close(fig)
    return OUT / "fig01_function_tree_standard.png"


def main():
    fp = load_font()
    m = Measurer(fp)

    chosen = None
    fs = FS_MAX
    while fs >= FS_MIN - 1e-9:
        p = build(fs, m)
        if p is not None:
            chosen = p
            break
        fs -= 0.25
    if chosen is None:
        raise SystemExit("字号降到 %.1fpt 仍排不下，请精简文字" % FS_MIN)

    out = draw(chosen, fp)
    from PIL import Image
    w_px, h_px = Image.open(out).size

    print("saved   :", out)
    print("bytes   :", out.stat().st_size)
    print("字号    : %.2f pt（图内即实际字号；标注 %.2f pt；根节点 %.2f pt）"
          % (chosen["fs"], chosen["ann_fs"], chosen["root_fs"]))
    print("像素    : %d x %d @ %d dpi" % (w_px, h_px, DPI))
    print("插入尺寸: %.2f in x %.2f in  （版心 6.30 x 9.73 in）"
          % (w_px / DPI, h_px / DPI))
    print("高度校验: 内容 %.1f pt / 上限 %.1f pt" % (chosen["H"], MAX_H_IN * PT))
    for i, r in enumerate(chosen["rows"]):
        print("  第 %d 行: %d 个模块，单列宽 %.1f pt，行高 %.1f pt"
              % (i + 1, r["n"], r["col_w"], r["h"]))
        for c in r["cells"]:
            print("      %s：%s" % ("/".join(c["name"]),
                                    " | ".join("/".join(k["name"])
                                               + ("（%s）" % "".join(k["ann"]) if k["ann"] else "")
                                               for k in c["kids"])))


if __name__ == "__main__":
    main()
