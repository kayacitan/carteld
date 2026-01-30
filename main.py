import discord
import asyncio
import os
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()

intents = discord.Intents.all()
bot = commands.Bot(command_prefix='!', intents=intents)


@bot.event
async def on_ready():
    print(f'Bot conectado como {bot.user}')
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
