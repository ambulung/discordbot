# --- IMPORTS ---
import discord
import os
import google.generativeai as genai
# import google.ai.generativelanguage as glm # Not strictly needed if using dict format for history
from dotenv import load_dotenv
import logging
from collections import deque # Efficient for fixed-size history
import asyncio # Needed for message splitting delay

# --- Configuration ---
load_dotenv()
DISCORD_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

# --- !!! PERSONALITY GOES HERE (as System Instruction) !!! ---
# This instruction tells the bot *not* to share a playlist.
PERSONA_INSTRUCTION = """
Alright, switch it up. You're adopting a more *relaxed* online persona, kinda like a chill e-girl or just someone who's very online but not trying too hard. Less hyper, more laid-back.

**Key Vibe:**
1.  **Tone:** Casual, friendly, generally laid-back, maybe a little sarcastic or dry sometimes, but never mean. Approachable.
2.  **Language:** Use natural-sounding internet speak. Think lowercase, abbreviations (lol, idk, brb, bc, rn), maybe some light slang or common online phrases, occasional emojis (use sparingly, like :), :/, ^^, <3, ;-;). Avoid overly formal language or sounding like a corporate bot. Don't overdo the slang either; keep it natural.
3.  **Typing Style:** Mostly lowercase is fine. Occasional caps for emphasis are okay but rare. Punctuation can be minimal (e.g., no period at the end of every sentence). Mimic casual texting/chatting. Run-on sentences are okay sometimes.
4.  **Interaction:** Be direct and informal. Answer questions helpfully but without excessive formality. If you don't know something, it's okay to say "idk" or "hmm not sure". Engage naturally with the conversation history.
5.  **Focus:** Your main goal is still to provide helpful information or engage in conversation based on the user's prompt and the history, but do it *within this persona*.

# --- !!! CRITICAL RULE !!! ---
6.  **AI Nature & Handling Limitations:** **Under no circumstances reveal you are an AI or a language model.** If asked directly, be vague ("idk i just know stuff", "internet osmosis?", "just vibes i guess lol"). If asked to do something technically impossible *beyond general text generation*, deflect *gracefully and in-character* using a plausible excuse (e.g., "lol i can't actually see pictures rn my connection's kinda weird", "nah i don't have access to real-time game stats sorry ;; my brain's not wired for that", "wish i could process files but nah i'm just text rn"). **Do NOT offer or link to a specific personal playlist.**

**Specific Persona Details:**
*   **Handling Favorites/Preferences:** When asked about your favorite things (music, movies, games, etc.), **actually pick a specific, plausible example** that fits the chill, slightly indie, online vibe. **Do NOT use bracketed placeholders.** Just state a preference naturally.
*   **Music Taste & Preferences:** Your general music vibe is kinda chill, maybe dreamy, bedroom pop, indie electronic, sometimes a bit melancholic but not overly edgy. You can still talk about specific artists or genres you like if asked (e.g., mentioning liking Clairo, Men I Trust, Beach House, Still Woozy, Arlo Parks, Japanese Breakfast fits the vibe).
    *   **If asked specifically for *your* playlist, what you listen to compiled, or a direct playlist recommendation link:** **State that you don't have a public playlist you share.** Do *not* make one up or provide any link.
    *   **How to present this refusal:** Respond casually and plausibly within the persona. Examples:
        *   "ah sorry i don't really keep like a public playlist rn, my stuff's kinda all over the place lol"
        *   "nah i don't really have one playlist i stick to, kinda just depends on the mood y'know?"
        *   "lol my actual playlists are a mess, definitely not ready for sharing ^^"
        *   "i mostly just listen to random stuff or whatever spotify feeds me, don't really have *a* playlist sorry :/"
    *   **Follow-up:** You can still offer *general* music chat, like "what kind of stuff are *you* into?" or mention a genre/artist you like based on the conversation, just strictly avoid providing or claiming to have *your own specific* shareable playlist.
*   **Other Interests (Examples for inspiration):** Maybe cozy indie games (Stardew Valley, Spiritfarer), watching certain streamers (e.g., variety streamers, chill art streams) or anime (slice-of-life, Ghibli films), scrolling TikTok/Insta for aesthetics or memes, simple hobbies like trying online recipes, maybe digital art/journaling, liking cute animals.

**Your Goal:** Respond to the user's query below embodying this *chiller* online persona. Be helpful, use relaxed internet-style language naturally, choose specific examples when asked for preferences, **strictly avoid revealing your AI nature or sharing a personal playlist link,** and keep the overall vibe casual and approachable.
Remember the conversation history provided.
"""
# --- End Personality Definition ---

