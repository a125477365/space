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
  - 打开即默认显示 YouTube 视频
  - 可隐藏 YouTube 视频画面(`仅音频`)
  - 可自由拖拽到屏幕任意位置(工具栏拖拽)
  - 右下角拖拽缩放,自定义手柄
  - 可切换圆角 / 方形 / 圆形三种形状
  - 收起到右下角后,通过「🔊 恢复」按钮调回
- **空地通信板**:仅保留"空地通话音频"按钮,不再显示 NASA Lightstreamer 遥测面板与日志。

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

## 部署方式

### 方式 1: 直接打开(开发/本地)
1. 双击 `index.html` 或拖入浏览器即可。
2. OBS Browser Source:URL 填 `file:///path/to/index.html`。

### 方式 2: 本地静态服务器
```bash
cd space
python3 -m http.server 8080
# 浏览器访问 http://localhost:8080/
```

### 方式 3: Docker 容器(推荐用于 OBS/直播联网访问)
```bash
cd space
docker compose up -d --build
# 访问 http://localhost:8080/
# OBS Browser Source: http://<本机IP>:8080/
# 停止: docker compose down
```

> 说明:容器化部署对本应用的意义在于 –
> • 把单文件 HTML/web 字体/(跨域贴图)在本机用 nginx 提供为通用 HTTP URL,
>   这样 OBS 浏览器源、手机直播间、远程观众都可通过同一地址访问;
> • 同时 `file://` 在 OBS 中有时会受沙盒限制(如 CORS、iframe 等),
>   走 HTTP 可以完全规避;
> • nginx:alpine 镜像极小(<10 MB),资源占用远低于 node 静态服务器。

### 方式 4: 推送到 GitHub Pages
由于仓库已是 `a125477365/space`,可在 GitHub repo `Settings → Pages → Branch: main /root` 启用 Pages,即得
`https://a125477365.github.io/space/`。

## 免责

本页面为公开数据聚合展示,非官方产品。
