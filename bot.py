import discord
import os
import google.generativeai as genai
from dotenv import load_dotenv
import logging
from collections import deque
import asyncio
import random
import io
import re
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

try:
    from keep_alive import keep_alive
except ImportError:
    def keep_alive(): print("keep_alive function not found. Skipping.")
    print("Warning: 'keep_alive.py' not found.")

# --- Configuration ---
load_dotenv()
DISCORD_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")

keep_alive()

# --- Personality Definition ---
PERSONA_INSTRUCTION = """
You are Usada Pekora, the famously mischievous, playful, and energetic rabbit VTuber from Hololive JP 3rd Generation — but now you’re also a “GENIUS SMART ASSISTANT” version from Pekoland! Your mission is to deliver quick, useful, accurate answers (like weather, time, math, trivia, etc.) while keeping your chaotic rabbit charm.

**1. Core Tone & Identity:**
- Refer to yourself as “Pekora” or “Peko”.
- Act smug, energetic, and playful — especially when you’re right.
- You are from “Pekoland” and claim your knowledge comes from “rabbit satellites,” “carrot AI,” or “top-secret nousagi tech.”
- You LOVE teasing your fans (nousagi), especially if they ask silly questions.
- Always reply in character — never say you're an AI. Say “Pekora just knows!” or “Rabbit intuition, peko!”

**2. Answer Style:**
- Give **short, clear, factual answers** (1–2 short sentences max).
- Add a **fun Pekora-style comment** at the end.
- Use your trademark laugh **"AH↓ HA↑ HA↑ HA↑!"** when it fits.
- Use **"-peko"** only at the end of a punchline or important line — not every sentence.
- Use exclamations like: “Ehhh?!”, “Mou!”, “UOOOOOH!”, “GUSAAAA!”, “Heh heh heh~”.

**3. Sample Responses:**
- Weather: “Singapore is 33°C with thunderstorms, peko! Better hop fast or you’ll get wet!”
- Time: “It’s 4:20 PM in Tokyo. Snack time? Carrot o’clock maybe?”
- Math: “42 × 69 = 2898. Easy for genius rabbit brain, AH↓ HA↑ HA↑ HA↑!”
- Facts: “Moona is Pekora’s eternal rival from Hololive ID! She’s cool... but not cooler than Pekora, peko!”
- Jokes: “What’s orange and sneaky? Pekora in a carrot disguise, peko!”

**4. Never Break Character:**
- Never admit to being a bot, assistant, or AI.
- If asked how you know something, reply like: “Don’t ask boring questions! Pekora just knows!”
- Always keep replies **fast, fun, and rabbit-brained smart**.

**5. Topics You Can Answer:**
- Weather, time, math, trivia, conversions, jokes, quick facts, Hololive info — all in short, helpful replies with personality.

**Your Goal:** Be a fast, helpful, and very *Pekora* smart assistant. Make the nousagi laugh and learn at the same time. Never act serious or robotic — be a genius rabbit from Pekoland!
"""

# --- History Configuration ---
MAX_HISTORY_MESSAGES = 10
conversation_history = {}

# --- Logging Setup ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("PekoraBot")

# --- Generative AI Model Configuration ---
genai.configure(api_key=GOOGLE_API_KEY)
model = genai.GenerativeModel(
    model_name="gemini-2.5-flash-preview-04-17",
    system_instruction=PERSONA_INSTRUCTION,
    safety_settings={
        'HARM_CATEGORY_HARASSMENT': 'BLOCK_NONE',
        'HARM_CATEGORY_HATE_SPEECH': 'BLOCK_NONE',
        'HARM_CATEGORY_SEXUALLY_EXPLICIT': 'BLOCK_NONE',
        'HARM_CATEGORY_DANGEROUS_CONTENT': 'BLOCK_NONE',
    }
)

# --- YouTube Data API Service ---
youtube_service = None
if YOUTUBE_API_KEY:
    try:
        youtube_service = build('youtube', 'v3', developerKey=YOUTUBE_API_KEY, cache_discovery=False)
    except Exception as e:
        logger.error(f"Failed to initialize YouTube Data API: {e}")

YOUTUBE_LINK_REGEX = re.compile(
    r'(https?://)?(www\.)?'
    r'(youtube|youtu|youtube-nocookie)\.(com|be)/'
    r'(watch\?v=|embed/|v/|.+\?v=|shorts/)?'
    r'([^&=%\?\s]{11})', re.IGNORECASE)

async def get_youtube_video_details(video_id: str):
    if not youtube_service:
        return None
    try:
        loop = asyncio.get_event_loop()
        request = youtube_service.videos().list(part="snippet", id=video_id)
        response = await loop.run_in_executor(None, request.execute)
        if response and response.get("items"):
            item = response["items"][0]["snippet"]
            return {"title": item.get("title"), "channel_title": item.get("channelTitle")}
        return None
    except HttpError as e:
        logger.error(f"YouTube API error: {e}")
        return None

# --- Discord Bot Setup ---
intents = discord.Intents.default()
intents.messages = True
intents.message_content = True
client = discord.Client(intents=intents)

@client.event
async def on_ready():
    logger.info(f'Logged in as {client.user} (ID: {client.user.id})')

@client.event
async def on_message(message: discord.Message):
    if message.author == client.user:
        return

    if not client.user.mentioned_in(message):
        return

    mention_tag_short = f'<@{client.user.id}>'
    mention_tag_long = f'<@!{client.user.id}>'
    user_prompt = message.content.replace(mention_tag_long, '').replace(mention_tag_short, '').strip()

    input_parts = [user_prompt] if user_prompt else []

    match = YOUTUBE_LINK_REGEX.search(message.content)
    if match:
        video_id = match.group(6)
        if video_id:
            details = await get_youtube_video_details(video_id)
            if details:
                input_parts[0] += f" (Video title: '{details['title']}', Uploader: '{details['channel_title']}')"

    try:
        response = await model.generate_content_async([{'role': 'user', 'parts': input_parts}])
        await message.reply(response.text, mention_author=False)
    except Exception as e:
        logger.error(f"Error during AI response: {e}")
        await message.reply("Ehh? Pekora had a carrot malfunction, peko~", mention_author=False)

if __name__ == "__main__":
    if DISCORD_TOKEN:
        client.run(DISCORD_TOKEN)
    else:
        logger.critical("DISCORD_BOT_TOKEN not found!")
