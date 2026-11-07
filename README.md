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
| 把判决写成可重算、可追溯的台账 | 引擎（脚本） |
| 把转录级引文与源 PDF 比对，给验收率 | 引擎（脚本） |

判决是格，不是分数。`UNTESTED` 和 `UNDETERMINED` 是合法且常见的状态，它们比一个漂亮的置信度更接近地质学的真实情况。

## 快速开始

```bash
git clone <your-fork-url> geo-argument-skills
cd geo-argument-skills
pip install -e ".[schema]"        # 装 jsonschema 后 `geoarg schema --validate` 可用；可选
geoarg check examples/south-atlantic
geoarg judge examples/south-atlantic
geoarg independence examples/south-atlantic
geoarg hit-set examples/south-atlantic
`geoarg workspace examples` 也能跑：仓库根下没有 `workspace.yaml`，所以只解析出一条 `basement-age → basement-age` 的链（来自 workspace-demo 的相对路径解析），没有跨案例证据冲突；`examples` 本身只做结构检查。
geoarg workspace examples/workspace-demo
geoarg ground examples/paper-demo --source examples/paper-demo/paper.pdf
geoarg report examples/south-atlantic
geoarg card examples/south-atlantic --for reviewer --lang zh
geoarg schema --list
```

无需联网。`geoarg` 只依赖 PyYAML、pypdf 与 python-docx，判决完全由契约和引擎决定。

跑测试：

```bash
python -m unittest discover -s scripts/tests
```

## 作为项目安装

引擎和两个技能作为一个包发行；装好后把技能目录装进 Agent 宿主：

```bash
pip install .
geoarg install-skills              # 装到已存在的 ~/.dsh/skills、~/.claude/skills、./.dsh/skills、./.claude/skills
geoarg install-skills --dest <dir>  # 或指定一个目录（可重复）
geoarg install-skills --check       # 只比对已装副本与包内版本，报告漂移
geoarg doctor                       # 引擎、依赖、已装技能一起自检
```

两个技能的第一步都是 `geoarg --version`：引擎缺失或低于 1.12 就停，不手算判决、`n_eff` 或验收率。wheel 内置技能副本（`geoarg/_skills`），因此 pip 安装后不依赖仓库目录。

## 引擎命令

