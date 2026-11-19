# novel-craft（DeepSeek Harness 插件）

长篇小说创作技能包，供 DeepSeek Harness（dsh）按需加载。源技能在 SkillHub 发布，本仓库是它的 dsh 插件封装。

## 安装

```sh
dsh plugin add sunlaoshi-123/novel-craft-dsh
```

或在 dsh 的插件市场搜索 `novel-craft`。

## 提供什么

一个按需技能 `novel-craft`，覆盖：

- 开书立项：定来路、分型、篇幅档、文风五维与冻结样本
- 骨架工程：成长线、核心机制、关系矩阵、格位表、容量核算
- 写单章：时间线预检、文笔纪律、逐章自检脚本
- 全书级检查：动作指纹、反向行为、章题来源
- 改稿核账：改动联动、编号反查、伏笔超期
- 五份本地自检脚本（字数、情感、结构、时间线、章节质量闸）

技能正文与细则按需读取，不一次装载全部。

## 结构

```
package.json          # dsh.bundle 声明
cordis.patch.yml      # 自注册行（勿删第一行）
lib/index.js          # 入口，注册技能
skills/novel-craft/   # 技能本体：SKILL.md + references/ + scripts/
```

## 版本

与 SkillHub 发布的 novel-craft 同步，当前 1.7.3。
