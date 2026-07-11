# 宁沧轨道交通中英文命名规则

## 1. 适用范围与优先级

本规则用于 `network.json`、地理索引图、主 SVG、图例和报告。最终站名必须在 `network.json` 中以完整中文词组与完整英文词组逐条保存。禁止使用汉字到拼音的逐字映射表，禁止在 SVG 生成阶段临时翻译或修改站名。

优先级如下：

1. 本文件列出的锁定译名；
2. 城市正式公共设施和交通枢纽的规范译名；
3. 专有地名的规范汉语拼音；
4. 通名的统一英语译法。

## 2. 城市与自然地理锁定译名

| 中文 | 英文 | 说明 |
|---|---|---|
| 宁沧市 | Ningcang | 标题可写 Ningcang Metro；正文首次可写 Ningcang Municipality，不在站名中添加 City |
| 沧江 | Cangjiang River | 主河名称，全图固定 |
| 青溪 | Qingxi River | 重要支流 |
| 青岚湾 | Qinglan Bay | 海湾 |
| 白鹭洲 | Bailuzhou Island | 江心岛；站名若直接使用“白鹭洲”则写 Bailuzhou |
| 东沙岛 | Dongsha Island | 湾内岛屿 |
| 海隅岛 | Haiyu Island | 湾内岛屿 |
| 松月水库 | Songyue Reservoir | 饮用水源 |
| 云苍山 | Yuncang Mountains | 山系 |
| 西山生态保护区 | Xishan Ecological Reserve | 保护区 |
| 螺汀湿地 | Luoting Wetland | 港城生态缓冲区 |
| 青岚深水港 | Qinglan Deepwater Port | 港口设施 |
| 沧江邮轮港 | Cangjiang Cruise Terminal | 客运港 |

自然地理采用“拼音专名 + 英文通名”。同一实体在站名、区域标注和地理索引中不得出现第二套译法。

## 3. 拼音规则

- 使用不带声调的汉语拼音，首字母大写。
- 未建立正式英文名的专有地名采用连写拼音，如 `Ningcang`、`Songyue`；不得逐字加空格。
- 不采用逐字空格拼接：`Bai Lu Zhou`、`Chao Ping` 均不允许。
- 宁沧既有交通系统已为一批透明地名登记正式语义英文名；这些名称视为城市官方英文外名而非运行时自由翻译。例如潮平固定为 `Tidal Plain`、雨湖固定为 `Rain Lake`、西岭机场固定为 `West Ridge Airport`。未列入锁定表的专名仍优先用拼音。
- 姓氏聚落可将姓氏与通名连写为专名；最终一旦选定必须全图一致。
- 方位词若属于锁定的城市英文名，按锁定名称使用；公共设施的明确方位后缀翻译为 `North / South / East / West`。
- 拼音中若需要避免音节歧义可使用规范撇号，但不得随意加连字符。

## 4. 历史地名与传统构筑物

老城站名应保持地方感。优先使用已登记的城市英文名；未登记专名采用拼音，具有明确构筑物通名时采用“登记专名或拼音专名 + 英文通名”：

| 中文通名 | 英文通名 | 示例 |
|---|---|---|
| 门 | Gate | 南薰门 → Southern Breeze Gate |
| 桥 | Bridge | 清平桥 → Qingping Bridge |
| 渡 | Ferry | 柳荫渡 → Willowshade Ferry |
| 巷 | Lane | 大井巷 → Dajing Lane |
| 坊 | Quarter | 永安坊 → Yong'an Quarter |
| 街 | Street | 百工街 → Baigong Street |
| 寺 | Temple | 报恩寺 → Bao'en Temple |
| 阁 / 楼 | Pavilion / Tower | 城隍阁 → Chenghuang Pavilion；钟鼓楼 → Bell and Drum Tower |
| 仓 | Granary / Warehouse | 东仓 → East Granary；三桅仓 → Sanwei Warehouse |
| 码头 | Pier / Terminal | 按客运或工业功能选用，并保持实体内一致 |

人民广场是全市锁定公共名称，统一为 `People's Square`。

## 5. 村镇、道路和社区

- 镇、村、浜、塘、埭、坞、浦、湾等若已有站名目录中的正式语义英文名，必须沿用；否则采用完整拼音。不得在生成器中临时自由意译。
- 道路使用“城市登记专名 + Road / Avenue / Street”；登记专名可以是拼音，也可以是经审核的透明语义英文名：
  - 路 → `Road`
  - 大道 → `Avenue`
  - 街 → `Street`
- 同一条道路不能一站写拼音、另一站写意译。例如海晏路在本网络锁定为 `Calm Seas Road`，全图不得再出现 `Haiyan Road`。
- `里`、`苑`、住宅区等现代社区通名分别统一为 `Quarter`、`Gardens`、`Estate`；专名前部沿用登记英文名或规范拼音。
- 站名本身只有专名、不含中文通名时，英文也只写专名，不擅自增加 `Town`、`Center` 或 `Park`。

## 6. 公共设施与功能名称

公共设施可以意译，采用自然、克制、全图统一的功能英语：

| 中文 | 英文 |
|---|---|
| 中央商务区 | Central Business District |
| 市民中心 | Civic Center |
| 市政厅 | City Hall |
| 人民广场 | People's Square |
| 城市博物馆 | City Museum |
| 大剧院 | Grand Theatre |
| 歌剧院 | Opera House |
| 文化中心 | Arts Center |
| 传媒中心 | Media Center |
| 体育中心 | Sports Center |
| 体育馆 | Arena |
| 图书馆 | Library |
| 会展中心 | Convention Center |
| 大学城 | University Town |
| 软件园 | Software Park |
| 生命科学园 | Life Sciences Park |
| 保税物流园 | Bonded Logistics Park |
| 港务中心 | Port Authority Center |
| 维修船坞 | Repair Dock |

