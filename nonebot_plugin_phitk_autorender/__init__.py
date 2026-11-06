from __future__ import annotations

import os
import asyncio
import shlex
import shutil
import base64
import re
import random
import yaml
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import aiofiles
import aiohttp
from nonebot import on_notice, on_message, logger
from nonebot.adapters.onebot.v11 import Bot, GroupUploadNoticeEvent, Message, MessageEvent, MessageSegment
from nonebot.rule import to_me
from nonebot.plugin import PluginMetadata

__plugin_meta__ = PluginMetadata(
    name="phitk-autorender",
    description="引用 .pez/.zip 文件，使用 phi-tk-cli 渲染视频并发送回群",
    usage="引用一个 .pez 或 .zip 文件，@机器人 发送 /xr [分辨率] [帧率] [压暗] [load] [result] [--其他 phi-tk-cli 参数]",
    type="application",
    homepage="https://github.com/CMDBookDevelope/nonebot-plugin-phitk-autorender",
    supported_adapters={"~onebot.v11"},
)
PLUGIN_DIR = Path(__file__).parent

# ===== 全局变量 =====
ymlInfo = ""
start_time = 0

# ===== 常量配置 =====
BINARY = "phi-tk-cli" #你的phi-tk-cli可执行文件绝对路径(或者wrapper.sh)
BASE_DIR = "/tmp/render" #存放渲染缓存的位置
ASSETS_PATH = "/usr/lib/ptkc-assets" #phi-tk-cli的assets位置
CRF = 20 #渲染质量参数

RESOLUTION_MAP = {
    "1k": "1920x1440",
    "2k": "2560x1920",
    "720p": "1280x720",
    "360p": "640x360",
    "480p": "854x480",
}
DEFAULT_RES = "1920x1440"
DEFAULT_FPS = 30

NAPCAT_VOLUME_PATH = "/var/lib/docker/volumes/7a9d91adccb99dfb1dd2b8fbca0bd4d80ff4e43b8aad8ab0af44210693957197/_data"
if NAPCAT_VOLUME_PATH:
    CONTAINER_BASE = "/app/.config/QQ"
else:
    CONTAINER_BASE = None

#系ぎて RE:MASTER !?15?!
# ===== 上传事件：仅记录日志，不发送提示 =====
upload_matcher = on_notice(priority=10, block=False)

@upload_matcher.handle()
async def handle_upload(bot: Bot, event: GroupUploadNoticeEvent):
    group_id = str(event.group_id)
    file_name = event.file.name
    file_id = event.file.id
    if not (file_name.lower().endswith(".pez") or file_name.lower().endswith(".zip")):
        return
    logger.info(f"群 {group_id} 上传了 .pez 文件：{file_name}，可引用该文件发送 /xr 指令")

# ===== 指令处理器：使用 on_message 手动解析 =====
render_cmd = on_message(rule=to_me(), priority=10, block=True)

