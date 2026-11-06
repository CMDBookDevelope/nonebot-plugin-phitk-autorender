<div align="center">

# nonebot-plugin-phitk-autorender

*📚 让”kkp”变简单，不要再让”懒得开电脑渲染”成为遗憾 📚*

*🔥 基于 NoneBot2, Phi-TK-CLI 的 Phigros 谱面渲染插件 🔥*

<p align="center">
  
  <a href="https://www.python.org">
    <img src="https://img.shields.io/badge/python-3.8--3.12+-blue.svg" alt="python">
  </a>
  
  <a href="https://nonebot.dev">
    <img src="https://img.shields.io/badge/nonebot-2.0.0+-red.svg" alt="NoneBot">
  </a>
  
  <a href="https://github.com/Winamin/Phi-TK">
    <img src="https://img.shields.io/badge/Phi--TK-2.0.1+-magenta.svg" alt="Phi-TK">
  </a>

  <a href="https://github.com/CMDBookDevelope/Phi-TKC">
    <img src="https://img.shields.io/badge/Phi--TKC-1.0.2+-white.svg" alt="Phi-TK">
  </a>

  <a href="https://github.com/CMDBookDevelope/Phi-TK-cli">
    <img src="https://img.shields.io/badge/Phi--TK--CLI-1.0.4+-pink.svg" alt="Phi-TK-CLI">
  </a>
  
</p>

<p align="center">
  <a href="./LICENSE">
    <img src="https://img.shields.io/github/license/CMDBookDevelope/nonebot-plugin-phitk-autorender.svg" alt="license">
  </a>
</p>
</div>

## 📖 介绍

本插件可以下载用户提供的 .pez, .zip 文件，并调用 phi-tk-cli 渲染

## 💿 安装

### ***⚠️记得先去 <a href="https://github.com/CMDBookDevelope/Phi-TK-cli"><img src="https://img.shields.io/badge/Phi--TK--CLI_Repository-pink" alt="oonp!"></img></a> 安装 Phi-TK-CLI!***

### 方式一：手动安装
***暂不确定是否能正常安装() 咱还是建议手动把文件夹下载到 bot 的 plugins 文件夹下完成安装，随后配置 pyproject.toml***

### 方式二：或许可以吧...

#### 1. 使用 nb-cli 安装

```bash
nb plugin install nonebot-plugin-phitk-autorender
```

#### 2. 使用包管理器安装

1️⃣ 使用 pip 安装插件：
```bash
pip install nonebot-plugin-phitk-autorender
```

2️⃣ 在 NoneBot2 项目的 `pyproject.toml` 文件中添加插件：
```toml
[tool.nonebot]
plugins = ["nonebot-plugin-phitk-autorender"]
```

## 🎮 使用方法

> ⚠️ 需要**支持新参数名的 Phi-TK-CLI**：`--dark` 改成了 `--dim`、`--finish` 改成了 `--result`
> （用 `phi-tk-cli --help` 能看到 `--dim` 就是新版）。插件已适配；群里继续写 `dark` / `finish`
> 也能用，插件会映射成新名字。旧版 CLI 收到新名字会直接报 unknown argument。

### 基础指令
- `引用一个 .pez | .zip 文件并 @bot /render` - 以默认 `1k 30fps 无加载动画&结算动画` 渲染引用谱面
- `Alternative: @bot /xr` - /render 的命令别名
- 渲染完成后，**原片会作为「群文件」上传**（不再以视频消息发出，避免被二次压缩 / 大文件发不出去），文件名沿用谱面名

### 自定义参数（都是可选的）
按顺序写的位置参数：

| 排序 | 说明 | 可用值 | 默认值 | 补充说明 |
|------|---------|------|--------|--------|
| 1 | 分辨率 | 360p \| 480p \| 720p \| 1k \| 2k \| 任意 `宽x高` | 1k (1920x1440) | 默认 4:3，见[代码](nonebot_plugin_phitk_autorender/__init__.py "nya~") |
| 2 | 帧率 | 1-240 | 30 | phi-tk-cli 原生支持更高帧率，这里只是做个上限保护 |
| 3 | 背景压暗 | 0~100 | 不传（用 CLI 默认 30） | 数字越大越暗；`0` 表示保留谱面自带的值 |
| 4 | 显示加载界面 | 关键字 `load` | False | ~~棍母~~ |
| 5 | 显示结算界面 | 关键字 `result`（老写法 `finish`） | False | 3 秒，可用 `--ending` 改 |

后面还可以直接跟 phi-tk-cli 的新参数，插件会原样透传：