| 命令 | 作用 |
| --- | --- |
| `geoarg check <case>` | 结构与交叉引用校验（每条 cp 与判废条件必须挂检验；`holds` / `refuted` / `passed` 必须有一个通过的检验，否则报 `unbacked`；`--profile draft` 把完整性缺口降为警告，`--explain` 给每条问题修复提示并列出剩余 TODO） |
| `geoarg judge <case>` | 计算判决与理由链 |
| `geoarg independence <case>` | 有效证据数 `n_eff / n`、平均相关系数、独立性警告；只计 `accepted` 记录；同时给出 rho 先验变化时的敏感性区间（stress 字段） |
| `geoarg hit-set <case>` | 单事件就能改变结论的结果，按区分力、再按成本排序 |
| `geoarg report <case>` | 生成 Word 报告（默认 `<case>/report.docx`）；`--format md` 输出 Markdown；`--format html` 输出单文件 HTML 页面；`--lang zh` 中文框架；`--lang auto` 用运行机器的系统语言；`--brief` 一页简报；`--judgment` / `--judgment-file` 附模型撰写的评述（`--brief` 同样支持） |
| `geoarg card <case> --for <reader>` | 结论页：按读者取舍。`researcher` 版给结论、缺少检验依据的项数、下一步检验与缺口；`reviewer` 版另给逐条理由、哪些结果会改变结论、证据独立性、引文核对表与审计信息。`--judgment` / `--judgment-file` 附模型撰写的评述 |
| `geoarg commit <case>` | 原子写入 `.geoarg/registry/`（目录锁），记录输入、引擎与论证链的哈希，并向 `.geoarg/ledger.jsonl` 追加一条 `commit` 记录；存在 `unbacked` 或未解决的论证链时拒绝提交 |
| `geoarg verify <case>` | 重算并报告任何漂移：输入被改、引擎被改、判决被改、台账最新提交与 registry 不一致、交付物被改、锚点被改；`--anchor <file>` 另校验抄到仓库外的检查点 |
| `geoarg attest <case>` | 把当前交付物（`report.*`、`card.*`）与评述文件的内容哈希绑定到已提交记录，写 `.geoarg/attestation.json` 并追加 `attestation` 台账；`--include` 收窄文件集，`--judgment-file` 绑定评述 |
| `geoarg anchor <case>` | 写 `.geoarg/anchor.json` 检查点：记录摘要、台账头、条数、引擎摘要（engine_sha256）与时间；把该文件抄到仓库外即可对外声明“某时刻的台账头” |
| `geoarg ledger <case>` | 显示台账条目（类型、时间、判决、摘要、链接）；`--json` |
| `geoarg schema [name] [--validate <file>]` | 列出随包安装的 JSON Schema（argument/evidence/test/bundle/workspace/attestation/anchor/domain），或打印指定 schema；`--list`、`--json`；`--validate` 校验一个实例文件 |
| `geoarg ground <case> --source <paper>` | 把每条 `source_locator` 的引文与源文档比对（PDF/DOCX/HTML/Markdown/纯文本），写接地台账并算验收率；有未接地引文时默认非零退出（`--allow-partial` 仅用于查看半成品台账）；旧的 `--pdf` 仍可用 |
| `geoarg migrate <case\|dir>` | 把 case 的三个 YAML（或 `bundle.yaml`、`workspace.yaml`）的 `schema_version` 行改写为当前版本，其余字节不动；`--dry-run` 只报告不改 |
| `geoarg bundle <dir>` | 读 `bundle.yaml`，给一组案例各算判决，取必需主张里最弱的一条作为论文组结论；`--json`、`--out`、`--lang` |
| `geoarg workspace <dir>` | 扫描目录下每个案例：判决、论证链、跨案例共用的证据、同一证据 id 内容冲突、已提交记录的漂移；`--no-judge` 快速模式只做结构检查，跳过判决、链路和漂移；有任何问题非零退出；`--json`、`--format html`、`--out`、`--lang` |
| `geoarg patterns` | 列出随包的论证模式（年代夹持、层序界面、滑动速率），并说明如何用 `geoarg new` 起一个骨架 |
| `geoarg new <dir> --pattern <name>` | 按模式生成三份 YAML 草稿（含 TODO）；`--id` / `--title` / `--claim` 可覆盖；已存在案例时拒绝覆盖（`--force`） |
| `geoarg adopt <notes.md> --out <dir>` | 确定性地把 Markdown 提纲（`Claim`/`Premises`/`Evidence`/`Tests` 小节）转成草稿案例；不确定的值一律标 TODO |
| `geoarg impact <case>` | 决策价值：留一法消融证据/测试（决定性/支撑/冗余/未用/未挂接）、`--assume` 改变假设、`--add-evidence` 待采证据、剩余阻塞与独立性变化；`--workspace` 把同一批待采证据套到整个工作区；`--json`、`--out`、`--lang` |
| `geoarg domains [case]` | 列出内置枚举、作用在该案例上的 `domain.yaml` 领域包（含随包模式、字段建议）与合并后的生效值；`--lang`、`--json` |
| `geoarg advise <case>` | 按最近的领域包给出作者检查清单：缺哪些建议检验方法、缺哪些期望证据族、默认 profile 与接地提示；不改变判决、不提交记录；`--lang`、`--json` |
| `geoarg edit <case>` | 启动本地表单编辑器（仅 127.0.0.1，令牌保护，保存时原子写入并校验）；`--host`、`--port`、`--no-browser` |
| `geoarg figures <case>` | 生成四张确定性 SVG 论证图（论证状态、独立性、决策价值、证据覆盖）；默认写入 `<case>/figures`，`--out`、`--lang`、`--json`；`report --format html` 自动内嵌该目录，`package --include-figures` 随包带走 |
| `geoarg sources <case>` | 可选：列出每条引用是否有引文片段和接地源；`--require-quote` / `--require-source` 可让检查失败 |
| `geoarg references <case>` | 可选：用 Crossref / Europe PMC 核验 DOI/PMCID/PMID/arXiv，写 `.geoarg/references.json` 快照；`--offline` 只读缓存 |
| `geoarg package <case> --out <dir>` | 写出可移交的证据包：折叠契约、台账/记录/证明/锚点/接地台账、已绑定产出、自包含 `report.html`、SHA-256 清单与最小 RO-Crate；`--include-source` 一并打包来源文档 |
| `geoarg install-skills` | 把随包的技能副本装到已存在的技能目录（`~/.dsh/skills`、`~/.claude/skills`、`./.dsh/skills`、`./.claude/skills`），`--dest` 指定目录，`--check` 只比对漂移 |
| `geoarg doctor` | 自检引擎版本、依赖、JSON Schema、随包技能与已装技能是否一致 |
| `geoarg verify-package <dir>` | 重算证据包内所有摘要并核对记录、台账链、证明、锚点与接地台账；失败返回非零 |

`check` 对不合规契约返回非零；`commit` 拒绝提交不合规契约或存在 `unbacked` 状态的契约；`verify` 对任何漂移返回非零。这就是“确定性在脚本里”的含义。

