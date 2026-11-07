# GeoArg 报告：Paper demo: a dated unconformity from a source PDF

- 主张: C1 (timing, L1)
- 陈述: The basal unconformity is a 12.3 Ma sequence boundary.
- 作者声明的领域: 年代学
- 结论: 未检验
- 规则版本: geoarg/0.7

## 为什么是这个结论
还没有任何检验取得结果。这不是支持弱，而是没有信息。
足以推翻结论的问题:
- 无
会削弱结论的证据:
- 无
还没有结果的问题:
- CP1：The dated grains come from the surface itself, not from reworked material；尚未检验。
- CP2：No fault repeats or omits the dated interval；尚未检验。
- CP3：The dated sample sits within the mapped surface everywhere the claim extends；尚未检验。
- D1：The dated grains are detrital and predate the surface；尚未检验。
- D2：The mapped surface is a facies boundary, not a time surface；尚未检验。
- E1：The surface is mappable between the two measured sections；尚未检验。
- E2：No younger unit sits below the mapped surface；尚未检验。

## 前提

| 编号 | 状态 | 说明 |
|---|---|---|
| P1 | 证据已接受 | A zircon U-Pb age of 12.3 Ma dates the basal unconformity. |
| P2 | 证据已接受 | The unconformity is traceable across the basin for 180 km. |
| P3 | 证据已接受 | Bioturbated silts above the surface record a marine flooding event. |

## 必须成立的条件

| 编号 | 状态 | 检验 | 说明 |
|---|---|---|---|
| CP1 | 尚未检验 | T1 | The dated grains come from the surface itself, not from reworked material. |
| CP2 | 尚未检验 | T2 | No fault repeats or omits the dated interval. |
| CP3 | 尚未检验 | T3 | The dated sample sits within the mapped surface everywhere the claim extends. |

## 反面证据

| 编号 | 状态 | 严重程度 | 检验 | 反面证据记录 | 说明 |
|---|---|---|---|---|---|
| D1 | 尚未检验 | 足以单独推翻 | T1 | - | The dated grains are detrital and predate the surface. |
| D2 | 尚未检验 | 足以单独推翻 | T3 | - | The mapped surface is a facies boundary, not a time surface. |

## 必须成立的推论

| 编号 | 状态 | 风险 | 检验 | 反面证据记录 | 说明 |
|---|---|---|---|---|---|
| E1 | 尚未检验 | 中 | T2 | - | The surface is mappable between the two measured sections. |
| E2 | 尚未检验 | 高 | T3 | - | No younger unit sits below the mapped surface. |

## 证据之间有多独立
- 独立证据：约 2.57 条 / 3 条记录（平均相关 0.083）
- 证据领域：field-mapping, geochronology, sedimentology

## 引文与原文是否一致
来源：paper.pdf（3 页，185 字符，文本层：yes）。
引文与原文一致的比例：1.0（3/3 条草拟引文已核对）。

| 记录 | 状态 | 声明页码 | 实际页码 |
|---|---|---|---|
| ev.dated.zircon | 与原文一致 | 1 | 1 |
| ev.extent.mapping | 与原文一致 | 2 | 2 |
| ev.flood.silt | 与原文一致 | 3 | 3 |

## 哪些结果会改变结论
当前结论：未检验。下面每一行都是一种单独就会改变结论的情况：

| 如果发生什么 | 检验 | 区分力 | 成本 | 结论会变成 |
|---|---|---|---|---|
| 如果 CP1（The dated grains come from the surface itself, not from reworked material）不成立 | T1 | 高 | 4 | 已被推翻 |
| 如果 D1（The dated grains are detrital and predate the surface）成立 | T1 | 高 | 4 | 已被推翻 |
| 如果 CP3（The dated sample sits within the mapped surface everywhere the claim extends）不成立 | T3 | 中 | 2 | 已被推翻 |
| 如果 D2（The mapped surface is a facies boundary, not a time surface）成立 | T3 | 中 | 2 | 已被推翻 |
| 如果 E2（No younger unit sits below the mapped surface）不成立 | T3 | 中 | 2 | 已被推翻 |
| 如果 CP2（No fault repeats or omits the dated interval）不成立 | T2 | 中 | 3 | 已被推翻 |
| 如果 E1（The surface is mappable between the two measured sections）不成立 | T2 | 中 | 3 | 证据被削弱 |
| 如果 P1（A zircon U-Pb age of 12.3 Ma dates the basal unconformity）的证据被撤回 | - | - | - | 已被推翻 |
| 如果 P2（The unconformity is traceable across the basin for 180 km）的证据被撤回 | - | - | - | 已被推翻 |
| 如果 P3（Bioturbated silts above the surface record a marine flooding event）的证据被撤回 | - | - | - | 已被推翻 |
_只列单事件结果；多条削弱性反面证据同时成立的情形没有列出。成本取作者声明的最低检验成本，单位同 test.yaml。_

## 这套论证没能表达的问题

| 类型 | 严重程度 | 说明 |
|---|---|---|
| 表达不了 | 次要 | The contract cannot record how far the dated sample sits from the mapped surface. |

## 审计信息
- 输入文件 argument.yaml：079918f13df56bdedcb60bff81f87ae525300ad7924b547b723a449d522d4c97
- 输入文件 evidence.yaml：8a5580c39efa899bee53052f069f13a729ce571511f910659738684bcfc2e101
- 输入文件 test.yaml：7940e2cba6d44fabe74496b12363c7446711173337a8d99533d8499316f0e9cd
- 核对程序版本：3b2415433830ee27869f9512668114b0d2e7f431e40d6c04eab0d89ecc1a3554
- 引文核对记录：590d5f55828424228ba08fbf8a5b48acb067201fc2f7d2a5029b4f974b26e928
- 论证文件格式：geoarg/0.7
- 规则版本：geoarg/0.7
- 引文核对格式版本：geoarg/ground/0.3
- 作者声明的领域：年代学
- 评述：未提供
