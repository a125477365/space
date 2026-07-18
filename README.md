# 空间站实时追踪 · Orbital Tracker LIVE

一个使用浏览器 Canvas + 公开 TLE 轨道数据 (CelesTrak) 实时绘制 ISS / 天宫 (CSS) 位置的 9:16 竖屏单页应用,可直接用于 OBS / 直播间 / 移动端展示。

## 特性

- **真实地球贴图**: 启动时加载 NASA Blue Marble 等距圆柱投影作为底图,失败时回退到 GeoJSON 矢量真实风格着色(深蓝海洋 + 纬度配色大陆 + 极地冰盖)。
- **空间站真实外形**: 不再以亮点表示,而是绘制
  - ISS 的桁架 + 四对太阳能板 + 中央加压舱 + 散热器
  - 天宫 CSS 的 T 字主体 + 三对太阳能板 + 节点舱
- **轨道预测**: 基于 SGP4 模型,过去 12 分钟虚线、未来 96 分钟实线;过去/未来独立路径绘制,消除子午线跨越导致的对接错位。
- **晨昏线**: 实时太阳直射点 + 夜半球阴影叠加。
- **乘组卡片**: 多行网格同时显示在轨宇航员(按 ISS/CSS 自动分组),含头像 / 名字 / 在轨天数。
- **空地通话音频窗口**:
  - 可隐藏 YouTube 视频画面(`仅音频`)
  - 可自由拖拽到屏幕任意位置
  - 右下角拖拽缩放,或浏览器原生 `resize`
  - 可切换圆角 / 方形 / 圆形三种形状
  - 收起到右下角后,通过恢复按钮调回
- **遥测状态**: NASA ISSLive Lightstreamer 实时遥测(AOS / LOS 事件)。

## 数据来源

| 项目 | 源 |
| --- | --- |
| ISS TLE | `https://celestrak.org/NORAD/elements/gp.php?CATNR=25544&FORMAT=TLE` |
| CSS TLE | `https://celestrak.org/NORAD/elements/gp.php?CATNR=48274&FORMAT=TLE` |
| 世界国界 | `https://raw.githubusercontent.com/johan/world.geo.json/master/countries.geo.json` |
| 宇航员 | `corquaid/international-space-station-APIs` |
| 通信遥测 | `https://push.lightstreamer.com` ISSLIVE |
| 空地通话音频 | `https://www.youtube.com/@NASA/live`(NASA 官方 ISS 直播) |

所有数据源均失败时会自动回退到内置离线 TLE(会标记 ⚠)。

## 使用方法

直接用浏览器打开 `index.html` 即可,无需构建。建议在 OBS 浏览器源中加入并设为竖屏分辨率(720×1280)。

## 免责

本页面为公开数据聚合展示,非官方产品。
