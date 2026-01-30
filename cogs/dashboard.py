import discord
from discord import ui, app_commands
from discord.ext import commands
from datetime import datetime, timedelta
import traceback
from database import Database


PRODUTOS = {
    "masterpick": {"nome": "Masterpick", "emoji": "🔧"},
    "camisa_forca": {"nome": "Camisa de Força", "emoji": "👕"},
    "ticket_corrida": {"nome": "Ticket de Corrida", "emoji": "🎫"},
}

PAGES = {
    "HOME": "HOME",
    "VENDAS": "VENDAS",
    "FABRICACAO": "FABRICAÇÃO",
    "ESTOQUE": "ESTOQUE",
    "ENCOMENDAS": "ENCOMENDAS",
    "METAS": "METAS",
    "BANCO": "BANCO",
}

PAGE_ORDER = [
    PAGES["VENDAS"],
    PAGES["FABRICACAO"],
    PAGES["ESTOQUE"],
    PAGES["ENCOMENDAS"],
    PAGES["METAS"],
    PAGES["BANCO"],
]


def _fmt_money(v: float | int | None) -> str:
    return f"R$ {float(v or 0.0):,.2f}".replace(",", ".")


def _fmt_dt(iso_str: str | None) -> str:
    if not iso_str:
        return "-"
    try:
        return datetime.fromisoformat(str(iso_str)).strftime("%d/%m %H:%M")
    except Exception:
        return str(iso_str)


async def _tem_cargo(interaction: discord.Interaction, cargo_id: int | None) -> bool:
    if not cargo_id:
        return False
    if not isinstance(interaction.user, discord.Member):
        return False
    return any(r.id == int(cargo_id) for r in interaction.user.roles)


