#!/usr/bin/env python3
"""
emoji_to_avatar.py — 把一个 emoji 字符渲染成 1024x1024 群头像 PNG.

零 LLM / 零 GPT 依赖。Twemoji PNG (Twitter 开源 emoji 集) 离线缓存到
~/.hermes/emoji-cache/, 用 Pillow 画到莫兰迪暖米背景上.

用法:
  python3 emoji_to_avatar.py 🚗 /tmp/avatar.png
  python3 emoji_to_avatar.py 🐎 /tmp/avatar.png --bg "#F5F1E8"
  python3 emoji_to_avatar.py 🏠 /tmp/avatar.png --bg "#E8F0E8" --size 1024 --emoji-pct 0.75

CDN 失败时:
  - 先检查 ~/.hermes/emoji-cache/<codepoint>.png 缓存
  - CDN 不通 → 报错, 让上层手动 fallback (可以用任何 PNG 代替, 例如手动放
    一个 ~/.hermes/img_out/topic-rooms/<slug>-avatar.png 进去)
"""
import argparse
import sys
import urllib.request
from pathlib import Path

try:
    from PIL import Image, ImageDraw
except ImportError:
    print(
        "ERR: Pillow not installed. Quick fix:\n"
        "  • Linux/system python:  pip3 install Pillow\n"
        "  • macOS (system python 3.14 自带 no Pillow + brew arm64/x86 撞 lib):\n"
        "      uv venv /tmp/.emoji-venv --python 3.12\n"
        "      source /tmp/.emoji-venv/bin/activate\n"
        "      uv pip install Pillow\n"
        "      python " + sys.argv[0] + " <emoji> <output.png>",
        file=sys.stderr,
    )
    sys.exit(2)


CACHE_DIR = Path.home() / ".hermes" / "emoji-cache"
TWEMOJI_BASE = "https://cdn.jsdelivr.net/gh/twitter/twemoji@latest/assets/72x72/"
# Twemoji 也有 svg 但要 cairosvg 才能转, 用 72x72 PNG 然后放大反而保险

# 备份 CDN (jsdelivr 走不通时)
ALT_CDNS = [
    "https://cdn.jsdelivr.net/gh/twitter/twemoji@latest/assets/72x72/",
    "https://twemoji.maxcdn.com/v/latest/72x72/",
    "https://cdnjs.cloudflare.com/ajax/libs/twemoji/14.0.2/72x72/",
]


def emoji_to_filename(emoji: str) -> str:
    """把 emoji 字符转成 twemoji 的文件名 (codepoint 用 '-' 连接, 跳过 fe0f variation selector)."""
    codepoints = []
    for ch in emoji:
        cp = ord(ch)
        if cp == 0xfe0f:
            continue  # variation selector, twemoji 不带
        codepoints.append(f"{cp:x}")
    return "-".join(codepoints) + ".png"


def download_twemoji(filename: str, cache_path: Path) -> bool:
    """从任一 CDN 拉 twemoji PNG, 落 cache_path. 返回 True 成功."""
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    last_err = None
    for base in ALT_CDNS:
        url = base + filename
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "emoji-to-avatar/1.0"})
            with urllib.request.urlopen(req, timeout=10) as r:
                data = r.read()
            if len(data) < 200:
                last_err = f"too small ({len(data)} bytes) from {base}"
                continue
            cache_path.write_bytes(data)
            return True
        except Exception as e:
            last_err = f"{type(e).__name__}: {e} (from {base})"
            continue
    print(f"ERR: 所有 CDN 拉 {filename} 都失败. 最后: {last_err}", file=sys.stderr)
    return False


def get_emoji_png(emoji: str) -> Path:
    """拿 emoji 对应的 PNG, 走 cache. 返回缓存 path."""
    filename = emoji_to_filename(emoji)
    cache_path = CACHE_DIR / filename
    if cache_path.exists() and cache_path.stat().st_size > 200:
        return cache_path
    if not download_twemoji(filename, cache_path):
        raise RuntimeError(f"can't get emoji PNG: {emoji} ({filename})")
    return cache_path


def hex_to_rgb(hexcolor: str) -> tuple:
    h = hexcolor.lstrip("#")
    if len(h) != 6:
        raise ValueError(f"hex color must be 6 chars, got '{hexcolor}'")
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))


def render_avatar(
    emoji: str,
    output: Path,
    bg_hex: str = "#F5F1E8",
    size: int = 1024,
    emoji_pct: float = 0.75,
    rounded: bool = False,
) -> None:
    """画头像: 纯色背景 + 居中 emoji (占 emoji_pct of canvas)."""
    bg_rgb = hex_to_rgb(bg_hex)
    canvas = Image.new("RGBA", (size, size), bg_rgb + (255,))
    
    if rounded:
        # 圆角(目前不用,留接口)
        mask = Image.new("L", (size, size), 0)
        ImageDraw.Draw(mask).rounded_rectangle([0, 0, size, size], radius=size // 8, fill=255)
        canvas.putalpha(mask)
    
    emoji_png_path = get_emoji_png(emoji)
    emoji_img = Image.open(emoji_png_path).convert("RGBA")
    
    # twemoji 72x72 → 放大到 emoji_pct * size, 用 LANCZOS 高质量重采样
    target_side = int(size * emoji_pct)
    emoji_img = emoji_img.resize((target_side, target_side), Image.LANCZOS)
    
    # 居中
    paste_x = (size - target_side) // 2
    paste_y = (size - target_side) // 2
    canvas.paste(emoji_img, (paste_x, paste_y), emoji_img)
    
    output.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output, "PNG", optimize=True)
    print(f"[emoji-avatar] {emoji} → {output} ({output.stat().st_size:,} bytes)")


def main():
    p = argparse.ArgumentParser(description="把 emoji 渲染成 1024x1024 群头像 PNG")
    p.add_argument("emoji", help="emoji 字符, 例如 🚗 🐎 🏠")
    p.add_argument("output", help="输出 PNG 路径")
    p.add_argument("--bg", default="#F5F1E8", help="背景色 hex (默认 #F5F1E8 莫兰迪暖米)")
    p.add_argument("--size", type=int, default=1024, help="边长 (默认 1024)")
    p.add_argument("--emoji-pct", type=float, default=0.75, help="emoji 占画布比例 (默认 0.75)")
    p.add_argument("--rounded", action="store_true", help="圆角 (默认不圆, 飞书自己会圆裁)")
    args = p.parse_args()
    
    render_avatar(
        emoji=args.emoji,
        output=Path(args.output),
        bg_hex=args.bg,
        size=args.size,
        emoji_pct=args.emoji_pct,
        rounded=args.rounded,
    )


if __name__ == "__main__":
    main()
