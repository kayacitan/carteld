import discord
from discord import ui, app_commands
from discord.ext import commands
import traceback
from database import Database


class ConfigView(ui.LayoutView):
    def __init__(self, db: Database):
        super().__init__()
        self.db = db

        container = ui.Container()
        container.add_item(ui.TextDisplay("# ⚙️ Configuração do Bot"))
        container.add_item(ui.Separator(spacing=discord.SeparatorSpacing.small))
        container.add_item(ui.TextDisplay("Selecione canais e cargos abaixo."))
        container.add_item(ui.Separator(spacing=discord.SeparatorSpacing.small))

        # Canal de logs (fabricação/vendas/encomendas/banco)
        self.sel_canal_logs = ui.ChannelSelect(
            placeholder="📢 Selecionar canal de logs (geral)",
            channel_types=[discord.ChannelType.text],
            min_values=1,
            max_values=1
        )
        self.sel_canal_logs.callback = self._set_canal_logs
        container.add_item(ui.ActionRow(self.sel_canal_logs))

        # Canal log metas (mantendo teu sistema meta)
        self.sel_canal_meta = ui.ChannelSelect(
            placeholder="🏁 Selecionar canal de logs (meta)",
            channel_types=[discord.ChannelType.text],
            min_values=1,
            max_values=1
        )
        self.sel_canal_meta.callback = self._set_canal_meta
        container.add_item(ui.ActionRow(self.sel_canal_meta))

        container.add_item(ui.Separator(spacing=discord.SeparatorSpacing.small))
        container.add_item(ui.TextDisplay("## Cargos do sistema"))

        # Cargo gerente (já existia no meta/config)
        self.sel_cargo_gerente = ui.RoleSelect(
            placeholder="👑 Selecionar cargo de gerente",
            min_values=1,
            max_values=1
        )
        self.sel_cargo_gerente.callback = self._set_cargo_gerente
        container.add_item(ui.ActionRow(self.sel_cargo_gerente))

        # Cargo meta paga
        self.sel_cargo_meta = ui.RoleSelect(
            placeholder="✅ Selecionar cargo de meta paga",
            min_values=1,
            max_values=1
        )
        self.sel_cargo_meta.callback = self._set_cargo_meta
        container.add_item(ui.ActionRow(self.sel_cargo_meta))

        # Novo: cargo vendedor
        self.sel_cargo_vendedor = ui.RoleSelect(
            placeholder="💰 Selecionar cargo de vendedor",
            min_values=1,
            max_values=1
        )
        self.sel_cargo_vendedor.callback = self._set_cargo_vendedor
        container.add_item(ui.ActionRow(self.sel_cargo_vendedor))

        self.sel_cargo_fabricante = ui.RoleSelect(
            placeholder="🏭 Selecionar cargo de fabricante",
            min_values=1,
            max_values=1
        )
        self.sel_cargo_fabricante.callback = self._set_cargo_fabricante
        container.add_item(ui.ActionRow(self.sel_cargo_fabricante))

        container.accent_color = discord.Colour.blurple()
        self.add_item(container)

    async def _set_canal_logs(self, interaction: discord.Interaction):
        try:
            canal = self.sel_canal_logs.values[0]
            ok = await self.db.set_canal_log(interaction.guild.id, canal.id)
            await interaction.response.send_message(
                "✅ Canal de logs atualizado!" if ok else "❌ Erro ao salvar canal de logs.",
                ephemeral=True
            )
        except Exception as e:
            print(f"Erro config canal logs: {e}")
            traceback.print_exc()
            await interaction.response.send_message("❌ Erro ao configurar canal de logs.", ephemeral=True)

    async def _set_canal_meta(self, interaction: discord.Interaction):
        try:
            canal = self.sel_canal_meta.values[0]
            ok = await self.db.set_config_meta(interaction.guild.id, canal_log_meta_id=canal.id)
            await interaction.response.send_message(
                "✅ Canal de log de meta atualizado!" if ok else "❌ Erro ao salvar canal de meta.",
                ephemeral=True
            )
        except Exception as e:
            print(f"Erro config canal meta: {e}")
            traceback.print_exc()
            await interaction.response.send_message("❌ Erro ao configurar canal de meta.", ephemeral=True)

    async def _set_cargo_gerente(self, interaction: discord.Interaction):
        try:
            cargo = self.sel_cargo_gerente.values[0]
            ok = await self.db.set_config_meta(interaction.guild.id, cargo_gerente_id=cargo.id)
            await interaction.response.send_message(
                "✅ Cargo de gerente atualizado!" if ok else "❌ Erro ao salvar cargo gerente.",
                ephemeral=True
            )
        except Exception as e:
            print(f"Erro config cargo gerente: {e}")
            traceback.print_exc()
            await interaction.response.send_message("❌ Erro ao configurar cargo gerente.", ephemeral=True)

    async def _set_cargo_meta(self, interaction: discord.Interaction):
        try:
            cargo = self.sel_cargo_meta.values[0]
            ok = await self.db.set_config_meta(interaction.guild.id, cargo_meta_paga_id=cargo.id)
            await interaction.response.send_message(
                "✅ Cargo de meta paga atualizado!" if ok else "❌ Erro ao salvar cargo meta paga.",
                ephemeral=True
            )
        except Exception as e:
            print(f"Erro config cargo meta: {e}")
            traceback.print_exc()
            await interaction.response.send_message("❌ Erro ao configurar cargo meta paga.", ephemeral=True)

    async def _set_cargo_vendedor(self, interaction: discord.Interaction):
        try:
            cargo = self.sel_cargo_vendedor.values[0]
            ok = await self.db.set_cargos_sistema(interaction.guild.id, cargo_vendedor_id=cargo.id)
            await interaction.response.send_message(
                "✅ Cargo de vendedor atualizado!" if ok else "❌ Erro ao salvar cargo vendedor.",
                ephemeral=True
            )
        except Exception as e:
            print(f"Erro config cargo vendedor: {e}")
            traceback.print_exc()
            await interaction.response.send_message("❌ Erro ao configurar cargo vendedor.", ephemeral=True)

    async def _set_cargo_fabricante(self, interaction: discord.Interaction):
        try:
            cargo = self.sel_cargo_fabricante.values[0]
            ok = await self.db.set_cargos_sistema(interaction.guild.id, cargo_fabricante_id=cargo.id)
            await interaction.response.send_message(
                "✅ Cargo de fabricante atualizado!" if ok else "❌ Erro ao salvar cargo fabricante.",
                ephemeral=True
            )
        except Exception as e:
            print(f"Erro config cargo fabricante: {e}")
            traceback.print_exc()
            await interaction.response.send_message("❌ Erro ao configurar cargo fabricante.", ephemeral=True)


class ConfigCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = Database()
        print("✅ Cog de Config carregado com sucesso!")

    @app_commands.command(name="config", description="Configurar o bot por servidor")
    @app_commands.checks.has_permissions(administrator=True)
    async def config(self, interaction: discord.Interaction):
        await interaction.response.send_message(view=ConfigView(self.db), ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(ConfigCog(bot))