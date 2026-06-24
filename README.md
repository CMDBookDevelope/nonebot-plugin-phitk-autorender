<div align="center">

# nonebot-plugin-phitk-autorender

*🔥 基于 NoneBot2, Phi-TK-CLI 的 Phigros 谱面渲染插件 🔥*

<p align="center">
  <img src="https://img.shields.io/badge/python-3.8--3.12+-blue.svg" alt="python">
  <img src="https://img.shields.io/badge/nonebot-2.0.0+-red.svg" alt="NoneBot">
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
- `arc <角色> <文字>` - 快速生成表情包
- `arc` - 进入交互模式（新手友好）
- `arc -h` - 查看文本帮助（快速参考）
- `arc帮助` - 查看图片帮助（精美版，推荐首次使用）

### 自定义参数（都是可选的）
| 参数 | 说明 | 范围 | 默认值 | 补充说明 |
|------|------|------|--------|----------|
| `-s, --size` | 文字大小 | 20~45 | 35 | 数字越大文字越大,多行文字建议25-35 |
| `-x` | 横向位置 | 0~296 | 148 | 0=最左边,148=居中,296=最右边 |
| `-y` | 纵向位置 | 0~256 | 128 | 0=最上方,128=居中,256=最下方 |
| `-r, --rotate` | 旋转角度 | -180~180 | -12 | 正数顺时针,负数逆时针,建议-30~30度 |
| `-c, --color` | 文字颜色 | 十六进制 | 角色专属 | 支持`#ff0000`或`ff0000`格式 |
| `-w, --stroke-width` | 描边宽度 | 整数 | 9 | 文字边框的粗细 |
| `-C, --stroke-color` | 描边颜色 | 十六进制 | 自动生成 | 默认比文字颜色深30% |

💡 提示: 文字包含空格需要加引号,换行使用`\n`

### 使用示例
```
arc luna 好耶！                         # 基础用法
arc hikari "第一行\n第二行" -s 45         # 多行文字
arc 17 喜欢... -x 150 -y 100 -r -20    # 调整位置和角度
arc nami "龙笔!" -c ff0000              # 自定义红色文字
arc eto "Ciallo～(∠・ω<)⌒☆" -s 30 -c #fdae92 -r -28 -x 120 -y 80  # 组合多个参数
```

## 📝 功能特点

- ✅ 支持生成 Arcaea 角色的表情包
- ✅ 支持命令模式和交互模式
- ✅ 跨平台支持
- ✅ 支持自定义文字、位置、角度、颜色等参数
- ✅ 支持多行文本和自动换行
- ✅ 智能文字大小调整
- ✅ 支持中文角色名称

## 🔧 依赖

- Python 3.8+ (已测试支持 3.8 - 3.12)
- NoneBot2 >= 2.0.0
- nonebot-plugin-alconna（跨平台支持）
- nonebot-plugin-htmlrender
- nonebot-plugin-localstore

## 📄 开源许可

本项目基于 [MIT](LICENSE) 许可证开源。

**注意事项：**
- 本项目代码使用 MIT 许可证开源，您可以自由使用和修改代码
- 项目中的表情包素材来源于 [Xestarrrr](https://x.com/Xestarrrr)
- 本项目基于 [arcaea-stickers](https://github.com/Rosemoe/arcaea-stickers) 项目开发
- 请遵守原始素材的使用条款和限制

## 🙏 鸣谢

- [Xestarrrr](https://x.com/Xestarrrr) - 原始表情包素材创作者
- [arcaea-stickers](https://github.com/Rosemoe/arcaea-stickers) - 网页版表情包生成器
- [nonebot-plugin-pjsk](https://github.com/lgc-NB2Dev/nonebot-plugin-pjsk) - 参考了部分代码
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
- 提交 [Issue](https://github.com/CMDBookDevelope/nonebot-plugin-phitk-autorender/issues)

*此 Readme.md 参考了 [nonebot-plugin-arcaea-sticker 的 readme](https://github.com/JQ-28/nonebot-plugin-arcaea-sticker#readme "oonp")*
