# -*- coding: utf-8 -*-
"""把软著用户手册（Markdown）渲染成登记用 PDF。
用法: python tools/softcopyright/render_manual_pdf.py

渲染规则：
- 页眉：软件名 V1.0 + 页码；页脚：用户操作说明书
- 一级标题(#)新起一页；二级(##)段前留白；三级(###)加粗；四级(####)缩进加粗
- 支持 **加粗**、`行内代码`、表格（自动换行）、无序/有序列表、引用、分隔线、代码块
- 支持 ![alt](path) 图片嵌入（自动缩放适配页面宽度）
- 9pt 宋体 + TextWriter（稳定中文方案）
"""
import os
import re
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

import fitz

SRC_MD = "docs/softcopyright/用户手册.md"
OUT_PDF = "docs/softcopyright/校园票务与智能分析系统-用户手册.pdf"

SOFT_NAME = "校园票务与智能分析系统"
VERSION = "V1.0"

PAGE_W = 595.0
PAGE_H = 842.0
MARGIN_L = 56.0
MARGIN_R = 56.0
TOP_LIMIT = 64.0      # 正文起始 y
BOTTOM_LIMIT = 790.0  # 正文下界（留更多底部空间）

FONT_SIZE = 9.0
LINE_H = 15.0         # 增大行距避免重叠
H1_SIZE = 16.0
H2_SIZE = 13.0
H3_SIZE = 11.0
H4_SIZE = 10.0

HEADER_TOP = 34.0
FOOTER_Y = PAGE_H - 30.0

CONTENT_WIDTH = PAGE_W - MARGIN_L - MARGIN_R  # 可用内容宽度

FONT_CANDIDATES = [
    "C:/Windows/Fonts/simsun.ttc",
    "C:/Windows/Fonts/msyh.ttc",
    "C:/Windows/Fonts/simhei.ttf",
]


def load_cjk_font():
    for p in FONT_CANDIDATES:
        if os.path.isfile(p):
            try:
                return fitz.Font(fontfile=p)
            except Exception:
                continue
    return None


# ---------------------------------------------------------------- 行内标记
BOLD_RE = re.compile(r"\*\*(.+?)\*\*")
CODE_RE = re.compile(r"`([^`]+)`")
IMG_RE = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)")


def strip_inline(text):
    """去掉 markdown 行内标记，返回纯文本（用于宽度计算）。"""
    t = BOLD_RE.sub(r"\1", text)
    t = CODE_RE.sub(r"\1", t)
    t = IMG_RE.sub("", t)
    return t


def emit_runs(tw, x, y, text, font, fontsize, bold_font=None):
    """按 **加粗** 与 `代码` 切分写入，逐段推进 x 坐标。"""
    cur_x = x
    pos = 0
    for m in re.finditer(r"(\*\*.+?\*\*|`[^`]+`)", text):
        if m.start() > pos:
            seg = text[pos:m.start()]
            tw.append((cur_x, y), seg, font=font, fontsize=fontsize)
            cur_x += text_width(font, seg, fontsize)
        seg = m.group(0)
        if seg.startswith("**"):
            seg = seg[2:-2]
            use_font = bold_font or font
            tw.append((cur_x, y), seg, font=use_font, fontsize=fontsize)
            cur_x += text_width(use_font, seg, fontsize)
        else:
            seg = seg[1:-1]
            tw.append((cur_x, y), seg, font=font, fontsize=fontsize)
            cur_x += text_width(font, seg, fontsize)
        pos = m.end()
    if pos < len(text):
        seg = text[pos:]
        tw.append((cur_x, y), seg, font=font, fontsize=fontsize)


def text_width(font, text, fontsize):
    try:
        return font.text_length(text, fontsize=fontsize)
    except Exception:
        return len(text) * fontsize * 0.5


