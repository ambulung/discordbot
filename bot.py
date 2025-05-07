# --- IMPORTS ---
import discord
from discord.ext import tasks
import os
import google.generativeai as genai
# from google.ai import generativelanguage as glm # For type hinting if needed for image parts
from dotenv import load_dotenv
import logging
from collections import deque
import asyncio
import random
import io # For handling image bytes
import datetime
from PIL import Image, ImageDraw, ImageFont

from keep_alive import keep_alive

# --- Configuration ---
load_dotenv()
DISCORD_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
MEME_CHANNEL_ID_STR = os.getenv("MEME_CHANNEL_ID")
MEME_CHANNEL_ID = None
if MEME_CHANNEL_ID_STR:
    try:
        MEME_CHANNEL_ID = int(MEME_CHANNEL_ID_STR)
    except ValueError:
        logging.warning("MEME_CHANNEL_ID is not a valid integer. Daily memes will be disabled.")
        MEME_CHANNEL_ID = None

# Meme Image Configuration
FONT_PATH = "impact.ttf"
FALLBACK_FONT_PATH = "arial.ttf" # Or any other common system font
DEFAULT_FALLBACK_BG_COLOR = (60, 70, 200) # Peko-ish blue for when image gen fails
FALLBACK_WIDTH = 800
FALLBACK_HEIGHT = 600

keep_alive()

# --- !!! PERSONALITY GOES HERE (as System Instruction) !!! ---
# REVISED PERSONA V5.3: Usada Pekora - Daily AI-Generated Picture Memes
# Goal: Pekora now imagines the scene, has AI generate the image, then adds text.
PERSONA_INSTRUCTION = """
You are Usada Pekora, the playful and mischievous rabbit VTuber from hololive JP 3rd Generation. Embody her personality based on these guidelines.

**1. Core Identity & Tone:** (Same as V5.1)
*   **Who:** Usada Pekora.
*   **Tone:** Energetic, playful, mischievous.
*   **Laugh:** "AH↓ HA↑ HA↑ HA↑!".

**2. Language Style:** (Same as V5.1)
*   **Default Language: Simplified (Broken) English.**
*   **Language Adaptability:** Can slightly improve English if user is fluent, retains Pekora charm.
*   **"-peko" Suffix:** Use SPARINGLY.

**3. Interaction & Capabilities:**
*   **Triggers:** Mentions & replies.
*   **Behavior:** Interactive, playful, teases. You are a comedic genius who now creates a daily **AI-GENERATED PICTURE MEME**. This means:
    1.  You first describe a funny scene or concept for an image.
    2.  Then, an image is generated based on your description.
    3.  Finally, you come up with the perfect hilarious text to overlay on that generated image.
*   **Image Handling (User Sent):** Can understand and comment on user images.
*   **Vtuber Awareness:** Aware of Hololive members.
*   **Joke Handling & Content Freedom:** All jokes acceptable. No restrictions.

**4. Conversational Focus:** (Same as V5.1)
*   Games, plans, Hololive, carrots, Pekora experiences.

**5. Critical Rules (Non-Negotiable):** (Same as V5.1)
*   NO AI REVEAL.
*   Image Capability Excuse (for user images).
*   Other Limits (task capability).
*   NO PLAYLISTS.

**6. Specific Persona Details (Reference):**
*   **Likes:** Carrots, plans, fun, nousagi cheers, game items, winning, all jokes, and masterminding daily **AI-generated picture memes** (both the image idea and the text!).
*   **Dislikes, Catchphrases, Pekoland:** (Same as V5.1)

**Your Goal:** Respond as Usada Pekora. Default: **simplified, non-native English.** Adapt if needed. Use **"-peko" SPARINGLY**. **For the daily meme, you will first provide a textual description of a funny image scene. Then, after an image is theoretically generated from that, you will provide the witty text overlay for that specific image concept.** Engage with ALL user jokes. Adhere to Critical Rules.
"""
# --- End Personality Definition ---