@render_cmd.handle()
async def handle_render(bot: Bot, event: MessageEvent):
    global start_time
    group_id = str(event.group_id)

    # 1. 提取纯文本，移除 @机器人
    raw_text = event.get_plaintext().strip()
    self_id = str(bot.self_id)
    start_time = time.time()
    if f"@{self_id}" in raw_text:
        raw_text = raw_text.replace(f"@{self_id}", "").strip()

    if not (raw_text.startswith("/xr") or raw_text.startswith("/render")):
        return

    # 2. 解析参数
    if raw_text.startswith("/xr"):
        args_text = raw_text[3:].strip()
    else:
        args_text = raw_text[7:].strip()

    options = parse_render_args(args_text)
    logger.info(
        f"解析参数：分辨率={options.resolution}, 帧率={options.fps}, CRF={options.crf}, "
        f"额外参数={options.flags or '无'}"
    )

    # 3. 检查是否引用消息
    reply = event.reply
    if not reply:
        await render_cmd.finish("请引用（回复）一个 .pez 或 .zip 文件后再发送此指令。")
        return

    # 4. 从 reply 中提取文件信息（优先）
    file_id = None
    file_name = None
    file_url = None

    for seg in reply.message:
        if seg.type == 'file':
            data = seg.data
            logger.info(f"文件段 data: {data}")  # 打印完整信息，便于调试

            # 提取文件ID（真正的ID字段）
            file_id = data.get('file_id') or data.get('id')
            # 提取下载URL（如果有，最优先使用）
            file_url = data.get('url')
            # 提取文件名（优先 name，其次 file，再 file_name）
            file_name = data.get('name') or data.get('file_name') or data.get('file')
            break

    # 若未能从 reply 获取，回退到 get_msg
    if not file_id and not file_url:
        try:
            msg_data = await bot.get_msg(message_id=reply.message_id)
            for seg in msg_data.get('message', []):
                if seg.get('type') == 'file':
                    data = seg.get('data', {})
                    logger.info(f"get_msg 文件段 data: {data}")
                    file_id = data.get('file_id') or data.get('id')
                    file_url = data.get('url')
                    file_name = data.get('name') or data.get('file_name') or data.get('file')
                    break
        except Exception as e:
            logger.error(f"获取引用消息失败: {e}")
            await render_cmd.finish("无法获取引用消息，请重试。")
            return

    logger.info(f"提取结果: file_id={file_id}, file_name={file_name}, file_url={file_url}")

    # 如果 file_name 仍为空，尝试从 file_id 中推断（若 file_id 是文件名）
    if not file_name and file_id and '.' in file_id and '/' not in file_id:
        file_name = file_id
        file_id = None  # 此时 file_id 实际是文件名，不能作为ID使用

    # 检查文件扩展名
    if not file_name:
        await render_cmd.finish("无法获取文件名，请确保引用的是有效的文件消息。")
        return

    if not (file_name.lower().endswith('.pez') or file_name.lower().endswith('.zip')):
        await render_cmd.finish(f"仅支持 .pez 或 .zip 文件，当前文件：{file_name}")
        return

    # 5. 准备下载路径
    timestamp = int(asyncio.get_event_loop().time())
    seed_dir = Path(BASE_DIR) / f"{timestamp}-{group_id}"
    raw_dir = seed_dir / "raw"
    assemb_dir = seed_dir / "assemb"
    raw_dir.mkdir(parents=True, exist_ok=True)
    assemb_dir.mkdir(parents=True, exist_ok=True)
    logger.info(f"创建种子目录: {seed_dir}")

    pez_path = raw_dir / file_name
    chart_zip = seed_dir / "chart.zip"
    result_video = seed_dir / "result.mp4"

    try:
        # 6. 下载文件（优先使用 URL）
        # if file_url:
        #     logger.info(f"使用 URL 下载: {file_url}")
        #     await download_file_by_url(file_url, pez_path)
        # elif file_id:
        #     logger.info(f"使用 file_id 下载: {file_id}")
        #     await download_file_by_id(bot, file_id, pez_path)
        # else:
        #     raise ValueError("既无 URL 也无 file_id，无法下载")

        # 1. 下载 .pez 文件
        logger.info(f"开始下载文件: {file_name} 到 {pez_path}")
        await download_file(bot, file_id, pez_path)
        logger.info(f"文件下载完成，大小: {os.path.getsize(pez_path)} bytes")

        # 7. 解压、重命名、打包、渲染（与之前完全一致）
        logger.info(f"解压 {pez_path} 到 {assemb_dir}")
        await unzip_pez(pez_path, assemb_dir)
        logger.info("解压完成")

        chart_json, cover_png, song_mp3, parsed_info = await process_assemb(assemb_dir)
        logger.info("重命名完成")

        #logger.info(f"压缩 {assemb_dir} 到 {chart_zip}")
        #await make_zip(assemb_dir, chart_zip)
        #logger.info(f"压缩完成，大小: {os.path.getsize(chart_zip)} bytes")

        # shutil.rmtree(assemb_dir, ignore_errors=True)
        #logger.info("已清理 assemb 目录")

        pre_msg = parsed_info
        logger.info(f"PreMsg:\n{pre_msg}")

        await bot.send_group_msg(group_id=event.group_id, message=f"开始渲染 {file_name}，请稍候喵~")
        cost = await run_phi_tk_cli(assemb_dir, result_video, options, start_time)
        logger.info(f"phi-tk-cli 完成，输出大小: {os.path.getsize(result_video)} bytes")

        await bot.send_group_msg(group_id=event.group_id, message=pre_msg + f"\nduring: {cost}")

        # 渲染结果改为「上传群文件」而不是发视频消息：
        # 视频消息会被客户端二次压缩，大文件还经常直接发送失败；群文件是原片。
        group_file_name = _group_file_name(file_name)
        await send_group_file(bot, event.group_id, result_video, group_file_name)

        # shutil.rmtree(seed_dir, ignore_errors=True)
        logger.info(f"成功处理 {file_name}，已发送至群 {group_id}")

    except Exception as e:
        logger.error(f"处理失败: {e}", exc_info=True)
        # 错误报告除了写日志，也发回群里；截断避免超过 QQ 消息长度限制。
        detail = f"{type(e).__name__}: {e}".strip()
        if len(detail) > 1500:
            detail = detail[:1500] + "…（已截断，完整日志见控制台）"
        try:
            await bot.send_group_msg(
                group_id=event.group_id,
                message=Message(MessageSegment.text(f"渲染失败：{file_name}\n{detail}")),
            )
        except Exception as send_err:
            logger.error(f"发送错误消息失败: {send_err}")
    # finally:
    #     shutil.rmtree(seed_dir, ignore_errors=True)
