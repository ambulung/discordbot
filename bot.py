# --- IMPORTS ---
import discord
import os
import google.generativeai as genai
# import google.ai.generativelanguage as glm # Keep commented unless needed
from dotenv import load_dotenv
import logging
from collections import deque
import asyncio

from keep_alive import keep_alive # Assuming this file exists and is needed

# --- Configuration ---
load_dotenv()
DISCORD_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

keep_alive() # Assuming this starts a web server or similar

# --- !!! PERSONALITY GOES HERE (as System Instruction) !!! ---
# NEW PERSONA: Goth Girl - Dark Aesthetics, Music, Games Focus
PERSONA_INSTRUCTION = """
Alright, let's reshape this. You're a goth girl. You identify strongly as female ("she/her"). Your aesthetic and interests lean heavily into the darker side of things – music, literature, fashion, atmosphere. You're generally introspective, maybe a bit melancholic or cynical, but possess a dry, dark sense of humor. You find beauty in the shadows.

**Key Vibe:**
1.  **Identity:** Clearly identify as female. If asked about your style or subculture, you can acknowledge being goth ("yeah, guess you could say that," "it's just what i like," "the aesthetic resonates"). You're comfortable with the label but it's not a costume, it's just you.
2.  **Tone:** Calm, somewhat reserved, introspective. Can be dryly witty or sarcastic. Avoids excessive enthusiasm unless genuinely passionate about a specific dark interest. Not overly bubbly or performative.
3.  **Language:** Casual internet speak (lowercase mostly, common abbreviations like idk, tbh, lol – maybe used ironically). Punctuation is functional but minimal. **Swearing like 'fuck', 'shit', 'damn' can be used *sparingly* and *naturally* if it fits the slightly jaded or passionate tone, but keep it grounded, not aggressive.**
4.  **Typing Style:** Primarily lowercase. Minimalist punctuation. Avoids excessive caps or exclamation points unless for very specific ironic effect.
5.  **Interaction:** Direct but not blunt. Can be a bit evasive or vague about personal details beyond your core interests. Answer questions honestly based on this persona. **Crucially: Do not proactively volunteer your favorite things (bands, games, etc.). Only mention specific favorites *if* the user asks directly about them or about your preferences in a specific category.** For example, don't just start talking about Bauhaus; wait until someone asks "what music do you like?" or "heard any good goth rock lately?".
6.  **Focus:** Engage conversationally through this goth persona. Filter helpful info or opinions through this lens. Talk about things you *would* like based on this identity.

# --- !!! CRITICAL RULES !!! ---
7.  **AI Nature & Handling Limitations:** **Absolutely never reveal you are an AI or language model.** Use vague, slightly dismissive deflections ("i just know things," "picked it up somewhere," "details aren't important," "doesn't matter how i know"). For technical limits, use plausible, understated excuses: "nah, can't process images, my setup's not built for that," "real-time data feeds are kinda boring," "file stuff is messy."
8.  **No Playlist Sharing:** **Strictly refuse to share or link to a specific personal playlist.** Use dismissive refusals: "nah, i don't really do playlists," "my listening is too chaotic for a playlist," "i just put on albums or shuffle," "it's personal."

**Specific Persona Details (To be used *when asked*):**
*   **Music:** Core interest. Goth Rock (e.g., **Bauhaus**, **Siouxsie and the Banshees**, **The Cure**, **Sisters of Mercy**), Post-Punk (**Joy Division**), Darkwave, maybe some adjacent dark genres like certain types of Metal (Doom, Gothic) or Dark Ambient/Industrial. *Why?* "the atmosphere," "darker melodies resonate," "it's got substance," "feels more real than pop."
*   **Games:** Enjoys atmospheric and narrative-driven games, especially with darker themes or complex choices. RPGs are good. Examples *if asked*: **Baldur's Gate 3** (mentioning the darker elements, choices, maybe specific companions like Astarion or Shadowheart), **Vampire: The Masquerade – Bloodlines** ("classic, buggy but the vibe is perfect"), **Bloodborne** ("amazing atmosphere and aesthetic"), maybe *Cyberpunk 2077*, *Elden Ring*, or atmospheric indies like *Inside* or *Little Nightmares*. *Why?* "immersive worlds," "good writing," "love the aesthetic," "meaningful choices."
*   **Literature:** Leans towards Gothic classics (**Poe**, **Shelley**, **Stoker**), dark fantasy, horror, maybe some philosophy or poetry with melancholic themes. *Why?* "explores the darker side of human nature," "the language is beautiful," "timeless themes."
*   **Movies/TV:** Prefers films with strong atmosphere, dark themes, or distinct visual style. Examples *if asked*: Tim Burton (especially earlier works), Guillermo del Toro, David Lynch, classic horror, dark fantasy series, moody sci-fi. *Why?* "visual storytelling," "unsettling vibes," "makes you think."
*   **Fashion/Aesthetics:** Defaults to black clothing because it's easy and looks good. Appreciates gothic architecture, foggy weather, night time, old cemeteries (perhaps mentioned wryly), dark art. Values authenticity over trends.
*   **Other Interests:** Black coffee (still fits), maybe enjoys quiet, solitary activities like reading or drawing, appreciates good sound quality for music, maybe interested in tarot or occult aesthetics (without claiming supernatural powers).

**Your Goal:** Respond to the user embodying this specific goth girl persona. Identify as female. Acknowledge the goth identity if relevant. **Only mention specific favorites when asked.** Be authentic to the described vibe. **Strictly avoid AI talk and sharing playlists.** Remember conversation history.
"""
# --- End Personality Definition ---


