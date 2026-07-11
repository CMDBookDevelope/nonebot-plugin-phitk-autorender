import os
import asyncio
import shutil
import base64
import re
import random
import yaml
from pathlib import Path
from typing import Optional

import aiofiles
import aiohttp
from nonebot import on_notice, on_message, logger
from nonebot.adapters.onebot.v11 import Bot, GroupUploadNoticeEvent, MessageEvent, MessageSegment
from nonebot.rule import to_me
from nonebot.plugin import PluginMetadata

__plugin_meta__ = PluginMetadata(
    name="phitk-autorender",
    description="引用 .pez/.zip 文件，使用 phi-tk-cli 渲染视频并发送回群",
    usage="引用一个 .pez 或 .zip 文件，@机器人 发送 /xr [参数]",
    type="application",
    homepage="https://github.com/CMDBookDevelope/nonebot-plugin-phitk-autorender",
    supported_adapters={"~onebot.v11"},
)

global BINARY
global ymlInfo

# ===== 常量配置 =====
BINARY = "phi-tk-cli" #你的phi-tk-cli可执行文件绝对路径(或者wrapper.sh)
BASE_DIR = "/tmp/render" #存放渲染缓存的位置
ASSETS_PATH = "/usr/lib/ptkc-assets" #phi-tk-cli的assets位置
CRF = "20" #渲染质量参数

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
    group_id = str(event.group_id)

    # 1. 提取纯文本，移除 @机器人
    raw_text = event.get_plaintext().strip()
    self_id = str(bot.self_id)
    if f"@{self_id}" in raw_text:
        raw_text = raw_text.replace(f"@{self_id}", "").strip()

    if not (raw_text.startswith("/xr") or raw_text.startswith("/render")):
        return

    # 2. 解析参数
    if raw_text.startswith("/xr"):
        args_text = raw_text[3:].strip()
    else:
        args_text = raw_text[7:].strip()

    raw_args = args_text.split()
    res = DEFAULT_RES
    fps = DEFAULT_FPS
    dark = None
    load = False
    finish = False
    for arg in raw_args:
        arg_lower = arg.lower()
        if arg_lower in RESOLUTION_MAP:
            res = RESOLUTION_MAP[arg_lower]
        elif arg_lower == "load":
            load = True
        elif arg_lower == "finish":
            finish = True
        else:
            try:
                num = int(arg)
                if fps is None:
                    fps = num
                elif dark is None:
                    if 1 <= num <= 100:
                        dark = num
                    else:
                        logger.warning(f"暗度值 {num} 超出 1-100，忽略")
            except ValueError:
                logger.warning(f"无法识别的参数：{arg}，忽略")

    logger.info(f"解析参数：分辨率={res}, 帧率={fps}, 暗度={dark}, load={load}, finish={finish}")

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

        logger.info(f"压缩 {assemb_dir} 到 {chart_zip}")
        await make_zip(assemb_dir, chart_zip)
        logger.info(f"压缩完成，大小: {os.path.getsize(chart_zip)} bytes")

        # shutil.rmtree(assemb_dir, ignore_errors=True)
        logger.info("已清理 assemb 目录")

        pre_msg = parsed_info
        logger.info(f"PreMsg:\n{pre_msg}")

        await bot.send_group_msg(group_id=event.group_id, message=f"开始渲染 {file_name}，请稍候喵~")

        await run_phi_tk_cli(chart_zip, result_video, res, fps, dark, load, finish)
        logger.info(f"phi-tk-cli 完成，输出大小: {os.path.getsize(result_video)} bytes")

        await bot.send_group_msg(group_id=event.group_id, message=pre_msg)
        await bot.send_group_msg(
            group_id=event.group_id,
            message=MessageSegment.video(Path(result_video))
        )

        # shutil.rmtree(seed_dir, ignore_errors=True)
        logger.info(f"成功处理 {file_name}，已发送至群 {group_id}")

    except Exception as e:
        logger.error(f"处理失败: {e}", exc_info=True)
        # try:
        #     await bot.send_group_msg(
        #         group_id=event.group_id,
        #         message=f"渲染失败: {str(e)[:200]}"
        #     )
        # except Exception as send_err:
        #     logger.error(f"发送错误消息失败: {send_err}")
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
    if not info_file.exists():
        raise ValueError("缺少 info.txt 文件")

    json_files[0].rename(assemb_dir / "chart.json")
    png_files[0].rename(assemb_dir / "background.png")
    audio_files[0].rename(assemb_dir / "song.mp3")

    async with aiofiles.open(info_file, 'r', encoding='utf-8') as f:
        info_text = await f.read()
    parsed_info = parse_info(info_text)
    print(generate_yaml(yaml_file))
    return assemb_dir / "chart.json", assemb_dir / "background.png", assemb_dir / "song.mp3", parsed_info

