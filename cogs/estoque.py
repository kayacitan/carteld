import discord
from discord import ui, app_commands
from discord.ext import commands
import traceback
from database import Database
from utils.emojis import STORE, X, PACKAGE, LIST, TOOL, SHIRT, TICKET

PRODUTOS = {
    "masterpick": {"nome": "Masterpick", "emoji": TOOL},
    "camisa_forca": {"nome": "Camisa de Força", "emoji": SHIRT},
    "ticket_corrida": {"nome": "Ticket de Corrida", "emoji": TICKET},
}


class EstoqueView(ui.LayoutView):
    def __init__(self, guild: discord.Guild, dados: dict):
        super().__init__()

        container = ui.Container()
        container.add_item(ui.TextDisplay(f"# {LIST} {PACKAGE} Estoque do Servidor"))
        container.add_item(ui.Separator(spacing=discord.SeparatorSpacing.small))

        for produto_id, info in PRODUTOS.items():
            qtd, res, disp = dados.get(produto_id, (0, 0, 0))
            container.add_item(ui.TextDisplay(
                f"## {info['emoji']} {info['nome']}\n"
                f"• **Total:** {qtd}\n"
                f"• **Reservado (encomendas):** {res}\n"
                f"• **Disponível:** {disp}"
            ))
            container.add_item(ui.Separator(spacing=discord.SeparatorSpacing.small))

        self.add_item(container)


class EstoqueCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = Database()
        print("Cog de Estoque carregado com sucesso!")

    @app_commands.command(name="estoque", description="Consultar o estoque atual de produtos")
    async def estoque(self, interaction: discord.Interaction):
        try:
            if not interaction.guild:
                await interaction.response.send_message(f"{X} Este comando só funciona em servidor.", ephemeral=True)
                return

            dados = {}
            for produto_id in PRODUTOS.keys():
                dados[produto_id] = await self.db.get_estoque_produto(interaction.guild.id, produto_id)

            view = EstoqueView(interaction.guild, dados)
            await interaction.response.send_message(view=view, ephemeral=True)

        except Exception as e:
            print(f"Erro no comando /estoque: {e}")
            traceback.print_exc()
            try:
                await interaction.response.send_message(f"{X} Erro ao consultar estoque.", ephemeral=True)
            except:
                pass


async def setup(bot: commands.Bot):
    cog = EstoqueCog(bot)
    await cog.db.init_db()
    await bot.add_cog(cog)
