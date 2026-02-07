import logging
import os
import subprocess

import psycopg2
import requests

from .config import (
    BOT_TOKEN,
    BOT_TOKEN_TECX,
    DB_HOST,
    DB_NAME,
    DB_PASSWORD,
    DB_PORT,
    DB_USER,
    LOG_FILE,
    MIN_OFFLINE_DURATION,
    TMP_DIR,
    TMP_HISTORY_DIR,
    TMP_INSTALL_DIR,
)


def setup_logger() -> logging.Logger:
    log_dir = os.path.dirname(LOG_FILE)
    os.makedirs(log_dir, exist_ok=True)

    logger = logging.getLogger("MonitorRotasLogger")
    logger.setLevel(logging.INFO)

    if logger.handlers:
        return logger

    file_handler = logging.FileHandler(LOG_FILE)
    file_handler.setLevel(logging.INFO)

    formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
    file_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    return logger


logger = setup_logger()


def ensure_dir(directory: str) -> None:
    os.makedirs(directory, exist_ok=True)


def ensure_tmp_dir() -> None:
    ensure_dir(TMP_DIR)


def ensure_history_dir() -> None:
    ensure_dir(TMP_HISTORY_DIR)


def ensure_install_dir() -> None:
    ensure_dir(TMP_INSTALL_DIR)


def send_alert(message: str, group_id: str) -> None:
    url = "https://rc7networks.webchat.net.br/api/message/add/5/"
    payload = {
        "token": BOT_TOKEN,
        "contact": group_id,
        "resolve_links": "1",
        "message": message,
    }
    try:
        response = requests.post(url, data=payload, verify=False, timeout=15)
        logging.info("Alerta enviado para %s: %s", group_id, response.text)
    except Exception as error:
        logging.error("Erro ao enviar alerta para %s: %s", group_id, error)


def get_db_connection():
    return psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
    )


def send_installation_alert(message: str, group_id: str) -> None:
    url = "https://tecxpro.webchat.net.br/api/message/add/1/"
    payload = {
        "token": BOT_TOKEN_TECX,
        "contact": group_id,
        "resolve_links": "1",
        "message": message,
    }
    try:
        response = requests.post(url, data=payload, verify=False, timeout=15)
        logging.info("Alerta enviado para %s: %s", group_id, response.text)
    except Exception as error:
        logging.error("Erro ao enviar alerta de instalação para %s: %s", group_id, error)


def consulta_onu_zabbix(pppoe: str) -> str:
    try:
        result = subprocess.run(
            ["python3", "/scripts/tudo-separado/consulta_onu_zabbix.py", pppoe],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError as error:
        logger.error("Erro ao chamar consulta_onu_zabbix.py: %s", error)
        return "Erro ao consultar Zabbix"


def get_cto_clients_and_signals():
    try:
        connection = psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD,
        )
        cursor = connection.cursor()
        cursor.execute(
            """
            SELECT
                admcore_servicointernet.id AS "ID",
                admcore_servicointernet.login AS "PPPoE",
                netcore_splitter.ident AS "Splitter ID",
                COALESCE(NULLIF(netcore_onu.info -> 'optical' ->> 'rx', '-'), '0.0')::float AS "Sinal ONU - TX",
                COALESCE(NULLIF(netcore_onu.info -> 'optical' ->> 'olt_rx', '-'), '0.0')::float AS "Sinal ONU - RX",
                COALESCE(netcore_onu.phy_addr, 'N/A') AS "Serial ONU"
            FROM
                netcore_onu
            INNER JOIN netcore_splitter ON netcore_splitter.id = netcore_onu.splitter_id
            LEFT JOIN admcore_servicointernet ON admcore_servicointernet.id = netcore_onu.service_id
            WHERE
                netcore_splitter.ident LIKE 'R%'
            ORDER BY
                "Splitter ID";
            """
        )
        resultados = cursor.fetchall()

        cto_clients = {}
        for row in resultados:
            splitter_id = row[2]
            if splitter_id not in cto_clients:
                cto_clients[splitter_id] = []

            cto_clients[splitter_id].append(
                {
                    "id": row[0],
                    "pppoe": row[1],
                    "splitter_id": splitter_id,
                    "sinal_tx": row[3],
                    "sinal_rx": row[4],
                    "serial_onu": row[5],
                }
            )

        return cto_clients
    except Exception as error:
        logger.error("Erro ao obter clientes das CTOs: %s", error)
        return {}
    finally:
        if connection:
            cursor.close()
            connection.close()


def parse_splitter(splitter_id: str) -> tuple[str, str]:
    try:
        if "-" in splitter_id:
            parts = splitter_id.split("-")
            rota = parts[0]
            caixa = "-".join(parts[1:])
            return rota, caixa
        raise ValueError(f"Formato inesperado para splitter_id: {splitter_id}")
    except Exception as error:
        logging.error("Erro ao analisar splitter_id '%s': %s", splitter_id, error)
        return "", ""


