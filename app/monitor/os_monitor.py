import json
import logging
import os
import threading
import time
from datetime import datetime, timedelta

import requests
import urllib3
import schedule

from .config import (
    BOT_TOKEN_GOFIBRA,
    GRUPO_1,
    GRUPO_2,
    GRUPO_ALERTAS,
    LOG_FILE,
    MIN_OFFLINE_DURATION,
    ROUTE_CHECK_INTERVAL,
    TMP_DIR,
    TMP_HISTORY_DIR,
    TMP_INSTALL_DIR,
    TMP_OFFLINE_DIR,
    TMP_PPPOE_MAP_DIR,
    TMP_REMOVED_DIR,
    TMP_SIGNALS_DIR,
)
from .utils import get_db_connection


urllib3.disable_warnings()

HISTORICO_DIR = "/opt/monitor_os"
HISTORICO_FILE = os.path.join(HISTORICO_DIR, "historico.json")

GRUPO_TECNICO01 = ["5581989096363"]
GRUPO_RELATORIO = ["5581989096363"]
GRUPO_SUPERVISOR = ["5581989096363"]
GRUPO_STATUS_ABERTA = ["558189096363:35@s"]
GRUPO_STATUS_FINALIZADA = ["558189096363:35@s"]
GRUPO_STATUS_EXECUCAO = ["558189096363:35@s"]
GRUPO_STATUS_PENDENTE = ["558189096363:35@s"]


def setup_logger() -> logging.Logger:
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.DEBUG)

    if logger.handlers:
        return logger

    log_format = "%(asctime)s - %(levelname)s - %(message)s"
    formatter = logging.Formatter(log_format)

    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
    file_handler = logging.FileHandler(LOG_FILE)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    return logger


logger = setup_logger()

MOTIVOS = {
    1: "Suporte - CLIENTE OFF SEM INTERNET",
    2: "Suporte - MANUTENÇÃO DE CAIXA FTTH",
    3: "Suporte - CLIENTE COM ALTO DB 28",
    4: "Suporte - PING JOGO ALTO",
    5: "Suporte - Internet Caindo ou LENTA",
    6: "Suporte - TROCA DE ONU",
    7: "Suporte - ONU NÃO DEVOLVEU",
    8: "Suporte - SUPORTE A IPTV",
    9: "Suporte - Remoção CONECTOR DE FIBRA ou ONU",
    21: "Suporte - Outros",
    22: "Financeiro - COLOCAR NO SPC",
    23: "Financeiro - Mudança de Plano",
    24: "Suporte - Troca De Endereço",
    25: "Suporte - Configuração de Roteador",
    26: "Financeiro - Outros",
    27: "Financeiro - Cancelamento da Internet",
    28: "Financeiro - Entrega de Carnê",
    29: "Cobrança - Título em atraso",
    30: "Cobrança - Lembrança de Pagamento",
    19: "Suporte - Instalação de Internet Fibra",
    100: "Troca de Onts - Clientes 900MB",
    101: "Troca de Onts - Clientes 700MB",
}


def construir_historico_inicial():
    historico_inicial = {}
    ocorrencias = get_os_by_status_and_tipo([0, 1, 2, 3])

    for ocorrencia in ocorrencias:
        id_ocorrencia = ocorrencia["id_ocorrencia"]
        historico_inicial[id_ocorrencia] = {
            "status": ocorrencia["status_ocorrencia"],
            "ultima_alteracao": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "data_abertura": ocorrencia["data_cadastro"],
            "tipo_ocorrencia": ocorrencia["tipo_ocorrencia"],
            "cliente_nome": ocorrencia["cliente_nome"],
            "responsavel": ocorrencia["responsavel"],
            "observacoes": ocorrencia.get("observacoes", ""),
            "latitude": ocorrencia.get("latitude", None),
            "longitude": ocorrencia.get("longitude", None),
        }

    return historico_inicial


def send_alert_tec_gofibra(message, contact_id):
    url = "https://gofibra.webchat.net.br/api/message/add/2/"

    payload = {
        "token": BOT_TOKEN_GOFIBRA,
        "resolve_links": "1",
        "message": message,
        "contact": contact_id,
    }

    try:
        response = requests.post(url, data=payload, verify=False, timeout=15)
        if response.status_code == 200:
            logger.info("Mensagem enviada para %s: %s", contact_id, response.text)
        else:
            logger.warning(
                "Falha ao enviar mensagem para %s, Status: %s, Resposta: %s",
                contact_id,
                response.status_code,
                response.text,
            )
    except Exception as error:
        logger.error("Erro ao enviar mensagem para %s: %s", contact_id, error)


def send_alert(message, group_ids):
    url = "https://gofibra.webchat.net.br/api/message/add/2/"
    payload_base = {
        "token": BOT_TOKEN_GOFIBRA,
        "resolve_links": "1",
        "message": message,
    }

    for group_id in group_ids:
        payload = payload_base.copy()
        payload["contact"] = group_id
        try:
            response = requests.post(url, data=payload, verify=False, timeout=15)
            if response.status_code == 200:
                logger.info("Mensagem enviada para %s: %s", group_id, response.text)
            else:
                logger.warning(
                    "Falha ao enviar mensagem para %s, Status: %s, Resposta: %s",
                    group_id,
                    response.status_code,
                    response.text,
                )
        except Exception as error:
            logger.error("Erro ao enviar mensagem para %s: %s", group_id, error)


def send_alert_gofibra(message, group_ids):
    url = "https://gofibra.webchat.net.br/api/message/add/2/"
    payload_base = {
        "token": BOT_TOKEN_GOFIBRA,
        "resolve_links": "1",
        "message": message,
    }

    for group_id in group_ids:
        payload = payload_base.copy()
        payload["contact"] = group_id
        try:
            response = requests.post(url, data=payload, verify=False, timeout=15)
            if response.status_code == 200:
                logger.info("Mensagem enviada para %s: %s", group_id, response.text)
            else:
                logger.warning(
                    "Falha ao enviar mensagem para %s, Status: %s, Resposta: %s",
                    group_id,
                    response.status_code,
                    response.text,
                )
        except Exception as error:
            logger.error("Erro ao enviar mensagem para %s: %s", group_id, error)


def calcular_tempo_aberto(data_abertura):
    abertura = datetime.strptime(data_abertura, "%Y-%m-%d %H:%M:%S")
    agora = datetime.now()
    diferenca = agora - abertura
    horas = diferenca.total_seconds() / 3600
    return f"{horas:.2f} horas"


