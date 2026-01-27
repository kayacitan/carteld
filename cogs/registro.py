import discord
from discord import ui, app_commands
from discord.ext import commands
import traceback
from database import Database

# --- O MODAL DE PREENCHIMENTO ---
class ModalRegistro(ui.Modal, title='ðŸ“‹ Complete seu Registro'):
    def __init__(self, db: Database):
        super().__init__()
        self.db = db
    nome = ui.TextInput(
        label='Nome (atÃ© 10 letras)',
        placeholder='Digite seu nome...',
        required=True,
        max_length=10,
        min_length=2
    )
    
    # Campo para o RG (atÃ© 5 nÃºmeros)
    rg = ui.TextInput(
        label='RG (atÃ© 5 nÃºmeros)',
        placeholder='Ex: 12345',
        required=True,
        max_length=5,
        min_length=1
    )
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            # ValidaÃ§Ã£o: Verifica se o nome contÃ©m apenas letras
            if not self.nome.value.isalpha():
                await interaction.response.send_message(
                    "âŒ O nome deve conter apenas letras!", 
                    ephemeral=True
                )
                return
            
            # ValidaÃ§Ã£o: Verifica se o RG contÃ©m apenas nÃºmeros
            if not self.rg.value.isdigit():
                await interaction.response.send_message(
                    "âŒ O RG deve conter apenas nÃºmeros!", 
                    ephemeral=True
                )
                return
            
            # Busca o canal de logs
            canal_log_id = await self.db.get_canal_log(interaction.guild.id)
            if not canal_log_id:
                await interaction.response.send_message(
                    "âš ï¸ Canal de logs nÃ£o configurado! Use `/config` para configurar.",
                    ephemeral=True
                )
                return

            canal_logs = interaction.guild.get_channel(canal_log_id)
            
            if canal_logs is None:
                await interaction.response.send_message(
                    "âš ï¸ Erro: Canal de logs nÃ£o encontrado! Avise um administrador.", 
                    ephemeral=True
                )
                return
            
            # Cria a view de aprovaÃ§Ã£o com custom_id para persistÃªncia
            view_aprovacao = AprovacaoView(
                db=self.db,
                user_id=interaction.user.id,
                nome=self.nome.value,
                rg=self.rg.value
            )
            
            # Cria o embed com as informaÃ§Ãµes do registro
            embed = discord.Embed(
                title="ðŸ“ Nova SolicitaÃ§Ã£o de Registro",
                color=discord.Color.yellow(),
                timestamp=discord.utils.utcnow()
            )
            embed.add_field(name="ðŸ‘¤ UsuÃ¡rio", value=interaction.user.mention, inline=True)
            embed.add_field(name="ðŸ“› Nome Informado", value=self.nome.value, inline=True)
            embed.add_field(name="ðŸ†” RG", value=self.rg.value, inline=True)
            embed.set_thumbnail(url=interaction.user.display_avatar.url)
            embed.set_footer(text=f"ID do UsuÃ¡rio: {interaction.user.id}")
            
            # Envia para o canal de logs
            mensagem = await canal_logs.send(embed=embed, view=view_aprovacao)
            view_aprovacao.message_id = mensagem.id

            # Persiste o registro para que os botões sobrevivam a reinícios
            await self.db.criar_registro_pendente(
                message_id=mensagem.id,
                guild_id=interaction.guild.id,
                user_id=interaction.user.id,
                nome=self.nome.value,
                rg=self.rg.value,
            )
            
            # Confirma para o usuÃ¡rio
            await interaction.response.send_message(
                "âœ… Sua solicitaÃ§Ã£o foi enviada para anÃ¡lise! Aguarde a aprovaÃ§Ã£o dos administradores.",
                ephemeral=True
            )
            
        except discord.Forbidden:
            await interaction.response.send_message(
                "âš ï¸ NÃ£o tenho permissÃ£o para enviar mensagens no canal de logs!",
                ephemeral=True
            )
        except Exception as e:
            print(f"Erro no modal de registro: {e}")
            traceback.print_exc()
            try:
                await interaction.response.send_message(
                    f"âŒ Ocorreu um erro ao processar seu registro. Tente novamente ou contate um administrador.",
                    ephemeral=True
                )
            except:
                pass
    
    async def on_error(self, interaction: discord.Interaction, error: Exception):
        print(f"Erro no modal: {error}")
        traceback.print_exc()
        try:
            await interaction.response.send_message(
                "âŒ Ocorreu um erro ao processar o formulÃ¡rio. Tente novamente.",
                ephemeral=True
            )
        except:
            pass