`card` 不改变判决：同一案例的研究者版与评审者版，判决、`n_eff`、接地验收率完全一致，只改取舍与顺序。读者身份在会话开始时问一次，属于呈现层，不写进契约。两种版本都用作者自己的陈述与普通语言，机器字段值留在台账里。

`profile` 是可选元数据。论证可以在 `argument.yaml` 里声明所属方向（`primary`，可带 `secondary` 与一行 `rationale`）；省略时交付物写「未声明」。它只用于在页头标出领域，不选择术语，也不改变判决、`n_eff` 或验收率。交付物里的条件、证据与推论一律引作者自己的陈述，不另造术语；`UNTESTED` 等机器值只出现在台账的 `verdict` 字段里。

`card` 顶部可以带一段 2–4 句的模型评述（`--judgment` 或 `--judgment-file`）：数字由引擎给，评述由模型写；审计块记录该段落的 sha256，用来区分散文与计算。省略时卡头注明「评述：未提供」，引擎模板不写散文。

`verify` 防的是无意漂移：registry 记录、台账与锚点都在案例目录里，都能被重写；重新运行 `commit` 会追加新记录；若已经 `attest` 或 `anchor`，要按 commit → attest → anchor 的顺序重跑，`verify` 才重新通过。要防伪造，需要把锚点文件抄到仓库外或交给外部时间戳服务；仓库只提供锚定所需的字节，不替你保管它。

## 可信层（1.12）

0.9 之前，`verify` 只能比对案例输入、引擎、判决与论证链；它不知道交付给读者的报告是不是由这次提交生成的，也不知道台账是否被整体替换。1.0 把这两件事补上：

1. **交付物绑定。** `commit` 之后运行 `geoarg attest <case> --judgment-file <text>`，引擎把 `report.*`、`card.*` 与评述文件的内容哈希、引擎/规则版本、运行环境写进 `.geoarg/attestation.json`，并追加一条 `attestation` 台账。改了报告而没重新 `attest`，`verify` 报 `deliverable changed since attestation`；换了引擎而没重新 `attest`，报 `engine changed since attestation`。
把这份文件抄到仓库之外（邮件、论文附件、机构存档、时间戳服务）之后，用 `geoarg verify <case> --anchor <file>` 读那份副本，检查台账头是否仍与它一致；普通 `verify` 只检查本地锚点与台账自洽。
3. **原子写入与锁。** `commit`、`attest`、`anchor` 与接地台账都先写临时文件再 `os.replace`，同一案例目录加锁，避免半写文件与并发覆盖。
- schema 是文档与第二意见；命名前缀比引擎宽松，不强制 `arg.` 之类前缀。
5. **多格式接地。** 源文档除 PDF 外支持 DOCX、HTML、Markdown、纯文本；页码语义只对 PDF 成立，其他格式共用第 1 页。

这四个信任级别的关系是：结构自洽（`check`）→ 记录可复核（`commit` / `verify`）→ 交付物可追溯（`attest`）→ 台账头可对外声明（`anchor`）。每一级只在前一级之上加一条可检查的承诺；越过 `anchor` 的“这是真的”不在本仓库射程内。设计参考见 [docs/prior-art.md](docs/prior-art.md)。

## 结果绑定

检验的 `status` 可以不再手填。给一条检验写 `result` 与 `pass_rule`，引擎按规则把结果算成 `passed` / `failed` / `inconclusive`；计算值优先于手填值，两者不一致时 `judge` 报警并采用计算值。

```yaml
- id: T1
  name: 主检验
  checks: [P1]
  method: {type: statistical, description: ...}
  discriminating_power: high
  cost: 3
  result:
    value: 0.5
    uncertainty: {kind: ci95, low: 0.4, high: 0.6}
  pass_rule: {op: ge, value: 0.0}
```

`pass_rule` 支持 `ge`、`le`、`between`、`within_ci`、`ratio` 五种。`commit` 会记录计算得到的状态；改了 `result` 或 `pass_rule` 而没重新 `commit`，`verify` 会报 `computed test statuses changed`。没有写 `result` 的检验仍按手填 `status` 处理。

## 论文组

一篇论文有多条主张时，用 `bundle.yaml` 把它们放进同一个目录：

```yaml
schema_version: geoarg/bundle/0.1
id: paper.2026
title: 论文标题
claims:
  - case: claims/c1
  - case: claims/c2
    label: 第二条主张
    required: false
```