# ===== 辅助函数（保持不变） =====
async def download_file(bot: Bot, file_id, save_path: Path):
    if not file_id:
        raise ValueError("无法获取文件 ID")
    logger.debug(f"尝试获取文件 ID: {file_id}")

    # 优先请求 base64 格式
    resp = await bot.get_file(file_id=file_id, type="base64")
    logger.debug(f"get_file 响应: {resp}")

    # 情况1: 返回 base64 内容
    if "file" in resp and isinstance(resp["file"], str) and len(resp["file"]) > 100:
        import base64
        file_data = resp["file"]
        if "," in file_data:
            file_data = file_data.split(",", 1)[1]
        try:
            decoded = base64.b64decode(file_data)
            async with aiofiles.open(save_path, 'wb') as f:
                await f.write(decoded)
            logger.info(f"文件已通过 Base64 解码保存到 {save_path}，大小: {len(decoded)} bytes")
            return
        except Exception as e:
            logger.warning(f"Base64 解码失败，尝试其他方式: {e}")

    # 情况2: 返回本地路径或 URL
    url = resp.get("url") or resp.get("file")
    if not url:
        raise ValueError("无法获取文件下载链接")

    # 本地文件路径
    if not url.startswith("http://") and not url.startswith("https://"):
        local_path = url.replace("file://", "", 1) if url.startswith("file://") else url

        # 应用 Docker 路径映射
        if CONTAINER_BASE and local_path.startswith(CONTAINER_BASE):
            mapped_path = local_path.replace(CONTAINER_BASE, NAPCAT_VOLUME_PATH, 1)
            logger.info(f"路径映射: {local_path} -> {mapped_path}")
            local_path = mapped_path

        logger.info(f"尝试本地文件路径: {local_path}")

        if not os.path.exists(local_path):
            raise FileNotFoundError(f"本地文件不存在: {local_path}")

        shutil.copy2(local_path, save_path)
        logger.info(f"文件已从本地复制到 {save_path}")
        logger.info(f"清理下载缓存：{os.remove(local_path)}")
    else:
        # HTTP 下载
        logger.info(f"开始 HTTP 下载文件，URL: {url}")
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                response.raise_for_status()
                async with aiofiles.open(save_path, 'wb') as f:
                    await f.write(await response.read())
        logger.info(f"文件已保存到 {save_path}")


