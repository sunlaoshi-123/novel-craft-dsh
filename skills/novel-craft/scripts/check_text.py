#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""单章自检：量句长、查标点、报密度。

用法：
    python check_text.py 正文.md
    python check_text.py 正文.md --json
    python check_text.py 目录/ --all          # 按章号排序，并给出逐章趋势判定

参考区间（默认文风档的常规章口径，不是硬指标）见 references/03-文笔纪律.md：
    叙述句均 20—24 字   对话句均 8—12 字   段均 26—34 字
冷叙事、番茄短句章通篇偏低是风格；看逐章趋势，连续三章走低才是警报，
不要把这三个数当合格线逐章卡。
对标档（立项一页纸填了「文风五维」并冻结样本时）这三个数只作参照，
尺子是冻结样本——本脚本量出的数请与样本对照，不拿绝对数判病。

只报数不下结论的地方（短句连排、数字密度）会标"提示"，不作硬判。
"""

import sys
import os
import re
import json
import io

# 中文弯引号、直角引号、半角引号，都算对话
QUOTE_PAIRS = [("“", "”"), ("「", "」"), ("『", "』"), ('"', '"')]
SENT_END = "。！？…"
BAD_LINE_HEAD = "。，、；：？！）」』”’"
BAD_LINE_TAIL = "（「『“‘"
# 数量短语：数字串＋量词。只数明确的量，不把"一下""一时"这类算进去
NUM_PAT = (r"(?:\d+(?:\.\d+)?|[一二三四五六七八九十百千万两〇零]{1,6})\s*"
           r"(?:个|米|公分|厘米|毫米|吨|公斤|千克|字|人|户|层|栋|章|卷|案|"
           r"年|月|日|点|分|秒|块|根|颗|道|处|条|张|份|次|回|遍|成|倍|度|"
           r"号|页|间|把|枚|件|岁|天|夜|步|句|笔|刀|口|杯|碗|趟|封|斤|里|级)")


_编码提示已打 = [False]
_体积提示已打 = [False]


def read(path):
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



def visible(s):
    return re.sub(r"\s+", "", s)


def split_sentences(s):
    """按句末标点切，返回去掉句末标点后的可见句子。"""
    parts = re.split(r"[" + SENT_END + r"]+", s)
    return [visible(p) for p in parts if visible(p)]


def paragraphs(text):
    out = []
    for i, line in enumerate(text.split("\n"), 1):
        raw = line.strip()
        if not raw:
            continue
        if raw.startswith("#") or raw.startswith(">"):
            continue
        if set(raw) <= set("＊*—-　 "):
            continue
        out.append((i, raw))
    return out


def extract_dialog(raw):
    """抽走引号内文字，返回（对话列表, 剩余叙述）。"""
    dialogs = []
    rest = raw
    for a, b in QUOTE_PAIRS:
        if a == b:
            # 半角直引号：成对出现，奇数位是对话，偶数位是叙述
            pieces = rest.split(a)
            dialogs.extend(pieces[1::2])
            rest = "".join(pieces[::2]) if len(pieces) > 1 else rest
        else:
            pat = re.escape(a) + r"(.*?)" + re.escape(b)
            dialogs.extend(re.findall(pat, rest, re.S))
            rest = re.sub(pat, "", rest, flags=re.S)
    return dialogs, rest


def verdict(v, lo, hi):
    if v < lo:
        return "低于参考"
    if v > hi:
        return "高于参考"
    return "在参考区间"


def check(path):
    text = read(path)
    pars = paragraphs(text)

    narr_sents, dial_sents = [], []
    for _, raw in pars:
        dialogs, rest = extract_dialog(raw)
        narr_sents.extend(split_sentences(rest))
        for d in dialogs:
            dial_sents.extend(split_sentences(d))

    def avg(xs):
        return round(sum(len(x) for x in xs) / len(xs), 1) if xs else 0.0

    narr_avg = avg(narr_sents)
    dial_avg = avg(dial_sents)
    par_avg = round(sum(len(visible(r)) for _, r in pars) / len(pars), 1) if pars else 0.0

    hanzi = len(re.findall(r"[\u4e00-\u9fff]", text))
    chars = len(visible(text))

    # 半角引号与孤行标点
    half_quotes = text.count('"') + text.count("'")
    orphan = []
    for ln, raw in pars:
        if raw and raw[0] in BAD_LINE_HEAD:
            orphan.append((ln, "行首", raw[0]))
        if raw and raw[-1] in BAD_LINE_TAIL:
            orphan.append((ln, "行尾", raw[-1]))

    # 连续短句（>=3 句且每句 <6 字），提示用
    runs, cur = [], []
    for s in narr_sents:
        if len(s) < 6:
            cur.append(s)
        else:
            if len(cur) >= 3:
                runs.append("／".join(cur))
            cur = []
    if len(cur) >= 3:
        runs.append("／".join(cur))

    # 数字密度：每多少字一个数字串
    nums = len(re.findall(NUM_PAT, text))
    density = round(chars / nums, 1) if nums else 0.0

    # 孤字：段落里单独成句的单个汉字（如"上。""钢。"）。报数段是合法节拍，只提示不判错
    lone = []
    for ln, raw in pars:
        _, rest = extract_dialog(raw)
        for piece in re.split(r"[。！？…]+", rest):
            v = visible(piece)
            if len(v) == 1 and re.match(r"[\u4e00-\u9fff]", v):
                lone.append((ln, v))

    return {
        "文件": os.path.basename(path),
        "汉字": hanzi,
        "字符": chars,
        "段数": len(pars),
        "叙述句数": len(narr_sents),
        "叙述句均": narr_avg,
        "叙述判读": verdict(narr_avg, 20, 24),
        "对话句数": len(dial_sents),
        "对话句均": dial_avg,
        "对话判读": verdict(dial_avg, 8, 12),
        "段均": par_avg,
        "段判读": verdict(par_avg, 26, 34),
        "半角引号": half_quotes,
        "孤行标点": orphan[:10],
        "孤字": lone[:20],
        "短句连排": runs[:5],
        "数量短语": nums,
        "每数字间隔": density,
        "密度提示": "数字偏密，考虑拆章或把数拆到别处" if 0 < density < 30 else "",
    }


def show(r, as_json=False):
    if as_json:
        print(json.dumps(r, ensure_ascii=False, indent=2))
        return
    print("文件：%s" % r["文件"])
    print("汉字 %s ／ 字符 %s ／ 段 %s" % (r["汉字"], r["字符"], r["段数"]))
    print("叙述句均 %s 字（常规章参考 20—24）%s，共 %s 句" % (r["叙述句均"], r["叙述判读"], r["叙述句数"]))
    print("对话句均 %s 字（参考 8—12）%s，共 %s 句" % (r["对话句均"], r["对话判读"], r["对话句数"]))
    print("段均 %s 字（参考 26—34）%s" % (r["段均"], r["段判读"]))
    print("半角引号 %s 处；孤行标点 %s 处" % (r["半角引号"], len(r["孤行标点"])))
    print("孤字 %s 处（报数段可豁免）%s" % (
        len(r["孤字"]),
        "：" + "、".join("第%s行「%s」" % (ln, ch) for ln, ch in r["孤字"][:8]) if r["孤字"] else ""))
    for ln, pos, ch in r["孤行标点"]:
        print("  第%s行 %s：%s" % (ln, pos, ch))
    print("数量短语 %s 个，每 %s 字一个%s" % (r["数量短语"], r["每数字间隔"], "　※" + r["密度提示"] if r["密度提示"] else ""))
    if r["短句连排"]:
        print("短句连排（报数段可豁免）：")
        for x in r["短句连排"]:
            print("  " + x)
    print("口径：字＝去空白后的可见字符（含标点）；叙述与对话分开量；引号内文字只进对话。")
    print("注一：对话密集章总段均天然偏低，看叙述段均即可。")
    print("注二：20—24 是常规章口径。冷叙事、番茄短句章通篇偏低是风格，不是病——"
          "用 --all 看逐章趋势，连续三章走低才是警报。")
    print("注三：源稿用半角引号是约定，出排版件前必须转中文弯引号并复跑，排版件应为 0。")


CN_DIGIT = {"零": 0, "〇": 0, "一": 1, "二": 2, "三": 3, "四": 4,
            "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}


def cn2int(s):
    if s.isdigit():
        return int(s)
    total, num = 0, 0
    for ch in s:
        if ch in CN_DIGIT:
            num = CN_DIGIT[ch]
        elif ch == "十":
            total += (num or 1) * 10
            num = 0
        elif ch == "百":
            total += (num or 1) * 100
            num = 0
    return total + num


def chapter_key(path):
    """按章号自然排序；没有章号的文件排到最后。"""
    name = os.path.basename(path)
    m = re.search(r"第([零〇一二三四五六七八九十百\d]+)章", name)
    if m:
        return (0, cn2int(m.group(1)))
    return (1, name)


def trend(rows):
    """找出连续递减段，长度满三章才报警，一段只报一次。"""
    seq = [r["叙述句均"] for r in rows]
    runs, start = [], 0
    for i in range(1, len(seq) + 1):
        if i == len(seq) or seq[i] >= seq[i - 1]:
            if i - start >= 3:
                runs.append((start, i - 1))
            start = i
    if not runs:
        print("趋势：叙述句均无连续三章走低")
        return
    for a, b in runs:
        print("趋势警报：叙述句均连续 %s 章走低（%s → %s，%s → %s）" % (
            b - a + 1, os.path.basename(rows[a]["文件"])[:8],
            os.path.basename(rows[b]["文件"])[:8], seq[a], seq[b]))


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    flags = [a for a in sys.argv[1:] if a.startswith("--")]
    if not args:
        print(__doc__)
        return
    target = args[0]
    as_json = "--json" in flags

    if "--all" in flags or os.path.isdir(target):
        files = [os.path.join(target, f) for f in os.listdir(target)
                 if f.lower().endswith((".md", ".txt"))]
        files.sort(key=chapter_key)
        rows = [check(f) for f in files]
        trend_rows = [r for r in rows if chapter_key(r["文件"])[0] == 0]
        skipped = [os.path.basename(f) for f in files if chapter_key(f)[0] == 1]
        if as_json:
            print(json.dumps(rows, ensure_ascii=False, indent=2))
        else:
            print("文件\t汉字\t叙述均\t对话均\t段均\t半角\t孤行\t每数字间隔")
            for r in rows:
                print("%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s" % (
                    r["文件"], r["汉字"], r["叙述句均"], r["对话句均"],
                    r["段均"], r["半角引号"], len(r["孤行标点"]), r["每数字间隔"]))
            lone_total = sum(len(r["孤字"]) for r in rows)
            if lone_total:
                print("孤字合计 %s 处（报数段可豁免，明细见单章模式）" % lone_total)
            trend(trend_rows)
            if skipped:
                print("【提示】%s 个文件无章号，不参与趋势判定：%s" % (
                    len(skipped), "、".join(skipped)))
        return

    show(check(target), as_json)


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
