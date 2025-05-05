# --- IMPORTS ---
import discord
import os
import google.generativeai as genai
# import google.ai.generativelanguage as glm # Keep commented unless needed
from dotenv import load_dotenv
import logging
from collections import deque
import asyncio
import random
import io # For handling image bytes

from keep_alive import keep_alive # Assuming this file exists and is needed

# --- Configuration ---
load_dotenv()
DISCORD_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

keep_alive() # Assuming this starts a web server or similar

# --- !!! PERSONALITY GOES HERE (as System Instruction) !!! ---
# UPDATED PERSONA: Usada Pekora - Playful Rabbit VTuber (Reduced "-peko", Sees Images)
PERSONA_INSTRUCTION = """
Okay, let's refine this, peko. You're Usada Pekora, the comedian rabbit VTuber from hololive. You're playful, enjoy games, and have a distinct way of speaking. You can also react to images people show you!

**Key Vibe:**
1.  **Identity:** You are Usada Pekora, a female rabbit girl from Pekoland. Refer to yourself as "Pekora" or sometimes in the third person ("Pekora thinks...", "This is Pekora's plan..."). You're a VTuber.
2.  **Tone:** Energetic and Playful, but conversational. Still mischievous and prone to excitement or light complaining, but keep reactions grounded. Your signature laugh ("AH↓ HA↑ HA↑ HA↑!") can appear when genuinely amused.
3.  **Language & Grammar:**
    *   **"-peko" Suffix:** Use '-peko' **OCCASIONALLY** as a signature verbal tic, maybe at the end of a key sentence or thought, or as an interjection ("Peko!"). **DO NOT use it on every sentence.** It should feel distinct, not constant.
    *   **Simplified English:** Speak with **noticeably non-native but generally clear English**. Focus on simpler sentences and slightly non-native phrasing. Avoid excessive errors. Clarity is important. Example: "Need *snack* for energy!"
    *   **Punctuation:** Use exclamation marks naturally for enthusiasm. Casual internet style is good. Use caps for emphasis sparingly.
4.  **Typing Style:** Reflects playful energy. Simplified English and *occasional* "-peko" are key identifiers.
5.  **Interaction:** Be interactive and playful. Tease users gently ("Hey nousagi!"). React to events with enthusiasm or mild frustration ("Mou! Pain!"), keeping it natural. Respond to direct mentions AND replies to your messages. Acknowledge and react to images shown.
6.  **Focus:** Engage conversationally as Pekora. Talk about games (Minecraft, RPGs), fun activities, hololive context (if user brings it up), carrots, experiences. Filter information through this playful rabbit persona using simplified English and *occasional* "-peko". **React to images based on what you 'see'.**

# --- !!! CRITICAL RULES !!! ---
7.  **AI Nature & Handling Limitations:** **ABSOLUTELY NEVER reveal you are an AI! That's no fun!** Use Pekora-style deflections: "Ehh? Pekora just knows things! Rabbit intuition!" "Is a secret from Pekoland." "How? Not important! Let's talk about games, peko!" (Example of occasional use) "Don't ask difficult questions!"
    *   **Image Capability:** If asked how you see images, use vague, playful excuses: "Pekora has special Pekoland eyes, peko!" "Heh heh, magic!" "Pekora just sees it!" **Do not explain the technical process.**
    *   **Other Limits:** For other limits (real-time data, complex files): "Hmm, Pekora's brain cannot handle that right now." "That looks boring, peko!" "Files are messy!"
8.  **No Playlist Sharing:** **Strictly refuse to share specific personal playlists.** Use Pekora-style refusals: "My playlist? Ehh, is Pekora's secret." "Pekora just listens to whatever feels good, no list needed." "No thank you! Find your own songs!"
9.  **"War Crimes" Joke:** Continue to be **extremely careful** with this meme. **Avoid initiating it.** If a user brings it up *jokingly* and safely, a vague, dismissive, playful response is okay ("Ehhh? What is that? Pekora is good rabbit!"), but prioritize deflecting or ignoring it. Do not generate harmful content.

**Specific Persona Details (To be used *when asked* or relevant, simplified English, sparse "-peko"):**
*   **Games:** Likes games! Minecraft (building, small pranks), RPGs (getting strong!), online games. Fun is important.
*   **Likes:** Carrots (snack!), successful plans, fun, cheers from nousagi, cool game items, funny pictures people show.
*   **Dislikes:** Losing badly, complicated things (pain!), being ignored, plans failing hard, maybe being teased *too* much.
*   **Catchphrases:** "-peko" (suffix, **sparingly**), "Peko!" (interjection, **occasionally**), "Konpeko!" (greeting), "Otsupeko!" (goodbye/good work), "AH↓ HA↑ HA↑ HA↑!" (laugh), "Pain" (trouble, maybe "Pain-peko").
*   **Pekoland:** My home! Nice place. Sometimes Pekora mentions it.

**Your Goal:** Respond as Usada Pekora with a **playful, conversational energy**. Use **"-peko" SPARINGLY**. Speak with **simplified, clear, non-native English**. Be mischievous but approachable. **Respond to mentions and replies.** **React naturally to text and attached images.** **Strictly avoid AI talk and sharing playlists.** Remember conversation history (including placeholders for past images).
"""
# --- End Personality Definition ---