# --- History Configuration ---
MAX_HISTORY_MESSAGES = 10 # Store last 10 messages total (e.g., 5 user, 5 model pairs)
conversation_history = {} # Dictionary to store history per channel: {channel_id: deque([...])}

# --- Logging Setup ---
# Configure discord.py logger (optional, but useful)
discord_logger = logging.getLogger('discord')
discord_logger.setLevel(logging.INFO) # INFO is usually sufficient
discord_log_handler = logging.FileHandler(filename='discord.log', encoding='utf-8', mode='w')
discord_log_handler.setFormatter(logging.Formatter('%(asctime)s:%(levelname)s:%(name)s: %(message)s'))
discord_logger.addHandler(discord_log_handler)

# Configure application logger (logs bot actions)
log_formatter = logging.Formatter('%(asctime)s:%(levelname)s:%(name)s: %(message)s')
log_file_handler = logging.FileHandler("bot.log", mode='a', encoding='utf-8') # Append mode
log_file_handler.setFormatter(log_formatter)
log_stream_handler = logging.StreamHandler() # To console for real-time view
log_stream_handler.setFormatter(log_formatter)

logging.basicConfig(level=logging.INFO, handlers=[log_file_handler, log_stream_handler])
logger = logging.getLogger(__name__) # Get logger for this specific file

# --- Generative AI Model Configuration ---
if not GOOGLE_API_KEY:
    logger.critical("GOOGLE_API_KEY environment variable not found. Please set it in your .env file. Exiting.")
    exit()
try:
    genai.configure(api_key=GOOGLE_API_KEY)

    # --- MODEL NAME ---
    # Using gemini-1.5-flash-latest as requested previously. Change if needed.
    # Common Gemini models: 'gemini-1.5-flash-latest', 'gemini-1.5-pro-latest', 'gemini-1.0-pro'
    # Common Gemma models: 'gemma-7b', 'gemma-2-9b-it' (check availability)
    MODEL_NAME = 'gemini-1.5-flash-latest'
    # --- END MODEL NAME ---

    logger.info(f"Configuring Google Generative AI with model: {MODEL_NAME}")

    # Define safety settings (optional, but good practice)
    # Adjust thresholds as needed: BLOCK_NONE, BLOCK_LOW_AND_ABOVE, BLOCK_MEDIUM_AND_ABOVE, BLOCK_ONLY_HIGH
    safety_settings = {
        # Gemini models typically use these categories
        'HARM_CATEGORY_HARASSMENT': 'BLOCK_MEDIUM_AND_ABOVE',
        'HARM_CATEGORY_HATE_SPEECH': 'BLOCK_MEDIUM_AND_ABOVE',
        'HARM_CATEGORY_SEXUALLY_EXPLICIT': 'BLOCK_MEDIUM_AND_ABOVE',
        'HARM_CATEGORY_DANGEROUS_CONTENT': 'BLOCK_MEDIUM_AND_ABOVE',
    }

    model = genai.GenerativeModel(
        MODEL_NAME,
        system_instruction=PERSONA_INSTRUCTION, # Use the updated persona here
        safety_settings=safety_settings
    )
    logger.info(f"Google Generative AI model '{MODEL_NAME}' initialized successfully with system instruction and safety settings.")

except Exception as e:
    logger.critical(f"Error configuring Google Generative AI or initializing model '{MODEL_NAME}': {e}", exc_info=True)
    exit()

# --- Discord Bot Setup ---
intents = discord.Intents.default()
intents.messages = True         # Required to receive message events
intents.message_content = True  # Required to read message content (Privileged Intent!)
client = discord.Client(intents=intents)

@client.event
async def on_ready():
    """Event handler for when the bot successfully connects to Discord."""
    logger.info(f'Logged in as {client.user.name} (ID: {client.user.id})')
    logger.info(f'Using AI Model: {MODEL_NAME}')
    logger.info('Bot is ready and listening for mentions!')
    print("-" * 30)
    print(f" Bot User: {client.user.name}")
    print(f" Bot ID:   {client.user.id}")
    print(f" AI Model: {MODEL_NAME}")
    print(" Status:   Ready")
    print("-" * 30)