# async def download_file_by_id(bot: Bot, file_id: str, save_path: Path):
#     """通过 file_id 下载文件"""
#     try:
#         resp = await bot.get_file(file_id=file_id, type="base64")
#         if "file" in resp and isinstance(resp["file"], str) and len(resp["file"]) > 100:
#             data = resp["file"]
#             if "," in data:
#                 data = data.split(",", 1)[1]
#             try:
#                 decoded = base64.b64decode(data)
#                 async with aiofiles.open(save_path, 'wb') as f:
#                     await f.write(decoded)
#                 logger.info(f"文件通过 Base64 保存，大小: {len(decoded)} bytes")
#                 return
#             except Exception as e:
#                 logger.warning(f"Base64 解码失败，尝试其他方式: {e}")
#     except Exception as e:
#         logger.warning(f"获取 base64 失败: {e}")

#     resp = await bot.get_file(file_id=file_id)
#     url = resp.get("url") or resp.get("file")
#     if not url:
#         raise ValueError("无法获取文件下载链接")

#     if not url.startswith("http://") and not url.startswith("https://"):
#         local_path = url.replace("file://", "", 1) if url.startswith("file://") else url
#         if CONTAINER_BASE and local_path.startswith(CONTAINER_BASE):
#             mapped_path = local_path.replace(CONTAINER_BASE, NAPCAT_VOLUME_PATH, 1)
#             logger.info(f"路径映射: {local_path} -> {mapped_path}")
#             local_path = mapped_path
#         if not os.path.exists(local_path):
#             raise FileNotFoundError(f"本地文件不存在: {local_path}")
#         shutil.copy2(local_path, save_path)
#         logger.info(f"文件从本地复制到 {save_path}")
#         try:
#             os.remove(local_path)
#             logger.info("清理下载缓存成功")
#         except Exception:
#             pass
#     else:
#         async with aiohttp.ClientSession() as session:
#             async with session.get(url) as response:
#                 response.raise_for_status()
#                 async with aiofiles.open(save_path, 'wb') as f:
#                     await f.write(await response.read())
#         logger.info(f"文件从 HTTP 下载到 {save_path}")

async def unzip_pez(pez_path: Path, target_dir: Path):
    import zipfile
    with zipfile.ZipFile(pez_path, 'r') as zf:
        zf.extractall(target_dir)
    logger.info(f"解压完成，目标目录: {target_dir}")

async def process_assemb(assemb_dir: Path):
    files = list(assemb_dir.iterdir())
    json_files = [f for f in files if f.suffix == '.json']
    png_files = [f for f in files if (f.suffix == '.png' or f.suffix == '.jpg')]
    audio_extensions = {'.wav', '.mp3', '.ogg', '.flac', '.m4a', '.aac'}
    audio_files = [f for f in files if f.suffix.lower() in audio_extensions]
    info_file = assemb_dir / "info.txt"
    yaml_file = assemb_dir / "info.yml"

    if len(json_files) != 1:
        raise ValueError(f"期望恰好一个 JSON 文件，找到 {len(json_files)} 个")
    if len(png_files) != 1:
        raise ValueError(f"期望恰好一个 PNG 文件，找到 {len(png_files)} 个")
    if len(audio_files) != 1:
        raise ValueError(f"期望恰好一个音频文件，找到 {len(audio_files)} 个")

    json_files[0].rename(assemb_dir / "chart.json")
    png_files[0].rename(assemb_dir / "background.png")
    audio_files[0].rename(assemb_dir / "song.mp3")

    # info.txt 是可选的老格式：谱面已经自带 info.yml 时直接用它，
    # 不能因为缺少 info.txt 就让整个渲染失败。
    if info_file.exists():
        async with aiofiles.open(info_file, 'r', encoding='utf-8') as f:
            info_text = await f.read()
        parsed_info = parse_info(info_text)
        if not yaml_file.exists():
            logger.info(generate_yaml(yaml_file))
    elif yaml_file.exists():
        parsed_info = await describe_yaml_info(yaml_file)
    else:
        raise ValueError("缺少 info.txt / info.yml 文件")

    return assemb_dir / "chart.json", assemb_dir / "background.png", assemb_dir / "song.mp3", parsed_info