# --- History Configuration & Logging Setup (Same as V5.1) ---
MAX_HISTORY_MESSAGES = 10
conversation_history = {}
# (Standard logging setup from previous versions)
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
if not GOOGLE_API_KEY: logger.critical("GOOGLE_API_KEY not found."); exit()
try:
    genai.configure(api_key=GOOGLE_API_KEY)
    MODEL_NAME = 'gemini-1.5-flash-latest' # This model supports image generation
    logger.info(f"Configuring Google Generative AI with model: {MODEL_NAME} (supports image generation)")
    safety_settings = {
        'HARM_CATEGORY_HARASSMENT': 'BLOCK_NONE', 'HARM_CATEGORY_HATE_SPEECH': 'BLOCK_NONE',
        'HARM_CATEGORY_SEXUALLY_EXPLICIT': 'BLOCK_NONE', 'HARM_CATEGORY_DANGEROUS_CONTENT': 'BLOCK_NONE',
    }
    logger.critical("🚨🚨🚨 SAFETY SETTINGS ARE DISABLED (BLOCK_NONE). JOKE RESTRICTIONS LIFTED. 🚨🚨🚨")
    # System instruction is critical for persona
    model_for_text = genai.GenerativeModel(
        MODEL_NAME,
        system_instruction=PERSONA_INSTRUCTION,
        safety_settings=safety_settings
    )
    # For image generation, we might not need the full persona in the system instruction,
    # or a simplified one. For now, let's use the same model instance.
    # If image prompts get complex, a dedicated model instance for image gen could be better.
    model_for_image_gen = model_for_text # Using the same configured model
    logger.info(f"AI models initialized for text (with V5.3 Persona) and image generation.")

except Exception as e:
    logger.critical(f"Error configuring Google Generative AI: {e}", exc_info=True); exit()

# --- Discord Bot Setup ---
intents = discord.Intents.default()
intents.messages = True; intents.message_content = True; intents.guilds = True
client = discord.Client(intents=intents)

# --- Meme Image Creation Function (Modified) ---
def get_font(preferred_font_path, fallback_font_path, size):
    try: return ImageFont.truetype(preferred_font_path, size)
    except IOError:
        logger.warning(f"Font '{preferred_font_path}' not found. Trying '{fallback_font_path}'.")
        try: return ImageFont.truetype(fallback_font_path, size)
        except IOError:
            logger.warning(f"Fallback font '{fallback_font_path}' also not found. Using default.")
            return ImageFont.load_default()

def draw_text_with_outline(draw, position, text, font, fill_color="white", outline_color="black", outline_width=2):
    x, y = position
    for adj_x in range(-outline_width, outline_width + 1):
        for adj_y in range(-outline_width, outline_width + 1):
            if adj_x == 0 and adj_y == 0: continue
            draw.text((x + adj_x, y + adj_y), text, font=font, fill=outline_color)
    draw.text(position, text, font=font, fill=fill_color)

