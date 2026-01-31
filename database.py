import aiosqlite
from datetime import datetime
import traceback


class Database:
    def __init__(self, db_name: str = 'fabricacao.db'):
        self.db_name = db_name

    async def init_db(self):
        """Inicializa o banco de dados criando as tabelas necessárias."""
        try:
            async with aiosqlite.connect(self.db_name) as db:
                # --- Config por servidor ---
                await db.execute('''
                    CREATE TABLE IF NOT EXISTS config_servidores (
                        guild_id INTEGER PRIMARY KEY,
                        canal_log_id INTEGER,
                        cargo_gerente_id INTEGER,
                        cargo_meta_paga_id INTEGER,
                        canal_log_meta_id INTEGER,
                        cargo_vendedor_id INTEGER,
                        cargo_fabricante_id INTEGER,
                        cargo_membro_id INTEGER,
                        cargo_morador_id INTEGER,
                        data_configuracao TEXT
                    )
                ''')

                # Garantir colunas novas caso o banco já exista
                for col in ["cargo_vendedor_id", "cargo_fabricante_id", "cargo_membro_id", "cargo_morador_id"]:
                    try:
                        await db.execute(f"ALTER TABLE config_servidores ADD COLUMN {col} INTEGER")
                    except Exception:
                        pass

                # --- Logs de fabricação ---
                await db.execute('''
                    CREATE TABLE IF NOT EXISTS logs_fabricacao (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        guild_id INTEGER NOT NULL,
                        user_id INTEGER NOT NULL,
                        user_name TEXT NOT NULL,
                        produto_id TEXT NOT NULL,
                        produto_nome TEXT NOT NULL,
                        quantidade INTEGER NOT NULL,
                        custo_total REAL NOT NULL,
                        materiais TEXT NOT NULL,
                        data_fabricacao TEXT NOT NULL
                    )
                ''')

                # --- Logs de vendas ---
                await db.execute('''
                    CREATE TABLE IF NOT EXISTS logs_vendas (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        guild_id INTEGER NOT NULL,
                        user_id INTEGER NOT NULL,
                        user_name TEXT NOT NULL,
                        produto_id TEXT NOT NULL,
                        produto_nome TEXT NOT NULL,
                        quantidade INTEGER NOT NULL,
                        valor_total REAL NOT NULL,
                        comprador TEXT,
                        data_venda TEXT NOT NULL
                    )
                ''')

                # --- Preço unitário por produto (venda) ---
                await db.execute('''
                    CREATE TABLE IF NOT EXISTS produtos_precos (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        guild_id INTEGER NOT NULL,
                        produto_id TEXT NOT NULL,
                        preco_unit REAL NOT NULL,
                        atualizado_em TEXT NOT NULL,
                        UNIQUE(guild_id, produto_id)
                    )
                ''')

                # --- Encomendas ---
                await db.execute('''
                    CREATE TABLE IF NOT EXISTS encomendas (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        guild_id INTEGER NOT NULL,
                        user_id INTEGER NOT NULL,
                        user_name TEXT NOT NULL,
                        produto_id TEXT NOT NULL,
                        produto_nome TEXT NOT NULL,
                        quantidade INTEGER NOT NULL,
                        preco_unit REAL NOT NULL,
                        cliente TEXT,
                        message_id INTEGER,
                        status TEXT NOT NULL DEFAULT 'pendente',
                        criado_em TEXT NOT NULL,
                        confirmado_em TEXT,
                        confirmado_por_id INTEGER
                    )
                ''')
                # Garantir coluna de mensagem para persistência
                try:
                    await db.execute("ALTER TABLE encomendas ADD COLUMN message_id INTEGER")
                except Exception:
                    pass

                # --- Banco pessoal ---
                await db.execute('''
                    CREATE TABLE IF NOT EXISTS banco_usuarios (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        guild_id INTEGER NOT NULL,
                        user_id INTEGER NOT NULL,
                        user_name TEXT NOT NULL,
                        saldo REAL NOT NULL DEFAULT 0.0,
                        ultima_fabricacao_valor REAL,
                        ultima_venda_valor REAL,
                        atualizado_em TEXT NOT NULL,
                        UNIQUE(guild_id, user_id)
                    )
                ''')

                # --- Extrato (ledger) do banco ---
                await db.execute('''
                    CREATE TABLE IF NOT EXISTS movimentos_banco (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        guild_id INTEGER NOT NULL,
                        user_id INTEGER NOT NULL,
                        user_name TEXT NOT NULL,
                        origem TEXT NOT NULL,            -- venda, fabricacao, encomenda, ajuste
                        delta REAL NOT NULL,
                        saldo_antes REAL NOT NULL,
                        saldo_depois REAL NOT NULL,
                        motivo TEXT,
                        ref_tipo TEXT,
                        ref_id INTEGER,
                        criado_em TEXT NOT NULL
                    )
                ''')

                # --- Estoque (com reservado para encomendas) ---
                await db.execute('''
                    CREATE TABLE IF NOT EXISTS estoque_produtos (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        guild_id INTEGER NOT NULL,
                        produto_id TEXT NOT NULL,
                        quantidade INTEGER NOT NULL DEFAULT 0,
                        reservado INTEGER NOT NULL DEFAULT 0,
                        atualizado_em TEXT NOT NULL,
                        UNIQUE(guild_id, produto_id)
                    )
                ''')

                # --- Estatísticas (mantidas) ---
                await db.execute('''
                    CREATE TABLE IF NOT EXISTS estatisticas_servidor (
                        guild_id INTEGER PRIMARY KEY,
                        total_fabricacoes INTEGER DEFAULT 0,
                        custo_total_gasto REAL DEFAULT 0.0,
                        ultima_atualizacao TEXT
                    )
                ''')

                await db.execute('''
                    CREATE TABLE IF NOT EXISTS estatisticas_usuario (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        guild_id INTEGER NOT NULL,
                        user_id INTEGER NOT NULL,
                        total_fabricacoes INTEGER DEFAULT 0,
                        custo_total_gasto REAL DEFAULT 0.0,
                        ultima_fabricacao TEXT,
                        UNIQUE(guild_id, user_id)
                    )
                ''')

                # --- Metas (mantidas) ---
                await db.execute('''
                    CREATE TABLE IF NOT EXISTS canais_meta (
                        canal_id INTEGER PRIMARY KEY,
                        guild_id INTEGER NOT NULL,
                        user_id INTEGER NOT NULL,
                        data_criacao TEXT NOT NULL,
                        ativo INTEGER DEFAULT 1
                    )
                ''')

                await db.execute('''
                    CREATE TABLE IF NOT EXISTS metas_aprovadas (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        guild_id INTEGER NOT NULL,
                        user_id INTEGER NOT NULL,
                        aprovado_por_id INTEGER NOT NULL,
                        descricao TEXT,
                        data_aprovacao TEXT NOT NULL
                    )
                ''')

                # --- Farm (novo sistema) ---
                await db.execute('''
                    CREATE TABLE IF NOT EXISTS farm_config (
                        guild_id INTEGER PRIMARY KEY,
                        enabled INTEGER DEFAULT 0,
                        approver_role_id INTEGER,
                        meta_freq TEXT,
                        meta_desc TEXT,
                        meta_qty INTEGER,
                        meta_tipo TEXT,
                        updated_at TEXT
                    )
                ''')

                await db.execute('''
                    CREATE TABLE IF NOT EXISTS farm_channels (
                        channel_id INTEGER PRIMARY KEY,
                        guild_id INTEGER NOT NULL,
                        user_id INTEGER NOT NULL,
                        active INTEGER DEFAULT 1,
                        created_at TEXT NOT NULL
                    )
                ''')

                # --- Registros pendentes (aprovacao persistente) ---
                await db.execute('''
                    CREATE TABLE IF NOT EXISTS registros_pendentes (
                        message_id INTEGER PRIMARY KEY,
                        guild_id INTEGER NOT NULL,
                        user_id INTEGER NOT NULL,
                        nome TEXT NOT NULL,
                        rg TEXT NOT NULL,
                        status TEXT NOT NULL DEFAULT 'pendente',
                        criado_em TEXT NOT NULL,
                        resolvido_em TEXT,
                        resolvido_por_id INTEGER,
                        resultado TEXT
                    )
                ''')

                await db.commit()
                print("✅ Banco de dados inicializado com sucesso!")

        except Exception as e:
            print(f"❌ Erro ao inicializar banco de dados: {e}")
            traceback.print_exc()

    # -------------------- CONFIG --------------------

    async def get_config_servidor(self, guild_id: int):
        """Retorna a linha completa de config_servidores do servidor."""
        try:
            async with aiosqlite.connect(self.db_name) as db:
                async with db.execute('''
                    SELECT guild_id, canal_log_id, cargo_gerente_id, cargo_meta_paga_id, canal_log_meta_id,
                           cargo_vendedor_id, cargo_fabricante_id, cargo_membro_id, cargo_morador_id, data_configuracao
                    FROM config_servidores
                    WHERE guild_id = ?
                ''', (int(guild_id),)) as cursor:
                    return await cursor.fetchone()
        except Exception as e:
            print(f"❌ Erro ao buscar config do servidor: {e}")
            traceback.print_exc()
            return None

    async def set_canal_log(self, guild_id: int, canal_id: int):
        """Define o canal de log para um servidor."""
        try:
            async with aiosqlite.connect(self.db_name) as db:
                now = datetime.now().isoformat()
                await db.execute('''
                    INSERT INTO config_servidores (guild_id, canal_log_id, data_configuracao)
                    VALUES (?, ?, ?)
                    ON CONFLICT(guild_id)
                    DO UPDATE SET canal_log_id = ?, data_configuracao = ?
                ''', (int(guild_id), int(canal_id), now, int(canal_id), now))
                await db.commit()
                return True
        except Exception as e:
            print(f"❌ Erro ao configurar canal de log: {e}")
            traceback.print_exc()
            return False

    async def get_canal_log(self, guild_id: int):
        """Obtém o canal de log configurado para um servidor."""
        try:
            async with aiosqlite.connect(self.db_name) as db:
                async with db.execute(
                    'SELECT canal_log_id FROM config_servidores WHERE guild_id = ?',
                    (int(guild_id),)
                ) as cursor:
                    result = await cursor.fetchone()
                    return result[0] if result else None
        except Exception as e:
            print(f"❌ Erro ao buscar canal de log: {e}")
            traceback.print_exc()
            return None

    async def set_cargos_sistema(self, guild_id: int, cargo_vendedor_id: int = None, cargo_fabricante_id: int = None):
        """Define cargos do sistema (vendedor/fabricante) sem mexer nos antigos."""
        try:
            async with aiosqlite.connect(self.db_name) as db:
                async with db.execute('''
                    SELECT cargo_vendedor_id, cargo_fabricante_id
                    FROM config_servidores WHERE guild_id = ?
                ''', (int(guild_id),)) as cursor:
                    row = await cursor.fetchone()

                atual_v, atual_f = (row[0], row[1]) if row else (None, None)
                novo_v = cargo_vendedor_id if cargo_vendedor_id is not None else atual_v
                novo_f = cargo_fabricante_id if cargo_fabricante_id is not None else atual_f

                now = datetime.now().isoformat()
                await db.execute('''
                    INSERT INTO config_servidores (guild_id, cargo_vendedor_id, cargo_fabricante_id, data_configuracao)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(guild_id)
                    DO UPDATE SET cargo_vendedor_id = ?, cargo_fabricante_id = ?, data_configuracao = ?
                ''', (int(guild_id), novo_v, novo_f, now, novo_v, novo_f, now))
                await db.commit()
                return True
        except Exception as e:
            print(f"❌ Erro ao configurar cargos do sistema: {e}")
            traceback.print_exc()
            return False

    async def get_cargos_sistema(self, guild_id: int):
        """Retorna (cargo_vendedor_id, cargo_fabricante_id, cargo_gerente_id)."""
        try:
            async with aiosqlite.connect(self.db_name) as db:
                async with db.execute('''
                    SELECT cargo_vendedor_id, cargo_fabricante_id, cargo_gerente_id
                    FROM config_servidores WHERE guild_id = ?
                ''', (int(guild_id),)) as cursor:
                    row = await cursor.fetchone()
                    if not row:
                        return None, None, None
                    return row[0], row[1], row[2]
        except Exception as e:
            print(f"❌ Erro ao buscar cargos do sistema: {e}")
            traceback.print_exc()
            return None, None, None

    async def set_cargos_boasvindas(self, guild_id: int, cargo_membro_id: int = None, cargo_morador_id: int = None):
        """Define cargos de boas-vindas (membro/morador) sem mexer nos outros."""
        try:
            async with aiosqlite.connect(self.db_name) as db:
                async with db.execute('''
                    SELECT cargo_membro_id, cargo_morador_id
                    FROM config_servidores WHERE guild_id = ?
                ''', (int(guild_id),)) as cursor:
                    row = await cursor.fetchone()

                atual_m, atual_r = (row[0], row[1]) if row else (None, None)
                novo_m = cargo_membro_id if cargo_membro_id is not None else atual_m
                novo_r = cargo_morador_id if cargo_morador_id is not None else atual_r

                now = datetime.now().isoformat()
                await db.execute('''
                    INSERT INTO config_servidores (guild_id, cargo_membro_id, cargo_morador_id, data_configuracao)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(guild_id)
                    DO UPDATE SET cargo_membro_id = ?, cargo_morador_id = ?, data_configuracao = ?
                ''', (int(guild_id), novo_m, novo_r, now, novo_m, novo_r, now))
                await db.commit()
                return True
        except Exception as e:
            print(f"❌ Erro ao configurar cargos de boas-vindas: {e}")
            traceback.print_exc()
            return False

    async def get_cargos_boasvindas(self, guild_id: int):
        """Retorna (cargo_membro_id, cargo_morador_id)."""
        try:
            async with aiosqlite.connect(self.db_name) as db:
                async with db.execute('''
                    SELECT cargo_membro_id, cargo_morador_id
                    FROM config_servidores WHERE guild_id = ?
                ''', (int(guild_id),)) as cursor:
                    row = await cursor.fetchone()
                    if not row:
                        return None, None
                    return row[0], row[1]
        except Exception as e:
            print(f"❌ Erro ao buscar cargos de boas-vindas: {e}")
            traceback.print_exc()
            return None, None

    # -------------------- CONFIG META --------------------

    async def set_config_meta(self, guild_id: int, cargo_gerente_id: int = None,
                              cargo_meta_paga_id: int = None, canal_log_meta_id: int = None):
        """Configura o sistema de metas para um servidor."""
        try:
            async with aiosqlite.connect(self.db_name) as db:
                async with db.execute('''
                    SELECT cargo_gerente_id, cargo_meta_paga_id, canal_log_meta_id
                    FROM config_servidores WHERE guild_id = ?
                ''', (int(guild_id),)) as cursor:
                    result = await cursor.fetchone()

                if result:
                    atual_gerente, atual_meta, atual_canal = result
                    novo_gerente = cargo_gerente_id if cargo_gerente_id is not None else atual_gerente
                    novo_meta = cargo_meta_paga_id if cargo_meta_paga_id is not None else atual_meta
                    novo_canal = canal_log_meta_id if canal_log_meta_id is not None else atual_canal
                else:
                    novo_gerente = cargo_gerente_id
                    novo_meta = cargo_meta_paga_id
                    novo_canal = canal_log_meta_id

                now = datetime.now().isoformat()
                await db.execute('''
                    INSERT INTO config_servidores
                    (guild_id, cargo_gerente_id, cargo_meta_paga_id, canal_log_meta_id, data_configuracao)
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(guild_id)
                    DO UPDATE SET
                        cargo_gerente_id = ?,
                        cargo_meta_paga_id = ?,
                        canal_log_meta_id = ?,
                        data_configuracao = ?
                ''', (
                    int(guild_id), novo_gerente, novo_meta, novo_canal, now,
                    novo_gerente, novo_meta, novo_canal, now
                ))
                await db.commit()
                return True
        except Exception as e:
            print(f"❌ Erro ao configurar sistema de metas: {e}")
            traceback.print_exc()
            return False

    async def get_config_meta(self, guild_id: int):
        """Retorna (guild_id, cargo_gerente_id, cargo_meta_paga_id, canal_log_meta_id)."""
        try:
            async with aiosqlite.connect(self.db_name) as db:
                async with db.execute('''
                    SELECT guild_id, cargo_gerente_id, cargo_meta_paga_id, canal_log_meta_id
                    FROM config_servidores
                    WHERE guild_id = ?
                ''', (int(guild_id),)) as cursor:
                    return await cursor.fetchone()
        except Exception as e:
            print(f"❌ Erro ao buscar config de meta: {e}")
            traceback.print_exc()
            return None

    # -------------------- CANAIS META --------------------

    async def criar_canal_meta(self, guild_id: int, canal_id: int, user_id: int):
        """Registra o canal de meta criado para um usuário."""
        try:
            async with aiosqlite.connect(self.db_name) as db:
                now = datetime.now().isoformat()
                await db.execute('''
                    INSERT OR REPLACE INTO canais_meta (canal_id, guild_id, user_id, data_criacao, ativo)
                    VALUES (?, ?, ?, ?, 1)
                ''', (int(canal_id), int(guild_id), int(user_id), now))
                await db.commit()
                return True
        except Exception as e:
            print(f"❌ Erro ao registrar canal de meta: {e}")
            traceback.print_exc()
            return False

    async def fechar_canal_meta(self, canal_id: int):
        """Marca um canal de meta como fechado."""
        try:
            async with aiosqlite.connect(self.db_name) as db:
                await db.execute('''
                    UPDATE canais_meta
                    SET ativo = 0
                    WHERE canal_id = ?
                ''', (int(canal_id),))
                await db.commit()
                return True
        except Exception as e:
            print(f"❌ Erro ao fechar canal de meta: {e}")
            traceback.print_exc()
            return False

    async def registrar_meta_aprovada(self, guild_id: int, user_id: int, aprovado_por_id: int, descricao: str):
        """Registra uma meta aprovada."""
        try:
            async with aiosqlite.connect(self.db_name) as db:
                now = datetime.now().isoformat()
                await db.execute('''
                    INSERT INTO metas_aprovadas (guild_id, user_id, aprovado_por_id, descricao, data_aprovacao)
                    VALUES (?, ?, ?, ?, ?)
                ''', (int(guild_id), int(user_id), int(aprovado_por_id), str(descricao), now))
                await db.commit()
                return True
        except Exception as e:
            print(f"❌ Erro ao registrar meta aprovada: {e}")
            traceback.print_exc()
            return False

    # -------------------- FARM --------------------

    async def get_farm_config(self, guild_id: int):
        try:
            async with aiosqlite.connect(self.db_name) as db:
                async with db.execute('''
                    SELECT guild_id, enabled, approver_role_id, meta_freq, meta_desc, meta_qty, meta_tipo
                    FROM farm_config
                    WHERE guild_id = ?
                ''', (int(guild_id),)) as cursor:
                    return await cursor.fetchone()
        except Exception as e:
            print(f"❌ Erro ao buscar config de farm: {e}")
            traceback.print_exc()
            return None

    async def set_farm_config(self, guild_id: int, approver_role_id=None,
                              meta_freq: str | None = None, meta_desc: str | None = None,
                              meta_qty: int | None = None, meta_tipo: str | None = None,
                              enabled: int | None = None):
        try:
            async with aiosqlite.connect(self.db_name) as db:
                async with db.execute('''
                    SELECT enabled, approver_role_id, meta_freq, meta_desc, meta_qty, meta_tipo
                    FROM farm_config
                    WHERE guild_id = ?
                ''', (int(guild_id),)) as cursor:
                    row = await cursor.fetchone()

                if row:
                    cur_enabled, cur_approver, cur_freq, cur_desc, cur_qty, cur_tipo = row
                else:
                    cur_enabled, cur_approver, cur_freq, cur_desc, cur_qty, cur_tipo = (0, None, None, None, None, None)

                new_enabled = cur_enabled if enabled is None else int(enabled)
                new_approver = cur_approver if approver_role_id is None else int(approver_role_id)
                new_freq = cur_freq if meta_freq is None else str(meta_freq)
                new_desc = cur_desc if meta_desc is None else str(meta_desc)
                new_qty = cur_qty if meta_qty is None else int(meta_qty)
                new_tipo = cur_tipo if meta_tipo is None else str(meta_tipo)
                now = datetime.now().isoformat()

                await db.execute('''
                    INSERT INTO farm_config
                    (guild_id, enabled, approver_role_id, meta_freq, meta_desc, meta_qty, meta_tipo, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(guild_id)
                    DO UPDATE SET enabled = ?, approver_role_id = ?, meta_freq = ?, meta_desc = ?, meta_qty = ?, meta_tipo = ?, updated_at = ?
                ''', (
                    int(guild_id), new_enabled, new_approver, new_freq, new_desc, new_qty, new_tipo, now,
                    new_enabled, new_approver, new_freq, new_desc, new_qty, new_tipo, now
                ))
                await db.commit()
                return True
        except Exception as e:
            print(f"❌ Erro ao salvar config de farm: {e}")
            traceback.print_exc()
            return False

    async def set_farm_enabled(self, guild_id: int, enabled: bool):
        return await self.set_farm_config(guild_id, enabled=1 if enabled else 0)

    async def set_farm_channel(self, guild_id: int, channel_id: int, user_id: int):
        try:
            async with aiosqlite.connect(self.db_name) as db:
                now = datetime.now().isoformat()
                await db.execute('''
                    INSERT OR REPLACE INTO farm_channels (channel_id, guild_id, user_id, active, created_at)
                    VALUES (?, ?, ?, 1, ?)
                ''', (int(channel_id), int(guild_id), int(user_id), now))
                await db.commit()
                return True
        except Exception as e:
            print(f"❌ Erro ao salvar canal de farm: {e}")
            traceback.print_exc()
            return False

    async def get_farm_channel(self, guild_id: int, user_id: int):
        try:
            async with aiosqlite.connect(self.db_name) as db:
                async with db.execute('''
                    SELECT channel_id
                    FROM farm_channels
                    WHERE guild_id = ? AND user_id = ? AND active = 1
                ''', (int(guild_id), int(user_id))) as cursor:
                    row = await cursor.fetchone()
                    return row[0] if row else None
        except Exception as e:
            print(f"❌ Erro ao buscar canal de farm: {e}")
            traceback.print_exc()
            return None

    async def close_farm_channel(self, channel_id: int):
        try:
            async with aiosqlite.connect(self.db_name) as db:
                await db.execute('''
                    UPDATE farm_channels
                    SET active = 0
                    WHERE channel_id = ?
                ''', (int(channel_id),))
                await db.commit()
                return True
        except Exception as e:
            print(f"❌ Erro ao fechar canal de farm: {e}")
            traceback.print_exc()
            return False

    # -------------------- PREÇOS (VENDAS) --------------------

    async def set_preco_produto(self, guild_id: int, produto_id: str, preco_unit: float):
        """Define/atualiza o preço unitário de venda do produto."""
        try:
            async with aiosqlite.connect(self.db_name) as db:
                now = datetime.now().isoformat()
                await db.execute('''
                    INSERT INTO produtos_precos (guild_id, produto_id, preco_unit, atualizado_em)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(guild_id, produto_id)
                    DO UPDATE SET preco_unit = ?, atualizado_em = ?
                ''', (int(guild_id), str(produto_id), float(preco_unit), now, float(preco_unit), now))
                await db.commit()
                return True
        except Exception as e:
            print(f"❌ Erro ao salvar preço do produto: {e}")
            traceback.print_exc()
            return False

    async def get_preco_produto(self, guild_id: int, produto_id: str):
        try:
            async with aiosqlite.connect(self.db_name) as db:
                async with db.execute('''
                    SELECT preco_unit FROM produtos_precos
                    WHERE guild_id = ? AND produto_id = ?
                ''', (int(guild_id), str(produto_id))) as cursor:
                    row = await cursor.fetchone()
                    return float(row[0]) if row else None
        except Exception as e:
            print(f"❌ Erro ao buscar preço do produto: {e}")
            traceback.print_exc()
            return None

    # -------------------- ESTOQUE --------------------

    async def _ensure_estoque_produto(self, guild_id: int, produto_id: str):
        try:
            async with aiosqlite.connect(self.db_name) as db:
                now = datetime.now().isoformat()
                await db.execute('''
                    INSERT OR IGNORE INTO estoque_produtos
                    (guild_id, produto_id, quantidade, reservado, atualizado_em)
                    VALUES (?, ?, 0, 0, ?)
                ''', (int(guild_id), str(produto_id), now))
                await db.commit()
                return True
        except Exception as e:
            print(f"❌ Erro ao garantir estoque do produto: {e}")
            traceback.print_exc()
            return False

    async def get_estoque_produto(self, guild_id: int, produto_id: str):
        """Retorna (quantidade, reservado, disponivel)."""
        try:
            await self._ensure_estoque_produto(guild_id, produto_id)
            async with aiosqlite.connect(self.db_name) as db:
                async with db.execute('''
                    SELECT quantidade, reservado
                    FROM estoque_produtos
                    WHERE guild_id = ? AND produto_id = ?
                ''', (int(guild_id), str(produto_id))) as cursor:
                    row = await cursor.fetchone()
                    qtd = int(row[0] or 0) if row else 0
                    res = int(row[1] or 0) if row else 0
                    return qtd, res, (qtd - res)
        except Exception as e:
            print(f"❌ Erro ao obter estoque: {e}")
            traceback.print_exc()
            return 0, 0, 0

    async def adicionar_estoque(self, guild_id: int, produto_id: str, quantidade: int):
        """Soma no estoque (fabricação)."""
        try:
            await self._ensure_estoque_produto(guild_id, produto_id)
            qtd, _, _ = await self.get_estoque_produto(guild_id, produto_id)
            novo_qtd = int(qtd) + int(quantidade)
            async with aiosqlite.connect(self.db_name) as db:
                await db.execute('''
                    UPDATE estoque_produtos
                    SET quantidade = ?, atualizado_em = ?
                    WHERE guild_id = ? AND produto_id = ?
                ''', (novo_qtd, datetime.now().isoformat(), int(guild_id), str(produto_id)))
                await db.commit()
            return True
        except Exception as e:
            print(f"❌ Erro ao adicionar estoque: {e}")
            traceback.print_exc()
            return False

    async def consumir_estoque(self, guild_id: int, produto_id: str, quantidade: int):
        """Consome estoque disponível (venda). Retorna True/False."""
        try:
            qtd, res, disp = await self.get_estoque_produto(guild_id, produto_id)
            if int(quantidade) > int(disp):
                return False
            novo_qtd = int(qtd) - int(quantidade)
            async with aiosqlite.connect(self.db_name) as db:
                await db.execute('''
                    UPDATE estoque_produtos
                    SET quantidade = ?, atualizado_em = ?
                    WHERE guild_id = ? AND produto_id = ?
                ''', (novo_qtd, datetime.now().isoformat(), int(guild_id), str(produto_id)))
                await db.commit()
            return True
        except Exception as e:
            print(f"❌ Erro ao consumir estoque: {e}")
            traceback.print_exc()
            return False

    async def consumir_estoque_sem_negativo(self, guild_id: int, produto_id: str, quantidade: int):
        """Consome até o disponível, sem deixar estoque negativo. Retorna (ok, consumido, disponivel)."""
        try:
            qtd, res, disp = await self.get_estoque_produto(guild_id, produto_id)
            consumido = min(int(quantidade), int(disp))
            novo_qtd = int(qtd) - int(consumido)
            if consumido > 0:
                async with aiosqlite.connect(self.db_name) as db:
                    await db.execute('''
                        UPDATE estoque_produtos
                        SET quantidade = ?, atualizado_em = ?
                        WHERE guild_id = ? AND produto_id = ?
                    ''', (novo_qtd, datetime.now().isoformat(), int(guild_id), str(produto_id)))
                    await db.commit()
            return True, int(consumido), int(disp)
        except Exception as e:
            print(f"❌ Erro ao consumir estoque (sem negativo): {e}")
            traceback.print_exc()
            return False, 0, 0

    async def reservar_estoque(self, guild_id: int, produto_id: str, quantidade: int):
        """Reserva estoque disponível para encomenda pendente."""
        try:
            qtd, res, disp = await self.get_estoque_produto(guild_id, produto_id)
            if int(quantidade) > int(disp):
                return False
            novo_res = int(res) + int(quantidade)
            async with aiosqlite.connect(self.db_name) as db:
                await db.execute('''
                    UPDATE estoque_produtos
                    SET reservado = ?, atualizado_em = ?
                    WHERE guild_id = ? AND produto_id = ?
                ''', (novo_res, datetime.now().isoformat(), int(guild_id), str(produto_id)))
                await db.commit()
            return True
        except Exception as e:
            print(f"❌ Erro ao reservar estoque: {e}")
            traceback.print_exc()
            return False

    async def reservar_estoque_permitir_negativo(self, guild_id: int, produto_id: str, quantidade: int):
        """
        Reserva mesmo sem disponível (permite encomenda criar "negativo").
        Mantém a lógica de reserva: só mexe no reservado; o total só cai na confirmação.
        """
        try:
            await self._ensure_estoque_produto(guild_id, produto_id)
            qtd, res, _ = await self.get_estoque_produto(guild_id, produto_id)
            novo_res = int(res) + int(quantidade)
            async with aiosqlite.connect(self.db_name) as db:
                await db.execute('''
                    UPDATE estoque_produtos
                    SET reservado = ?, atualizado_em = ?
                    WHERE guild_id = ? AND produto_id = ?
                ''', (novo_res, datetime.now().isoformat(), int(guild_id), str(produto_id)))
                await db.commit()
            return True
        except Exception as e:
            print(f"❌ Erro ao reservar estoque (negativo): {e}")
            traceback.print_exc()
            return False

    async def confirmar_reserva_encomenda(self, guild_id: int, produto_id: str, quantidade: int):
        """Ao confirmar encomenda: tira do reservado e do total (pode ficar negativo no total)."""
        try:
            qtd, res, _ = await self.get_estoque_produto(guild_id, produto_id)
            if int(quantidade) > int(res):
                return False
            novo_res = int(res) - int(quantidade)
            novo_qtd = int(qtd) - int(quantidade)
            async with aiosqlite.connect(self.db_name) as db:
                await db.execute('''
                    UPDATE estoque_produtos
                    SET quantidade = ?, reservado = ?, atualizado_em = ?
                    WHERE guild_id = ? AND produto_id = ?
                ''', (novo_qtd, novo_res, datetime.now().isoformat(), int(guild_id), str(produto_id)))
                await db.commit()
            return True
        except Exception as e:
            print(f"❌ Erro ao confirmar reserva: {e}")
            traceback.print_exc()
            return False

    # -------------------- BANCO --------------------

    async def _ensure_banco_usuario(self, guild_id: int, user_id: int, user_name: str):
        async with aiosqlite.connect(self.db_name) as db:
            await db.execute('''
                INSERT INTO banco_usuarios (guild_id, user_id, user_name, saldo, atualizado_em)
                VALUES (?, ?, ?, 0.0, ?)
                ON CONFLICT(guild_id, user_id)
                DO UPDATE SET user_name = ?, atualizado_em = ?
            ''', (
                int(guild_id), int(user_id), str(user_name), datetime.now().isoformat(),
                str(user_name), datetime.now().isoformat()
            ))
            await db.commit()

    async def get_banco_usuario(self, guild_id: int, user_id: int, user_name: str):
        try:
            await self._ensure_banco_usuario(guild_id, user_id, user_name)
            async with aiosqlite.connect(self.db_name) as db:
                async with db.execute('''
                    SELECT saldo, ultima_fabricacao_valor, ultima_venda_valor
                    FROM banco_usuarios
                    WHERE guild_id = ? AND user_id = ?
                ''', (int(guild_id), int(user_id))) as cursor:
                    row = await cursor.fetchone()
                    if not row:
                        return 0.0, None, None
                    return float(row[0] or 0.0), row[1], row[2]
        except Exception as e:
            print(f"❌ Erro ao obter banco do usuário: {e}")
            traceback.print_exc()
            return 0.0, None, None

    async def aplicar_movimento_banco(self, guild_id: int, user_id: int, user_name: str,
                                     delta: float, ultima_fabricacao_valor=None, ultima_venda_valor=None,
                                     origem: str = "sistema", motivo: str = None, ref_tipo: str = None, ref_id: int = None):
        """Aplica delta e registra no extrato."""
        try:
            await self._ensure_banco_usuario(guild_id, user_id, user_name)
            async with aiosqlite.connect(self.db_name) as db:
                async with db.execute('''
                    SELECT saldo, ultima_fabricacao_valor, ultima_venda_valor
                    FROM banco_usuarios
                    WHERE guild_id = ? AND user_id = ?
                ''', (int(guild_id), int(user_id))) as cursor:
                    row = await cursor.fetchone()

                saldo_atual = float(row[0] or 0.0) if row else 0.0
                fab_atual = row[1] if row else None
                venda_atual = row[2] if row else None

                novo_saldo = saldo_atual + float(delta)
                novo_fab = ultima_fabricacao_valor if ultima_fabricacao_valor is not None else fab_atual
                novo_venda = ultima_venda_valor if ultima_venda_valor is not None else venda_atual

                await db.execute('''
                    UPDATE banco_usuarios
                    SET saldo = ?,
                        ultima_fabricacao_valor = ?,
                        ultima_venda_valor = ?,
                        user_name = ?,
                        atualizado_em = ?
                    WHERE guild_id = ? AND user_id = ?
                ''', (
                    float(novo_saldo),
                    (float(novo_fab) if novo_fab is not None else None),
                    (float(novo_venda) if novo_venda is not None else None),
                    str(user_name),
                    datetime.now().isoformat(),
                    int(guild_id), int(user_id)
                ))

                await db.execute('''
                    INSERT INTO movimentos_banco
                    (guild_id, user_id, user_name, origem, delta, saldo_antes, saldo_depois, motivo, ref_tipo, ref_id, criado_em)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    int(guild_id), int(user_id), str(user_name),
                    str(origem),
                    float(delta),
                    float(saldo_atual),
                    float(novo_saldo),
                    (str(motivo) if motivo else None),
                    (str(ref_tipo) if ref_tipo else None),
                    (int(ref_id) if ref_id is not None else None),
                    datetime.now().isoformat()
                ))

                await db.commit()
                return float(novo_saldo)
        except Exception as e:
            print(f"❌ Erro ao aplicar movimento no banco: {e}")
            traceback.print_exc()
            return None

    async def get_extrato_banco(self, guild_id: int, user_id: int, limite: int = 50):
        try:
            async with aiosqlite.connect(self.db_name) as db:
                async with db.execute('''
                    SELECT origem, delta, saldo_antes, saldo_depois, motivo, ref_tipo, ref_id, criado_em
                    FROM movimentos_banco
                    WHERE guild_id = ? AND user_id = ?
                    ORDER BY id DESC
                    LIMIT ?
                ''', (int(guild_id), int(user_id), int(limite))) as cursor:
                    return await cursor.fetchall()
        except Exception as e:
            print(f"❌ Erro ao buscar extrato: {e}")
            traceback.print_exc()
            return []

    # -------------------- LOGS PRINCIPAIS --------------------

    async def registrar_fabricacao(self, guild_id: int, user_id: int, user_name: str,
                                   produto_id: str, produto_nome: str, quantidade: int,
                                   custo_total: float, materiais: str):
        try:
            async with aiosqlite.connect(self.db_name) as db:
                cursor = await db.execute('''
                    INSERT INTO logs_fabricacao 
                    (guild_id, user_id, user_name, produto_id, produto_nome, quantidade, custo_total, materiais, data_fabricacao)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    int(guild_id), int(user_id), str(user_name),
                    str(produto_id), str(produto_nome), int(quantidade),
                    float(custo_total), str(materiais), datetime.now().isoformat()
                ))
                await db.commit()
                return cursor.lastrowid
        except Exception as e:
            print(f"❌ Erro ao registrar fabricação: {e}")
            traceback.print_exc()
            return None

    async def registrar_venda(self, guild_id: int, user_id: int, user_name: str,
                              produto_id: str, produto_nome: str, quantidade: int,
                              valor_total: float, comprador: str = None):
        try:
            async with aiosqlite.connect(self.db_name) as db:
                cursor = await db.execute('''
                    INSERT INTO logs_vendas
                    (guild_id, user_id, user_name, produto_id, produto_nome, quantidade, valor_total, comprador, data_venda)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    int(guild_id), int(user_id), str(user_name),
                    str(produto_id), str(produto_nome),
                    int(quantidade), float(valor_total), comprador,
                    datetime.now().isoformat()
                ))
                await db.commit()
                return cursor.lastrowid
        except Exception as e:
            print(f"❌ Erro ao registrar venda: {e}")
            traceback.print_exc()
            return None

    async def criar_encomenda(self, guild_id: int, user_id: int, user_name: str,
                              produto_id: str, produto_nome: str, quantidade: int,
                              preco_unit: float, cliente: str = None):
        try:
            async with aiosqlite.connect(self.db_name) as db:
                cursor = await db.execute('''
                    INSERT INTO encomendas
                    (guild_id, user_id, user_name, produto_id, produto_nome, quantidade, preco_unit, cliente, status, criado_em)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'pendente', ?)
                ''', (
                    int(guild_id), int(user_id), str(user_name),
                    str(produto_id), str(produto_nome),
                    int(quantidade), float(preco_unit), cliente,
                    datetime.now().isoformat()
                ))
                await db.commit()
                return cursor.lastrowid
        except Exception as e:
            print(f"❌ Erro ao criar encomenda: {e}")
            traceback.print_exc()
            return None

    async def confirmar_encomenda(self, encomenda_id: int, confirmado_por_id: int):
        try:
            async with aiosqlite.connect(self.db_name) as db:
                await db.execute('''
                    UPDATE encomendas
                    SET status = 'confirmada',
                        confirmado_em = ?,
                        confirmado_por_id = ?
                    WHERE id = ? AND status = 'pendente'
                ''', (datetime.now().isoformat(), int(confirmado_por_id), int(encomenda_id)))

                await db.commit()

                async with db.execute('SELECT status FROM encomendas WHERE id = ?', (int(encomenda_id),)) as cursor:
                    row = await cursor.fetchone()
                    return (row is not None and row[0] == 'confirmada')
        except Exception as e:
            print(f"❌ Erro ao confirmar encomenda: {e}")
            traceback.print_exc()
            return False

    async def get_encomenda_por_id(self, encomenda_id: int):
        """
        Retorna:
        (guild_id, user_id, user_name, produto_id, produto_nome, quantidade, preco_unit, cliente, status)
        """
        try:
            async with aiosqlite.connect(self.db_name) as db:
                async with db.execute('''
                    SELECT guild_id, user_id, user_name, produto_id, produto_nome, quantidade, preco_unit, cliente, status
                    FROM encomendas
                    WHERE id = ?
                ''', (int(encomenda_id),)) as cursor:
                    return await cursor.fetchone()
        except Exception as e:
            print(f"❌ Erro ao buscar encomenda: {e}")
            traceback.print_exc()
            return None

    async def set_encomenda_message_id(self, encomenda_id: int, message_id: int):
        """Associa a mensagem do log à encomenda para reidratar botões após reinício."""
        try:
            async with aiosqlite.connect(self.db_name) as db:
                await db.execute('''
                    UPDATE encomendas
                    SET message_id = ?
                    WHERE id = ?
                ''', (int(message_id), int(encomenda_id)))
                await db.commit()
            return True
        except Exception as e:
            print(f"❌ Erro ao salvar message_id da encomenda: {e}")
            traceback.print_exc()
            return False

    async def listar_encomendas_pendentes(self):
        """Retorna lista de (id, guild_id, user_id, message_id) pendentes com mensagem."""
        try:
            async with aiosqlite.connect(self.db_name) as db:
                async with db.execute('''
                    SELECT id, guild_id, user_id, message_id
                    FROM encomendas
                    WHERE status = 'pendente' AND message_id IS NOT NULL
                ''') as cursor:
                    return await cursor.fetchall()
        except Exception as e:
            print(f"❌ Erro ao listar encomendas pendentes: {e}")
            traceback.print_exc()
            return []

    # -------------------- CONSULTAS PARA /BANCO --------------------

    async def get_logs_usuario_fabricacao(self, guild_id: int, user_id: int, limite: int = 30):
        try:
            async with aiosqlite.connect(self.db_name) as db:
                async with db.execute('''
                    SELECT produto_nome, quantidade, custo_total, data_fabricacao, materiais
                    FROM logs_fabricacao
                    WHERE guild_id = ? AND user_id = ?
                    ORDER BY id DESC
                    LIMIT ?
                ''', (int(guild_id), int(user_id), int(limite))) as cursor:
                    return await cursor.fetchall()
        except Exception as e:
            print(f"❌ Erro ao buscar logs de fabricação: {e}")
            traceback.print_exc()
            return []

    async def get_logs_usuario_vendas(self, guild_id: int, user_id: int, limite: int = 30):
        try:
            async with aiosqlite.connect(self.db_name) as db:
                async with db.execute('''
                    SELECT produto_nome, quantidade, valor_total, comprador, data_venda
                    FROM logs_vendas
                    WHERE guild_id = ? AND user_id = ?
                    ORDER BY id DESC
                    LIMIT ?
                ''', (int(guild_id), int(user_id), int(limite))) as cursor:
                    return await cursor.fetchall()
        except Exception as e:
            print(f"❌ Erro ao buscar logs de vendas: {e}")
            traceback.print_exc()
            return []

    # -------------------- DASHBOARD (SERVIDOR) --------------------

    async def get_logs_vendas_servidor(self, guild_id: int, limite: int = 10):
        try:
            async with aiosqlite.connect(self.db_name) as db:
                async with db.execute('''
                    SELECT produto_nome, quantidade, valor_total, comprador, data_venda, user_name
                    FROM logs_vendas
                    WHERE guild_id = ?
                    ORDER BY id DESC
                    LIMIT ?
                ''', (int(guild_id), int(limite))) as cursor:
                    return await cursor.fetchall()
        except Exception as e:
            print(f"❌ Erro ao buscar logs de vendas do servidor: {e}")
            traceback.print_exc()
            return []

    async def get_total_vendas_periodo(self, guild_id: int, inicio_iso: str, fim_iso: str):
        try:
            async with aiosqlite.connect(self.db_name) as db:
                async with db.execute('''
                    SELECT COALESCE(SUM(valor_total), 0)
                    FROM logs_vendas
                    WHERE guild_id = ? AND data_venda BETWEEN ? AND ?
                ''', (int(guild_id), str(inicio_iso), str(fim_iso))) as cursor:
                    row = await cursor.fetchone()
                    return float(row[0] or 0.0)
        except Exception as e:
            print(f"❌ Erro ao somar vendas por período: {e}")
            traceback.print_exc()
            return 0.0

    async def get_logs_fabricacao_servidor(self, guild_id: int, limite: int = 10):
        try:
            async with aiosqlite.connect(self.db_name) as db:
                async with db.execute('''
                    SELECT produto_nome, quantidade, custo_total, data_fabricacao, user_name
                    FROM logs_fabricacao
                    WHERE guild_id = ?
                    ORDER BY id DESC
                    LIMIT ?
                ''', (int(guild_id), int(limite))) as cursor:
                    return await cursor.fetchall()
        except Exception as e:
            print(f"❌ Erro ao buscar logs de fabricação do servidor: {e}")
            traceback.print_exc()
            return []

    async def get_total_custo_fabricacao_periodo(self, guild_id: int, inicio_iso: str, fim_iso: str):
        try:
            async with aiosqlite.connect(self.db_name) as db:
                async with db.execute('''
                    SELECT COALESCE(SUM(custo_total), 0)
                    FROM logs_fabricacao
                    WHERE guild_id = ? AND data_fabricacao BETWEEN ? AND ?
                ''', (int(guild_id), str(inicio_iso), str(fim_iso))) as cursor:
                    row = await cursor.fetchone()
                    return float(row[0] or 0.0)
        except Exception as e:
            print(f"❌ Erro ao somar fabricação por período: {e}")
            traceback.print_exc()
            return 0.0

    async def get_encomendas_pendentes_servidor(self, guild_id: int, limite: int = 10):
        try:
            async with aiosqlite.connect(self.db_name) as db:
                async with db.execute('''
                    SELECT id, produto_nome, quantidade, preco_unit, cliente, user_name, criado_em
                    FROM encomendas
                    WHERE guild_id = ? AND status = 'pendente'
                    ORDER BY id DESC
                    LIMIT ?
                ''', (int(guild_id), int(limite))) as cursor:
                    return await cursor.fetchall()
        except Exception as e:
            print(f"❌ Erro ao listar encomendas pendentes do servidor: {e}")
            traceback.print_exc()
            return []

    async def get_ultimas_encomendas_confirmadas(self, guild_id: int, limite: int = 5):
        try:
            async with aiosqlite.connect(self.db_name) as db:
                async with db.execute('''
                    SELECT id, produto_nome, quantidade, preco_unit, cliente, user_name, confirmado_em
                    FROM encomendas
                    WHERE guild_id = ? AND status = 'confirmada'
                    ORDER BY id DESC
                    LIMIT ?
                ''', (int(guild_id), int(limite))) as cursor:
                    return await cursor.fetchall()
        except Exception as e:
            print(f"❌ Erro ao listar encomendas confirmadas do servidor: {e}")
            traceback.print_exc()
            return []

    async def get_metas_aprovadas_periodo(self, guild_id: int, inicio_iso: str, fim_iso: str):
        try:
            async with aiosqlite.connect(self.db_name) as db:
                async with db.execute('''
                    SELECT COUNT(*)
                    FROM metas_aprovadas
                    WHERE guild_id = ? AND data_aprovacao BETWEEN ? AND ?
                ''', (int(guild_id), str(inicio_iso), str(fim_iso))) as cursor:
                    row = await cursor.fetchone()
                    return int(row[0] or 0)
        except Exception as e:
            print(f"❌ Erro ao contar metas aprovadas no período: {e}")
            traceback.print_exc()
            return 0

    async def get_movimentos_banco_servidor(self, guild_id: int, limite: int = 10):
        try:
            async with aiosqlite.connect(self.db_name) as db:
                async with db.execute('''
                    SELECT user_name, origem, delta, saldo_depois, criado_em
                    FROM movimentos_banco
                    WHERE guild_id = ?
                    ORDER BY id DESC
                    LIMIT ?
                ''', (int(guild_id), int(limite))) as cursor:
                    return await cursor.fetchall()
        except Exception as e:
            print(f"❌ Erro ao buscar movimentos do banco do servidor: {e}")
            traceback.print_exc()
            return []

    async def get_top_saldos_servidor(self, guild_id: int, limite: int = 5):
        try:
            async with aiosqlite.connect(self.db_name) as db:
                async with db.execute('''
                    SELECT user_name, saldo
                    FROM banco_usuarios
                    WHERE guild_id = ?
                    ORDER BY saldo DESC
                    LIMIT ?
                ''', (int(guild_id), int(limite))) as cursor:
                    return await cursor.fetchall()
        except Exception as e:
            print(f"❌ Erro ao buscar top saldos do servidor: {e}")
            traceback.print_exc()
            return []

    # -------------------- REGISTROS PENDENTES --------------------

    async def criar_registro_pendente(self, message_id: int, guild_id: int, user_id: int, nome: str, rg: str):
        """Salva (ou atualiza) um registro pendente ligado a uma mensagem."""
        try:
            async with aiosqlite.connect(self.db_name) as db:
                now = datetime.now().isoformat()
                await db.execute('''
                    INSERT OR REPLACE INTO registros_pendentes
                    (message_id, guild_id, user_id, nome, rg, status, criado_em, resolvido_em, resolvido_por_id, resultado)
                    VALUES (?, ?, ?, ?, ?, 'pendente', ?, NULL, NULL, NULL)
                ''', (int(message_id), int(guild_id), int(user_id), str(nome), str(rg), now))
                await db.commit()
                return True
        except Exception as e:
            print(f"❌ Erro ao criar registro pendente: {e}")
            traceback.print_exc()
            return False

    async def obter_registro_pendente_por_mensagem(self, message_id: int):
        """Retorna (message_id, guild_id, user_id, nome, rg, status) se existir."""
        try:
            async with aiosqlite.connect(self.db_name) as db:
                async with db.execute('''
                    SELECT message_id, guild_id, user_id, nome, rg, status
                    FROM registros_pendentes
                    WHERE message_id = ?
                ''', (int(message_id),)) as cursor:
                    return await cursor.fetchone()
        except Exception as e:
            print(f"❌ Erro ao obter registro pendente: {e}")
            traceback.print_exc()
            return None

    async def listar_registros_pendentes(self):
        """Retorna lista de (message_id, guild_id, user_id, nome, rg) ainda pendentes."""
        try:
            async with aiosqlite.connect(self.db_name) as db:
                async with db.execute('''
                    SELECT message_id, guild_id, user_id, nome, rg
                    FROM registros_pendentes
                    WHERE status = 'pendente'
                ''') as cursor:
                    return await cursor.fetchall()
        except Exception as e:
            print(f"❌ Erro ao listar registros pendentes: {e}")
            traceback.print_exc()
            return []

    async def resolver_registro_pendente(self, message_id: int, resolvido_por_id: int, resultado: str):
        """Marca um registro como resolvido (aprovado/negado)."""
        try:
            async with aiosqlite.connect(self.db_name) as db:
                now = datetime.now().isoformat()
                cursor = await db.execute('''
                    UPDATE registros_pendentes
                    SET status = 'resolvido',
                        resolvido_em = ?,
                        resolvido_por_id = ?,
                        resultado = ?
                    WHERE message_id = ? AND status = 'pendente'
                ''', (now, int(resolvido_por_id), str(resultado), int(message_id)))
                await db.commit()
                return cursor.rowcount > 0
        except Exception as e:
            print(f"❌ Erro ao resolver registro pendente: {e}")
            traceback.print_exc()
            return False

    async def limpar_dados_servidor(self, guild_id: int):
        try:
            async with aiosqlite.connect(self.db_name) as db:
                await db.execute('DELETE FROM logs_fabricacao WHERE guild_id = ?', (int(guild_id),))
                await db.execute('DELETE FROM logs_vendas WHERE guild_id = ?', (int(guild_id),))
                await db.execute('DELETE FROM encomendas WHERE guild_id = ?', (int(guild_id),))
                await db.execute('DELETE FROM produtos_precos WHERE guild_id = ?', (int(guild_id),))
                await db.execute('DELETE FROM banco_usuarios WHERE guild_id = ?', (int(guild_id),))
                await db.execute('DELETE FROM movimentos_banco WHERE guild_id = ?', (int(guild_id),))
                await db.execute('DELETE FROM estoque_produtos WHERE guild_id = ?', (int(guild_id),))
                await db.execute('DELETE FROM config_servidores WHERE guild_id = ?', (int(guild_id),))
                await db.execute('DELETE FROM registros_pendentes WHERE guild_id = ?', (int(guild_id),))
                await db.commit()
                return True
        except Exception as e:
            print(f"❌ Erro ao limpar dados do servidor: {e}")
            traceback.print_exc()
            return False
