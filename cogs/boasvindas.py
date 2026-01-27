import discord
from discord import ui, app_commands
from discord.ext import commands
from database import Database
import traceback


class Welcome(ui.LayoutView):
    def __init__(self, db: Database):
        super().__init__()
        self.db = db

        container = discord.ui.Container(ui.TextDisplay('# Bem-vindo(a) ao Servidor!'))
        container.add_item(ui.Separator(spacing=discord.SeparatorSpacing.small))

        galeria_wc = ui.MediaGallery()
        galeria_wc.add_item(media='https://media.discordapp.net/attachments/1366148719967211612/1465503657452765286/Cartel.png?ex=69795823&is=697806a3&hm=6d37d5b02ab93b40bb31234a9b2518a68222014a0eb9472be730b8b1c5990561&=&format=webp&quality=lossless')
        container.add_item(galeria_wc)

        botaowelcome = ui.Button(label='Novo Membro')
        botaowelcome.callback = self.botaowelcome

        linha = ui.ActionRow(botaowelcome)
        container.add_item(linha)

        self.add_item(container)
    
    async def botaowelcome(self, interaction: discord.Interaction):
        try:
            cargo_membro_id, _ = await self.db.get_cargos_boasvindas(interaction.guild.id)
            if not cargo_membro_id:
                await interaction.response.send_message(
                    'Cargo de membro não configurado. Use /config para definir.',
                    ephemeral=True
                )
                return

            cargo = interaction.guild.get_role(int(cargo_membro_id))

            if cargo is None:
                await interaction.response.send_message('Cargo não encontrado', ephemeral=True)
                return

            if cargo in interaction.user.roles:
                await interaction.response.send_message('Você já possui esse cargo', ephemeral=True)
                return

            await interaction.user.add_roles(cargo)
            await interaction.response.send_message('Bem vindo! Agora você pode acessar os canais.', ephemeral=True)
        except Exception as e:
            print(f"Erro no boas-vindas: {e}")
            traceback.print_exc()
            await interaction.response.send_message('Erro ao processar. Tente novamente.', ephemeral=True)

class BoasVindasCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.db = Database()

    @app_commands.command(name='boasvindas', description='Envia o painel')
    @app_commands.checks.has_permissions(administrator=True)
    async def painel(self, interaction: discord.Interaction):
        layout = Welcome(self.db)
        await interaction.response.send_message(view=layout)

    @painel.error
    async def painel_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message('Você não tem permissão para usar este comando!', ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(BoasVindasCog(bot))
