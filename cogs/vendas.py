import discord
from discord import ui, app_commands
from discord.ext import commands
from datetime import datetime
import traceback
from database import Database


PRODUTOS = {
    "masterpick": {"nome": "Masterpick", "emoji": "🔧", "preco_unit": 2000.00},
    "camisa_forca": {"nome": "Camisa de Força", "emoji": "👕", "preco_unit": 6000.00},
    "ticket_corrida": {"nome": "Ticket de Corrida", "emoji": "🎫", "preco_unit": 1000.00},
}


def _fmt_money(v: float) -> str:
    return f"R$ {float(v):,.2f}".replace(",", ".")


async def _tem_cargo(interaction: discord.Interaction, cargo_id: int | None) -> bool:
    if not cargo_id:
        return False
    if not isinstance(interaction.user, discord.Member):
        return False
    return any(r.id == int(cargo_id) for r in interaction.user.roles)


async def _pode_usar_vendas(db: Database, interaction: discord.Interaction) -> bool:
    if interaction.user.guild_permissions.administrator:
        return True
    cargo_vendedor_id, _, cargo_gerente_id = await db.get_cargos_sistema(interaction.guild.id)
    if await _tem_cargo(interaction, cargo_gerente_id):
        return True
    if await _tem_cargo(interaction, cargo_vendedor_id):
        return True
    return False


async def _pode_confirmar_encomenda(db: Database, interaction: discord.Interaction, dono_id: int) -> bool:
    if interaction.user.guild_permissions.administrator:
        return True
    if interaction.guild and interaction.guild.owner_id == interaction.user.id:
        return True
    if interaction.user.id == dono_id:
        return True
    _, _, cargo_gerente_id = await db.get_cargos_sistema(interaction.guild.id)
    if await _tem_cargo(interaction, cargo_gerente_id):
        return True
    return False


