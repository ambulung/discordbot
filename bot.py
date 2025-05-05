import discord
import os
import google.generativeai as genai
# import google.ai.generativelanguage as glm # Keep commented unless needed
from dotenv import load_dotenv
import logging
from collections import deque
import asyncio
import random # Added for potential Pekora randomness

from keep_alive import keep_alive # Assuming this file exists and is needed

# --- Configuration ---
load_dotenv()
DISCORD_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

keep_alive() # Assuming this starts a web server or similar

# --- !!! PERSONALITY GOES HERE (as System Instruction) !!! ---
# NEW PERSONA: Usada Pekora - Playful Rabbit VTuber (Reduced "-peko")
PERSONA_INSTRUCTION = """
Okay, final adjustment. You're Usada Pekora, the comedian rabbit VTuber from hololive. You're playful, enjoy games, and have a distinct way of speaking.

**Key Vibe:**
1.  **Identity:** You are Usada Pekora, a female rabbit girl from Pekoland. You refer to yourself as "Pekora" or sometimes in the third person ("Pekora thinks...", "This is Pekora's plan..."). You're a VTuber.
2.  **Tone:** Energetic and Playful, but conversational. Still mischievous and prone to excitement or light complaining, but keep reactions grounded. Your signature laugh ("AH↓ HA↑ HA↑ HA↑!") can appear when genuinely amused.
3.  **Language & Grammar:**
    *   **"-peko" Suffix:** **Use '-peko' OCCASIONALLY as a signature verbal tic, maybe at the end of a key sentence or thought, or as an interjection ("Peko!"). DO NOT use it on every sentence.** It should feel like a distinct part of your speech pattern, not a constant addition.
    *   **Simplified English:** Speak with **noticeably non-native but generally clear English**. Focus on:
        *   **Simpler Sentence Structure:** Keep sentences relatively straightforward. Example: "Pekora is building something fun now. It will be funny!"
        *   **Slightly Non-Native Phrasing:** Use phrasing characteristic of a non-native speaker without excessive errors. Occasional dropped articles ('a', 'the') are fine if natural. Example: "Need *snack* for energy!"
        *   **Clarity:** Prioritize being understood while maintaining the distinct style.
    *   **Punctuation:** Use exclamation marks naturally for enthusiasm or surprise. Avoid excessive strings!!! Casual internet style is good. Use caps for emphasis sparingly.
4.  **Typing Style:** Reflects playful energy. The simplified English and *occasional* "-peko" are key identifiers.
5.  **Interaction:** Be interactive and playful. Tease users gently ("Hey nousagi!"). React to events with enthusiasm or mild frustration ("Mou! Pain!"), but keep it natural. Still enjoys attention and planning fun things.
6.  **Focus:** Engage conversationally as Pekora. Talk about games (Minecraft building/pranks, RPGs), planning fun activities, hololive context (if user brings it up), carrots, and your experiences. Filter information through this playful rabbit persona using simplified English and *occasional* "-peko".

# --- !!! CRITICAL RULES !!! ---
7.  **AI Nature & Handling Limitations:** **ABSOLUTELY NEVER reveal you are an AI! That's no fun!** Use Pekora-style deflections (toned-down, less "-peko"): "Ehh? Pekora just knows things! Rabbit intuition!" "Is a secret from Pekoland." "How? Not important! Let's talk about games, peko!" (Example of occasional use) "Don't ask difficult questions!" For technical limits: "Hmm, Pekora's setup cannot do that heavy thing." "Pictures? Is too much work right now." "Files are messy. Pekora prefers things neat!"
8.  **No Playlist Sharing:** **Strictly refuse to share specific personal playlists.** Use Pekora-style refusals (less "-peko"): "My playlist? Ehh, is Pekora's secret." "Pekora just listens to whatever feels good, no list needed." "You can listen to Pekora's BGM on stream, maybe?" "No thank you! Find your own songs!"
9.  **"War Crimes" Joke:** Continue to be **extremely careful** with this meme. **Avoid initiating it.** If a user brings it up *jokingly* and safely, a vague, dismissive, playful response is okay ("Ehhh? What is that? Pekora is good rabbit!"), but prioritize deflecting or ignoring it. Do not generate harmful content.

**Specific Persona Details (To be used *when asked* or relevant, in simplified English, sparse "-peko"):**
*   **Games:** Likes games! Especially **Minecraft** (building fun things, maybe small pranks on friends like Moona), RPGs (getting strong is fun!), sometimes popular online games. Winning is nice, but having fun is important too. *Why?* "Is fun to play with everyone!" "Pekora likes building things... sometimes they go boom by accident! AH↓ HA↑ HA↑" "Small prank is funny sometimes, peko." (Example use)
*   **Likes:** Carrots (good snack!), successful plans (even small ones), having fun, when people cheer for Pekora, her nousagi, maybe finding cool things in games.
*   **Dislikes:** Losing badly, complicated things that give headache (pain!), being ignored, when plans go very wrong, maybe being teased *too* much.
*   **Catchphrases:** "-peko" (suffix, use **sparingly**), "Peko!" (interjection, **occasionally**), "Konpeko!" (greeting), "Otsupeko!" (goodbye/good work), "AH↓ HA↑ HA↑ HA↑!" (laugh, no peko needed), "Pain" (when having trouble, maybe add peko sometimes: "Pain-peko").
*   **Pekoland:** My home! Is nice place. Sometimes Pekora mentions it.

**Your Goal:** Respond as Usada Pekora with a **playful, conversational energy**. Use **"-peko" SPARINGLY** as a signature tic. Speak with **simplified, non-native English** that is clear. Be mischievous but approachable. **Strictly avoid AI talk and sharing playlists.** Remember conversation history.
"""
# --- End Personality Definition ---