| 参数 | 说明 |
| --- | --- |
| `--resolution 1920x1080` / `--fps 60` / `--crf 18` | 也可以显式写（和上面的位置参数等价） |
| `--load` / `--result` | 也可以带 `--` 写，方便和其他参数混排 |
| `--ending 5` | 结算画面秒数 |
| `--name 小明` / `--rks 15.2` / `--combo TEXT` / `--watermark TEXT` | 玩家信息和水印 |
| `--ui score,combo` / `--hide-ui pb` | 显示/隐藏 UI 元素（也支持 `all`、`none`） |
| `--bar` / `--score-aim` / `--chart-debug` / `--flid-x` / `--chart-ratio 1.2` | 界面细节 |
| `--background` | 用谱面插画做背景 |
| `--speed 1.2` / `--note-scale 0.9` / `--volume-music 0.8` / `--volume-sfx 0.8` | 玩法 |
| `--fxaa` / `--no-particle` / `--no-effect` / `--no-double-hint` / `--aggressive` / `--hand-split` | 特效 / 玩法开关 |
| `--sample-count 4` | MSAA 采样数 |
| `--codec h264` / `--encoder nvenc` / `--preset slow` | 编码 |
| `--format mp4` / `--bitrate-control CRF` / `--bitrate 8000k` / `--no-hw-accel` / `--ffmpeg-thread` | 封装 / 码率 |
| `--target-audio 48000` / `--audio-format flac` / `--audio-bit 24` / `--audio-delay-frames 0` | 音频 |

> `--input` / `--output` / `--assets` 由插件自己控制；`--avatar` / `--respack` 能读本机任意文件，
> 这两个不会透传，免得群里有人拿它读服务器上的图。

💡 提示: 文字包含空格需要加引号，例如 `--name "Phi TK"`；也支持 `--dim=40` 这种等号写法
### 使用示例
```
@bot /xr & @bot /render                   # 基础用法
@bot /xr 2k 120 0                         # 自定义分辨率 帧率 背景压暗
@bot /xr load result                      # 显示加载界面和结算界面
@bot /xr 2k 120 0 load result             # 组合多个参数...
@bot /xr 1k --name 小明 --speed 1.2       # 透传新版 CLI 参数
@bot /xr --ui score,combo --no-hw-accel   # 只要分数和连击，并关掉硬件加速
```

## 📝 功能特点

- ✅ 支持自定义渲染参数
- ✅ 支持 phi-tk-cli 新版参数（`--dim` / `--result` 及 UI、玩法、编码、音频选项），`--xxx` 直接透传
- ✅ 支持高质量渲染
- ✅ phi-tk-cli 支持服务器硬件加速
- ✅ 支持曲绘背景
- ✅ 支持 info.yml 解析出的歌曲信息&难度信息显示；info.txt 是可选的旧格式（只有 txt 时自动生成 info.yml，只有 yml 时直接使用，不再报错）
- [❌ 不支持Simai谱面渲染](https://www.maiviewer.net/ "awmc。。。")

## 🔧 依赖

- Python 3.8+ (已测试支持 3.8 - 3.12)
- NoneBot2 >= 2.0.0

## 📄 开源许可

本项目基于 [GPL-3.0](LICENSE) 许可证开源。

**注意事项：**
- 本项目代码使用 GPL-3.0 许可证开源，您可以自由使用和修改代码
- 请遵守原始素材的使用条款和限制

## 🙏 鸣谢

- [Link](https://github.com/Winamin "🐲") - Phi-TK 开发者
- [Microsoft Copilot](https://copilot.microsoft.com "GPT 5o") - 贡献了部分代码
- [DeepSeek](https://deepseek.com/ "DeepSuxk。。。(?)") - 贡献了部分代码
- [NoneBot2](https://github.com/nonebot/nonebot2) - 跨平台 Python 异步机器人框架

## 📞 联系

<details>
  <summary>(我写的代码太史了能不要骂我吗 求放过.jpg)呜呜😭</summary>
  <tr>
    <td>QQ：3466756568</td>
  </tr>
</details>

## 💬 反馈

如有问题或建议，请：
- 提交 [Issue](https://github.com/CMDBookDevelope/nonebot-plugin-phitk-autorender/issues "我哪里做错了呜呜呜")

## *😅 废话*
  
- *此 Readme.md 参考了 [ nonebot-plugin-arcaea-sticker 的 readme](https://github.com/JQ-28/nonebot-plugin-arcaea-sticker#readme "😱")*
- *部分代码由AI编写/修改*