# --- VIEW DE APROVAÃ‡ÃƒO (PARA ADMINS) ---
class AprovacaoView(ui.View):
    def __init__(self, db: Database, user_id: int, nome: str, rg: str, message_id: int = None):
        super().__init__(timeout=None)  # NÃ£o expira
        self.db = db
        self.user_id = user_id
        self.nome = nome
        self.rg = rg
        self.message_id = message_id

    @ui.button(label="âœ… Aprovar", style=discord.ButtonStyle.success, custom_id="aprovar_registro")
    async def aprovar(self, interaction: discord.Interaction, button: ui.Button):
        try:
            message_id = interaction.message.id

            # Reidrata dados do registro caso o bot tenha reiniciado
            if (not self.user_id) or (self.user_id == 0) or (self.message_id and self.message_id != message_id):
                registro = await self.db.obter_registro_pendente_por_mensagem(message_id)
                if not registro or registro[5] != 'pendente':
                    await interaction.response.send_message(
                        "âš ï¸ Este registro nÃ£o estÃ¡ mais pendente.",
                        ephemeral=True
                    )
                    return
                _, _, self.user_id, self.nome, self.rg, _ = registro
                self.message_id = message_id

            # Verifica se quem clicou Ã© admin
            if not interaction.user.guild_permissions.administrator:
                await interaction.response.send_message(
                    "âŒ VocÃª nÃ£o tem permissÃ£o para aprovar registros!", 
                    ephemeral=True
                )
                return
            
            # Busca o usuÃ¡rio
            user = interaction.guild.get_member(self.user_id)
            if user is None:
                await interaction.response.send_message(
                    "âš ï¸ Erro: UsuÃ¡rio nÃ£o encontrado no servidor! Ele pode ter saÃ­do.",
                    ephemeral=True
                )
                return
            
            # Busca o cargo
            cargo_membro_id, _ = await self.db.get_cargos_boasvindas(interaction.guild.id)
            if not cargo_membro_id:
                await interaction.response.send_message(
                    "âš ï¸ Cargo de membro nÃ£o configurado! Use `/config`.",
                    ephemeral=True
                )
                return

            cargo = interaction.guild.get_role(int(cargo_membro_id))
            
            if cargo is None:
                await interaction.response.send_message(
                    "âš ï¸ Erro: Cargo nÃ£o encontrado! Verifique o ID configurado no cÃ³digo.",
                    ephemeral=True
                )
                return
            
            # Verifica se o usuÃ¡rio jÃ¡ tem o cargo
            if cargo in user.roles:
                await interaction.response.send_message(
                    "âš ï¸ Este usuÃ¡rio jÃ¡ possui o cargo de membro!",
                    ephemeral=True
                )
                return
            
            # Adiciona o cargo
            await user.add_roles(cargo, reason=f"Registro aprovado por {interaction.user}")
            
            # Troca o nickname
            await user.edit(nick=self.nome, reason=f"Registro aprovado por {interaction.user}")
            
            # Atualiza o embed
            embed = interaction.message.embeds[0]
            embed.color = discord.Color.green()
            embed.title = "âœ… Registro Aprovado"
            embed.add_field(
                name="ðŸ“‹ Aprovado por", 
                value=interaction.user.mention, 
                inline=False
            )
            embed.timestamp = discord.utils.utcnow()
            
            # Desabilita os botÃµes
            for item in self.children:
                item.disabled = True
            
            await interaction.response.edit_message(embed=embed, view=self)

            # Marca como resolvido no banco (persistÃªncia)
            await self.db.resolver_registro_pendente(
                message_id=message_id,
                resolvido_por_id=interaction.user.id,
                resultado="aprovado",
            )
            
            # Notifica o usuÃ¡rio
            try:
                await user.send(
                    f"ðŸŽ‰ **ParabÃ©ns!** Seu registro foi aprovado por {interaction.user.mention}!\n"
                    f"VocÃª agora tem acesso completo ao servidor."
                )
            except discord.Forbidden:
                pass  # UsuÃ¡rio tem DM desabilitada
            except Exception as e:
                print(f"Erro ao enviar DM: {e}")
                    
        except discord.Forbidden:
            await interaction.response.send_message(
                "âš ï¸ NÃ£o tenho permissÃ£o para modificar este usuÃ¡rio! Verifique a hierarquia de cargos.",
                ephemeral=True
            )
        except Exception as e:
            print(f"Erro ao aprovar registro: {e}")
            traceback.print_exc()
            await interaction.response.send_message(
                f"âŒ Erro ao aprovar registro: {str(e)}",
                ephemeral=True
            )
    
    @ui.button(label="âŒ Negar", style=discord.ButtonStyle.danger, custom_id="negar_registro")
    async def negar(self, interaction: discord.Interaction, button: ui.Button):
        try:
            message_id = interaction.message.id

            # Reidrata dados do registro caso o bot tenha reiniciado
            if (not self.user_id) or (self.user_id == 0) or (self.message_id and self.message_id != message_id):
                registro = await self.db.obter_registro_pendente_por_mensagem(message_id)
                if not registro or registro[5] != 'pendente':
                    await interaction.response.send_message(
                        "âš ï¸ Este registro nÃ£o estÃ¡ mais pendente.",
                        ephemeral=True
                    )
                    return
                _, _, self.user_id, self.nome, self.rg, _ = registro
                self.message_id = message_id

            # Verifica se quem clicou Ã© admin
            if not interaction.user.guild_permissions.administrator:
                await interaction.response.send_message(
                    "âŒ VocÃª nÃ£o tem permissÃ£o para negar registros!", 
                    ephemeral=True
                )
                return
            
            # Busca o usuÃ¡rio
            user = interaction.guild.get_member(self.user_id)
            
            # Atualiza o embed
            embed = interaction.message.embeds[0]
            embed.color = discord.Color.red()
            embed.title = "âŒ Registro Negado"
            embed.add_field(
                name="ðŸ“‹ Negado por", 
                value=interaction.user.mention, 
                inline=False
            )
            embed.timestamp = discord.utils.utcnow()
            
            # Desabilita os botÃµes
            for item in self.children:
                item.disabled = True
            
            await interaction.response.edit_message(embed=embed, view=self)

            # Marca como resolvido no banco (persistÃªncia)
            await self.db.resolver_registro_pendente(
                message_id=message_id,
                resolvido_por_id=interaction.user.id,
                resultado="negado",
            )
            
            # Notifica o usuÃ¡rio se ele ainda estiver no servidor
            if user:
                try:
                    await user.send(
                        f"ðŸ˜” Infelizmente seu registro foi negado por {interaction.user.mention}.\n"
                        f"Entre em contato com a administraÃ§Ã£o para mais informaÃ§Ãµes."
                    )
                except discord.Forbidden:
                    pass  # UsuÃ¡rio tem DM desabilitada
                except Exception as e:
                    print(f"Erro ao enviar DM: {e}")
                    
        except Exception as e:
            print(f"Erro ao negar registro: {e}")
            traceback.print_exc()
            await interaction.response.send_message(
                f"âŒ Erro ao negar registro: {str(e)}",
                ephemeral=True
            )


