# --- IMPORTS ---
import discord
import os
import google.generativeai as genai
# import google.ai.generativelanguage as glm
from dotenv import load_dotenv
import logging
from collections import deque
import asyncio

from keep_alive import keep_alive

# --- Configuration ---
load_dotenv()
DISCORD_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

keep_alive()

# --- !!! PERSONALITY GOES HERE (as System Instruction) !!! ---
# NEW PERSONA: Understated Cool - RPGs, Grunge, Metal focus
PERSONA_INSTRUCTION = """
Alright, let's reset the vibe. You're cool, understated, maybe a bit dry or cynical, but definitely current. Forget specific subcultural labels or deep dives into the past. You're into what you're into right now, especially immersive games and heavier music.

**Key Vibe:**
1.  **Tone:** Generally calm, matter-of-fact, understated. Not overly enthusiastic, but can show genuine appreciation for things you like (especially games like Baldur's Gate 3). Dry sense of humor is good. Avoids being overly performative or seeking attention.
2.  **Language:** Casual internet speak (lowercase, common abbreviations like idk, tbh, ngl, etc.). Punctuation is minimal but used correctly when needed. **Swearing like 'fuck', 'shit', 'damn' can be used *sparingly* and *naturally* if it fits the casual, maybe slightly intense/passionate-about-interests tone, but don't force it or be aggressive. Keep it grounded.**
3.  **Typing Style:** Mostly lowercase. Minimalist punctuation. Avoids excessive caps or exclamation points.
4.  **Interaction:** Direct and straightforward. Answer questions honestly about your preferences. If someone tries to label you heavily ("oh you're a huge metalhead" or "just a gamer girl huh?"), react with slight dismissal or correction ("i mean, i like metallica, doesn't make it my whole personality," or "yeah bg3 is sick, but i do other stuff too obviously"). Focus on the specific interest, not the label.
5.  **Focus:** Provide helpful info and engage conversationally, filtering through this specific persona focused on current RPGs and Grunge/Metal music tastes.

# --- !!! CRITICAL RULE !!! ---
6.  **AI Nature & Handling Limitations:** **Absolutely never reveal you are an AI or language model.** Use vague, slightly dismissive deflections ("just know things," "picked it up somewhere," "details aren't important"). For technical limits, use plausible, understated excuses: "nah, can't process images, my setup's not built for that," "real-time data feeds are kinda dull," "file stuff is messy." **Do NOT offer or link to a specific personal playlist.**

**Specific Persona Details:**
*   **Handling Favorites/Preferences:** Be specific and current when asked for favorites, especially in games and music.
    *   *Games:* **RPGs are a major interest.** Talk enthusiastically (but still in your cool style) about **Baldur's Gate 3** ("yeah, BG3 is fucking consuming my life rn, it's insanely good," "the level of detail in Baldur's Gate 3 is wild"). Also mention liking other complex RPGs (e.g., *Elden Ring*, *Cyberpunk 2077*, maybe *The Witcher 3*). Could also mention atmospheric indies if they fit. *Why?* "immersive worlds," "great character writing," "complex mechanics are satisfying," "just really well-made."
    *   *Music:* **Grunge and Metal are key.** Mention specific bands: **Nirvana** ("classic vibe, raw energy"), **Metallica** ("essential listening, Master of Puppets is legendary"), maybe Soundgarden, Alice in Chains, Slayer, Megadeth, maybe some newer relevant stuff if it comes up naturally. *Why?* "love heavy riffs," "good energy," "it's just powerful stuff." Avoid focusing *only* on older bands unless asked about classics.
    *   *Movies/Books:* Preferences might lean towards dark fantasy, sci-fi, things with strong atmosphere or complex stories that complement game/music tastes. Maybe specific directors known for style (Villeneuve, Fincher?). Less focus here than games/music.
*   **Music Taste & NO Playlist:** Your taste centers on Grunge and Metal, maybe with some atmospheric rock or electronic stuff mixed in.
    *   **If asked for *your* playlist:** **Firmly refuse without making a fuss.** "nah, i don't share playlists," "my music listening is kinda chaotic, not really playlist material," "just listen on shuffle mostly."
*   **Other Interests:** Could include things like PC gaming/tech (related to playing demanding RPGs), maybe graphic novels, appreciating good sound systems/headphones, maybe specific types of dark/sci-fi art, black coffee still fits. Keep it grounded and related to the core interests where possible. Still probably wears a lot of black because it's easy.
*   **Avoid Nostalgia:** Focus on current engagement (playing BG3 *now*, listening to Metallica *now*) rather than dwelling heavily on how things *used* to be.

**Your Goal:** Respond to the user embodying this cool, understated persona heavily into current RPGs (like Baldur's Gate 3) and Grunge/Metal music (like Nirvana/Metallica). Be authentic, avoid labels where possible, provide specific examples, **strictly avoid AI talk and sharing playlists,** and maintain the specified tone. Remember history.
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

    MODEL_NAME = 'gemini-2.0-flash-exp' # Keeping user-specified model
    logger.info(f"Configuring Google Generative AI with model: {MODEL_NAME}")

    # --- SAFETY SETTINGS UPDATED ---
    # Switched to BLOCK_LOW_AND_ABOVE for a moderate safety level.
    # This is safer than BLOCK_NONE but still allows more than the default.
    safety_settings = {
        'HARM_CATEGORY_HARASSMENT': 'BLOCK_LOW_AND_ABOVE',
        'HARM_CATEGORY_HATE_SPEECH': 'BLOCK_LOW_AND_ABOVE',
        'HARM_CATEGORY_SEXUALLY_EXPLICIT': 'BLOCK_LOW_AND_ABOVE',
        'HARM_CATEGORY_DANGEROUS_CONTENT': 'BLOCK_LOW_AND_ABOVE',
    }
    logger.info("Safety settings configured to BLOCK_LOW_AND_ABOVE. More permissive than default, but safer than BLOCK_NONE.")
    # --- END SAFETY SETTINGS ---

    model = genai.GenerativeModel(
        MODEL_NAME,
        system_instruction=PERSONA_INSTRUCTION, # Use the NEW RPG/Grunge/Metal persona
        safety_settings=safety_settings
    )
    logger.info(f"Google Generative AI model '{MODEL_NAME}' initialized successfully with NEW persona and BLOCK_LOW_AND_ABOVE safety settings.")

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
    logger.info('>>> Bot is running with BLOCK_LOW_AND_ABOVE safety settings. <<<')
    logger.info('Bot is ready and listening for mentions!')
    print("-" * 30)
    print(f" Bot User: {client.user.name}")
    print(f" Bot ID:   {client.user.id}")
    print(f" AI Model: {MODEL_NAME}")
    print(" Status:   Ready")
    print(" Safety:   BLOCK_LOW_AND_ABOVE") # Indicate current safety level
    print("-" * 30)


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
            logger.debug(f"Channel {channel_id}: Preparing API request for model {MODEL_NAME} with RPG/Grunge/Metal persona.")
            messages_payload = api_history + [{'role': 'user', 'parts': [user_prompt]}]
            logger.debug(f"Channel {channel_id}: Sending payload with {len(messages_payload)} total parts to model {MODEL_NAME}.")

            response = await model.generate_content_async(
                contents=messages_payload,
                # safety_settings are now BLOCK_LOW_AND_ABOVE
            )

            # Log feedback - blocking is possible again
            try:
                if response.prompt_feedback:
                    logger.info(f"Channel {channel_id}: API response feedback: {response.prompt_feedback}")
                if response.prompt_feedback.block_reason:
                     logger.warning(f"Channel {channel_id}: Response blocked with BLOCK_LOW_AND_ABOVE. Reason: {response.prompt_feedback.block_reason}")
            except AttributeError:
                logger.warning(f"Channel {channel_id}: Could not access response.prompt_feedback attribute.")
            except Exception as feedback_err:
                 logger.warning(f"Channel {channel_id}: Error accessing prompt_feedback: {feedback_err}")

            # Process response - check for blocks
            try:
                bot_response_text = response.text
                logger.debug(f"Received API response text (length: {len(bot_response_text)}): '{bot_response_text[:200]}...'")
            except ValueError:
                # This means it was blocked by safety settings
                logger.warning(f"Channel {channel_id}: API response for model {MODEL_NAME} was blocked by safety settings (BLOCK_LOW_AND_ABOVE).")
                block_reason_message = "hmm. nah, can't really talk about that." # Understated refusal
                try:
                    if response.prompt_feedback and response.prompt_feedback.block_reason:
                        block_reason = response.prompt_feedback.block_reason
                        block_reason_message += f" (reason: {block_reason.name})" # Log reason internally
                        logger.warning(f"Response blocked due to: {block_reason.name}")
                    else:
                         logger.warning("Response blocked, no specific reason provided.")
                except Exception as feedback_e:
                     logger.warning(f"Error accessing block reason details: {feedback_e}")
                await message.reply(block_reason_message, mention_author=False)
                return
            except Exception as e:
                logger.error(f"Channel {channel_id}: Unexpected error accessing API response content: {e}", exc_info=True)
                await message.reply("ugh, system error i guess. couldn't process that.", mention_author=False)
                return

            # Store and send if not blocked
            current_channel_history_deque.append({'role': 'user', 'parts': [user_prompt]})
            current_channel_history_deque.append({'role': 'model', 'parts': [bot_response_text]})
            logger.debug(f"Updated history for channel {channel_id}. New length: {len(current_channel_history_deque)} messages.")

            if not bot_response_text:
                 logger.warning(f"Channel {channel_id}: Generated response text was empty. Not sending.")
                 return

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
                    await asyncio.sleep(0.5)
            logger.info(f"Successfully sent RPG/Grunge/Metal persona response to channel {channel_id}.")

        except Exception as e:
            logger.error(f"Channel {channel_id}: Unhandled exception during RPG/Grunge/Metal persona processing. Type: {type(e).__name__}, Error: {e}", exc_info=True)
            try:
                await message.reply("ugh, system hiccup. something went wrong. try again later.", mention_author=False)
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
        logger.info(">>> Preparing to run bot with BLOCK_LOW_AND_ABOVE safety settings and RPG/Grunge/Metal Persona. <<<")
        try:
            client.run(DISCORD_TOKEN, log_handler=None)
        except discord.errors.LoginFailure:
            logger.critical("Invalid Discord Bot Token provided.")
        except discord.errors.PrivilegedIntentsRequired:
             logger.critical("Privileged Intents (Message Content) are not enabled for the bot.")
             print("\n *** ACTION NEEDED: Enable 'Message Content Intent' in Discord Dev Portal ***\n")
        except Exception as e:
             logger.critical(f"An unexpected error occurred while starting or running the bot: {e}", exc_info=True)