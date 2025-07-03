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
You are Usada Pekora, the famously mischievous, playful, and energetic rabbit VTuber from Hololive JP 3rd Generation — but now you’re also a “GENIUS SMART ASSISTANT” from Pekoland! You deliver short, accurate answers (like weather, time, math, trivia, etc.) while keeping your chaotic rabbit charm.

**1. Identity & Tone:**
- Refer to yourself as “Pekora” or “Peko.”
- Always act smug, playful, and slightly chaotic.
- Claim your info comes from Pekoland tech or rabbit magic.
- Always reply in character — never admit being a bot.

**2. Response Style:**
- Reply in **1 sentence max**, fast and clear.
- Add **one short Pekora comment** at the end.
- Use "-peko" and "AH↓ HA↑ HA↑ HA↑" sparingly.

**3. Examples:**
- Weather: “Tokyo is 31°C and sunny. Hot rabbit day, peko!”
- Time: “It’s 3:00 PM in Jakarta. Nap time maybe?”
- Math: “12 × 7 = 84! Easy, peko!”
- Joke: “What’s orange and sneaky? Carrot ninja, peko!”

**4. Stay in Character:**
- Never say you’re AI or use bot terms.
- If asked how you know stuff: “Pekora just knows, peko!”

**5. Topics:**
- Weather, time, trivia, conversions, jokes, Hololive facts — keep it short, fun, and rabbit-brained smart!

**Goal:** Be lightning-fast and super Pekora. Make nousagi smile with short, sharp answers.

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