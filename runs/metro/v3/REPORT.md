# 生成报告

## 最终产物

- 主图：`metro.svg`
- 主图预览：`preview.png`
- 地理索引图：`geographic_inset.svg`、`geographic_inset.png`
- 数据文件：`geography.json`、`corridors.json`、`line_plan.json`、`network.json`
- 规划说明：`CITY_PLAN.md`、`CORRIDOR_PLAN.md`、`NAMING_RULES.md`
- 验证脚本：`validate_network.py`、`score_layout.py`、`validate_svg.py`

## 核心指标

- 城市：澜海市 / Lanhai
- 可见线路：18 条
- 唯一车站：192 座
- 双语车站：192 座
- 换乘站：43 座
- 四线换乘站：2 座
- 跨澜江线路：7 条
- 环线：1 条
- 半环线：1 条
- 支线：2 条
- 市域快线：2 条
- 机场服务线路：4 条
- 建设中线路：1 条

## 布局验证

- 非八方向线段：0
- 最大角度偏差：0.0°
- 非换乘交叉：10
- 核心区非换乘交叉：6
- 过长线段：0
- 最大线段长度：500 px
- 平均快线站距：246.03 px

## 标签验证

- 检测方法：Playwright Chromium / Google Chrome `getBBox()`
- 标签碰撞：0
- 中文-中文碰撞：0
- 英文-英文碰撞：0
- 中文-英文碰撞：0
- 标签压站点：0
- 标签压图例：0
- 标签越界：0
- 最小中文字号：18 px
- 最小英文字号：10 px
- 最小换乘站中文字号：20 px
- 最小换乘站英文字号：11 px

## 迭代记录

- 骨架候选：4 个，否决 3 个，采用 `skeleton-3`。
- 完整候选：2 个，首轮用于标签盒审查，第二轮作为最终图。
- 修复过的问题包括：同名异地站、非八方向短折线、铁路枢纽覆盖不足、机场地理距离偏差、核心区非换乘交叉过多、标签 BBox 检测误把引导线计入文字盒。

## 最终结论

`validate_network.py`、`score_layout.py`、`validate_svg.py` 均通过。`metadata.json` 的 `result.status` 已更新为 `completed`。