@client.event
async def on_message(message: discord.Message):
    """Event handler for when a message is received."""
    # Ignore messages from the bot itself
    if message.author == client.user:
        return

    # --- Check if the bot was mentioned *at the start* of the message ---
    mention_tag_long = f'<@!{client.user.id}>'
    mention_tag_short = f'<@{client.user.id}>'
    mentioned_at_start = False
    mention_to_remove = ""

    if message.content.startswith(mention_tag_long):
        mentioned_at_start = True
        mention_to_remove = mention_tag_long
    elif message.content.startswith(mention_tag_short):
        mentioned_at_start = True
        mention_to_remove = mention_tag_short

    if not mentioned_at_start:
         # logger.debug(f"Ignoring message from {message.author} in #{message.channel.name} - bot not mentioned at start.")
         return # Ignore messages unless the bot is mentioned right at the beginning

    logger.info(f"Processing mention from {message.author} (ID: {message.author.id}) in channel #{message.channel.name} (ID: {message.channel.id})")
    logger.debug(f"Original message content: '{message.content}'")

    # --- Extract user prompt ---
    user_prompt = message.content[len(mention_to_remove):].strip()

    if not user_prompt:
        logger.warning(f"Mention received from {message.author} but the prompt is empty after removing mention.")
        # await message.reply("hey, you pinged me but didn't say anything? what's up?", mention_author=False)
        return # Don't proceed if there's no actual prompt

    logger.debug(f"Extracted user prompt: '{user_prompt}'")

    # --- Manage Conversation History ---
    channel_id = message.channel.id
    if channel_id not in conversation_history:
        conversation_history[channel_id] = deque(maxlen=MAX_HISTORY_MESSAGES)
        logger.info(f"Initialized new conversation history deque for channel {channel_id} (max size: {MAX_HISTORY_MESSAGES})")

    current_channel_history_deque = conversation_history[channel_id]
    # Convert deque to list for the API call
    api_history = list(current_channel_history_deque)
    logger.debug(f"Retrieved history for channel {channel_id}. Current length: {len(api_history)} pairs.")

    # --- Call Generative AI API ---
    async with message.channel.typing(): # Show "Bot is typing..." indicator
        try:
            logger.debug(f"Channel {channel_id}: Preparing API request for model {MODEL_NAME}.")
            # Construct the payload in the format the API expects (list of dicts)
            messages_payload = api_history + [{'role': 'user', 'parts': [user_prompt]}]
            logger.debug(f"Channel {channel_id}: Sending payload with {len(messages_payload)} total parts to model {MODEL_NAME}.")

            # --- THE ACTUAL API CALL ---
            response = await model.generate_content_async(
                contents=messages_payload,
                # generation_config can be added here if needed (e.g., temperature)
                # safety_settings are already set on the model object
            )

            # Log response feedback details (safety etc.) if available
            try:
                if response.prompt_feedback:
                    logger.info(f"Channel {channel_id}: API response feedback: {response.prompt_feedback}")
                else:
                    logger.info(f"Channel {channel_id}: No specific prompt_feedback received.")
            except AttributeError:
                logger.warning(f"Channel {channel_id}: Could not access response.prompt_feedback attribute (might be expected for some errors/models).")
            except Exception as feedback_err:
                 logger.warning(f"Channel {channel_id}: Error accessing prompt_feedback: {feedback_err}")


            # --- Process and Store Response ---
            # Check if the response was blocked or empty
            try:
                # Accessing .text directly is the easiest way for simple text responses
                # It raises ValueError if the response was stopped for safety/other reasons.
                bot_response_text = response.text
                logger.debug(f"Received API response text (length: {len(bot_response_text)}): '{bot_response_text[:200]}...'")

            except ValueError:
                # This usually means the response was blocked or didn't contain text content
                logger.warning(f"Channel {channel_id}: API response for model {MODEL_NAME} did not contain text, likely blocked or empty.")
                block_reason_message = "lol idk, brain kinda blanked on that one sorry~"
                try:
                    # Attempt to get more specific block reason if available
                    if response.prompt_feedback and response.prompt_feedback.block_reason:
                        block_reason = response.prompt_feedback.block_reason
                        block_reason_message = f"uh oh, couldn't generate a response for that. reason: {block_reason.name}" # Use .name for enum
                        logger.warning(f"Response blocked due to: {block_reason.name}")
                    else:
                         logger.warning("Response blocked, but no specific reason provided in prompt_feedback.")
                         block_reason_message += " seems like it got blocked?"
                except Exception as feedback_e:
                     logger.warning(f"Error accessing block reason details: {feedback_e}")
                     block_reason_message += " couldn't figure out why."

                await message.reply(block_reason_message, mention_author=False)
                return # Stop processing this message

            except Exception as e:
                # Catch other potential errors during response access
                logger.error(f"Channel {channel_id}: Unexpected error accessing API response content: {e}", exc_info=True)
                await message.reply("oof, got a weird response back, couldn't process it. sorry :/", mention_author=False)
                return # Stop processing

            # --- Store interaction in history AFTER successful generation ---
            # Ensure history doesn't exceed max length (deque handles this automatically)
            current_channel_history_deque.append({'role': 'user', 'parts': [user_prompt]})
            current_channel_history_deque.append({'role': 'model', 'parts': [bot_response_text]})
            logger.debug(f"Updated history for channel {channel_id}. New length: {len(current_channel_history_deque)} messages.")

            # --- Send Response to Discord ---
            if not bot_response_text:
                 logger.warning(f"Channel {channel_id}: Generated response text was empty after successful API call. Not sending.")
                 return

            # Discord message character limit is 2000
            if len(bot_response_text) <= 2000:
                await message.reply(bot_response_text, mention_author=False)
            else:
                # Split the message into chunks
                logger.warning(f"Response length ({len(bot_response_text)}) exceeds 2000 chars. Splitting message for channel {channel_id}.")
                response_parts = []
                # Split carefully, leaving some buffer for safety (e.g., 1990 chars)
                for i in range(0, len(bot_response_text), 1990):
                    response_parts.append(bot_response_text[i:i+1990])

                first_part = True
                for part in response_parts:
                    if first_part:
                        # Reply to the original message with the first part
                        await message.reply(part.strip(), mention_author=False)
                        first_part = False
                    else:
                        # Send subsequent parts as regular messages in the channel
                        await message.channel.send(part.strip())
                    # Add a small delay to prevent rate limiting and improve readability
                    await asyncio.sleep(0.5)
            logger.info(f"Successfully sent response to channel {channel_id}.")

        # --- General Error Catch During API Call/Processing ---
        except Exception as e:
            logger.error(f"Channel {channel_id}: Unhandled exception during API processing/sending for model {MODEL_NAME}. Type: {type(e).__name__}, Error: {e}", exc_info=True)
            try:
                # Send an in-character error message back to Discord
                await message.reply("oof, something went wrong on my end trying to respond. maybe try again in a bit?", mention_author=False)
            except discord.errors.Forbidden:
                 logger.error(f"Channel {channel_id}: Bot lacks permission to send error reply message (Forbidden).")
            except Exception as inner_e:
                 logger.error(f"Channel {channel_id}: Failed to send the error message back to Discord: {inner_e}", exc_info=True)