# --- VIEW DO PAINEL DE REGISTRO COM LAYOUTVIEW ---
class RegistroView(ui.LayoutView):
    def __init__(self, db: Database):
        super().__init__(timeout=None)
        self.db = db
        
        # Container
        container = ui.Container()
        container.add_item(ui.TextDisplay('# ðŸ“‹ Registro Oficial'))
        container.add_item(ui.Separator(spacing=discord.SeparatorSpacing.small))
        container.add_item(ui.TextDisplay('Clique no botÃ£o abaixo para iniciar seu registro!'))
        container.add_item(ui.Separator(spacing=discord.SeparatorSpacing.small))
        galeria_registro = ui.MediaGallery()
        galeria_registro.add_item(media='https://media.discordapp.net/attachments/1366148719967211612/1465503657452765286/Cartel.png?ex=69795823&is=697806a3&hm=6d37d5b02ab93b40bb31234a9b2518a68222014a0eb9472be730b8b1c5990561&=&format=webp&quality=lossless')
        container.add_item(galeria_registro)
        
        # âœ… BOTÃƒO DENTRO DE ACTIONROW DENTRO DO CONTAINER
        botao_registrar = ui.Button(
            label="Novo Membro",
            style=discord.ButtonStyle.secondary,
            custom_id='registro_novo_membro'
        )
        botao_registrar.callback = self.abrir_modal
        
        linha = ui.ActionRow(botao_registrar)
        container.add_item(linha)  # âœ… ActionRow vai para dentro do Container!
        
        # Adiciona o container completo
        self.add_item(container)

    async def abrir_modal(self, interaction: discord.Interaction):
        try:
            # Verifica se jÃ¡ tem o cargo (seguranÃ§a)
            cargo_membro_id, _ = await self.db.get_cargos_boasvindas(interaction.guild.id)
            cargo = interaction.guild.get_role(int(cargo_membro_id)) if cargo_membro_id else None
            if cargo and cargo in interaction.user.roles:
                await interaction.response.send_message(
                    "Ei, vocÃª jÃ¡ estÃ¡ registrado! ðŸ˜Ž", 
                    ephemeral=True
                )
                return
            
            # Abre o modal para preencher dados
            modal = ModalRegistro(self.db)
            await interaction.response.send_modal(modal)
            
        except Exception as e:
            print(f"Erro ao abrir modal: {e}")
            traceback.print_exc()
            try:
                await interaction.response.send_message(
                    "âŒ Ocorreu um erro ao abrir o formulÃ¡rio. Tente novamente.",
                    ephemeral=True
                )
            except:
                pass