def carregar_historico():
    os.makedirs(HISTORICO_DIR, exist_ok=True)
    if os.path.exists(HISTORICO_FILE):
        with open(HISTORICO_FILE, "r") as file:
            try:
                return json.load(file)
            except json.JSONDecodeError:
                logger.warning("O arquivo historico.json está vazio ou corrompido.")
                return {}
    return {}


def salvar_historico(historico):
    try:
        with open(HISTORICO_FILE, "w") as file:
            json.dump(historico, file, indent=4)
        logger.info("Histórico salvo com sucesso.")
    except Exception as error:
        logger.error("Erro ao salvar o histórico: %s", error)


def converter_data(data_str):
    if data_str is None:
        return None
    try:
        return datetime.strptime(data_str, "%d-%m-%Y %H:%M:%S").strftime("%Y-%m-%d %H:%M:%S")
    except ValueError:
        logger.error("Erro ao converter data: %s", data_str)
        return None


def obter_tecnico_info(responsavel_id):
    tecnico = db.session.query(Usuario).filter_by(id=responsavel_id).first()
    if tecnico:
        return {"name": tecnico.name, "ramal": tecnico.ramal}
    return None


def coletar_os_por_setor(setor_id):
    connection = get_db_connection()
    if not connection:
        logger.error("Erro na conexão com o banco de dados")
        return []

    try:
        cursor = connection.cursor()
        query = """
            SELECT
                atendimento_os.id AS id_ocorrencia,
                atendimento_os.status AS status,
                TO_CHAR(atendimento_os.data_agendamento, 'DD-MM-YYYY HH24:MI:SS') AS data_agendamento,
                atendimento_os.conteudo AS conteudo,
                atendimento_os.tipoos AS tipoos,
                atendimento_os.prioridade AS prioridade,
                TO_CHAR(atendimento_os.data_cadastro, 'DD-MM-YYYY HH24:MI:SS') AS data_cadastro,
                TO_CHAR(atendimento_os.data_alteracao, 'DD-MM-YYYY HH24:MI:SS') AS data_alteracao,
                TO_CHAR(atendimento_os.data_finalizacao, 'DD-MM-YYYY HH24:MI:SS') AS data_finalizacao,
                atendimento_os.observacao AS observacao,
                atendimento_os.servicoprestado AS servicoprestado,
                admcore_pessoa.nome AS cliente_nome,
                admcore_endereco.logradouro AS endereco_logradouro,
                admcore_endereco.numero AS endereco_numero,
                admcore_endereco.bairro AS endereco_bairro,
                admcore_endereco.cidade AS endereco_cidade,
                admcore_endereco.uf AS endereco_uf,
                admcore_endereco.cep AS endereco_cep,
                auth_user.name AS tecnico_nome,
                auth_user.ramal AS tecnico_ramal,
                atendimento_os.setor_id AS setor_id
            FROM
                atendimento_os
            LEFT JOIN atendimento_ocorrencia ON atendimento_os.ocorrencia_id = atendimento_ocorrencia.id
            LEFT JOIN admcore_clientecontrato ON atendimento_ocorrencia.clientecontrato_id = admcore_clientecontrato.id
            LEFT JOIN admcore_cliente ON admcore_clientecontrato.cliente_id = admcore_cliente.id
            LEFT JOIN admcore_pessoa ON admcore_cliente.pessoa_id = admcore_pessoa.id
            LEFT JOIN admcore_endereco ON admcore_cliente.endereco_id = admcore_endereco.id
            LEFT JOIN auth_user ON atendimento_os.responsavel_id = auth_user.id
            WHERE
                atendimento_os.setor_id = %s
            ORDER BY
                atendimento_os.data_cadastro ASC NULLS FIRST;
        """
        cursor.execute(query, (setor_id,))
        resultados = cursor.fetchall()

        lista_ocorrencias = [
            {
                "id_ocorrencia": row[0],
                "status": row[1],
                "data_agendamento": row[2],
                "conteudo": row[3],
                "tipoos": row[4],
                "prioridade": row[5],
                "data_cadastro": row[6],
                "data_alteracao": row[7],
                "data_finalizacao": row[8],
                "observacao": row[9],
                "servicoprestado": row[10],
                "cliente_nome": row[11] or "Nome não informado",
                "endereco": f"{row[12]}, {row[13]}" if row[12] and row[13] else "Endereço não informado",
                "endereco_bairro": row[14] or "Bairro não informado",
                "endereco_cidade": row[15] or "Cidade não informada",
                "tecnico_nome": row[18] or "Técnico não informado",
                "tecnico_ramal": row[19] or "TECNICO SEM NUMERO",
                "setor_id": row[20],
            }
            for row in resultados
        ]
        return lista_ocorrencias

    except Exception as error:
        logger.error("Erro ao coletar O.S. por setor_id %s: %s", setor_id, error)
        return []
    finally:
        if connection:
            cursor.close()
            connection.close()


