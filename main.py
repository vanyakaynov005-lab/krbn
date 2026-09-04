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

# Инициализируем клиент
gemini_client = None
if GEMINI_KEY:
    gemini_client = genai.Client(api_key=GEMINI_KEY.strip())

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f"Бот запущен: {bot.user}")
    try:
        synced = await bot.tree.sync()
        print(f"Синхронизировано команд: {len(synced)}")
    except Exception as e:
        print(f"Ошибка синхронизации: {e}")

@bot.tree.command(name="спросить", description="Задать вопрос нейросети Gemini")
@app_commands.describe(вопрос="Твой вопрос")
async def ask_gemini(interaction: discord.Interaction, вопрос: str):
    await interaction.response.defer()

    if not gemini_client:
        await interaction.followup.send("❌ Переменная GEMINI_API_KEY не найдена на хостинге!")
        return

    try:
        loop = asyncio.get_running_loop()
        response = await loop.run_in_executor(
            None,
            lambda: gemini_client.models.generate_content(
                model="gemini-2.5-flash",
                contents=вопрос
            )
        )
        answer = response.text or "Ответ пустой"

        if len(answer) <= 1900:
            await interaction.followup.send(f"**Вопрос:** {вопрос}\n\n{answer}")
        else:
            await interaction.followup.send(f"**Вопрос:** {вопрос}\n\n{answer[:1900]}")
            for i in range(1900, len(answer), 1900):
                await interaction.channel.send(answer[i:i+1900])

    except Exception as e:
        err_msg = str(e)
        print(f"Ошибка: {traceback.format_exc()}")
        await interaction.followup.send(f"❌ Ошибка от Google API:\n```{err_msg[:1800]}```")

@bot.tree.command(name="арт", description="Сгенерировать картинку")
@app_commands.describe(промпт="Что нарисовать?")
async def generate_art(interaction: discord.Interaction, промпт: str):
    await interaction.response.defer()

    if not gemini_client:
        await interaction.followup.send("❌ Переменная GEMINI_API_KEY не найдена на хостинге!")
        return

    try:
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(
            None,
            lambda: gemini_client.models.generate_images(
                model="imagen-3.0-generate-002",
                prompt=промпт,
                config=types.GenerateImagesConfig(
                    number_of_images=1,
                    aspect_ratio="1:1"
                )
            )
        )

        if not result.generated_images:
            await interaction.followup.send("❌ Не удалось получить картинку (фильтр безопасности).")
            return

        img_bytes = result.generated_images[0].image.image_bytes
        img = Image.open(io.BytesIO(img_bytes))

        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        buffer.seek(0)

        file = discord.File(fp=buffer, filename="art.png")
        await interaction.followup.send(f"🎨 **Запрос:** {промпт}", file=file)

    except Exception as e:
        err_msg = str(e)
        print(f"Ошибка арт: {traceback.format_exc()}")
        await interaction.followup.send(f"❌ Ошибка Imagen:\n```{err_msg[:1800]}```")

bot.run(DISCORD_TOKEN)
)