def get_clients_and_routes():
    try:
        connection = psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD,
        )
        cursor = connection.cursor()
        cursor.execute(
            """
            SELECT
                admcore_servicointernet.id AS id,
                admcore_servicointernet.login AS pppoe,
                netcore_splitter.ident AS splitter_id
            FROM netcore_onu
            INNER JOIN netcore_splitter ON netcore_splitter.id = netcore_onu.splitter_id
            LEFT JOIN admcore_servicointernet ON admcore_servicointernet.id = netcore_onu.service_id
            WHERE netcore_splitter.ident LIKE 'R%';
            """
        )
        results = cursor.fetchall()
        clients = {
            str(row[0]): {"pppoe": row[1], "splitter_id": row[2]} for row in results
        }
        return clients
    except Exception as error:
        logger.error("Erro ao buscar clientes e rotas: %s", error)
        return {}
    finally:
        if connection:
            cursor.close()
            connection.close()


def get_clients_and_data():
    try:
        connection = psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD,
        )
        cursor = connection.cursor()
        cursor.execute(
            """
            SELECT
                admcore_servicointernet.id AS id,
                admcore_servicointernet.login AS pppoe,
                netcore_splitter.ident AS splitter_id,
                COALESCE(netcore_onu.phy_addr, 'N/A') AS serial_onu
            FROM netcore_onu
            INNER JOIN netcore_splitter ON netcore_splitter.id = netcore_onu.splitter_id
            LEFT JOIN admcore_servicointernet ON admcore_servicointernet.id = netcore_onu.service_id
            WHERE netcore_splitter.ident LIKE 'R%';
            """
        )

        results = cursor.fetchall()

        clients = {}
        for row in results:
            client_id = str(row[0])
            pppoe = row[1] or client_id
            splitter_id = row[2]
            serial_onu = row[3]

            if not client_id or not splitter_id:
                logger.warning(
                    "Cliente com ID ou Splitter nulo: ID=%s, Splitter=%s. Ignorando.",
                    client_id,
                    splitter_id,
                )
                continue

            clients[client_id] = {
                "pppoe": pppoe,
                "splitter_id": splitter_id,
                "serial_onu": serial_onu,
            }

        logger.info("Clientes processados: %s", len(clients))
        return clients
    except Exception as error:
        logger.error("Erro ao buscar clientes e dados: %s", error)
        return {}
    finally:
        if "cursor" in locals():
            cursor.close()
        if "connection" in locals():
            connection.close()


def fetch_additional_client_data(serial_onu: str):
    try:
        connection = psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD,
        )
        cursor = connection.cursor()
        cursor.execute(
            """
            SELECT
                admcore_servicointernet.id AS id_cliente,
                admcore_servicointernet.clientecontrato_id AS contrato_id,
                admcore_servicointernet.login AS pppoe,
                COALESCE(netcore_splitter.ident, 'N/A') AS splitter
            FROM netcore_onu
            LEFT JOIN admcore_servicointernet ON admcore_servicointernet.id = netcore_onu.service_id
            LEFT JOIN netcore_splitter ON netcore_splitter.id = netcore_onu.splitter_id
            WHERE netcore_onu.phy_addr = %s
            LIMIT 1;
            """,
            (serial_onu,),
        )
        result = cursor.fetchone()
        if result:
            return {
                "id_cliente": result[0],
                "contrato_id": result[1],
                "pppoe": result[2],
                "splitter": result[3],
            }
        return None
    except Exception as error:
        logger.error("Erro ao buscar dados adicionais para Serial %s: %s", serial_onu, error)
        return None
    finally:
        if connection:
            cursor.close()
            connection.close()


def get_offline_clients():
    try:
        connection = psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD,
        )
        cursor = connection.cursor()
        cursor.execute(
            f"""
            WITH ultimo_registro AS (
                SELECT
                    radacct.username,
                    MAX(radacct.radacctid) AS radacctid
                FROM
                    radacct
                GROUP BY
                    radacct.username
            )
            SELECT
                netcore_splitter.ident AS "Splitter ID",
                COUNT(
                    CASE
                        WHEN radacct.acctstoptime IS NOT NULL
                         AND (EXTRACT(EPOCH FROM NOW()) - EXTRACT(EPOCH FROM radacct.acctstoptime))
                         > {MIN_OFFLINE_DURATION}
                        THEN 1
                    END
                ) AS "Offline Count",
                STRING_AGG(
                    CASE
                        WHEN radacct.acctstoptime IS NOT NULL
                         AND (EXTRACT(EPOCH FROM NOW()) - EXTRACT(EPOCH FROM radacct.acctstoptime))
                         > {MIN_OFFLINE_DURATION}
                        THEN radacct.username || ' (Desconectado em: ' ||
                             TO_CHAR(radacct.acctstoptime, 'DD-MM-YYYY HH24:MI:SS') || ')'
                        ELSE NULL
                    END,
                    E'\\n'
                ) AS "Clientes Offline"
            FROM
                radacct
            INNER JOIN ultimo_registro ON radacct.radacctid = ultimo_registro.radacctid
            INNER JOIN admcore_servicointernet ON radacct.username = admcore_servicointernet.login
            LEFT JOIN netcore_onu ON netcore_onu.service_id = admcore_servicointernet.id
            LEFT JOIN netcore_splitter ON netcore_splitter.id = netcore_onu.splitter_id
            WHERE
                netcore_splitter.ident LIKE 'R%'
            GROUP BY
                netcore_splitter.ident
            ORDER BY
                "Offline Count" DESC;
            """
        )
        resultados = cursor.fetchall()
        offline_clients = {}
        for row in resultados:
            splitter_id = row[0]
            offline_count = row[1]
            clientes_offline = row[2] if row[2] else "Nenhum cliente offline."
            offline_clients[splitter_id] = {
                "offline_count": offline_count,
                "clientes_offline": clientes_offline,
            }
        return offline_clients
    except Exception as error:
        logger.error("Erro ao obter clientes offline: %s", error)
        return {}
    finally:
        if connection:
            cursor.close()
            connection.close()