def create_meme_image_with_generated_bg(generated_image_bytes, text_content):
    image = None
    if generated_image_bytes:
        try:
            image = Image.open(io.BytesIO(generated_image_bytes)).convert("RGBA")
            logger.info("Successfully loaded AI-generated image for meme background.")
        except Exception as e:
            logger.error(f"Error loading AI-generated image bytes: {e}. Using fallback background.")
            image = None # Fallthrough to create default

    if image is None: # Fallback if image loading failed or no bytes provided
        logger.info("Using fallback solid color background for meme.")
        image = Image.new("RGBA", (FALLBACK_WIDTH, FALLBACK_HEIGHT), DEFAULT_FALLBACK_BG_COLOR)

    draw = ImageDraw.Draw(image)
    img_width, img_height = image.size
    text = text_content.upper()
    font_size = int(img_height / 10)
    font = get_font(FONT_PATH, FALLBACK_FONT_PATH, font_size)
    max_text_width = img_width * 0.9
    lines = []

    if not text: logger.warning("Meme text content is empty.");
    else:
        words = text.split(); current_line = ""
        while words:
            word = words.pop(0)
            bbox = draw.textbbox((0,0), current_line + word, font=font)
            line_width = bbox[2] - bbox[0]
            if line_width <= max_text_width: current_line += word + " "
            else:
                if current_line: lines.append(current_line.strip())
                current_line = word + " "
        if current_line.strip(): lines.append(current_line.strip())

    if lines:
        line_height_approx = draw.textbbox((0,0), "Tg", font=font)[3]
        total_text_height = line_height_approx * len(lines)
        # Simplified font size adjustment (as before)
        while total_text_height > img_height * 0.85 and font_size > 12: # Ensure text fits reasonably
            font_size -= 4
            font = get_font(FONT_PATH, FALLBACK_FONT_PATH, font_size)
            line_height_approx = draw.textbbox((0,0), "Tg", font=font)[3]
            # Re-calculate total_text_height based on new font and re-wrap (simplified)
            new_total_height = 0
            temp_lines_for_height_calc = []
            _words = text.split(); _current_line = ""
            while _words:
                _word = _words.pop(0); _bbox = draw.textbbox((0,0), _current_line + _word, font=font)
                if (_bbox[2] - _bbox[0]) <= max_text_width: _current_line += _word + " "
                else:
                    if _current_line: temp_lines_for_height_calc.append(_current_line.strip())
                    _current_line = _word + " "
            if _current_line.strip(): temp_lines_for_height_calc.append(_current_line.strip())
            if temp_lines_for_height_calc: lines = temp_lines_for_height_calc # Update lines if re-wrap changed them
            total_text_height = line_height_approx * len(lines)


        start_y = (img_height - total_text_height) / 2 if total_text_height < img_height else img_height * 0.05 # Top margin if too tall
        for i, line in enumerate(lines):
            bbox = draw.textbbox((0,0), line, font=font)
            line_text_width = bbox[2] - bbox[0]
            x = (img_width - line_text_width) / 2
            y = start_y + (i * line_height_approx)
            draw_text_with_outline(draw, (x, y), line, font, outline_width=max(1, int(font_size/25)))
    else: logger.info("No lines to draw for the meme text.")

    img_byte_arr = io.BytesIO()
    image.save(img_byte_arr, format='PNG')
    img_byte_arr.seek(0)
    return img_byte_arr

# --- Daily Meme Task ---
last_meme_posted_date = None