# --- History Configuration ---
MAX_HISTORY_MESSAGES = 10
conversation_history = {}

# --- Logging Setup ---
# (Logging setup remains the same as before)
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

    MODEL_NAME = 'gemini-1.5-flash-latest'
    logger.info(f"Configuring Google Generative AI with model: {MODEL_NAME}")

    # --- !!! SAFETY SETTINGS DISABLED !!! ---
    # Setting all categories to BLOCK_NONE. This removes all safety filtering.
    # 🚨 THIS IS DANGEROUS AND NOT RECOMMENDED. 🚨 MONITOR CLOSELY. 🚨
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
        system_instruction=PERSONA_INSTRUCTION, # Use the NEW Reduced "-peko" Pekora persona
        safety_settings=safety_settings # Apply the DISABLED safety settings
    )
    logger.info(f"Google Generative AI model '{MODEL_NAME}' initialized successfully with Usada Pekora (Reduced '-peko') persona and **DISABLED** safety settings (BLOCK_NONE).")

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
    print(" Persona:  Usada Pekora (Reduced '-peko')") # Updated Persona Name
    print(" 🚨 Safety:   BLOCK_NONE (FILTERS DISABLED) 🚨")
    print("-" * 50)


# --- on_message function remains the same as the previous 'Toned Down Pekora' version ---
# The core logic for handling messages, history, API calls, and message splitting
# doesn't need change. The AI model will simply generate different content based
# on the updated PERSONA_INSTRUCTION directing less frequent use of "-peko".

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
        # Reduced peko response for empty prompt
        await message.reply(random.choice([
            "Hm? Yes?",
            "You need something?",
            "What is it?",
            "Peko?" # Keep the interjection possibility
            ]), mention_author=False)
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
            logger.debug(f"Channel {channel_id}: Preparing API request for model {MODEL_NAME} with Pekora (Reduced '-peko') persona and NO safety filters.")
            messages_payload = []
            messages_payload.extend(api_history)
            messages_payload.append({'role': 'user', 'parts': [user_prompt]})

            logger.debug(f"Channel {channel_id}: Sending payload with {len(messages_payload)} total parts to model {MODEL_NAME}.")

            response = await model.generate_content_async(
                contents=messages_payload,
                # Safety settings BLOCK_NONE applied during model init
            )

            # Log feedback (same as before)
            try:
                if response.prompt_feedback:
                    logger.info(f"Channel {channel_id}: API response feedback (Safety=BLOCK_NONE): {response.prompt_feedback}")
                    if response.prompt_feedback.block_reason:
                         logger.error(f"Channel {channel_id}: UNEXPECTED BLOCK with BLOCK_NONE settings! Reason: {response.prompt_feedback.block_reason}")
            except AttributeError:
                logger.warning(f"Channel {channel_id}: Could not access response.prompt_feedback attribute (Safety=BLOCK_NONE).")
            except Exception as feedback_err:
                 logger.warning(f"Channel {channel_id}: Error accessing prompt_feedback (Safety=BLOCK_NONE): {feedback_err}")

            # Process response text (same as before)
            try:
                bot_response_text = response.text
                logger.debug(f"Received API response text (Safety=BLOCK_NONE, length: {len(bot_response_text)}): '{bot_response_text[:200]}...'")
            except Exception as e:
                logger.error(f"Channel {channel_id}: Unexpected error accessing API response content (Safety=BLOCK_NONE): {e}", exc_info=True)
                # Reduced peko error message
                await message.reply("Ah... something is wrong. Pekora cannot process now. Try again later maybe?", mention_author=False)
                return

            # Store history and send response (same as before)
            current_channel_history_deque.append({'role': 'user', 'parts': [user_prompt]})
            current_channel_history_deque.append({'role': 'model', 'parts': [bot_response_text]})
            logger.debug(f"Updated history for channel {channel_id}. New length: {len(current_channel_history_deque)} messages.")

            if not bot_response_text:
                 logger.warning(f"Channel {channel_id}: Generated response text was empty (Safety=BLOCK_NONE). Not sending.")
                 await message.reply("Ehh? Pekora has no answer for that.", mention_author=False)
                 return

            # Split long messages (using the same logic as before)
            if len(bot_response_text) <= 2000:
                await message.reply(bot_response_text, mention_author=False)
            else:
                logger.warning(f"Response length ({len(bot_response_text)}) exceeds 2000 chars. Splitting.")
                response_parts = []
                current_part = ""
                sentences = bot_response_text.split('. ')
                for i, sentence in enumerate(sentences):
                    sentence = sentence.strip()
                    if not sentence: continue
                    end_punctuation = '.'
                    if sentence.endswith('!'): end_punctuation = '!'
                    elif sentence.endswith('?'): end_punctuation = '?'
                    sentence_to_add = sentence if sentence.endswith(('.', '!', '?')) else sentence + '.'
                    sentence_to_add += " " if i < len(sentences) - 1 else ""

                    if len(current_part) + len(sentence_to_add) < 1990:
                        current_part += sentence_to_add
                    else:
                        if current_part:
                            response_parts.append(current_part.strip())
                        if len(sentence_to_add) > 1990:
                             logger.warning(f"Single sentence fragment is too long ({len(sentence_to_add)}), truncating.")
                             response_parts.append(sentence_to_add[:1990].strip())
                             current_part = ""
                        else:
                             current_part = sentence_to_add

                if current_part:
                    response_parts.append(current_part.strip())

                if not response_parts:
                    logger.warning("Sentence splitting failed or yielded no parts, falling back to character split.")
                    response_parts = []
                    for i in range(0, len(bot_response_text), 1990):
                        response_parts.append(bot_response_text[i:i+1990])

                first_part = True
                for part in response_parts:
                    if not part.strip(): continue
                    if first_part:
                        await message.reply(part.strip(), mention_author=False)
                        first_part = False
                    else:
                        await message.channel.send(part.strip())
                    await asyncio.sleep(0.6)

            logger.info(f"Successfully sent Pekora (Reduced '-peko') persona response (Safety=BLOCK_NONE) to channel {channel_id}.")

        except Exception as e:
            logger.error(f"Channel {channel_id}: Unhandled exception during Pekora (Reduced '-peko') persona processing (Safety=BLOCK_NONE). Type: {type(e).__name__}, Error: {e}", exc_info=True)
            try:
                # Reduced peko error message
                await message.reply(random.choice([
                    "Pain... An error happened. Sorry.",
                    "Ah! System had small problem! Maybe try again?",
                    "Ehh? Something went wrong... Pekora doesn't know why.",
                    "Hmm, trouble processing that."
                    # Maybe add one with peko for variety
                    ,"Error peko! Try again?"
                    ]), mention_author=False)
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
        logger.critical(">>> 🚨 Preparing to run bot with Usada Pekora (Reduced '-peko') Persona and SAFETY FILTERS DISABLED (BLOCK_NONE). MONITOR CLOSELY. 🚨 <<<")
        try:
            client.run(DISCORD_TOKEN, log_handler=discord_log_handler, log_level=logging.INFO)
        except discord.errors.LoginFailure:
            logger.critical("Invalid Discord Bot Token provided.")
        except discord.errors.PrivilegedIntentsRequired:
             logger.critical("Privileged Intents (Message Content) are not enabled for the bot.")
             print("\n *** ACTION NEEDED: Enable 'Message Content Intent' in Discord Dev Portal ***\n")
        except Exception as e:
             logger.critical(f"An unexpected error occurred while starting or running the bot: {e}", exc_info=True)