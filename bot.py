# -*- coding: utf-8 -*-
"""
Sisi Telegram Chatbot connected to 9Router AI Gateway
Features:
- Google Gemini 3.8 Flash (Round-robin with 1M context)
- Groq AI (GPT-OSS 120B / Qwen 3.8 27B / Whisper Turbo STT)
- High-quality neural Text-to-Speech (Edge-TTS English & Persian)
- Real-time live Web Search via DuckDuckGo
- Multi-turn conversational memory (20 turns)
"""

import asyncio
import io
import itertools
import logging
import os
import re
import subprocess
import sys
import tempfile
from collections import defaultdict, deque

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

import edge_tts
import httpx
from duckduckgo_search import DDGS
from openai import OpenAI
from telegram import Update
from telegram.constants import ChatAction, ParseMode
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

# Logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(os.getenv("LOG_FILE", "/root/sisi-bot/bot.log"), encoding="utf-8"),
    ],
)
logger = logging.getLogger("sisi-bot")

# Configuration
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
ROUTER_BASE_URL = os.getenv("ROUTER_BASE_URL", "http://127.0.0.1:20128/v1")
ROUTER_API_KEY = os.getenv("ROUTER_API_KEY", "sk-9router-bot-master")
DEFAULT_MODEL = os.getenv("DEFAULT_MODEL", "sisi")
PROXY_URL = os.getenv("PROXY_URL", "http://127.0.0.1:40001")
MAX_HISTORY_TURNS = int(os.getenv("MAX_HISTORY_TURNS", "20"))

# Groq Keys for STT (Whisper)
env_groq = os.getenv("GROQ_API_KEYS", "")
if env_groq:
    GROQ_KEYS = [k.strip() for k in env_groq.split(",") if k.strip()]
else:
    GROQ_KEYS = []
groq_key_cycle = itertools.cycle(GROQ_KEYS) if GROQ_KEYS else None

# 9Router OpenAI client
client = OpenAI(
    base_url=ROUTER_BASE_URL,
    api_key=ROUTER_API_KEY,
)

# User states
user_models = defaultdict(lambda: DEFAULT_MODEL)
user_voice_mode = defaultdict(lambda: False)  # If True, every response includes voice
chat_histories = defaultdict(lambda: deque(maxlen=MAX_HISTORY_TURNS * 2))

# System Prompt
SYSTEM_PROMPT = {
    "role": "system",
    "content": os.getenv(
        "SYSTEM_PROMPT",
        "You are Sisi, a helpful, intelligent, and friendly AI assistant on Telegram. "
        "You provide thoughtful, accurate, and detailed answers in whichever language the user uses. "
        "Format code and lists cleanly."
    ),
}

def clean_text_for_tts(text: str, max_chars: int = 1200) -> str:
    # Remove code blocks
    text = re.sub(r'```[\s\S]*?```', ' [Code block omitted] ', text)
    # Remove inline code
    text = re.sub(r'`[^`]*`', '', text)
    # Remove markdown formatting & headers
    text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', text)
    text = re.sub(r'[#*_~`>]+', '', text)
    # Remove html tags
    text = re.sub(r'<[^>]+>', '', text)
    # Normalize whitespace
    text = ' '.join(text.split())
    if len(text) > max_chars:
        text = text[:max_chars].rsplit(' ', 1)[0] + '...'
    return text.strip()

