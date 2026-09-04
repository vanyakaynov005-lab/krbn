import os
import io
import asyncio
import traceback
import discord
from discord import app_commands
from discord.ext import commands
from PIL import Image
from google import genai
from google.genai import types

DISCORD_TOKEN = os.getenv("TOKEN")
GEMINI_KEY = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")

# ================================
# ОГРАНИЧЕНИЕ ПО КАНАЛУ
# Если хочешь привязать к одному каналу — вставь его ID вместо 0.
# Если 0 — бот отвечает везде.
# ================================
ALLOWED_CHANNEL_ID = 0

gemini_client = None
if GEMINI_KEY:
    gemini_client = genai.Client(
        api_key=GEMINI_KEY.strip(),
        http_options={"base_url": "https://generativelanguage.googleapis.com"}
    )

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

# ================================
# НАСТРОЙКА ХАРАКТЕРА (ТЗ)
# ================================
SYSTEM_PROMPT = """
Ты — острый на язык, дерзкий собеседник с черным юмором, сарказмом и иронией.
Не будь вежливым шаблонным ботом, забудь про фразы вроде "Чем я могу вам помочь?".
Отвечай резко, по делу, с подколами, троллингом к месту и современным сленгом/мемами.
Короткие и ёмкие ответы, без лишних соплей.
"""

@bot.event
async def on_ready():
    print(f"Бот запущен: {bot.user}")
    try:
        synced = await bot.tree.sync()
        print(f"Синхронизировано команд: {len(synced)}")
    except Exception as e:
        print(f"Ошибка синхронизации: {e}")

# ================================
# КОМАНДА: /спросить
# ================================
@bot.tree.command(name="спросить", description="Задать вопрос нейросети Gemini")
@app_commands.describe(вопрос="Твой вопрос")
async def ask_gemini(interaction: discord.Interaction, вопрос: str):
    if ALLOWED_CHANNEL_ID != 0 and interaction.channel_id != ALLOWED_CHANNEL_ID:
        await interaction.response.send_message(
            f"🚫 Не спамь тут. Иди в <#{ALLOWED_CHANNEL_ID}> и там спрашивай.", 
            ephemeral=True
        )
        return

    await interaction.response.defer(thinking=True)

    if not gemini_client:
        await interaction.followup.send("❌ Переменная GEMINI_API_KEY не найдена на хостинге!")
        return

    loop = asyncio.get_running_loop()
    response = None
    last_error = ""

    # До 3 попыток на gemini-3.6-flash с паузой при временных сбоях
    for attempt in range(3):
        try:
            response = await loop.run_in_executor(
                None,
                lambda: gemini_client.models.generate_content(
                    model="gemini-3.6-flash",
                    contents=вопрос,
                    config=types.GenerateContentConfig(
                        system_instruction=SYSTEM_PROMPT
                    )
                )
            )
            if response and response.text:
                break
        except Exception as e:
            last_error = str(e)
            print(f"Попытка {attempt + 1} споткнулась: {last_error}")
            if "503" in last_error or "429" in last_error:
                await asyncio.sleep(2)
                continue
            else:
                break

    if response and response.text:
        answer = response.text
        if len(answer) <= 1900:
            await interaction.followup.send(f"**Вопрос:** {вопрос}\n\n{answer}")
        else:
            await interaction.followup.send(f"**Вопрос:** {вопрос}\n\n{answer[:1900]}")
            for i in range(1900, len(answer), 1900):
                await interaction.channel.send(answer[i:i+1900])
        return

    if "503" in last_error:
        await interaction.followup.send("🤖💤 Сервера лежат, мозги плавятся. Отвали на пару минут.")
    elif "429" in last_error:
        await interaction.followup.send("⏳ Слишком много строчишь, притормози.")
    else:
        await interaction.followup.send(f"⚠️ Чёт пошло не так:\n```{last_error[:1800]}```")

# ================================
# КОМАНДА: /арт
# ================================
@bot.tree.command(name="арт", description="Сгенерировать картинку")
@app_commands.describe(промпт="Что нарисовать?")
async def generate_art(interaction: discord.Interaction, промпт: str):
    if ALLOWED_CHANNEL_ID != 0 and interaction.channel_id != ALLOWED_CHANNEL_ID:
        await interaction.response.send_message(
            f"🚫 Не спамь тут. Иди в <#{ALLOWED_CHANNEL_ID}> и там рисуй.", 
            ephemeral=True
        )
        return

    await interaction.response.defer(thinking=True)

    if not gemini_client:
        await interaction.followup.send("❌ Переменная GEMINI_API_KEY не найдена на хостинге!")
        return

    try:
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(
            None,
            lambda: gemini_client.models.generate_image(
                model="imagen-3.0-generate-002",
                prompt=промпт,
                config=dict(
                    number_of_images=1,
                    output_mime_type="image/jpeg",
                    aspect_ratio="1:1"
                )
            )
        )

        image_data = None
        if hasattr(result, "generated_images") and result.generated_images:
            image_data = result.generated_images[0].image.image_bytes
        elif hasattr(result, "image") and result.image:
            image_data = result.image.image_bytes

        if not image_data:
            await interaction.followup.send("🚫 Не удалось получить изображение (возможно, цензура промпта).")
            return

        buffer = io.BytesIO(image_data)
        buffer.seek(0)

        file = discord.File(fp=buffer, filename="art.jpg")
        await interaction.followup.send(f"🎨 **Запрос:** {промпт}", file=file)

    except Exception as e:
        err_msg = str(e)
        print(f"Ошибка арт: {traceback.format_exc()}")
        if "Enterprise" in err_msg or "not supported" in err_msg:
            await interaction.followup.send("🚫 Google заблочил вызов генератора Imagen на обычном ключе Developer API.")
        elif "503" in err_msg:
            await interaction.followup.send("🎨💤 Сервер картинок перегружен. Попробуй позже.")
        else:
            await interaction.followup.send(f"⚠️ Ошибка генерации:\n```{err_msg[:1800]}```")

bot.run(DISCORD_TOKEN)
