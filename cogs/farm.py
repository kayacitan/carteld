import discord
from discord import ui, app_commands
from discord.ext import commands
import traceback
from database import Database
from utils.emojis import CHECK, X, SETTINGS, USER, STORE, LIST, EYE, TRASH, FOLDER, TOGGLE_OFF, TOGGLE_ON


FREQ_OPTIONS = [
    ("daily", "Diária"),
    ("weekly", "Semanal"),
    ("monthly", "Mensal"),
]


def _freq_label(value: str | None) -> str:
    for k, v in FREQ_OPTIONS:
        if k == value:
            return v
    return "Não definido"


def _bool_label(value: int | None) -> str:
    return "Ativo" if int(value or 0) == 1 else "Inativo"


async def _get_farm_config(db: Database, guild_id: int):
    row = await db.get_farm_config(guild_id)
    if not row:
        return {
            "enabled": 0,
            "approver_role_id": None,
            "meta_freq": None,
            "meta_desc": None,
            "meta_qty": None,
            "meta_tipo": None,
        }
    _guild_id, enabled, approver_role_id, meta_freq, meta_desc, meta_qty, meta_tipo = row
    return {
        "enabled": int(enabled or 0),
        "approver_role_id": approver_role_id,
        "meta_freq": meta_freq,
        "meta_desc": meta_desc,
        "meta_qty": meta_qty,
        "meta_tipo": meta_tipo,
    }


def _build_meta_text(cfg: dict) -> str:
    desc = cfg.get("meta_desc") or "Não definida"
    qty = cfg.get("meta_qty")
    tipo = cfg.get("meta_tipo") or "-"
    qty_txt = str(qty) if qty is not None else "-"
    return f"Descrição: {desc}\nQuantidade: {qty_txt}\nTipo: {tipo}"


class FarmConfigView(ui.LayoutView):
    def __init__(self, db: Database, guild: discord.Guild, cfg: dict):
        super().__init__(timeout=None)
        self.db = db
        self.guild = guild
        self._build(cfg)

    def _build(self, cfg: dict):
        role = self.guild.get_role(cfg["approver_role_id"]) if cfg["approver_role_id"] else None
        role_txt = role.mention if role else "Não definido"
        freq_txt = _freq_label(cfg["meta_freq"])
        meta_txt = _build_meta_text(cfg)
        status_txt = _bool_label(cfg["enabled"])

        container = ui.Container()
        container.add_item(ui.TextDisplay("**Sistema de Farms**"))
        container.add_item(ui.Separator(spacing=discord.SeparatorSpacing.small))

        btn_role = ui.Button(label="⚙️ Editar", style=discord.ButtonStyle.secondary)
        btn_role.callback = self._edit_role
        try:
            container.add_item(ui.Section(
                ui.TextDisplay(f"**👥 Cargo de Aprovador do Farm**\n{role_txt}"),
                accessory=btn_role
            ))
        except Exception:
            container.add_item(ui.TextDisplay(f"**👥 Cargo de Aprovador do Farm**\n{role_txt}"))
            container.add_item(ui.ActionRow(btn_role))

        btn_freq = ui.Button(label="⚙️ Editar", style=discord.ButtonStyle.secondary)
        btn_freq.callback = self._edit_freq
        try:
            container.add_item(ui.Section(
                ui.TextDisplay(f"**🗂️ Tipo de Meta Configurada**\n{freq_txt}"),
                accessory=btn_freq
            ))
        except Exception:
            container.add_item(ui.TextDisplay(f"**🗂️ Tipo de Meta Configurada**\n{freq_txt}"))
            container.add_item(ui.ActionRow(btn_freq))

        btn_meta = ui.Button(label="⚙️ Editar", style=discord.ButtonStyle.secondary)
        btn_meta.callback = self._edit_meta
        try:
            container.add_item(ui.Section(
                ui.TextDisplay(f"**🎯 Meta Objetivo**\n{meta_txt}"),
                accessory=btn_meta
            ))
        except Exception:
            container.add_item(ui.TextDisplay(f"**🎯 Meta Objetivo**\n{meta_txt}"))
            container.add_item(ui.ActionRow(btn_meta))

        container.add_item(ui.Separator(spacing=discord.SeparatorSpacing.small))
        status_badge = f"🟢 **Ativo**" if cfg["enabled"] == 1 else f"🔴 **Inativo**"
        container.add_item(ui.TextDisplay(f"Status: {status_badge}"))

        btn_toggle = ui.Button(
            label=("Ativar Farm" if cfg["enabled"] == 0 else "Desativar Farm"),
            emoji=(TOGGLE_OFF if cfg["enabled"] == 0 else TOGGLE_ON),
            style=discord.ButtonStyle.success if cfg["enabled"] == 0 else discord.ButtonStyle.danger
        )
        btn_toggle.callback = self._toggle

        btn_back = ui.Button(label="Voltar", style=discord.ButtonStyle.secondary)
        btn_back.callback = self._close

        container.add_item(ui.ActionRow(btn_toggle, btn_back))
        container.add_item(ui.Separator(spacing=discord.SeparatorSpacing.small))
        container.add_item(ui.TextDisplay("↳ Em caso de dúvidas, assista os tutoriais."))
        self.clear_items()
        self.add_item(container)
        return

    async def refresh(self, interaction: discord.Interaction):
        cfg = await _get_farm_config(self.db, self.guild.id)
        self._build(cfg)
        await interaction.response.edit_message(view=self)

    async def _edit_role(self, interaction: discord.Interaction):
        await interaction.response.edit_message(view=FarmEditRoleView(self.db, self.guild))

    async def _edit_freq(self, interaction: discord.Interaction):
        await interaction.response.edit_message(view=FarmEditFreqView(self.db, self.guild))

    async def _edit_meta(self, interaction: discord.Interaction):
        modal = FarmMetaModal(self.db, self.guild, interaction.message.id, interaction.channel_id)
        await interaction.response.send_modal(modal)

    async def _toggle(self, interaction: discord.Interaction):
        cfg = await _get_farm_config(self.db, self.guild.id)
        enabled = 0 if cfg["enabled"] == 1 else 1
        await self.db.set_farm_enabled(self.guild.id, bool(enabled))
        await self.refresh(interaction)

    async def _close(self, interaction: discord.Interaction):
        await interaction.response.edit_message(content="Configuração de farm fechada.", view=None)


