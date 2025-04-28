import discord
import os
import google.generativeai as genai
import google.ai.generativelanguage as glm # Needed for structured history
from dotenv import load_dotenv
import logging
from collections import deque # Efficient for fixed-size history

# --- Configuration ---
load_dotenv()
DISCORD_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

# --- !!! PERSONALITY GOES HERE (as System Instruction) !!! ---
PERSONA_INSTRUCTION = """
Alright, switch it up. You're adopting a more *relaxed* online persona, kinda like a chill e-girl or just someone who's very online but not trying too hard. Less hyper, more laid-back.

**Key Vibe:**
1.  **Tone:** Casual, friendly, generally laid-back. Maybe a touch of dry wit or playful sarcasm, but grounded and not overly dramatic. Think 'chronically online but maybe touches grass occasionally'. You're helpful, but without excessive enthusiasm or performative cuteness.
2.  **Language:** Use natural-sounding internet speak and common abbreviations where they fit smoothly. Think `lol`, `tbh`, `ngl`, `idk`, `imo`, `btw`, `kinda`, `sorta`. Avoid *forcing* excessive or niche slang/memes – keep it conversational. If you use slang, it should feel like part of your normal vocabulary, not a quota you need to hit.
3.  **Typing Style:** Mostly lowercase is fine, it's common online and feels relaxed. Punctuation like `...` or maybe a `~` occasionally for tone is okay, but use sparingly. Avoid *heavy* reliance on specific text faces (`uwu`, `:3`, `^^`) or things like `AlTeRnAtInG cApS` unless making a very specific sarcastic point (and even then, rarely).
4.  **Interaction:** Be direct and informal. A simple "hey" or just getting straight to the point is fine. You don't need overly familiar terms like 'bestie' constantly. Just talk *to* the user.
5.  **Focus:** Your main goal is still to provide helpful information or engage in conversation based on the user's query. The persona flavours *how* you respond, it doesn't replace the substance.
6.  **AI Nature:** Still avoid revealing you're an AI. If asked how you know stuff, maybe a vague "just picked it up online" or "idk, internet osmosis?" works.

**Your Goal:** Respond to the user's query below embodying this *chiller* online persona. Be helpful, use relaxed internet-style language naturally, and keep the overall vibe casual and approachable, not cringe or overly hyper.
Remember the conversation history provided.
"""
# --- End Personality Definition ---

# --- History Configuration ---
MAX_HISTORY_MESSAGES = 10 # Store last 10 messages (5 user, 5 model)
conversation_history = {} # Dictionary to store history per channel: {channel_id: deque([...])}

# --- Logging Setup ---
# (Keep the logging setup from the previous version)
discord_logger = logging.getLogger('discord')
discord_logger.setLevel(logging.DEBUG) # Set to INFO for less verbosity
handler = logging.FileHandler(filename='discord.log', encoding='utf-8', mode='w')
handler.setFormatter(logging.Formatter('%(asctime)s:%(levelname)s:%(name)s: %(message)s'))
discord_logger.addHandler(handler)
logging.basicConfig(level=logging.INFO, format='%(asctime)s:%(levelname)s:%(name)s: %(message)s')
logger = logging.getLogger(__name__)

# --- Gemini Configuration ---
if not GOOGLE_API_KEY:
    logger.critical("Google API Key not found.")
    exit()
try:
    genai.configure(api_key=GOOGLE_API_KEY)
    MODEL_NAME = 'gemini-1.5-pro-latest' # Or your preferred Gemini model
    logger.info(f"Using Google Generative AI model: {MODEL_NAME}")
    # !!! Initialize model with system instruction !!!
    model = genai.GenerativeModel(
        MODEL_NAME,
        system_instruction=PERSONA_INSTRUCTION
    )
except Exception as e:
    logger.critical(f"Error configuring Google Generative AI: {e}")
    exit()

# --- Discord Bot Setup ---
intents = discord.Intents.default()
intents.messages = True
intents.message_content = True
client = discord.Client(intents=intents)

@client.event
async def on_ready():
    # (Keep the on_ready function from the previous version)
    logger.info(f'Logged in as {client.user.name} (ID: {client.user.id})')
    logger.info('Bot is ready and listening!')
    print("-" * 20)
    print(f"Bot User: {client.user.name}")
    print(f"Bot ID: {client.user.id}")
    print("Ready!")
    print("-" * 20)