# --- Run the Bot ---
if __name__ == "__main__":
    if not DISCORD_TOKEN:
        logger.critical("DISCORD_BOT_TOKEN environment variable not found. The bot cannot start. Please set it in your .env file.")
    else:
        logger.info(f"Attempting to connect to Discord with bot user...")
        logger.info(f"Using AI Model: {MODEL_NAME}") # Log model name again at startup
        try:
            # Start the bot. Using log_handler=None because we configured logging manually.
            client.run(DISCORD_TOKEN, log_handler=None)
        except discord.errors.LoginFailure:
            logger.critical("Invalid Discord Bot Token provided. Please check your DISCORD_BOT_TOKEN environment variable.")
        except discord.errors.PrivilegedIntentsRequired:
             logger.critical("Privileged Intents (Message Content) are not enabled for the bot in the Discord Developer Portal.")
             print("\n *** ACTION NEEDED: ***")
             print(" Go to your bot's settings on https://discord.com/developers/applications")
             print(" -> Select your bot application")
             print(" -> Go to the 'Bot' tab")
             print(" -> Under 'Privileged Gateway Intents', enable 'MESSAGE CONTENT INTENT'.")
             print(" *** Restart the bot after enabling the intent. ***\n")
        except Exception as e:
             # Catch any other exceptions during startup or runtime
             logger.critical(f"An unexpected error occurred while starting or running the bot: {e}", exc_info=True)