class FarmEditRoleView(ui.LayoutView):
    def __init__(self, db: Database, guild: discord.Guild):
        super().__init__(timeout=None)
        self.db = db
        self.guild = guild

        container = ui.Container()
        container.add_item(ui.TextDisplay("# Cargo de Aprovador do Farm"))
        container.add_item(ui.Separator(spacing=discord.SeparatorSpacing.small))
        container.add_item(ui.TextDisplay("Selecione o cargo que poderá aprovar o farm."))

        sel = ui.RoleSelect(min_values=1, max_values=1)
        sel.callback = self._set_role
        container.add_item(ui.ActionRow(sel))

        btn_back = ui.Button(label="Voltar", style=discord.ButtonStyle.secondary)
        btn_back.callback = self._back
        container.add_item(ui.ActionRow(btn_back))

        self.add_item(container)

    async def _set_role(self, interaction: discord.Interaction):
        cargo = interaction.data["values"][0]
        await self.db.set_farm_config(self.guild.id, approver_role_id=int(cargo))
        cfg = await _get_farm_config(self.db, self.guild.id)
        view = FarmConfigView(self.db, self.guild, cfg)
        await view.refresh(interaction)

    async def _back(self, interaction: discord.Interaction):
        cfg = await _get_farm_config(self.db, self.guild.id)
        view = FarmConfigView(self.db, self.guild, cfg)
        await view.refresh(interaction)


class FarmEditFreqView(ui.LayoutView):
    def __init__(self, db: Database, guild: discord.Guild):
        super().__init__(timeout=None)
        self.db = db
        self.guild = guild

        container = ui.Container()
        container.add_item(ui.TextDisplay("# Tipo de Meta"))
        container.add_item(ui.Separator(spacing=discord.SeparatorSpacing.small))
        container.add_item(ui.TextDisplay("Selecione a frequência da meta."))

        sel = ui.Select(
            options=[
                discord.SelectOption(label=label, value=value)
                for value, label in FREQ_OPTIONS
            ]
        )
        sel.callback = self._set_freq
        container.add_item(ui.ActionRow(sel))

        btn_back = ui.Button(label="Voltar", style=discord.ButtonStyle.secondary)
        btn_back.callback = self._back
        container.add_item(ui.ActionRow(btn_back))

        self.add_item(container)

    async def _set_freq(self, interaction: discord.Interaction):
        value = interaction.data["values"][0]
        await self.db.set_farm_config(self.guild.id, meta_freq=value)
        cfg = await _get_farm_config(self.db, self.guild.id)
        view = FarmConfigView(self.db, self.guild, cfg)
        await view.refresh(interaction)

    async def _back(self, interaction: discord.Interaction):
        cfg = await _get_farm_config(self.db, self.guild.id)
        view = FarmConfigView(self.db, self.guild, cfg)
        await view.refresh(interaction)