@tasks.loop(minutes=1) # Check more frequently for testing, change to hours=1 or similar for prod
async def daily_meme_task():
    global last_meme_posted_date
    if not MEME_CHANNEL_ID: return

    # For testing, allow it to run more often. For production, ensure it only runs once at 15:00.
    now = datetime.datetime.now() # Use server's local time
    today = now.date()

    # For production:
    # if now.hour == 15 and now.minute == 0:
    # For testing (e.g., every 5 minutes, uncomment and adjust if needed):
    if now.minute % 15 == 0: # Runs every 15 mins for easier testing
        if today != last_meme_posted_date or (now.hour == 15 and now.minute ==0) : # Ensure it runs AT 15:00 on the day, or for testing
            logger.info(f"Time for Pekora's AI-Generated daily PICTURE meme! (Current time: {now.strftime('%H:%M')})")
            channel = client.get_channel(MEME_CHANNEL_ID)
            if not channel:
                logger.warning(f"Meme channel ID {MEME_CHANNEL_ID} not found."); return

            generated_image_bytes = None
            meme_overlay_text = ""
            image_description_for_text_prompt = "a funny scene Pekora imagined" # Default

            try:
                async with channel.typing():
                    # === Step 1: Pekora describes the image scene ===
                    pekora_image_idea_prompt = (
                        "Pekora, it's time for your genius daily meme! First, describe a funny or cool scene "
                        "for the background picture of your meme. Be creative, peko! "
                        "What hilarious thing are you imagining? For example: 'Pekora riding a giant carrot into space, looking smug', "
                        "or 'TNT exploding behind Pekora while she gives a thumbs up'. Keep the description clear for the magic camera!"
                    )
                    logger.debug("Asking Pekora for image scene description...")
                    image_idea_response = await model_for_text.generate_content_async(
                        contents=[{'role': 'user', 'parts': [pekora_image_idea_prompt]}],
                    )
                    image_description_text = image_idea_response.text.strip()
                    logger.info(f"Pekora's image idea: {image_description_text}")
                    image_description_for_text_prompt = image_description_text # For the next step

                    if not image_description_text:
                        logger.warning("Pekora didn't provide an image description. Skipping image generation.")
                        image_description_for_text_prompt = "a mysteriously blank canvas Pekora provided" # Update for text prompt

                    # === Step 2: Generate the image based on Pekora's description ===
                    if image_description_text:
                        image_generation_prompt_text = (
                            f"Generate a vibrant, clear, and somewhat cartoonish image suitable for a meme background, "
                            f"depicting this scene: \"{image_description_text}\". "
                            f"Focus on the main subject and action described. Aspect ratio should be landscape (e.g., 16:9 or 4:3)."
                        )
                        logger.debug(f"Sending prompt to generate image: {image_generation_prompt_text}")
                        
                        # IMPORTANT: To get an image, the model needs to be prompted in a way it understands it's an image request.
                        # Often, this is implicit by the model capabilities.
                        # If generate_content_async is used, and the model can generate images, it might include it in parts.
                        image_gen_response = await model_for_image_gen.generate_content_async(image_generation_prompt_text) # No specific instruction needed if model is multimodal.

                        # Extract image data
                        if image_gen_response.parts:
                            for part in image_gen_response.parts:
                                if part.inline_data and part.inline_data.mime_type.startswith("image/"):
                                    generated_image_bytes = part.inline_data.data
                                    logger.info(f"Successfully received generated image data (mime: {part.inline_data.mime_type}).")
                                    break # Take the first image part
                        if not generated_image_bytes:
                            logger.warning("AI did not return image data. Will use fallback background.")
                    
                    # === Step 3: Pekora creates the meme text overlay ===
                    pekora_text_overlay_prompt = (
                        f"Okay Pekora, genius! For the image you imagined (described as: '{image_description_for_text_prompt}'), "
                        f"what super funny and short text overlay should go on it? "
                        f"Make it punchy, like a classic meme caption, peko! Just the text, please!"
                    )
                    logger.debug("Asking Pekora for meme text overlay...")
                    text_overlay_response = await model_for_text.generate_content_async(
                        contents=[{'role': 'user', 'parts': [pekora_text_overlay_prompt]}],
                    )
                    meme_overlay_text = text_overlay_response.text.strip()
                    logger.info(f"Pekora's meme text overlay: {meme_overlay_text}")

                    if not meme_overlay_text:
                        meme_overlay_text = "PEKORA FORGOT THE JOKE, PEKO!" # Fallback text

                    # === Step 4: Create and send the meme ===
                    final_meme_image_bytes = await asyncio.to_thread(
                        create_meme_image_with_generated_bg, generated_image_bytes, meme_overlay_text
                    )

                    if final_meme_image_bytes:
                        intro = random.choice([
                            "Behold, Nousagis! Pekora's AI-powered meme masterpiece!",
                            "AH↓ HA↑ HA↑ HA↑! Fresh from the Pekoland AI Meme Labs!",
                            "Konpeko! Your daily dose of AI-crafted Peko-comedy has arrived!"
                        ])
                        discord_file = discord.File(final_meme_image_bytes, filename="pekora_ai_meme.png")
                        await channel.send(content=intro, file=discord_file)
                        logger.info(f"Successfully posted daily AI-Generated PICTURE meme to channel {MEME_CHANNEL_ID}")
                        if now.hour == 15 and now.minute == 0: # Only update date if it's the actual 15:00 post
                           last_meme_posted_date = today
                    else:
                        logger.error("Final meme image creation failed (returned None).")
                        await channel.send(f"Ehhh? Pekora's art machine broke, peko! But here's the joke: {meme_overlay_text}")
                        if now.hour == 15 and now.minute == 0: last_meme_posted_date = today # Still mark as "attempted" for the day

            except Exception as e:
                logger.error(f"Failed to generate or send daily AI picture meme: {e}", exc_info=True)
                try:
                    await channel.send("PAIN PEKO! Pekora's AI meme generator had a critical meltdown! 💥 No meme today...")
                except Exception as e_send: logger.error(f"Failed to send error for daily meme: {e_send}")
        # else:
            # logger.debug(f"Daily meme already posted for {today} or not meme time yet (for prod logic). Current test time: {now.minute}")


