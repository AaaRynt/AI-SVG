# 富士山 SVG 生成实验报告

## 完成结果

本轮已完成高复杂度、静态、自包含的富士山 SVG 风景插画。最终画面为 1600 × 1000，包含冬季雪峰、多层云海与山腰雾气、高空薄云、山脚城市、道路与基础设施、湖面、山体与云层反射、太阳及城市灯光碎片反射、水纹、岸线和前景树林。光照采用左暖右冷的清晨方向性关系。

最终文件：

- `fuji.svg`
- `preview.png`
- `generate_fuji.py`
- `validate_svg.py`
- `metadata.json`
- `REPORT.md`

## 精确指标

- SVG 总行数：5794
- 非空、非纯注释行数：5775
- SVG 文件大小：1,012,605 字节
- SVG 元素总数：5622
- 可渲染图形元素：5372
- 可见图元类型：7 类
- 关键语义图层：19 个，全部存在且包含可见内容
- 渐变定义：18 个，其中 17 个得到实际引用
- PNG 尺寸：1600 × 1000
- PNG 文件大小：1,207,833 字节

主要元素类型数量：

| 元素类型         | 数量 |
| ---------------- | ---: |
| `path`           | 3883 |
| `rect`           | 1486 |
| `g`              |  124 |
| `stop`           |   61 |
| `circle`         |   29 |
| `linearGradient` |   17 |
| `feGaussianBlur` |    4 |
| `filter`         |    4 |
| `clipPath`       |    3 |
| `ellipse`        |    1 |
| `line`           |    1 |
| `mask`           |    1 |
| `polygon`        |    1 |
| `polyline`       |    1 |
| `radialGradient` |    1 |

此外各有 1 个 `svg`、`defs`、`title`、`desc` 和 `metadata` 元素。

## 生成、验证与渲染

- 固定随机种子：20260629
- 生成轮次：4
- 验证轮次：4
- 渲染尝试：5
- 成功渲染并实际检查的轮次：4
- 最终渲染工具：Google Chrome 150.0.7871.47 无头模式的原生 SVG 渲染器
- 辅助渲染工具：ImageMagick 7.1.2-18
- 最终验证：37 项通过，0 项失败

实际执行过的核心命令：

```bash
python3 generate_fuji.py
python3 validate_svg.py fuji.svg
wc -l -c fuji.svg
magick -background none -density 96 fuji.svg -resize 1600x1000! preview.png
'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome' --headless=new --disable-gpu --hide-scrollbars --force-device-scale-factor=1 --window-size=1600,1000 --screenshot=preview.png file:///Users/rynt/Desktop/Code/ai-fuji-svg/runs/fuji/v2/fuji.svg
magick identify -format 'PNG %wx%h %b\n' preview.png
wc -c preview.png
```

生成器、验证器和浏览器渲染命令均实际执行；其中生成器与验证器按上述轮次数重复运行。

## 验证结果

严格验证器最终全部通过，覆盖：UTF-8 与 XML 解析、SVG 根元素和 16:10 `viewBox`、5794 行与 5775 条有效内容行、5622 个元素、5372 个可渲染图形、7 类可见图元、19 个关键图层、ID 唯一性、禁用元素与外部资源、隐藏和画布外凑数、尺寸有效性、内部 URL 与 `use` 引用、渐变语义与复用、文件大小，以及每个主要图元独占物理行。

最终文件未包含 `<image>`、`<foreignObject>`、Base64、`data:image`、位图、外部 URL、远程字体、脚本或浏览器运行时生成逻辑。

## 预览检查与修复

第一轮发现：

- 可见图元类型只有 `path`、`rect`、`circle` 三类，严格验证未通过。
- ImageMagick 无法解析蒙版内的渐变填充，首次渲染失败。

修复：

- 为真实画面内容增加 `ellipse` 日晕、`line` 城市线路、`polygon` 山体光面和 `polyline` 山脊，最终达到 7 类可见图元。
- 将倒影蒙版改为中灰基底和黑色水平断裂线，纵向衰减由反射元素的透明度完成。

第二轮发现：

- ImageMagick 虽能完成渲染，但其 SVG 委托将部分渐变和蒙版错误显示为大面积黑白块。
- Chrome 原生渲染显示作品本身结构完整，但山顶略像双圆峰，山脊线交叉偏密，部分云体偏尖并遮挡过多城市，完整山体倒影形成明显三角形，太阳射线偏强。

修复：

- 使用 Chrome 原生 SVG 渲染生成正式预览，避免把 ImageMagick 的委托缺陷误判为作品缺陷。
- 重塑略不对称的山顶轮廓，限制山脊分别沿左右坡向下行，降低山脊与雪面碎纹的对比。
- 调整云体贝塞尔峰值、尺寸、透明度和整组柔化，让城市、道路与灯光保持可见。
- 降低完整山体倒影基底，仅保留弱色偏移和大量分段水纹重构；同时减弱太阳直射线。

第三轮发现：

- 冷暖山体覆盖层在中心形成过直的阴影边界。

修复：

- 将分界改成随中央山脊起伏的曲线路径，并重新执行生成、验证、浏览器渲染和全画面检查。

最终检查确认：富士山完整显示，视觉焦点位于雪峰；山顶略不对称；三层云海未完全遮山；城市贴合山脚与岸线；倒影上下方向正确、颜色偏移且弱于主体；太阳反射在左侧形成碎片化纵向光带；城市灯光反射短小不规则；水纹远细近宽；前景树林没有遮挡主体；未发现黑块、白块、巨大异常图形、漂浮建筑、失效引用或裁剪错误。

## 当前已知限制

- ImageMagick 7.1.2-18 的内置 SVG 委托无法忠实显示本作品的部分渐变和蒙版，因此最终预览与视觉验收使用 Chrome 原生 SVG 渲染器。现代 Chrome、Safari 和 Firefox 所支持的标准 SVG 渐变、裁剪、蒙版和滤镜均为本文件采用的能力。
- SVG 包含五千余个可见或结构元素，以换取高复杂度山体、城市、云海与水纹细节；旧式或资源受限的 SVG 查看器可能比现代浏览器加载更慢。
- 未从环境确认具体模型名称，因此 `metadata.json` 中保留为 `null`。