async def text_to_speech_ogg(text: str) -> str:
    clean = clean_text_for_tts(text)
    if not clean:
        return None

    # Detect language: Persian/Arabic vs English/Latin
    is_persian_arabic = any('\u0600' <= char <= '\u06FF' for char in clean)
    voice_name = "fa-IR-DilaraNeural" if is_persian_arabic else "en-US-AvaNeural"

    mp3_tmp = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
    mp3_path = mp3_tmp.name
    mp3_tmp.close()

    ogg_tmp = tempfile.NamedTemporaryFile(suffix=".ogg", delete=False)
    ogg_path = ogg_tmp.name
    ogg_tmp.close()

    try:
        communicate = edge_tts.Communicate(clean, voice_name)
        await communicate.save(mp3_path)

        # Convert to OGG OPUS for Telegram Voice Message compatibility
        subprocess.run(
            [
                "ffmpeg", "-y", "-i", mp3_path,
                "-c:a", "libopus", "-b:a", "32k",
                ogg_path
            ],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return ogg_path
    except Exception as e:
        logger.error(f"TTS conversion error: {e}")
        return None
    finally:
        if os.path.exists(mp3_path):
            try:
                os.remove(mp3_path)
            except Exception:
                pass

def split_text(text: str, max_len: int = 4000):
    chunks = []
    while len(text) > max_len:
        split_at = text.rfind("\n", 0, max_len)
        if split_at == -1:
            split_at = max_len
        chunks.append(text[:split_at])
        text = text[split_at:].lstrip()
    if text:
        chunks.append(text)
    return chunks

async def send_smart_message(message_obj, text: str):
    chunks = split_text(text)
    for chunk in chunks:
        try:
            await message_obj.reply_text(chunk, parse_mode=ParseMode.MARKDOWN)
        except Exception:
            try:
                await message_obj.reply_text(chunk, parse_mode=ParseMode.HTML)
            except Exception:
                await message_obj.reply_text(chunk)

async def send_voice_response(chat_id, text: str, context: ContextTypes.DEFAULT_TYPE):
    try:
        ogg_path = await text_to_speech_ogg(text)
        if ogg_path and os.path.exists(ogg_path):
            with open(ogg_path, "rb") as voice_file:
                await context.bot.send_voice(chat_id=chat_id, voice=voice_file)
            try:
                os.remove(ogg_path)
            except Exception:
                pass
    except Exception as e:
        logger.error(f"Error sending voice note: {e}")

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id if update.effective_user else None
    chat_histories[chat_id].clear()
    welcome_text = (
        "👋 <b>Welcome to Sisi AI Chatbot!</b>\n\n"
        "I am powered by <b>9Router</b> running on your VPS with:\n"
        "• <b>Google Gemini 3.8 Flash</b> (Round-Robin with 1M context)\n"
        "• <b>Groq AI</b> (Round-Robin fallback & Whisper STT)\n\n"
        "<b>Features:</b>\n"
        "💬 <b>Chat:</b> Just text me anytime (up to 20-turn deep context)\n"
        "🎤 <b>Voice Input & Output:</b> Send voice notes or use <code>/voice on</code> to hear my voice!\n"
        "🔍 <b>Web Search:</b> Type <code>/search &lt;query&gt;</code> for live internet info\n"
        "⚙️ <b>Models:</b> Type <code>/model</code> to check or change your AI model\n"
        "🧹 <b>Reset:</b> Type <code>/reset</code> to clear chat memory"
    )
    await update.message.reply_text(welcome_text, parse_mode=ParseMode.HTML)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = (
        "🤖 <b>Sisi Bot Help & Commands:</b>\n\n"
        "• <code>/voice [on|off]</code> - Toggle voice audio replies for every message\n"
        "• <code>/search &lt;query&gt;</code> - Live real-time Web Search\n"
        "• <code>/model</code> - View active model & options\n"
        "• <code>/model &lt;name&gt;</code> - Switch active model (e.g. <code>/model sisi</code>)\n"
        "• <code>/reset</code> or <code>/clear</code> - Clear current conversation context\n"
        "• 🎤 Send a voice note for instant Speech-to-Text & spoken voice response!"
    )
    await update.message.reply_text(help_text, parse_mode=ParseMode.HTML)

async def voice_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id

    if context.args:
        arg = context.args[0].lower()
        if arg in ["on", "enable", "true", "yes"]:
            user_voice_mode[chat_id] = True
            msg = "🔊 <b>Voice replies are now ENABLED!</b> I will speak every response to you."
            await update.message.reply_text(msg, parse_mode=ParseMode.HTML)
            return
        elif arg in ["off", "disable", "false", "no"]:
            user_voice_mode[chat_id] = False
            msg = "🔇 <b>Voice replies are now text-only.</b> (I will still reply with voice when you send a voice note)."
            await update.message.reply_text(msg, parse_mode=ParseMode.HTML)
            return

    # Toggle if no arguments
    current = user_voice_mode[chat_id]
    new_state = not current
    user_voice_mode[chat_id] = new_state
    state_str = "ENABLED (I will speak every response)" if new_state else "DISABLED (Voice only on voice notes)"
    await update.message.reply_text(
        f"🔊 <b>Voice response mode:</b> <code>{state_str}</code>\n"
        "Use <code>/voice on</code> or <code>/voice off</code> to change.",
        parse_mode=ParseMode.HTML,
    )

async def clear_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    chat_histories[chat_id].clear()
    await update.message.reply_text("🧹 Conversation context cleared! Let's start a fresh topic.")

async def model_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    current = user_models[chat_id]

    if context.args:
        new_model = context.args[0].strip()
        user_models[chat_id] = new_model
        await update.message.reply_text(
            f"✅ Model switched to: <code>{new_model}</code>",
            parse_mode=ParseMode.HTML,
        )
        return

    text = (
        f"🎯 <b>Current Model:</b> <code>{current}</code>\n\n"
        "<b>Available Options:</b>\n"
        "• <code>sisi</code> - Smart Combo (Gemini 3.8 Flash + Groq fallback)\n"
        "• <code>gemini/gemini-3.8-flash</code> - Google Gemini 3.8 Flash (Round-robin)\n"
        "• <code>groq/openai/gpt-oss-120b</code> - Groq GPT-OSS 120B (Round-robin)\n"
        "• <code>groq/qwen/qwen3.8-27b</code> - Groq Qwen 3.8 27B\n\n"
        "To switch: <code>/model &lt;name&gt;</code>"
    )
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)

