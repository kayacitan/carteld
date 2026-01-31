import discord
from discord import ui, app_commands
from discord.ext import commands
from datetime import datetime
import io
import traceback
from database import Database
from utils.emojis import CHECK, X, DIN, PIGGY, SETTINGS, USER, LIST


def _fmt_money(v: float) -> str:
    return f"R$ {float(v):,.2f}".replace(",", ".")


class EditarSaldoModal(ui.Modal):
    def __init__(self, db: Database, alvo: discord.Member):
        super().__init__(title="🐷 Editar Saldo")
        self.db = db
        self.alvo = alvo

        self.delta = ui.TextInput(
            label="Valor (use negativo para remover - )",
            placeholder="Ex: 10000 ou -5000",
            required=True,
            min_length=1,
            max_length=20
        )
        self.motivo = ui.TextInput(
            label="Motivo",
            placeholder="Opcional",
            required=False,
            max_length=80
        )
        self.add_item(self.delta)
        self.add_item(self.motivo)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            # só o próprio ou dono do servidor
            if interaction.user.id != self.alvo.id and interaction.guild.owner_id != interaction.user.id and not interaction.user.guild_permissions.administrator:
                await interaction.response.send_message(f"{X} Você não pode editar o saldo de outra pessoa.", ephemeral=True)
                return

            delta = float(self.delta.value.replace(",", "."))
            motivo = self.motivo.value.strip() if self.motivo.value else None

            novo_saldo = await self.db.aplicar_movimento_banco(
                guild_id=interaction.guild.id,
                user_id=self.alvo.id,
                user_name=str(self.alvo),
                delta=float(delta),
                origem="ajuste",
                motivo=motivo,
                ref_tipo="ajuste",
                ref_id=None
            )
            await interaction.response.send_message(
                f"{CHECK} Saldo atualizado.\n{PIGGY} Novo saldo: **{_fmt_money(novo_saldo)}**",
                ephemeral=True
            )
        except Exception as e:
            print(f"Erro ao editar saldo: {e}")
            traceback.print_exc()
            try:
                await interaction.response.send_message(f"{X} Erro ao editar saldo.", ephemeral=True)
            except:
                pass