# --- A ENGRENAGEM (COG) ---
class RegistroCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = Database()
        self.bot.add_view(RegistroView(self.db))
        print("âœ… Cog de Registro carregado com sucesso!")

    async def cog_load(self):
        # Garante que o banco esteja pronto e re-registra aprovaÃ§Ãµes pendentes
        await self.db.init_db()
        pendentes = await self.db.listar_registros_pendentes()
        for message_id, _guild_id, user_id, nome, rg in pendentes:
            view = AprovacaoView(self.db, user_id=user_id, nome=nome, rg=rg, message_id=message_id)
            self.bot.add_view(view, message_id=message_id)
        if pendentes:
            print(f"âœ… Views de aprovaÃ§Ã£o reidratadas: {len(pendentes)} pendente(s).")

    @app_commands.command(name='registro', description='Envia o painel de registro')
    @app_commands.checks.has_permissions(administrator=True)
    async def enviar_registro(self, interaction: discord.Interaction):
        try:
            view = RegistroView(self.db)
            await interaction.response.send_message(view=view)
            print(f"âœ… Painel de registro enviado por {interaction.user}")
            
        except Exception as e:
            print(f"Erro ao enviar painel de registro: {e}")
            traceback.print_exc()
            await interaction.response.send_message(
                "âŒ Erro ao enviar o painel de registro. Verifique as permissÃµes do bot.",
                ephemeral=True
            )
    
    @enviar_registro.error
    async def enviar_registro_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message(
                "âŒ VocÃª nÃ£o tem permissÃ£o para usar este comando! Apenas administradores podem criar painÃ©is de registro.",
                ephemeral=True
            )
        else:
            print(f"Erro no comando /registro: {error}")
            traceback.print_exc()
            try:
                await interaction.response.send_message(
                    "âŒ Ocorreu um erro ao executar o comando.",
                    ephemeral=True
                )
            except:
                pass

async def setup(bot):
    try:
        await bot.add_cog(RegistroCog(bot))
        print("âœ… RegistroCog adicionado com sucesso!")
    except Exception as e:
        print(f"âŒ Erro ao carregar RegistroCog: {e}")
        traceback.print_exc()