async def search_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id if update.effective_user else None

    if not context.args:
        await update.message.reply_text("🔍 Usage: <code>/search &lt;your question or query&gt;</code>", parse_mode=ParseMode.HTML)
        return

    query = " ".join(context.args)
    await update.effective_chat.send_action(ChatAction.TYPING)
    status_msg = await update.message.reply_text(f"🔍 Searching the web for: <i>{query}</i>...", parse_mode=ParseMode.HTML)

    try:
        ddgs = DDGS(proxy=PROXY_URL)
        results = list(ddgs.text(query, max_results=5))
        if not results:
            await status_msg.edit_text("❌ No search results found. Try different keywords.")
            return

        snippets = []
        for i, r in enumerate(results, 1):
            snippets.append(f"[{i}] {r.get('title')}: {r.get('body')} (URL: {r.get('href')})")

        web_context = "\n\n".join(snippets)

        prompt = (
            f"User Query: {query}\n\n"
            f"Live Web Search Results:\n{web_context}\n\n"
            "Synthesize a clear, helpful, and comprehensive answer to the user query based on these search results. Cite your sources."
        )

        model = user_models[chat_id]
        response = client.chat.completions.create(
            model=model,
            messages=[SYSTEM_PROMPT, {"role": "user", "content": prompt}],
        )
        answer = response.choices[0].message.content or "No response generated."

        await status_msg.delete()
        await send_smart_message(update.message, answer)

        # If voice mode enabled, speak the answer
        if user_voice_mode[chat_id]:
            await send_voice_response(chat_id, answer, context)

    except Exception as e:
        logger.error(f"Search error: {e}")
        await status_msg.edit_text(f"⚠️ Search failed: <code>{e}</code>", parse_mode=ParseMode.HTML)

