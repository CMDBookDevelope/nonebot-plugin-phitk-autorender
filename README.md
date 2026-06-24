<div align="center">

# nonebot-plugin-phitk-autorender

*📚 让”kkp”变简单，不要再让”懒得开电脑渲染”成为遗憾 📚*

*🔥 基于 NoneBot2, Phi-TK-CLI 的 Phigros 谱面渲染插件 🔥*

<p align="center">
  <img src="https://img.shields.io/badge/python-3.8--3.12+-blue.svg" alt="python">
  <img src="https://img.shields.io/badge/nonebot-2.0.0+-red.svg" alt="NoneBot">
  <img src="https://img.shields.io/badge/Phi--TK-2.0.1+-magenta.svg" alt="Phi-TK">
  <img src="https://img.shields.io/badge/Phi--TK--CLI-1.0.0+-pink.svg" alt="Phi-TK-CLI">
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

### 基础指令
- `引用一个 .pez | .zip 文件并 @bot /render` - 以默认 `1080p 30fps 无加载动画&结算动画 背景亮度40` 渲染引用谱面
- `Alternative: @bot /xr` - /render 的命令别名

### 自定义参数（都是可选的）
| 排序 | 说明 | 可用值 | 默认值 | 补充说明 |
|------|---------|------|--------|--------|
| 1 | 分辨率 | 360p \| 480p \| 720p \| 1k \| 2k | 1k | 默认4:3 详见[代码](nonebot_plugin_phitk_autorender/__init__.py#L31-L37 "nya~") |
| 2 | 帧率 | 0-120 | 30 | 其实 phi-tk-cli 原生支持更高帧率，可修改代码解除最高 120fps 限制 |
| 3 | 背景亮度 | 0~100 | 40 | 0=最暗 100=最亮 |
| 4 | 显示加载界面 | 布尔 | False | ~~棍母~~ |
| 5 | 显示结算界面 | 布尔 | False | 3秒 |

💡 提示: 文字包含空格需要加引号,换行使用`\n`
### 使用示例
```
@bot /xr & @bot /render                   # 基础用法
@bot /xr 2k 120 0                         # 自定义分辨率 帧率 背景亮度
@bot /xr load finish                      # 显示加载界面和结算界面
@bot /xr 2k 120 0 load finish             # 组合多个参数...
```

## 📝 功能特点

- ✅ 支持自定义渲染参数
- ✅ 支持高质量渲染
- ✅ phi-tk-cli 支持服务器硬件加速
- ✅ 支持曲绘背景
- ✅ 支持 info.yml 解析出的歌曲信息&难度信息显示 (❌ 暂不支持 info.txt 解析)
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