`geoarg bundle <dir>` 逐条运行 `judge`，按 `SUPPORTED < UNDETERMINED < UNTESTED < SUSPENDED < DEFEATED` 取必需主张里最弱的一条作为论文组结论；可选主张只列出，不参与聚合。缺目录或不合规的案例列为 problem，不会悄悄算进结论。`case` 路径相对 bundle 根目录写，也可以直接写绝对路径。

## 论证链与工作区

一条论证的前提可以来自另一条论证。写 `derived` 前提时用 `argument_ref` 指向目标论证，而不是复制结论：

```yaml
- id: P4
  statement: 上覆地层不晚于 3.2 Ga
  kind: derived
  argument_ref: overlying-strata
```

解析顺序：最近的工作区文件 `workspace.yaml` 里的论证 id → 相对/绝对案例路径 → 同级目录。工作区文件长这样：

```yaml
schema_version: geoarg/workspace/0.1
id: project.example
arguments:
  - id: basement-age
    case: claims/basement-age
  - id: overlying-strata
    case: claims/overlying-strata
```

`judge` 从案例目录向上找最近的 `workspace.yaml`，把目标论证的判决映射成这条前提的状态：目标成立则前提成立；目标被削弱、无法判定或未检验则前提挂在 `pending`；目标被推翻则前提算硬问题；引用找不到、论证链成环或目标案例坏了，写入工作区问题并让 `commit` 拒绝提交。`commit` 把论证链摘要写进 registry，`verify` 重算，链变了会报 `argument chain changed since commit`。报告与卡片里，派生前提写成「结论来自另一条论证（…）：…」，不出现内部状态名。

## 全局证据名录与漂移

`geoarg workspace <dir>` 把目录下每个案例（含 `argument.yaml` 的目录）扫描一遍，输出：

- 每条论证的目录、主张 id、领域与结论；
- 每条论证链：哪条前提、引用哪条论证、引用是否解析、目标结论；
- 跨案例共用的证据 id；同一 id 在不同论证里内容不一致时列为证据冲突并算问题；
- 已提交记录的漂移：有 `.geoarg/registry/` 的案例重跑 `verify`，输入、引擎、判决或论证链变化都会报出来；
- 问题汇总与工作区结论；有问题时命令非零退出。

它不改任何案例，也不重算论文组结论；它是“这组论证彼此是否自洽”的检查，不是新的判决。

## 追加式台账

`commit` 除原子写 `.geoarg/registry/<claim>.json` 外，还往 `.geoarg/ledger.jsonl` 追加一行 `{schema_version: geoarg/ledger/0.3, kind: commit, claim_id, created_at, record_sha256, verdict, rule_version, engine_sha256, prev, sha256}`，把提交串成链。`attest` 与 `anchor` 追加 `kind: attestation` / `kind: anchor` 的条目；`verify` 检查链的 `prev` 链接、最新 `commit` 是否就是当前 registry 记录、以及存在的 `attestation` / `anchor` 是否仍匹配。台账仍在案例目录内，重跑 `commit` 仍会追加新链；它证明“提交历史未被悄悄改写”，不证明“没有伪造提交”。要防伪造，每行带一个 `sha256`（本行正文的哈希），`prev` 指向上一行的 `sha256`；0.1/0.2 旧行没有 `sha256`，读取时按 record_sha256 兼容。用 `anchor` 把台账头带到仓库外。

## 接地门

LLM 最常见的地质错误不是推理错，是把没写的话写成引文。接地门把这一步从“模型自觉”变成“脚本比对”：

1. 转录级证据必须写 `source_locator`（页码 + 原文句子）。
2. `geoarg ground --source` 打开源文档（PDF、DOCX、HTML、Markdown、纯文本），把句子规范化后与整份文档的文本比对（跨页引文也能接地）；页码语义只对 PDF 成立，其他格式的引文都记在第 1 页。
3. 结果四态：`grounded`（原页找到）、`page-mismatch`（找到但页码错）、`not-found`（编的）、`not-groundable`（PDF 没有文本层，或源文档没有可读文本）。不做 OCR：扫描件需要先自己转成文字。
4. `check` 与 `commit` 拒绝“accepted 但未接地”的转录级证据；有未接地引文时 `ground` 默认非零退出；台账摘要进 registry，改引文会被 `verify` 抓出来。台账同时记下源文档格式与路径；源文件被换掉后 `check` 报 `source document changed since grounding`；`verify` 比对的是记录里已存的接地台账摘要，不重新读源文件。

验收率 = `grounded / drafted`。它和 `n_eff` 是两个维度：一个说证据有几条独立线，一个说引文有几条确实存在。这道门只证明“这句话在源文件里”，不证明“这句话支持这条前提”；后者是审计的事。

## 设计原则