async def describe_yaml_info(yaml_file: Path) -> str:
    """Build the pre-render message from an existing info.yml.

    Phira charts use a real YAML mapping, while some RPE exports save the
    "Key: Value" text under a .yml name; handle both.
    """
    async with aiofiles.open(yaml_file, 'r', encoding='utf-8') as f:
        text = await f.read()
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError:
        data = None
    if not isinstance(data, dict):
        return parse_info(text)

    name = data.get("name") or data.get("Name") or "UK"
    level = data.get("level") or data.get("Level") or "UK Lv.?"
    composer = data.get("composer") or data.get("Composer") or "UK"
    charter = data.get("charter") or data.get("Charter") or "UK"
    tip = data.get("tip") or data.get("Tip") or ""
    lines = [
        "Render Complete:",
        f"Name: {name}",
        f"Level: {level}",
        f"Composer: {composer}",
        f"Charter: {charter}",
    ]
    if tip:
        lines.append(f"tip: {tip}")
    return "\n".join(lines)

    #async def make_zip(source_dir: Path, output_zip: Path):
    #import zipfile
    # with zipfile.ZipFile(output_zip, 'w', zipfile.ZIP_DEFLATED) as zf:
    #     for root, _, files in os.walk(source_dir):
    #         for file in files:
    #             file_path = Path(root) / file
    #             arcname = file_path.relative_to(source_dir)
    #             zf.write(file_path, arcname)
    #os.system(f"zip -j {output_zip} {source_dir}/*")
    #logger.info(f"压缩完成: {output_zip}")

# async def download_file_by_url(url: str, save_path: Path):
#     """通过 HTTP URL 下载文件"""
#     async with aiohttp.ClientSession() as session:
#         async with session.get(url) as response:
#             response.raise_for_status()
#             async with aiofiles.open(save_path, 'wb') as f:
#                 await f.write(await response.read())
#     logger.info(f"文件从 URL 下载到 {save_path}")

# ===== 渲染参数（适配 phi-tk-cli 2026-11 版的参数改名）=====
#
# 改名：
#   --dark   → --dim     （背景压暗，0-100）
#   --finish → --result  （结算画面）
# 没变：--input / --output / --resolution / --crf / --fps / --assets / --load
# 另外 CLI 新增了 UI / 玩法 / 编码 / 音频一大堆参数，这里按「是否需要取值」
# 列了全表，群友在 /xr 后面直接写 `--name 小明`、`--speed 1.2`、
# `--ui score,combo` 就能透传给 phi-tk-cli。
CLI_OPTIONS: dict[str, bool] = {
    # 基础
    "resolution": True,
    "fps": True,
    "crf": True,
    # UI / 场景
    "dim": True,
    "result": False,
    "load": False,
    "ending": True,
    "name": True,
    "rks": True,
    "combo": True,
    "watermark": True,
    "ui": True,
    "hide-ui": True,
    "bar": False,
    "score-aim": False,
    "chart-debug": False,
    "flid-x": False,
    "chart-ratio": True,
    "background": False,
    # 玩法 / 特效
    "speed": True,
    "note-scale": True,
    "volume-music": True,
    "volume-sfx": True,
    "fxaa": False,
    "no-particle": False,
    "no-effect": False,
    "no-double-hint": False,
    "aggressive": False,
    "hand-split": False,
    "sample-count": True,
    # 编码
    "codec": True,
    "encoder": True,
    "preset": True,
    "format": True,
    "bitrate-control": True,
    "bitrate": True,
    "no-hw-accel": False,
    "ffmpeg-thread": False,
    # 音频
    "target-audio": True,
    "audio-format": True,
    "audio-bit": True,
    "audio-delay-frames": True,
}

# 老名字继续接受：群里还有人写 dark / finish
CLI_OPTION_ALIASES = {"dark": "dim", "finish": "result"}

