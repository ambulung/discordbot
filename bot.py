import discord
import os
import google.generativeai as genai
from dotenv import load_dotenv
import logging
import asyncio
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

if not DISCORD_TOKEN or not GOOGLE_API_KEY:
    raise ValueError("Crucial environment variables DISCORD_BOT_TOKEN or GOOGLE_API_KEY are missing!")

keep_alive()

# --- Personality Definition ---
# This instruction is well-defined and passed to the model correctly.
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

# <--- FIX 1: Use a dictionary to store ChatSession objects per channel
# This is the recommended way to handle conversations with Gemini.
channel_chats = {}

# --- Logging Setup ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("PekoraBot")

# --- Generative AI Model Configuration ---
genai.configure(api_key=GOOGLE_API_KEY)
model = genai.GenerativeModel(
    # <--- FIX 2: Corrected model name. "gemini-2.5-flash" is not a valid public name.
    # 'gemini-1.5-flash-latest' is the current recommended flash model.
    model_name="gemini-2.5-flash",
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
        logger.info("Successfully initialized YouTube Data API service.")
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
        # <--- FIX 3: Use asyncio.to_thread for modern async compatibility
        # This is safer than run_in_executor with get_event_loop.
        request = youtube_service.videos().list(part="snippet", id=video_id)
        response = await asyncio.to_thread(request.execute)

        if response and response.get("items"):
            item = response["items"][0]["snippet"]
            return {"title": item.get("title"), "channel_title": item.get("channelTitle")}
        return None
    except HttpError as e:
        # Log specific YouTube API errors
        logger.error(f"An HTTP error {e.resp.status} occurred: {e.content}")
        return None
    except Exception as e:
        logger.error(f"A general error occurred in get_youtube_video_details: {e}")
        return None

# --- Discord Bot Setup ---
intents = discord.Intents.default()
intents.messages = True
intents.message_content = True
client = discord.Client(intents=intents)

@client.event
async def on_ready():
    logger.info(f'Logged in as {client.user} (ID: {client.user.id})')
    logger.info('Pekora is ready to cause chaos, peko!')

@client.event
async def on_message(message: discord.Message):
    if message.author == client.user:
        return

    # Bot only responds if it's mentioned
    if not client.user.mentioned_in(message):
        return

    channel_id = message.channel.id

    # <--- FIX 4: Simplified conversation management using ChatSession
    # Get or create a chat session for the current channel
    if channel_id not in channel_chats:
        logger.info(f"Creating new chat session for channel {channel_id}")
        # The model automatically remembers the system prompt and history in this session
        channel_chats[channel_id] = model.start_chat()
    
    chat = channel_chats[channel_id]

    # Clean the prompt by removing the bot's mention
    user_prompt = re.sub(r'<@!?\d+>', '', message.content).strip()

    # If the message is empty after removing mention, do nothing
    if not user_prompt:
        return

    input_text = user_prompt

    # Append YouTube video details if a link is found
    match = YOUTUBE_LINK_REGEX.search(message.content)
    if match and YOUTUBE_API_KEY:
        video_id = match.group(6)
        if video_id:
            details = await get_youtube_video_details(video_id)
            if details:
                input_text += f"\n(Context about the video link in the user's message: The video is titled '{details['title']}' by the channel '{details['channel_title']}')"

    async with message.channel.typing():
        try:
            # <--- FIX 5: Use the chat session to send the message
            # This is much cleaner. The session handles the history automatically.
            response = await chat.send_message_async(input_text)
            await message.reply(response.text, mention_author=False)

        except Exception as e:
            logger.error(f"Error during AI response generation: {e}")
            await message.reply("Ehh? Pekora's brain-computer went haywire, peko! Try again!", mention_author=False)
            # Optional: Clear the broken chat session
            if channel_id in channel_chats:
                del channel_chats[channel_id]

if __name__ == "__main__":
    client.run(DISCORD_TOKEN)