避免使用 `Dream Town`、`Future City`、`Smart Valley` 等营销式译名。英文必须对应中文语义，不添加中文不存在的形容词。

## 7. 学校与研究机构

- 城市正式大学可使用已锁定校名：宁沧大学 → `Ningcang University`。
- “学院”按机构性质使用 `College` 或 `Academy`；“研究院”使用 `Research Institute`；“实验室”使用 `Laboratories`。
- 校区使用 `Campus`，前部沿用登记英文名；玄湖校区在本网络锁定为 `Mystic Lake Campus`。
- 书院若为传统历史书院使用 `Academy`；不得把所有校园站都写成 `University Station 1/2`。

## 8. 铁路、机场、港口与公路枢纽

- 国家铁路客站统一使用 `Railway Station`：
  - 宁沧站 → `Ningcang Railway Station`
  - 宁沧北站 → `Ningcang North Railway Station`
  - 宁沧东站 → `Ningcang East Railway Station`
  - 宁沧南站 → `Ningcang South Railway Station`
- 城际综合枢纽可使用 `Intercity Hub`；锁定名称澄北城际枢纽 → `Clearwater North Intercity Hub`。
- 国际机场实体为 `Ningcang International Airport`。
- 航站楼站名统一为 `Airport Terminal 1 / 2 / 3`，中文用“一号/二号/三号航站楼”；不混用 `T1 Station`。
- 第二机场为 `West Ridge Airport`，其航站楼为 `West Ridge Terminal`。
- 长途汽车枢纽统一使用 `Coach Terminal`。
- 深水港站名为 `Deepwater Port`；若带专名则写 `Qinglan Deepwater Port`。
- 邮轮客运设施用 `Cruise Terminal`，集装箱设施用 `Container Terminal`，不得互换。

## 9. 线路名称

| 线路 | 中文 | 英文 |
|---|---|---|
| L1–L5、L7–L10、L12 | 1号线等 | Line 1 等 |
| L6 | 6号线（环线） | Line 6 (Ring) |
| L11 | 11号线（半环线） | Line 11 (Semicircle) |
| L13 | 13号线（机场快线） | Line 13 (Airport Express) |
| L14 | 14号线（市域快线） | Line 14 (Regional Express) |
| L15 | 15号线（建设中） | Line 15 (Under Construction) |
| B1 | 港区支线 | Port Branch |
| B2 | 大学城支线 | University Town Branch |

图例、站点换乘标识、线路路径和报告必须使用相同线路名称，不另造简称。

## 10. 锁定锚点译名

以下候选站目录 ID 在最终网络中必须采用本表译名；若候选目录中存在旧译名，以本表为准：

| ID | 中文 | 英文 |
|---|---|---|
| NC-OC-028 | 人民广场 | People's Square |
| NC-OC-019 | 南薰门 | Southern Breeze Gate |
| NC-OC-022 | 柳荫渡 | Willowshade Ferry |
| NC-RH-001 | 宁沧站 | Ningcang Railway Station |
| NC-RH-002 | 宁沧北站 | Ningcang North Railway Station |
| NC-RH-003 | 宁沧东站 | Ningcang East Railway Station |
| NC-RH-004 | 宁沧南站 | Ningcang South Railway Station |
| NC-RH-015 | 澄北城际枢纽 | Clearwater North Intercity Hub |
| NC-CB-004 | 中央商务区 | Central Business District |
| NC-CB-016 | 市政厅 | City Hall |
| NC-IS-004 | 旧海关 | Historic Customs House |
| NC-SF-001 | 南浦金融城 | South Harbor Financial District |
| NC-SF-004 | 江湾文化馆 | Riverbend Arts Center |
| NC-NR-001 | 北原中心 | North Plain Civic Center |
| NC-UN-018 | 大学城中心 | University Town Center |
| NC-UN-019 | 雨湖 | Rain Lake |
| NC-ET-001 | 东澜中心 | East River Civic Center |
| NC-CO-002 | 潮平 | Tidal Plain |
| NC-CO-012 | 滨海文化中心 | Coastal Arts Center |
| NC-AP-012 | 西岭机场 | West Ridge Airport |
| NC-PT-001 | 深水港 | Deepwater Port |

## 11. 英文排版

- 英文采用标题式大小写；短介词和连词按正常英语规则小写。
- 不使用全大写长站名，机场代码等正式缩写除外。
- 中文是主标签，英文是次标签；两者作为同一标签单元布局。
- 中文最小字号不低于 18 px，英文不低于 10 px；换乘站分别不低于 20 px 和 11 px。
- 英文可在语义边界换行，不得拆开拼音专名或将 `Railway Station` 分散到无关位置。
- 撇号统一使用直撇号字符，例如 `People's Square`；避免同图混用不同弯引号。

## 12. 最终审核清单

1. 中文站名全部唯一。
2. 英文站名全部唯一。
3. 所有铁路站均以 `Railway Station` 结尾，城际枢纽例外。
4. 所有航站楼均使用 `Airport Terminal n`。
5. `Road / Avenue / Street` 使用规则一致。
6. 专有地名不出现逐字空格拼音或未经锁定的自由翻译。
7. 公共功能名称不夹杂拼音通名。
8. 同一实体在地理图、主图、图例和报告中的英文完全一致。
9. 不存在字符级拼音生成代码或运行时翻译。
10. 英文经过词组级人工复核，并记录真实检查结果。