class Renderer:
    def __init__(self, doc, font, bold_font=None):
        self.doc = doc
        self.font = font
        self.bold_font = bold_font or font
        self.page = None
        self.tw = None
        self.y = 0.0
        self.pageno = 0
        self.in_code = False

    def new_page(self):
        self.page = self.doc.new_page(width=PAGE_W, height=PAGE_H)
        self.tw = fitz.TextWriter(self.page.rect)
        self.pageno += 1
        self.y = TOP_LIMIT
        # 页眉
        self.tw.append((MARGIN_L, HEADER_TOP), "%s %s" % (SOFT_NAME, VERSION),
                       font=self.font, fontsize=8)
        hdr_right = "第 %d 页" % self.pageno
        hdr_w = text_width(self.font, hdr_right, 8)
        self.tw.append((PAGE_W - MARGIN_R - hdr_w, HEADER_TOP),
                       hdr_right, font=self.font, fontsize=8)
        self.page.draw_line((MARGIN_L, HEADER_TOP + 7),
                            (PAGE_W - MARGIN_R, HEADER_TOP + 7),
                            color=(0.6, 0.6, 0.6), width=0.5)
        # 页脚
        self.tw.append((MARGIN_L, FOOTER_Y), "用户操作说明书",
                       font=self.font, fontsize=7.5)

    def flush(self):
        if self.tw is not None:
            self.tw.write_text(self.page)

    def ensure_space(self, h):
        """确保当前页有 h 像素的剩余空间，不够则翻页。"""
        if self.y + h > BOTTOM_LIMIT:
            self.flush()
            self.new_page()
            return True
        return False

    def space(self, h):
        if self.y + h > BOTTOM_LIMIT:
            self.flush()
            self.new_page()
        else:
            self.y += h

    def wrap_lines(self, text, fontsize, indent, max_width=None):
        """按可用宽度折行，返回 [(indent, line), ...]"""
        avail = (max_width or CONTENT_WIDTH) - indent
        out, cur = [], ""
        for ch in text:
            if ch == "\t":
                ch = "    "
            test = cur + ch
            if text_width(self.font, test, fontsize) > avail and cur:
                out.append((indent, cur))
                cur = ch
            else:
                cur = test
        if cur:
            out.append((indent, cur))
        return out or [(indent, "")]

    def para(self, text, fontsize=FONT_SIZE, indent=0.0, gap=4.0, bold=False):
        for ind, line in self.wrap_lines(text, fontsize, indent):
            self.ensure_space(LINE_H)
            use_font = self.bold_font if bold else self.font
            emit_runs(self.tw, MARGIN_L + ind, self.y, line,
                      self.font, fontsize, self.bold_font)
            self.y += LINE_H if fontsize <= 10 else fontsize + 5
        self.space(gap)

    @staticmethod
    def _compressed_copy(img_path, max_px=1200, quality=75):
        """把大图压成 JPEG 缓存副本，显著减小 PDF 体积（上传更稳）。"""
        cache_dir = os.path.normpath(
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".dsh-tmp-docx", "imgcache")
        )
        os.makedirs(cache_dir, exist_ok=True)
        out = os.path.join(
            cache_dir,
            "%s.%dq%d.jpg" % (os.path.splitext(os.path.basename(img_path))[0], max_px, quality),
        )
        if os.path.isfile(out) and os.path.getmtime(out) >= os.path.getmtime(img_path):
            return out
        from PIL import Image
        with Image.open(img_path) as im:
            im = im.convert("RGB")
            w, h = im.size
            if w > max_px:
                im = im.resize((max_px, int(round(h * max_px / w))), Image.LANCZOS)
            im.save(out, "JPEG", quality=quality, optimize=True)
        return out

    def insert_image(self, img_path, caption="", max_w=None, max_h=400.0):
        """插入图片，自动缩放适配页面宽度。"""
        # 解析相对路径
        if not os.path.isabs(img_path):
            img_path = os.path.join(os.path.dirname(SRC_MD), "..", "..", img_path)
            img_path = os.path.normpath(img_path)

        if not os.path.isfile(img_path):
            self.para("[图片未找到: %s]" % img_path, fontsize=8, gap=2)
            return

        try:
            img_path = self._compressed_copy(img_path)
        except Exception:
            pass  # 压缩失败时回退用原图

        try:
            img_doc = fitz.open(img_path)
            img_page = img_doc[0]
            img_w = img_page.rect.width
            img_h = img_page.rect.height
            img_doc.close()
        except Exception:
            # 尝试用 PIL 获取尺寸
            try:
                from PIL import Image
                with Image.open(img_path) as im:
                    img_w, img_h = im.size
            except Exception:
                self.para("[图片无法读取: %s]" % img_path, fontsize=8, gap=2)
                return

        avail_w = max_w or CONTENT_WIDTH
        scale = min(avail_w / img_w, max_h / img_h, 1.0)
        draw_w = img_w * scale
        draw_h = img_h * scale

        # 确保有足够空间
        total_h = draw_h + (18 if caption else 6)
        self.ensure_space(total_h)

        # 居中放置
        x0 = MARGIN_L + (avail_w - draw_w) / 2
        rect = fitz.Rect(x0, self.y, x0 + draw_w, self.y + draw_h)
        self.page.insert_image(rect, filename=img_path)
        self.y += draw_h + 4

        # 图注
        if caption:
            cap_w = text_width(self.font, caption, 8)
            cap_x = MARGIN_L + (CONTENT_WIDTH - cap_w) / 2
            self.ensure_space(14)
            self.tw.append((cap_x, self.y), caption, font=self.font, fontsize=8)
            self.y += 14

        self.space(6)

    def table(self, rows):
        """渲染表格：满宽自适应列宽、单元格内换行、完整网格线、表头底纹、跨页重复表头。"""
        if not rows:
            return
        cols = max(len(r) for r in rows)
        fs = FONT_SIZE - 0.5   # 表格字号略小
        cell_pad = 5.0         # 单元格单侧水平 padding
        vert_pad = 4.0         # 单元格单侧垂直 padding
        line_h = LINE_H        # 单元格内行高

        cells = [[strip_inline(row[ci]) if ci < len(row) else ""
                  for ci in range(cols)] for row in rows]

        # 每列不可断词的最大宽度（列宽下限）
        min_content = [0.0] * cols
        for ci in range(cols):
            for row in cells:
                for word in re.split(r"[,\s]+", row[ci]):
                    if word:
                        min_content[ci] = max(
                            min_content[ci], text_width(self.font, word, fs))

        # 每列单行理想宽度
        ideal = [0.0] * cols
        for row in cells:
            for ci in range(cols):
                ideal[ci] = max(ideal[ci], text_width(self.font, row[ci], fs))

        avail = CONTENT_WIDTH - cols * 2 * cell_pad
        total = sum(ideal)
        if total <= 1:
            widths = [avail / cols] * cols
        elif total <= avail:
            # 内容不足一页宽：按比例拉伸铺满，表格更美观
            widths = [w * avail / total for w in ideal]
        else:
            # 超宽：先等比压缩，再按不可断词下限做迭代回收
            scale = avail / total
            widths = [max(w * scale, m) for w, m in zip(ideal, min_content)]
            for _ in range(10):
                over = sum(widths) - avail
                if over <= 0.5:
                    break
                extras = [max(w - m, 0.0) for w, m in zip(widths, min_content)]
                pool = sum(extras)
                if pool <= 0.5:
                    break
                widths = [w - over * e / pool if e > 0 else w
                          for w, e in zip(widths, extras)]
        # 下限兜底（极端情况整体再缩）
        widths = [max(w, m) for w, m in zip(widths, min_content)]
        if sum(widths) > avail:
            s = avail / sum(widths)
            widths = [w * s for w in widths]

        box_w = [w + 2 * cell_pad for w in widths]   # 每列格子总宽
        table_w = sum(box_w)
        x_end = MARGIN_L + table_w

        # 预计算每行布局
        layouts = []
        for row in cells:
            cell_lines = []
            max_lines = 1
            for ci in range(cols):
                lines = self.wrap_lines(row[ci], fs, 0, max_width=widths[ci])
                cell_lines.append([t for _, t in lines])
                max_lines = max(max_lines, len(lines))
            row_h = max_lines * line_h + 2 * vert_pad
            layouts.append((cell_lines, max_lines, row_h))

        def draw_row(ri):
            cell_lines, max_lines, row_h = layouts[ri]
            y0 = self.y
            y1 = y0 + row_h
            # 底纹：表头深一点，数据行隔行浅灰
            if ri == 0:
                self.page.draw_rect(fitz.Rect(MARGIN_L, y0, x_end, y1),
                                    color=None, fill=(0.90, 0.90, 0.93))
            elif ri % 2 == 0:
                self.page.draw_rect(fitz.Rect(MARGIN_L, y0, x_end, y1),
                                    color=None, fill=(0.965, 0.965, 0.975))
            # 横线（顶+底）
            self.page.draw_line((MARGIN_L, y0), (x_end, y0),
                                color=(0.55, 0.55, 0.55), width=0.6)
            self.page.draw_line((MARGIN_L, y1), (x_end, y1),
                                color=(0.55, 0.55, 0.55), width=0.6)
            # 竖线
            cx = MARGIN_L
            for ci in range(cols + 1):
                self.page.draw_line((cx, y0), (cx, y1),
                                    color=(0.68, 0.68, 0.68), width=0.4)
                if ci < cols:
                    cx += box_w[ci]
            # 文本
            cx = MARGIN_L
            for ci in range(cols):
                for li, lt in enumerate(cell_lines[ci]):
                    ly = y0 + vert_pad + li * line_h + fs * 0.85
                    self.tw.append((cx + cell_pad, ly), lt,
                                   font=self.font, fontsize=fs)
                cx += box_w[ci]
            self.y = y1

        for ri in range(len(layouts)):
            row_h = layouts[ri][2]
            if self.y + row_h > BOTTOM_LIMIT:
                self.flush()
                self.new_page()
                if ri > 0:
                    draw_row(0)  # 跨页重复表头
            draw_row(ri)

        self.space(8)


