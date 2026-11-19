#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""故事时间线机械自检：格位表日期序列 ＋ 正文时间表达待核清单。

用法（全部中文参数）：
    python check_timeline.py 格位表.md 正文目录/

只做四件机械可靠的事，见 references/12-故事时间线.md 第五节：
  1. 格位表日期零倒序、首末、相邻间隔分布（间隔不均合法，只报告不判错）；
  2. 正文绝对日期／年份是否落在格位表区间内；
  3. 章内跨日合法／越界：本格起日＋(N−1) 须落在相邻格日期之前，
     逐个打印「第 N 天」的折算落点，越过相邻格即报「侵了下一章」；
  4. 跨章递增的「第 N 天」计数与格位表相邻间隔对照，报双轴警报。

【一章覆盖多格】格位表可加一列「章」，写「第 3 章」即声明该格属于哪一章。
有该列时，本章相邻格取「本章末格之后那一格」，合并覆盖不再误判越界；
无该列时按「第 k 章 ↔ 第 k 格」硬套，落点恰等于相邻格日的改报「待核」。

【能力边界·务必读】抓不到：地点倒挂、动作状态断裂、同一时段互斥、
人物位置错、「回来的第三天」这类语义矛盾、相对计时有没有起算点。
本脚本输出的是「待核清单」，不是合格证明。全绿只说明没抓到机械信号，
仍须按 12 号细则第三节逐章人工三查。
"""

import sys
import io
import os
import re
import glob
import datetime
from collections import Counter

中文数字 = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6,
          "七": 7, "八": 8, "九": 9, "十": 10, "十一": 11, "十二": 12}


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



def 转数字(s):
    """认阿拉伯数字与「十三／二十／二十三」这类两位中文数字。
    只认到「十二」会让第十三天以后的硬天数静默漏检——漏检比误报更危险。"""
    s = (s or "").strip()
    if not s:
        return None
    if s.isdigit():
        return int(s)
    if s in 中文数字:
        return 中文数字[s]
    if "十" in s:
        a, _, b = s.partition("十")
        if (a == "" or a in 中文数字) and (b == "" or b in 中文数字):
            return (中文数字[a] if a else 1) * 10 + (中文数字[b] if b else 0)
    return None
    return None


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

def 解析格位表(path):
    """返回 (rows, 诊断)。rows 每项＝(行号, 格号, 日期原文, 章号, 精度, 折算日)。"""
    t = 读(path)
    t2 = t.replace("｜", "|")
    数据, gi, di, ci, 表数, 主首行 = 主格位表(t2)
    诊断 = []
    if 表数 > 1:
        诊断.append("【提示】同一文件检出 %d 张格位表，疑似多表混排；按数据最多的第 %d 行那张验，其余跳过。" % (表数, 主首行))
        诊断.append("格位表建议单独存一份文件；多张表首尾相接会把正常的日期读成倒序。")
    rows = []
    无日期 = 0
    for ln, cells in 数据:
        if len(cells) <= max(gi, di):
            continue
        g = cells[gi] if gi is not None else "—"
        d, prec = 解析日期精度(cells[di])
        if d is None:
            无日期 += 1
            continue
        chap = None
        if ci is not None and len(cells) > ci:
            m = re.search(r"第\s*(\d+)\s*章", cells[ci])
            chap = int(m.group(1)) if m else None
        rows.append((ln, g or "—", cells[di], chap, prec, d))
    if 无日期:
        诊断.append("【提示】%d 格无日期（结尾／尾声），未纳入日期序列。" % 无日期)
    return rows, 诊断



def 章序(path):
    base = os.path.basename(path)
    m = re.search(r"第\s*(\d+)\s*章", base)
    return int(m.group(1)) if m else 0


def 扫描正文(目录):
    fs = glob.glob(os.path.join(目录, "*.md"))
    fs = [f for f in fs if not os.path.basename(f).startswith(".")
          and "格位表" not in os.path.basename(f)]  # 格位表若同目录，不能当正文章扫
    fs.sort(key=lambda f: (章序(f), f))
    out = []
    for f in fs:
        t = 读(f)
        items = []
        for ln, line in enumerate(t.split("\n"), 1):
            # 绝对日期与年份
            for m in re.finditer(r"\b(\d{4})-(\d{1,2})-(\d{1,2})\b", line):
                items.append((ln, "绝对日期", m.group(0)))
            for m in re.finditer(r"([一二三四五六七八九〇零]{4})年", line):
                items.append((ln, "年份", m.group(0)))
            # 相对计时：第 N 天 / 隔了 N 天 / N 天后 / 回来的第 N 天 / 第二天傍晚
            for m in re.finditer(r"(?:回来的|在[^，。]{0,8}的)?第([一二三四五六七八九十\d]+)天", line):
                n = 转数字(m.group(1))
                items.append((ln, "第N天", (m.group(0), n)))
            for m in re.finditer(r"隔了?([一二三四五六七八九十\d]+)天", line):
                n = 转数字(m.group(1))
                items.append((ln, "隔N天", (m.group(0), n)))
            for m in re.finditer(r"([一二三四五六七八九十\d]+)天后", line):
                n = 转数字(m.group(1))
                items.append((ln, "N天后", (m.group(0), n)))
        out.append((os.path.basename(f), items))
    return out


def parse_day(s):
    """日期容错解析：认 2026-11-07／2026/11/07／2026.11.07／2026年11月7日。"""
    t = (s or "").strip()
    for ch in "年月":
        t = t.replace(ch, "-")
    t = t.replace("日", "").replace("/", "-").replace(".", "-").replace("—", "-")
    try:
        return datetime.date.fromisoformat(t)
    except Exception:
        pass
    try:
        y, m, d = [int(x) for x in t.split("-")[:3]]
        return datetime.date(y, m, d)
    except Exception:
        return None


def main():
    if len(sys.argv) < 3:
        print("用法：python check_timeline.py 格位表.md 正文目录/")
        return
    格表, 正文目录 = sys.argv[1], sys.argv[2]
    if not os.path.isfile(格表):
        print("【错误 E01】格位表不存在：%s" % 格表)
        print("【怎么办】路径加引号、先 ls 确认文件在。")
        return
    if not os.path.isdir(正文目录):
        print("【错误 E01】正文目录不存在：%s" % 正文目录)
        print("【怎么办】确认目录路径；末尾带不带斜杠都行。")
        return

    rows, 诊断 = 解析格位表(格表)
    print("=== 一、格位表日期序列 ===")
    for x in 诊断:
        print("  " + x)
    if not rows:
        print("  未识别到带日期的表格行，无法验。")
        print("  支持完整日（2026.11.07）、只到月（2026.11）、月加旬（2026.11下／底）；")
        print("  表头须含「格号／#／序号／格」列和「时间／年月日／日期」列。")
        return
    日期 = [r[5] for r in rows]
    精度列 = [r[4] for r in rows]
    倒序 = [(rows[k][0], rows[k][2], rows[k + 1][0], rows[k + 1][2])
          for k in range(len(日期) - 1) if 日期[k] > 日期[k + 1]]
    精度计数 = Counter(精度列)
    print("  带日期行 %d 个（日 %d／旬或月底 %d／只到月 %d），首 %s → 末 %s" % (
        len(rows), 精度计数.get("日", 0), 精度计数.get("旬", 0), 精度计数.get("月", 0),
        日期[0], 日期[-1]))
    if 精度计数.get("月", 0) or 精度计数.get("旬", 0):
        print("  【提示】%d 格日期只到月／旬，按该月 1／11／21／28 日折算用于排序，" % (
            精度计数.get("月", 0) + 精度计数.get("旬", 0)))
        print("  已单列、不计入日差统计，也不当作完整日期。")
    if 倒序:
        print("  【警报】日期倒序 %d 处（排序按日期、不按编号后缀）" % len(倒序))
        for a, d1, b, d2 in 倒序[:5]:
            print("    第 %d 行 %s → 第 %d 行 %s" % (a, d1, b, d2))
    else:
        print("  日期序列：零倒序")
    # 日差只取相邻两格都是「日」精度的；跨精度会造出假间隔（2023.10 按 1 日 → 11.02 会得到 32 天）
    日差 = [(日期[k + 1] - 日期[k]).days for k in range(len(日期) - 1)
           if 精度列[k] == "日" and 精度列[k + 1] == "日"]
    常见 = Counter(日差).most_common(4)
    print("  相邻间隔分布（%d 对完整日相邻，只报告不判错）：%s" % (
        len(日差), "、".join("%d 天×%d" % (g, c) for g, c in 常见) if 常见 else "无"))
    年区间 = (日期[0].year, 日期[-1].year)

    print("")
    print("=== 二、正文时间表达待核清单 ===")
    章节 = 扫描正文(目录=正文目录)
    if not 章节:
        print("  【提示】正文目录内未找到 md 文件（只扫 .md，不扫 .txt／.docx）")

    # 章→格 映射。格位表有「章」列时按该列取，能正确处理一章合并覆盖多格；
    # 无该列则按「第 k 章 ↔ 第 k 格」一一对应——一旦有章合并覆盖，后续全错位一格。
    章号列 = [r[3] for r in rows]
    章格 = {}
    for 格索引0, c in enumerate(章号列):
        if c is not None:
            章格.setdefault(c, []).append(格索引0)
    有章列 = bool(章格)
    if 有章列:
        print("  格位表带「章」列：按章映射 %d 章 → %d 格（一章可合并覆盖多格）" % (
            len(章格), sum(len(v) for v in 章格.values())))
    else:
        print("  格位表无「章」列：按「第 k 章 ↔ 第 k 格」一一对应")
        if len(章节) != len(日期):
            print("  【提示】正文 %d 章、格位表 %d 格，数目不等。若某章合并覆盖多格，" % (len(章节), len(日期)))
            print("  在格位表加一列「章」写「第 N 章」，量具按该列取相邻格，不再按章序硬套；")
            print("  不加也不影响判断，但越界项会按其性质分列【警报】与【待核】，不一律当硬伤。")

    # 双轴判定的基准取「正文实际覆盖的那几格」，不取全书众数：
    # 长篇常按卷变速，全书众数与前十章无关，拿它当依据会报错方向。
    if 有章列:
        已映射 = [章格[章序(n)][-1] for n, _ in 章节 if 章序(n) in 章格]
        覆盖 = (max(已映射) + 1) if 已映射 else min(len(章节), len(日期))
    else:
        覆盖 = min(len(章节), len(日期))
    覆盖间隔 = [(日期[k + 1] - 日期[k]).days for k in range(max(覆盖 - 1, 0))
               if 精度列[k] == "日" and 精度列[k + 1] == "日"]
    覆盖常见 = Counter(覆盖间隔).most_common(3) if 覆盖间隔 else []
    主间隔 = 覆盖常见[0][0] if 覆盖常见 else 0
    print("  正文 %d 章 → 对应格位表前 %d 格，该区间主间隔 %d 天（%s）" % (
        len(章节), 覆盖, 主间隔,
        "、".join("%d 天×%d" % (g, c) for g, c in 覆盖常见) if 覆盖常见 else "无"))
    alldays = []
    for 章索引, (name, items) in enumerate(章节):
        if 有章列:
            格s = 章格.get(章序(name))
            if 格s:
                本格起日 = 日期[格s[0]]
                末格 = 格s[-1]
                相邻格日 = 日期[末格 + 1] if 末格 + 1 < len(日期) else None
            else:
                本格起日 = 相邻格日 = None
        else:
            本格起日 = 日期[章索引] if 章索引 < len(日期) else None
            相邻格日 = 日期[章索引 + 1] if 章索引 + 1 < len(日期) else None
        if not items:
            continue
        print("  【%s】" % name)
        for ln, kind, val in items[:12]:
            if kind == "年份":
                yr = val[:4]
                数字年 = 0
                for ch in yr:
                    数字年 = 数字年 * 10 + {"〇": 0, "零": 0, "一": 1, "二": 2, "三": 3,
                                        "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}.get(ch, 0)
                if 数字年 and not (年区间[0] <= 数字年 <= 年区间[1]):
                    print("    第 %d 行 %s：年份 %d 不在格位表 %d—%d 区间，待核" % (
                        ln, val, 数字年, 年区间[0], 年区间[1]))
                else:
                    print("    第 %d 行 %s：年份落在区间内" % (ln, val))
            elif kind == "绝对日期":
                try:
                    d = datetime.date.fromisoformat(val)
                    ok = 日期[0] <= d <= 日期[-1]
                    print("    第 %d 行 %s：%s，待核是否与本章格位日期一致" % (
                        ln, val, "落在格位表区间内" if ok else "不在格位表区间内"))
                except ValueError:
                    print("    第 %d 行 %s：日期格式待核" % (ln, val))
            else:
                text, n = val
                if kind == "第N天" and n is not None:
                    alldays.append((name, ln, n, 本格起日, 相邻格日))
                if kind == "第N天" and n is not None and 本格起日 and 相邻格日:
                    # 章内跨日合法：本格起日＋(N-1) 须落在相邻格日期之前。
                    # 落点「等于」相邻格日要分两种：有「章」列且该格已声明属本章＝合法；
                    # 无「章」列则无法区分「合并覆盖」与「真越界」，报【待核】不报【警报】。
                    try:
                        落点 = 本格起日 + datetime.timedelta(days=n - 1)
                        if 落点 > 相邻格日:
                            判语 = "越界，侵了下一章"
                        elif 落点 == 相邻格日:
                            判语 = ("正落在下一格当日，越界（该格已声明属本章时为合法）" if 有章列
                                    else "正落在相邻格当日：若本章合并覆盖该格属合法，否则即越界，须人判")
                        else:
                            判语 = "章内跨日，合法"
                        print("    第 %d 行 %-12s %s（本格 %s，第%d日＝%s，相邻格 %s；%s）" % (
                            ln, kind, text, 本格起日, n, 落点, 相邻格日, 判语))
                    except Exception:
                        print("    第 %d 行 %-12s %s（须给起算点）" % (ln, kind, text))
                else:
                    print("    第 %d 行 %-12s %s（须给起算点，按格位表日期差折算）" % (ln, kind, text))
        if len(items) > 12:
            print("    ……另有 %d 处，详见正文" % (len(items) - 12))

    print("")
    print("=== 三、双轴警报（正文自建连续计时 vs 格位表）===")
    # 章内跨日合法，只有「跨章递增的硬天数」才是第二根轴；
    # 同一章里出现「第二天」不作为警报依据（见 12 号层第一节第 5 条）。
    按章计数 = {}
    for name, ln, n, _a, _b in alldays:
        按章计数.setdefault(name, set()).add(n)
    跨章章数 = len(按章计数)
    不同天 = sorted(set(n for _, _, n, _a, _b in alldays))
    越界项 = [(name, ln, n, str(a), str(b)) for name, ln, n, a, b in alldays
            if a and b and (a + datetime.timedelta(days=n - 1)) > b]
    压线项 = [(name, ln, n, str(a), str(b)) for name, ln, n, a, b in alldays
            if a and b and (a + datetime.timedelta(days=n - 1)) == b]
    if 有章列:
        # 已按「章」列声明覆盖范围，相邻格取的是本章末格之后那一格，等于即真越界。
        越界项 = 越界项 + 压线项
        压线项 = []
    if 越界项:
        print("  【警报】%d 处硬天数越过相邻格日期（侵了下一章的时间）：" % len(越界项))
        for name, ln, n, a, b in 越界项[:5]:
            print("    %s 第 %d 行「第%d天」，本格 %s、相邻格 %s" % (name, ln, n, a, b))
    if 压线项:
        print("  【待核】%d 处硬天数正落在相邻格当日，可能是一章合并覆盖该格：" % len(压线项))
        for name, ln, n, a, b in 压线项[:5]:
            print("    %s 第 %d 行「第%d天」，本格 %s、相邻格 %s" % (name, ln, n, a, b))
        print("  处置：本章确实覆盖到该格，就在格位表加「章」列写「第 N 章」再跑一遍，")
        print("  量具会按声明取相邻格；只覆盖本格却写到这里，按 `12` 第一节第 5 条即越界。")
    if 跨章章数 >= 2 and len(不同天) >= 2 and 主间隔 > 1:
        print("  【警报】%d 个不同章出现递增的「第 N 天」计数（%s），格位表相邻格主间隔 %d 天。" % (
            跨章章数, "／".join("第%d天" % n for n in 不同天[:10]), 主间隔))
        print("  两套时间轴并存的高置信信号：正文跨章按连续日顺延，格位表按 %d 天跳格。" % 主间隔)
        print("  处置按 `references/12-故事时间线.md` 第二节：给每个硬天数补起算点并折算回格位日期，")
        print("  或删掉硬天数改模糊时间；不许反向改格位表。")
    elif 跨章章数 >= 2:
        print("  多章出现「第 N 天」，但计数未呈跨章递增；仍须逐章核起算点与覆盖区间。")
    elif 越界项 or 压线项:
        print("  未抓到跨章连续「第 N 天」计数；越界项按上面处置，不许反向改格位表。")
    else:
        print("  未抓到跨章连续「第 N 天」计数，也未抓到越界硬天数。")
        print("  **单章内的「第二天」是章内跨日，合法**，只需按 `12` 第一节第 5 条在章首工作注记明本格起日与覆盖日数。")
        print("  不代表时间线无误。")

    print("")
    print("=== 能力边界（必读）===")
    print("  本脚本抓不到：地点倒挂、动作状态断裂、同一时段互斥、人物位置错、")
    print("  「回来的第三天」这类语义矛盾、相对计时有没有起算点。")
    print("  输出是待核清单，不是合格证明。全绿仍须按 `references/12-故事时间线.md` 第三节逐章人工三查。")


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
