# -*- coding: utf-8 -*-
"""生成「实体图」系列——每张数据表配一张「XX 实体图」，粒度与 docs/sql/schema.sql 一致。

为每张数据表配一张「XX 实体图」，
字段明细见 docs/sql/schema.sql 的「序号/字段名/数据类型/长度/主键/备注说明」六列说明。
本脚本产出前者：属性以椭圆形式环绕实体矩形，主键属性加下划线。

布局：属性椭圆分左右两列（属性多时按列均分），列距与行距由实测文字尺寸决定，
字体从大到小搜索，取第一个「节点互不重叠 + 连线不穿节点 + 不超 A4 版心」的档位。
"""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties
from matplotlib.patches import Ellipse, FancyArrowPatch, Rectangle

FONT_PATH = r"C:\Windows\Fonts\msyh.ttc"
OUT_DIR = Path(__file__).resolve().parent
CODE_DIR = OUT_DIR / "er"

DPI = 300
PT = 72.0
WIDTH_IN = 6.2
MAX_H_IN = 8.6
W = WIDTH_IN * PT

FS_MIN, FS_MAX, FS_STEP = 7.5, 15.0, 0.25
PAD_X, PAD_Y = 9.0, 6.0
ELL_PAD_X, ELL_PAD_Y = 11.0, 6.5
KEY_MARGIN = 1.5          # 主键下划线与文字底边的距离。旧值 4.0 时下划线落在
                          # cy+th/2+4，而椭圆下沿在 cy+th/2+ELL_PAD_Y(=6.5)，
                          # 两者只差 2.5pt，下划线与椭圆弧视觉上糊在一起看不出来。

# 每张实体图 = (键, 题注, [(属性名, 是否主键), ...])
# 题注不含编号前缀：文档里题注由编号 + 文字两部分组成，
# 整段替换会把域拆掉，故 A1 段只写表名部分。
ENTITIES = [
    ("user", "用户实体图（sys_user）", [
        ("用户ID", True), ("用户名", False), ("密码", False), ("姓名", False),
        ("手机号", False), ("状态", False), ("角色", False),
        ("封禁到期时间", False), ("封禁原因", False), ("创建时间", False),
    ]),
    ("activity", "活动实体图（activity）", [
        ("活动ID", True), ("标题", False), ("描述", False), ("地点", False),
        ("开始时间", False), ("结束时间", False), ("抢票开始时间", False),
        ("抢票结束时间", False), ("总库存", False), ("剩余库存", False),
        ("状态", False), ("版本号", False), ("组织者ID", False), ("创建时间", False),
    ]),
    ("ticket_type", "票种实体图（ticket）", [
        ("票种ID", True), ("活动ID", False), ("票种名称", False),
        ("总库存", False), ("剩余库存", False), ("版本号", False), ("创建时间", False),
    ]),
    ("ticket_order", "订单实体图（ticket_order）", [
        ("订单ID", True), ("用户ID", False), ("活动ID", False),
        ("票种名称", False), ("下单时间", False),
    ]),
    ("eticket", "电子票实体图（eticket）", [
        ("电子票ID", True), ("票号", False), ("二维码内容", False), ("订单ID", False),
        ("用户ID", False), ("活动ID", False), ("票种名称", False), ("状态", False),
        ("使用时间", False), ("创建时间", False),
    ]),
    ("checkin", "核销记录实体图（checkin_record）", [
        ("记录ID", True), ("电子票ID", False), ("票号", False), ("活动ID", False),
        ("用户ID", False), ("票种名称", False), ("核销员ID", False), ("核销时间", False),
    ]),
    ("comment", "评论实体图（activity_comment）", [
        ("评论ID", True), ("活动ID", False), ("用户ID", False), ("用户名", False),
        ("父评论ID", False), ("内容", False), ("情感值", False), ("情感标签", False),
        ("创建时间", False),
    ]),
    ("grab_log", "抢票日志实体图（grab_log）", [
        ("日志ID", True), ("用户ID", False), ("用户名", False), ("活动ID", False),
        ("IP", False), ("User-Agent", False), ("结果", False), ("创建时间", False),
    ]),
]


class Measurer:
    def __init__(self) -> None:
        self.fig = plt.figure(figsize=(2, 2), dpi=72)
        self.renderer = self.fig.canvas.get_renderer()

    def size(self, text: str, fs: float, fp: FontProperties):
        t = self.fig.text(0, 0, text, fontproperties=fp, fontsize=fs)
        bb = t.get_window_extent(renderer=self.renderer)
        t.remove()
        return float(bb.width), float(bb.height)