class FarmMetaModal(ui.Modal):
    def __init__(self, db: Database, guild: discord.Guild, message_id: int, channel_id: int):
        super().__init__(title="Definir Meta de Farm")
        self.db = db
        self.guild = guild
        self.message_id = int(message_id)
        self.channel_id = int(channel_id)

        self.desc = ui.TextInput(label="Descrição da meta", required=True, max_length=120)
        self.qty = ui.TextInput(label="Quantidade (número)", required=True, max_length=12)
        self.tipo = ui.TextInput(label="Tipo", required=True, max_length=40)
        self.add_item(self.desc)
        self.add_item(self.qty)
        self.add_item(self.tipo)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            qty = int(self.qty.value)
        except ValueError:
            await interaction.response.send_message(f"{X} Quantidade inválida. Use apenas números.", ephemeral=True)
            return

        await self.db.set_farm_config(
            self.guild.id,
            meta_desc=self.desc.value.strip(),
            meta_qty=qty,
            meta_tipo=self.tipo.value.strip()
        )

        try:
            channel = interaction.guild.get_channel(self.channel_id)
            if channel:
                msg = await channel.fetch_message(self.message_id)
                cfg = await _get_farm_config(self.db, self.guild.id)
                view = FarmConfigView(self.db, self.guild, cfg)
                await msg.edit(view=view)
        except Exception:
            pass

        await interaction.response.send_message(f"{CHECK} Meta atualizada com sucesso.", ephemeral=True)


class FarmUserPanelView(ui.LayoutView):
    def __init__(self, db: Database, guild: discord.Guild | None):
        super().__init__(timeout=None)
        self.db = db
        self.guild = guild

        container = ui.Container()
        guild_name = guild.name if guild else "Servidor"
        container.add_item(ui.TextDisplay(f"**Servidor de {guild_name} • Painel de Farm**"))
        container.add_item(ui.Separator(spacing=discord.SeparatorSpacing.small))
        container.add_item(ui.TextDisplay("Clique no botão abaixo para abrir sua pasta de farm."))

        btn_open = ui.Button(
            label="Abrir pasta",
            style=discord.ButtonStyle.secondary,
            emoji=FOLDER,
            custom_id="farm:abrir_pasta"
        )
        btn_open.callback = self._open_folder
        container.add_item(ui.ActionRow(btn_open))

        self.add_item(container)

    async def _open_folder(self, interaction: discord.Interaction):
        try:
            if not interaction.guild:
                await interaction.response.send_message(f"{X} Este comando só funciona em servidor.", ephemeral=True)
                return
            cfg = await _get_farm_config(self.db, interaction.guild.id)
            if cfg["enabled"] != 1:
                await interaction.response.send_message(f"{X} O sistema de farm está desativado.", ephemeral=True)
                return

            approver_role_id = cfg["approver_role_id"]
            approver_role = interaction.guild.get_role(approver_role_id) if approver_role_id else None
            if not approver_role:
                await interaction.response.send_message(f"{X} Cargo de aprovador não configurado.", ephemeral=True)
                return

            existing_id = await self.db.get_farm_channel(interaction.guild.id, interaction.user.id)
            if existing_id:
                canal = interaction.guild.get_channel(existing_id)
                if canal:
                    await interaction.response.send_message(
                        f"{CHECK} Sua pasta já está aberta: {canal.mention}",
                        ephemeral=True
                    )
                    return

            await interaction.response.defer(ephemeral=True)

            overwrites = {
                interaction.guild.default_role: discord.PermissionOverwrite(read_messages=False),
                interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True, attach_files=True),
                approver_role: discord.PermissionOverwrite(read_messages=True, send_messages=True, manage_messages=True),
                interaction.guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True, manage_channels=True)
            }

            for role in interaction.guild.roles:
                if role.permissions.administrator:
                    overwrites[role] = discord.PermissionOverwrite(
                        read_messages=True,
                        send_messages=True,
                        manage_messages=True
                    )

            canal = await interaction.guild.create_text_channel(
                name=f"farm-{interaction.user.name}",
                topic=f"Farm de {interaction.user.id}",
                overwrites=overwrites,
                reason=f"Pasta de farm criada para {interaction.user}"
            )

            await self.db.set_farm_channel(interaction.guild.id, canal.id, interaction.user.id)

            view = FarmFolderView(self.db, interaction.user.mention)
            await canal.send(view=view)

            await interaction.followup.send(
                f"{CHECK} Pasta criada com sucesso! Acesse {canal.mention}.",
                ephemeral=True
            )
        except Exception as e:
            print(f"Erro ao abrir pasta de farm: {e}")
            traceback.print_exc()
            try:
                await interaction.followup.send(f"{X} Erro ao abrir a pasta de farm.", ephemeral=True)
            except Exception:
                pass