1. **确定性在脚本，判断在模型。** 判决、独立性和可撤回条件由代码算；模型只做它擅长的拆分、解释和报告。
2. **契约即接口。** 三个 YAML 文件是人和脚本共同读的边界，字段与枚举见 [contract-fields.md](skills/geology/geo-arg-register/references/contract-fields.md)。
3. **判决可重算。** `commit` 记录输入哈希与引擎哈希，任何改动都会在 `verify` 里暴露。结论可以错，台账不能含糊。记录本身可重写，所以它证明的是“可复核”，不是“不可伪造”。
4. **满足状态要检验背书。** cp 的 `holds`、判废条件的 `refuted`、蕴含的 `passed` 都必须有一个通过的检验；没有的话引擎把它列为 `unbacked`，判决停在 `UNDETERMINED`，`commit` 拒绝提交。
5. **`unknown` 是合法状态。** 契约不逼你填置信度，它逼你说清楚“缺什么检验”。
6. **缺口是一等公民。** 填不进契约的东西写进 `gaps`，标 `blocking`，它比假装表达完整更有用。
7. **引文要落地。** 转录级证据必须带原文锚点并过接地门；未接地的引文不得保持 `accepted`。
8. **能绑定就绑定。** 检验结果能写进 `result` 与 `pass_rule` 时，状态由引擎算，不靠手填；手填只留给无法结构化记录的结果。
9. **论文结论取最弱一条。** 一组主张的联合结论不高于其中最弱的一条；可选主张不参与聚合。
10. **交付物可绑定，台账头可带出仓库。** `attest` 把报告/卡片/评述绑到提交记录，`anchor` 把台账头写成可对外保管的检查点；仓库提供检查所需的字节，不冒充时间戳机构。

## 目录结构

```
geo-argument-skills/
├── skills/geology/            # 两个技能
│   ├── geo-arg-register/      #   填契约
│   └── geo-arg-audit/         #   审独立性 + 判别力 + 链
├── docs/geology/              # 中文使用页
├── docs/prior-art.md          # 信任层可借鉴的既有机制（英文）
├── scripts/geoarg/            # 确定性引擎
│   ├── _schema/               #   随包 JSON Schema（8 个）
│   └── _skills/               #   随包技能副本（wheel 构建时生成，仓库里没有）
├── scripts/tests/             # 单元测试
├── examples/south-atlantic/   # 教学案例（占位引用）
├── examples/paper-demo/       # 合成 PDF + 已提交接地台账
├── examples/workspace-demo/   # 论证链与工作区演示（两个案例 + workspace.yaml）
├── examples/domain-demo/     # 领域包示例（domain.yaml 扩展枚举）
├── examples/domain-packs/    # 三个可复用领域包（geochronology/stratigraphy/tectonics）
└── .claude-plugin/plugin.json # 插件清单
```

## 案例

`examples/south-atlantic` 是一条板块重建论证的完整契约：3 条前提、5 个判废条件、2 个蕴含、7 个检验。它的引用是占位，目的是让你看到契约的形状，而不是让你引用它的结论。预期行为：`check` 干净、判决 `UNTESTED`、`n_eff = 1.2 / 3`、`hit-set` 列出 13 条单事件结果。

`examples/paper-demo` 是接地门的演示：一份合成 PDF（三页，含三条引文），三条转录级证据带原文锚点，台账已提交。预期行为：`geoarg ground` 验收率 1.000，三页文本层可读，`check` 干净。

`examples/workspace-demo` 是论证链与工作区的演示：两条论证（`basement-age` 与 `cover-age`）用 `workspace.yaml` 连起来，`cover-age` 的派生前提指向 `basement-age`。预期行为：`geoarg judge examples/workspace-demo/cover-age` 为 `UNTESTED`，派生前提显示为「被引用的论证未检验」；`geoarg workspace examples/workspace-demo` 显示一条已解析的链，结论「结构一致」。这两个案例未提交，因此没有登记表与锚点。

`geoarg workspace examples` 会列出全部示例案例（paper-demo、south-atlantic、workspace-demo 的两个案例、domain-demo、domain-packs/geochronology/age-bracket）：`cover-age` 会向上找到 `workspace-demo/workspace.yaml`，所以会出现一条已解析的链；改用 `examples/workspace-demo` 为根可看聚焦的两个案例视图。它还会检查跨案例共用的证据 id、同一 id 的内容冲突，以及有提交记录时的漂移；只读，不改任何案例。

对已提交的案例，跑一次 `geoarg attest <case> --judgment-file <text>` 把交付物绑到记录，再跑 `geoarg anchor <case>` 把台账头写成检查点；两者之后都由 `verify` 检查。

## 降低上手成本（1.3）

三条路径，任选：

