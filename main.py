import os
import asyncio
import traceback
import discord
from discord import app_commands
from discord.ext import commands
from google import genai
from google.genai import types

DISCORD_TOKEN = os.getenv("TOKEN")
GEMINI_KEY = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")

# 0 — отвечать везде, либо ID нужного канала
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
# КОМАНДА: /слышь
# ================================
@bot.tree.command(name="слышь", description="Пояснить за вопрос")
@app_commands.describe(базар="Чё хотел?")
async def hear_me_out(interaction: discord.Interaction, базар: str):
    if ALLOWED_CHANNEL_ID != 0 and interaction.channel_id != ALLOWED_CHANNEL_ID:
        await interaction.response.send_message(
            f"🚫 Не спамь тут. Иди в <#{ALLOWED_CHANNEL_ID}> и там возникай.", 
            ephemeral=True
        )
        return

    await interaction.response.defer(thinking=True)

    if not gemini_client:
        await interaction.followup.send("❌ GEMINI_API_KEY потерялся где-то на хостинге.")
        return

    loop = asyncio.get_running_loop()
    response = None
    last_error = ""

    # До 3 попыток на актуальной gemini-3.6-flash
    for attempt in range(3):
        try:
            response = await loop.run_in_executor(
                None,
                lambda: gemini_client.models.generate_content(
                    model="gemini-3.6-flash",
                    contents=базар,
                    config=types.GenerateContentConfig(
                        system_instruction=SYSTEM_PROMPT
                    )
                )
            )
            if response and response.text:
                break
        except Exception as e:
            last_error = str(e)
            print(f"Попытка {attempt + 1}: {last_error}")
            if "503" in last_error or "429" in last_error:
                await asyncio.sleep(2)
                continue
            else:
                break

    if response and response.text:
        answer = response.text
        if len(answer) <= 1900:
            await interaction.followup.send(f"**Ты выдал:** {базар}\n\n{answer}")
        else:
            await interaction.followup.send(f"**Ты выдал:** {базар}\n\n{answer[:1900]}")
            for i in range(1900, len(answer), 1900):
                await interaction.channel.send(answer[i:i+1900])
        return

    if "503" in last_error:
        await interaction.followup.send("🤖💤 Серваки у гугла в мыле. Отвали на пару минут.")
    elif "429" in last_error:
        await interaction.followup.send("⏳ Слишком резво строчишь, притормози.")
    else:
        await interaction.followup.send(f"⚠️ Чёт пошло не так:\n```{last_error[:1800]}```")

bot.run(DISCORD_TOKEN)
