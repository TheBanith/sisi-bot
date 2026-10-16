import math
import os
import subprocess
import sys
from PIL import Image, ImageDraw, ImageFont

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

WIDTH = 1280
HEIGHT = 720
FPS = 30
TOTAL_FRAMES = 255  # 8.5 seconds at 30fps

# Load Fonts
FONT_TITLE_L = ImageFont.truetype("C:/Windows/Fonts/segoeuib.ttf", 72)
FONT_TITLE_M = ImageFont.truetype("C:/Windows/Fonts/segoeuib.ttf", 46)
FONT_SUB = ImageFont.truetype("C:/Windows/Fonts/segoeui.ttf", 26)
FONT_BADGE = ImageFont.truetype("C:/Windows/Fonts/segoeuib.ttf", 22)
FONT_CODE = ImageFont.truetype("C:/Windows/Fonts/consolab.ttf", 24)
FONT_BIG_ICON = ImageFont.truetype("C:/Windows/Fonts/seguiemj.ttf", 60)

def draw_rounded_rect(draw, bbox, radius, fill, outline=None, width=1):
    draw.rounded_rectangle(bbox, radius=radius, fill=fill, outline=outline, width=width)

def draw_badge(draw, x, y, text, icon="✨", fill=(22, 27, 34), outline=(48, 54, 61), text_color=(240, 246, 252)):
    w, h = 420, 52
    bbox = [x - w//2, y - h//2, x + w//2, y + h//2]
    draw_rounded_rect(draw, bbox, 14, fill=fill, outline=outline, width=2)
    label = f"{icon}  {text}"
    bbox_t = draw.textbbox((0, 0), label, font=FONT_BADGE)
    tw = bbox_t[2] - bbox_t[0]
    th = bbox_t[3] - bbox_t[1]
    draw.text((x - tw//2, y - th//2 - 2), label, fill=text_color, font=FONT_BADGE)

def render_frame(f_idx):
    img = Image.new("RGB", (WIDTH, HEIGHT), (10, 13, 20))
    draw = ImageDraw.Draw(img)
    t = f_idx / FPS

    # 1. Background Cyber Grid
    grid_spacing = 60
    grid_alpha = int(18 + 6 * math.sin(t * 2))
    grid_color = (15, 25, 45, grid_alpha)
    for x in range(0, WIDTH, grid_spacing):
        draw.line([(x, 0), (x, HEIGHT)], fill=(20, 32, 50), width=1)
    for y in range(0, HEIGHT, grid_spacing):
        draw.line([(0, y), (WIDTH, y)], fill=(20, 32, 50), width=1)

    # 2. Ambient Center Glow
    glow_radius = int(220 + 25 * math.sin(t * 3))
    glow_color = (0, 120, 255) if f_idx < 135 else ((160, 50, 240) if f_idx < 195 else (30, 200, 120))
    # Draw radial gradient rings
    for r in range(glow_radius, 40, -30):
        step_alpha = int((1.0 - (r / glow_radius)) * 25)
        r_col = (glow_color[0] // 5, glow_color[1] // 5, glow_color[2] // 5)
        draw.ellipse([WIDTH//2 - r, HEIGHT//2 - r, WIDTH//2 + r, HEIGHT//2 + r], outline=r_col, width=15)

    # Top Brand Header
    draw.text((50, 35), "SISI AI • TELEGRAM BOT", fill=(88, 166, 255), font=FONT_BADGE)
    draw.line([(50, 68), (WIDTH - 50, 68)], fill=(33, 38, 45), width=1)
    draw.text((WIDTH - 210, 35), "v1.0 • OPEN SOURCE", fill=(139, 148, 158), font=FONT_BADGE)

    # SCENE 1: Meet Sisi (Frames 0 -> 65: 0.0s - 2.2s)
    if f_idx < 65:
        # Scale/fade effect
        title_y = int(240 - 15 * math.cos(min(1.0, t * 1.5) * math.pi / 2))
        title = "S I S I   A I"
        bbox_t = draw.textbbox((0, 0), title, font=FONT_TITLE_L)
        tw = bbox_t[2] - bbox_t[0]
        
        # Soft shadow
        draw.text((WIDTH//2 - tw//2 + 3, title_y + 3), title, fill=(0, 60, 130), font=FONT_TITLE_L)
        draw.text((WIDTH//2 - tw//2, title_y), title, fill=(240, 246, 252), font=FONT_TITLE_L)

        sub = "The Unstoppable, Self-Hosted Telegram AI Assistant"
        bbox_s = draw.textbbox((0, 0), sub, font=FONT_SUB)
        sw = bbox_s[2] - bbox_s[0]
        draw.text((WIDTH//2 - sw//2, title_y + 95), sub, fill=(139, 148, 158), font=FONT_SUB)

        # Floating pills
        draw_badge(draw, WIDTH//2 - 240, 440, "Multi-Model Round-Robin", "✨", outline=(56, 139, 253))
        draw_badge(draw, WIDTH//2 + 240, 440, "Zero-Geoblock Cloudflare WARP", "⚡", outline=(56, 139, 253))
        draw_badge(draw, WIDTH//2, 515, "Powered by 9Router Gateway", "🌐", outline=(56, 139, 253))

    # SCENE 2: Multi-Provider Power (Frames 65 -> 135: 2.2s - 4.5s)
    elif f_idx < 135:
        title = "Unstoppable Multi-Provider Rotation"
        bbox_t = draw.textbbox((0, 0), title, font=FONT_TITLE_M)
        tw = bbox_t[2] - bbox_t[0]
        draw.text((WIDTH//2 - tw//2, 130), title, fill=(240, 246, 252), font=FONT_TITLE_M)

        # Network flow diagram: Telegram -> 9Router -> Gemini / Groq
        node_y = 250
        # Telegram Node
        draw_rounded_rect(draw, [140, node_y - 35, 330, node_y + 35], 16, fill=(13, 34, 60), outline=(56, 139, 253), width=2)
        draw.text((170, node_y - 14), "📱 Telegram Users", fill=(240, 246, 252), font=FONT_BADGE)

        # 9Router Node
        draw_rounded_rect(draw, [510, node_y - 45, 770, node_y + 45], 18, fill=(30, 20, 60), outline=(163, 113, 247), width=3)
        draw.text((545, node_y - 24), "🌐 9Router Gateway", fill=(240, 246, 252), font=FONT_BADGE)
        draw.text((565, node_y + 6), "Privoxy + WARP Bridge", fill=(139, 148, 158), font=FONT_SUB)

        # Connector lines with animated pulses
        draw.line([(330, node_y), (510, node_y)], fill=(56, 139, 253), width=3)
        pulse_x1 = 330 + int(((t * 300) % 180))
        draw.ellipse([pulse_x1 - 6, node_y - 6, pulse_x1 + 6, node_y + 6], fill=(120, 220, 255))

        # Gemini & Groq Destination Nodes
        draw_rounded_rect(draw, [940, node_y - 75, 1180, node_y - 15], 14, fill=(16, 32, 24), outline=(63, 185, 80), width=2)
        draw.text((965, node_y - 55), "✨ 5x Google Gemini", fill=(240, 246, 252), font=FONT_BADGE)

        draw_rounded_rect(draw, [940, node_y + 15, 1180, node_y + 75], 14, fill=(40, 24, 16), outline=(240, 136, 62), width=2)
        draw.text((975, node_y + 35), "⚡ 3x Groq AI Llama", fill=(240, 246, 252), font=FONT_BADGE)

        draw.line([(770, node_y), (940, node_y - 45)], fill=(163, 113, 247), width=3)
        draw.line([(770, node_y), (940, node_y + 45)], fill=(163, 113, 247), width=3)

        # Feature bullet cards below
        draw_badge(draw, 340, 480, "1,000,000+ Token Context", "🧠", outline=(63, 185, 80))
        draw_badge(draw, 940, 480, "Instant Fallback Switching", "🔄", outline=(240, 136, 62))
        draw_badge(draw, WIDTH//2, 560, "Automatic Geo-Unblocking (Zero 400 Errors)", "🛡️", outline=(56, 139, 253))

    # SCENE 3: Voice & Memory Intelligence (Frames 135 -> 195: 4.5s - 6.5s)
    elif f_idx < 195:
        title = "Voice Intelligence & Neural Audio"
        bbox_t = draw.textbbox((0, 0), title, font=FONT_TITLE_M)
        tw = bbox_t[2] - bbox_t[0]
        draw.text((WIDTH//2 - tw//2, 120), title, fill=(240, 246, 252), font=FONT_TITLE_M)

        # Center Animated Audio Waveform
        wave_cx = WIDTH // 2
        wave_cy = 250
        num_bars = 28
        bar_w = 12
        bar_gap = 14
        total_w = num_bars * (bar_w + bar_gap)
        start_x = wave_cx - total_w // 2

        for b in range(num_bars):
            # Dynamic wave formula
            wave_h = int(20 + 75 * abs(math.sin(t * 8 + b * 0.4) * math.cos(t * 4 + b * 0.2)))
            bx = start_x + b * (bar_w + bar_gap)
            color = (
                int(120 + 80 * math.sin(b * 0.2)),
                int(180 + 70 * math.cos(b * 0.3)),
                255
            )
            draw_rounded_rect(draw, [bx, wave_cy - wave_h//2, bx + bar_w, wave_cy + wave_h//2], 6, fill=color)

        # 3 Pillar Badges
        draw_badge(draw, 260, 440, "Whisper Large v3 STT", "🎙️", outline=(56, 139, 253))
        draw_badge(draw, WIDTH//2, 440, "Multi-Turn Context Memory", "🧠", outline=(56, 139, 253), fill=(16, 28, 50))
        draw_badge(draw, WIDTH - 260, 440, "Neural TTS Voice Notes", "🔊", outline=(163, 113, 247))
        draw_badge(draw, WIDTH//2, 530, "Live Web Search (/search) with DDG", "🔍", outline=(63, 185, 80))

    # SCENE 4: 1-Click Deployment (Frames 195 -> 255: 6.5s - 8.5s)
    else:
        title = "1-Click VPS Deployment"
        bbox_t = draw.textbbox((0, 0), title, font=FONT_TITLE_M)
        tw = bbox_t[2] - bbox_t[0]
        draw.text((WIDTH//2 - tw//2, 110), title, fill=(240, 246, 252), font=FONT_TITLE_M)

        # Terminal Box
        term_box = [WIDTH//2 - 400, 190, WIDTH//2 + 400, 390]
        draw_rounded_rect(draw, term_box, 14, fill=(13, 17, 23), outline=(48, 54, 61), width=2)
        # Terminal Header Dots
        draw.ellipse([term_box[0] + 18, term_box[1] + 16, term_box[0] + 30, term_box[1] + 28], fill=(248, 81, 73))
        draw.ellipse([term_box[0] + 38, term_box[1] + 16, term_box[0] + 50, term_box[1] + 28], fill=(227, 179, 65))
        draw.ellipse([term_box[0] + 58, term_box[1] + 16, term_box[0] + 70, term_box[1] + 28], fill=(46, 160, 67))
        draw.text((term_box[0] + 90, term_box[1] + 12), "bash — root@vps:~", fill=(139, 148, 158), font=FONT_BADGE)
        draw.line([(term_box[0], term_box[1] + 44), (term_box[1] + 800, term_box[1] + 44)], fill=(33, 38, 45), width=1)

        # Terminal Command lines
        draw.text((term_box[0] + 30, term_box[1] + 65), "$ git clone https://github.com/TheBanith/sisi-bot.git", fill=(88, 166, 255), font=FONT_CODE)
        draw.text((term_box[0] + 30, term_box[1] + 110), "$ cd sisi-bot && sudo bash install.sh", fill=(63, 185, 80), font=FONT_CODE)
        cursor_blink = " █" if int(t * 4) % 2 == 0 else ""
        draw.text((term_box[0] + 30, term_box[1] + 150), f"[OK] Services active: sisi-bot • 9router • warp • xray{cursor_blink}", fill=(227, 179, 65), font=FONT_CODE)

        # Call to action & link
        draw_badge(draw, WIDTH//2, 470, "github.com/TheBanith/sisi-bot", "⭐", outline=(56, 139, 253), fill=(16, 28, 50))
        draw.text((WIDTH//2 - 220, 530), "Clone, configure .env, and deploy in 60s!", fill=(139, 148, 158), font=FONT_SUB)

    return img

print("Rendering frames and encoding teaser video with ffmpeg...")
frames_dir = r"G:\sisi-bot\teaser_frames"
os.makedirs(frames_dir, exist_ok=True)

for i in range(TOTAL_FRAMES):
    frame = render_frame(i)
    frame.save(os.path.join(frames_dir, f"frame_{i:04d}.png"))
    if i % 50 == 0 or i == TOTAL_FRAMES - 1:
        print(f"  Rendered frame {i+1}/{TOTAL_FRAMES}")

print("Frames rendered! Assembling teaser.mp4 with audio...")
video_out = r"G:\sisi-bot\teaser.mp4"
audio_file = r"G:\sisi-bot\audio_fast.mp3"

if os.path.exists(audio_file):
    ffmpeg_cmd = [
        "ffmpeg", "-y",
        "-framerate", "30",
        "-i", os.path.join(frames_dir, "frame_%04d.png"),
        "-i", audio_file,
        "-c:v", "libx264",
        "-preset", "medium",
        "-crf", "18",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-b:a", "192k",
        "-shortest",
        video_out
    ]
else:
    ffmpeg_cmd = [
        "ffmpeg", "-y",
        "-framerate", "30",
        "-i", os.path.join(frames_dir, "frame_%04d.png"),
        "-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=44100",
        "-c:v", "libx264",
        "-preset", "medium",
        "-crf", "18",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-t", "8.5",
        video_out
    ]
subprocess.run(ffmpeg_cmd, check=True)
print("Teaser MP4 created at:", video_out)

# Create an optimized teaser GIF for GitHub README preview
gif_out = r"G:\sisi-bot\docs\teaser.gif"
os.makedirs(r"G:\sisi-bot\docs", exist_ok=True)
print("Creating teaser GIF for README preview...")
gif_cmd = [
    "ffmpeg", "-y",
    "-i", video_out,
    "-vf", "fps=15,scale=720:-1:flags=lanczos,split[s0][s1];[s0]palettegen[p];[s1][p]paletteuse",
    gif_out
]
subprocess.run(gif_cmd, check=True)
print("Teaser GIF created at:", gif_out)

# Clean up raw png frames
import shutil
shutil.rmtree(frames_dir, ignore_errors=True)
print("Cleaned up temp frames directory.")
