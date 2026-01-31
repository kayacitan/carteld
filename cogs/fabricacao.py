import discord
from discord import ui, app_commands
from discord.ext import commands
from datetime import datetime
import traceback
from database import Database
from utils.emojis import CHECK, X, DIN, PIGGY, STORE, USER, CONTAINER, SETTINGS, PACKAGE, LIST, TOOL, SHIRT, TICKET

# Definição dos produtos
PRODUTOS = {
    "masterpick": {
        "nome": "Masterpick",
        "custo": 500,
        "emoji": TOOL,
        "materiais": {
            "Alumínio": 4,
            "Ferro": 4,
            "Borracha": 1,
            "Cobre": 1,
            "Saco Plástico": 1
        }
    },
    "camisa_forca": {
        "nome": "Camisa de Força",
        "custo": 1950,
        "emoji": SHIRT,
        "materiais": {
            "Tecido": 8
        }
    },
    "ticket_corrida": {
        "nome": "Ticket de Corrida",
        "custo": 360,
        "emoji": TICKET,
        "materiais": {
            "Folha de Papel": 1,
            "Lata de Tinta": 1,
            "Embalagem Plástica": 1
        }
    }
}


# --- MODAL PARA QUANTIDADE ---
class QuantidadeModal(ui.Modal, title='Quantidade de Fabricação'):
    def __init__(self, produto_id: str, produto: dict, db: Database):
        super().__init__()
        self.produto_id = produto_id
        self.produto = produto
        self.db = db

    quantidade = ui.TextInput(
        label='Quantidade',
        placeholder='Digite a quantidade a fabricar...',
        required=True,
        min_length=1,
        max_length=10
    )

    async def on_submit(self, interaction: discord.Interaction):
        try:
            qtd = int(self.quantidade.value)

            if qtd <= 0:
                await interaction.response.send_message(
                    f"{X} A quantidade deve ser maior que zero!",
                    ephemeral=True
                )
                return

            # Calcular materiais e custo total
            custo_total = self.produto["custo"] * qtd

            # Criar lista de materiais
            materiais_lista = []
            for material, qtd_material in self.produto["materiais"].items():
                total_material = qtd_material * qtd
                materiais_lista.append(f"• **{material}**: {total_material}")

            materiais_texto = "\n".join(materiais_lista)

            # Criar view de confirmação
            view = ConfirmacaoView(
                self.produto_id,
                self.produto,
                qtd,
                custo_total,
                materiais_texto,
                self.db
            )

            await interaction.response.send_message(
                view=view,
                ephemeral=True
            )

        except ValueError:
            await interaction.response.send_message(
                f"{X} Por favor, digite apenas números!",
                ephemeral=True
            )
        except Exception as e:
            print(f"Erro no modal de quantidade: {e}")
            traceback.print_exc()
            await interaction.response.send_message(
                f"{X} Ocorreu um erro ao processar a quantidade. Tente novamente.",
                ephemeral=True
            )

    async def on_error(self, interaction: discord.Interaction, error: Exception):
        print(f"Erro no modal: {error}")
        traceback.print_exc()
        try:
            await interaction.response.send_message(
                f"{X} Ocorreu um erro ao processar o formulário. Tente novamente.",
                ephemeral=True
            )
        except:
            pass