class BancoView(ui.LayoutView):
    def __init__(self, db: Database, alvo: discord.Member, saldo: float, ult_fab, ult_venda):
        super().__init__()
        self.db = db
        self.alvo = alvo

        container = ui.Container()
        container.add_item(ui.TextDisplay(f"# {PIGGY} Banco do Usuário"))
        container.add_item(ui.Separator(spacing=discord.SeparatorSpacing.small))
        container.add_item(ui.TextDisplay(f"**{USER} Usuário:** {alvo.mention}"))
        container.add_item(ui.TextDisplay(f"**{PIGGY} Caixa (atual):** {_fmt_money(saldo)}"))
        container.add_item(ui.TextDisplay(f"**Última fabricação:** {_fmt_money(ult_fab) if ult_fab is not None else '-'}"))
        container.add_item(ui.TextDisplay(f"**Última venda:** {_fmt_money(ult_venda) if ult_venda is not None else '-'}"))
        container.add_item(ui.Separator(spacing=discord.SeparatorSpacing.small))

        btn_editar = ui.Button(label="Editar saldo", style=discord.ButtonStyle.secondary, emoji=SETTINGS)
        btn_editar.callback = self.editar_saldo

        btn_transcrever = ui.Button(label="Transcrever", style=discord.ButtonStyle.secondary)
        btn_transcrever.callback = self.transcrever

        container.add_item(ui.ActionRow(btn_editar, btn_transcrever))
        self.add_item(container)

    async def editar_saldo(self, interaction: discord.Interaction):
        modal = EditarSaldoModal(self.db, self.alvo)
        await interaction.response.send_modal(modal)

    async def transcrever(self, interaction: discord.Interaction):
        try:
            saldo, ult_fab, ult_venda = await self.db.get_banco_usuario(interaction.guild.id, self.alvo.id, str(self.alvo))
            logs_fab = await self.db.get_logs_usuario_fabricacao(interaction.guild.id, self.alvo.id, limite=30)
            logs_vendas = await self.db.get_logs_usuario_vendas(interaction.guild.id, self.alvo.id, limite=30)
            extrato = await self.db.get_extrato_banco(interaction.guild.id, self.alvo.id, limite=50)

            linhas = []
            linhas.append(f"{LIST} TRANSCRIPT BANCO - {self.alvo} (ID: {self.alvo.id})")
            linhas.append(f"Gerado em: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
            linhas.append("")
            linhas.append(f"Saldo atual: {_fmt_money(saldo)}")
            linhas.append(f"Última fabricação: {_fmt_money(ult_fab) if ult_fab is not None else '—'}")
            linhas.append(f"Última venda: {_fmt_money(ult_venda) if ult_venda is not None else '—'}")
            linhas.append("")
            linhas.append(f"=== {LIST} EXTRATO (últimos movimentos) ===")
            for origem, delta, antes, depois, motivo, ref_tipo, ref_id, criado_em in extrato:
                linhas.append(f"- [{criado_em}] {origem.upper()} | Δ {_fmt_money(delta)} | {_fmt_money(antes)} -> {_fmt_money(depois)}"
                              + (f" | motivo: {motivo}" if motivo else "")
                              + (f" | ref: {ref_tipo}#{ref_id}" if ref_tipo and ref_id else ""))

            linhas.append("")
            linhas.append(f"=== {LIST} ÚLTIMAS FABRICAÇÕES ===")
            for produto_nome, quantidade, custo_total, data_fabricacao, materiais in logs_fab:
                linhas.append(f"- [{data_fabricacao}] {produto_nome} x{quantidade} | custo: {_fmt_money(custo_total)}")
                linhas.append(f"  materiais: {materiais}")

            linhas.append("")
            linhas.append(f"=== {LIST} ÚLTIMAS VENDAS ===")
            for produto_nome, quantidade, valor_total, comprador, data_venda in logs_vendas:
                linhas.append(f"- [{data_venda}] {produto_nome} x{quantidade} | total: {_fmt_money(valor_total)} | para: {comprador or 'Não informado'}")

            data = "\n".join(linhas).encode("utf-8")
            arquivo = discord.File(fp=io.BytesIO(data), filename=f"transcript_banco_{self.alvo.id}.txt")
            await interaction.response.send_message("Transcript gerado:", file=arquivo, ephemeral=True)

        except Exception as e:
            print(f"Erro ao transcrever banco: {e}")
            traceback.print_exc()
            try:
                await interaction.response.send_message(f"{X} Erro ao gerar transcript.", ephemeral=True)
            except:
                pass


class BancoCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = Database()
        print("Cog de Banco carregado com sucesso!")

    @app_commands.command(name="banco", description=f"{LIST} Ver banco pessoal e histórico")
    async def banco(self, interaction: discord.Interaction, usuario: discord.Member = None):
        if not interaction.guild:
            await interaction.response.send_message(f"{X} Este comando só funciona em servidor.", ephemeral=True)
            return
        try:
            if not interaction.response.is_done():\n                await interaction.response.defer(ephemeral=True)
            alvo = usuario or interaction.user
            saldo, ult_fab, ult_venda = await self.db.get_banco_usuario(interaction.guild.id, alvo.id, str(alvo))
            view = BancoView(self.db, alvo, saldo, ult_fab, ult_venda)
            await interaction.followup.send(view=view, ephemeral=True)
        except Exception as e:
            print(f"Erro no comando /banco: {e}")
            traceback.print_exc()
            if not interaction.response.is_done():
                await interaction.response.send_message(f"{X} Erro ao abrir o banco.", ephemeral=True)
            else:
                await interaction.followup.send(f"{X} Erro ao abrir o banco.", ephemeral=True)

async def setup(bot: commands.Bot):
    cog = BancoCog(bot)
    await cog.db.init_db()
    await bot.add_cog(cog)