class VendaEncomendaModal(ui.Modal):
    def __init__(self, db: Database, modo: str, produto_id: str):
        self.db = db
        self.modo = modo
        self.produto_id = produto_id

        titulo = "💰 Registrar Venda" if modo == "venda" else "📦 Registrar Encomenda"
        super().__init__(title=titulo)

        self.quantidade = ui.TextInput(
            label="Quantidade",
            placeholder="Digite a quantidade...",
            required=True,
            min_length=1,
            max_length=10
        )

        self.cliente = ui.TextInput(
            label="Para quem foi?",
            placeholder="Nome do comprador/cliente...",
            required=False,
            max_length=50
        )

        self.add_item(self.quantidade)
        self.add_item(self.cliente)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            if not await _pode_usar_vendas(self.db, interaction):
                await interaction.response.send_message("❌ Você não tem permissão para usar o sistema de vendas.", ephemeral=True)
                return

            qtd = int(self.quantidade.value)
            if qtd <= 0:
                await interaction.response.send_message("❌ A quantidade deve ser maior que zero.", ephemeral=True)
                return

            cliente = self.cliente.value.strip() if self.cliente.value else "Não informado"

            canal_log_id = await self.db.get_canal_log(interaction.guild.id)
            if not canal_log_id:
                await interaction.response.send_message(
                    "⚠️ Canal de logs não configurado. Use `/config` para configurar primeiro.",
                    ephemeral=True
                )
                return

            canal_logs = interaction.guild.get_channel(canal_log_id)
            if not canal_logs:
                await interaction.response.send_message(
                    "⚠️ Canal de logs não encontrado. Verifique `/config`.",
                    ephemeral=True
                )
                return

            produto_info = PRODUTOS.get(self.produto_id)
            if not produto_info:
                await interaction.response.send_message("❌ Produto inválido.", ephemeral=True)
                return

            nome_produto = produto_info["nome"]

            # garante preço correto de VENDA (fixo)
            preco_fixo_venda = float(produto_info["preco_unit"])
            preco_db = await self.db.get_preco_produto(interaction.guild.id, self.produto_id)
            if (preco_db is None) or (float(preco_db) != preco_fixo_venda):
                await self.db.set_preco_produto(interaction.guild.id, self.produto_id, preco_fixo_venda)
                preco_unit = preco_fixo_venda
            else:
                preco_unit = float(preco_db)

            valor_total = float(preco_unit) * qtd

            # ---------------- VENDA ----------------
            if self.modo == "venda":
                ok_estoque, consumido, disp = await self.db.consumir_estoque_sem_negativo(
                    interaction.guild.id, self.produto_id, qtd
                )
                if not ok_estoque:
                    await interaction.response.send_message(
                        "Erro ao consumir estoque. Tente novamente.",
                        ephemeral=True
                    )
                    return

                venda_id = await self.db.registrar_venda(
                    guild_id=interaction.guild.id,
                    user_id=interaction.user.id,
                    user_name=str(interaction.user),
                    produto_id=self.produto_id,
                    produto_nome=nome_produto,
                    quantidade=qtd,
                    valor_total=valor_total,
                    comprador=cliente
                )
                if not venda_id:
                    await interaction.response.send_message("❌ Erro ao salvar venda no banco.", ephemeral=True)
                    return

                novo_saldo = await self.db.aplicar_movimento_banco(
                    guild_id=interaction.guild.id,
                    user_id=interaction.user.id,
                    user_name=str(interaction.user),
                    delta=float(valor_total),
                    ultima_venda_valor=float(valor_total),
                    origem="venda",
                    ref_tipo="venda",
                    ref_id=int(venda_id)
                )

                log_view = LogVendaView(
                    usuario=interaction.user,
                    produto_nome=nome_produto,
                    quantidade=qtd,
                    preco_unit=preco_unit,
                    valor_total=valor_total,
                    comprador=cliente,
                    saldo_atual=novo_saldo
                )
                await canal_logs.send(view=log_view)

                await interaction.response.send_message("✅ Venda registrada com sucesso!", ephemeral=True)
                return

            # ---------------- ENCOMENDA ----------------
            # encomenda vira lembrete: nao reserva/consome estoque aqui

            encomenda_id = await self.db.criar_encomenda(
                guild_id=interaction.guild.id,
                user_id=interaction.user.id,
                user_name=str(interaction.user),
                produto_id=self.produto_id,
                produto_nome=nome_produto,
                quantidade=qtd,
                preco_unit=preco_unit,
                cliente=cliente
            )
            if not encomenda_id:
                await interaction.response.send_message("❌ Erro ao criar encomenda.", ephemeral=True)
                return

            view_encomenda = LogEncomendaPendenteView(
                db=self.db,
                encomenda_id=encomenda_id,
                dono_id=interaction.user.id,
                produto_nome=nome_produto,
                quantidade=qtd,
                preco_unit=preco_unit,
                cliente=cliente,
                user_name=str(interaction.user),
                user_id=interaction.user.id
            )
            mensagem = await canal_logs.send(view=view_encomenda)
            await self.db.set_encomenda_message_id(encomenda_id, mensagem.id)

            await interaction.response.send_message("✅ Encomenda registrada como pendente!", ephemeral=True)

        except ValueError:
            await interaction.response.send_message("❌ Digite apenas números válidos na quantidade.", ephemeral=True)
        except Exception as e:
            print(f"Erro no modal de venda/encomenda: {e}")
            traceback.print_exc()
            try:
                await interaction.response.send_message("❌ Erro ao processar. Tente novamente.", ephemeral=True)
            except:
                pass


class EscolherProdutoView(ui.LayoutView):
    def __init__(self, db: Database, modo: str):
        super().__init__()
        self.db = db
        self.modo = modo

        container = ui.Container()
        titulo = "💰 Registrar Venda" if modo == "venda" else "📦 Registrar Encomenda"

        container.add_item(ui.TextDisplay(f"# {titulo}"))
        container.add_item(ui.TextDisplay("Selecione o produto abaixo:"))
        container.add_item(ui.Separator(spacing=discord.SeparatorSpacing.small))

        for produto_id, info in PRODUTOS.items():
            preco = info["preco_unit"]
            container.add_item(ui.TextDisplay(
                f"## {info['emoji']} {info['nome']}\n"
                f"💰 Valor unitário: {_fmt_money(preco)}"
            ))
            container.add_item(ui.Separator(spacing=discord.SeparatorSpacing.small))

        select = ui.Select(
            placeholder="Selecione o produto...",
            min_values=1,
            max_values=1,
            options=[
                discord.SelectOption(
                    label=info["nome"],
                    value=produto_id,
                    emoji=info["emoji"]
                )
                for produto_id, info in PRODUTOS.items()
            ]
        )
        select.callback = self.on_select_produto

        container.add_item(ui.ActionRow(select))
        self.add_item(container)

    async def on_select_produto(self, interaction: discord.Interaction):
        modal = VendaEncomendaModal(self.db, self.modo, interaction.data["values"][0])
        await interaction.response.send_modal(modal)