def get_os_by_status_and_tipo(status, tipo_ocorrencia=None):
    connection = get_db_connection()
    if not connection:
        logger.error("Erro na conexão com o banco de dados")
        return []
    try:
        cursor = connection.cursor()

        query_base = """
            SELECT
                atendimento_ocorrencia.id AS id_ocorrencia,
                atendimento_ocorrencia.numero AS numero_ocorrencia,
                atendimento_os.status AS status_os,
                atendimento_ocorrencia.conteudo AS conteudo_ocorrencia,
                TO_CHAR(atendimento_ocorrencia.data_agendamento, 'DD-MM-YYYY HH24:MI:SS') AS data_agendamento,
                TO_CHAR(atendimento_ocorrencia.data_cadastro, 'DD-MM-YYYY HH24:MI:SS') AS data_cadastro,
                TO_CHAR(atendimento_ocorrencia.data_alteracao, 'DD-MM-YYYY HH24:MI:SS') AS data_alteracao,
                TO_CHAR(atendimento_ocorrencia.data_finalizacao, 'DD-MM-YYYY HH24:MI:SS') AS data_finalizacao,
                atendimento_ocorrencia.observacoes AS observacoes,
                atendimento_ocorrencia.contato AS contato,
                atendimento_ocorrencia.contato_numero AS contato_numero,
                atendimento_ocorrencia.tipo_id AS tipo_ocorrencia,
                atendimento_os.responsavel_id AS responsavel,
                auth_user.name AS tecnico_nome,
                auth_user.ramal AS tecnico_ramal,
                atendimento_ocorrencia.clientecontrato_id AS clientecontrato,
                admcore_pessoa.nome AS cliente_nome,
                atendimento_os.servicoprestado AS servicoprestado,
                admcore_endereco.logradouro AS endereco_logradouro,
                admcore_endereco.numero AS endereco_numero,
                admcore_endereco.bairro AS endereco_bairro,
                admcore_endereco.cidade AS endereco_cidade,
                admcore_endereco.cep AS endereco_cep,
                admcore_endereco.uf AS endereco_uf,
                admcore_endereco.pais AS endereco_pais,
                admcore_endereco.complemento AS endereco_complemento,
                admcore_endereco.pontoreferencia AS endereco_pontoreferencia,
                atendimento_os.latitude AS latitude,
                atendimento_os.longitude AS longitude,
                atendimento_os.usuario_id AS usuario_id,
                usuario_abre.name AS usuario_abre_nome,
                usuario_finaliza.name AS usuario_finaliza_nome
            FROM atendimento_ocorrencia
            LEFT JOIN atendimento_os ON atendimento_ocorrencia.id = atendimento_os.ocorrencia_id
            LEFT JOIN admcore_clientecontrato ON atendimento_ocorrencia.clientecontrato_id = admcore_clientecontrato.id
            LEFT JOIN admcore_cliente ON admcore_clientecontrato.cliente_id = admcore_cliente.id
            LEFT JOIN admcore_pessoa ON admcore_cliente.pessoa_id = admcore_pessoa.id
            LEFT JOIN admcore_endereco ON admcore_cliente.endereco_id = admcore_endereco.id
            LEFT JOIN auth_user ON atendimento_os.responsavel_id = auth_user.id
            LEFT JOIN auth_user AS usuario_abre ON atendimento_os.usuario_id = usuario_abre.id
            LEFT JOIN auth_user AS usuario_finaliza ON atendimento_os.usuario_finaliza_id = usuario_finaliza.id
        """

        if tipo_ocorrencia:
            query = (
                query_base
                + """
                WHERE atendimento_ocorrencia.status IN %s
                  AND atendimento_ocorrencia.tipo_id = %s
                ORDER BY atendimento_ocorrencia.data_cadastro ASC NULLS FIRST;
            """
            )
            cursor.execute(query, (tuple(status), tipo_ocorrencia))
        else:
            query = (
                query_base
                + """
                WHERE atendimento_ocorrencia.status IN %s
                ORDER BY atendimento_ocorrencia.data_cadastro ASC NULLS FIRST;
            """
            )
            cursor.execute(query, (tuple(status),))

        results = cursor.fetchall()

        ocorrencias = []
        for row in results:
            ocorrencias.append(
                {
                    "id_ocorrencia": row[0],
                    "numero_ocorrencia": row[1],
                    "status_ocorrencia": row[2],
                    "conteudo_ocorrencia": row[3],
                    "data_agendamento": converter_data(row[4]),
                    "data_cadastro": converter_data(row[5]),
                    "data_alteracao": converter_data(row[6]),
                    "data_finalizacao": converter_data(row[7]),
                    "observacoes": row[8],
                    "contato": row[9],
                    "contato_numero": row[10],
                    "tipo_ocorrencia": row[11],
                    "responsavel": row[12],
                    "tecnico_nome": row[13],
                    "tecnico_ramal": row[14],
                    "clientecontrato": row[15],
                    "cliente_nome": row[16],
                    "servicoprestado": row[17],
                    "endereco": (
                        f"{row[18]}, {row[19]}, {row[20]}, {row[21]} - {row[22]} - {row[23]},"
                        f" {row[24]} ({row[25]})"
                    ),
                    "latitude": row[27],
                    "longitude": row[28],
                    "usuario_id": row[29],
                    "usuario_abre_nome": row[30],
                    "usuario_finaliza_nome": row[31],
                }
            )
        return ocorrencias
    except Exception as error:
        logger.error(
            "Erro ao buscar ocorrências com status %s e tipo %s: %s", status, tipo_ocorrencia, error
        )
        return []
    finally:
        if connection:
            cursor.close()
            connection.close()


def formatar_tempo_execucao(segundos):
    tempo = timedelta(seconds=segundos)
    horas, resto = divmod(tempo.total_seconds(), 3600)
    minutos, segundos = divmod(resto, 60)
    return f"{int(horas)} horas, {int(minutos)} minutos, e {int(segundos)} segundos"


def gerar_alerta(ocorrencia, status_atual, ultimo_status, historico):
    mensagem = None
    id_ocorrencia = str(ocorrencia["id_ocorrencia"])
    grupo_destino = None

    latitude = historico[id_ocorrencia].get("latitude")
    longitude = historico[id_ocorrencia].get("longitude")

    if latitude and longitude:
        link_maps = f"https://www.google.com/maps?q={latitude},{longitude}"
    else:
        link_maps = None

    if status_atual == 0:
        grupo_destino = GRUPO_STATUS_ABERTA
        mensagem = (
            f"\U000026A0 *Ocorrência {id_ocorrencia} Aberta*\n"
            f"*Cliente:* ```{ocorrencia['cliente_nome']}```\n"
            f"*Usuário que Abriu a Ocorrência:* ```{ocorrencia['usuario_abre_nome']}```\n"
            f"*Responsável Técnico:* ```{ocorrencia['tecnico_nome']}```\n"
            f"*Abertura:* ```{ocorrencia['data_cadastro']}```\n"
            f"*Endereço:* ```{ocorrencia['endereco']}```\n"
            "--------------------------------------------------\n"
            f"*Conteúdo:* ```{ocorrencia['conteudo_ocorrencia']}```\n\n"
        )

    elif status_atual == 1:
        grupo_destino = GRUPO_STATUS_FINALIZADA
        tempo_aberto = calcular_tempo_aberto(historico[id_ocorrencia]["data_abertura"])
        hora_execucao = historico[id_ocorrencia].get("hora_execucao", None)
        tempo_execucao = calcular_tempo_decorrido(hora_execucao) if hora_execucao else "Não registrado"

        mensagem = (
            f"\U00002705 *Ocorrência {id_ocorrencia} Finalizada*\n"
            f"*Cliente:* ```{ocorrencia['cliente_nome']}```\n"
            f"*Responsável:* ```{ocorrencia['tecnico_nome']}```\n"
            f"*Endereço:* ```{ocorrencia['endereco']}```\n"
            f"*Tempo Aberta:* ```{tempo_aberto}```\n"
            f"*Tempo de Execução:* ```{tempo_execucao}```\n"
            f"*Usuário que Finalizou:* ```{ocorrencia['usuario_finaliza_nome']}```\n"
            "--------------------------------------------------\n"
            f"*RELATORIO TECNICO:* ```{ocorrencia['servicoprestado']}```\n"
        )

    elif status_atual == 2:
        grupo_destino = GRUPO_STATUS_EXECUCAO
        hora_execucao = historico[id_ocorrencia].get("hora_execucao", "Não registrada")
        mensagem = (
            f"\U0001F527 *Ocorrência {id_ocorrencia} em Execução*\n"
            f"*Cliente:* ```{ocorrencia['cliente_nome']}```\n"
            f"*Responsável:* ```{ocorrencia['tecnico_nome']}```\n"
            f"*Endereço:* ```{ocorrencia['endereco']}```\n"
            f"*Hora de Início:* ```{hora_execucao}```\n"
        )

    elif status_atual == 3:
        grupo_destino_pendente = [GRUPO_SUPERVISOR]
        grupo_destino = GRUPO_STATUS_PENDENTE
        hora_execucao = historico[id_ocorrencia].get("hora_execucao", None)
        tempo_execucao = calcular_tempo_decorrido(hora_execucao) if hora_execucao else "Não registrado"

        mensagem = (
            f"\U000023F3 *Ocorrência {id_ocorrencia}* ```AGUARDANDO LIBERAÇAO```\n"
            f"*Cliente:* ```{ocorrencia['cliente_nome']}```\n"
            f"*Responsável:* ```{ocorrencia['tecnico_nome']}```\n"
            f"*Endereço:* ```{ocorrencia['endereco']}```\n"
            f"*Tempo em Execução:* ```{tempo_execucao}```\n"
            "--------------------------------------------------\n"
            f"*Conteúdo:* ```{ocorrencia['conteudo_ocorrencia']}```\n\n"
            "--------------------------------------------------\n"
            f"*RELATORIO TECNICO:* ```{ocorrencia['servicoprestado']}```\n"
        )

    if mensagem and grupo_destino:
        send_alert(mensagem, grupo_destino)
        logger.info("Alerta gerado para ocorrência %s (Status: %s).", id_ocorrencia, status_atual)

        if status_atual == 2 and link_maps:
            mensagem_localizacao = (
                f"\U0001F4CD *Localização da Ocorrência {id_ocorrencia}:* ({link_maps})"
            )
            send_alert(mensagem_localizacao, grupo_destino)
            logger.info("Localização enviada para ocorrência %s.", id_ocorrencia)

        if status_atual == 3:
            send_alert_gofibra(mensagem, grupo_destino_pendente)
            logger.info("Mensagem de pendente enviada para grupos adicionais: %s.", grupo_destino_pendente)


