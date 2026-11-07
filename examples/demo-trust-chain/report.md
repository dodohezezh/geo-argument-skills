# GeoArg 报告：Paper demo: a dated unconformity from a source PDF

- 主张: C1（时间关系；层级 L1）
- 陈述: The basal unconformity is a 12.3 Ma sequence boundary.
- 作者声明的领域: 年代学
- 结论: 未检验
- 规则版本: geoarg/0.7

## 为什么是这个结论
还没有任何检验取得结果。这不是支持弱，而是没有信息。
_层级由作者标注：L0 是定义，L4 是解释；它不改变本工具给出的结论。_
足以推翻结论的问题:
- 无
会削弱结论的证据:
- 无
还没有结果的问题:
- CP1：The dated grains come from the surface itself, not from reworked material。
- CP2：No fault repeats or omits the dated interval。
- CP3：The dated sample sits within the mapped surface everywhere the claim extends。
- D1：The dated grains are detrital and predate the surface。
- D2：The mapped surface is a facies boundary, not a time surface。
- E1：The surface is mappable between the two measured sections。
- E2：No younger unit sits below the mapped surface。

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

| 编号 | 状态 | 严重程度 | 检验 | 关联的反面证据 | 说明 |
|---|---|---|---|---|---|
| D1 | 尚未检验 | 足以单独推翻 | T1 | - | The dated grains are detrital and predate the surface. |
| D2 | 尚未检验 | 足以单独推翻 | T3 | - | The mapped surface is a facies boundary, not a time surface. |

## 必须成立的推论

| 编号 | 状态 | 不成立时的风险 | 检验 | 关联的反面证据 | 说明 |
|---|---|---|---|---|---|
| E1 | 尚未检验 | 中 | T2 | - | The surface is mappable between the two measured sections. |
| E2 | 尚未检验 | 高 | T3 | - | No younger unit sits below the mapped surface. |

## 证据之间有多独立
- 独立证据：约 2.57 条（共 3 条记录，平均相关 0.083）
- 证据领域：field-mapping, geochronology, sedimentology

## 引文与原文是否一致
来源：paper.pdf（3 页，185 字符，文本层：是）。
引文与原文一致的比例：1.0（3/3 条引文已核对）。

| 记录 | 状态 | 声明页码 | 实际页码 |
|---|---|---|---|
| ev.dated.zircon | 与原文一致 | 1 | 1 |
| ev.extent.mapping | 与原文一致 | 2 | 2 |
| ev.flood.silt | 与原文一致 | 3 | 3 |

## 哪些结果会改变结论
当前结论：未检验。下面每一行都是一种单独就会改变结论的情况：

| 如果发生什么 | 检验 | 区分力 | 成本 | 结论会变成 |
|---|---|---|---|---|
| 如果 CP1「The dated grains come from the surface itself, not from reworked material」不成立 | T1 | 高 | 4 | 已被推翻 |
| 如果 D1「The dated grains are detrital and predate the surface」成立 | T1 | 高 | 4 | 已被推翻 |
| 如果 CP3「The dated sample sits within the mapped surface everywhere the claim extends」不成立 | T3 | 中 | 2 | 已被推翻 |
| 如果 D2「The mapped surface is a facies boundary, not a time surface」成立 | T3 | 中 | 2 | 已被推翻 |
| 如果 E2「No younger unit sits below the mapped surface」不成立 | T3 | 中 | 2 | 已被推翻 |
| 如果 CP2「No fault repeats or omits the dated interval」不成立 | T2 | 中 | 3 | 已被推翻 |
| 如果 E1「The surface is mappable between the two measured sections」不成立 | T2 | 中 | 3 | 被反面证据削弱 |
| 如果 P1「A zircon U-Pb age of 12.3 Ma dates the basal unconformity」的证据被撤回 | - | - | - | 已被推翻 |
| 如果 P2「The unconformity is traceable across the basin for 180 km」的证据被撤回 | - | - | - | 已被推翻 |
| 如果 P3「Bioturbated silts above the surface record a marine flooding event」的证据被撤回 | - | - | - | 已被推翻 |
_只列单事件结果；多条削弱性反面证据同时成立的情形没有列出。成本取作者声明的最低检验成本，单位同 test.yaml。_

## 这套论证没能表达的问题

| 类型 | 严重程度 | 说明 |
|---|---|---|
| 表达不了 | 次要 | The contract cannot record how far the dated sample sits from the mapped surface. |

## 审计信息
_以下为核对用的哈希与版本号，读者可以跳过。_
- 输入文件 argument.yaml：caaa56649d6afb23cad1f14d8602db600edecf650f24be577f2232b1a42e8fa0
- 输入文件 evidence.yaml：ef3de3975fa549c932c4677f209888092e926953a5d47ae7ecc4912e241a9be9
- 输入文件 test.yaml：23814cde72ad0d165db1b54a3fda85746442945452664035f5bb1bde8eec9de8
- 核对程序版本：73f3bed2cdc5ff0b28198f6346470e380d9636363220999ef359364ec7132b35
- 引文核对记录：7201daa18ec0be3233ab5978f1b96a215291a4a3d2c721e3cc38d14c9496e3fe
- 论证文件格式：geoarg/0.7
- 规则版本：geoarg/0.7
- 引文核对格式版本：geoarg/ground/0.3
- 作者声明的领域：年代学
- 评述：未提供
