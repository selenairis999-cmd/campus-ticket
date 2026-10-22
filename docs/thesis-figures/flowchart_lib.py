# -*- coding: utf-8 -*-
"""
标准流程图渲染引擎（论文图 5 / 图 6 / 图 7 共用）。

符号约定（与论文其余流程图一致）：
  圆角矩形 = 起止框，矩形 = 处理框，菱形 = 判断框，实线箭头 = 控制流。纯黑白。

排版要点：
  1. 框宽框高由 matplotlib 实际渲染的文字尺寸测量得到（measure），不手工估算，
     因此中文永远不会顶到框线；
  2. 菱形按「文字块须落在菱形内接矩形内」的约束自动放大（w/DW + h/DH <= 0.94）；
  3. 节点间距按类型给足（含判断框的间隔 24pt，其余 16pt），箭头标签让开菱形顶点；
  4. 画布逻辑单位就是 pt，设计宽度 = 论文中的插入宽度，图内字号即论文实际字号；
  5. 自动从大到小试字号，取第一个宽高都放得下的档位。

右侧失败列由 fail 指定：{主流程下标: [文字行]}；
若该分支需要汇回主流程（而非直接结束），写成 {下标: {"lines": [...], "merge": True}}，
引擎会从该框底部引一条折线汇入主流程中轴。

用法见 make_fig5_flowchart.py / make_fig6_flowchart.py / make_fig7_flowchart.py。
"""
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties
from matplotlib.patches import FancyBboxPatch, Polygon, Rectangle
from PIL import Image

FONT_CANDIDATES = (r"C:\Windows\Fonts\msyh.ttc",
                   r"C:\Windows\Fonts\simhei.ttf",
                   r"C:\Windows\Fonts\simsun.ttc")

DPI = 300
PT = 72.0


def load_font():
    """优先微软雅黑，其次黑体、宋体。"""
    for path in FONT_CANDIDATES:
        if os.path.exists(path):
            return FontProperties(fname=path)
    return FontProperties()


