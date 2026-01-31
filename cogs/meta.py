import discord
from discord import ui, app_commands
from discord.ext import commands
from datetime import datetime
import traceback
from database import Database
from utils.emojis import CHECK, X, USER, SETTINGS, LIST


class MetaView(ui.LayoutView):
    def __init__(self, db: Database):
        super().__init__(timeout=None)
        self.db = db
        
        # Container principal
        container = ui.Container()
        container.add_item(ui.TextDisplay(f'# {CHECK} Registre sua Meta'))
        container.add_item(ui.Separator(spacing=discord.SeparatorSpacing.small))
        container.add_item(ui.TextDisplay(
            'Mande uma foto da meta entregue e em qual baú ou para quem foi mandado'
        ))
        container.add_item(ui.Separator(spacing=discord.SeparatorSpacing.small))
        
        
        # Botão para registrar meta
        botao_registrar = ui.Button(
            label="Registrar Meta",
            style=discord.ButtonStyle.secondary
        )
        botao_registrar.callback = self.registrar_meta
        
        galeria_meta = ui.MediaGallery()
        galeria_meta.add_item(media='https://media.discordapp.net/attachments/1366148719967211612/1465503657452765286/Cartel.png?ex=69795823&is=697806a3&hm=6d37d5b02ab93b40bb31234a9b2518a68222014a0eb9472be730b8b1c5990561&=&format=webp&quality=lossless')
        container.add_item(galeria_meta)

        linha = ui.ActionRow(botao_registrar)
        container.add_item(linha)

        self.add_item(container)
    
    async def registrar_meta(self, interaction: discord.Interaction):
        try:
            # Verificar se já tem canal aberto
            canal_existente = discord.utils.get(
                interaction.guild.text_channels,
                topic=f"Meta de {interaction.user.id}"
            )
            
            if canal_existente:
                await interaction.response.send_message(
                    f"⚠️ Você já possui um canal de meta aberto: {canal_existente.mention}",
                    ephemeral=True
                )
                return
            
            # Buscar configurações do banco
            config = await self.db.get_config_meta(interaction.guild.id)
            
            if not config:
                await interaction.response.send_message(
                    "⚠️ Sistema de metas não configurado! Peça a um administrador para usar `/config`.",
                    ephemeral=True
                )
                return
            
            cargo_gerente_id = config[1]  # cargo_gerente_id
            
            if not cargo_gerente_id:
                await interaction.response.send_message(
                    "⚠️ Cargo de gerente não configurado! Peça a um administrador para configurar.",
                    ephemeral=True
                )
                return
            
            cargo_gerente = interaction.guild.get_role(cargo_gerente_id)
            
            if not cargo_gerente:
                await interaction.response.send_message(
                    "⚠️ Cargo de gerente não encontrado! Peça a um administrador para reconfigurar.",
                    ephemeral=True
                )
                return
            
            await interaction.response.defer(ephemeral=True)
            
            # Criar canal privado
            overwrites = {
                interaction.guild.default_role: discord.PermissionOverwrite(read_messages=False),
                interaction.user: discord.PermissionOverwrite(
                    read_messages=True,
                    send_messages=True,
                    attach_files=True
                ),
                cargo_gerente: discord.PermissionOverwrite(
                    read_messages=True,
                    send_messages=True,
                    manage_messages=True
                ),
                interaction.guild.me: discord.PermissionOverwrite(
                    read_messages=True,
                    send_messages=True,
                    manage_channels=True
                )
            }
            
            # Adicionar permissão para administradores
            for role in interaction.guild.roles:
                if role.permissions.administrator:
                    overwrites[role] = discord.PermissionOverwrite(
                        read_messages=True,
                        send_messages=True,
                        manage_messages=True
                    )
            
            canal = await interaction.guild.create_text_channel(
                name=f"meta-{interaction.user.name}",
                topic=f"Meta de {interaction.user.id}",
                overwrites=overwrites,
                reason=f"Canal de meta criado para {interaction.user}"
            )
            
            # Registrar canal no banco
            await self.db.criar_canal_meta(
                guild_id=interaction.guild.id,
                canal_id=canal.id,
                user_id=interaction.user.id
            )
            
            # Enviar mensagem de boas-vindas no canal
            container_boas_vindas = ui.Container()
            container_boas_vindas.add_item(ui.TextDisplay(f'# {USER} Meta de {interaction.user.mention}'))
            container_boas_vindas.add_item(ui.Separator(spacing=discord.SeparatorSpacing.small))
            container_boas_vindas.add_item(ui.TextDisplay(
                f'Olá {interaction.user.mention}!\n\n'
                f'Este canal foi criado para você registrar sua meta.\n\n'
                f'**Instruções:**\n'
                f'• Envie a foto da meta entregue\n'
                f'• Informe em qual baú ou para quem foi enviada\n'
                f'• Aguarde a análise dos gerentes/administradores'
            ))
            container_boas_vindas.add_item(ui.Separator(spacing=discord.SeparatorSpacing.small))
            container_boas_vindas.add_item(ui.TextDisplay(
                f'**Gerentes:** {cargo_gerente.mention}\n'
                f'Vocês serão notificados quando a meta for enviada.'
            ))
            
            view_boas_vindas = ui.LayoutView()
            view_boas_vindas.add_item(container_boas_vindas)
            
            await canal.send(view=view_boas_vindas)
            
            # Confirmar para o usuário
            await interaction.followup.send(
                f"{CHECK} Canal criado com sucesso!\n"
                f"Acesse {canal.mention} para enviar sua meta.",
                ephemeral=True
            )
            
            print(f"Canal de meta criado para {interaction.user} no servidor {interaction.guild.name}")
            
        except discord.Forbidden:
            await interaction.followup.send(
                f"{X} Não tenho permissão para criar canais! Peça a um administrador para ajustar as permissões.",
                ephemeral=True
            )
        except Exception as e:
            print(f"Erro ao criar canal de meta: {e}")
            traceback.print_exc()
            try:
                await interaction.followup.send(
                    f"{X} Erro ao criar canal de meta. Tente novamente.",
                    ephemeral=True
                )
            except:
                pass


