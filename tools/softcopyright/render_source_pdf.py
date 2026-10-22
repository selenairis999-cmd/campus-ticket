# -*- coding: utf-8 -*-
"""把分页源码文本渲染成软著登记用 PDF（每页 50 行 + 页眉页脚）。
用法: python tools/softcopyright/render_source_pdf.py

踩坑记录（重要）：
- `doc.insert_font()` 在 PyMuPDF 1.27 已不存在（Document 无此方法），
  早期版本靠它在文档级注册字体，之后每页 insert_text 引用。
- `page.insert_font()` + `page.insert_text()` 是可行的，但**只在该页有效**，
  其它页的中文会退化成 `·`。
- 可靠做法：`fitz.Font(fontfile=...)` 建字体对象 + `fitz.TextWriter` 写入。
  TextWriter 每页新建，显式携带 font 对象，中文稳定不退化。
"""
import os
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

import fitz  # PyMuPDF

PAGES_DIR = "docs/softcopyright/pages"
OUT_PDF = "docs/softcopyright/校园票务与智能分析系统_源代码.pdf"

SOFT_NAME = "校园票务与智能分析系统"
VERSION = "V1.0"

PAGE_W = 595.0  # A4 宽 pt
PAGE_H = 842.0
MARGIN_L = 50.0
MARGIN_R = 50.0
MARGIN_T = 72.0
FONT_SIZE = 8.0     # 从 9.0 降到 8.0，容纳长行 Java 代码
LINE_H = 12.0       # 相应压缩行距
# 8.0pt 宋体下，一行的最大可容纳字符数（实测安全值）
MAX_COLS = 105

HEADER_TOP = 34.0
FOOTER_Y = PAGE_H - 32.0

# 按优先级选择中文字体
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


def main():
    files = sorted(f for f in os.listdir(PAGES_DIR) if f.endswith(".txt"))
    if not files:
        print("没有分页文件，请先运行 make_source_pages.py")
        return
    print("分页文件: %d 个" % len(files))

    font = load_cjk_font()
    if font is None:
        print("未找到中文字体，无法生成")
        return

    doc = fitz.open()
    total = len(files)
    for i, fn in enumerate(files, 1):
        with open(os.path.join(PAGES_DIR, fn), encoding="utf-8") as fh:
            lines = fh.read().split("\n")
        page = doc.new_page(width=PAGE_W, height=PAGE_H)
        tw = fitz.TextWriter(page.rect)

        # 页眉：左=软件名与版本，右=第 X 页 共 Y 页
        tw.append((MARGIN_L, HEADER_TOP), "%s %s" % (SOFT_NAME, VERSION),
                  font=font, fontsize=8)
        tw.append((PAGE_W - MARGIN_R - 92, HEADER_TOP),
                  "第 %d 页  共 %d 页" % (i, total),
                  font=font, fontsize=8)
        # 页眉分隔线
        page.draw_line((MARGIN_L, HEADER_TOP + 8), (PAGE_W - MARGIN_R, HEADER_TOP + 8),
                       color=(0.6, 0.6, 0.6), width=0.5)

        y = MARGIN_T
        for ln in lines:
            # 超长行做视觉截断，防止溢出右边界
            if len(ln) > MAX_COLS:
                ln = ln[:MAX_COLS - 3] + "..."
            tw.append((MARGIN_L, y), ln, font=font, fontsize=FONT_SIZE)
            y += LINE_H

        tw.append((MARGIN_L, FOOTER_Y), "源代码（每页 50 行，本页为第 %d 页）" % i,
                  font=font, fontsize=7.5)

        tw.write_text(page)

    os.makedirs(os.path.dirname(OUT_PDF), exist_ok=True)
    # 字体子集化：只保留实际用到的字形，避免整颗中文字体嵌入导致文件过大
    try:
        doc.subset_fonts(fallback=False)
    except Exception as e:
        print("字体子集化失败(忽略):", e)
    doc.save(OUT_PDF, deflate=True, garbage=4, clean=True)
    doc.close()
    print("已生成: %s" % OUT_PDF)
    d = fitz.open(OUT_PDF)
    print("页数: %d  大小: %d B" % (d.page_count, os.path.getsize(OUT_PDF)))
    d.close()


if __name__ == "__main__":
    main()