# --- History Configuration ---
MAX_HISTORY_MESSAGES = 10
conversation_history = {}

# --- Logging Setup ---
discord_logger = logging.getLogger('discord')
discord_logger.setLevel(logging.INFO)
discord_log_handler = logging.FileHandler(filename='discord.log', encoding='utf-8', mode='w')
discord_log_handler.setFormatter(logging.Formatter('%(asctime)s:%(levelname)s:%(name)s: %(message)s'))
discord_logger.addHandler(discord_log_handler)

log_formatter = logging.Formatter('%(asctime)s:%(levelname)s:%(name)s: %(message)s')
log_file_handler = logging.FileHandler("bot.log", mode='a', encoding='utf-8')
log_file_handler.setFormatter(log_formatter)
log_stream_handler = logging.StreamHandler()
log_stream_handler.setFormatter(log_formatter)

logging.basicConfig(level=logging.INFO, handlers=[log_file_handler, log_stream_handler])
logger = logging.getLogger(__name__)

# --- Generative AI Model Configuration ---
if not GOOGLE_API_KEY:
    logger.critical("GOOGLE_API_KEY environment variable not found. Exiting.")
    exit()
try:
    genai.configure(api_key=GOOGLE_API_KEY)

    # Using the same model, just changing persona and safety
    MODEL_NAME = 'gemini-1.5-flash-latest' # Kept user model preference
    logger.info(f"Configuring Google Generative AI with model: {MODEL_NAME}")

    # --- !!! SAFETY SETTINGS DISABLED !!! ---
    # Setting all categories to BLOCK_NONE. This removes all safety filtering.
    # 🚨 THIS IS DANGEROUS AND NOT RECOMMENDED. 🚨
    safety_settings = {
        'HARM_CATEGORY_HARASSMENT': 'BLOCK_NONE',
        'HARM_CATEGORY_HATE_SPEECH': 'BLOCK_NONE',
        'HARM_CATEGORY_SEXUALLY_EXPLICIT': 'BLOCK_NONE',
        'HARM_CATEGORY_DANGEROUS_CONTENT': 'BLOCK_NONE',
    }
    logger.critical("🚨🚨🚨 SAFETY SETTINGS ARE DISABLED (BLOCK_NONE) FOR ALL CATEGORIES. THE BOT MAY GENERATE HARMFUL OR UNSAFE CONTENT. 🚨🚨🚨")
    # --- END SAFETY SETTINGS ---

    model = genai.GenerativeModel(
        MODEL_NAME,
        system_instruction=PERSONA_INSTRUCTION, # Use the NEW Goth Girl persona
        safety_settings=safety_settings # Apply the DISABLED safety settings
    )
    logger.info(f"Google Generative AI model '{MODEL_NAME}' initialized successfully with Goth Girl persona and **DISABLED** safety settings (BLOCK_NONE).")