class FarmFolderView(ui.LayoutView):
    def __init__(self, db: Database, owner_mention: str | None = None):
        super().__init__(timeout=None)
        self.db = db
        self.owner_mention = owner_mention or "Usuário"

        container = ui.Container()
        container.add_item(ui.TextDisplay(f"** {self.owner_mention}, essa é sua pasta de farm!**"))
        container.add_item(ui.Separator(spacing=discord.SeparatorSpacing.small))

        btn_close = ui.Button(label="Fechar Pasta", style=discord.ButtonStyle.danger, emoji=TRASH)
        btn_close.callback = self._close_folder

        btn_meta = ui.Button(label="Ver Metas", style=discord.ButtonStyle.secondary, emoji=EYE)
        btn_meta.callback = self._show_meta

        container.add_item(ui.ActionRow(btn_close, btn_meta))
        self.add_item(container)

    async def _has_permission(self, interaction: discord.Interaction) -> bool:
        if interaction.user.guild_permissions.administrator:
            return True
        if not interaction.guild:
            return False
        cfg = await _get_farm_config(self.db, interaction.guild.id)
        approver_role_id = cfg["approver_role_id"]
        if approver_role_id and any(r.id == approver_role_id for r in interaction.user.roles):
            return True
        owner_id = None
        if interaction.channel and getattr(interaction.channel, "topic", None):
            topic = interaction.channel.topic
            if topic and topic.startswith("Farm de "):
                try:
                    owner_id = int(topic.replace("Farm de ", ""))
                except Exception:
                    owner_id = None
        return owner_id is not None and interaction.user.id == owner_id

    async def _close_folder(self, interaction: discord.Interaction):
        if not await self._has_permission(interaction):
            await interaction.response.send_message(f"{X} Você não pode fechar esta pasta.", ephemeral=True)
            return
        try:
            await self.db.close_farm_channel(interaction.channel.id)
            await interaction.response.send_message(f"{CHECK} Pasta será fechada em 5 segundos.", ephemeral=True)
            await interaction.channel.delete(reason=f"Pasta de farm fechada por {interaction.user}")
        except Exception as e:
            print(f"Erro ao fechar pasta de farm: {e}")
            traceback.print_exc()
            try:
                await interaction.response.send_message(f"{X} Erro ao fechar a pasta.", ephemeral=True)
            except Exception:
                pass

    async def _show_meta(self, interaction: discord.Interaction):
        if not await self._has_permission(interaction):
            await interaction.response.send_message(f"{X} Você não pode ver as metas.", ephemeral=True)
            return

        if not interaction.guild:
            await interaction.response.send_message(f"{X} Comando inválido fora do servidor.", ephemeral=True)
            return
        cfg = await _get_farm_config(self.db, interaction.guild.id)
        freq_txt = _freq_label(cfg["meta_freq"])
        desc = cfg.get("meta_desc") or "Não definida"
        qty = cfg.get("meta_qty")
        tipo = cfg.get("meta_tipo") or "-"
        qty_txt = str(qty) if qty is not None else "-"

        container = ui.Container()
        container.add_item(ui.TextDisplay(f"** Servidor de {interaction.guild.name} • Meta de Farm**"))
        container.add_item(ui.Separator(spacing=discord.SeparatorSpacing.small))
        container.add_item(ui.TextDisplay(
            f"**Frequência**\n"
            f"{freq_txt}\n"
            f"**Descrição**\n"
            f"**Observação:** {desc}\n"
            f"**Quantidade:** {qty_txt}\n"
            f"**Tipo:** {tipo}"
        ))

        view = ui.LayoutView()
        view.add_item(container)
        await interaction.response.send_message(view=view, ephemeral=True)


class FarmCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = Database()
        self.bot.add_view(FarmFolderView(self.db))
        self.bot.add_view(FarmUserPanelView(self.db, None))
        print("Cog de Farm carregado com sucesso!")

    @app_commands.command(name="farm", description="Abrir o painel do sistema de farm")
    async def farm(self, interaction: discord.Interaction):
        if not interaction.guild:
            await interaction.response.send_message(f"{X} Este comando só funciona em servidor.", ephemeral=True)
            return
        view = FarmUserPanelView(self.db, interaction.guild)
        await interaction.response.send_message(view=view)


async def setup(bot: commands.Bot):
    cog = FarmCog(bot)
    await cog.db.init_db()
    await bot.add_cog(cog)