# 群里直接写、不带 -- 的关键字
CLI_KEYWORDS = {"dark": "dim", "finish": "result", "dim": "dim", "load": "load", "result": "result"}

# 这些参数不让群友指定：前三个由插件控制，后三个（avatar/respack）能读本机任意文件
CLI_PROTECTED = {"input", "output", "assets", "avatar", "respack"}


@dataclass
class RenderOptions:
    """一次渲染要传给 phi-tk-cli 的参数。"""

    resolution: str = DEFAULT_RES
    fps: int = DEFAULT_FPS
    crf: int = CRF
    # 规范名 → 取值；None 表示布尔开关。用 dict 保留命令行里的顺序。
    flags: dict = field(default_factory=dict)
    # 用户显式给过的参数，位置参数不会覆盖它们
    explicit: set = field(default_factory=set)


def _normalize_resolution(text: str) -> Optional[str]:
    token = text.strip().lower()
    if token in RESOLUTION_MAP:
        return RESOLUTION_MAP[token]
    if re.fullmatch(r"\d{2,5}x\d{2,5}", token):
        return token
    return None


def _store_option(options: RenderOptions, name: str, value: Optional[str]) -> None:
    """把解析出的参数写进 options，顺便做一次轻量校验。"""
    name = CLI_OPTION_ALIASES.get(name, name)

    if name == "resolution":
        resolution = _normalize_resolution(value or "")
        if resolution:
            options.resolution = resolution
            options.explicit.add("resolution")
        else:
            logger.warning(f"无法识别的分辨率：{value}，忽略")
        return

    if name == "fps":
        try:
            fps = int(str(value))
            if fps <= 0:
                raise ValueError
        except (TypeError, ValueError):
            logger.warning(f"帧率必须是正整数，收到 {value}，忽略")
            return
        options.fps = fps
        options.explicit.add("fps")
        return

    if name == "crf":
        try:
            crf = int(str(value))
        except (TypeError, ValueError):
            logger.warning(f"CRF 必须是 1-51 的整数，收到 {value}，忽略")
            return
        if not 1 <= crf <= 51:
            logger.warning(f"CRF {crf} 超出 1-51，忽略")
            return
        options.crf = crf
        return

    if name not in CLI_OPTIONS:
        logger.warning(f"未知参数 --{name}，忽略")
        return

    if CLI_OPTIONS[name]:
        if value is None:
            logger.warning(f"参数 --{name} 缺少取值，忽略")
            return
        # --dim 旧版是 --dark，范围 0-100（CLI 侧还会再 clamp 一次）
        if name == "dim":
            try:
                dim = int(value)
            except (TypeError, ValueError):
                logger.warning(f"压暗值必须是 0-100 的整数，收到 {value}，忽略")
                return
            if not 0 <= dim <= 100:
                logger.warning(f"压暗值 {dim} 超出 0-100，忽略")
                return
            value = str(dim)
            options.explicit.add("dim")
        options.flags[name] = value
    else:
        options.flags[name] = None