1. 已有论文或草案：`geoarg adopt notes.md --out my-case` 把提纲变成可校验草稿。Markdown 只需四个小节（`Claim`、`Premises`、`Evidence`、`Tests`），条目以 `- P1: ...` 开头；证据条目下可写 `source`、`page`、`quote`。
2. 只有问题：`geoarg patterns` 看随包模式，`geoarg new my-case --pattern geochronology-age-bracket` 生成骨架。
3. 起好之后：`geoarg check my-case --profile draft --explain`。draft 档只把"还没写完"的字段降为警告（scope、audit、coverage 等），引用与枚举错误仍然报错；`--explain` 给每条问题一句修复提示；填完 TODO 再跑严格档。

草稿里的每个 `TODO` 都是留给作者的问题，不是引擎猜测的答案。`adopt` 不推断证据，缺证据时生成占位记录；`new` 不改写模式里的结论，只替换 id、标题、主张与日期。

## 决策价值（1.3）

`geoarg impact <case>` 回答"哪条数据真的在支撑结论、再做什么能改变它"，不估计概率，也不给主张打分：

- 留一法：逐条拿掉证据或测试重算，分类为 `decisive`（结论变了）、`backing`（结论不变但理由变了）、`redundant`（没有影响）、`untapped`（测试还没有挂到任何声明状态）。
- `--assume test:T1=passed --assume cp:CP1=holds`：模拟"数据到手且解释成立"。测试结果与声明状态要一起给，因为引擎只承认被测试支撑的状态。
- `--add-evidence new.yaml`：把尚未采到的证据追加到副本里，看结论与独立性是否变化（不要求先有 grounding）。
- 输出还列出剩余阻塞（hard/soft/pending、unbacked、未跑的关键测试）与独立性变化。
- `--workspace <dir>` 把同一批待采证据套到工作区每个案例，显示"一次测量会同时影响哪几条主张"。
- 语言：`--lang en|zh`；`--out` 写 Markdown；`--json` 输出机器可读字段。

限制：impact 只重算引擎已有的规则，声明的状态仍被当作解读判断；留一法一次只动一条记录，不衡量记录之间的相互作用；它不核查数据本身是否可靠。

## HTML 报告（1.4）

`geoarg report <case> --format html` 生成单文件 `report.html`：内嵌样式、无外部资源，浏览器直接打开或打印成 PDF；每个章节可折叠（原生 `<details>`），证据、引文与审计信息都在同一页。`geoarg workspace <dir> --format html` 生成同样风格的工作区页面（多案例、论证链、共用证据、冲突、漂移）。

HTML 与 Markdown、Word 一样只是渲染：它不改判决，也不加校验；`attest` 默认绑定 `report.html`，所以交付的页面同样处在 commit → attest → anchor 的信任链里。渲染器对作者文本做 HTML 转义，不执行页面中的任何脚本。

## 领域包、字段建议与表单编辑器（1.6）

`domain.yaml` 让同一个引擎服务不同的地质子领域：在案例目录（或它的某个上级目录）放一份 pack，就能为该案例扩展 11 组枚举值（domain、profile、claim kind、检验类型、蕴含类型、cp 类型、判废类型、证据类型、校验级别、独立性类别、缺口类型）。最近的 pack 生效；内置值永远保留，pack 只能加值，不能改语义。`geoarg domains <case>` 打印当前生效值；`geoarg check` 用扩展后的枚举做校验，schema 只检查形状。pack 的字段建议是作者的检查清单：`advise` 只打印缺什么和为什么，不改变判决，也不提交记录。

```yaml
schema_version: geoarg/domain/0.1
name: quaternary
enums:
  domains: [quaternary-geology]
  claim_kinds: [age-model]
  method_types: [tephrochronology]
```

`commit` 会记录 pack 的摘要；提交后改动 pack，`verify` 报 `domain pack changed since commit`。完整示例见 `examples/domain-demo`。

1.6 起 pack 还可以携带字段知识：`default_profile`（默认 profile 与理由）、`patterns_dir`（随包模式目录，默认 `patterns/`）、
`test_suggestions`（按 claim kind 建议检验方法与理由）、`evidence_families`（期望证据族与独立性类别）、`grounding`（接地格式与提示）。
这些字段进入 pack 摘要，因此改动后同样会被 `verify` 报出。`geoarg patterns <case>` 会列出随包模式；`geoarg new` 在 pack 目录内
会优先使用该 pack 的模式；`geoarg advise <case>` 输出上面的检查清单。三个可直接使用的 pack 在 `examples/domain-packs/`。

