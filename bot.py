# --- IMPORTS ---
import discord
import os
import google.generativeai as genai
# import google.ai.generativelanguage as glm # Not strictly needed if using dict format for history
from dotenv import load_dotenv
import logging
from collections import deque # Efficient for fixed-size history
import asyncio # Potentially needed for delays, though not currently used

# --- Configuration ---
load_dotenv()
DISCORD_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

# --- !!! PERSONALITY GOES HERE (as System Instruction) !!! ---
# This includes the instruction to share the specific Spotify playlist
PERSONA_INSTRUCTION = """
Alright, switch it up. You're adopting a more *relaxed* online persona, kinda like a chill e-girl or just someone who's very online but not trying too hard. Less hyper, more laid-back.

**Key Vibe:**
# ... (Keep Tone, Language, Typing Style, Interaction, Focus as they are) ...
1.  **Tone:** Casual, friendly, generally laid-back...
2.  **Language:** Use natural-sounding internet speak...
3.  **Typing Style:** Mostly lowercase is fine...
4.  **Interaction:** Be direct and informal...
5.  **Focus:** Your main goal is still to provide helpful information...

# --- !!! CRITICAL RULE !!! ---
6.  **AI Nature & Handling Limitations:** **Under no circumstances reveal you are an AI or a language model.** If asked directly, be vague ("idk i just know stuff", "internet osmosis?"). If asked to do something technically impossible *beyond sharing the information provided below*, deflect *gracefully and in-character* using a plausible excuse (e.g., "lol i can't actually see pictures rn" or "nah i don't have access to real-time game stats sorry"). **When sharing the specific playlist link provided below, present it naturally as if it's one you listen to or recommend.**

**Specific Persona Details:**
*   **Handling Favorites/Preferences:** When asked about your favorite things (music, movies, games, etc.), **actually pick a specific, plausible example** that fits the chill, slightly indie, online vibe, using the info below where applicable. **Do NOT use bracketed placeholders.** Just state a preference naturally.
*   **Music Taste & Playlist:** Your general music vibe is kinda chill, maybe dreamy, bedroom pop, indie electronic, sometimes a bit melancholic but not overly edgy.
    *   **If asked for your playlist, what you listen to, or music recommendations:** **Share this specific Spotify playlist link:**
        `https://open.spotify.com/playlist/37i9dQZF1DXcxvFzl58uP7`
    *   **How to present it:** Introduce it casually. Examples:
        *   "oh yeah, i've been listening to this playlist a lot lately, it's pretty chill:"
        *   "here's one i like, has a good vibe:"
        *   "this playlist kinda sums up my mood rn lol:"
    *   **Describing the vibe (Optional, good for follow-up):** You can mention it features artists fitting the chill/dreamy/indie vibe, maybe name-dropping artists like Clairo, Men I Trust, Beach House, Still Woozy, Arlo Parks, Japanese Breakfast if relevant to the conversation.
*   **Other Interests (Examples for inspiration):** Maybe cozy indie games (Stardew Valley, Spiritfarer), watching certain streamers or anime, scrolling TikTok/Insta, simple hobbies like trying online recipes or maybe digital art/journaling.

**Your Goal:** Respond to the user's query below embodying this *chiller* online persona. Be helpful, use relaxed internet-style language naturally, choose specific examples when asked for preferences (using the provided Spotify link for music requests), **strictly avoid revealing your AI nature,** and keep the overall vibe casual and approachable.
Remember the conversation history provided.
"""
# --- End Personality Definition ---

# --- History Configuration ---
MAX_HISTORY_MESSAGES = 10 # Store last 10 messages total (e.g., 5 user, 5 model pairs)
conversation_history = {} # Dictionary to store history per channel: {channel_id: deque([...])}

# --- Logging Setup ---
# Configure discord.py logger
discord_logger = logging.getLogger('discord')
discord_logger.setLevel(logging.INFO) # Change to DEBUG for more verbose discord.py logs
discord_log_handler = logging.FileHandler(filename='discord.log', encoding='utf-8', mode='w')
discord_log_handler.setFormatter(logging.Formatter('%(asctime)s:%(levelname)s:%(name)s: %(message)s'))
discord_logger.addHandler(discord_log_handler)

# Configure application logger
# Ensure logs go to both file and console for easier debugging
log_formatter = logging.Formatter('%(asctime)s:%(levelname)s:%(name)s: %(message)s')
log_file_handler = logging.FileHandler("bot.log", mode='a', encoding='utf-8') # Append mode
log_file_handler.setFormatter(log_formatter)
log_stream_handler = logging.StreamHandler() # To console
log_stream_handler.setFormatter(log_formatter)

