# paper-demo：引文核对演示

这个案例演示引文核对：转录级证据必须带原文锚点，引文与源 PDF 比对通过后才算核对通过、可以继续标记为 `accepted`。

## 文件

| 文件 | 内容 |
| --- | --- |
| `paper.pdf` | 合成的三页 PDF，用于测试。里面的句子是编的，不是真实文献。 |
| `argument.yaml` | 一条 `timing` 论证：不整合面是 12.3 Ma 的层序界面。含 3 条前提、3 个必须成立的条件、2 条反证（都是致命级）、2 条可检验推论。 |
| `evidence.yaml` | 3 条转录级证据，各带 `source_locator`（页码 + 原文句子）。 |
| `test.yaml` | 3 条检验：在第二个剖面重测该界面（区分力高，成本 4）、在剖面之间追索该界面（中，3）、核对采样点位置与界面高程（中，2）。 |
| `.geoarg/ground/C1.json` | 已提交的引文核对记录：3 条引文全部与原文一致，验收率 1.0。 |

## 预期行为

```bash
geoarg ground examples/paper-demo --source examples/paper-demo/paper.pdf
geoarg check examples/paper-demo
geoarg judge examples/paper-demo
```

- `ground`：`pypdf` 读出 3 页文本层，3 条引文全部在原页找到，`acceptance rate 1.000`。
- `check`：0 个问题。
- `judge`：`UNTESTED C1 (geoarg/0.7)`，因为三条检验都还没有结果。

## 故意留的坑

把 `evidence.yaml` 第一条的 `quote` 改一个词（例如把 `12.3 Ma` 改成 `12.9 Ma`），再跑 `check`：

```
PROBLEM: evidence ev.dated.zircon: grounding is stale (the quote changed since ground)
FAIL  C1  (1 problem(s))
```

重跑 `ground` 会把它标成 `not-found`，验收率降到 0.667，并返回非零退出码：

```
acceptance rate: 0.667 (2/3 drafted quotes grounded)
  not-found      ev.dated.zircon  page 1
```

把第一条的 `page` 从 1 改成 2，重跑 `ground` 会得到：

```
acceptance rate: 0.667 (2/3 drafted quotes grounded)
  page-mismatch  ev.dated.zircon  page 1 (declared page 2)
```

这两种失败对应两种不同的错误：编造引文和引错位置。

## 说明

`paper.pdf` 是脚本生成的合成文件，不含任何真实出版物内容。它的用途是让引文核对在没有真实论文时也能端到端跑通；真实论文的验收测试在拿到 PDF 之后单独做。

`examples/demo-trust-chain` 是同一份契约加已提交演示信任链的副本；本目录只保留契约
与接地台账（`.geoarg/ground/C1.json`），不包含 registry/ledger/attestation/anchor。