def calcular_tempo_decorrido(hora_inicio):
    if not hora_inicio:
        return "Não registrado"

    try:
        inicio = datetime.strptime(hora_inicio, "%Y-%m-%d %H:%M:%S")
        agora = datetime.now()
        delta = agora - inicio
        horas, resto = divmod(delta.total_seconds(), 3600)
        minutos, segundos = divmod(resto, 60)
        return f"{int(horas)} horas, {int(minutos)} minutos e {int(segundos)} segundos"
    except Exception as error:
        logger.error("Erro ao calcular tempo decorrido: %s", error)
        return "Não registrado"


def monitorar_ocorrencias():
    logger.info("Carregando histórico de ocorrências...")

    historico = carregar_historico()
    if not historico:
        logger.info("Histórico vazio, criando histórico inicial...")
        historico = construir_historico_inicial()
        salvar_historico(historico)

    while True:
        try:
            ocorrencias = get_os_by_status_and_tipo([0, 1, 2, 3])
            houve_atualizacao = False

            for ocorrencia in ocorrencias:
                id_ocorrencia = str(ocorrencia["id_ocorrencia"])
                status_atual = ocorrencia["status_ocorrencia"]
                ultimo_status = historico.get(id_ocorrencia, {}).get("status")

                data_abertura = ocorrencia.get("data_cadastro", None)

                if not data_abertura:
                    logger.warning("⚠ O.S. %s não tem data de abertura válida. Ignorando.", id_ocorrencia)
                    continue

                try:
                    datetime.strptime(data_abertura, "%Y-%m-%d %H:%M:%S")
                except ValueError:
                    logger.warning("⚠ O.S. %s tem data de abertura inválida: %s. Ignorando.", id_ocorrencia, data_abertura)
                    continue

                if "latitude" not in historico.get(id_ocorrencia, {}):
                    historico.setdefault(id_ocorrencia, {}).update(
                        {
                            "latitude": ocorrencia.get("latitude"),
                            "longitude": ocorrencia.get("longitude"),
                        }
                    )
                    logger.debug(
                        "Atualizado histórico para ocorrência %s: Latitude %s, Longitude %s",
                        id_ocorrencia,
                        ocorrencia.get("latitude"),
                        ocorrencia.get("longitude"),
                    )

                if status_atual != ultimo_status:
                    if status_atual == 2:
                        logger.info(
                            "Registrando hora de execução para ocorrência %s: %s",
                            id_ocorrencia,
                            datetime.now(),
                        )
                        historico[id_ocorrencia]["hora_execucao"] = datetime.now().strftime(
                            "%Y-%m-%d %H:%M:%S"
                        )
                    elif ultimo_status == 2:
                        logger.info("Calculando tempo de execução para ocorrência %s", id_ocorrencia)
                        historico[id_ocorrencia]["tempo_execucao"] = calcular_tempo_decorrido(
                            historico[id_ocorrencia].get("hora_execucao")
                        )

                    historico[id_ocorrencia]["status"] = status_atual
                    houve_atualizacao = True
                    gerar_alerta(ocorrencia, status_atual, ultimo_status, historico)

            if houve_atualizacao:
                salvar_historico(historico)

        except Exception as error:
            logger.error("Erro no monitoramento de ocorrências: %s", error)

        logger.info("Monitoramento concluído. Aguardando 30 segundos.")
        time.sleep(30)


def gerar_relatorio_setor(setor, periodo):
    global os_alertadas

    lista_ocorrencias = coletar_os_por_setor(setor)

    if not lista_ocorrencias:
        logger.info("Nenhuma O.S. encontrada para o setor %s no período %s.", setor, periodo)
        return

    for ocorrencia in lista_ocorrencias:
        id_ocorrencia = ocorrencia["id_ocorrencia"]
        cliente_nome = ocorrencia.get("cliente_nome", "Nome não informado")
        endereco = ocorrencia.get("endereco", "Endereço não informado")
        bairro = ocorrencia.get("endereco_bairro", "Bairro não informado")
        conteudo = ocorrencia.get("conteudo", "Conteúdo não informado")
        link_os = (
            f"https://gofibra.sgp.net.br/admin/atendimento/ocorrencia/os/{id_ocorrencia}/print/"
        )

        mensagem = (
            f"*Relatório de O.S. - Período {periodo.upper()}*\n\n"
            f" *Cliente*: ```{cliente_nome}```\n"
            f" *Endereço*: ```{endereco}, Bairro: {bairro}```\n"
            "-----------------------------------\n\n"
            f" *Conteúdo*: ```{conteudo}```\n"
            "-----------------------------------\n\n"
            f" [*O.S. {id_ocorrencia}*]({link_os})\n\n"
            "✅ *Fim da O.S.*"
        )

        send_alert(mensagem, GRUPO_RELATORIO)
        logger.info("Mensagem enviada para O.S. %s no setor %s, período %s.", id_ocorrencia, setor, periodo)

        os_alertadas.add(id_ocorrencia)


