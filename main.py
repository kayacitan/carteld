import discord
import asyncio
import os
import itertools
from discord.ext import commands, tasks
from dotenv import load_dotenv

load_dotenv()

intents = discord.Intents.all()
bot = commands.Bot(command_prefix='!', intents=intents)

# 🔁 Ciclo de status (SÓ TEXTO)
status_cycle = itertools.cycle([
    discord.Game("Estoy cansado jefe... 😴"),
    discord.Game("Ninguém trabalha aqui! 🚫"),
])

# 🔁 Loop que troca o TEXTO mantendo AUSENTE
@tasks.loop(seconds=60)
async def rotate_status():
    activity = next(status_cycle)
    await bot.change_presence(
        status=discord.Status.idle,  # sempre ausente
        activity=activity
    )


@bot.event
async def on_ready():
    print(f'Bot conectado como {bot.user}')

    # inicia o loop UMA vez
    if not rotate_status.is_running():
        rotate_status.start()

    try:
        synced = await bot.tree.sync()
        print(f'{len(synced)} comando(s) sincronizado(s)')
    except Exception as e:
        print(f'Erro ao sincronizar comandos: {e}')


COGS = [
    'cogs.boasvindas',
    'cogs.registro',
    'cogs.fabricacao',
    'cogs.config',
    'cogs.meta',
    'cogs.vendas',
    'cogs.banco',
    'cogs.estoque',
    'cogs.dashboard',
    'cogs.emojis',
    'cogs.farm',
]


async def load_extensions():
    for cog in COGS:
        await bot.load_extension(cog)
    print('Cogs carregados')


async def main():
    async with bot:
        await load_extensions()
        await bot.start(os.getenv('DISCORD_TOKEN'))


if __name__ == '__main__':
    asyncio.run(main())