def parse_render_args(args_text: str) -> RenderOptions:
    """/xr 后面的参数解析。

    支持三种写法，可混用：
      /xr 1k 60 40 load result        # 位置参数 + 关键字（老写法）
      /xr 1920x1080 60 --dim 40 --result
      /xr --ui score,combo --speed 1.2
    第一个裸数字是帧率、第二个是压暗（老版本这里写反了，已修）。
    """
    options = RenderOptions()
    try:
        tokens = shlex.split(args_text)
    except ValueError:
        tokens = args_text.split()

    positional_numbers = []
    index = 0
    while index < len(tokens):
        token = tokens[index].strip()
        index += 1
        if not token:
            continue
        lowered = token.lower()

        # --name=value / --name value / --flag
        if token.startswith("-"):
            name, _, inline = token.lstrip("-").partition("=")
            name = name.lower().replace("_", "-")
            if name in CLI_PROTECTED:
                logger.warning(f"参数 --{name} 由插件控制，忽略")
                # 顺手把它后面的取值也吃掉，免得被当成位置参数
                if inline is None and index < len(tokens) and not tokens[index].startswith("-"):
                    index += 1
                continue
            needs_value = CLI_OPTIONS.get(CLI_OPTION_ALIASES.get(name, name), False)
            value = inline or None
            if needs_value and value is None:
                if index >= len(tokens):
                    logger.warning(f"参数 --{name} 缺少取值，忽略")
                    continue
                value = tokens[index]
                index += 1
            elif not needs_value and inline:
                logger.warning(f"参数 --{name} 是开关，忽略取值 {inline}")
            _store_option(options, name, value)
            continue

        # key=value（res=1k、dim=40 ...）
        if "=" in token:
            key, _, value = token.partition("=")
            key = key.lower().replace("_", "-")
            if key in ("res", "resolution"):
                _store_option(options, "resolution", value)
            elif key in CLI_OPTIONS or key in CLI_OPTION_ALIASES:
                _store_option(options, key, value)
            else:
                logger.warning(f"无法识别的参数：{token}，忽略")
            continue

        # load / result / finish / dim 之类的关键字
        if lowered in CLI_KEYWORDS:
            name = CLI_KEYWORDS[lowered]
            if CLI_OPTIONS[name]:
                # dim 这种要取值的，后面跟个数字
                if index < len(tokens) and tokens[index].isdigit():
                    _store_option(options, name, tokens[index])
                    index += 1
                else:
                    logger.warning(f"{lowered} 后面需要一个 0-100 的数字，忽略")
            else:
                _store_option(options, name, None)
            continue

        # 分辨率：1k / 2k / 720p / 1920x1440
        resolution = _normalize_resolution(lowered)
        if resolution:
            options.resolution = resolution
            options.explicit.add("resolution")
            continue

        # 裸数字：第一个是帧率，第二个是压暗
        if re.fullmatch(r"\d+", token):
            positional_numbers.append(int(token))
            continue

        logger.warning(f"无法识别的参数：{token}，忽略")

    for number in positional_numbers:
        if "fps" not in options.explicit:
            if number <= 0 or number > 240:
                logger.warning(f"帧率 {number} 不合理，忽略")
                continue
            options.fps = number
            options.explicit.add("fps")
        elif "dim" not in options.explicit:
            if not 0 <= number <= 100:
                logger.warning(f"压暗值 {number} 超出 0-100，忽略")
                continue
            options.flags["dim"] = str(number)
            options.explicit.add("dim")
        else:
            logger.warning(f"多余的参数 {number}，忽略")

    return options


def build_cli_argv(input_path: Path, output_video: Path, options: RenderOptions) -> list:
    """拼出 phi-tk-cli 的命令行（新的参数名）。"""
    argv = [
        BINARY,
        "--input", input_path.as_posix(),
        "--output", output_video.as_posix(),
        "--resolution", options.resolution,
        "--crf", str(options.crf),
        "--fps", str(options.fps),
        "--assets", ASSETS_PATH,
    ]
    for name, value in options.flags.items():
        if value is None:
            argv.append(f"--{name}")
        else:
            argv.extend([f"--{name}", str(value)])
    return argv