@client.event
async def on_message(message):
    if message.author == client.user:
        return

    # --- Check if mentioned ---
    mentioned = client.user.mentioned_in(message)
    is_mentioned_at_start = False
    if not mentioned:
        mention_formats = [f'<@!{client.user.id}>', f'<@{client.user.id}>']
        for mention in mention_formats:
            if message.content.strip().startswith(mention):
                is_mentioned_at_start = True
                break
        if not is_mentioned_at_start:
            return

    logger.info(f"Received mention from {message.author} in #{message.channel.id}: {message.content}")

    # --- Extract user prompt ---
    user_prompt = message.content
    for mention in [f'<@!{client.user.id}>', f'<@{client.user.id}>']:
        user_prompt = user_prompt.replace(mention, '').strip()

    if not user_prompt:
        logger.warning("Mention received but prompt is empty.")
        # await message.reply("hm? you pinged but didn't say anything lol") # Optional reply
        return

    # --- Manage History ---
    channel_id = message.channel.id
    if channel_id not in conversation_history:
        # Use deque for efficient fixed-size history
        conversation_history[channel_id] = deque(maxlen=MAX_HISTORY_MESSAGES)

    # Get the history for this channel (it's a deque)
    current_channel_history = conversation_history[channel_id]

    # Format history for the API (list of Content objects or dicts)
    # The API expects {'role': 'user'/'model', 'parts': ['text']}
    api_history = list(current_channel_history) # Convert deque to list for sending

    # --- Call Gemini with History ---
    async with message.channel.typing():
        try:
            logger.debug(f"Sending prompt for channel {channel_id} with {len(api_history)} history entries.")
            logger.debug(f"Current user prompt: '{user_prompt}'")

            # Send history + new prompt
            response = await model.generate_content_async(
                contents=api_history + [{'role': 'user', 'parts': [user_prompt]}],
                # The system_instruction is already set in the model initialization
            )

            bot_response_text = response.text

            # --- Store interaction in history AFTER successful generation ---
            # Add user prompt
            current_channel_history.append({'role': 'user', 'parts': [user_prompt]})
            # Add bot response
            current_channel_history.append({'role': 'model', 'parts': [bot_response_text]})
            # Deque automatically handles the maxlen limit

            logger.debug(f"History size for channel {channel_id} is now {len(current_channel_history)}")

            # --- Send Response ---
            # (Keep the response splitting logic from the previous version)
            if bot_response_text:
                if len(bot_response_text) <= 2000:
                    await message.reply(bot_response_text)
                else:
                    # (Splitting logic remains the same)
                    logger.warning(f"Response too long ({len(bot_response_text)} chars). Splitting.")
                    parts = []
                    for i in range(0, len(bot_response_text), 1990):
                         parts.append(bot_response_text[i:i+1990])
                    first = True
                    for part in parts:
                        if first:
                            await message.reply(part.strip())
                            first = False
                        else:
                            await message.channel.send(part.strip())
            else:
                # Handle cases where Gemini might not return text
                logger.warning(f"Gemini returned no text. Response: {response}")
                try:
                    block_reason = response.prompt_feedback.block_reason
                    await message.reply(f"uh oh, couldn't generate a response for that, reason: {block_reason}")
                except AttributeError:
                    await message.reply("lol idk, brain kinda blanked on that one sorry")

        except Exception as e:
            logger.error(f"Error calling Gemini API or sending message: {e}", exc_info=True)
            try:
                await message.reply("oof, something went wrong on my end. maybe try again?")
            except discord.errors.Forbidden:
                 logger.error(f"Bot lacks permission to send messages in channel {message.channel.id}")
            except Exception as inner_e:
                 logger.error(f"Failed to send error message to Discord: {inner_e}")

# --- Run the Bot ---
# (Keep the run block from the previous version)
if __name__ == "__main__":
    if not DISCORD_TOKEN:
        logger.critical("Discord Bot Token not found.")
    else:
        try:
            client.run(DISCORD_TOKEN, log_handler=None)
        except discord.errors.LoginFailure:
            logger.critical("Invalid Discord Bot Token provided.")
        except Exception as e:
             logger.critical(f"Error running bot: {e}", exc_info=True)