HISTORICO_OS_NOVA_PATH = "/opt/monitor_os/historico_os_nova.json"
os_alertadas = set()


def carregar_historico_os_nova():
    try:
        if os.path.exists(HISTORICO_OS_NOVA_PATH):
            with open(HISTORICO_OS_NOVA_PATH, "r") as arquivo:
                dados = json.load(arquivo)
                logger.info("✅ Histórico carregado: %s", dados)
                return set(dados)
        logger.info("⚠ Nenhum histórico encontrado. Criando um novo histórico vazio.")
        return set()
    except Exception as error:
        logger.error("❌ Erro ao carregar histórico: %s", error)
        return set()


def salvar_historico_os_nova(dados):
    try:
        with open(HISTORICO_OS_NOVA_PATH, "w") as arquivo:
            json.dump(list(dados), arquivo, indent=4)
        logger.info("✅ Histórico atualizado salvo.")
    except Exception as error:
        logger.error("❌ Erro ao salvar histórico: %s", error)


os.makedirs(HISTORICO_DIR, exist_ok=True)
os_alertadas = carregar_historico_os_nova()


def enviar_alerta_os_nova(ocorrencia, setor=None):
    id_ocorrencia = ocorrencia["id_ocorrencia"]
    cliente_nome = ocorrencia.get("cliente_nome", "Nome não informado")
    endereco = ocorrencia.get("endereco", "Endereço não informado")
    bairro = ocorrencia.get("endereco_bairro", "Bairro não informado")
    conteudo = ocorrencia.get("conteudo", "Conteúdo não informado")
    setor = setor or ocorrencia.get("setor_id", "N/D")
    link_os = f"https://gofibra.sgp.net.br/admin/atendimento/ocorrencia/os/{id_ocorrencia}/print/"

    mensagem = (
        f"\U0001F4E2 *Nova O.S. aberta no Setor {setor}*\n\n"
        f" *Cliente*: ```{cliente_nome}```\n"
        f" *Endereço*: ```{endereco}, Bairro: {bairro}```\n"
        "-----------------------------------\n\n"
        f" *Conteúdo*: ```{conteudo}```\n"
        "-----------------------------------\n\n"
        f" [*O.S. {id_ocorrencia}*]({link_os})\n\n"
        "✅ *Fim da O.S.*"
    )

    send_alert(mensagem, GRUPO_RELATORIO)
    logger.info("Alerta enviado para nova O.S. %s no setor %s.", id_ocorrencia, setor)

    os_alertadas.add(id_ocorrencia)
    logger.info("O.S. %s adicionada ao conjunto de alertadas.", id_ocorrencia)

    salvar_historico_os_nova(os_alertadas)


os_alertadas = carregar_historico_os_nova()


def monitorar_os_novas(setores):
    global os_alertadas

    logger.info("✅ Iniciando monitoramento contínuo de novas O.S.")

    while True:
        try:
            hoje = datetime.today().strftime("%Y-%m-%d")
            ocorrencias = get_os_by_status_and_tipo([0])

            for ocorrencia in ocorrencias:
                id_ocorrencia = str(ocorrencia["id_ocorrencia"])
                tecnico_nome = ocorrencia.get("tecnico_nome", "NÃO INFORMADO")
                tecnico_ramal = ocorrencia.get("tecnico_ramal", None)

                logger.debug(
                    "O.S. %s: Técnico: %s, Ramal: %s", id_ocorrencia, tecnico_nome, tecnico_ramal
                )

                if id_ocorrencia in os_alertadas:
                    continue

                data_agendamento_str = ocorrencia.get("data_agendamento", None)
                if data_agendamento_str:
                    try:
                        data_agendamento = datetime.strptime(
                            data_agendamento_str, "%Y-%m-%d %H:%M:%S"
                        ).strftime("%Y-%m-%d")
                        if data_agendamento != hoje:
                            logger.info(
                                "⚠ O.S. %s ignorada (agendada para %s).", id_ocorrencia, data_agendamento
                            )
                            continue
                    except ValueError:
                        logger.warning(
                            "⚠ O.S. %s tem data inválida: %s. Ignorando.",
                            id_ocorrencia,
                            data_agendamento_str,
                        )
                        continue
                else:
                    logger.info("⚠ O.S. %s ignorada (sem data de agendamento).", id_ocorrencia)
                    continue

                if not tecnico_ramal or str(tecnico_ramal).strip() == "":
                    logger.warning(
                        "⚠ O.S. %s tem técnico '%s' mas SEM RAMAL VÁLIDO. Ignorando.",
                        id_ocorrencia,
                        tecnico_nome,
                    )
                    continue

                enviar_alerta_os_nova(ocorrencia, ocorrencia.get("setor_id"))

                os_alertadas.add(id_ocorrencia)
                salvar_historico_os_nova(os_alertadas)

                logger.info("✅ Alerta enviado para nova O.S. %s.", id_ocorrencia)

        except Exception as error:
            logger.error("❌ Erro no monitoramento de novas O.S.: %s", error)

        logger.info("🔄 Monitoramento de novas O.S. concluído. Aguardando 30 segundos.")
        time.sleep(30)


