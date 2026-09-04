import os
import io
import asyncio
import discord
from discord import app_commands
from discord.ext import commands
from PIL import Image
from google import genai
from google.genai import types

# Читаем ключи из переменных хостинга (в коде секретов НЕТ)
DISCORD_TOKEN = os.getenv("TOKEN")
GEMINI_KEY = os.getenv("GEMINI_API_KEY")

if not DISCORD_TOKEN or not GEMINI_KEY:
    print("ОШИБКА: Не заданы переменные TOKEN или GEMINI_API_KEY на хостинге!")

# Инициализируем клиент Google GenAI
gemini_client = genai.Client(api_key=GEMINI_KEY)

# Базовые настройки Discord
intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f"Бот успешно ожил: {bot.user}")
    try:
        # Регаем слэш-команды в Discord
        synced = await bot.tree.sync()
        print(f"Синхронизировано команд: {len(synced)}")
    except Exception as e:
        print(f"Ошибка синхронизации слэш-команд: {e}")

# ================================
# КОМАНДА: /спросить
# ================================
@bot.tree.command(name="спросить", description="Задать вопрос нейросети Gemini")
@app_commands.describe(вопрос="Твой вопрос для ИИ")
async def ask_gemini(interaction: discord.Interaction, вопрос: str):
    # Говорим Дискорду, что думаем (чтобы не упал по таймауту 3 сек)
    await interaction.response.defer()

    try:
        loop = asyncio.get_running_loop()
        response = await loop.run_in_executor(
            None,
            lambda: gemini_client.models.generate_content(
                model="gemini-2.5-flash",
                contents=вопрос
            )
        )
        answer = response.text

        # Лимит одного сообщения в Дискорде — 2000 символов
        if len(answer) <= 1900:
            await interaction.followup.send(f"**Вопрос:** {вопрос}\n\n{answer}")
        else:
            # Если ответ гигантский — бьем на части
            await interaction.followup.send(f"**Вопрос:** {вопрос}\n\n{answer[:1900]}")
            for i in range(1900, len(answer), 1900):
                await interaction.channel.send(answer[i:i+1900])

    except Exception as e:
        print(f"Ошибка генерации текста: {e}")
        await interaction.followup.send("❌ Не вышло сгенерировать ответ. Чекни логи на хостинге.")

# ================================
# КОМАНДА: /арт
# ================================
@bot.tree.command(name="арт", description="Сгенерировать картинку")
@app_commands.describe(промпт="Что нарисовать?")
async def generate_art(interaction: discord.Interaction, промпт: str):
    await interaction.response.defer()

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
            await interaction.followup.send("❌ Картинку сгенерировать не удалось (возможно, сработал цензор).")
            return

        # Достаем картинку и пакуем в буфер памяти
        img_bytes = result.generated_images[0].image.image_bytes
        img = Image.open(io.BytesIO(img_bytes))

        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        buffer.seek(0)

        file = discord.File(fp=buffer, filename="art.png")
        await interaction.followup.send(f"🎨 **Запрос:** {промпт}", file=file)

    except Exception as e:
        print(f"Ошибка генерации арта: {e}")
        await interaction.followup.send("❌ Ошибка при создании картинки. Глянь логи.")

# Запуск бота
bot.run(DISCORD_TOKEN)
