import discord
import os
import google.generativeai as genai
# import google.ai.generativelanguage as glm # Not strictly needed if using dict format for history
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
# Dictionary to store history per channel: {channel_id: deque([...])}
# Each item in the deque will be a dict: {'role': 'user'/'model', 'parts': ['text']}
conversation_history = {}

# --- Logging Setup ---
# Configure discord.py logger
discord_logger = logging.getLogger('discord')
discord_logger.setLevel(logging.INFO) # Change to DEBUG for more verbose discord.py logs
discord_log_handler = logging.FileHandler(filename='discord.log', encoding='utf-8', mode='w')
discord_log_handler.setFormatter(logging.Formatter('%(asctime)s:%(levelname)s:%(name)s: %(message)s'))
discord_logger.addHandler(discord_log_handler)

# Configure application logger
logging.basicConfig(level=logging.INFO, format='%(asctime)s:%(levelname)s:%(name)s: %(message)s',
                    handlers=[logging.FileHandler("bot.log", mode='a'), logging.StreamHandler()])
logger = logging.getLogger(__name__)

# --- Gemini Configuration ---
if not GOOGLE_API_KEY:
    logger.critical("GOOGLE_API_KEY environment variable not found. Exiting.")
    exit()
try:
    genai.configure(api_key=GOOGLE_API_KEY)
    MODEL_NAME = 'gemini-1.5-pro-latest' # Or your preferred Gemini model
    logger.info(f"Configuring Google Generative AI with model: {MODEL_NAME}")

    # Initialize the model with the system instruction for the persona
    # This instruction will be implicitly used for all generate_content calls on this model object
    model = genai.GenerativeModel(
        MODEL_NAME,
        system_instruction=PERSONA_INSTRUCTION
    )
    logger.info("Google Generative AI model initialized successfully with system instruction.")
except Exception as e:
    logger.critical(f"Error configuring Google Generative AI or initializing model: {e}", exc_info=True)
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
    logger.info('Bot is ready and listening for mentions!')
    print("-" * 20)
    print(f" Bot User: {client.user.name}")
    print(f" Bot ID:   {client.user.id}")
    print(" Status:   Ready")
    print("-" * 20)