def get_technician_by_id(responsavel_id):
    connection = get_db_connection()
    if not connection:
        logger.error("Erro na conexão com o banco de dados")
        return []

    try:
        cursor = connection.cursor()
        query = """
            SELECT
                atendimento_os.id AS id_ocorrencia,
                atendimento_os.status AS status,
                TO_CHAR(atendimento_os.data_agendamento, 'DD-MM-YYYY HH24:MI:SS') AS data_agendamento,
                atendimento_os.conteudo AS conteudo,
                atendimento_os.tipoos AS tipoos,
                atendimento_os.prioridade AS prioridade,
                TO_CHAR(atendimento_os.data_cadastro, 'DD-MM-YYYY HH24:MI:SS') AS data_cadastro,
                TO_CHAR(atendimento_os.data_alteracao, 'DD-MM-YYYY HH24:MI:SS') AS data_alteracao,
                TO_CHAR(atendimento_os.data_finalizacao, 'DD-MM-YYYY HH24:MI:SS') AS data_finalizacao,
                atendimento_os.observacao AS observacao,
                atendimento_os.servicoprestado AS servicoprestado,
                admcore_pessoa.nome AS cliente_nome,
                admcore_endereco.logradouro AS endereco_logradouro,
                admcore_endereco.numero AS endereco_numero,
                admcore_endereco.bairro AS endereco_bairro,
                admcore_endereco.cidade AS endereco_cidade,
                admcore_endereco.uf AS endereco_uf,
                admcore_endereco.cep AS endereco_cep,
                auth_user.name AS tecnico_nome,
                auth_user.id AS responsavel_id,
                auth_user.ramal AS tecnico_ramal,
                atendimento_os.setor_id AS setor_id
            FROM
                atendimento_os
            LEFT JOIN atendimento_ocorrencia ON atendimento_os.ocorrencia_id = atendimento_ocorrencia.id
            LEFT JOIN admcore_clientecontrato ON atendimento_ocorrencia.clientecontrato_id = admcore_clientecontrato.id
            LEFT JOIN admcore_cliente ON admcore_clientecontrato.cliente_id = admcore_cliente.id
            LEFT JOIN admcore_pessoa ON admcore_cliente.pessoa_id = admcore_pessoa.id
            LEFT JOIN admcore_endereco ON admcore_cliente.endereco_id = admcore_endereco.id
            LEFT JOIN auth_user ON atendimento_ocorrencia.responsavel_id = auth_user.id
            WHERE
                auth_user.id = %s
            ORDER BY
                atendimento_os.data_cadastro ASC NULLS FIRST;
        """
        cursor.execute(query, (responsavel_id,))
        resultados = cursor.fetchall()

        lista_ocorrencias = [
            {
                "id_ocorrencia": row[0],
                "status": row[1],
                "data_agendamento": row[2],
                "conteudo": row[3],
                "tipoos": row[4],
                "prioridade": row[5],
                "data_cadastro": row[6],
                "data_alteracao": row[7],
                "data_finalizacao": row[8],
                "observacao": row[9],
                "servicoprestado": row[10],
                "cliente_nome": row[11] or "Nome não informado",
                "endereco": f"{row[12]}, {row[13]}" if row[12] and row[13] else "Endereço não informado",
                "endereco_bairro": row[14] or "Bairro não informado",
                "endereco_cidade": row[15] or "Cidade não informada",
                "responsavel_id": row[16],
                "tecnico_ramal": row[17] or "Ramal não informado",
                "setor_id": row[18],
            }
            for row in resultados
        ]
        return lista_ocorrencias

    except Exception as error:
        logger.error("Erro ao coletar O.S. por responsavel_id %s: %s", responsavel_id, error)
        return []
    finally:
        if connection:
            cursor.close()
            connection.close()


def responsavel_carregar_historico(arquivo):
    if os.path.exists(arquivo):
        with open(arquivo, "r") as f:
            return json.load(f)
    return {}


def responsavel_salvar_historico(arquivo, dados):
    with open(arquivo, "w") as f:
        json.dump(dados, f)


HISTORICO_DIR = "/opt/monitor_os/"
RESPONSAVEL_HISTORICO_TECNICOS = "/opt/monitor_os/historico_tecnicos.json"
RESPONSAVEL_HISTORICO_OS = "/opt/monitor_os/historico_os.json"


def carregar_historico_tecnicos():
    try:
        if os.path.exists(RESPONSAVEL_HISTORICO_TECNICOS):
            with open(RESPONSAVEL_HISTORICO_TECNICOS, "r") as arquivo:
                dados = json.load(arquivo)
                logger.info("Histórico de técnicos carregado: %s", dados)
                return dados
        logger.info("Arquivo de histórico de técnicos não encontrado, criando um novo histórico.")
        return {}
    except Exception as error:
        logger.error("Erro ao carregar histórico de técnicos: %s", error)
        return {}


def carregar_historico_os():
    try:
        if os.path.exists(RESPONSAVEL_HISTORICO_OS):
            with open(RESPONSAVEL_HISTORICO_OS, "r") as arquivo:
                dados = json.load(arquivo)
                logger.info("Histórico de O.S. carregado: %s", dados)
                return set(dados)
        logger.info("Arquivo de histórico de O.S. não encontrado, criando um novo histórico.")
        return set()
    except Exception as error:
        logger.error("Erro ao carregar histórico de O.S.: %s", error)
        return set()


def salvar_historico_tecnicos():
    try:
        with open(RESPONSAVEL_HISTORICO_TECNICOS, "w") as arquivo:
            json.dump(responsavel_historico_tecnicos, arquivo)
        logger.info("Histórico de técnicos salvo em %s.", RESPONSAVEL_HISTORICO_TECNICOS)
    except Exception as error:
        logger.error("Erro ao salvar histórico de técnicos: %s", error)


def salvar_historico_os():
    try:
        with open(RESPONSAVEL_HISTORICO_OS, "w") as arquivo:
            json.dump(list(responsavel_historico_os), arquivo)
        logger.info("Histórico de O.S. salvo em %s.", RESPONSAVEL_HISTORICO_OS)
    except Exception as error:
        logger.error("Erro ao salvar histórico de O.S.: %s", error)


os_monitoradas_anteriores = set()
alerta_sem_os_enviado = set()
responsavel_historico_tecnicos = carregar_historico_tecnicos()
responsavel_historico_os = carregar_historico_os()