`geoarg edit <case>` 启动一个只监听 127.0.0.1 的本地表单编辑器（无外部依赖、令牌保护、原子保存、保存后立即校验），可编辑 claim、推理、前提、条件、判废条件、蕴含、证据与检验；它不新增信任层级，提交门槛不变。

## 可移交的证据包（1.7）

`geoarg package <case> --out <dir>` 把一个已提交、已证明的案例折叠成一个可以离开本机的目录：

- `argument.yaml` / `evidence.yaml` / `test.yaml` 与 `.geoarg/` 下的记录、台账、证明、锚点、接地台账；
- 证明绑定的产出与判断段落，外加一份按当前语言生成的自包含 `report.html`；
- `manifest.json`：每个文件的 SHA-256、记录/台账头/锚点/证明摘要、引擎版本与规则版本；
- `ro-crate-metadata.json`：最小 RO-Crate 1.1 元数据，方便仓库归档；
- `README.md`：这份包是什么、怎么核对、边界在哪里。

证据包本身仍是一个可用的案例目录（同一引擎版本）：`geoarg check .`、`geoarg verify .` 可以直接运行。`geoarg verify-package <dir>` 不信任清单：它重算全部摘要，重新加载契约校验并重算判决，核对记录摘要、台账自哈希链、证明与锚点的交叉引用、已绑定产出的字节；任何不一致都返回非零并列出问题。

边界：摘要只证明字节一致，不证明数据为真；包不替代外部时间戳或签名服务；跨引擎版本读取时 `verify-package` 会给出版本警告，判决重算仍以包内契约为准。

## 论证图（1.8）

`geoarg figures <case>` 生成四张 SVG：论证状态（各条前提/条件/判废条件/蕴含分别有多少阻断、削弱、待定、满足）、独立性压力（报告的 n_eff 随假定 pairwise rho 的变化）、决策价值（留一法消融的证据类别，以及检验的判别力对成本）、证据覆盖与可检测性。图直接按 88 mm 或 180 mm 落地宽度绘制，落在纸面后的字号不低于 6 pt，并配有语义色板与灰度检查。

