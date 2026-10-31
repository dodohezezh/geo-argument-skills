# geo-argument-skills

**把地质论证变成可机检的契约：一条结论、它的前提、它的判废条件，以及什么检验能把它推翻。**

一个 AI 可以替你写出“多条独立证据支持这一结论”，但它不会在证据变了的时候告诉你哪几条结论必须撤回。这个仓库把那部分从模型手里拿走：契约由模型填，判决由脚本算。

## 这是什么

两个 Agent Skill（[geo-arg-register](skills/geology/geo-arg-register/SKILL.md) 与 [geo-arg-audit](skills/geology/geo-arg-audit/SKILL.md)）加一个确定性引擎 `geoarg`：

| 能力 | 交给谁 |
| --- | --- |
| 把主张拆成前提、凭据、成立条件、判废条件、蕴含 | 技能（模型） |
| 计算判决（SUPPORTED / UNDETERMINED / UNTESTED / SUSPENDED / DEFEATED） | 引擎（脚本） |
| 计算有效独立证据数 `n_eff`、暴露伪独立 | 引擎（脚本） |
| 列出“现在什么结果能撤回这条结论” | 引擎（脚本） |
| 把判决写成可重算、防篡改的台账 | 引擎（脚本） |
| 把转录级引文与源 PDF 比对，给验收率 | 引擎（脚本） |

判决是格，不是分数。`UNTESTED` 和 `UNDETERMINED` 是合法且常见的状态，它们比一个漂亮的置信度更接近地质学的真实情况。

## 快速开始

```bash
git clone <your-fork-url> geo-argument-skills
cd geo-argument-skills
pip install -e .
geoarg check examples/south-atlantic
geoarg judge examples/south-atlantic
geoarg independence examples/south-atlantic
geoarg hit-set examples/south-atlantic
geoarg ground examples/paper-demo --pdf examples/paper-demo/paper.pdf
geoarg report examples/south-atlantic
```

无需联网。`geoarg` 只依赖 PyYAML、pypdf 与 python-docx，判决完全由契约和引擎决定。

跑测试：

```bash
python -m unittest discover -s scripts/tests
```

## 引擎命令

| 命令 | 作用 |
| --- | --- |
| `geoarg check <case>` | 结构与交叉引用校验（每条 cp 与判废条件必须挂检验） |
| `geoarg judge <case>` | 计算判决与理由链 |
| `geoarg independence <case>` | 有效证据数 `n_eff / n`、平均相关系数、独立性警告 |
| `geoarg hit-set <case>` | 单事件判废路径，按判别力排序 |
| `geoarg report <case>` | 生成 Word 报告（默认 `<case>/report.docx`）；`--format md` 输出 Markdown；`--lang zh` 中文框架；`--full` 完整版（默认一页简报） |
| `geoarg commit <case>` | 写入 `.geoarg/registry/`，记录输入与引擎的哈希 |
| `geoarg verify <case>` | 重算并报告任何漂移：输入被改、引擎被改、判决被改 |
| `geoarg ground <case> --pdf <paper>` | 把每条 `source_locator` 的引文与 PDF 文本层比对，写接地台账并算验收率 |

`check` 对不合规契约返回非零；`commit` 拒绝提交不合规契约；`verify` 对任何漂移返回非零。这就是“确定性在脚本里”的含义。

## 接地门

LLM 最常见的地质错误不是推理错，是把没写的话写成引文。接地门把这一步从“模型自觉”变成“脚本比对”：

1. 转录级证据必须写 `source_locator`（页码 + 原文句子）。
2. `geoarg ground` 打开源 PDF，把句子规范化后与文本层逐页比对。
3. 结果四态：`grounded`（原页找到）、`page-mismatch`（找到但页码错）、`not-found`（编的）、`not-groundable`（PDF 没有文本层）。
4. `check` 与 `commit` 拒绝“accepted 但未接地”的转录级证据；台账摘要进 registry，改引文会被 `verify` 抓出来。

验收率 = `grounded / drafted`。它和 `n_eff` 是两个维度：一个说证据有几条独立线，一个说引文有几条确实存在。这道门只证明“这句话在源文件里”，不证明“这句话支持这条前提”；后者是审计的事。

## 设计原则

1. **确定性在脚本，判断在模型。** 判决、独立性和可撤回条件由代码算；模型只做它擅长的拆分、解释和报告。
2. **契约即接口。** 三个 YAML 文件是人和脚本共同读的边界，字段与枚举见 [contract-fields.md](skills/geology/geo-arg-register/references/contract-fields.md)。
3. **判决可重算。** `commit` 记录输入哈希与引擎哈希，任何改动都会在 `verify` 里暴露。结论可以错，台账不能含糊。
4. **`unknown` 是合法状态。** 契约不逼你填置信度，它逼你说清楚“缺什么检验”。
5. **缺口是一等公民。** 填不进契约的东西写进 `gaps`，标 `blocking`，它比假装表达完整更有用。
6. **引文要落地。** 转录级证据必须带原文锚点并过接地门；未接地的引文不得保持 `accepted`。

## 目录结构

```
geo-argument-skills/
├── skills/geology/            # 两个技能
│   ├── geo-arg-register/      #   填契约
│   └── geo-arg-audit/         #   审独立性 + 判别力
├── docs/geology/              # 中文使用页
├── scripts/geoarg/            # 确定性引擎
├── scripts/tests/             # 单元测试
├── schema/                    # JSON Schema（可选校验）
├── examples/south-atlantic/   # 教学案例（占位引用）
├── examples/paper-demo/       # 合成 PDF + 已提交接地台账
└── .claude-plugin/plugin.json # 插件清单
```

## 案例

`examples/south-atlantic` 是一条板块重建论证的完整契约：3 条前提、5 个判废条件、2 个蕴含、7 个检验。它的引用是占位，目的是让你看到契约的形状，而不是让你引用它的结论。预期行为：`check` 干净、判决 `UNTESTED`、`n_eff = 1.2 / 3`、`hit-set` 列出 13 条单事件判废路径。

`examples/paper-demo` 是接地门的演示：一份合成 PDF（三页，含两条引文），三条转录级证据带原文锚点，台账已提交。预期行为：`geoarg ground` 验收率 1.000，三页文本层可读，`check` 干净。

## 局限（v0.2）

- **不验证结论的真假**，只验证论证的结构与检验状态。地质学的真值不在这个仓库的射程内。
- **契约有成本。** 填一条论证需要几条到几十条前提，这是这个方法的代价，也是它比“直接写结论”慢的原因。
- **`hit-set` 只枚举单事件路径。** 多个降级判废条件同时成立的情况需要在报告里显式写出。
- **相关系数是估计。** `n_eff` 的 rho 表是先验，不是测量值。报告时必须带上假设。
- **接地门只比字符串。** 规范化后找不到就算 `not-found`；它能证明句子存在，不能证明句子被正确使用，也不做 OCR。扫描版 PDF 会得到 `not-groundable`。
- **度量范围小。** 独立性与判别力的完整研究（语料、专家标注、历史回测）不在本仓库内。

## 与上游 skill 生态的关系

布局、`SKILL.md` 约定、`docs/` 页面结构和 `plugin.json` 清单借鉴了 [mattpocock/skills](https://github.com/mattpocock/skills) 的组织方式；内容与引擎是这个仓库自己的。把本仓库的 `skills/` 目录链接进 `~/.claude/skills` 即可被支持该格式的 Agent 加载：

```bash
ln -s "$PWD/skills/geology" ~/.claude/skills/geology   # macOS / Linux
```

## License

MIT