def monitorar_responsavel_id():
    global os_monitoradas_anteriores, alerta_sem_os_enviado, responsavel_historico_tecnicos, responsavel_historico_os

    os.makedirs(HISTORICO_DIR, exist_ok=True)

    logger.info("Iniciando monitoramento de responsáveis por O.S. nos setores 1 e 2...")

    while True:
        try:
            hoje = datetime.today().strftime("%Y-%m-%d")
            os_setores = coletar_os_por_setor(1) + coletar_os_por_setor(2)
            os_atual = {os["id_ocorrencia"]: os for os in os_setores}
            logger.info("O.S. encontradas nos setores 1 e 2: %s", len(os_setores))

            tecnicos_atuais = {}
            tecnicos_encontrados = set()

            if os_atual != os_monitoradas_anteriores:
                alerta_sem_os_enviado = set()

                for ocorrencia in os_setores:
                    id_ocorrencia = ocorrencia["id_ocorrencia"]
                    status = ocorrencia.get("status")
                    tecnico_nome = ocorrencia.get("tecnico_nome", None)
                    tecnico_ramal = ocorrencia.get("tecnico_ramal", "TECNICO SEM NUMERO")
                    setor_id = ocorrencia.get("setor_id", None)
                    data_agendamento_str = ocorrencia.get("data_agendamento", None)

                    if status != 0:
                        continue

                    if tecnico_nome and tecnico_ramal != "TECNICO SEM NUMERO":
                        if not setor_id:
                            mensagem_setor = (
                                f"\U000026A0 *O.S. {id_ocorrencia} atribuída a {tecnico_nome} está SEM"
                                " setor definido!*\n"
                                f"Cliente: {ocorrencia.get('cliente_nome')}\n"
                                "Verifique no sistema e corrija o campo `setor_id`."
                            )
                            send_alert_gofibra(mensagem_setor, GRUPO_SUPERVISOR)

                        if data_agendamento_str:
                            try:
                                data_agendamento = datetime.strptime(
                                    data_agendamento_str, "%d-%m-%Y %H:%M:%S"
                                ).strftime("%Y-%m-%d")
                                if data_agendamento != hoje:
                                    mensagem_atendente = (
                                        "\U0001F6A8 *Alerta para Atendente:*\n"
                                        f"A O.S. {id_ocorrencia} foi atribuída ao técnico {tecnico_nome},"
                                        f" mas *não está agendada para hoje ({data_agendamento})*.\n"
                                        "Verifique o agendamento no SGP."
                                    )
                                    send_alert_gofibra(mensagem_atendente, GRUPO_SUPERVISOR)
                            except ValueError:
                                logger.warning(
                                    "🚫 O.S. %s com data de agendamento inválida: %s",
                                    id_ocorrencia,
                                    data_agendamento_str,
                                )
                        else:
                            mensagem_data = (
                                f"\U0001F6A8 *O.S. {id_ocorrencia} atribuída a {tecnico_nome} está"
                                " sem data de agendamento!*\n"
                                "Verifique o campo 'data_agendamento' no SGP."
                            )
                            send_alert_gofibra(mensagem_data, GRUPO_SUPERVISOR)

                        tecnicos_encontrados.add(tecnico_nome)

                        if tecnico_nome not in tecnicos_atuais:
                            tecnicos_atuais[tecnico_nome] = {"ramal": tecnico_ramal, "os_list": []}
                        tecnicos_atuais[tecnico_nome]["os_list"].append(id_ocorrencia)

                        if id_ocorrencia not in responsavel_historico_os:
                            mensagem = (
                                f"\U000026A0\uFE0F *Técnico {tecnico_nome}, você tem "
                                f"{len(tecnicos_atuais[tecnico_nome]['os_list'])} O.S. pendentes:*\n"
                                f"{', '.join(map(str, tecnicos_atuais[tecnico_nome]['os_list']))}\n"
                                "Por favor, verifique no aplicativo SGP."
                            )
                            send_alert_tec_gofibra(mensagem, tecnico_ramal)
                            logger.info(
                                "Alerta enviado para o técnico %s, ramal %s.", tecnico_nome, tecnico_ramal
                            )
                            responsavel_historico_os.add(id_ocorrencia)

                            mensagem_supervisor = (
                                f"\U0001F4E2 Alerta enviado para o técnico {tecnico_nome}.\n"
                                "\U000026A0\uFE0F Resumo das O.S. do técnico no APP:\n"
                                f"- Total de O.S.: {len(tecnicos_atuais[tecnico_nome]['os_list'])}\n"
                                f"- IDs: {', '.join(map(str, tecnicos_atuais[tecnico_nome]['os_list']))}\n"
                                f"- Ramal: {tecnico_ramal}."
                            )
                            send_alert(mensagem_supervisor, GRUPO_SUPERVISOR)

                for tecnico_nome, dados in responsavel_historico_tecnicos.items():
                    if tecnico_nome not in tecnicos_encontrados and dados["status"] == 2:
                        ramal_ausente = dados["ramal"]
                        mensagem_ausente = (
                            f"\U000026A0\uFE0F *Técnico {tecnico_nome}, você não tem mais O.S. "
                            "atribuída no momento.*\n"
                            "Por favor, aguarde novas atribuições."
                        )
                        send_alert_tec_gofibra(mensagem_ausente, ramal_ausente)
                        logger.info("Alerta de ausência de O.S. enviado para %s.", tecnico_nome)
                        responsavel_historico_tecnicos[tecnico_nome]["status"] = 1

                for tecnico_nome, dados in tecnicos_atuais.items():
                    if tecnico_nome in responsavel_historico_tecnicos:
                        os_anteriores = set(responsavel_historico_tecnicos[tecnico_nome].get("os_list", []))
                        os_novas = set(dados["os_list"])
                        if os_anteriores != os_novas:
                            added_os = os_novas - os_anteriores
                            removed_os = os_anteriores - os_novas
                            if added_os:
                                mensagem = (
                                    f"\U000026A0\uFE0F *Técnico {tecnico_nome}, novas O.S. "
                                    f"atribuídas:* \nAdicionadas: {', '.join(map(str, added_os))}\n"
                                    f"Total de O.S.: {len(dados['os_list'])}"
                                )
                                send_alert_tec_gofibra(mensagem, dados["ramal"])
                            if removed_os:
                                mensagem = (
                                    f"\U000026A0\uFE0F *Técnico {tecnico_nome}, Sempre atenção em suas"
                                    " O.S e Testes com Cliente e Baixas.* \n"
                                    "\U0001F4E2 *COMUNICAÇÃO É TUDO PESSOAL* \U0001F4E2\n"
                                    "\U0001F4E2 *OS REMOVIDA DA SUA CAIXA - ```VERIFICAR```* \U0001F4E2"
                                )
                                send_alert_tec_gofibra(mensagem, dados["ramal"])

                for tecnico_nome, dados in tecnicos_atuais.items():
                    responsavel_historico_tecnicos[tecnico_nome] = {
                        "status": 2,
                        "ramal": dados["ramal"],
                        "os_list": dados["os_list"],
                    }

                responsavel_salvar_historico(RESPONSAVEL_HISTORICO_TECNICOS, responsavel_historico_tecnicos)
                responsavel_salvar_historico(RESPONSAVEL_HISTORICO_OS, list(responsavel_historico_os))

            os_monitoradas_anteriores = os_atual
            time.sleep(15)

        except Exception as error:
            logger.error("Erro no monitoramento de responsáveis: %s", error)
            time.sleep(15)