# --- VIEW DE CONFIRMACAO ---
class ConfirmacaoView(ui.LayoutView):
    def __init__(self, produto_id: str, produto: dict, quantidade: int, custo_total: float, materiais: str, db: Database):
        super().__init__()
        self.produto_id = produto_id
        self.produto = produto
        self.quantidade = quantidade
        self.custo_total = custo_total
        self.materiais = materiais
        self.db = db
        self._finalizado = False

        # Criar container de confirmação
        container = ui.Container()
        container.add_item(ui.TextDisplay(f'# {STORE} Confirmação de Fabricação'))
        container.add_item(ui.Separator(spacing=discord.SeparatorSpacing.large))

        # Informações do produto
        container.add_item(ui.TextDisplay(f"**{PACKAGE} Produto:** {self.produto['nome']}"))
        container.add_item(ui.TextDisplay(f"**Quantidade:** {self.quantidade} unidade(s)"))

        container.add_item(ui.Separator(spacing=discord.SeparatorSpacing.large))

        # Custo total
        custo_formatado = f"R$ {self.custo_total:,.2f}".replace(',', '.')
        container.add_item(ui.TextDisplay(f"**{DIN} Custo Total:** {custo_formatado}"))

        container.add_item(ui.Separator(spacing=discord.SeparatorSpacing.large))

        # Materiais necessários
        container.add_item(ui.TextDisplay(f"**{CONTAINER} Materiais Necessários:**\n{self.materiais}"))

        container.add_item(ui.Separator(spacing=discord.SeparatorSpacing.large))

        # Botões de confirmação
        botao_confirmar = ui.Button(
            label=f"{CHECK} Confirmar Fabricação",
            style=discord.ButtonStyle.success
        )
        botao_confirmar.callback = self.confirmar

        botao_cancelar = ui.Button(
            label=f"{X} Cancelar",
            style=discord.ButtonStyle.danger
        )
        botao_cancelar.callback = self.cancelar

        linha = ui.ActionRow(botao_confirmar, botao_cancelar)
        container.add_item(linha)

        self.add_item(container)

    async def confirmar(self, interaction: discord.Interaction):
        try:
            if self._finalizado:
                return
            self._finalizado = True

            # Desabilitar botões (fica inacessível após confirmar)
            for item in self.children:
                if isinstance(item, ui.Container):
                    for comp in item.children:
                        if isinstance(comp, ui.ActionRow):
                            for btn in comp.children:
                                if isinstance(btn, ui.Button):
                                    btn.disabled = True

            await interaction.response.edit_message(view=self)

            # Buscar canal de log do banco de dados
            canal_log_id = await self.db.get_canal_log(interaction.guild.id)

            if canal_log_id is None:
                await interaction.followup.send(
                    f"{X} Canal de logs não configurado! Use {SETTINGS} `/config` para configurar.",
                    ephemeral=True
                )
                return

            canal_logs = interaction.guild.get_channel(canal_log_id)

            if canal_logs is None:
                await interaction.followup.send(
                    f"{X} Canal de logs não encontrado! Verifique a configuração.",
                    ephemeral=True
                )
                return

            # Registrar no banco de dados
            await self.db.registrar_fabricacao(
                guild_id=interaction.guild.id,
                user_id=interaction.user.id,
                user_name=str(interaction.user),
                produto_id=self.produto_id,
                produto_nome=self.produto['nome'],
                quantidade=self.quantidade,
                custo_total=self.custo_total,
                materiais=self.materiais
            )

            await self.db.adicionar_estoque(
                guild_id=interaction.guild.id,
                produto_id=self.produto_id,
                quantidade=self.quantidade
            )

            # Atualizar banco pessoal (fabricação desconta)
            novo_saldo = await self.db.aplicar_movimento_banco(
                guild_id=interaction.guild.id,
                user_id=interaction.user.id,
                user_name=str(interaction.user),
                delta=-float(self.custo_total),
                ultima_fabricacao_valor=float(self.custo_total),
                origem="fabricacao"
            )

            # Criar LayoutView para o logggg
            log_view = LogFabricacaoView(
                usuario=interaction.user,
                produto=self.produto,
                quantidade=self.quantidade,
                custo_total=self.custo_total,
                materiais=self.materiais,
                saldo_atual=novo_saldo
            )

            await canal_logs.send(view=log_view)

            # Confirmar para o usuário
            await interaction.followup.send(
                f"{CHECK} **Fabricação confirmada!**\n"
                f"{self.quantidade}x {self.produto['nome']} foram fabricados com sucesso!",
                ephemeral=True
            )

        except discord.Forbidden:
            await interaction.followup.send(
                f"{X} Não tenho permissão para enviar mensagens no canal de logs!",
                ephemeral=True
            )
        except Exception as e:
            print(f"Erro ao confirmar fabricação: {e}")
            traceback.print_exc()
            await interaction.followup.send(
                f"{X} Erro ao processar a fabricação. Tente novamente.",
                ephemeral=True
            )

    async def cancelar(self, interaction: discord.Interaction):
        try:
            # Desabilitar botões
            for item in self.children:
                if isinstance(item, ui.Container):
                    for comp in item.children:
                        if isinstance(comp, ui.ActionRow):
                            for btn in comp.children:
                                if isinstance(btn, ui.Button):
                                    btn.disabled = True

            await interaction.response.edit_message(view=self)
            await interaction.followup.send(
                f"{X} Fabricação cancelada.",
                ephemeral=True
            )
        except Exception as e:
            print(f"Erro ao cancelar: {e}")
            traceback.print_exc()


# --- LAYOUTVIEW PARA LOG DE FABRICACAO ---
class LogFabricacaoView(ui.LayoutView):
    def __init__(self, usuario: discord.Member, produto: dict, quantidade: int, custo_total: float, materiais: str, saldo_atual=None):
        super().__init__()

        container = ui.Container()
        container.add_item(ui.TextDisplay(f'# {STORE} Nova Fabricação Realizada'))
        container.add_item(ui.Separator(spacing=discord.SeparatorSpacing.small))

        container.add_item(ui.TextDisplay(f"**{USER} Usuário:** {usuario.mention} (ID: {usuario.id})"))
        container.add_item(ui.TextDisplay(f"**{PACKAGE} Produto:** {produto['nome']}"))
        container.add_item(ui.TextDisplay(f"**Quantidade:** {quantidade} unidade(s)"))

        container.add_item(ui.Separator(spacing=discord.SeparatorSpacing.large))

        custo_formatado = f"R$ {custo_total:,.2f}".replace(',', '.')
        container.add_item(ui.TextDisplay(f"**{DIN} Custo Total:** {custo_formatado}"))

        if saldo_atual is not None:
            saldo_formatado = f"R$ {float(saldo_atual):,.2f}".replace(',', '.')
            container.add_item(ui.TextDisplay(f"**{PIGGY} Saldo em caixa:** {saldo_formatado}"))

        container.add_item(ui.Separator(spacing=discord.SeparatorSpacing.large))
        container.add_item(ui.TextDisplay(f"**{CONTAINER} Materiais Utilizados:**\n{materiais}"))
        container.add_item(ui.Separator(spacing=discord.SeparatorSpacing.large))

        data_hora = datetime.now().strftime("%d/%m/%Y às %H:%M:%S")
        container.add_item(ui.TextDisplay(f"**Data e Hora:** {data_hora}"))

        self.add_item(container)