def get_onu_status(pppoe: str) -> str:
    try:
        result = subprocess.run(
            ["python3", "consulta_onu_zabbix.py", pppoe],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            logger.error("Erro ao executar consulta_onu_zabbix.py: %s", result.stderr)
            return f"Erro ao consultar status da ONU para {pppoe}."
        return result.stdout.strip()
    except Exception as error:
        logger.error("Erro ao chamar consulta_onu_zabbix.py: %s", error)
        return f"Erro inesperado ao consultar status da ONU para {pppoe}."


def get_os_details(tecnico: str):
    try:
        connection = psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD,
        )
        cursor = connection.cursor()
        query = """
            SELECT
                atendimento_os.id AS os_id,
                atendimento_os.tipoos AS tipo,
                atendimento_os.status AS status,
                atendimento_os.prioridade AS prioridade,
                TO_CHAR(atendimento_os.data_cadastro, 'DD-MM-YYYY HH24:MI:SS') AS data_cadastro,
                TO_CHAR(atendimento_os.data_alteracao, 'DD-MM-YYYY HH24:MI:SS') AS ultima_alteracao,
                TO_CHAR(atendimento_os.data_finalizacao, 'DD-MM-YYYY HH24:MI:SS') AS data_finalizacao,
                atendimento_os.conteudo AS conteudo,
                atendimento_os.servicoprestado AS servico_prestado,
                atendimento_os.cobranca_valor AS cobranca_valor,
                atendimento_os.cobranca_vencimento AS cobranca_vencimento,
                atendimento_os.data_previsao_finalizacao AS previsao_finalizacao,
                atendimento_os.anotacao_publica AS anotacao_publica,
                netcore_splitter.ident AS splitter_id,
                admcore_pessoa.nome AS cliente,
                auth_user.username AS tecnico,
                ROUND((EXTRACT(EPOCH FROM (NOW() - atendimento_os.data_alteracao)) / 3600), 2)
                  AS tempo_aberta_horas
            FROM atendimento_os
            INNER JOIN atendimento_ocorrencia ON atendimento_os.ocorrencia_id = atendimento_ocorrencia.id
            INNER JOIN admcore_clientecontrato ON atendimento_ocorrencia.clientecontrato_id = admcore_clientecontrato.id
            INNER JOIN admcore_cliente ON admcore_clientecontrato.cliente_id = admcore_cliente.id
            INNER JOIN admcore_pessoa ON admcore_cliente.pessoa_id = admcore_pessoa.id
            INNER JOIN auth_user ON atendimento_os.responsavel_id = auth_user.id
            LEFT JOIN admcore_servicointernet ON admcore_servicointernet.clientecontrato_id =
                admcore_clientecontrato.id
            LEFT JOIN netcore_onu ON netcore_onu.service_id = admcore_servicointernet.id
            LEFT JOIN netcore_splitter ON netcore_splitter.id = netcore_onu.splitter_id
            WHERE atendimento_os.status = 0
              AND auth_user.username = %s
            ORDER BY atendimento_os.data_alteracao ASC NULLS FIRST;
        """

        cursor.execute(query, (tecnico,))
        resultados = cursor.fetchall()

        os_details = []
        for row in resultados:
            os_details.append(
                {
                    "os_id": row[0],
                    "tipo": row[1],
                    "status": row[2],
                    "prioridade": row[3],
                    "data_cadastro": row[4],
                    "ultima_alteracao": row[5],
                    "data_finalizacao": row[6],
                    "conteudo": row[7],
                    "servico_prestado": row[8],
                    "cobranca_valor": row[9],
                    "cobranca_vencimento": row[10],
                    "previsao_finalizacao": row[11],
                    "anotacao_publica": row[12],
                    "splitter_id": row[13],
                    "cliente": row[14],
                    "tecnico": row[15],
                    "tempo_aberta_horas": row[16],
                }
            )

        return os_details
    except Exception as error:
        logger.error("Erro ao buscar detalhes das O.S.: %s", error)
        return []
    finally:
        if "cursor" in locals():
            cursor.close()
        if "connection" in locals():
            connection.close()
