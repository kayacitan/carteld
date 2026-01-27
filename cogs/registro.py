import discord
from discord import ui, app_commands
from discord.ext import commands
import traceback
from database import Database

# --- O MODAL DE PREENCHIMENTO ---
class ModalRegistro(ui.Modal, title='📋 Complete seu Registro'):
    def __init__(self, db: Database):
        super().__init__()
        self.db = db
    nome = ui.TextInput(
        label='Nome (até 10 letras)',
        placeholder='Digite seu nome...',
        required=True,
        max_length=10,
        min_length=2
    )
    
    # Campo para o RG (até 5 números)
    rg = ui.TextInput(
        label='RG (até 5 números)',
        placeholder='Ex: 12345',
        required=True,
        max_length=5,
        min_length=1
    )
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            # Validação: Verifica se o nome contém apenas letras
            if not self.nome.value.isalpha():
                await interaction.response.send_message(
                    "❌ O nome deve conter apenas letras!", 
                    ephemeral=True
                )
                return
            
            # Validação: Verifica se o RG contém apenas números
            if not self.rg.value.isdigit():
                await interaction.response.send_message(
                    "❌ O RG deve conter apenas números!", 
                    ephemeral=True
                )
                return
            
            # Busca o canal de logs
            canal_log_id = await self.db.get_canal_log(interaction.guild.id)
            if not canal_log_id:
                await interaction.response.send_message(
                    "⚠️ Canal de logs não configurado! Use `/config` para configurar.",
                    ephemeral=True
                )
                return

            canal_logs = interaction.guild.get_channel(canal_log_id)
            
            if canal_logs is None:
                await interaction.response.send_message(
                    "⚠️ Erro: Canal de logs não encontrado! Avise um administrador.", 
                    ephemeral=True
                )
                return
            
            # Cria a view de aprovação com custom_id para persistência
            view_aprovacao = AprovacaoView(
                db=self.db,
                user_id=interaction.user.id,
                nome=self.nome.value,
                rg=self.rg.value
            )
            
            # Cria o embed com as informações do registro
            embed = discord.Embed(
                title="📝 Nova Solicitação de Registro",
                color=discord.Color.yellow(),
                timestamp=discord.utils.utcnow()
            )
            embed.add_field(name="👤 Usuário", value=interaction.user.mention, inline=True)
            embed.add_field(name="📛 Nome Informado", value=self.nome.value, inline=True)
            embed.add_field(name="🆔 RG", value=self.rg.value, inline=True)
            embed.set_thumbnail(url=interaction.user.display_avatar.url)
            embed.set_footer(text=f"ID do Usuário: {interaction.user.id}")
            
            # Envia para o canal de logs
            await canal_logs.send(embed=embed, view=view_aprovacao)
            
            # Confirma para o usuário
            await interaction.response.send_message(
                "✅ Sua solicitação foi enviada para análise! Aguarde a aprovação dos administradores.",
                ephemeral=True
            )
            
        except discord.Forbidden:
            await interaction.response.send_message(
                "⚠️ Não tenho permissão para enviar mensagens no canal de logs!",
                ephemeral=True
            )
        except Exception as e:
            print(f"Erro no modal de registro: {e}")
            traceback.print_exc()
            try:
                await interaction.response.send_message(
                    f"❌ Ocorreu um erro ao processar seu registro. Tente novamente ou contate um administrador.",
                    ephemeral=True
                )
            except:
                pass
    
    async def on_error(self, interaction: discord.Interaction, error: Exception):
        print(f"Erro no modal: {error}")
        traceback.print_exc()
        try:
            await interaction.response.send_message(
                "❌ Ocorreu um erro ao processar o formulário. Tente novamente.",
                ephemeral=True
            )
        except:
            pass