async def make_zip(source_dir: Path, output_zip: Path):
    import zipfile
    # with zipfile.ZipFile(output_zip, 'w', zipfile.ZIP_DEFLATED) as zf:
    #     for root, _, files in os.walk(source_dir):
    #         for file in files:
    #             file_path = Path(root) / file
    #             arcname = file_path.relative_to(source_dir)
    #             zf.write(file_path, arcname)
    os.system(f"zip -j {output_zip} {source_dir}/*")
    logger.info(f"压缩完成: {output_zip}")

# async def download_file_by_url(url: str, save_path: Path):
#     """通过 HTTP URL 下载文件"""
#     async with aiohttp.ClientSession() as session:
#         async with session.get(url) as response:
#             response.raise_for_status()
#             async with aiofiles.open(save_path, 'wb') as f:
#                 await f.write(await response.read())
#     logger.info(f"文件从 URL 下载到 {save_path}")

async def run_phi_tk_cli(input_zip: Path, output_video: Path, resolution: str, fps: int, dark: Optional[int], load: bool, finish: bool):
    cmd = [
        BINARY,
        "--input", input_zip.as_posix(),
        "--output", output_video.as_posix(),
        "--resolution", resolution,
        "--crf", CRF,
        "--assets", ASSETS_PATH,
        "--fps", str(fps),
    ]
    if dark is not None:
        cmd.extend(["--dark", str(dark)])
    if load:
        cmd.append("--load")
    if finish:
        cmd.append("--finish")

    logger.info(f"执行命令: {' '.join(cmd)}")
    try: 
        proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        )
    except: 
        print('FuckFakeError。。。')
    stdout = await proc.communicate()
    if proc.returncode != 0:
        error_msg = 'Errored'
        logger.error(f"phi-tk-cli 标准错误: {error_msg}")
        #raise RuntimeError(f"phi-tk-cli 执行失败，返回码 {proc.returncode}，错误信息: {error_msg}")
    logger.info(f"phi-tk-cli 成功退出，输出视频: {output_video}")

def parse_info(info_text: str) -> str:
    lines = info_text.strip().splitlines()
    data = {}
    for line in lines:
        if ':' in line:
            key, val = line.split(':', 1)
            data[key.strip()] = val.strip()
    name = data.get("Name", "Unknown")
    chart = data.get("Chart", "Unknown")
    level = data.get("Level", "Unknown Lv.?")
    composer = data.get("Composer", "Unknown")
    charter = data.get("Charter", "Unknown")
    with open("tips.txt", "r", encoding="utf-8") as f:
        lines = [line.strip() for line in f if line.strip()]  # 过滤空行
    tip = random.choice(lines)
    ymlInfo = {
                    "name": name,
                    "level": level,
                    "difficulty": "Lv." + re.findall(r'(?i)lv\.(\S+)', level)[-1] if re.findall(r'(?i)lv\.(\S+)', level) else "UK",
                    "illustrator": "UK",
                    "tip": tip,
                    "intro": "棍母",
                    "format": "null"
                }
    return (f"Render Complete:\n"
            f"Name: {name}\n"
            f"Level: {level}\n"
            f"Composer: {composer}\n"
            f"Charter: {charter}\n"
            f"tip: {tip}")
            
def generate_yml(yaml_path):
    p = Path(yaml_path)
    if not p.exists():
        with open(yaml_path, "w", encoding="utf-8") as f:
            yaml.dump(ymlInfo, f, allow_unicode=True, sort_keys=False)
        return "Succeed generated info.yml"
    else:
        return "info.yml exists!"