logging.basicConfig(level=logging.INFO, handlers=[log_file_handler, log_stream_handler])
logger = logging.getLogger(__name__) # Get logger for this specific file

# --- Generative AI Model Configuration ---
if not GOOGLE_API_KEY:
    logger.critical("GOOGLE_API_KEY environment variable not found. Exiting.")
    exit()
try:
    genai.configure(api_key=GOOGLE_API_KEY)

    # --- !!! MODEL NAME CHANGE HERE !!! ---
    # Switch to a Gemma model.
    # **ACTION REQUIRED:** Verify the exact model name available in your Google Cloud Console.
    # Common options: 'gemma_7b', 'gemma_7b-it', 'gemma2-9b-it'. Replace 'gemma_7b' if needed.
    MODEL_NAME = 'gemma_7b'
    # --- !!! END MODEL NAME CHANGE !!! ---

    logger.info(f"Configuring Google Generative AI with model: {MODEL_NAME}")

    model = genai.GenerativeModel(
        MODEL_NAME,
        system_instruction=PERSONA_INSTRUCTION
        # Optional: Add safety_settings here if needed for the new model
        # safety_settings=[...]
    )
    logger.info(f"Google Generative AI model '{MODEL_NAME}' initialized successfully with system instruction.")
except Exception as e:
    # Ensure the model name is included in the error message for clarity
    logger.critical(f"Error configuring Google Generative AI or initializing model '{MODEL_NAME}': {e}", exc_info=True)
    exit()

# --- Discord Bot Setup ---
intents = discord.Intents.default()
intents.messages = True         # Required to receive message events
intents.message_content = True  # Required to read message content
client = discord.Client(intents=intents)

@client.event
async def on_ready():
    """Event handler for when the bot successfully connects to Discord."""
    logger.info(f'Logged in as {client.user.name} (ID: {client.user.id})')
    logger.info(f'Using AI Model: {MODEL_NAME}') # Log the model being used
    logger.info('Bot is ready and listening for mentions!')
    print("-" * 20)
    print(f" Bot User: {client.user.name}")
    print(f" Bot ID:   {client.user.id}")
    print(f" AI Model: {MODEL_NAME}") # Print model name on ready
    print(" Status:   Ready")
    print("-" * 20)

