#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""情感落点自检：验证每案是否挂了情感落点（回 references/10-文笔与情感层.md）。

用法：
    python check_emotion.py 落点表.md
    python check_emotion.py 落点表.md --json
    python check_emotion.py 目录/ --all        # 目录内逐文件

判据见 references/10-文笔与情感层.md：
    主感：从 {疼／悬／爽／空／暖} 只选一个主感（可带一个辅感，但主感必填）。
    落点槽：每案必须至少命中 {代价／回声／翻转／错位} 之一。

本脚本是"结构代理"——它不判断文笔好坏，只判断作者是否按约定登记了
情感落点坐标（专治"稿子里有落点、表里没登记"的疏漏）。
接受两类输入：
    1) 独立的"情感落点表"：表头须含「主感」列与含「落点」的列
       （「落点」「落点槽」「落点说明」均可），模板见 references/10-文笔与情感层.md 第五节；
    2) 草稿里内嵌的同结构标记表。
未识别到合格表头时明确报「不判通过」，不把空结果当合格。
"""

import sys
import os
import re
import json
import io

FEELS = ["疼", "悬", "爽", "空", "暖"]
SLOTS = ["代价", "回声", "翻转", "错位"]


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



def parse_tables(text):
    """返回 [(表头列列表, [(行号, [单元格...])...]) ...] 仅含主感/落点列的表。"""
    # 中文输入法常打出全角竖线；不转成半角，整张表会被当成普通段落跳过。
    text = text.replace("｜", "|")
    lines = text.split("\n")
    out = []
    i = 0
    n = len(lines)
    while i < n:
        raw = lines[i].strip()
        if not raw.startswith("|"):
            i += 1
            continue
        header = [c.strip() for c in raw.strip("|").split("|")]
        hz = [c for c in header]
        # 主感须精确列名；落点列允许「落点」「落点槽」「落点说明」等写法。
        # 判存在与取下标必须用同一条件，否则会 StopIteration 崩掉（2026-11 实测）。
        是落点表 = ("主感" in hz) and any("落点" in c for c in hz)
        j = i + 1
        有分隔 = j < n and re.match(r"^\s*\|?[\s:|-]+\|?\s*$", lines[j])
        # 缺分隔行时只对认得出表头的落点表放行。放宽到全部表格，
        # 会把正文里以竖线开头的行当成表头，误报比漏报更难查。
        if not 有分隔 and not 是落点表:
            i += 1
            continue
        if 是落点表:
            数据起 = (j + 1) if 有分隔 else (i + 1)
            idx_feel = hz.index("主感")
            idx_slot = next(k for k, c in enumerate(hz) if "落点" in c)
            rows = []
            k = 数据起
            while k < n and lines[k].strip().startswith("|"):
                cells = [c.strip() for c in lines[k].strip("|").split("|")]
                if cells and not set("".join(cells)) <= set(":- "):
                    rows.append((k + 1, cells))
                k += 1
            out.append((hz, rows, idx_feel, idx_slot))
            i = k
        else:
            i = j + 1
    return out


def check_file(path):
    text = read(path)
    tables = parse_tables(text)
    issues = []
    checked = 0
    for hz, rows, fi, si in tables:
        for ln, cells in rows:
            checked += 1
            feel = cells[fi] if fi < len(cells) else ""
            slot = cells[si] if si < len(cells) else ""
            # 主感：取第一个字，须在集合；允许"悬/空"这种辅感写法，主感取首个
            feel_main = re.sub(r"[／/]", " ", feel).split()[0] if feel else ""
            if not feel_main or feel_main not in FEELS:
                issues.append((ln, "主感缺失或非法", feel))
            # 落点槽：须至少命中一个
            if not any(s in slot for s in SLOTS):
                issues.append((ln, "落点槽缺失（须含 代价/回声/翻转/错位 之一）", slot))
    return {
        "文件": os.path.basename(path),
        "落点行数": checked,
        "未过项数": len(issues),
        "未过明细": [{"行": ln, "问题": why, "原值": val} for ln, why, val in issues],
    }


def show(r, as_json=False):
    if as_json:
        print(json.dumps(r, ensure_ascii=False, indent=2))
        return
    print("文件：%s" % r["文件"])
    print("情感落点行数 %s，未过 %s 项" % (r["落点行数"], r["未过项数"]))
    if r["落点行数"] == 0:
        print("  未识别到情感落点表：表头须同时含「主感」与「落点（或落点槽）」两列。")
        print("  **本次不判通过**——没量到东西不等于合格；模板见 `references/10-文笔与情感层.md` 第五节。")
    elif r["未过明细"]:
        for it in r["未过明细"]:
            print("  第%s行：%s（原值「%s」）" % (it["行"], it["问题"], it["原值"]))
    else:
        print("  全部通过：每案主感合法、且至少挂一个情感落点槽。")


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
        rows = [check_file(f) for f in files]
        if as_json:
            print(json.dumps(rows, ensure_ascii=False, indent=2))
        else:
            for r in rows:
                show(r, as_json)
        total_issue = sum(r["未过项数"] for r in rows)
        empty = sum(1 for r in rows if r["落点行数"] == 0)
        print("汇总：%s 个文件，未过合计 %s 项；未识别到落点表的文件 %s 个（不判通过）" % (
            len(rows), total_issue, empty))
        return

    show(check_file(target), as_json)


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
