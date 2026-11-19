// novel-craft bundle entry point.
// 随包携带 SKILL.md + references + scripts，用 ctx.skills.register() 注册为一个按需技能。
// resourceBase 指向技能目录，故 references/**、scripts/** 的相对引用在任意 cwd 下可解析。
import { existsSync, readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

export const name = 'novel-craft'
export const inject = ['skills']

const packageRoot = dirname(dirname(fileURLToPath(import.meta.url)))
const skillDir = join(packageRoot, 'skills', 'novel-craft')
const skillPath = join(skillDir, 'SKILL.md')

// frontmatter 解析：只认首行 --- 与成行闭合 ---；行尾归一 + 去 BOM。
// description 在源技能里是带引号的多行 YAML，这里取到第一个冒号后的整段并去引号。
function splitFrontmatter(text) {
  const norm = text.replace(/^\uFEFF/, '').replace(/\r\n?/g, '\n')
  const match = /^---[ \t]*\n([\s\S]*?)\n---[ \t]*(?:\n|$)/.exec(norm)
  if (!match) return { fields: {}, body: norm, parsed: false }
  const meta = match[1]
  const body = norm.slice(match[0].length).replace(/^\n+/, '')
  const read = (key) => {
    const m = new RegExp(`^${key}:\\s*(.+)$`, 'm').exec(meta)
    return m?.[1]?.trim().replace(/^["']|["']$/g, '')
  }
  return {
    fields: { name: read('name'), description: read('description'), whenToUse: read('whenToUse'), version: read('version') },
    body,
    parsed: true,
  }
}

export function apply(ctx) {
  if (!existsSync(skillPath)) {
    ctx.logger?.warn?.(`[novel-craft] 技能文件缺失：${skillPath}`)
    return
  }
  const { fields, body } = splitFrontmatter(readFileSync(skillPath, 'utf8'))
  const disposer = ctx.skills.register({
    name: fields.name || 'novel-craft',
    source: 'runtime',
    description: fields.description || '长篇小说创作技能包',
    ...(fields.whenToUse ? { whenToUse: fields.whenToUse } : {}),
    content: body,
    resourceBase: { kind: 'directory', path: skillDir },
  })
  // 返回注销器：卸载 / HMR 时移除该贡献，避免残留
  return () => disposer?.()
}
