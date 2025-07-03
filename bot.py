import discord
import os
import google.generativeai as genai
from dotenv import load_dotenv
import logging
import asyncio
import re
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# This is a helper function to keep the bot running on services like Replit.
# If you are not using Replit, you can safely ignore this part.
try:
    from keep_alive import keep_alive
except ImportError:
    def keep_alive():
        print("keep_alive function not found. If not using a hosting service like Replit, this is normal.")
    print("Warning: 'keep_alive.py' not found. The bot will run without the keep_alive server.")

# --- Configuration ---
load_dotenv()
DISCORD_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY") # This one is optional

# Halt if crucial tokens are missing
if not DISCORD_TOKEN or not GOOGLE_API_KEY:
    raise ValueError("FATAL: Environment variables DISCORD_BOT_TOKEN or GOOGLE_API_KEY are missing!")

# Start the keep_alive server if it exists
keep_alive()

# --- Personality Definition ---
# This system instruction defines the bot's persona.
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

# --- Chat Session Management ---
# This dictionary will store a ChatSession object for each channel to maintain conversation history.
channel_chats = {}

# --- Logging Setup ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("PekoraBot")

# --- Generative AI Model Configuration ---
genai.configure(api_key=GOOGLE_API_KEY)
model = genai.GenerativeModel(
    model_name="gemini-2.5-flash", # Correct model name
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
        # Build the YouTube service object
        youtube_service = build('youtube', 'v3', developerKey=YOUTUBE_API_KEY, cache_discovery=False)
        logger.info("Successfully initialized YouTube Data API service.")
    except Exception as e:
        logger.error(f"Failed to initialize YouTube Data API: {e}. YouTube link features will be disabled.")
else:
    logger.warning("YOUTUBE_API_KEY not found. YouTube link features will be disabled.")

# Regex to find YouTube links in messages
YOUTUBE_LINK_REGEX = re.compile(
    r'(https?://)?(www\.)?'
    r'(youtube|youtu|youtube-nocookie)\.(com|be)/'
    r'(watch\?v=|embed/|v/|.+\?v=|shorts/)?'
    r'([^&=%\?\s]{11})', re.IGNORECASE)

async def get_youtube_video_details(video_id: str):
    """Fetches video title and channel from YouTube API."""
    if not youtube_service:
        return None
    try:
        # Run the blocking API call in a separate thread to not block the bot
        request = youtube_service.videos().list(part="snippet", id=video_id)
        response = await asyncio.to_thread(request.execute)

        if response and response.get("items"):
            item = response["items"][0]["snippet"]
            return {"title": item.get("title"), "channel_title": item.get("channelTitle")}
        return None
    except HttpError as e:
        logger.error(f"An HTTP error {e.resp.status} occurred while fetching YouTube data: {e.content}")
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
    """Event handler for when the bot logs in."""
    logger.info(f'Logged in as {client.user} (ID: {client.user.id})')
    logger.info('Pekora is ready to cause chaos, peko!')
    await client.change_presence(activity=discord.Game(name="with carrots, peko!"))


@client.event
async def on_message(message: discord.Message):
    """Event handler for when a message is sent."""
    # Ignore messages from the bot itself
    if message.author == client.user:
        return

    # Bot only responds if it's mentioned
    if not client.user.mentioned_in(message):
        return

    channel_id = message.channel.id

    # Get or create a chat session for the current channel to maintain context
    if channel_id not in channel_chats:
        logger.info(f"Creating new chat session for channel {channel_id}")
        # The model automatically remembers the system prompt and history in this session
        channel_chats[channel_id] = model.start_chat()
    
    chat = channel_chats[channel_id]

    # Clean the user's prompt by removing the bot's mention
    user_prompt = re.sub(r'<@!?\d+>', '', message.content).strip()

    # If the message is empty after removing mention, do nothing
    if not user_prompt:
        return

    input_text = user_prompt

    # Append YouTube video details to the prompt if a link is found
    match = YOUTUBE_LINK_REGEX.search(message.content)
    if match and youtube_service:
        video_id = match.group(6)
        if video_id:
            # Show typing indicator while fetching API data
            async with message.channel.typing():
                details = await get_youtube_video_details(video_id)
            if details:
                # Add context for the AI
                input_text += f"\n(Context about the video link in the user's message: The video is titled '{details['title']}' by the channel '{details['channel_title']}')"

    # Show a "typing..." indicator while waiting for the AI response
    async with message.channel.typing():
        try:
            # Send the user's prompt to the Gemini model via the chat session
            response = await chat.send_message_async(input_text)
            # Reply to the user's message without pinging them
            await message.reply(response.text, mention_author=False)

        except Exception as e:
            logger.error(f"Error during AI response generation: {e}")
            await message.reply("Ehh? Pekora's brain-computer went haywire, peko! Try again!", mention_author=False)
            # Optional: Clear the broken chat session so the next message starts fresh
            if channel_id in channel_chats:
                del channel_chats[channel_id]

# --- Main Execution ---
if __name__ == "__main__":
    client.run(DISCORD_TOKEN)