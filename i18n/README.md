# ProxUI 简体中文汉化（zh-CN）

本仓库是 [greenlogles/ProxUI](https://github.com/greenlogles/ProxUI) 的汉化分支。汉化以
**可重复套用的工具链**形式实现，而不是一次性手改——上游更新后可以重新跑脚本再套一遍。

## 汉化方式

没有引入运行时翻译层，也没有改 `app.py`。文案在**源码层面**被替换成中文，因此：

- 零运行时开销、零额外请求；
- 不依赖 DOM 二次扫描，不存在"动态内容漏翻"的匹配脆弱性；
- 后端日志与异常信息保持英文，便于搜索排错。

替换只发生在三种精确位置上，避免误伤结构：

| 位置 | 规则 |
|---|---|
| HTML 文本节点 `>文本<` | 整节点归一化后精确匹配 |
| 静态属性 `title/placeholder/aria-label/alt` | 仅匹配非 Alpine 绑定（跳过 `:attr`、`x-attr`、`@attr`） |
| JS 字符串字面量 `'…'` `"…"` `` `…` `` | 整字面量精确匹配，保留原引号类型 |

含 Jinja 表达式（`{{ }}` / `{% %}`）的节点**不参与**整节点替换，改用 `special.json` /
`special_js.json` 中的长片段替换，确保 `{{ }}` 与 `${ }` 占位符原样保留。

## 目录结构

```
i18n/
├── extract.py                 提取待译文案 -> candidates.json
├── apply.py                   应用词典（支持 --check 干跑）
├── build_special.py           由骨架生成 special.json
└── dict/
    ├── html_text_a.json       模板可见文本（A–N）
    ├── html_text_b.json       模板可见文本（N–Z 及句尾片段）
    ├── html_attr.json         静态属性文案
    ├── js_string_a.json       外部 JS 与内联脚本字面量（A–F）
    ├── js_string_b.json       外部 JS 与内联脚本字面量（F–Z）
    ├── special.json           含 {{ }} 的插值文案（32 条）
    ├── special_js.json        含 ${ } 的插值文案与动态拼接 DOM 文案（102 条）
    └── special.skeleton.json  插值节点的精确原文骨架（供 build_special.py 使用）
```

## 实测覆盖

从干净的上游提交（`64bb45d`）重跑 `python3 i18n/apply.py`，实际替换点：

| 类型 | 替换数 |
|---|---|
| HTML 文本节点 | 766 |
| 静态属性 | 68 |
| JS 字符串字面量 | 397 |
| 插值/动态片段 | 142 |
| **合计** | **1373** |

英文长句（连续 ≥3 个英文单词）消除率，口径为对比 `HEAD` 与工作区：

| 范围 | 汉化前 | 汉化后 | 消除 |
|---|---|---|---|
| `templates/`（文本节点 + 内联脚本） | 528 | 53 | 90.0% |
| `static/js/` | 136 | 3 | 97.8% |
| **合计** | **664** | **56** | **91.6%** |

剩余部分构成：

- **可见文本节点只剩 3 处**：2 处是"Proxmox Backup Server 目标会忽略此项…"这类
  含英文产品名的中文句子，1 处是 JS 源码注释（非用户可见）；
- `templates/` 那 53 的其余部分全部是 **CSS 类名**（`form-control form-control-sm`、
  `btn btn-sm btn-outline-danger` 等）与 `firewall=1` 这类配置串——**本就不应翻译**。

## 验证手段

每次改动后跑以下四项，全部通过才提交：

1. **Jinja 编译**：23 个模板全部 `Environment.get_template()` 通过，0 失败；
2. **JS 语法**：14 个 `static/js/*.js` 全部 `node --check` 通过；
3. **内联脚本回归**：对改动过的内联 `<script>` 块，比对"改前可编译、改后不可编译"的差异，0 回归；
4. **定界符守恒**：逐文件比对 `{{ }} {% %}` 与原 `<div> <script>` 计数，全部一致。

## 上游更新后如何重套

```bash
git fetch upstream
git merge upstream/main          # 或 rebase
python3 i18n/apply.py            # 重新套用词典；幂等，已翻译处不会重复处理
python3 i18n/apply.py --check    # 查看本次新增了多少待译文案
```

`apply.py --check` 会打印各分桶的词典命中率。命中率下降说明上游加了新文案，
按提示把新字符串补进对应 `dict/*.json` 即可——**不需要**再碰任何模板文件。

## 已知限制

- **未在真实 Proxmox 环境中联调**。本文所有覆盖率为静态代码度量，
  未验证实际运行时的页面表现。
- `app.py` 的后端消息（flash、`jsonify` 的 error/message）**保持英文**。
  这样做是有意的：`tests/` 中有 `assertIn("Missing iso_image parameter", ...)`
  一类断言锁定英文原文，翻译会破坏测试，且会降低排错时可搜索性。
- 少数动态拼接串（如内存显示 `GB/MB/Unknown` 的复合片段）因涉及布局空白，
  保留了英文。
- 技术术语按 Proxmox 中文习惯保留英文：VM→虚拟机、Container→容器、
  Guest→客户机、Node→节点、Snippet→片段、Job→作业；`cloud-init`、`Bond`、
  `ZFS`、`Ceph`、`idmap`、`writeback` 等保持原文。

## 许可证

沿袭上游 **GPL-3.0**。词典与脚本同为衍生作品，分发时须遵循同一许可证。