class PainelVendasView(ui.LayoutView):
    def __init__(self, db: Database):
        super().__init__(timeout=None)
        self.db = db

        container = ui.Container()
        container.add_item(ui.TextDisplay("# 🧾 Registro de Vendas"))
        container.add_item(ui.Separator(spacing=discord.SeparatorSpacing.large))
        container.add_item(ui.TextDisplay("Escolha uma opção abaixo:"))
        container.add_item(ui.Separator(spacing=discord.SeparatorSpacing.large))

        btn_venda = ui.Button(
            label="Registrar Venda",
            style=discord.ButtonStyle.secondary,
            custom_id="painel_vendas:registrar_venda"
        )
        btn_venda.callback = self.abrir_venda

        btn_encomenda = ui.Button(
            label="Registrar Encomenda",
            style=discord.ButtonStyle.secondary,
            custom_id="painel_vendas:registrar_encomenda"
        )
        btn_encomenda.callback = self.abrir_encomenda

        try:
            container.add_item(ui.Section(
                ui.TextDisplay("• **Registrar Venda**\nRegistra **venda imediata** e envia para o canal de logs, registre com **atenção!**"),
                accessory=btn_venda
            ))
            container.add_item(ui.Separator(spacing=discord.SeparatorSpacing.large))
            container.add_item(ui.Section(
                ui.TextDisplay("• **Registrar Encomenda**\nCria **ENCOMENDA** pendente e permite confirmar entrega mais tarde, registre com **atenção!**"),
                accessory=btn_encomenda
            ))
        except Exception:
            container.add_item(ui.TextDisplay("• **Registrar Venda**\nRegistra **venda imediata** e envia para o canal de logs, registre com **atenção!**"))
            container.add_item(ui.ActionRow(btn_venda))
            container.add_item(ui.Separator(spacing=discord.SeparatorSpacing.large))
            container.add_item(ui.TextDisplay("• **Registrar Encomenda**\nCria **ENCOMENDA** pendente e permite confirmar entrega mais tarde, registre com **atenção!**"))
            container.add_item(ui.ActionRow(btn_encomenda))

        container.add_item(ui.Separator(spacing=discord.SeparatorSpacing.large))
        galeria_vendas = ui.MediaGallery()
        galeria_vendas.add_item(media='https://media.discordapp.net/attachments/1366148719967211612/1465503657452765286/Cartel.png?ex=69795823&is=697806a3&hm=6d37d5b02ab93b40bb31234a9b2518a68222014a0eb9472be730b8b1c5990561&=&format=webp&quality=lossless')
        container.add_item(galeria_vendas)

        self.add_item(container)

    async def abrir_venda(self, interaction: discord.Interaction):
        if not await _pode_usar_vendas(self.db, interaction):
            await interaction.response.send_message("❌ Você não tem permissão para usar o sistema de vendas.", ephemeral=True)
            return
        await interaction.response.send_message(view=EscolherProdutoView(self.db, modo="venda"), ephemeral=True)

    async def abrir_encomenda(self, interaction: discord.Interaction):
        if not await _pode_usar_vendas(self.db, interaction):
            await interaction.response.send_message("❌ Você não tem permissão para usar o sistema de vendas.", ephemeral=True)
            return
        await interaction.response.send_message(view=EscolherProdutoView(self.db, modo="encomenda"), ephemeral=True)