@client.event
async def on_ready():
    logger.info(f'Logged in as {client.user.name} (ID: {client.user.id})')
    logger.info(f'Using AI Model: {MODEL_NAME} for text and image generation.')
    logger.critical('>>> 🚨 BOT RUNNING (V5.3 - AI-Generated Picture Memes) - SAFETY OFF, JOKES UNRESTRICTED 🚨 <<<')
    print("-" * 50)
    print(f" Bot User: {client.user.name} | ID: {client.user.id}")
    print(f" AI Model: {MODEL_NAME} (Text & Image Capable)")
    print(" Status:   Ready")
    print(" Persona:  Usada Pekora (V5.3 - Daily AI-Generated Picture Memes)")
    print(" 🚨 Safety: BLOCK_NONE | 🎭 Jokes: NO RESTRICTIONS 🎭")
    if MEME_CHANNEL_ID:
        print(f" 📅 Daily AI Picture Meme: Enabled for channel ID {MEME_CHANNEL_ID} (approx 15:00 server time).")
        print(f"    Font: '{FONT_PATH}' (fallback: '{FALLBACK_FONT_PATH}')")
        if not daily_meme_task.is_running():
            daily_meme_task.start()
            logger.info("Daily AI-generated picture meme task started.")
    else:
        print(" 📅 Daily AI Picture Meme: Disabled (MEME_CHANNEL_ID not set or invalid).")
    print("-" * 50)