class DashboardView(ui.LayoutView):
    def __init__(self, db: Database, guild: discord.Guild, user_id: int):
        super().__init__(timeout=None)
        self.db = db
        self.guild = guild
        self.user_id = int(user_id)
        self.page = PAGES["VENDAS"]

    async def render(self):
        self.clear_items()
        container = await self._build_page()
        self.add_item(container)

    async def _build_page(self) -> ui.Container:
        if self.page == PAGES["VENDAS"]:
            return await self._build_vendas()
        if self.page == PAGES["FABRICACAO"]:
            return await self._build_fabricacao()
        if self.page == PAGES["ESTOQUE"]:
            return await self._build_estoque()
        if self.page == PAGES["ENCOMENDAS"]:
            return await self._build_encomendas()
        if self.page == PAGES["METAS"]:
            return await self._build_metas()
        if self.page == PAGES["BANCO"]:
            return await self._build_banco()
        return await self._build_home()

    def _nav_button(self, label: str, target_page: str):
        button = ui.Button(label=label, style=discord.ButtonStyle.secondary)

        async def _callback(interaction: discord.Interaction):
            await self._on_nav(interaction, target_page)

        button.callback = _callback
        return button

    def _action_buttons(self):
        buttons = []
        btn_prev = ui.Button(label="Anterior", style=discord.ButtonStyle.secondary)
        btn_prev.callback = self._on_prev
        buttons.append(btn_prev)

        btn_next = ui.Button(label="Proximo", style=discord.ButtonStyle.secondary)
        btn_next.callback = self._on_next
        buttons.append(btn_next)

        btn_refresh = ui.Button(label="Atualizar", style=discord.ButtonStyle.primary)
        btn_refresh.callback = self._on_refresh
        buttons.append(btn_refresh)

        return ui.ActionRow(*buttons)

    async def _safe_defer(self, interaction: discord.Interaction):
        if not interaction.response.is_done():
            await interaction.response.defer()

    def _page_index(self) -> int:
        try:
            return PAGE_ORDER.index(self.page)
        except ValueError:
            return 0

    def _set_page_by_offset(self, offset: int):
        if not PAGE_ORDER:
            return
        idx = (self._page_index() + offset) % len(PAGE_ORDER)
        self.page = PAGE_ORDER[idx]

    async def _ensure_author(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                "❌ Este painel é privado. Use /dashboard para abrir o seu.",
                ephemeral=True
            )
            return False
        return True

    async def _on_nav(self, interaction: discord.Interaction, target_page: str):
        if not await self._ensure_author(interaction):
            return
        try:
            self.page = target_page
            await self.render()
            await self._safe_defer(interaction)
            await interaction.edit_original_response(view=self)
        except Exception as e:
            print(f"Erro ao navegar no dashboard: {e}")
            traceback.print_exc()
            try:
                await interaction.response.send_message(
                    "Erro ao abrir a tela. Tente novamente.",
                    ephemeral=True
                )
            except Exception:
                pass

    async def _on_prev(self, interaction: discord.Interaction):
        if not await self._ensure_author(interaction):
            return
        try:
            self._set_page_by_offset(-1)
            await self.render()
            await self._safe_defer(interaction)
            await interaction.edit_original_response(view=self)
        except Exception as e:
            print(f"Erro ao voltar no dashboard: {e}")
            traceback.print_exc()
            try:
                await interaction.response.send_message(
                    "Erro ao abrir a tela. Tente novamente.",
                    ephemeral=True
                )
            except Exception:
                pass

    async def _on_next(self, interaction: discord.Interaction):
        if not await self._ensure_author(interaction):
            return
        try:
            self._set_page_by_offset(1)
            await self.render()
            await self._safe_defer(interaction)
            await interaction.edit_original_response(view=self)
        except Exception as e:
            print(f"Erro ao avancar no dashboard: {e}")
            traceback.print_exc()
            try:
                await interaction.response.send_message(
                    "Erro ao abrir a tela. Tente novamente.",
                    ephemeral=True
                )
            except Exception:
                pass

    async def _on_refresh(self, interaction: discord.Interaction):
        if not await self._ensure_author(interaction):
            return
        try:
            await self.render()
            await self._safe_defer(interaction)
            await interaction.edit_original_response(view=self)
        except Exception as e:
            print(f"Erro ao atualizar dashboard: {e}")
            traceback.print_exc()
            try:
                await interaction.response.send_message(
                    "❌ Ocorreu um erro ao atualizar. Tente novamente.",
                    ephemeral=True
                )
            except Exception:
                pass

    async def _on_close(self, interaction: discord.Interaction):
        if not await self._ensure_author(interaction):
            return
        try:
            await self._safe_defer(interaction)
            await interaction.edit_original_response(content="Painel fechado.", view=None)
        except Exception as e:
            print(f"Erro ao fechar dashboard: {e}")
            traceback.print_exc()

    def _add_section(self, container: ui.Container, text: str, button: ui.Button):
        try:
            container.add_item(ui.Section(ui.TextDisplay(text), accessory=button))
        except Exception:
            container.add_item(ui.TextDisplay(text))
            container.add_item(ui.ActionRow(button))

    def _periodos(self):
        agora = datetime.now()
        inicio_hoje = agora.replace(hour=0, minute=0, second=0, microsecond=0)
        inicio_semana = agora - timedelta(days=7)
        return (
            inicio_hoje.isoformat(),
            agora.isoformat(),
            inicio_semana.isoformat(),
            agora.isoformat(),
        )

    async def _build_home(self) -> ui.Container:
        inicio_hoje, fim_hoje, inicio_semana, fim_semana = self._periodos()

        total_hoje = await self.db.get_total_vendas_periodo(self.guild.id, inicio_hoje, fim_hoje)
        total_semana = await self.db.get_total_vendas_periodo(self.guild.id, inicio_semana, fim_semana)
        custo_fab_semana = await self.db.get_total_custo_fabricacao_periodo(self.guild.id, inicio_semana, fim_semana)
        pendentes = await self.db.get_encomendas_pendentes_servidor(self.guild.id, limite=10)
        metas_semana = await self.db.get_metas_aprovadas_periodo(self.guild.id, inicio_semana, fim_semana)
        top_saldos = await self.db.get_top_saldos_servidor(self.guild.id, limite=5)
        movimentos = await self.db.get_movimentos_banco_servidor(self.guild.id, limite=5)

        estoque_info = {}
        for produto_id in PRODUTOS.keys():
            estoque_info[produto_id] = await self.db.get_estoque_produto(self.guild.id, produto_id)

        container = ui.Container()
        container.add_item(ui.TextDisplay(f"# 📊 Dashboard — {self.guild.name}"))
        container.add_item(ui.Separator(spacing=discord.SeparatorSpacing.large))

        vendas_texto = (
            f"**💰 Vendas**\n"
            f"• Hoje: {_fmt_money(total_hoje)}\n"
            f"• Últimos 7 dias: {_fmt_money(total_semana)}"
        )
        self._add_section(container, vendas_texto, self._nav_button("Ver", PAGES["VENDAS"]))
        container.add_item(ui.Separator(spacing=discord.SeparatorSpacing.small))

        fab_texto = (
            f"**🏭 Fabricação**\n"
            f"• Custo (7 dias): {_fmt_money(custo_fab_semana)}"
        )
        self._add_section(container, fab_texto, self._nav_button("Ver", PAGES["FABRICACAO"]))
        container.add_item(ui.Separator(spacing=discord.SeparatorSpacing.small))

        estoque_linhas = []
        for produto_id, info in PRODUTOS.items():
            qtd, res, disp = estoque_info.get(produto_id, (0, 0, 0))
            estoque_linhas.append(
                f"• {info['emoji']} **{info['nome']}**: {qtd} | disp {disp} | res {res}"
            )
        estoque_texto = "**📦 Estoque**\n" + ("\n".join(estoque_linhas) if estoque_linhas else "Sem dados.")
        self._add_section(container, estoque_texto, self._nav_button("Ver", PAGES["ESTOQUE"]))
        container.add_item(ui.Separator(spacing=discord.SeparatorSpacing.small))

        encomendas_texto = f"**📦 Encomendas**\n• Pendentes: {len(pendentes)}"
        self._add_section(container, encomendas_texto, self._nav_button("Ver", PAGES["ENCOMENDAS"]))
        container.add_item(ui.Separator(spacing=discord.SeparatorSpacing.small))

        metas_texto = (
            f"**✅ Metas**\n"
            f"• Aprovadas (7 dias): {metas_semana}\n"
            f"• Pendentes: indisponível"
        )
        self._add_section(container, metas_texto, self._nav_button("Ver", PAGES["METAS"]))
        container.add_item(ui.Separator(spacing=discord.SeparatorSpacing.small))

        top_saldos_txt = "Sem dados."
        if top_saldos:
            top_saldos_txt = "\n".join(
                [f"• {user}: {_fmt_money(saldo)}" for user, saldo in top_saldos]
            )
        mov_txt = "Sem movimentos recentes."
        if movimentos:
            mov_txt = "\n".join(
                [f"• {user} ({origem}): {_fmt_money(delta)} — {_fmt_dt(data)}"
                 for user, origem, delta, _saldo, data in movimentos]
            )
        banco_texto = (
            "**🏦 Banco**\n"
            f"Top saldos:\n{top_saldos_txt}\n"
            f"Movimentos recentes:\n{mov_txt}"
        )
        self._add_section(container, banco_texto, self._nav_button("Ver", PAGES["BANCO"]))

        container.add_item(ui.Separator(spacing=discord.SeparatorSpacing.large))
        container.add_item(self._action_buttons())
        return container

    async def _build_vendas(self) -> ui.Container:
        inicio_hoje, fim_hoje, inicio_semana, fim_semana = self._periodos()
        total_hoje = await self.db.get_total_vendas_periodo(self.guild.id, inicio_hoje, fim_hoje)
        total_semana = await self.db.get_total_vendas_periodo(self.guild.id, inicio_semana, fim_semana)
        logs = await self.db.get_logs_vendas_servidor(self.guild.id, limite=10)

        linhas = []
        for produto, qtd, total, comprador, data_venda, user_name in logs:
            linhas.append(
                f"• {produto} x{qtd} — {_fmt_money(total)} — {comprador or 'Não informado'} — {user_name} — {_fmt_dt(data_venda)}"
            )
        lista = "\n".join(linhas) if linhas else "Nenhuma venda registrada."

        container = ui.Container()
        container.add_item(ui.TextDisplay("# 💰 Vendas — Resumo do Servidor"))
        container.add_item(ui.Separator(spacing=discord.SeparatorSpacing.small))
        container.add_item(ui.TextDisplay(
            f"• Hoje: {_fmt_money(total_hoje)}\n"
            f"• Últimos 7 dias: {_fmt_money(total_semana)}"
        ))
        container.add_item(ui.Separator(spacing=discord.SeparatorSpacing.small))
        container.add_item(ui.TextDisplay(f"**Últimas 10 vendas:**\n{lista}"))
        container.add_item(ui.Separator(spacing=discord.SeparatorSpacing.large))
        container.add_item(self._action_buttons())
        return container

    async def _build_fabricacao(self) -> ui.Container:
        _inicio_hoje, _fim_hoje, inicio_semana, fim_semana = self._periodos()
        custo_semana = await self.db.get_total_custo_fabricacao_periodo(self.guild.id, inicio_semana, fim_semana)
        logs = await self.db.get_logs_fabricacao_servidor(self.guild.id, limite=10)

        linhas = []
        for produto, qtd, custo_total, data_fab, user_name in logs:
            linhas.append(
                f"• {produto} x{qtd} — {_fmt_money(custo_total)} — {user_name} — {_fmt_dt(data_fab)}"
            )
        lista = "\n".join(linhas) if linhas else "Nenhuma fabricação registrada."

        container = ui.Container()
        container.add_item(ui.TextDisplay("# 🏭 Fabricação — Resumo do Servidor"))
        container.add_item(ui.Separator(spacing=discord.SeparatorSpacing.small))
        container.add_item(ui.TextDisplay(f"• Custo (7 dias): {_fmt_money(custo_semana)}"))
        container.add_item(ui.Separator(spacing=discord.SeparatorSpacing.small))
        container.add_item(ui.TextDisplay(f"**Últimas 10 fabricações:**\n{lista}"))
        container.add_item(ui.Separator(spacing=discord.SeparatorSpacing.large))
        container.add_item(self._action_buttons())
        return container

    async def _build_estoque(self) -> ui.Container:
        container = ui.Container()
        container.add_item(ui.TextDisplay("# 📦 Estoque — Resumo do Servidor"))
        container.add_item(ui.Separator(spacing=discord.SeparatorSpacing.small))

        for produto_id, info in PRODUTOS.items():
            qtd, res, disp = await self.db.get_estoque_produto(self.guild.id, produto_id)
            container.add_item(ui.TextDisplay(
                f"## {info['emoji']} {info['nome']}\n"
                f"• Total: {qtd}\n"
                f"• Reservado: {res}\n"
                f"• Disponível: {disp}"
            ))
            container.add_item(ui.Separator(spacing=discord.SeparatorSpacing.small))

        container.add_item(self._action_buttons())
        return container

    async def _build_encomendas(self) -> ui.Container:
        pendentes = await self.db.get_encomendas_pendentes_servidor(self.guild.id, limite=10)
        confirmadas = await self.db.get_ultimas_encomendas_confirmadas(self.guild.id, limite=5)

        pendentes_txt = "Nenhuma encomenda pendente."
        if pendentes:
            pendentes_txt = "\n".join(
                [
                    f"• #{eid} {produto} x{qtd} — {cliente or 'Não informado'} — {user} — {_fmt_dt(criado)}"
                    for eid, produto, qtd, _preco, cliente, user, criado in pendentes
                ]
            )

        confirmadas_txt = "Nenhuma encomenda confirmada recentemente."
        if confirmadas:
            confirmadas_txt = "\n".join(
                [
                    f"• #{eid} {produto} x{qtd} — {cliente or 'Não informado'} — {user} — {_fmt_dt(confirmado)}"
                    for eid, produto, qtd, _preco, cliente, user, confirmado in confirmadas
                ]
            )

        container = ui.Container()
        container.add_item(ui.TextDisplay("# 📦 Encomendas — Resumo do Servidor"))
        container.add_item(ui.Separator(spacing=discord.SeparatorSpacing.small))
        container.add_item(ui.TextDisplay(f"**Pendentes:**\n{pendentes_txt}"))
        container.add_item(ui.Separator(spacing=discord.SeparatorSpacing.small))
        container.add_item(ui.TextDisplay(f"**Confirmadas recentes:**\n{confirmadas_txt}"))
        container.add_item(ui.Separator(spacing=discord.SeparatorSpacing.large))
        container.add_item(self._action_buttons())
        return container

    async def _build_metas(self) -> ui.Container:
        _inicio_hoje, _fim_hoje, inicio_semana, fim_semana = self._periodos()
        aprovadas = await self.db.get_metas_aprovadas_periodo(self.guild.id, inicio_semana, fim_semana)

        container = ui.Container()
        container.add_item(ui.TextDisplay("# ✅ Metas — Resumo do Servidor"))
        container.add_item(ui.Separator(spacing=discord.SeparatorSpacing.small))
        container.add_item(ui.TextDisplay(
            f"• Aprovadas (7 dias): {aprovadas}\n"
            f"• Pendentes: indisponível"
        ))
        container.add_item(ui.Separator(spacing=discord.SeparatorSpacing.large))
        container.add_item(self._action_buttons())
        return container

    async def _build_banco(self) -> ui.Container:
        top_saldos = await self.db.get_top_saldos_servidor(self.guild.id, limite=5)
        movimentos = await self.db.get_movimentos_banco_servidor(self.guild.id, limite=10)

        top_txt = "Sem dados."
        if top_saldos:
            top_txt = "\n".join([f"• {user}: {_fmt_money(saldo)}" for user, saldo in top_saldos])

        mov_txt = "Sem movimentos recentes."
        if movimentos:
            mov_txt = "\n".join(
                [
                    f"• {user} ({origem}): {_fmt_money(delta)} — {_fmt_dt(data)}"
                    for user, origem, delta, _saldo, data in movimentos
                ]
            )

        container = ui.Container()
        container.add_item(ui.TextDisplay("# 🏦 Banco — Resumo do Servidor"))
        container.add_item(ui.Separator(spacing=discord.SeparatorSpacing.small))
        container.add_item(ui.TextDisplay(f"**Top saldos:**\n{top_txt}"))
        container.add_item(ui.Separator(spacing=discord.SeparatorSpacing.small))
        container.add_item(ui.TextDisplay(f"**Movimentos recentes:**\n{mov_txt}"))
        container.add_item(ui.Separator(spacing=discord.SeparatorSpacing.large))
        container.add_item(self._action_buttons())
        return container


class DashboardCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = Database()
        print("✅ Cog de Dashboard carregado com sucesso!")

    @app_commands.command(name="dashboard", description="Abrir a dashboard administrativa")
    async def dashboard(self, interaction: discord.Interaction):
        try:
            if not interaction.guild:
                await interaction.response.send_message("❌ Este comando só funciona em servidor.", ephemeral=True)
                return

            if interaction.user.guild_permissions.administrator:
                permitido = True
                cargo_gerente_id = None
            else:
                _, _, cargo_gerente_id = await self.db.get_cargos_sistema(interaction.guild.id)
                if cargo_gerente_id is None:
                    await interaction.response.send_message(
                        "❌ Cargo gerente não configurado. Apenas administradores podem usar /dashboard.",
                        ephemeral=True
                    )
                    return
                permitido = await _tem_cargo(interaction, cargo_gerente_id)

            if not permitido:
                await interaction.response.send_message(
                    "❌ Você não tem permissão para usar o dashboard.",
                    ephemeral=True
                )
                return

            view = DashboardView(self.db, interaction.guild, interaction.user.id)
            await view.render()
            await interaction.response.defer(ephemeral=True)
            await interaction.followup.send(view=view, ephemeral=True)

        except Exception as e:
            print(f"Erro no comando /dashboard: {e}")
            traceback.print_exc()
            try:
                await interaction.response.send_message(
                    "❌ Ocorreu um erro ao abrir o dashboard.",
                    ephemeral=True
                )
            except Exception:
                pass


async def setup(bot: commands.Bot):
    try:
        cog = DashboardCog(bot)
        await cog.db.init_db()
        await bot.add_cog(cog)
        print("✅ DashboardCog adicionado com sucesso!")
    except Exception as e:
        print(f"❌ Erro ao carregar DashboardCog: {e}")
        traceback.print_exc()
