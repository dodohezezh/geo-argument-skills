# geo-arg-register（登记一条地质论证）

## 它做什么

把一条地质结论写成可机检的契约：主张、前提、凭据（warrant）、成立条件（ceteris paribus）、判废条件（defeater）、蕴含（entailment）、证据台账、检验台账、以及一张“契约表达不了什么”的缺口表。契约写完后由 `geoarg` 计算判决，而不是由写契约的模型自我评价。

转录级证据还要过一道接地门：`geoarg ground <case> --source <paper>` 把每条引文与源 PDF 的文本层比对，只有 `grounded` 的引文才能保持 `accepted`。有未接地引文时 `ground` 默认非零退出；这道门防的是“把没写的话写成引文”，不负责判断引文用得对不对。

## 什么时候会用到

- 有一句地质结论，想记录、辩护或请人评审。
- 想知道“这条结论到底依赖哪几条前提、什么证据能推翻它”。
- 一篇论文、一份报告或一张图里的结论会被别人引用，需要留下可追溯的依赖结构。
- 在写综述、摘要或项目书，要把“多条独立证据支持”这句话落到实处。

## 常见问题

**必须写成 YAML 吗？** 是。契约是给人看、给脚本读的，YAML 两者都照顾。三份文件分别是 `argument.yaml`、`evidence.yaml`、`test.yaml`。

**前提写几条合适？** 从 3 到 7 条开始。写不出 3 条通常说明主张太模糊；写到 20 条说明该拆成两个契约。

**判废条件写不出来怎么办？** 那就说明这条论证还没有可检验的形状。先写“什么观察会让我撤回这句话”，再倒推成判废条件。

**条件写着 holds、检验还没跑，能算成立吗？** 不能。cp 的 `holds`、判废条件的 `refuted`、蕴含的 `passed` 都要有一个已通过且判别力不为 `none` 的检验背书，否则 `geoarg judge` 把它列为 `unbacked`，判决停在 `UNDETERMINED` 或 `UNTESTED`，`geoarg commit` 拒绝提交。

**测试还没有结果，能提交吗？** 能。`unknown` 是合法状态，判决会给出 `UNTESTED`，并列出“现在什么结果能撤回它”。这正是契约的用处。

**论证属于哪个领域要写吗？** 可以写，但只是元数据。`argument.yaml` 的 `profile.primary`（`general-geology`、`geochronology`、`planetary-geology`、`tectonics`）会在交付物页头标出领域；可带 `secondary` 与一行 `rationale`。省略则写“未声明”。它不选择术语、不改变用词，也不影响判决、`n_eff` 或验收率；一条论证一个领域，不按论文定。

**模型能自己填契约吗？** 能填，但每一步都要落到可核对的证据和检验上。填不进去的地方写进 `gaps`，这是设计的一部分，不是失败。

**引文会被检查吗？** 会。转录级证据必须写 `source_locator`（页码加原文句子），`geoarg ground <case> --source <paper>` 与源文件（PDF、DOCX、HTML、Markdown 或纯文本）比对后写台账。`not-found` 说明引文是编的，记录必须改成 `disputed`；`page-mismatch` 说明页码错了，改页码而不是改引文。扫描版 PDF 没有文本层，会得到 `not-groundable`，先 OCR 或把该记录降为解释级；非 PDF 格式的页码统一记为第 1 页。

**接地通过就等于引文用对了吗？** 不等于。接地只证明这句话确实在源文件里；它是否支持这条前提，是审计要回答的问题。

**检验结果能写进契约吗？** 能。`test.yaml` 里给一条检验写 `result`（`value`，可带 `uncertainty`、`n`、`data_ref`）和 `pass_rule`（`ge`、`le`、`between`、`within_ci`、`ratio`），引擎就会算出 `passed` / `failed` / `inconclusive`；算出的状态优先于手填的 `status`，两者不一致时 `judge` 报警。`commit` 记录算出的状态，改了 `result` 或 `pass_rule` 而没有重新提交，`verify` 会报 `computed test statuses changed`。写不成数值的检验仍手填 `status`。

**一篇论文有多条主张怎么办？** 在上一级目录写 `bundle.yaml`（`schema_version: geoarg/bundle/0.1`、`id`、`title`、`claims` 列表；每项 `case` 是相对目录，可带 `label` 与 `required`）。`geoarg bundle <dir>` 逐条运行 `judge`，必需主张按“成立 < 无法判定 < 未检验 < 被削弱 < 被推翻”取最弱一条作为论文组结论；可选主张只列出，不参与聚合。缺目录或不合规的案例会列为 problem，不会悄悄算进结论。

**一条论证的前提来自另一条论证怎么办？** 把前提标成 `derived`，用 `argument_ref` 指向目标论证，并在案例目录上方最近的 `workspace.yaml` 里登记目标（`arguments` 列表，每项含 `id` 与 `case`），或直接写相对/同级案例路径。`geoarg judge` 会解析这条引用，把目标论证的结论映射成前提状态：目标成立则前提成立；目标被削弱、无法判定或未检验则前提挂在待定；目标被推翻则算硬问题。引用找不到或论证链成环时，`commit` 拒绝提交。

**一组相关论证怎么一起检查？** `geoarg workspace <dir>` 扫描目录下每个案例：判决、论证链是否解析、跨案例共用的证据 id、同一 id 内容不同的证据冲突、已提交记录的漂移；有问题时非零退出。它不改任何案例，也不替代论文组结论。

**旧契约怎么升级？** `geoarg migrate <case>` 只把三个 YAML（或 `bundle.yaml`、`workspace.yaml`）的 `schema_version` 行改到当前版本，其余字节不动；`--dry-run` 只看不改。旧式字符串 `result.value` 和缺失的 `pass_rule` 需要人工补齐，迁移后 `check` 会指出来。

**交付物和提交记录绑在一起吗？** 交付前运行 `geoarg attest <case> --judgment-file <text>`，它把报告、结论页和评述文本的 sha256 绑到当前提交记录上，写 `.geoarg/attestation.json` 并追加一条台账。之后改了任一份绑定文件而没重新 `attest`，`verify` 会报 `deliverable changed since attestation`；换了引擎而没重新 `attest`，会报 `engine changed since attestation`。attestation 只证明字节一致，不证明文字写得对。

**台账能证明提交没被改过吗？** 台账在案例目录内，能发现链被改，但替换整个台账并重算并不难拦。`geoarg anchor <case>` 把台账头写成 `.geoarg/anchor.json` 检查点；只有把这个文件复制到案例目录之外（或交给外部时间戳服务）保管，才能对“某个时间点的台账头”作证。本地锚点不等于时间戳。

## 它生效的标志

- `geoarg check` 返回 0，`geoarg judge` 打印判决。
- 每条已接受的转录级引文都有 `grounded` 台账，报告里写着验收率。
- 另一个人只看契约，能说出“这条论证依赖哪五条前提、哪三个条件”。
- 报告里出现判废条件及其检验，而不是只有支持性证据。
- 契约里声明了论证所属领域，或明确说明省略。
- 检验有数值结果时，契约里写了 `result` 与 `pass_rule`，判决用的是引擎算出的状态。
- 论文有多条主张时，目录里有 `bundle.yaml`，组结论取必需主张里最弱一条。
- 出现了至少一条写进 `gaps` 的“契约表达不了”的东西。
