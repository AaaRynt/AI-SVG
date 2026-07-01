# 写实级富士山 SVG 生成报告

## 输出文件

- `fuji.svg`
- `preview.png`
- `generate_fuji.py`
- `validate_svg.py`
- `REPORT.md`
- `metadata.json`

## 最终指标

- SVG 总行数：4761
- 非空非注释行数：4742
- SVG 元素总数：4695
- 可见图形元素数：4597
- SVG 文件大小：941353 字节
- PNG 尺寸：1600 × 1000
- 使用的渲染工具：ImageMagick `magick`

## 主要元素类型数量

- `path`：3905
- `rect`：668
- `circle`：24
- `g`：20
- `linearGradient`：14
- `stop`：52
- `clipPath`：3
- `filter`：2
- `feGaussianBlur`：2
- `radialGradient`：1
- `defs`：1
- `svg`：1
- `title`：1
- `desc`：1

## 实际执行过的命令

```bash
python3 generate_fuji.py
python3 validate_svg.py fuji.svg
magick -background none fuji.svg preview.png
magick identify -format 'preview=%w x %h\n' preview.png
magick preview.png -format 'p250_300=%[pixel:p{250,300}]\np800_80=%[pixel:p{800,80}]\np800_500=%[pixel:p{800,500}]\n' info:
wc -l fuji.svg
wc -c fuji.svg
magick identify -format '%w %h\n' preview.png
date -Iseconds
```

## 验证结果

验证器最终退出码为 0，全部检查通过：

- UTF-8 有效
- XML 可解析
- 根元素为 `<svg>`
- `viewBox` 有效
- 总行数不少于 3000
- 非空非注释行数不少于 2800
- 元素复杂度达标
- 所有关键图层存在且包含可见元素
- 不包含 `<image>`
- 不包含 `<foreignObject>`
- 不包含 Base64
- 不包含 `data:image`
- 不包含外部 URL
- 不包含运行时脚本
- 不存在透明度为 0 或 `display="none"` 的凑数元素
- `url(#...)` 引用有效
- `<use>` 引用有效
- 文件大小处于合理范围

## 生成和检查轮次

- 生成轮次：4
- 渲染和检查轮次：4
- 自修复轮次：3

## 预览检查中发现的问题

- 第一轮：SVG 行数为 5265，略高于建议上限 5000；整体偏暗，山体暗线压过雪面。
- 第二轮：行数收敛到建议范围内，但本地 ImageMagick 渲染下天空和山腰仍偏暗。
- 第三轮：关键渐变在 ImageMagick 下出现黑色太阳光晕。

## 实际修复的问题

- 减少部分山脊、水纹、云层和前景植物数量，将 SVG 收敛到 4761 行。
- 提亮天空、山体、云海和城市空气透视。
- 增加更明确的积雪面和雪舌，降低山体暗线不透明度。
- 为关键层增加实体色基础，避免本地渲染器把渐变显示为近黑色。
- 将太阳光晕改为透明实体色圆层，修复黑色大圆异常。

## 当前已知限制

- 本地 ImageMagick 对部分 SVG 渐变的呈现较弱，因此生成器使用实体色基础层保证预览稳定；现代浏览器中渐变层仍会参与显示。
- 作品是高复杂度矢量旅游海报风格，接近写实但不是照片级物理渲染。