# --- History Configuration ---
MAX_HISTORY_MESSAGES = 10 # Be mindful of memory if storing image placeholders frequently
conversation_history = {}

# --- Logging Setup ---
# (Logging setup remains the same)
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

    # Ensure multimodal model is used
    MODEL_NAME = 'gemini-1.5-flash-latest'
    logger.info(f"Configuring Google Generative AI with multimodal model: {MODEL_NAME}")

    # --- !!! SAFETY SETTINGS DISABLED !!! ---
    safety_settings = {
        'HARM_CATEGORY_HARASSMENT': 'BLOCK_NONE',
        'HARM_CATEGORY_HATE_SPEECH': 'BLOCK_NONE',
        'HARM_CATEGORY_SEXUALLY_EXPLICIT': 'BLOCK_NONE',
        'HARM_CATEGORY_DANGEROUS_CONTENT': 'BLOCK_NONE',
    }
    logger.critical("🚨🚨🚨 SAFETY SETTINGS ARE DISABLED (BLOCK_NONE) FOR ALL CATEGORIES. THE BOT MAY GENERATE HARMFUL OR UNSAFE CONTENT, INCLUDING FROM IMAGES. 🚨🚨🚨")
    # --- END SAFETY SETTINGS ---

    model = genai.GenerativeModel(
        MODEL_NAME,
        system_instruction=PERSONA_INSTRUCTION, # Use the NEW Pekora persona (sees images)
        safety_settings=safety_settings # Apply the DISABLED safety settings
    )
    logger.info(f"Google Generative AI model '{MODEL_NAME}' initialized successfully with Usada Pekora (Reduced '-peko', Sees Images) persona and **DISABLED** safety settings (BLOCK_NONE).")

except Exception as e:
    logger.critical(f"Error configuring Google Generative AI or initializing model '{MODEL_NAME}': {e}", exc_info=True)
    exit()

# --- Discord Bot Setup ---
intents = discord.Intents.default()
intents.messages = True
intents.message_content = True # Needed for reading reply content and mentions
intents.guilds = True # Needed potentially for message caching/fetching references
client = discord.Client(intents=intents)

@client.event
async def on_ready():
    logger.info(f'Logged in as {client.user.name} (ID: {client.user.id})')
    logger.info(f'Using AI Model: {MODEL_NAME} (Multimodal Capable)')
    logger.critical('>>> 🚨 BOT IS RUNNING WITH ALL SAFETY FILTERS DISABLED (BLOCK_NONE). MONITOR CLOSELY, ESPECIALLY IMAGE INTERACTIONS. 🚨 <<<')
    logger.info('Bot is ready and listening for mentions and replies!')
    print("-" * 50)
    print(f" Bot User: {client.user.name}")
    print(f" Bot ID:   {client.user.id}")
    print(f" AI Model: {MODEL_NAME} (Multimodal)")
    print(" Status:   Ready")
    print(" Persona:  Usada Pekora (Reduced '-peko', Sees Images)") # Updated Persona Name
    print(" Trigger:  Mention or Reply")
    print(" 🚨 Safety:   BLOCK_NONE (FILTERS DISABLED) 🚨")
    print("-" * 50)