# --- VIEW PRINCIPAL DE FABRICACAO ---
class FabricacaoView(ui.LayoutView):
    def __init__(self, db: Database):
        super().__init__(timeout=None)
        self.db = db

        container = ui.Container()
        container.add_item(ui.TextDisplay(f'# {LIST} {STORE} Registro de Fabricação'))
        container.add_item(ui.Separator(spacing=discord.SeparatorSpacing.large))
        container.add_item(ui.TextDisplay('Selecione o produto que deseja fabricar abaixo:'))
        container.add_item(ui.Separator(spacing=discord.SeparatorSpacing.large))

        for produto_id, info in PRODUTOS.items():
            materiais_texto = "\n".join([f"• {mat}: {qtd}" for mat, qtd in info['materiais'].items()])
            container.add_item(ui.TextDisplay(f"**{info['emoji']} {info['nome']}**"))
            receita_info = (
                f"{DIN} Custo: R$ {info['custo']:,.2f}".replace(',', '.') + "\n"
                f"{CONTAINER} Materiais:\n{materiais_texto}"
            )
            container.add_item(ui.TextDisplay(receita_info))
            container.add_item(ui.Separator(spacing=discord.SeparatorSpacing.large))


        galeria_fabricacao = ui.MediaGallery()
        galeria_fabricacao.add_item(media='https://media.discordapp.net/attachments/1366148719967211612/1465503657452765286/Cartel.png?ex=69795823&is=697806a3&hm=6d37d5b02ab93b40bb31234a9b2518a68222014a0eb9472be730b8b1c5990561&=&format=webp&quality=lossless')
        container.add_item(galeria_fabricacao)

        select = ui.Select(
            placeholder="Selecione o produto para fabricar...",
            options=[
                discord.SelectOption(
                    label=info['nome'],
                    description=f"Custo: R$ {info['custo']:,.2f}".replace(',', '.'),
                    value=produto_id,
                    emoji=info['emoji']
                )
                for produto_id, info in PRODUTOS.items()
            ]
        )
        select.callback = self.selecionar_produto

        container.add_item(ui.ActionRow(select))
        self.add_item(container)

    async def selecionar_produto(self, interaction: discord.Interaction):
        try:
            produto_id = interaction.data["values"][0]
            produto = PRODUTOS[produto_id]
            modal = QuantidadeModal(produto_id, produto, self.db)
            await interaction.response.send_modal(modal)
        except Exception as e:
            print(f"Erro ao selecionar produto: {e}")
            traceback.print_exc()
            try:
                await interaction.response.send_message(
                    f"{X} Ocorreu um erro ao processar a seleção. Tente novamente.",
                    ephemeral=True
                )
            except:
                pass


class FabricacaoCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = Database()
        print("Cog de Fabricação carregado com sucesso!")

    @app_commands.command(name='fabricacao', description='Iniciar processo de fabricação de produtos')
    async def fabricacao(self, interaction: discord.Interaction):
        try:
            canal_log_id = await self.db.get_canal_log(interaction.guild.id)

            if canal_log_id is None:
                await interaction.response.send_message(
                    f"{X} Canal de logs não configurado! Use {SETTINGS} `/config` para configurar primeiro.",
                    ephemeral=True
                )
                return

            view = FabricacaoView(self.db)
            await interaction.response.send_message(view=view)
            print(f"Painel de fabricação enviado por {interaction.user}")

        except Exception as e:
            print(f"Erro ao enviar painel de fabricação: {e}")
            traceback.print_exc()
            await interaction.response.send_message(
                f"{X} Erro ao enviar o painel de fabricação. Verifique as permissões do bot.",
                ephemeral=True
            )

    @fabricacao.error
    async def fabricacao_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        print(f"Erro no comando /fabricacao: {error}")
        traceback.print_exc()
        try:
            await interaction.response.send_message(
                f"{X} Ocorreu um erro ao executar o comando.",
                ephemeral=True
            )
        except:
            pass


async def setup(bot):
    try:
        cog = FabricacaoCog(bot)
        await cog.db.init_db()
        await bot.add_cog(cog)
        print("FabricacaoCog adicionado com sucesso!")
    except Exception as e:
        print(f"Erro ao carregar FabricacaoCog: {e}")
        traceback.print_exc()