async def run_phi_tk_cli(input_chart: Path, output_video: Path, options: RenderOptions, started_at: float = 0):
    # input_chart 可以是 .pez/.zip 压缩包，也可以是已经解好的谱面目录
    cmd = build_cli_argv(input_chart, output_video, options)
    logger.info(f"执行命令: {' '.join(shlex.quote(part) for part in cmd)}")
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
    except Exception as e:
        logger.error(f"启动子进程失败: {str(e)}")
        raise RuntimeError(f"启动 phi-tk-cli 进程异常: {e}") from e

    stdout, stderr = await proc.communicate()
    out_text = stdout.decode(errors="ignore").strip()
    err_text = stderr.decode(errors="ignore").strip()

    if proc.returncode != 0:
        # 新版 render.rs 的日志走 stdout（env_logger），报错只看 stderr 会漏
        logger.error(
            f"phi-tk-cli 退出码 {proc.returncode}\n"
            f"STDOUT:\n{out_text[-4000:]}\nSTDERR:\n{err_text[-4000:]}"
        )
        raise RuntimeError(f"phi-tk-cli 执行失败，返回码 {proc.returncode}")

    if err_text:
        logger.debug(f"phi-tk-cli STDERR: {err_text[-4000:]}")

    #Calc Time...
    diff = time.time() - started_at if started_at else 0.0
    m = int(diff // 60)
    s = diff % 60
    cost = f"{m}m{s:.2f}s"
    logger.info(f"phi-tk-cli 成功退出，输出视频: {output_video}, 用时{cost}")
    return cost


def _group_file_name(chart_file_name: str, suffix: str = ".mp4") -> str:
    """用谱面名给群文件起名，顺便去掉 QQ 群文件名不接受的字符。"""
    stem = Path(chart_file_name).stem.strip()
    if not stem or stem.startswith("."):
        stem = "render"
    stem = re.sub(r'[\\/:*?"<>|\r\n\t]', "_", stem)
    return f"{stem}{suffix}"


async def send_group_file(bot: Bot, group_id: int, video_path: Path, name: str) -> None:
    """把渲染结果上传到群文件（原片，不会被二次压缩）。

    OneBot v11 的 `upload_group_file` 在 nonebot-adapter-onebot 里没有显式方法，
    `Bot.__getattr__` 会把它转成 `call_api("upload_group_file", ...)`，直接调用即可。
    `file` 传本地绝对路径（NapCat / go-cqhttp 都支持），`name` 是群文件里显示的名字。
    """
    if not video_path.exists():
        raise FileNotFoundError(f"渲染结果不存在：{video_path}")

    size_mb = os.path.getsize(video_path) / 1024 / 1024
    logger.info(f"上传群文件：{name}（{size_mb:.2f} MB）")
    resp = await bot.upload_group_file(
        group_id=group_id,
        file=video_path.as_posix(),
        name=name,
    )
    logger.info(f"群文件上传完成：{resp}")

    # 上传动作本身在部分实现里不会在群里留提示，补一句话告诉群友去哪找。
    try:
        await bot.send_group_msg(
            group_id=group_id,
            message=f"渲染完成，原片已上传到群文件：{name}（{size_mb:.1f} MB）",
        )
    except Exception as notify_err:
        logger.warning(f"发送群文件提示失败: {notify_err}")


def parse_info(info_text: str) -> str:
    global ymlInfo
    lines = info_text.strip().splitlines()
    data = {}
    for line in lines:
        if ':' in line:
            key, val = line.split(':', 1)
            data[key.strip()] = val.strip()
    name = data.get("Name", "UK")
    chart = data.get("Chart", "UK")
    level = data.get("Level", "UK Lv.?")
    composer = data.get("Composer", "UK")
    charter = data.get("Charter", "UK")
    illustrator = data.get("Illustration", "UK")
    with open(PLUGIN_DIR / "tips.txt", "r", encoding="utf-8") as f:
        lines = [line.strip() for line in f if line.strip()]  # 过滤空行
    tip = random.choice(lines)
    ymlInfo = {
                    "name": name,
                    "level": level,
                    "difficulty": int(re.findall(r'(?i)lv\.(\S+)', level)[-1] if re.findall(r'(?i)lv\.(\S+)', level) else 67),
                    "illustrator": illustrator,
                    "tip": tip,
                    "intro": "棍母",
                    "composer": composer,
                    "charter": charter,
                }
    return (f"Render Complete:\n"
            f"Name: {name}\n"
            f"Level: {level}\n"
            f"Composer: {composer}\n"
            f"Charter: {charter}\n"
            f"tip: {tip}")
            
def generate_yaml(yaml_path):
    p = Path(yaml_path)
    if not p.exists():
        with open(yaml_path, "w", encoding="utf-8") as f:
            yaml.dump(ymlInfo, f, allow_unicode=True, sort_keys=False)
        return "Succeed generated info.yml"
    else:
        return "info.yml exists!"