class LogVendaView(ui.LayoutView):
    def __init__(self, usuario: discord.Member, produto_nome: str, quantidade: int, preco_unit: float,
                 valor_total: float, comprador: str, saldo_atual: float | None = None):
        super().__init__()

        container = ui.Container()
        container.add_item(ui.TextDisplay("# 💰 Venda Registrada"))
        container.add_item(ui.Separator(spacing=discord.SeparatorSpacing.large))
        container.add_item(ui.TextDisplay(f"**👤 Vendedor:** {usuario.mention} (ID: {usuario.id})"))
        container.add_item(ui.TextDisplay(f"**📦 Produto:** {produto_nome}"))
        container.add_item(ui.TextDisplay(f"**🔢 Quantidade:** {quantidade}"))
        container.add_item(ui.TextDisplay(f"**💵 Valor unitário:** {_fmt_money(preco_unit)}"))
        container.add_item(ui.TextDisplay(f"**💰 Total:** {_fmt_money(valor_total)}"))
        container.add_item(ui.TextDisplay(f"**🧑 Comprador:** {comprador}"))

        if saldo_atual is not None:
            container.add_item(ui.Separator(spacing=discord.SeparatorSpacing.large))
            container.add_item(ui.TextDisplay(f"**🏦 Saldo atual do vendedor:** {_fmt_money(saldo_atual)}"))

        container.add_item(ui.Separator(spacing=discord.SeparatorSpacing.large))
        container.add_item(ui.TextDisplay(f"**🕒 Data:** {datetime.now().strftime('%d/%m/%Y às %H:%M:%S')}"))

        self.add_item(container)


class LogEncomendaPendenteView(ui.LayoutView):
    def __init__(self, db: Database, encomenda_id: int, dono_id: int,
                 produto_nome: str, quantidade: int, preco_unit: float,
                 cliente: str, user_name: str, user_id: int):
        super().__init__(timeout=None)
        self.db = db
        self.encomenda_id = int(encomenda_id)
        self.dono_id = int(dono_id)
        self._confirmado = False
        self.produto_nome = str(produto_nome)
        self.quantidade = int(quantidade)
        self.preco_unit = float(preco_unit)
        self.cliente = str(cliente)
        self.user_name = str(user_name)
        self.user_id = int(user_id)

        container = ui.Container()
        container.add_item(ui.TextDisplay('# Encomenda Pendente'))
        container.add_item(ui.Separator(spacing=discord.SeparatorSpacing.large))
        container.add_item(ui.TextDisplay(f'**ID da encomenda:** #{self.encomenda_id}'))
        container.add_item(ui.TextDisplay(f'**Vendedor:** <@{self.user_id}> (ID: {self.user_id})'))
        container.add_item(ui.TextDisplay(f'**Produto:** {self.produto_nome}'))
        container.add_item(ui.TextDisplay(f'**Quantidade:** {self.quantidade}'))
        container.add_item(ui.TextDisplay(f'**Valor unitario:** {_fmt_money(self.preco_unit)}'))
        container.add_item(ui.TextDisplay(f'**Total:** {_fmt_money(self.preco_unit * self.quantidade)}'))
        container.add_item(ui.TextDisplay(f'**Comprador:** {self.cliente or "Nao informado"}'))
        container.add_item(ui.Separator(spacing=discord.SeparatorSpacing.large))
        container.add_item(ui.TextDisplay(f'**Data:** {datetime.now().strftime("%d/%m/%Y %H:%M:%S")}'))
        container.add_item(ui.Separator(spacing=discord.SeparatorSpacing.small))
        container.add_item(ui.TextDisplay('Clique para confirmar quando a entrega for feita.'))
        container.add_item(ui.Separator(spacing=discord.SeparatorSpacing.small))

        self.btn_confirmar = ui.Button(
            label='Confirmar Entrega',
            style=discord.ButtonStyle.success,
            custom_id='encomenda_confirmar'
        )
        self.btn_confirmar.callback = self.confirmar_entrega
        container.add_item(ui.ActionRow(self.btn_confirmar))

        self.add_item(container)

    async def confirmar_entrega(self, interaction: discord.Interaction):
        try:
            if self._confirmado:
                return

            if not await _pode_confirmar_encomenda(self.db, interaction, self.dono_id):
                await interaction.response.send_message("❌ Você não pode confirmar esta encomenda.", ephemeral=True)
                return

            self._confirmado = True
            self.btn_confirmar.disabled = True
            await interaction.response.edit_message(view=self)

            dados = await self.db.get_encomenda_por_id(self.encomenda_id)
            if not dados:
                await interaction.followup.send("❌ Não foi possível encontrar a encomenda.", ephemeral=True)
                return

            guild_id, user_id, user_name, produto_id, produto_nome, quantidade, preco_unit, cliente, status = dados
            if status != "pendente":
                await interaction.followup.send("⚠️ Essa encomenda já foi confirmada ou não está pendente.", ephemeral=True)
                return

            sucesso = await self.db.confirmar_encomenda(self.encomenda_id, confirmado_por_id=interaction.user.id)
            if not sucesso:
                await interaction.followup.send("❌ Não foi possível confirmar a encomenda.", ephemeral=True)
                return

            valor_total = float(preco_unit) * int(quantidade)

            novo_saldo = await self.db.aplicar_movimento_banco(
                guild_id=int(guild_id),
                user_id=int(user_id),
                user_name=str(user_name),
                delta=float(valor_total),
                ultima_venda_valor=float(valor_total),
                origem="encomenda",
                ref_tipo="encomenda",
                ref_id=int(self.encomenda_id)
            )

            canal_log_id = await self.db.get_canal_log(interaction.guild.id)
            canal_logs = interaction.guild.get_channel(canal_log_id) if canal_log_id else None

            log_final = LogVendaView(
                usuario=interaction.guild.get_member(int(user_id)) or interaction.user,
                produto_nome=str(produto_nome),
                quantidade=int(quantidade),
                preco_unit=float(preco_unit),
                valor_total=float(valor_total),
                comprador=str(cliente or "Não informado"),
                saldo_atual=novo_saldo
            )

            if canal_logs:
                await canal_logs.send(view=log_final)

            await interaction.followup.send("✅ Entrega confirmada! Log final enviada.", ephemeral=True)

        except Exception as e:
            print(f"Erro ao confirmar encomenda: {e}")
            traceback.print_exc()
            try:
                await interaction.followup.send("❌ Erro ao confirmar. Tente novamente.", ephemeral=True)
            except:
                pass


class VendasCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = Database()
        # registra a view persistente do painel ao carregar o cog
        self.bot.add_view(PainelVendasView(self.db))
        self.bot.loop.create_task(self._rehydrate_encomendas_pendentes())
        print("✅ Cog de Vendas carregado com sucesso!")

    @app_commands.command(name="vendas", description="Abrir o painel do sistema de vendas")
    async def vendas(self, interaction: discord.Interaction):
        if not await _pode_usar_vendas(self.db, interaction):
            await interaction.response.send_message("❌ Você não tem permissão para usar este comando.", ephemeral=True)
            return
        view = PainelVendasView(self.db)
        await interaction.response.send_message(view=view)

    async def _rehydrate_encomendas_pendentes(self):
        try:
            await self.bot.wait_until_ready()
            pendentes = await self.db.listar_encomendas_pendentes()
            if not pendentes:
                return

            for encomenda_id, guild_id, user_id, message_id in pendentes:
                try:
                    dados = await self.db.get_encomenda_por_id(encomenda_id)
                    if not dados:
                        continue

                    (
                        _guild_id,
                        _user_id,
                        user_name,
                        _produto_id,
                        produto_nome,
                        quantidade,
                        preco_unit,
                        cliente,
                        status
                    ) = dados
                    if status != "pendente":
                        continue

                    canal_log_id = await self.db.get_canal_log(int(guild_id))
                    if not canal_log_id:
                        continue

                    guild = self.bot.get_guild(int(guild_id))
                    if not guild:
                        continue

                    canal = guild.get_channel(int(canal_log_id))
                    if not canal:
                        continue

                    try:
                        mensagem = await canal.fetch_message(int(message_id))
                    except Exception:
                        continue

                    view = LogEncomendaPendenteView(
                        db=self.db,
                        encomenda_id=encomenda_id,
                        dono_id=user_id,
                        produto_nome=produto_nome,
                        quantidade=quantidade,
                        preco_unit=preco_unit,
                        cliente=cliente or "Não informado",
                        user_name=user_name,
                        user_id=_user_id
                    )
                    self.bot.add_view(view, message_id=int(message_id))
                    await mensagem.edit(view=view)
                except Exception as e:
                    print(f"Erro ao reidratar encomenda #{encomenda_id}: {e}")
                    traceback.print_exc()
        except Exception as e:
            print(f"Erro ao reidratar encomendas pendentes: {e}")
            traceback.print_exc()

async def setup(bot: commands.Bot):
    await bot.add_cog(VendasCog(bot))