# --- VIEW DE APROVAÇÃO (PARA ADMINS) ---
class AprovacaoView(ui.View):
    def __init__(self, db: Database, user_id: int, nome: str, rg: str):
        super().__init__(timeout=None)  # Não expira
        self.db = db
        self.user_id = user_id
        self.nome = nome
        self.rg = rg
    
    @ui.button(label="✅ Aprovar", style=discord.ButtonStyle.success, custom_id="aprovar_registro")
    async def aprovar(self, interaction: discord.Interaction, button: ui.Button):
        try:
            # Verifica se quem clicou é admin
            if not interaction.user.guild_permissions.administrator:
                await interaction.response.send_message(
                    "❌ Você não tem permissão para aprovar registros!", 
                    ephemeral=True
                )
                return
            
            # Busca o usuário
            user = interaction.guild.get_member(self.user_id)
            if user is None:
                await interaction.response.send_message(
                    "⚠️ Erro: Usuário não encontrado no servidor! Ele pode ter saído.",
                    ephemeral=True
                )
                return
            
            # Busca o cargo
            cargo_membro_id, _ = await self.db.get_cargos_boasvindas(interaction.guild.id)
            if not cargo_membro_id:
                await interaction.response.send_message(
                    "⚠️ Cargo de membro não configurado! Use `/config`.",
                    ephemeral=True
                )
                return

            cargo = interaction.guild.get_role(int(cargo_membro_id))
            
            if cargo is None:
                await interaction.response.send_message(
                    "⚠️ Erro: Cargo não encontrado! Verifique o ID configurado no código.",
                    ephemeral=True
                )
                return
            
            # Verifica se o usuário já tem o cargo
            if cargo in user.roles:
                await interaction.response.send_message(
                    "⚠️ Este usuário já possui o cargo de membro!",
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
            embed.title = "✅ Registro Aprovado"
            embed.add_field(
                name="📋 Aprovado por", 
                value=interaction.user.mention, 
                inline=False
            )
            embed.timestamp = discord.utils.utcnow()
            
            # Desabilita os botões
            for item in self.children:
                item.disabled = True
            
            await interaction.response.edit_message(embed=embed, view=self)
            
            # Notifica o usuário
            try:
                await user.send(
                    f"🎉 **Parabéns!** Seu registro foi aprovado por {interaction.user.mention}!\n"
                    f"Você agora tem acesso completo ao servidor."
                )
            except discord.Forbidden:
                pass  # Usuário tem DM desabilitada
            except Exception as e:
                print(f"Erro ao enviar DM: {e}")
                    
        except discord.Forbidden:
            await interaction.response.send_message(
                "⚠️ Não tenho permissão para modificar este usuário! Verifique a hierarquia de cargos.",
                ephemeral=True
            )
        except Exception as e:
            print(f"Erro ao aprovar registro: {e}")
            traceback.print_exc()
            await interaction.response.send_message(
                f"❌ Erro ao aprovar registro: {str(e)}",
                ephemeral=True
            )
    
    @ui.button(label="❌ Negar", style=discord.ButtonStyle.danger, custom_id="negar_registro")
    async def negar(self, interaction: discord.Interaction, button: ui.Button):
        try:
            # Verifica se quem clicou é admin
            if not interaction.user.guild_permissions.administrator:
                await interaction.response.send_message(
                    "❌ Você não tem permissão para negar registros!", 
                    ephemeral=True
                )
                return
            
            # Busca o usuário
            user = interaction.guild.get_member(self.user_id)
            
            # Atualiza o embed
            embed = interaction.message.embeds[0]
            embed.color = discord.Color.red()
            embed.title = "❌ Registro Negado"
            embed.add_field(
                name="📋 Negado por", 
                value=interaction.user.mention, 
                inline=False
            )
            embed.timestamp = discord.utils.utcnow()
            
            # Desabilita os botões
            for item in self.children:
                item.disabled = True
            
            await interaction.response.edit_message(embed=embed, view=self)
            
            # Notifica o usuário se ele ainda estiver no servidor
            if user:
                try:
                    await user.send(
                        f"😔 Infelizmente seu registro foi negado por {interaction.user.mention}.\n"
                        f"Entre em contato com a administração para mais informações."
                    )
                except discord.Forbidden:
                    pass  # Usuário tem DM desabilitada
                except Exception as e:
                    print(f"Erro ao enviar DM: {e}")
                    
        except Exception as e:
            print(f"Erro ao negar registro: {e}")
            traceback.print_exc()
            await interaction.response.send_message(
                f"❌ Erro ao negar registro: {str(e)}",
                ephemeral=True
            )


# --- VIEW DO PAINEL DE REGISTRO COM LAYOUTVIEW ---
class RegistroView(ui.LayoutView):
    def __init__(self, db: Database):
        super().__init__()
        self.db = db
        
        # Container
        container = ui.Container()
        container.add_item(ui.TextDisplay('# 📋 Registro Oficial'))
        container.add_item(ui.Separator(spacing=discord.SeparatorSpacing.small))
        container.add_item(ui.TextDisplay('Clique no botão abaixo para iniciar seu registro!'))
        container.add_item(ui.Separator(spacing=discord.SeparatorSpacing.small))
        galeria_registro = ui.MediaGallery()
        galeria_registro.add_item(media='https://media.discordapp.net/attachments/1366148719967211612/1465503657452765286/Cartel.png?ex=69795823&is=697806a3&hm=6d37d5b02ab93b40bb31234a9b2518a68222014a0eb9472be730b8b1c5990561&=&format=webp&quality=lossless')
        container.add_item(galeria_registro)
        
        # ✅ BOTÃO DENTRO DE ACTIONROW DENTRO DO CONTAINER
        botao_registrar = ui.Button(
            label="Novo Membro",
            style=discord.ButtonStyle.secondary
        )
        botao_registrar.callback = self.abrir_modal
        
        linha = ui.ActionRow(botao_registrar)
        container.add_item(linha)  # ✅ ActionRow vai para dentro do Container!
        
        # Adiciona o container completo
        self.add_item(container)

    async def abrir_modal(self, interaction: discord.Interaction):
        try:
            # Verifica se já tem o cargo (segurança)
            cargo_membro_id, _ = await self.db.get_cargos_boasvindas(interaction.guild.id)
            cargo = interaction.guild.get_role(int(cargo_membro_id)) if cargo_membro_id else None
            if cargo and cargo in interaction.user.roles:
                await interaction.response.send_message(
                    "Ei, você já está registrado! 😎", 
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
                    "❌ Ocorreu um erro ao abrir o formulário. Tente novamente.",
                    ephemeral=True
                )
            except:
                pass


# --- A ENGRENAGEM (COG) ---
class RegistroCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = Database()
        # Adiciona a view de aprovação persistente
        self.bot.add_view(AprovacaoView(self.db, user_id=0, nome="", rg=""))
        print("✅ Cog de Registro carregado com sucesso!")

    @app_commands.command(name='registro', description='Envia o painel de registro')
    @app_commands.checks.has_permissions(administrator=True)
    async def enviar_registro(self, interaction: discord.Interaction):
        try:
            view = RegistroView(self.db)
            await interaction.response.send_message(view=view)
            print(f"✅ Painel de registro enviado por {interaction.user}")
            
        except Exception as e:
            print(f"Erro ao enviar painel de registro: {e}")
            traceback.print_exc()
            await interaction.response.send_message(
                "❌ Erro ao enviar o painel de registro. Verifique as permissões do bot.",
                ephemeral=True
            )
    
    @enviar_registro.error
    async def enviar_registro_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message(
                "❌ Você não tem permissão para usar este comando! Apenas administradores podem criar painéis de registro.",
                ephemeral=True
            )
        else:
            print(f"Erro no comando /registro: {error}")
            traceback.print_exc()
            try:
                await interaction.response.send_message(
                    "❌ Ocorreu um erro ao executar o comando.",
                    ephemeral=True
                )
            except:
                pass

async def setup(bot):
    try:
        await bot.add_cog(RegistroCog(bot))
        print("✅ RegistroCog adicionado com sucesso!")
    except Exception as e:
        print(f"❌ Erro ao carregar RegistroCog: {e}")
        traceback.print_exc()