class Flowchart:
    """把「主流程 + 右侧失败分支」的规格渲染成 PNG。"""

    def __init__(self, main, fail=None, vlab=None, hlab=None,
                 width_in=6.2, max_h_in=9.4, fs_min=7.0, fs_max=9.5,
                 margin_x=5.0, margin_top=8.0, margin_bottom=8.0,
                 pad_x=10.0, pad_y=7.0, gap_n=16.0, gap_d=24.0, gap_h=26.0,
                 line_width=1.2, linespacing=1.45, font=None):
        self.main = main
        self.fail = fail or {}
        self.vlab = vlab or {}
        self.hlab = hlab or {}
        self.width_in = width_in
        self.max_h_in = max_h_in
        self.fs_min, self.fs_max = fs_min, fs_max
        self.margin_x, self.margin_top, self.margin_bottom = margin_x, margin_top, margin_bottom
        self.pad_x, self.pad_y = pad_x, pad_y
        self.gap_n, self.gap_d, self.gap_h = gap_n, gap_d, gap_h
        self.line_width = line_width
        self.linespacing = linespacing
        self.font = font or load_font()
        self.W = width_in * PT

        # 文字测量用的临时画布：1 数据单位 = 1 像素
        self._mfig = plt.figure(figsize=(6, 6), dpi=DPI)
        self._max = self._mfig.add_axes([0, 0, 1, 1])
        self._max.set_xlim(0, 6 * DPI)
        self._max.set_ylim(0, 6 * DPI)
        self._max.axis("off")
        self._mrenderer = self._mfig.canvas.get_renderer()

    # ------------------------------------------------------------ 测量
    def measure(self, lines, fs):
        """返回文本块在 pt 单位下的 (宽, 高)。"""
        t = self._max.text(0.01, 0.5, "\n".join(lines), fontproperties=self.font,
                           fontsize=fs, linespacing=self.linespacing)
        bb = t.get_window_extent(renderer=self._mrenderer)
        t.remove()
        return bb.width * PT / DPI, bb.height * PT / DPI

    def diamond_size(self, tw, th, fs):
        """按内接矩形约束求菱形外框尺寸，保证文字不被边线切到。

        菱形内接矩形条件：tw/dw + th/dh <= 1（此处留 6% 余量取 0.94）。
        初值只影响收敛步数，不影响正确性，故取得较紧以免菱形虚胖。
        """
        dw = max(1.6 * tw, 11.0 * fs)
        dh = max(1.6 * th, 4.0 * fs)
        while tw / dw + th / dh > 0.94:
            dw *= 1.03
            dh *= 1.03
        return dw, dh

    def fail_lines(self, spec):
        """兼容 [行] 与 {"lines": [...], "merge": bool} 两种写法。"""
        if isinstance(spec, dict):
            return spec["lines"], bool(spec.get("merge"))
        return spec, False

    # ------------------------------------------------------------ 布局
    def build(self, fs):
        main = []
        for kind, lines, gap in self.main:
            tw, th = self.measure(lines, fs)
            if kind == "decision":
                bw, bh = self.diamond_size(tw, th, fs)
            else:
                extra = 14.0 if kind == "terminal" else 0.0
                bw, bh = tw + 2 * self.pad_x + extra, th + 2 * self.pad_y
            main.append({"kind": kind, "lines": lines, "gap": gap,
                         "w": bw, "h": bh, "tw": tw, "th": th})

        fail = {}
        for idx, spec in self.fail.items():
            lines, merge = self.fail_lines(spec)
            tw, th = self.measure(lines, fs)
            fail[idx] = {"lines": lines, "merge": merge, "w": tw + 2 * self.pad_x,
                         "h": th + 2 * self.pad_y, "tw": tw, "th": th}

        mw = max(n["w"] for n in main)
        fw = max(v["w"] for v in fail.values()) if fail else 0.0

        # 横向分支标签（如「已核销 / 已作废」）比默认列间距宽时会压到菱形顶点，
        # 故按标签实测宽度把间距撑开
        gap_h = self.gap_h
        for idx, lab in self.hlab.items():
            if lab:
                lw, _ = self.measure([lab], fs - 0.5)
                gap_h = max(gap_h, lw + 10.0)

        y = self.margin_top
        for n in main:
            n["cy"] = y + n["h"] / 2.0
            y = n["cy"] + n["h"] / 2.0
            if n is not main[-1]:
                y += self.gap_d if n["gap"] == "d" else self.gap_n
        total_h = y + self.margin_bottom
        return main, fail, mw + gap_h + fw, total_h, mw, fw, gap_h

    # ------------------------------------------------------------ 绘制
    def render(self, out_path, verbose=True):
        fs, layout = self.fs_min, None
        for i in range(int((self.fs_max - self.fs_min) / 0.25) + 1):
            cand = self.fs_max - 0.25 * i
            res = self.build(cand)
            if res[2] <= self.W - 2 * self.margin_x and res[3] <= self.max_h_in * PT:
                fs, layout = cand, res
                break
        if layout is None:                      # 放不下就用最小字号硬排
            fs = self.fs_min
            layout = self.build(fs)
        main, fail, total_w, total_h, mw, fw, gap_h = layout

        cx = self.margin_x + mw / 2.0                       # 主列中轴
        rx = self.margin_x + mw + gap_h + fw / 2.0          # 失败列中轴

        fig = plt.figure(figsize=(self.width_in, total_h / PT), dpi=DPI)
        ax = fig.add_axes([0, 0, 1, 1])
        ax.set_xlim(0, self.W)
        ax.set_ylim(total_h, 0)                             # y 轴向下，按阅读顺序排布
        ax.axis("off")

        stroke = dict(edgecolor="black", linewidth=self.line_width, facecolor="white")

        def put_text(x, y, lines):
            ax.text(x, y, "\n".join(lines), fontproperties=self.font, fontsize=fs,
                    ha="center", va="center", color="black",
                    linespacing=self.linespacing, zorder=3)

        def draw_node(kind, lines, w, h, x, y):
            if kind == "decision":
                ax.add_patch(Polygon([(x, y - h / 2), (x + w / 2, y),
                                      (x, y + h / 2), (x - w / 2, y)],
                                     closed=True, zorder=2, **stroke))
            elif kind == "terminal":
                ax.add_patch(FancyBboxPatch((x - w / 2, y - h / 2), w, h,
                                            boxstyle="round,pad=0,rounding_size=%f" % (h / 2.2),
                                            zorder=2, **stroke))
            else:
                ax.add_patch(Rectangle((x - w / 2, y - h / 2), w, h, zorder=2, **stroke))
            put_text(x, y, lines)

        def arrow(x1, y1, x2, y2):
            ax.annotate("", xy=(x2, y2), xytext=(x1, y1), zorder=1,
                        arrowprops=dict(arrowstyle="-|>", color="black",
                                        linewidth=self.line_width,
                                        mutation_scale=13, shrinkA=0, shrinkB=0))

        def polyline(points, head=True):
            """折线连接；head=False 表示汇入主流程线（标准画法不带箭头）。"""
            for (x1, y1), (x2, y2) in zip(points[:-2], points[1:-1]):
                ax.plot([x1, x2], [y1, y2], color="black",
                        linewidth=self.line_width, zorder=1)
            (x1, y1), (x2, y2) = points[-2], points[-1]
            if head:
                arrow(x1, y1, x2, y2)
            else:
                ax.plot([x1, x2], [y1, y2], color="black",
                        linewidth=self.line_width, zorder=1)

        for n in main:
            draw_node(n["kind"], n["lines"], n["w"], n["h"], cx, n["cy"])
        for idx, v in fail.items():
            draw_node("process", v["lines"], v["w"], v["h"], rx, main[idx]["cy"])

        def top(n):
            return n["cy"] - n["h"] / 2.0

        def bottom(n):
            return n["cy"] + n["h"] / 2.0

        # 主流程纵向箭头 + 分支标签
        for i in range(len(main) - 1):
            a, b = main[i], main[i + 1]
            arrow(cx, bottom(a), cx, top(b))
            lab = self.vlab.get(i, "")
            if lab:
                ax.text(cx + 5, (bottom(a) + top(b)) / 2.0, lab, fontproperties=self.font,
                        fontsize=fs - 0.5, ha="left", va="center", color="black", zorder=3)

        # 右侧失败分支
        prev_bottom = None
        for idx in sorted(fail):
            n, v = main[idx], fail[idx]
            arrow(cx + n["w"] / 2.0, n["cy"], rx - v["w"] / 2.0, n["cy"])
            lab = self.hlab.get(idx, "")
            if lab:
                ax.text((cx + n["w"] / 2.0 + rx - v["w"] / 2.0) / 2.0, n["cy"] - 3, lab,
                        fontproperties=self.font, fontsize=fs - 0.5,
                        ha="center", va="bottom", color="black", zorder=3)
            box_top, box_bottom = n["cy"] - v["h"] / 2.0, n["cy"] + v["h"] / 2.0
            if prev_bottom is not None and box_top < prev_bottom + 4.0:
                raise SystemExit("失败列出现重叠：下标 %d（上框底 %.1f，本框顶 %.1f）"
                                 % (idx, prev_bottom, box_top))
            prev_bottom = box_bottom
            if v["merge"]:                      # 汇回主流程中轴
                if idx + 1 >= len(main):
                    raise SystemExit("merge 分支必须位于最后一个节点之前")
                y_merge = (bottom(n) + top(main[idx + 1])) / 2.0
                y_merge = max(y_merge, box_bottom + 5.0)
                polyline([(rx, box_bottom), (rx, y_merge), (cx, y_merge)], head=False)

        fig.savefig(out_path, dpi=DPI, facecolor="white")
        px = Image.open(out_path).size
        info = {"font_size": fs, "pixels": px, "bytes": os.path.getsize(out_path),
                "insert_w_in": self.width_in, "insert_h_in": self.width_in * total_h / self.W,
                "main_w": mw, "fail_w": fw, "total_w": total_w, "total_h": total_h,
                "used_w": mw + self.gap_h + fw, "avail_w": self.W - 2 * self.margin_x,
                "avail_h": self.max_h_in * PT}
        if verbose:
            print("saved   :", out_path)
            print("bytes   :", info["bytes"])
            print("字号    : %.2f pt（论文中即为实际字号）" % fs)
            print("像素    : %d x %d @ %d dpi" % (px[0], px[1], DPI))
            print("插入尺寸: %.2f in x %.2f in  （版心 6.30 x 9.73 in）"
                  % (info["insert_w_in"], info["insert_h_in"]))
            print("宽度校验: 主列 %.1f + 间距 %.1f + 失败列 %.1f = %.1f pt（可用 %.1f）"
                  % (mw, gap_h, fw, mw + gap_h + fw, info["avail_w"]))
            print("高度校验: 内容 %.1f pt / 可用 %.1f pt" % (total_h, info["avail_h"]))
        return info