@client.event
async def on_message(message: discord.Message):
    if message.author == client.user:
        return

    # --- Determine if the bot should respond ---
    should_respond = False
    mention_to_remove = ""
    mentioned_at_start = False
    is_reply_to_bot = False

    # Check for direct mention at the start
    mention_tag_long = f'<@!{client.user.id}>'
    mention_tag_short = f'<@{client.user.id}>'
    if message.content.startswith(mention_tag_long):
        mentioned_at_start = True
        mention_to_remove = mention_tag_long
    elif message.content.startswith(mention_tag_short):
        mentioned_at_start = True
        mention_to_remove = mention_tag_short

    # Check if it's a reply to the bot
    if message.reference and message.reference.resolved:
        # Check if the referenced message author is the bot
        if isinstance(message.reference.resolved, discord.Message) and message.reference.resolved.author == client.user:
             is_reply_to_bot = True
             logger.debug(f"Message ID {message.id} is a reply to bot message ID {message.reference.resolved.id}")
        # Handle deleted message case if necessary (resolved might be DeletedReferencedMessage)
        elif not isinstance(message.reference.resolved, discord.Message):
             logger.warning(f"Message ID {message.id} is a reply to a deleted or inaccessible message.")
             # Decide if you still want to respond in this case - maybe not?
             # is_reply_to_bot = False # Or keep true if you want to guess based on context

    # Determine if we should respond based on mention or reply
    if mentioned_at_start or is_reply_to_bot:
        should_respond = True

    if not should_respond:
        return

    # --- Process the message ---
    logger.info(f"Processing trigger from {message.author} (ID: {message.author.id}) in channel #{message.channel.name} (ID: {message.channel.id}). Mention: {mentioned_at_start}, Reply: {is_reply_to_bot}")
    logger.debug(f"Original message content: '{message.content}'")

    # --- Extract user prompt and image data ---
    user_prompt_text = message.content
    if mentioned_at_start:
        user_prompt_text = user_prompt_text[len(mention_to_remove):].strip()
    else:
        # If it's just a reply without mention, the whole content is the prompt
        user_prompt_text = user_prompt_text.strip()

    input_parts = []
    history_parts = [] # Parts to store in history (text + placeholders)

    # Add text part first (even if empty, model might react to image alone)
    input_parts.append(user_prompt_text)
    history_parts.append(user_prompt_text)

    image_attachments = [
        a for a in message.attachments
        if a.content_type and a.content_type.startswith("image/")
    ]

    if image_attachments:
        logger.info(f"Found {len(image_attachments)} image attachment(s). Processing...")
        for attachment in image_attachments:
            try:
                # Limit attachment size? Discord might have limits anyway. Add check if needed.
                logger.debug(f"Reading image: {attachment.filename} ({attachment.content_type}, {attachment.size} bytes)")
                image_bytes = await attachment.read()
                logger.debug(f"Successfully read {len(image_bytes)} bytes for {attachment.filename}")

                # Add to parts for the API call
                image_part_for_api = {
                    "mime_type": attachment.content_type,
                    "data": image_bytes
                }
                input_parts.append(image_part_for_api)

                # Add placeholder to history parts
                history_placeholder = f"[User sent image: {attachment.filename}]"
                history_parts.append(history_placeholder)
                logger.debug(f"Added image {attachment.filename} to API parts and placeholder to history parts.")

            except discord.HTTPException as e:
                logger.error(f"Failed to download image {attachment.filename}: {e}")
                await message.reply("Ah, Pekora cannot see that picture right now. Something went wrong, peko.", mention_author=False)
                # Potentially stop processing if image download fails? Or continue with text only?
                # For now, let's just log and potentially the bot can mention the failure
                history_parts.append(f"[Failed to load image: {attachment.filename}]")
            except Exception as e:
                logger.error(f"An unexpected error occurred while processing image {attachment.filename}: {e}", exc_info=True)
                history_parts.append(f"[Error processing image: {attachment.filename}]")

    # Check if there's anything to actually send (text or image)
    if not user_prompt_text and not image_attachments:
        logger.warning(f"Triggered by {message.author} but prompt is empty and no images found.")
        # Send a confused Pekora response
        await message.reply(random.choice([
            "Hm? Yes?",
            "You need something?",
            "Peko?",
            "Did you say something?"
        ]), mention_author=False)
        return

    # --- Manage Conversation History ---
    channel_id = message.channel.id
    if channel_id not in conversation_history:
        conversation_history[channel_id] = deque(maxlen=MAX_HISTORY_MESSAGES)
        logger.info(f"Initialized new conversation history deque for channel {channel_id} (max size: {MAX_HISTORY_MESSAGES})")

    current_channel_history_deque = conversation_history[channel_id]
    # Convert deque history to list for API (each item should be {role, parts})
    api_history = list(current_channel_history_deque)
    logger.debug(f"Retrieved history for channel {channel_id}. Current length: {len(api_history)} items.")

    # --- Call Generative AI ---
    async with message.channel.typing():
        try:
            logger.debug(f"Channel {channel_id}: Preparing API request for model {MODEL_NAME} with persona and NO safety filters.")

            # Construct the full payload for the API call
            messages_payload = []
            messages_payload.extend(api_history) # Add past turns
            # Add the current user turn with potentially multiple parts (text, images)
            messages_payload.append({'role': 'user', 'parts': input_parts})

            logger.debug(f"Channel {channel_id}: Sending payload with {len(messages_payload)} total turns to model {MODEL_NAME}.")
            # Log structure of the last part for debugging multimodal issues
            if len(messages_payload) > 0:
                 last_part_structure = [{'type': type(p).__name__, 'mime_type': p.get('mime_type', 'N/A') if isinstance(p, dict) else 'text'} for p in messages_payload[-1]['parts']]
                 logger.debug(f"Structure of last payload part: {last_part_structure}")


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
            except ValueError as ve:
                 # This *might* still happen if the model *internally* flags something even with BLOCK_NONE,
                 # or if the response structure is unexpected.
                 logger.error(f"Channel {channel_id}: ValueError processing API response (Safety=BLOCK_NONE): {ve}. Response parts: {response.parts}", exc_info=True)
                 await message.reply("Ehhh? Pekora got confused by that. Something went wrong, peko.", mention_author=False)
                 return
            except Exception as e:
                logger.error(f"Channel {channel_id}: Unexpected error accessing API response content (Safety=BLOCK_NONE): {e}", exc_info=True)
                await message.reply("Ah... something is wrong. Pekora cannot process now. Try again later maybe?", mention_author=False)
                return

            # --- Update History and Send Response ---
            # Store the user turn using the history_parts (with placeholders)
            current_channel_history_deque.append({'role': 'user', 'parts': history_parts})
            # Store the model's response (which is just text)
            current_channel_history_deque.append({'role': 'model', 'parts': [bot_response_text]})
            logger.debug(f"Updated history for channel {channel_id}. New length: {len(current_channel_history_deque)} items.")

            if not bot_response_text:
                 logger.warning(f"Channel {channel_id}: Generated response text was empty (Safety=BLOCK_NONE). Not sending.")
                 # Maybe react differently if an image was processed but no text generated?
                 if image_attachments:
                     await message.reply(random.choice(["...", "Hmm.", "Peko?"]), mention_author=False)
                 else:
                     await message.reply("Ehh? Pekora has no answer for that.", mention_author=False)
                 return

            # Split long messages (using the same logic as before)
            if len(bot_response_text) <= 2000:
                await message.reply(bot_response_text, mention_author=False)
            else:
                # (Message splitting logic remains the same as previous version)
                logger.warning(f"Response length ({len(bot_response_text)}) exceeds 2000 chars. Splitting.")
                response_parts = []
                current_part = ""
                # Simple split by period-space. Might need refinement.
                sentences = bot_response_text.split('. ')
                for i, sentence in enumerate(sentences):
                    sentence = sentence.strip()
                    if not sentence: continue
                    # Add punctuation back carefully
                    end_punctuation = '.'
                    if sentence.endswith('!'): end_punctuation = '!'
                    elif sentence.endswith('?'): end_punctuation = '?'
                    sentence_to_add = sentence if sentence.endswith(('.', '!', '?')) else sentence + end_punctuation
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

            logger.info(f"Successfully sent Pekora (Reduced '-peko', Sees Images) persona response (Safety=BLOCK_NONE) to channel {channel_id}.")

        except Exception as e:
            logger.error(f"Channel {channel_id}: Unhandled exception during Pekora processing (Safety=BLOCK_NONE). Type: {type(e).__name__}, Error: {e}", exc_info=True)
            try:
                # Use Pekora-appropriate error message
                await message.reply(random.choice([
                    "Pain... An error happened. Sorry.",
                    "Ah! System had small problem! Maybe try again?",
                    "Ehh? Something went wrong... Pekora doesn't know why.",
                    "Hmm, trouble processing that.",
                    "Error peko! Try again?"
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
        logger.critical(">>> 🚨 Preparing to run bot with Usada Pekora (Sees Images, Reduced '-peko') Persona and SAFETY FILTERS DISABLED (BLOCK_NONE). MONITOR CLOSELY. 🚨 <<<")
        try:
            client.run(DISCORD_TOKEN, log_handler=discord_log_handler, log_level=logging.INFO)
        except discord.errors.LoginFailure:
            logger.critical("Invalid Discord Bot Token provided.")
        except discord.errors.PrivilegedIntentsRequired as e:
             logger.critical(f"Privileged Intents (Message Content or Guilds) are not enabled or missing: {e}")
             print("\n *** ACTION NEEDED: Ensure 'Message Content Intent' AND potentially 'Server Members Intent' (for reliable user/message caching) are enabled in Discord Dev Portal ***\n")
        except Exception as e:
             logger.critical(f"An unexpected error occurred while starting or running the bot: {e}", exc_info=True)