def main():
    if not os.path.isfile(SRC_MD):
        print("找不到 %s" % SRC_MD)
        return
    font = load_cjk_font()
    if font is None:
        print("未找到中文字体")
        return

    # 尝试加载粗体字体
    bold_font = None
    bold_candidates = [
        "C:/Windows/Fonts/simhei.ttf",
        "C:/Windows/Fonts/msyhbd.ttc",
    ]
    for p in bold_candidates:
        if os.path.isfile(p):
            try:
                bold_font = fitz.Font(fontfile=p)
                break
            except Exception:
                continue

    doc = fitz.open()
    r = Renderer(doc, font, bold_font)
    r.pending_title = True

    with open(SRC_MD, encoding="utf-8") as fh:
        md_lines = fh.read().split("\n")

    i = 0
    while i < len(md_lines):
        line = md_lines[i].rstrip()
        s = line.strip()

        # 代码块
        if s.startswith("```"):
            r.in_code = not r.in_code
            i += 1
            continue
        if r.in_code:
            r.para("    " + s, fontsize=FONT_SIZE - 0.5, gap=0.0)
            i += 1
            continue

        if not s:
            r.space(3)
            i += 1
            continue

        # 图片 ![](path)
        img_m = IMG_RE.match(s)
        if img_m:
            alt = img_m.group(1)
            path = img_m.group(2)
            r.insert_image(path, caption=alt)
            i += 1
            continue

        # 表格
        if s.startswith("|") and s.endswith("|"):
            rows = []
            while i < len(md_lines) and md_lines[i].strip().startswith("|"):
                cells = [c.strip() for c in md_lines[i].strip().strip("|").split("|")]
                if not all(set(c) <= set("-: ") and c for c in cells):
                    rows.append(cells)
                i += 1
            if rows:
                r.table(rows)
            continue

        if s.startswith("---"):
            r.space(6)
            r.page.draw_line((MARGIN_L, r.y), (PAGE_W - MARGIN_R, r.y),
                             color=(0.7, 0.7, 0.7), width=0.6)
            r.space(10)
            i += 1
            continue

        if s.startswith("# "):
            if getattr(r, "pending_title", False):
                r.pending_title = False
                r.new_page()
            else:
                r.flush()
                r.new_page()
            r.para(s[2:], fontsize=H1_SIZE, gap=10, bold=True)
        elif s.startswith("#### "):
            r.para(s[5:], fontsize=H4_SIZE, gap=3, bold=True)
        elif s.startswith("### "):
            r.para(s[4:], fontsize=H3_SIZE, gap=3, bold=True)
        elif s.startswith("## "):
            r.space(6)
            r.para(s[3:], fontsize=H2_SIZE, gap=6, bold=True)
        elif s.startswith(">"):
            r.para(s.lstrip("> "), fontsize=FONT_SIZE - 0.5, indent=6, gap=4)
        elif re.match(r"^\s*[-*]\s+", line):
            body = re.sub(r"^\s*[-*]\s+", "", line)
            r.para("• " + strip_inline(body), indent=8, gap=2)
        elif re.match(r"^\s*\d+[.)]\s+", line):
            m_num = re.match(r"^\s*(\d+[.)])\s+", line)
            num = m_num.group(1) if m_num else ""
            body = re.sub(r"^\s*\d+[.)]\s+", "", line)
            r.para(num + " " + strip_inline(body), indent=10, gap=2)
        else:
            # 清理残留的 markdown 标记
            clean = strip_inline(s)
            r.para(clean, gap=4)
        i += 1

    r.flush()
    os.makedirs(os.path.dirname(OUT_PDF), exist_ok=True)
    # 字体子集化：只保留实际用到的字形，避免整颗 18MB 中文字体嵌入
    try:
        doc.subset_fonts(fallback=False)
    except Exception as e:
        print("字体子集化失败(忽略):", e)
    doc.save(OUT_PDF, deflate=True, garbage=4, clean=True)
    doc.close()
    d = fitz.open(OUT_PDF)
    print("已生成: %s" % OUT_PDF)
    print("页数: %d  大小: %d B" % (d.page_count, os.path.getsize(OUT_PDF)))
    bad = [p + 1 for p in range(d.page_count) if "·" in d[p].get_text()]
    print("替代方块页: %s" % (bad if bad else "无"))
    d.close()


if __name__ == "__main__":
    main()
