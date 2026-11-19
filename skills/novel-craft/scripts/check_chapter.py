#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""章级质量闸：情绪强度曲线、章末钩位置、章际承接。

用法（全部中文参数）：
    python check_chapter.py 正文目录/
    python check_chapter.py 正文目录/ --all       # 逐章明细
    python check_chapter.py 正文目录/ --quiet     # 只报警报

只做三件机械可靠的事，判据见 references/13-章节质量闸.md：
  1. 逐章情绪强度打分，报「连续三章走低」与「单章掉档」；
  2. 章末钩位置：末三段有无钩特征；中段有钩而末段无钩＝钩埋中段；
  3. 章际承接：上章末段与下章首段并排输出（只提示，不判定）。

字句级量具（段均／叙述句均／对话句均／半角引号／孤行／数字密度）不在本脚本重算，
唯一口径是 scripts/check_text.py 正文目录/ --all。两个量具给同一章报不同的数，
比没有量具更糟。

【能力边界·务必读】抓不到：钩子好不好、情绪写得真不真、人物像不像同一个人、
情节合不合理。强度是**词频代理**，会漏掉不靠情绪词写的克制段落（冷叙事尤其明显），
也会被情绪词堆砌骗过。输出是待核清单，不是合格证明。全绿仍须人工通读。
"""

import sys
import io
import os
import re
import glob
import json

# 情绪强度词表：身体反应（最硬，×3）／情绪直述（×1）／冲突动作（×2）
# 可按题材增删，改这里不影响其它脚本。
身体 = ["心里一沉", "心一沉", "手心出汗", "手心", "喉咙发紧", "喉咙", "头皮发麻", "头皮",
      "后背", "发麻", "喘不上", "喘", "手抖", "腿软", "冷汗", "脸热", "耳鸣", "胃里",
      "胸口", "牙关", "眼眶", "鼻子一酸", "气短", "发紧", "发凉", "发热"]
情绪 = ["急", "慌", "怕", "怒", "气", "恨", "愧", "难堪", "委屈", "松了口气", "踏实",
      "发怵", "心里没底", "不安", "沉默", "没说话", "愣", "怔", "僵", "沉默", "难受",
      "疼", "苦", "憋", "疑", "惊", "喜", "悲"]
冲突 = ["拍", "摔", "顶", "堵", "逼", "吵", "争", "拒", "不让", "压", "拦", "打断",
      "盯", "冷笑", "撂", "顶撞", "拍了", "摔了", "顶了", "顶回去", "扭", "推", "扯"]

# 钩子特征
钩疑问 = ["？", "?", "怎么", "为什么", "是不是", "能不能", "要不要", "算不算", "该往哪",
       "凭什么", "什么时候", "谁"]
钩未完成 = ["还没", "没有", "没", "未", "空", "剩下", "只差", "等", "待", "下一次",
        "再往后", "往后", "以后再", "总有一天"]
钩新信息 = ["电话", "电报", "信", "来人", "通知", "调令", "文件", "名单", "报了", "叫走",
        "传话", "条子", "批文"]


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



def 段落(text):
    out = []
    for i, line in enumerate(text.split("\n"), 1):
        s = line.strip()
        if not s or s.startswith("#") or s.startswith(">"):
            continue
        if set(s) <= set("＊*—-　 "):
            continue
        out.append((i, s))
    return out


def 数词(s, words):
    return sum(s.count(w) for w in words)


def 章序(path):
    m = re.search(r"第\s*(\d+)\s*章", os.path.basename(path))
    return int(m.group(1)) if m else 0


def 有钩(text):
    命中 = []
    for 名, 表 in (("疑问/未定", 钩疑问), ("未完成", 钩未完成), ("新信息", 钩新信息)):
        if any(k in text for k in 表):
            命中.append(名)
    return 命中


def 分析(path):
    t = 读(path)
    ps = 段落(t)
    if not ps:
        return None
    汉字 = len(re.findall(r"[\u4e00-\u9fff]", t))
    身 = 数词(t, 身体)
    情 = 数词(t, 情绪)
    冲 = 数词(t, 冲突)
    强度 = 身 * 3 + 情 * 1 + 冲 * 2

    末段 = ps[-3:] if len(ps) >= 3 else ps
    末钩 = 有钩(" ".join(x[1] for x in 末段))
    if len(ps) > 6:
        中 = ps[len(ps) // 2: len(ps) // 2 + 3]
        中钩 = 有钩(" ".join(x[1] for x in 中))
    else:
        中钩 = []

    return {
        "文件": os.path.basename(path),
        "章": 章序(path),
        "汉字": 汉字,
        "身体": 身, "情绪": 情, "冲突": 冲, "强度": 强度,
        "每千字强度": round(强度 / 汉字 * 1000, 1) if 汉字 else 0,
        "末段钩": 末钩, "中段钩": 中钩,
        "末段": ps[-1][1][:40],
        "首段": ps[0][1][:40],
    }


def 主(目录, 全量=False, 静默=False):
    fs = [f for f in glob.glob(os.path.join(目录, "*.md"))
          if not os.path.basename(f).startswith(".")]
    fs.sort(key=lambda f: (章序(f), f))
    if not fs:
        print("目录内没有 md：%s" % 目录)
        return
    rows = [r for r in (分析(f) for f in fs) if r]
    if not rows:
        print("未解析到正文段落")
        return

    if 全量 and not 静默:
        print(" 章  汉字  身体 情绪 冲突 强度 千字强度  末段钩      中段钩")
        for r in rows:
            print(" %2d  %4d  %3d %3d %3d  %4d  %5.1f    %-10s  %-10s" % (
                r["章"], r["汉字"], r["身体"], r["情绪"], r["冲突"], r["强度"],
                r["每千字强度"], "、".join(r["末段钩"]) or "无",
                "、".join(r["中段钩"]) or "无"))
        print()

    print("=== 一、情绪强度曲线 ===")
    seq = [r["强度"] for r in rows]
    print("  强度序列：", seq)
    千 = [r["每千字强度"] for r in rows]
    print("  千字强度：", 千)
    警报 = 0
    for i in range(len(seq) - 2):
        if seq[i] > seq[i + 1] > seq[i + 2]:
            print("  【警报】第 %d—%d 章强度连续三章走低（%d → %d → %d），读者体感会变平。" % (
                rows[i]["章"], rows[i + 2]["章"], seq[i], seq[i + 1], seq[i + 2]))
            警报 += 1
    均 = sum(千) / len(千) if 千 else 0
    for r in rows:
        if 均 and r["每千字强度"] < 均 * 0.6:
            print("  【待核】第 %d 章千字强度 %.1f，仅全书均值的 %.0f%%（可能是克制写法，也可能是这一章没使劲）。"
                  % (r["章"], r["每千字强度"], r["每千字强度"] / 均 * 100))
            警报 += 1
    if not 警报:
        print("  未抓到连续走低或明显掉档。**这不等于情绪写得好**，只是没出现词频层面的塌陷。")

    print("")
    print("=== 二、章末钩位置 ===")
    埋中 = 0
    for r in rows:
        if r["中段钩"] and not r["末段钩"]:
            print("  【待核】第 %d 章中段有钩（%s）而末段无钩——钩埋在中段。末段：%s" % (
                r["章"], "、".join(r["中段钩"]), r["末段"]))
            埋中 += 1
        elif not r["末段钩"] and not r["中段钩"]:
            print("  【待核】第 %d 章末段未见钩特征。末段：%s" % (r["章"], r["末段"]))
    if not 埋中:
        print("  未发现「中段有钩、末段无钩」的错位。钩子质量仍须人工读。")
    print("  注：钩特征是词面判断，克制型收尾（一句白描收住）会被判「无钩」，属正常，人工确认即可。")

    print("")
    print("=== 三、字句量具（不在此重算）===")
    print("  段均／叙述句均／对话句均／半角引号／孤行／数字密度，唯一口径是 `scripts/check_text.py 正文目录/ --all`。")
    print("  本脚本不重复算这些数，避免同一章出现两套数字。")
    print("")
    print("=== 四、章际承接（只提示，不判定）===")
    for a, b in zip(rows, rows[1:]):
        print("  第 %d 章末：%s" % (a["章"], a["末段"]))
        print("  → 第 %d 章首：%s" % (b["章"], b["首段"]))
        break
    print("  其余章对请人工按 references/12-故事时间线.md 第三节三查逐条对读。")

    print("")
    print("=== 能力边界（必读）===")
    print("  强度是词频代理：会漏掉不靠情绪词写的克制段落（冷叙事尤其明显），")
    print("  也会被情绪词堆砌骗过（词多不等于真疼）。钩是词面特征：白描收尾会被判无钩。")
    print("  抓不到：钩好不好、情绪真不真、人物像不像同一个人、情节合不合理。")
    print("  输出是待核清单，不是合格证明。全绿仍须人工通读。")


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    开关 = [a for a in sys.argv[1:] if a.startswith("--")]
    if not args:
        print("用法：python check_chapter.py 正文目录/ [--all] [--quiet]")
        return
    if not os.path.isdir(args[0]):
        print("【错误 E01】目录不存在：%s" % args[0])
        print("【怎么办】路径加引号、先 ls 确认目录在。")
        return
    主(args[0], 全量="--all" in 开关, 静默="--quiet" in 开关)


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