def processar_djson(djson_str, linha_id, nome_cliente):
    try:
        if isinstance(djson_str, dict):
            djson_data = djson_str
        else:
            djson_data = json.loads(djson_str)

        if "ativacao" in djson_data:
            ativacao = djson_data["ativacao"]

            status_payment = ativacao.get("statusPayment", False)

            msisdn = ativacao.get("msisdn", "Não disponível")
            eSimQrCodeUrl = ativacao.get("eSimQrCodeUrl", None)
            pix_code = ativacao["pix"].get("code", "")
            qr_code_url = ativacao["pix"].get("qrCodeUrl", "")
            expires_at = ativacao["pix"].get("expiresAt", "")
            value = float(ativacao["pix"].get("value", 0)) / 100
            is_portability = ativacao.get("isPortability", False)
            iccid = ativacao.get("iccid", "Não disponível")

            mensagem = f"\U0001F4DE Olá {nome_cliente}, seus dados de ativação estão abaixo:\n"
            mensagem += f"\U0001F4F1 *Número Contratado*: {msisdn}\n"
            mensagem += f"\U0001F4B0 *Valor do Plano*: R${value:.2f}\n"
            if is_portability:
                mensagem += "\U0001F4E6 *Status*: Portabilidade\n"
            else:
                mensagem += "\U0001F4E6 *Status*: Não é portabilidade\n"
            mensagem += f"\U0001F4B7 *ICCID*: {iccid}\n"
            mensagem += f"\U000023F3 *Validade até*: {expires_at}\n"
            if status_payment:
                mensagem += "\U000027A1 *Ainda pode ser ativado. Realize o pagamento para ativação.*\n"
            else:
                mensagem += "\U0000274C *O tempo de pagamento expirou.*\n"

            send_alert_tec_gofibra(mensagem, GRUPO_SUPERVISOR)

            if pix_code and qr_code_url:
                mensagem_pix = (
                    "\U000026A0 *Atenção!*\n"
                    f"\U0001F4B8 *Código Pix*: `{pix_code}`\n\n"
                    "\U0001F4B0 *Por favor, efetue o pagamento para ativação.*\n"
                    f"\U0001F4C5 *Validade até:* {expires_at}\n\n"
                )
                send_alert_tec_gofibra(mensagem_pix, GRUPO_SUPERVISOR)

                mensagem_qr = (
                    f"\U0001F4F7 *QR Code para pagamento:* {qr_code_url}\n\n"
                    "\U0001F4F2 *Por favor, utilize o QR Code para efetuar o pagamento.*"
                )
                send_alert_tec_gofibra(mensagem_qr, GRUPO_SUPERVISOR)

            if eSimQrCodeUrl:
                mensagem_qr_esim = (
                    f"\U0001F4F1 *QR Code para ativação do eSIM*: {eSimQrCodeUrl}\n\n"
                    "\U0001F4F2 *Por favor, utilize o QR Code para ativar o eSIM.*"
                )
                send_alert_tec_gofibra(mensagem_qr_esim, GRUPO_SUPERVISOR)

            return True
        logger.warning("Linha %s não possui 'ativacao' no DJSON.", linha_id)
        return False

    except json.JSONDecodeError:
        logger.error("Erro ao decodificar o DJSON para a linha %s.", linha_id)
        return False


def obter_linhas_com_djson():
    try:
        query = """
        SELECT
            servicotelefonialinha.id AS "Linha ID",
            servicotelefonialinha.numero AS "Número",
            servicotelefonialinha.simcard AS "Simcard",
            servicotelefonialinha.observacao AS "Observação",
            servicotelefonialinha.data_cadastro AS "Data Cadastro",
            servicotelefonialinha.data_alteracao AS "Data Alteração",
            pessoa.nome AS "Nome Cliente",
            servicotelefonialinha.djson AS "DJSON"
        FROM
            admcore_servicotelefonialinha AS servicotelefonialinha
        JOIN
            admcore_servicotelefonia AS servicotelefonia
            ON servicotelefonialinha.servicotelefonia_id = servicotelefonia.id
        JOIN
            admcore_clientecontrato AS clientecontrato
            ON clientecontrato.id = servicotelefonia.clientecontrato_id
        JOIN
            admcore_cliente AS cliente
            ON cliente.id = clientecontrato.cliente_id
        JOIN
            admcore_pessoa AS pessoa
            ON pessoa.id = cliente.pessoa_id
        WHERE
            servicotelefonialinha.djson IS NOT NULL
        """

        connection = get_db_connection()
        cursor = connection.cursor()
        cursor.execute(query)
        linhas = cursor.fetchall()

        linhas_processadas = []
        for linha in linhas:
            linhas_processadas.append(
                {
                    "id": linha[0],
                    "numero": linha[1],
                    "simcard": linha[2],
                    "observacao": linha[3],
                    "data_cadastro": linha[4],
                    "data_alteracao": linha[5],
                    "nome_cliente": linha[6],
                    "djson": linha[7],
                }
            )

        cursor.close()
        connection.close()
        return linhas_processadas

    except Exception as error:
        logger.error("Erro ao coletar as linhas com DJSON: %s", error)
        return []


def monitorar_linhas():
    while True:
        try:
            linhas = obter_linhas_com_djson()
            for linha in linhas:
                linha_id = linha["id"]
                djson_str = linha["djson"]
                nome_cliente = linha["nome_cliente"]

                processar_djson(djson_str, linha_id, nome_cliente)

            time.sleep(30)

        except Exception as error:
            logger.error("Erro ao monitorar as linhas: %s", error)
            time.sleep(30)


def executar_agendamentos():
    logger.info("⏳ Agendamentos de relatórios iniciados.")
    while True:
        schedule.run_pending()
        time.sleep(15)


def iniciar_monitoramento():
    try:
        setores_para_monitorar = [1, 2, 3]

        os_novas_thread = threading.Thread(
            target=monitorar_os_novas, args=(setores_para_monitorar,), daemon=True
        )
        os_novas_thread.start()

        monitoramento_ocorrencias_thread = threading.Thread(
            target=monitorar_ocorrencias, daemon=True
        )
        monitoramento_ocorrencias_thread.start()

        monitoramento_responsavel_id_thread = threading.Thread(
            target=monitorar_responsavel_id, daemon=True
        )
        monitoramento_responsavel_id_thread.start()

        linhas_monitoramento_thread = threading.Thread(target=monitorar_linhas, daemon=True)
        linhas_monitoramento_thread.start()

        executar_agendamentos()

    except Exception as error:
        logger.error("Erro ao iniciar o monitoramento: %s", error)


if __name__ == "__main__":
    iniciar_monitoramento()