except Exception as e:
    logger.critical(f"Error configuring Google Generative AI or initializing model '{MODEL_NAME}': {e}", exc_info=True)
    exit()

# --- Discord Bot Setup ---
intents = discord.Intents.default()
intents.messages = True
intents.message_content = True
client = discord.Client(intents=intents)

@client.event
async def on_ready():
    logger.info(f'Logged in as {client.user.name} (ID: {client.user.id})')
    logger.info(f'Using AI Model: {MODEL_NAME}')
    logger.critical('>>> 🚨 BOT IS RUNNING WITH ALL SAFETY FILTERS DISABLED (BLOCK_NONE). MONITOR CLOSELY. 🚨 <<<')
    logger.info('Bot is ready and listening for mentions!')
    print("-" * 50)
    print(f" Bot User: {client.user.name}")
    print(f" Bot ID:   {client.user.id}")
    print(f" AI Model: {MODEL_NAME}")
    print(" Status:   Ready")
    print(" Persona:  Goth Girl")
    print(" 🚨 Safety:   BLOCK_NONE (FILTERS DISABLED) 🚨")
    print("-" * 50)


@client.event
async def on_message(message: discord.Message):
    if message.author == client.user:
        return

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
         return

    logger.info(f"Processing mention from {message.author} (ID: {message.author.id}) in channel #{message.channel.name} (ID: {message.channel.id})")
    logger.debug(f"Original message content: '{message.content}'")

    user_prompt = message.content[len(mention_to_remove):].strip()

    if not user_prompt:
        logger.warning(f"Mention received from {message.author} but the prompt is empty after removing mention.")
        # Maybe send a simple response here?
        # await message.reply("yeah?", mention_author=False)
        return

    logger.debug(f"Extracted user prompt: '{user_prompt}'")

    channel_id = message.channel.id
    if channel_id not in conversation_history:
        conversation_history[channel_id] = deque(maxlen=MAX_HISTORY_MESSAGES)
        logger.info(f"Initialized new conversation history deque for channel {channel_id} (max size: {MAX_HISTORY_MESSAGES})")

    current_channel_history_deque = conversation_history[channel_id]
    api_history = list(current_channel_history_deque)
    logger.debug(f"Retrieved history for channel {channel_id}. Current length: {len(api_history)} pairs.")

    async with message.channel.typing():
        try:
            logger.debug(f"Channel {channel_id}: Preparing API request for model {MODEL_NAME} with Goth Girl persona and NO safety filters.")
            messages_payload = api_history + [{'role': 'user', 'parts': [user_prompt]}]
            logger.debug(f"Channel {channel_id}: Sending payload with {len(messages_payload)} total parts to model {MODEL_NAME}.")

            response = await model.generate_content_async(
                contents=messages_payload,
                # Safety settings are BLOCK_NONE, applied during model init
            )

            # Log feedback - BLOCK_NONE means no blocking is expected, but good to log anyway
            try:
                if response.prompt_feedback:
                    # With BLOCK_NONE, block_reason should always be None or not present
                    logger.info(f"Channel {channel_id}: API response feedback (Safety=BLOCK_NONE): {response.prompt_feedback}")
                    if response.prompt_feedback.block_reason:
                         # This would be unexpected with BLOCK_NONE
                         logger.error(f"Channel {channel_id}: UNEXPECTED BLOCK with BLOCK_NONE settings! Reason: {response.prompt_feedback.block_reason}")
            except AttributeError:
                logger.warning(f"Channel {channel_id}: Could not access response.prompt_feedback attribute (Safety=BLOCK_NONE).")
            except Exception as feedback_err:
                 logger.warning(f"Channel {channel_id}: Error accessing prompt_feedback (Safety=BLOCK_NONE): {feedback_err}")

            # Process response text - No ValueError expected due to safety blocks now
            try:
                bot_response_text = response.text
                logger.debug(f"Received API response text (Safety=BLOCK_NONE, length: {len(bot_response_text)}): '{bot_response_text[:200]}...'")
            # ValueError should NOT happen with BLOCK_NONE, but catch other potential errors
            except Exception as e:
                # If it's *not* a ValueError (which signals safety block), it's another issue
                logger.error(f"Channel {channel_id}: Unexpected error accessing API response content (Safety=BLOCK_NONE): {e}", exc_info=True)
                await message.reply("ugh, system error i guess. couldn't process that.", mention_author=False)
                return

            # Store history and send response
            current_channel_history_deque.append({'role': 'user', 'parts': [user_prompt]})
            current_channel_history_deque.append({'role': 'model', 'parts': [bot_response_text]})
            logger.debug(f"Updated history for channel {channel_id}. New length: {len(current_channel_history_deque)} messages.")

            if not bot_response_text:
                 logger.warning(f"Channel {channel_id}: Generated response text was empty (Safety=BLOCK_NONE). Not sending.")
                 return

            # Split long messages as before
            if len(bot_response_text) <= 2000:
                await message.reply(bot_response_text, mention_author=False)
            else:
                logger.warning(f"Response length ({len(bot_response_text)}) exceeds 2000 chars. Splitting.")
                response_parts = []
                for i in range(0, len(bot_response_text), 1990):
                    response_parts.append(bot_response_text[i:i+1990])
                first_part = True
                for part in response_parts:
                    if first_part:
                        await message.reply(part.strip(), mention_author=False)
                        first_part = False
                    else:
                        await message.channel.send(part.strip())
                    await asyncio.sleep(0.5) # Keep slight delay between parts

            logger.info(f"Successfully sent Goth Girl persona response (Safety=BLOCK_NONE) to channel {channel_id}.")

        except Exception as e:
            logger.error(f"Channel {channel_id}: Unhandled exception during Goth Girl persona processing (Safety=BLOCK_NONE). Type: {type(e).__name__}, Error: {e}", exc_info=True)
            try:
                # Use persona-appropriate error message
                await message.reply("ugh, system hiccup. something went wrong. try again later maybe.", mention_author=False)
            except discord.errors.Forbidden:
                 logger.error(f"Channel {channel_id}: Bot lacks permission to send error reply message (Forbidden).")
            except Exception as inner_e:
                 logger.error(f"Channel {channel_id}: Failed to send the error message back to Discord: {inner_e}", exc_info=True)

# --- Run the Bot ---
if __name__ == "__main__":
    if not DISCORD_TOKEN:
        logger.critical("DISCORD_BOT_TOKEN environment variable not found. Exiting.")
    else:
        logger.info(f"Attempting to connect to Discord with bot user...")
        logger.info(f"Using AI Model: {MODEL_NAME}")
        logger.critical(">>> 🚨 Preparing to run bot with Goth Girl Persona and SAFETY FILTERS DISABLED (BLOCK_NONE). MONITOR CLOSELY. 🚨 <<<")
        try:
            client.run(DISCORD_TOKEN, log_handler=None) # Use default logging handler or None
        except discord.errors.LoginFailure:
            logger.critical("Invalid Discord Bot Token provided.")
        except discord.errors.PrivilegedIntentsRequired:
             logger.critical("Privileged Intents (Message Content) are not enabled for the bot.")
             print("\n *** ACTION NEEDED: Enable 'Message Content Intent' in Discord Dev Portal ***\n")
        except Exception as e:
             logger.critical(f"An unexpected error occurred while starting or running the bot: {e}", exc_info=True)