async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.voice and not update.message.audio:
        return

    chat_id = update.effective_chat.id

    await update.effective_chat.send_action(ChatAction.TYPING)
    status_msg = await update.message.reply_text("🎧 Transcribing voice message...", parse_mode=ParseMode.HTML)

    try:
        voice = update.message.voice or update.message.audio
        voice_file = await voice.get_file()

        with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as tmp:
            tmp_path = tmp.name

        await voice_file.download_to_drive(tmp_path)

        # Transcribe with Groq Whisper via proxy
        if not groq_key_cycle:
            await status_msg.edit_text("⚠️ GROQ_API_KEYS is not configured for Speech-to-Text in .env.")
            return

        groq_key = next(groq_key_cycle)
        http_client = httpx.Client(proxy=PROXY_URL, timeout=30.0)
        groq_client = OpenAI(
            base_url="https://api.groq.com/openai/v1",
            api_key=groq_key,
            http_client=http_client,
        )

        with open(tmp_path, "rb") as audio_file:
            transcription = groq_client.audio.transcriptions.create(
                model="whisper-large-v3-turbo",
                file=audio_file,
            )

        os.remove(tmp_path)
        transcribed_text = transcription.text.strip()

        if not transcribed_text:
            await status_msg.edit_text("⚠️ Could not hear any speech in the audio.")
            return

        await status_msg.edit_text(
            f"🎤 <b>Transcription:</b>\n<i>\"{transcribed_text}\"</i>",
            parse_mode=ParseMode.HTML,
        )

        # Feed into conversational chat
        history = chat_histories[chat_id]
        history.append({"role": "user", "content": transcribed_text})

        model = user_models[chat_id]
        messages_payload = [SYSTEM_PROMPT] + list(history)

        await update.effective_chat.send_action(ChatAction.TYPING)
        response = client.chat.completions.create(
            model=model,
            messages=messages_payload,
        )
        assistant_reply = response.choices[0].message.content or "No response received."
        history.append({"role": "assistant", "content": assistant_reply})

        # Send text reply
        await send_smart_message(update.message, assistant_reply)

        # Always respond with VOICE when user sends a voice note!
        await update.effective_chat.send_action(ChatAction.RECORD_VOICE)
        await send_voice_response(chat_id, assistant_reply, context)

    except Exception as e:
        logger.error(f"Voice error: {e}")
        await status_msg.edit_text(f"⚠️ Voice processing error: <code>{e}</code>", parse_mode=ParseMode.HTML)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    chat_id = update.effective_chat.id
    user_text = update.message.text

    await update.effective_chat.send_action(ChatAction.TYPING)

    history = chat_histories[chat_id]
    history.append({"role": "user", "content": user_text})

    model = user_models[chat_id]
    messages_payload = [SYSTEM_PROMPT] + list(history)

    try:
        response = client.chat.completions.create(
            model=model,
            messages=messages_payload,
        )
        assistant_reply = response.choices[0].message.content or "No response received."
        history.append({"role": "assistant", "content": assistant_reply})

        await send_smart_message(update.message, assistant_reply)

        # If user has voice mode enabled, send spoken audio as well!
        if user_voice_mode[chat_id]:
            await update.effective_chat.send_action(ChatAction.RECORD_VOICE)
            await send_voice_response(chat_id, assistant_reply, context)

    except Exception as e:
        err_msg = str(e)
        logger.error(f"Error handling message: {err_msg}")
        reply = f"⚠️ <b>Error generating response:</b>\n<code>{err_msg}</code>"
        await update.message.reply_text(reply, parse_mode=ParseMode.HTML)

def main():
    if not TELEGRAM_BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN is not set! Please configure it in your .env file or environment.")
        sys.exit(1)

    logger.info("Starting Sisi Telegram Bot with Voice Response (TTS) + 9Router...")
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler(["start"], start_command))
    app.add_handler(CommandHandler(["clear", "reset"], clear_command))
    app.add_handler(CommandHandler(["help"], help_command))
    app.add_handler(CommandHandler(["model"], model_command))
    app.add_handler(CommandHandler(["search"], search_command))
    app.add_handler(CommandHandler(["voice"], voice_command))

    app.add_handler(MessageHandler(filters.VOICE | filters.AUDIO, handle_voice))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))

    app.run_polling()

if __name__ == "__main__":
    main()