`geoarg report <case> --format html` 会自动内嵌 `<case>/figures/*.svg`，页面仍是单个自包含文件；`geoarg package <case> --include-figures` 把图放进证据包的 `files/figures/` 并写进 manifest。图形只是解释状态的呈现：不进入 `engine_digest`，不改变判决，也不能替代证据。规则与取舍见 `docs/figures.md`；部分视觉规则借鉴 [nature-figure-craft](https://github.com/Alto-R/nature-figure-craft)（代码 MIT、文档 CC BY 4.0），未复制其代码，也未新增绘图依赖。

## 引用核验（可选，1.10）

引用核验是独立于信任链的可选层，`check` / `commit` / `verify` 默认不联网、也不要求它。

- `geoarg sources <case>`：离线列出每条带 citation 的证据是否有引文片段、案例是否有接地源；`--require-quote` / `--require-source` 可让检查以非零退出。
- `geoarg references <case>`：从 citation 中提取 DOI/PMCID/PMID/arXiv，向 Crossref 和 Europe PMC 核验存在性、年份与第一作者，能报告时也报告撤稿；结果写入 `.geoarg/references.json` 快照，`--offline` 只读缓存，`--require-verified` 只在全部 verified 时通过。

状态分 verified / mismatch / not-found / retracted / unverifiable / no-identifier。它核验"文献存在且元数据对得上"，不核验"内容是否支持主张"；图书、报告、地区期刊常常只能 unverifiable，这是覆盖边界，不是项目故障。详见 `docs/references.md`。

引用核验是给作者和审阅者的准入提示，不改变判决，也不构成"引文为真"的证明。

## 反面证据绑定（1.10）

`defeaters[]` 与 `entailments[]` 可以各带一个 `counter_evidence` 字段，列出支撑这条反面证据或失败推论的证据 id：

```yaml
inference:
  defeaters:
    - id: D1
      type: undercutting
      severity: fatal
      state: established
      test_ref: T1
      counter_evidence: [ev.surovell.resampling]
```

这个字段只影响报告与决策价值，不改变判决规则：

- `independence` 额外给出反面证据自身的 `counter` 块（条数、n_eff、证据族），说明几条反证之间是否互相独立；
- `impact` 的留一法把被这些字段引用的证据标为 `counter: true`，不再误判成 `unused`；
- `report` 的反面证据表与推论表各多一列「反面证据记录」；
- `geoarg check` 校验 id 存在且行内不重复；字段可选，不填时行为与 1.9 相同。

## 局限（v1.12）

- **不验证结论的真假**，只验证论证的结构、检验状态与引文是否落地。地质学的真值不在这个仓库的射程内。
- **契约有成本。** 填一条论证需要几条到几十条前提，这是这个方法的代价，也是它比“直接写结论”慢的原因。
- **判决是“自洽的台账”，不是“证据自动成立”。** `hold` / `refuted` / `passed` 必须由通过的检验背书，但检验的 `status` 本身仍是契约里填的；引擎不读实验数据，也不重跑检验。它能抓出“没做检验却声称成立”，抓不出“检验做了但报错结果”。
- **`hit-set` 只枚举单事件路径。** 多个降级判废条件同时成立的情况需要在报告里显式写出。
- **相关系数是估计。** `n_eff` 的 rho 表是先验，不是测量值。报告时必须带上假设。
- **接地门只覆盖 accepted 的转录级证据。** 测量级与解释级证据不做引文比对；门也只比字符串，不做 OCR，规范化后找不到就算 `not-found`。
- **论证链的解析范围有限。** `derived` 前提只在最近的 `workspace.yaml`、相对/绝对案例路径或同级目录里解析；跨仓库、跨机器的引用不做搜索，找不到或成环时 `commit` 拒绝提交，而不是给一个乐观判决。
- **链只做相邻状态继承。** 目标论证的结论按 `SUPPORTED / SUSPENDED / UNTESTED / UNDETERMINED / DEFEATED` 映射成前提状态，不重算证据独立性；同一证据 id 被两条论证复用时，工作区只报内容是否冲突，不会自动给两条论证降权。
- **工作区漂移只覆盖已提交记录。** 没有 `.geoarg/registry/` 的案例只能看结构问题；证据名录按内容哈希判“同 id 不同内容”，不证明来源同一。
- **追加式台账只防本地改写。** 整份 `.geoarg/ledger.jsonl` 仍可被整体替换；1.2 之前的旧行没有 `sha256`：改动它们的 `record_sha256` 会破坏下一行的 `prev`，但改动旧行的其它字段不会被发现；1.2 起的行逐行可校验。要防伪造，把 `anchor.json` 带出仓库并用 `verify --anchor <file>` 对照。
- 重新 `commit` 只会替换记录；如果已经 `attest` 或 `anchor`，还要按 commit → attest → anchor 重跑，`verify` 才会重新通过。
- 绑定集默认是 `report.*` 与 `card.*`（含裸 `report.md`、`card.md`），也可以显式 `--include`；judgment 用 `--judgment-file` 绑定。
- **schema 是第二意见。** 8 个 schema 随 wheel 发布，用来校验文档形状；权威仍是 `contract.validate`，两者冲突以引擎为准。
- 只把 `anchor.json` 抄出去还不够，还要用 `verify --anchor <file>` 去读它；普通 `verify` 只检查本地锚点与台账自洽。
- **结果绑定只覆盖能写成规则的结果。** 二值判断、区间估计、相对变化可以交给引擎；涉及统计模型选择、多重比较校正、主观评分的检验仍只能手填 `status`，引擎不替你做统计推断。
- **`migrate` 只改版本行，不改语义。** 旧契约里写成字符串的 `result.value`、缺失的 `pass_rule` 需要人工补齐；迁移后会先被 `check` 指出来。
- **论文组结论是“最弱一条”。** 聚合只做保守下界，不做概率合成，也不替代编辑对主张重要性的判断。
- **多格式接地不做版面分析与 OCR。** DOCX 只读段落与表格文字；HTML 只取可见文本节点；扫描 PDF 与图片没有文本层就算 `not-groundable`，需要先自行转写成可读文本。
- **交付物不另造术语。** 卡片与报告引用作者自己的陈述和普通语言；`profile` 只标领域，不改变用词、判决、`n_eff` 或验收率。机器值（`verdict`、`n_eff`、`status`）保留在台账与审计块里。
- **评述由模型撰写。** `card` 顶部的评述不是引擎生成；引擎只给数字与理由项。审计块记录其 sha256，但读卡的人仍需自己判断这段文字是否忠实。
- **度量范围小。** 独立性与判别力的完整研究（语料、专家标注、历史回测）不在本仓库内。

- draft 档只是写作期 lint：它不降低提交门槛，`commit` 仍按严格档校验。

## 与上游 skill 生态的关系

布局、`SKILL.md` 约定、`docs/` 页面结构和 `plugin.json` 清单借鉴了 [mattpocock/skills](https://github.com/mattpocock/skills) 的组织方式；内容与引擎是这个仓库自己的。把本仓库的 `skills/` 目录链接进 `~/.claude/skills` 即可被支持该格式的 Agent 加载：

```bash
ln -s "$PWD/skills/geology" ~/.claude/skills/geology   # macOS / Linux
```

## License

MIT