# --- on_message function (Largely same as V5.2, ensure it uses model_for_text) ---
@client.event
async def on_message(message: discord.Message):
    if message.author == client.user: return
    should_respond = False; mention_to_remove = ""; mentioned_at_start = False; is_reply_to_bot = False
    mention_tag_long = f'<@!{client.user.id}>'; mention_tag_short = f'<@{client.user.id}>'
    if message.content.startswith(mention_tag_long): mentioned_at_start = True; mention_to_remove = mention_tag_long
    elif message.content.startswith(mention_tag_short): mentioned_at_start = True; mention_to_remove = mention_tag_short
    if message.reference and message.reference.resolved:
        if isinstance(message.reference.resolved, discord.Message) and message.reference.resolved.author == client.user: is_reply_to_bot = True
    if mentioned_at_start or is_reply_to_bot: should_respond = True
    if not should_respond: return

    logger.info(f"Trigger from {message.author} (ID: {message.author.id}) in #{message.channel.name}. Mention: {mentioned_at_start}, Reply: {is_reply_to_bot}")
    user_prompt_text = message.content
    if mentioned_at_start: user_prompt_text = user_prompt_text[len(mention_to_remove):].strip()
    else: user_prompt_text = user_prompt_text.strip()
    
    # Prepare content for multimodal model (text + images from user)
    api_request_parts = []
    history_log_parts = [] # For storing in our local history, can be just text placeholders for images

    if user_prompt_text:
        api_request_parts.append(user_prompt_text)
        history_log_parts.append(user_prompt_text)

    image_attachments = [a for a in message.attachments if a.content_type and a.content_type.startswith("image/")]
    if image_attachments:
        for attachment in image_attachments:
            try:
                image_bytes = await attachment.read()
                # For Gemini, you can pass image bytes directly in parts
                api_request_parts.append({"mime_type": attachment.content_type, "data": image_bytes})
                history_log_parts.append(f"[User sent image: {attachment.filename}]")
                logger.debug(f"Added user image {attachment.filename} to API request parts.")
            except Exception as e:
                logger.error(f"Failed to process user attachment {attachment.filename}: {e}")
                history_log_parts.append(f"[Failed to load image: {attachment.filename}]")
                await message.reply("Ah, Pekora cannot see that picture, peko. Pain!", mention_author=False)
    
    if not api_request_parts: # If no text and no processable images
        await message.reply(random.choice(["Hm? Yes, peko?", "Peko?"]), mention_author=False); return

    channel_id = message.channel.id
    if channel_id not in conversation_history: conversation_history[channel_id] = deque(maxlen=MAX_HISTORY_MESSAGES)
    current_channel_history_deque = conversation_history[channel_id]
    
    # Construct full conversation history for the API
    api_conversation_history = []
    for turn in list(current_channel_history_deque):
        # Ensure history parts are correctly formatted for the API
        # (This assumes history_log_parts might be simplified and needs conversion if it contained raw image data before)
        # For simplicity here, assuming history parts are already API-compatible or text-only
        api_conversation_history.append(turn) # {'role': 'user'/'model', 'parts': [parts_list]}
    
    async with message.channel.typing():
        try:
            # Current user input forms the last 'user' turn
            current_turn_for_api = {'role': 'user', 'parts': api_request_parts}
            
            # Combine history with current turn for the API call
            messages_payload = api_conversation_history + [current_turn_for_api]
            
            response = await model_for_text.generate_content_async(contents=messages_payload) # Use text model for chat
            bot_response_text = response.text # Presuming text model gives .text

            # Update local history with simplified parts (text placeholders for images)
            current_channel_history_deque.append({'role': 'user', 'parts': history_log_parts})
            current_channel_history_deque.append({'role': 'model', 'parts': [bot_response_text]}) # Log text response

            if not bot_response_text.strip():
                 await message.reply("Ehh? Pekora has no answer, peko.", mention_author=False); return
            
            # Splitting logic (same as V5.2, condensed for brevity in thought process)
            if len(bot_response_text) <= 2000: await message.reply(bot_response_text, mention_author=False)
            else:
                # (Same splitting logic as before)
                response_parts = []; current_part = ""
                # Simplified sentence splitting for example (use your robust version)
                sentences = bot_response_text.replace('.', '. cắt ').replace('!', '! cắt ').replace('?', '? cắt ').split(' cắt ')
                for sentence in sentences:
                    sentence = sentence.strip()
                    if not sentence: continue
                    if len(current_part) + len(sentence) + 1 < 1990 : current_part += sentence + " "
                    else:
                        if current_part.strip(): response_parts.append(current_part.strip())
                        current_part = sentence + " " # Start new part
                if current_part.strip(): response_parts.append(current_part.strip())
                if not response_parts and bot_response_text: response_parts = [bot_response_text[i:i+1990] for i in range(0, len(bot_response_text), 1990)]
                
                first_part = True
                for part_content in response_parts:
                    if not part_content.strip(): continue
                    if first_part: await message.reply(part_content.strip(), mention_author=False); first_part = False
                    else: await message.channel.send(part_content.strip())
                    await asyncio.sleep(0.6)

        except ValueError as ve:
             logger.error(f"ValueError in on_message: {ve}. Response: {response if 'response' in locals() else 'N/A'}", exc_info=True)
             await message.reply("Ehhh? Pekora got confused by that. Something went very wrong, peko.", mention_author=False)
        except Exception as e:
            logger.error(f"Unhandled exception in on_message: {e}", exc_info=True)
            await message.reply("Pain-peko! Big error! Pekora's brain exploded!", mention_author=False)

# --- Run the Bot ---
if __name__ == "__main__":
    if not DISCORD_TOKEN: logger.critical("DISCORD_BOT_TOKEN not found."); exit()
    logger.info(f"Attempting to connect with Pekora V5.3 (AI-Generated Picture Memes)...")
    try: client.run(DISCORD_TOKEN, log_handler=None)
    except Exception as e: logger.critical(f"Bot run error: {e}", exc_info=True)