def build_one(key, title, attrs, fp, m: Measurer):
    """从大到小搜索字号，返回 (fig, fs, w_pt, h_pt) 或 None。"""
    for fs in [FS_MAX - i * FS_STEP for i in range(int((FS_MAX - FS_MIN) / FS_STEP) + 1)]:
        ent_w, ent_h = m.size(title.split("  ")[-1], fs * 1.15, fp)
        ent_w += 2 * PAD_X
        ent_h += 2 * PAD_Y

        # 属性椭圆尺寸
        sizes = []
        for name, is_key in attrs:
            tw, th = m.size(name, fs, fp)
            sizes.append((tw + 2 * ELL_PAD_X, th + 2 * ELL_PAD_Y, tw, th, is_key))

        n = len(attrs)
        # 左列取 ceil(n/2) 个、右列从 ceil(n/2) 开始，两列不相交。
        # 旧写法 right = attrs[n//2 if n%2 else n//2:]，n 为奇数时 n//2 == (n-1)/2，
        # 正好等于左列最后一个下标，于是属性个数为 7 的三张实体图
        # （票种/订单/核销记录）各有一个属性被同时画在左右两列。
        cut = (n + 1) // 2
        left = attrs[:cut]
        right = attrs[cut:]

        # 每列宽度
        def col_w(sub):
            idx = [attrs.index(a) for a in sub]
            return max(sizes[i][0] for i in idx) if idx else 0.0

        wl, wr = col_w(left), col_w(right)
        gap_x = 46.0
        total_w = wl + gap_x + ent_w + gap_x + wr
        if total_w > W - 2 * 8.0:
            continue

        # 每列的行距 = 该列最大椭圆高 + 行间隙
        def col_layout(sub, cx):
            idx = [attrs.index(a) for a in sub]
            if not idx:
                return [], 0.0
            hmax = max(sizes[i][1] for i in idx)
            vgap = 8.0
            y = 0.0
            out = []
            for i in idx:
                out.append((cx, y + sizes[i][1] / 2.0, i))
                y += hmax + vgap
            return out, y - vgap

        left_cx = 8.0 + wl / 2.0
        right_cx = W - 8.0 - wr / 2.0
        L, hl = col_layout(left, left_cx)
        R, hr = col_layout(right, right_cx)

        # 纵向留白按「内容真实跨度 + 上下等距 PAD_V」反推，不能用 ent_h*0.35 这类
        # 启发式：旧写法 body_h = max(hl,hr) + ent_h*0.35，而 y_off =
        # (body_h - max(hl,hr))/2 = ent_h*0.175，两者叠加会把最上面一个椭圆的
        # 顶边推到坐标 4.4~5.1pt，而轴上限是 8pt —— 8 张图顶部都被裁掉约 3pt
        # （实体框、连线与椭圆上沿一起被切）。
        # col_layout 让每个椭圆中心 = 累计 y + 自身高度/2，因此第 1 个椭圆
        # 的**顶边为 0**、底边为自身高度；最后一个椭圆的底边为
        # max(hl,hr) - hmax/2 + sizes[last][1]。
        first_h = sizes[[attrs.index(a) for a in (left or right)][0]][1]
        last_i = [attrs.index(a) for a in (left or right)][-1]
        content_top = 0.0
        content_bot = max(hl, hr) - max(sizes[i][1] for i in
                                        [attrs.index(a) for a in (left or right)]) / 2.0 \
            + sizes[last_i][1] / 2.0 + sizes[last_i][1] / 2.0
        PAD_V = 8.0
        body_h = (content_bot - content_top) + 2 * PAD_V
        y_off = PAD_V - content_top          # 让最上椭圆顶边正好落在 PAD_V
        ent_cy = body_h / 2.0
        L = [(x, y + y_off, i) for x, y, i in L]
        R = [(x, y + y_off, i) for x, y, i in R]

        h_pt = body_h + 2 * PAD_V
        if h_pt > MAX_H_IN * PT:
            continue
        return (fs, ent_w, ent_h, ent_cy, L, R, body_h, wl, wr,
                [attrs.index(a) for a in left])
    return None