class AvaliacaoMetaView(ui.LayoutView):
    def __init__(self, db: Database, user_id: int, canal_meta_id: int, mensagem_meta: discord.Message):
        super().__init__()
        self.db = db
        self.user_id = user_id
        self.canal_meta_id = canal_meta_id
        self.mensagem_meta = mensagem_meta
        
        # Container
        container = ui.Container()
        container.add_item(ui.TextDisplay(f'# {CHECK} Avaliação de Meta'))
        container.add_item(ui.Separator(spacing=discord.SeparatorSpacing.small))
        container.add_item(ui.TextDisplay(
            'Gerentes e administradores, avaliem a meta enviada acima.\n\n'
            '**Ações disponíveis:**\n'
            f"• {CHECK} Aprovar - Dá o cargo e envia para o log\n"
            f"• {X} Reprovar - Fecha o canal sem dar o cargo"
        ))
        
        # Botões
        botao_aprovar = ui.Button(
            label="Aprovar Meta",
            emoji=CHECK,
            style=discord.ButtonStyle.success
        )
        botao_aprovar.callback = self.aprovar
        
        botao_reprovar = ui.Button(
            label="Reprovar Meta",
            emoji=X,
            style=discord.ButtonStyle.danger
        )
        botao_reprovar.callback = self.reprovar
        
        linha = ui.ActionRow(botao_aprovar, botao_reprovar)
        container.add_item(linha)
        
        self.add_item(container)
    
    async def aprovar(self, interaction: discord.Interaction):
        try:
            # Verificar permissões
            if not (interaction.user.guild_permissions.administrator or 
                    any(role.id == (await self.db.get_config_meta(interaction.guild.id))[1] 
                        for role in interaction.user.roles)):
                await interaction.response.send_message(
                    f"{X} Apenas administradores e gerentes podem aprovar metas!",
                    ephemeral=True
                )
                return
            
            # Desabilitar botões
            for item in self.children:
                if isinstance(item, ui.Container):
                    for comp in item.children:
                        if isinstance(comp, ui.ActionRow):
                            for btn in comp.children:
                                if isinstance(btn, ui.Button):
                                    btn.disabled = True
            
            await interaction.response.edit_message(view=self)
            
            # Buscar configurações
            config = await self.db.get_config_meta(interaction.guild.id)
            cargo_meta_id = config[2]  # cargo_meta_paga_id
            canal_log_id = config[3]  # canal_log_meta_id
            
            user = interaction.guild.get_member(self.user_id)
            
            if not user:
                await interaction.followup.send(
                    "⚠️ Usuário não encontrado no servidor!",
                    ephemeral=True
                )
                return
            
            # Dar cargo de meta paga
            if cargo_meta_id:
                cargo = interaction.guild.get_role(cargo_meta_id)
                if cargo:
                    await user.add_roles(cargo, reason=f"Meta aprovada por {interaction.user}")
            
            # Enviar para o canal de logs
            if canal_log_id:
                canal_log = interaction.guild.get_channel(canal_log_id)
                if canal_log:
                    # Criar log da meta aprovada
                    container_log = ui.Container()
                    container_log.add_item(ui.TextDisplay(f"# {LIST} {CHECK} Meta Aprovada"))
                    container_log.add_item(ui.Separator(spacing=discord.SeparatorSpacing.small))
                    container_log.add_item(ui.TextDisplay(f"**{USER} Usuário:** {user.mention} (ID: {user.id})"))
                    container_log.add_item(ui.TextDisplay(f"**{CHECK} Aprovado por:** {interaction.user.mention}"))
                    container_log.add_item(ui.TextDisplay(f"**Data:** {datetime.now().strftime('%d/%m/%Y às %H:%M:%S')}"))
                    container_log.add_item(ui.Separator(spacing=discord.SeparatorSpacing.small))
                    
                    # Adicionar conteúdo da mensagem original
                    if self.mensagem_meta.content:
                        container_log.add_item(ui.TextDisplay(f"**Descrição:**\n{self.mensagem_meta.content}"))
                    
                    
                    view_log = ui.LayoutView()
                    view_log.add_item(container_log)
                    
                    # Enviar texto e anexos
                    files = []
                    if self.mensagem_meta.attachments:
                        for attachment in self.mensagem_meta.attachments:
                            try:
                                file = await attachment.to_file()
                                files.append(file)
                            except:
                                pass
                    
                    await canal_log.send(view=view_log, files=files if files else None)
            
            # Registrar no banco
            await self.db.registrar_meta_aprovada(
                guild_id=interaction.guild.id,
                user_id=self.user_id,
                aprovado_por_id=interaction.user.id,
                descricao=self.mensagem_meta.content or "Sem descrição"
            )
            
            # Notificar usuário
            try:
                await user.send(
                f"{CHECK} **Parabéns!** Sua meta foi aprovada por {interaction.user.mention}!\n"
                    f"Você recebeu o cargo de meta paga."
                )
            except:
                pass
            
            # Fechar canal após 5 segundos
            await interaction.followup.send(
                f"{CHECK} Meta aprovada com sucesso!\n"
                f"Este canal será fechado em 5 segundos..."
            )
            
            await self.db.fechar_canal_meta(self.canal_meta_id)
            
            import asyncio
            await asyncio.sleep(5)
            
            canal = interaction.guild.get_channel(self.canal_meta_id)
            if canal:
                await canal.delete(reason=f"Meta aprovada por {interaction.user}")
            
        except Exception as e:
            print(f"Erro ao aprovar meta: {e}")
            traceback.print_exc()
            await interaction.followup.send(
                f"{X} Erro ao aprovar meta. Tente novamente.",
                ephemeral=True
            )
    
    async def reprovar(self, interaction: discord.Interaction):
        try:
            # Verificar permissões
            if not (interaction.user.guild_permissions.administrator or 
                    any(role.id == (await self.db.get_config_meta(interaction.guild.id))[1] 
                        for role in interaction.user.roles)):
                await interaction.response.send_message(
                    f"{X} Apenas administradores e gerentes podem reprovar metas!",
                    ephemeral=True
                )
                return
            
            # Desabilitar botões
            for item in self.children:
                if isinstance(item, ui.Container):
                    for comp in item.children:
                        if isinstance(comp, ui.ActionRow):
                            for btn in comp.children:
                                if isinstance(btn, ui.Button):
                                    btn.disabled = True
            
            await interaction.response.edit_message(view=self)
            
            user = interaction.guild.get_member(self.user_id)
            
            # Notificar usuário
            if user:
                try:
                    await user.send(
                        f"{X} Sua meta foi reprovada por {interaction.user.mention}.\n"
                        f"Entre em contato com a administração para mais informações."
                    )
                except:
                    pass
            
            # Fechar canal
            await interaction.followup.send(
                f"{X} Meta reprovada.\n"
                f"Este canal será fechado em 5 segundos..."
            )
            
            await self.db.fechar_canal_meta(self.canal_meta_id)
            
            import asyncio
            await asyncio.sleep(5)
            
            canal = interaction.guild.get_channel(self.canal_meta_id)
            if canal:
                await canal.delete(reason=f"Meta reprovada por {interaction.user}")
            
        except Exception as e:
            print(f"Erro ao reprovar meta: {e}")
            traceback.print_exc()


class MetaCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = Database()
        print("Cog de Meta carregado com sucesso!")
    
    @app_commands.command(name='meta', description='Envia o painel de registro de metas')
    @app_commands.checks.has_permissions(administrator=True)
    async def meta(self, interaction: discord.Interaction):
        try:
            # Verificar configuração
            config = await self.db.get_config_meta(interaction.guild.id)
            
            if not config or not config[1]:  # Verifica se cargo_gerente está configurado
                await interaction.response.send_message(
                    "⚠️ Sistema de metas não configurado!\n"
                    "Use `/config cargo_gerente:@Gerente cargo_meta:@MetaPaga canal_log_meta:#logs`",
                    ephemeral=True
                )
                return
            
            view = MetaView(self.db)
            await interaction.response.send_message(view=view)
            print(f"Painel de meta enviado por {interaction.user}")
            
        except Exception as e:
            print(f"Erro ao enviar painel de meta: {e}")
            traceback.print_exc()
            await interaction.response.send_message(
                f"{X} Erro ao enviar o painel de meta. Verifique as permissões do bot.",
                ephemeral=True
            )
    
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Detecta quando um usuário envia uma mensagem no canal de meta"""
        try:
            # Ignorar mensagens do bot
            if message.author.bot:
                return
            
            # Verificar se é um canal de meta
            if not message.channel.topic or not message.channel.topic.startswith("Meta de "):
                return
            
            # Extrair user_id do tópico
            try:
                user_id = int(message.channel.topic.replace("Meta de ", ""))
            except:
                return
            
            # Verificar se é o dono do canal enviando
            if message.author.id != user_id:
                return
            
            # Verificar se tem anexo (foto)
            if not message.attachments:
                await message.reply(
                    "⚠️ Por favor, envie uma foto da meta juntamente com a descrição!",
                    delete_after=10
                )
                return
            
            # Criar view de avaliação
            view = AvaliacaoMetaView(self.db, user_id, message.channel.id, message)
            
            await message.reply(view=view)
            
            # Notificar gerentes
            config = await self.db.get_config_meta(message.guild.id)
            if config and config[1]:
                cargo_gerente = message.guild.get_role(config[1])
                if cargo_gerente:
                    await message.channel.send(
                        f"{LIST} {SETTINGS} {cargo_gerente.mention} - Nova meta enviada para avaliação!"
                    )
            
        except Exception as e:
            print(f"Erro ao processar mensagem de meta: {e}")
            traceback.print_exc()
    
    @meta.error
    async def meta_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message(
                f"{X} Você não tem permissão para usar este comando! Apenas administradores.",
                ephemeral=True
            )


async def setup(bot):
    try:
        cog = MetaCog(bot)
        await cog.db.init_db()
        await bot.add_cog(cog)
        print("MetaCog adicionado com sucesso!")
    except Exception as e:
        print(f"Erro ao carregar MetaCog: {e}")
        traceback.print_exc()
