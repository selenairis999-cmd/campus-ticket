# -*- coding: utf-8 -*-
"""软著源代码 PDF 的自动验收脚本。
逐页检查：页数、每页代码行数、页眉完整性、中文是否退化成 ·、是否越界。
用法: python tools/softcopyright/verify_source_pdf.py
"""
import os
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

import fitz

PDF = "docs/softcopyright/校园票务与智能分析系统_源代码.pdf"
EXPECT_PAGES = 60
EXPECT_LINES = 50
CODE_TOP = 60.0
CODE_BOTTOM = 790.0
MARGIN = 45.0


def main():
    if not os.path.isfile(PDF):
        print("找不到 PDF：%s" % PDF)
        return 1
    doc = fitz.open(PDF)
    issues = []
    trunc = 0
    for pno in range(doc.page_count):
        pg = doc[pno]
        txt = pg.get_text()
        if "·" in txt:
            issues.append("第%d页 中文退化成 ·" % (pno + 1))
        if "校园票务与智能分析系统" not in txt:
            issues.append("第%d页 页眉缺软件名" % (pno + 1))
        if ("共 %d 页" % EXPECT_PAGES) not in txt:
            issues.append("第%d页 页眉缺页码" % (pno + 1))
        trunc += txt.count("...")

        # 用 dict 模式逐行统计，blocks 模式会把整页合成一个块
        lines = []
        for blk in pg.get_text("dict")["blocks"]:
            if blk.get("type") != 0:
                continue
            for ln in blk["lines"]:
                lines.append((ln["bbox"][1], ln["bbox"][0], ln["bbox"][2]))
        code = [l for l in lines if CODE_TOP < l[0] < CODE_BOTTOM]
        if len(code) != EXPECT_LINES:
            issues.append("第%d页 代码行数 = %d（应为 %d）" % (pno + 1, len(code), EXPECT_LINES))
        W = pg.rect.width
        for y, x0, x1 in lines:
            if x0 < MARGIN or x1 > W - MARGIN:
                issues.append("第%d页 越界 x=%.0f..%.0f" % (pno + 1, x0, x1))
                break
    n = doc.page_count
    doc.close()

    print("=" * 52)
    print("软著源代码 PDF 验收报告")
    print("=" * 52)
    print("文件        : %s" % PDF)
    print("大小        : %d B" % os.path.getsize(PDF))
    print("页数        : %d（要求 %d）%s" % (n, EXPECT_PAGES, "OK" if n == EXPECT_PAGES else "✗"))
    print("每页代码行  : %d 行/页" % EXPECT_LINES)
    print("长行截断    : %d 处" % trunc)
    print("-" * 52)
    if issues:
        print("发现问题 %d 处：" % len(issues))
        for i in issues[:20]:
            print("  ✗ %s" % i)
        if len(issues) > 20:
            print("  …… 其余 %d 处略" % (len(issues) - 20))
        print("-" * 52)
        print("结论：需修复后重新提交")
        return 1
    print("✓ 页数正确")
    print("✓ 每页恰好 %d 行代码" % EXPECT_LINES)
    print("✓ 页眉软件名/页码完整")
    print("✓ 中文无乱码（未出现替代方块）")
    print("✓ 无水平越界")
    print("-" * 52)
    print("结论：符合软著登记要求，可直接提交")
    return 0


if __name__ == "__main__":
    sys.exit(main())