def render(key, title, attrs, fp, m, spec):
    fs, ent_w, ent_h, ent_cy, L, R, body_h, wl, wr, left_col = spec
    h_pt = body_h + 2 * 8.0
    fig = plt.figure(figsize=(W / PT, h_pt / PT), dpi=DPI)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, W)
    # 轴范围必须与 h_pt 一致：数据 y 从 0 到 h_pt，画布高 h_pt。
    # 旧写法 set_ylim(body_h + 8, 8) 只覆盖 body_h 高度而画布是 body_h+16，
    # 等于把内容纵向拉伸 1.09 倍并让最上沿越过轴上限被裁掉。
    ax.set_ylim(h_pt, 0.0)
    ax.axis("off")

    # 实体矩形
    ex0, ey0 = W / 2.0 - ent_w / 2.0, ent_cy - ent_h / 2.0
    ax.add_patch(Rectangle((ex0, ey0), ent_w, ent_h, facecolor="white",
                           edgecolor="black", linewidth=1.8, zorder=3))
    ax.text(W / 2.0, ent_cy, title.split("  ")[-1], fontproperties=fp, fontsize=fs * 1.15,
            ha="center", va="center", zorder=4)
    # 注：实体框与标题在函数末尾还会以更高 zorder 再画一次（遮挡控制），此处保留
    # 只是为了在连线之前先占位，成本可忽略。
    for row, (cx, cy, i) in enumerate(L + R):
        name, is_key = attrs[i]
        ew, eh, tw, th, _k = (lambda t: (t[0], t[1], t[2], t[3], t[4]))(
            (lambda n2, k2: (
                m.size(n2, fs, fp)[0] + 2 * ELL_PAD_X,
                m.size(n2, fs, fp)[1] + 2 * ELL_PAD_Y,
                m.size(n2, fs, fp)[0], m.size(n2, fs, fp)[1], k2))(name, is_key))
        ax.add_patch(Ellipse((cx, cy), ew, eh, facecolor="white", edgecolor="black",
                             linewidth=1.2, zorder=3))
        ax.text(cx, cy, name, fontproperties=fp, fontsize=fs, ha="center", va="center",
                zorder=4)
        if is_key:
            ax.plot([cx - tw / 2.0, cx + tw / 2.0],
                    [cy + th / 2.0 + KEY_MARGIN, cy + th / 2.0 + KEY_MARGIN],
                    color="black", linewidth=1.0, zorder=5)

        # 连线：从椭圆朝向实体框的端点出发，连到实体框竖边上**与其同高**的点。
        #
        # 为什么不做"扇面展开"：早先的写法把同一侧所有连线的终点都固定在竖边
        # 中点，结果 7 条线在框边糊成一束；改成沿竖边等距展开后，虽然不再重叠，
        # 但同一侧行数多于 3 时，靠下的椭圆要把线拉到上面的槽、靠上的椭圆拉到
        # 下面的槽，**相邻连线互相穿越**（checkin 图 4 行时肉眼可见左侧交叉成 X）。
        # 根因是扇面高度 span = ent_h*0.86 与每行间距无关：行距 = hmax+8，
        # 两侧行数不同时两者不相等，槽位与行位必然错开。
        #
        # 正确做法是让终点 y **等于起点 y**：竖边上每条线落点与自身椭圆同高，
        # 连线在竖直方向严格单调、绝不相交，且终点必在竖边上（不会伸出框外，
        # 因此框重绘后能干净地压在连线之上）。竖边可用高度只有 ent_h，故先把
        # 起点的 y 夹到 [ent_cy-ent_h/2+PAD, ent_cy+ent_h/2-PAD]，避免线落到框角。
        side_margin = 4.0
        ty = min(max(cy, ent_cy - ent_h / 2.0 + side_margin),
                 ent_cy + ent_h / 2.0 - side_margin)
        if cx < W / 2.0:
            ax.add_patch(FancyArrowPatch(
                (cx + ew / 2.0, cy), (ex0, ty), arrowstyle="-", color="black",
                linewidth=0.9, shrinkA=0.0, shrinkB=0.0, zorder=2,
                connectionstyle="arc3,rad=0.0"))
        else:
            ax.add_patch(FancyArrowPatch(
                (cx - ew / 2.0, cy), (ex0 + ent_w, ty), arrowstyle="-", color="black",
                linewidth=0.9, shrinkA=0.0, shrinkB=0.0, zorder=2,
                connectionstyle="arc3,rad=0.0"))
    # 遮挡：连线（zorder=2）必须在椭圆（zorder=3）与实体框（zorder=8）之下。
    # 旧代码把实体框的 zorder 设为 3、与椭圆同层，而添加顺序又排在所有椭圆与
    # 连线之前，于是后画的连线直接压在活动实体框的边框上、把它盖住 —— 视觉上
    # 就是"线条被挡住/边框断成两截"。这里把实体框与标题抽到最后重画一次并置于
    # 最高层，保证任何连线都不会压到框与椭圆之上。
    ax.add_patch(Rectangle((ex0, ey0), ent_w, ent_h, facecolor="white",
                           edgecolor="black", linewidth=1.8, zorder=8))
    ax.text(W / 2.0, ent_cy, title.split("  ")[-1], fontproperties=fp, fontsize=fs * 1.15,
            ha="center", va="center", zorder=9)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = CODE_DIR / f"fig04_er_{key}.png"
    fig.savefig(out, dpi=DPI, facecolor="white")
    plt.close(fig)
    return out, fs, h_pt


def main() -> int:
    CODE_DIR.mkdir(parents=True, exist_ok=True)
    fp = FontProperties(fname=FONT_PATH)
    m = Measurer()
    manifest = []
    for key, title, attrs in ENTITIES:
        spec = build_one(key, title, attrs, fp, m)
        if spec is None:
            print(f"[FAIL] {key} 无可用字号档位")
            return 1
        out, fs, h_pt = render(key, title, attrs, fp, m, spec)
        px_w = int(round(W / PT * DPI))
        px_h = int(round(h_pt / PT * DPI))
        print(f"{key:<12} fs={fs:.2f}pt  {px_w}x{px_h}  "
              f"插 {WIDTH_IN:.2f}x{h_pt/PT:.2f}in  {out.stat().st_size} B")
        manifest.append({
            "key": key, "title": title, "path": str(out), "fs": fs,
            "insert_in": WIDTH_IN, "insert_h_in": round(h_pt / PT, 3),
        })
    (CODE_DIR / "_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"共 {len(manifest)} 张实体图")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
