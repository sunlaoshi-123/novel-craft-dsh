#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""结构层核账：边数、容量、格位、占比。文笔层另用 check_text.py。

用法（全部中文参数）：
    python check_structure.py 边数 核心人数 扩展人数 扩展内部边数
    python check_structure.py 容量 台阶数 每台阶案数 每案章数 单章字数 目标字数
    python check_structure.py 格位 格位表.md
    python check_structure.py 占比 总边数 承重有向边数 知情格数 主表行数

判据见 references/01b-矩阵与加人.md、references/01c-格位与容量.md。
"""

import sys
import io
import os
import re
import datetime


_编码提示已打 = [False]
_体积提示已打 = [False]


def 读(path):
    """按 BOM／UTF-8／GB18030 顺序试，尽量不因为编码把文件挡在外面。
    中文 Windows 上 Word 另存与记事本「ANSI」是 GBK，记事本「Unicode」是 UTF-16。"""
    try:
        大小 = os.path.getsize(path)
        if 大小 > 8 * 1024 * 1024 and not _体积提示已打[0]:
            print("【提示】文件较大（%.1f MB）。全量扫描会慢，单章正文通常只有几百 KB；"
                  % (大小 / 1048576.0))
            print("全本合订建议按卷拆开跑，或先只跑单章。")
            _体积提示已打[0] = True
    except OSError:
        pass
    raw = io.open(path, "rb").read()
    if raw.startswith(b"\xff\xfe") or raw.startswith(b"\xfe\xff"):
        if not _编码提示已打[0]:
            print("【提示】文件不是 UTF-8，已按 UTF-16 读取（原文件未改动）")
            _编码提示已打[0] = True
        return raw.decode("utf-16")
    for enc, 名 in (("utf-8-sig", None), ("gb18030", "GB18030")):
        try:
            t = raw.decode(enc)
        except UnicodeDecodeError:
            continue
        if 名 and not _编码提示已打[0]:
            print("【提示】文件不是 UTF-8，已按 %s 读取（原文件未改动）" % 名)
            _编码提示已打[0] = True
        return t
    raise UnicodeDecodeError("utf-8", raw, 0, min(1, len(raw)), "既非 UTF-8 也非 GB18030")



def 整数(x, 名):
    try:
        v = int(x)
    except ValueError:
        print("【错误 E07】「%s」要填整数，收到：%s" % (名, x))
        print("【怎么办】参数只填数字，不要带单位或汉字；用法见本文件开头的说明。")
        raise SystemExit(2)
    if v < 0:
        print("【错误 E07】「%s」不能为负，收到：%s" % (名, x))
        print("【怎么办】改成正整数或 0。")
        raise SystemExit(2)
    return v


def 边数(c, e, x):
    a, b, d = c * (c - 1), 2 * c * e, x
    总 = a + b + d
    print("分层三段：核心内部 %d×%d＝%d 条；核心↔扩展 2×%d×%d＝%d 条；扩展内部 %d 条" % (c, c - 1, a, c, e, b, d))
    print("总边数 %d 条，折合 %d 对" % (总, 总 // 2))
    if e == 0:
        print("【提示】扩展层为空，本次是全连特例（E＝0），不是另一套规则。")
    if d % 2:
        print("【警报】扩展内部边数 %d 为奇数，成对建边要求偶数。" % d)
    if 总 % 2:
        print("【警报】总边数为奇数，无法成对，每人出入不会相等。")
    if 总 // 2 < 60:
        print("【提示】关系对数 %d ＜ 60，占比类判据不启用，只按定性规矩查。" % (总 // 2))
    else:
        print("【提示】关系对数已达 60，启用占比类判据（承重边 10—15%）。")


def 容量(台阶, 案, 章, 字, 目标):
    每台阶章 = 案 * 章
    预计 = 台阶 * 每台阶章 * 字
    print("台阶 %d × 每台阶 %d 案 × 每案 %d 章 × 单章 %d 字 ＝ %d 字" % (台阶, 案, 章, 字, 预计))
    print("目标 %d 字，达成率 %.1f%%" % (目标, 预计 / 目标 * 100 if 目标 else 0))
    if 预计 >= 目标:
        print("【结论】容量达标，可进入设计收口。")
        return
    差 = 目标 - 预计
    print("【结论】**不达标，差 %d 字，不许开写**。" % 差)
    每案字 = 章 * 字
    if 每案字:
        print("补足参考：再加 %d 个案，或每台阶多加 %d 案，或每案多写 %d 章。" % (
            (差 + 每案字 - 1) // 每案字,
            (差 + 台阶 * 每案字 - 1) // (台阶 * 每案字),
            (差 + 台阶 * 案 * 字 - 1) // (台阶 * 案 * 字)))


def _格号列(文本):
    """从表头含「格号」的表里取该列数字。技能的格位表模板就是这种写法，
    照模板填的表如果认不出来，等于模板自己不合规（2026-11 实测）。"""
    lines = 文本.split("\n")
    列 = None
    结果 = []
    for line in lines:
        s = line.strip()
        if not s.startswith("|"):
            列 = None
            continue
        cells = [c.strip() for c in s.strip("|").split("|")]
        if 列 is None:
            if "格号" in cells:
                列 = cells.index("格号")
            continue
        if len(cells) <= 列:
            continue
        v = cells[列]
        if re.fullmatch(r"\d+", v):
            结果.append(int(v))
    return 结果


def 解析日期精度(s):
    """把日期列折成一个可排序的 date，并标精度：日／旬／月／无。
    日：2023.07.08／2026-11-03／2026年11月3日，含「夜」「17:41」等日内修饰；
    旬：2026.08上／中／下 → 该月 1／11／21 日，2028.10底 → 28 日；
    月：2023.10／2026.06—08／2027.02底 → 该月 1 日；
    无：结尾／尾声／空。折算日只用于排序，不参与日差统计。"""
    t = (s or "").strip()
    if not t or re.search(r"结尾|尾声|待定|^—+$|^-$", t):
        return None, "无"
    t2 = re.sub(r"\d{1,2}:\d{2}|上午|下午|夜里|夜晚|傍晚|凌晨|夜|当晚", "", t)
    ym = re.search(r"(\d{4})\s*[-/.年]\s*(\d{1,2})", t2)
    if not ym:
        return None, "无"
    y, mo = int(ym.group(1)), int(ym.group(2))
    if not (1 <= mo <= 12):
        return None, "无"
    tail = t2[ym.end():]
    if re.search(r"上(旬|半)?", tail):
        return datetime.date(y, mo, 1), "旬"
    if re.search(r"中(旬|半)?", tail):
        return datetime.date(y, mo, 11), "旬"
    if re.search(r"下(旬|半)?", tail):
        return datetime.date(y, mo, 21), "旬"
    if re.search(r"底|末", tail):
        return datetime.date(y, mo, 28), "旬"
    d = re.search(r"[-/.月]\s*(\d{1,2})\s*日?", tail)
    if d:
        day = int(d.group(1))
        if 1 <= day <= 31:
            try:
                return datetime.date(y, mo, day), "日"
            except ValueError:
                return None, "无"
    return datetime.date(y, mo, 1), "月"


def 表格块(文本):
    """按连续竖线行切表格块：[(首行号, [(行号, cells), ...]), ...]。"""
    lines = 文本.split("\n")
    blocks, cur = [], []
    for i, line in enumerate(lines, 1):
        if line.strip().startswith("|"):
            cur.append((i, [c.strip() for c in line.strip().strip("|").split("|")]))
        else:
            if len(cur) >= 2:
                blocks.append(cur)
            cur = []
    if len(cur) >= 2:
        blocks.append(cur)
    return blocks


def 格位表块(块):
    """块是不是格位表。是则返回 (格号列号, 日期列号, 章列号或None)。"""
    head = 块[0][1]
    gi = next((i for i, c in enumerate(head) if c in ("格号", "#", "序号", "格")), None)
    di = next((i for i, c in enumerate(head)
               if any(k in c for k in ("时间", "年月日", "日期"))), None)
    if gi is None or di is None:
        return None
    ci = next((i for i, c in enumerate(head) if c == "章"), None)
    return gi, di, ci


def 主格位表(文本):
    """返回 (数据行, 格号列, 日期列, 章列, 候选表数, 主表首行)。
    一个文件里混着多张从 0 起的表时，只取数据最多的那张，其余跳过。"""
    候选 = []
    for 块 in 表格块(文本):
        info = 格位表块(块)
        if info is None:
            continue
        gi, di, ci = info
        数据 = [r for r in 块[1:]
                if not all(re.fullmatch(r":?-{2,}:?", c) for c in r[1] if c)]
        候选.append((len(数据), 块[0][0], 数据, gi, di, ci))
    if not 候选:
        return [], None, None, None, 0, None
    候选.sort(key=lambda x: (x[0], x[1]))
    n, 首行, 数据, gi, di, ci = 候选[-1]
    return 数据, gi, di, ci, len(候选), 首行

def 格位(path):
    文本 = 读(path).replace("｜", "|")
    主数据, 主gi, 主di, 主ci, 表数, 主首行 = 主格位表(文本)
    if 表数 > 1:
        print("【提示】同一文件检出 %d 张格位表，疑似多表混排；按数据最多的第 %d 行那张验。" % (表数, 主首行))
    # 主格号三种写法都认：表格「格号」列、正文「格 3」、「第 3 格」；带「后」的插入位不算主格
    # 主表里的格号列是权威，优先用；正文散落的「格 N」提及只在没有表格列时兜底。
    # 旧版按数量取舍（列格多于正文正则才用），混排文件里正文提及比表格行多，会反过来
    # 采用散落提及、报出假倒序（2026-11《这楼要塌》实测）。
    列格 = [int(r[1][主gi]) for r in 主数据
            if 主gi is not None and len(r[1]) > 主gi and re.fullmatch(r"\d+", r[1][主gi])]
    if 列格:
        主格 = 列格
        print("格号取自表格「格号」列（%d 行）。" % len(列格))
    else:
        主格 = [int(a or b) for a, b in re.findall(r"格\s*(\d+)\s*(?!后)|第\s*(\d+)\s*格", 文本)]
    带前缀 = re.findall(r"格\s*\d+\s*后\s*[一二三四五六七八九十\d]+", 文本)
    print("主格 %d 处，带前缀格 %d 处" % (len(主格), len(带前缀)))
    if not 主格:
        print("未识别到主格号。三种写法任选：表头带「格号」列并把格号写成纯数字／")
        print("写成「格 3」／写成「第 3 格」。")
        return
    去重 = []
    for n in 主格:
        if n not in 去重:
            去重.append(n)
    倒序 = [(去重[i], 去重[i + 1]) for i in range(len(去重) - 1) if 去重[i] > 去重[i + 1]]
    if 倒序:
        print("【警报】格号倒序 %s" % 倒序[:5])
    else:
        print("格号顺序：零倒序")
    缺 = list(range(min(去重), max(去重) + 1))
    if sorted(去重) != 缺:
        print("【提示】主格号有空号 %s（空号允许，重排会打断引用，不要补号）。" % [n for n in 缺 if n not in 去重][:8])
    else:
        print("主格号：连续无空号")
    无日期 = []
    for i, line in enumerate(文本.split("\n"), 1):
        if "后" in line and re.search(r"格\s*\d+\s*后", line) and not re.search(r"\d{4}", line):
            无日期.append(i)
    if 带前缀:
        if 无日期:
            print("【警报】%d 行带前缀格未写年月日，无法验零倒序：第 %s 行" % (len(无日期), "、".join(map(str, 无日期[:8]))))
        else:
            print("带前缀格：均带年月日")

    # 日期零倒序：按表格物理行序取年月日序列。判据里的「零倒序」指日期，不是格号；
    # 格位表按平台章时间轴排，排序按日期、不按编号后缀（见 01c 第四节）。
    # 日期零倒序：只在主格位表里取，不受同文件里其它从 0 起的表干扰；
    # 日期允许完整日／月／旬三种精度，折算日只用于排序，不参与日差。
    日期行 = []
    for ln, cells in 主数据:
        if 主di is None or len(cells) <= 主di:
            continue
        d, prec = 解析日期精度(cells[主di])
        if d is not None:
            日期行.append((ln, d.isoformat()))
    if not 日期行:
        print("【提示】未识别到表格行日期，无法验日期零倒序；表头须含格号列与日期列")
        return
    日期倒序 = [(日期行[k][0], 日期行[k][1], 日期行[k + 1][0], 日期行[k + 1][1])
             for k in range(len(日期行) - 1) if 日期行[k][1] > 日期行[k + 1][1]]
    if 日期倒序:
        print("【警报】日期倒序 %d 处（按物理行序，排序按日期不按编号后缀）：" % len(日期倒序))
        for a, d1, b, d2 in 日期倒序[:5]:
            print("  第 %d 行 %s → 第 %d 行 %s" % (a, d1, b, d2))
    else:
        print("日期序列：零倒序（%d 行，%s → %s；排序按日期、不是按编号后缀）" % (
            len(日期行), 日期行[0][1], 日期行[-1][1]))



def 占比(总边, 承重边, 知情格, 主表行):
    对 = 总边 // 2
    print("总边数 %d 条＝%d 对；承重边 %d 条；知情格 %d 格；主表 %d 行" % (总边, 对, 承重边, 知情格, 主表行))
    if 对 < 60:
        print("【结论】对数＜60，占比判据不启用；只查三条定性规矩——同一条边不连续两个台阶兑现／首尾不许一人独扛／每条承重边至少变形两次。")
        return
    p = 承重边 / 总边 * 100 if 总边 else 0
    print("承重边占比 %.1f%%（按有向边计：%d／%d；参考基线 10—15%%）" % (p, 承重边, 总边))
    if p < 10:
        print("【提示】占比偏低，人物多于戏。")
    elif p > 15:
        print("【提示】占比偏高，关系太密、没余量。")
    else:
        print("承重边占比在参考基线内。")
    if 知情格:
        print("知情格平均挂 %.1f 行戏（每格至少换出一场戏）" % (主表行 / 知情格))
    print("单条边挂戏上限：主表行数的两成＝%.0f 行，逐条核时不要超。" % (主表行 * 0.2))


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return
    cmd = sys.argv[1]
    a = sys.argv[2:]
    if cmd == "边数" and len(a) == 3:
        边数(整数(a[0], "核心人数"), 整数(a[1], "扩展人数"), 整数(a[2], "扩展内部边数"))
    elif cmd == "容量" and len(a) == 5:
        容量(*[整数(x, "参数") for x in a])
    elif cmd == "格位" and len(a) == 1:
        格位(a[0])
    elif cmd == "占比" and len(a) == 4:
        占比(*[整数(x, "参数") for x in a])
    else:
        print("【错误 E08】参数个数或写法不对，下面是用法的原文：")
        print(__doc__)


if __name__ == "__main__":
    try:
        main()
    except FileNotFoundError as e:
        print("【错误 E01】找不到文件：%s" % e.filename)
        print("【怎么办】路径加引号、先 ls 确认文件在；目录名不要留空格。")
        sys.exit(2)
    except IsADirectoryError as e:
        print("【错误 E02】给的是目录，这个脚本要的是文件：%s" % e.filename)
        print("【怎么办】单章传文件路径；批量按文件头用法加 --all 并给目录。")
        sys.exit(2)
    except UnicodeDecodeError:
        print("【错误 E03】连 GB18030 也解不了，这个文件多半不是纯文本。")
        print("【怎么办】确认传的是 .md／.txt，不是 .docx／.pdf；Word 稿请先另存为纯文本再跑。")
        sys.exit(2)
    except PermissionError as e:
        print("【错误 E04】没有读取权限：%s" % e.filename)
        print("【怎么办】换到有权限的目录，或先把文件复制出来再跑。")
        sys.exit(2)
    except KeyboardInterrupt:
        print("\n已中断。")
        sys.exit(130)
    except Exception as e:
        print("【错误 E05】%s：%s" % (type(e).__name__, e))
        print("【怎么办】把这一行连同执行的命令一起，按 references/14-反馈与台账.md 整理成一段反馈。")
        sys.exit(1)