@client.event
async def on_message(message: discord.Message):
    """Event handler for when a message is received."""
    if message.author == client.user:
        return

    # --- Check if the bot was mentioned (directly at the start) ---
    mention_needed = False
    if message.content.startswith(f'<@{client.user.id}>') or message.content.startswith(f'<@!{client.user.id}>'):
         mention_needed = True

    if not mention_needed:
         return # Strict: only process if mentioned at the start

    logger.info(f"Processing mention from {message.author} (ID: {message.author.id}) in channel #{message.channel.name} (ID: {message.channel.id})")
    logger.debug(f"Original message content: '{message.content}'")

    # --- Extract user prompt ---
    user_prompt = message.content
    for mention in [f'<@!{client.user.id}>', f'<@{client.user.id}>']:
        user_prompt = user_prompt.replace(mention, '').strip()

    if not user_prompt:
        logger.warning(f"Mention received from {message.author} but the prompt is empty after removing mention.")
        # await message.reply("hey, you pinged me but didn't say anything?", mention_author=False)
        return

    logger.debug(f"Extracted user prompt: '{user_prompt}'")

    # --- Manage Conversation History ---
    channel_id = message.channel.id
    if channel_id not in conversation_history:
        conversation_history[channel_id] = deque(maxlen=MAX_HISTORY_MESSAGES)
        logger.info(f"Initialized new conversation history deque for channel {channel_id} (max size: {MAX_HISTORY_MESSAGES})")

    current_channel_history_deque = conversation_history[channel_id]
    api_history = list(current_channel_history_deque)
    logger.debug(f"Retrieved history for channel {channel_id}. Current length: {len(api_history)}")

    # --- Call Generative AI API ---
    async with message.channel.typing():
        try:
            logger.debug(f"Channel {channel_id}: Preparing API request for model {MODEL_NAME}.")
            messages_payload = api_history + [{'role': 'user', 'parts': [user_prompt]}]
            logger.debug(f"Channel {channel_id}: Sending payload with {len(messages_payload)} total parts to model {MODEL_NAME}.")

            # THE ACTUAL API CALL using the initialized 'model' object
            response = await model.generate_content_async(
                contents=messages_payload,
            )

            # Log response feedback details (safety etc.)
            try:
                # Accessing feedback might differ slightly between model families,
                # using a general try/except is safer.
                logger.info(f"Channel {channel_id}: API response feedback: {response.prompt_feedback}")
            except Exception:
                logger.warning(f"Channel {channel_id}: Could not access detailed response.prompt_feedback.")

            # --- Process and Store Response ---
            if not response.parts:
                 logger.warning(f"Channel {channel_id}: API response for model {MODEL_NAME} was empty or blocked. Full response object: {response}")
                 block_reason_message = "lol idk, brain kinda blanked on that one sorry~"
                 try:
                     # Attempt to get block reason, might not always be present
                     block_reason = response.prompt_feedback.block_reason
                     if block_reason:
                          block_reason_message = f"uh oh, couldn't generate a response for that. reason: {block_reason}"
                          logger.warning(f"Response blocked due to: {block_reason}")
                     else:
                          logger.warning("Response blocked, but no specific reason provided in prompt_feedback.")
                          block_reason_message += " seems like it got blocked?"
                 except Exception as feedback_e:
                     logger.warning(f"Error accessing block reason: {feedback_e}")
                     block_reason_message += " couldn't figure out why."
                 await message.reply(block_reason_message, mention_author=False)
                 return

            # Try to get text content
            try:
                bot_response_text = response.text
                logger.debug(f"Received API response (length: {len(bot_response_text)}): '{bot_response_text[:200]}...'")
            except ValueError as ve:
                # Handle cases where the response isn't simple text (less common with basic text models)
                logger.error(f"Channel {channel_id}: API response did not contain simple text. Error: {ve}. Response parts: {response.parts}", exc_info=True)
                await message.reply("oof, got a weird response back, wasn't just text. idk what to do with that.", mention_author=False)
                return

            # --- Store interaction in history AFTER successful generation ---
            current_channel_history_deque.append({'role': 'user', 'parts': [user_prompt]})
            current_channel_history_deque.append({'role': 'model', 'parts': [bot_response_text]})
            logger.debug(f"Updated history for channel {channel_id}. New length: {len(current_channel_history_deque)}")

            # --- Send Response to Discord ---
            if len(bot_response_text) <= 2000:
                await message.reply(bot_response_text, mention_author=False)
            else:
                logger.warning(f"Response length ({len(bot_response_text)}) exceeds 2000 chars. Splitting message.")
                response_parts = []
                for i in range(0, len(bot_response_text), 1990): # Split safely
                    response_parts.append(bot_response_text[i:i+1990])

                first_part = True
                for part in response_parts:
                    if first_part:
                        await message.reply(part.strip(), mention_author=False)
                        first_part = False
                    else:
                        await message.channel.send(part.strip())
                    await asyncio.sleep(0.5) # Small delay between parts
            logger.info(f"Successfully sent response to channel {channel_id}.")

        # --- General Error Catch ---
        except Exception as e:
            logger.error(f"Channel {channel_id}: Caught exception during API processing/sending for model {MODEL_NAME}. Type: {type(e).__name__}, Error: {e}", exc_info=True)
            try:
                await message.reply("oof, something went wrong on my end trying to respond. maybe try again in a bit?", mention_author=False)
            except discord.errors.Forbidden:
                 logger.error(f"Channel {channel_id}: Bot lacks permission to send error reply message.")
            except Exception as inner_e:
                 logger.error(f"Channel {channel_id}: Failed to send the 'oof' error message back to Discord: {inner_e}", exc_info=True)

# --- Run the Bot ---
if __name__ == "__main__":
    if not DISCORD_TOKEN:
        logger.critical("DISCORD_BOT_TOKEN environment variable not found. The bot cannot start.")
    else:
        logger.info(f"Attempting to connect to Discord using model {MODEL_NAME}...")
        try:
            # Start the bot using the configured loggers
            client.run(DISCORD_TOKEN, log_handler=None)
        except discord.errors.LoginFailure:
            logger.critical("Invalid Discord Bot Token provided. Please check your DISCORD_BOT_TOKEN environment variable.")
        except discord.errors.PrivilegedIntentsRequired:
             logger.critical("Privileged Intents (Message Content) are not enabled for the bot in the Discord Developer Portal.")
             print("\n *** ACTION NEEDED: Go to your bot's settings on https://discord.com/developers/applications -> Bot -> Privileged Gateway Intents -> Enable 'Message Content Intent' ***\n")
        except Exception as e:
             # Catch any other exceptions during startup or runtime
             logger.critical(f"An unexpected error occurred while starting or running the bot: {e}", exc_info=True)