# paper-demo：接地门演示

这个案例演示 v0.2 的接地门：转录级证据必须带原文锚点，引文与源 PDF 比对通过后才能保持 `accepted`。

## 文件

| 文件 | 内容 |
| --- | --- |
| `paper.pdf` | 合成的三页 PDF，用于测试。里面的句子是编的，不是真实文献。 |
| `argument.yaml` | 一条 `timing` 论证：不整合面是 12.3 Ma 的层序界面。含 3 条前提、3 个成立条件、2 个致命判废条件、1 个降级判废条件、2 个蕴含。 |
| `evidence.yaml` | 3 条转录级证据，各带 `source_locator`（页码 + 原文句子）。 |
| `test.yaml` | 3 条检验：页内文本核对、区域可追索性、下伏地层年龄。 |
| `.geoarg/ground/C1.json` | 已提交的接地台账：3 条引文全部 `grounded`，验收率 1.0。 |

## 预期行为

```bash
geoarg ground examples/paper-demo --pdf examples/paper-demo/paper.pdf
geoarg check examples/paper-demo
geoarg judge examples/paper-demo
```

- `ground`：`pypdf` 读出 3 页文本层，3 条引文全部在原页找到，`acceptance rate 1.000`。
- `check`：0 个问题。
- `judge`：`UNTESTED C1 (geoarg/0.2)`，因为三条闸门检验都还没有结果。

## 故意留的坑

把 `evidence.yaml` 里任意一条 `quote` 改掉一个词，再跑 `check`：会得到 `not grounded (stale ledger or changed quote)` 的问题；重跑 `ground` 会把它标成 `not-found`。把 `page` 改成 2，重跑 `ground` 会得到 `page-mismatch`。这两种失败对应两种不同的错误：编造和引错位置。

## 说明

`paper.pdf` 是脚本生成的合成文件，不含任何真实出版物内容。它的用途是让接地门在没有真实论文时也能端到端跑通；真实论文的验收测试在拿到 PDF 之后单独做。