@client.event
async def on_message(message: discord.Message):
    """Event handler for when a message is received."""
    # Ignore messages sent by the bot itself
    if message.author == client.user:
        return

    # --- Check if the bot was mentioned ---
    mentioned = client.user.mentioned_in(message)
    is_direct_mention_at_start = False

    # Check if the message *starts* with a mention (e.g., "@Bot hello")
    # discord.py's mentioned_in checks anywhere in the message
    if not mentioned:
        # Check for both mention formats (<@USER_ID> and <@!USER_ID>)
        mention_formats = [f'<@{client.user.id}>', f'<@!{client.user.id}>']
        for mention in mention_formats:
            # Use startswith after stripping leading whitespace
            if message.content.strip().startswith(mention):
                is_direct_mention_at_start = True
                break
        # If not mentioned anywhere AND not starting with a direct mention, ignore
        if not is_direct_mention_at_start:
            return
    elif not message.content.strip().startswith((f'<@{client.user.id}>', f'<@!{client.user.id}>')):
        # It was mentioned, but not at the very beginning (e.g., "hello @Bot how are you")
        # You might want to ignore these depending on desired behavior. For now, we process them.
        # logger.debug(f"Bot mentioned, but not at the start of the message in C:{message.channel.id}")
        pass # Continue processing mentions anywhere in the message

    logger.info(f"Processing mention from {message.author} (ID: {message.author.id}) in channel #{message.channel.name} (ID: {message.channel.id})")
    logger.debug(f"Original message content: '{message.content}'")

    # --- Extract user prompt ---
    user_prompt = message.content
    # Remove all occurrences of the bot's mention
    for mention in [f'<@!{client.user.id}>', f'<@{client.user.id}>']:
        user_prompt = user_prompt.replace(mention, '').strip()

    # Check if the prompt is empty after removing the mention
    if not user_prompt:
        logger.warning(f"Mention received from {message.author} but the prompt is empty after removing mention.")
        # Optional: Send a reply if pinged with no text
        # await message.reply("hey, you pinged me but didn't say anything?", mention_author=False)
        return

    logger.debug(f"Extracted user prompt: '{user_prompt}'")

    # --- Manage Conversation History ---
    channel_id = message.channel.id
    if channel_id not in conversation_history:
        # Use deque for efficient fixed-size history management (FIFO)
        conversation_history[channel_id] = deque(maxlen=MAX_HISTORY_MESSAGES)
        logger.info(f"Initialized new conversation history deque for channel {channel_id} (max size: {MAX_HISTORY_MESSAGES})")

    # Get the history deque for this channel
    current_channel_history_deque = conversation_history[channel_id]

    # Format history for the API (needs to be a list of dicts)
    # Convert the deque to a list for sending to the API
    api_history = list(current_channel_history_deque)
    logger.debug(f"Retrieved history for channel {channel_id}. Current length: {len(api_history)}")

    # --- Call Gemini API ---
    async with message.channel.typing(): # Show "Bot is typing..." indicator
        try:
            logger.debug(f"Sending request to Gemini for channel {channel_id}. History length: {len(api_history)}. Prompt: '{user_prompt}'")

            # Construct the messages payload for the API
            # The history list already contains dicts in the correct format
            # Add the current user message to the end
            messages_payload = api_history + [{'role': 'user', 'parts': [user_prompt]}]

            # Generate content using the model (which has the system instruction pre-configured)
            response = await model.generate_content_async(
                contents=messages_payload,
                # safety_settings=... # Optional: configure safety settings if needed
                # generation_config=... # Optional: configure temperature, top_p, etc.
            )

            # --- Process and Store Response ---
            # Check if the response was blocked or has no text
            if not response.parts:
                 logger.warning(f"Gemini response was empty or blocked. Full response object: {response}")
                 try:
                     # Attempt to get the block reason if available
                     block_reason = response.prompt_feedback.block_reason
                     block_reason_message = f"uh oh, couldn't generate a response for that. reason: {block_reason}"
                     logger.warning(f"Response blocked due to: {block_reason}")
                 except Exception: # Catch potential attribute errors if prompt_feedback isn't as expected
                     block_reason_message = "lol idk, brain kinda blanked on that one sorry~ seems like it got blocked?"
                     logger.warning("Response blocked, but couldn't determine specific reason.")
                 await message.reply(block_reason_message, mention_author=False)
                 return # Stop processing this message

            bot_response_text = response.text
            logger.debug(f"Received Gemini response (length: {len(bot_response_text)}): '{bot_response_text[:200]}...'") # Log beginning of response

            # --- Store interaction in history AFTER successful generation ---
            # Append the user's prompt message to the deque
            current_channel_history_deque.append({'role': 'user', 'parts': [user_prompt]})
            # Append the model's response message to the deque
            current_channel_history_deque.append({'role': 'model', 'parts': [bot_response_text]})
            # The deque automatically discards the oldest item if maxlen is exceeded

            logger.debug(f"Updated history for channel {channel_id}. New length: {len(current_channel_history_deque)}")

            # --- Send Response to Discord ---
            # Split the response if it's too long for a single Discord message
            if len(bot_response_text) <= 2000:
                await message.reply(bot_response_text, mention_author=False) # Use reply for context, don't ping user
            else:
                logger.warning(f"Response length ({len(bot_response_text)}) exceeds 2000 chars. Splitting message.")
                response_parts = []
                # Split into chunks (leaving some buffer room for Discord limits)
                for i in range(0, len(bot_response_text), 1990):
                    response_parts.append(bot_response_text[i:i+1990])

                first_part = True
                for part in response_parts:
                    if first_part:
                        await message.reply(part.strip(), mention_author=False)
                        first_part = False
                    else:
                        # Send subsequent parts as regular messages in the channel
                        await message.channel.send(part.strip())
                    # Consider adding a small delay between parts if needed, though usually not necessary
                    # await asyncio.sleep(0.5)
            logger.info(f"Successfully sent response to channel {channel_id}.")

        except Exception as e:
            logger.error(f"An error occurred during Gemini API call or Discord message sending: {e}", exc_info=True)
            try:
                # Send a user-friendly error message (fitting the persona)
                await message.reply("oof, something went wrong on my end trying to respond. maybe try again in a bit?", mention_author=False)
            except discord.errors.Forbidden:
                 logger.error(f"Bot lacks permission to send messages in channel {message.channel.id} (ID: {message.channel.id})")
            except Exception as inner_e:
                 logger.error(f"Failed even to send the error message back to Discord: {inner_e}", exc_info=True)

# --- Run the Bot ---
if __name__ == "__main__":
    if not DISCORD_TOKEN:
        logger.critical("DISCORD_BOT_TOKEN environment variable not found. The bot cannot start.")
    else:
        logger.info("Attempting to connect to Discord...")
        try:
            # Start the bot. log_handler=None prevents discord.py from setting up its own root logger handler,
            # allowing our specific discord logger setup to work without conflict.
            client.run(DISCORD_TOKEN, log_handler=None)
        except discord.errors.LoginFailure:
            logger.critical("Invalid Discord Bot Token provided. Please check your DISCORD_BOT_TOKEN environment variable.")
        except Exception as e:
             logger.critical(f"An unexpected error occurred while running the bot: {e}", exc_info=True)