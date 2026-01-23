import discord
import asyncio
from discord import ui, app_commands
from discord.ext import commands


class Welcome(ui.LayoutView):
    def __init__(self):
        super().__init__()

        self.cargo_id = 1365523570570297414

        container = discord.ui.Container(ui.TextDisplay('# Bem-vindo(a) ao Servidor!'))
        container.add_item(ui.Separator(spacing=discord.SeparatorSpacing.small))
        container.accent_color = discord.Colour.dark_blue()

        galeria_wc = ui.MediaGallery()
        galeria_wc.add_item(media='https://media.discordapp.net/attachments/1457125599272374372/1457438138288050237/testar_separador.png?ex=695c008a&is=695aaf0a&hm=6bc044ed3f11d9087a87bc2f0dcea4828f1ef2a967fea1daa250bdd66e8124a5&=&format=webp&quality=lossless&width=1872&height=148')
        container.add_item(galeria_wc)
        container.add_item(ui.Separator(spacing=discord.SeparatorSpacing.small))


        botaowelcome = ui.Button(label='Novo Membro')
        botaowelcome.callback = self.botaowelcome

        linha = ui.ActionRow(botaowelcome)
        container.add_item(linha)

        self.add_item(container)
    
    async def botaowelcome(self, interaction: discord.Interaction):
        cargo = interaction.guild.get_role(1374858229393264710)

        if cargo is None:
            await interaction.response.send_message('Cargo não encontrado', ephemeral=True)
            return

        if cargo in interaction.user.roles:
            await interaction.response.send_message('Você já possui esse cargo', ephemeral=True)
            return

        await interaction.user.add_roles(cargo)
        await interaction.response.send_message('Bem vindo"Agora você pode acessar os canais.', ephemeral=True)

class BoasVindasCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name='boasvindas', description='Envia o painel')
    @app_commands.checks.has_permissions(administrator=True)
    async def painel(self, interaction: discord.Interaction):
        layout = Welcome()
        await interaction.response.send_message(view=layout)

    @painel.error
    async def painel_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message('Você não tem permissão para usar este comando!', ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(BoasVindasCog(bot))