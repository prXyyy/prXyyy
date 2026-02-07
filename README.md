# Monitor de O.S. em Docker

Este projeto roda o seu `os_monitor.py` dentro de um container e expõe uma página web simples para acompanhar os logs em tempo real.

## Como funciona

- O serviço inicia o monitoramento (threads de O.S., responsáveis e linhas) ao subir o container.
- Os logs ficam em `/opt/monitor_os/logs/monitor_os.log` e são exibidos na UI.
- A página web permite iniciar o monitor se ele estiver parado.

## Estrutura do projeto

```
app/
  main.py              # Flask + inicialização do monitor
  monitor/
    os_monitor.py      # Seu script principal
    utils.py           # Acesso a DB e helpers
    config.py          # Configuração via variáveis de ambiente
  templates/           # UI
  static/              # CSS
logs/                  # Persistência de logs
historico/             # Persistência de históricos JSON
```

## Pré-requisitos

- Docker
- Docker Compose

## Tutorial completo (Debian 12 do zero)

### 1) Atualize o sistema

```bash
sudo apt update && sudo apt upgrade -y
```

### 2) Instale Docker e Docker Compose

```bash
sudo apt install -y ca-certificates curl gnupg lsb-release
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/debian/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
  https://download.docker.com/linux/debian $(lsb_release -cs) stable" \
  | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
```

Opcional (rodar Docker sem sudo):

```bash
sudo usermod -aG docker $USER
newgrp docker
```

### 3) Clone o projeto

```bash
git clone <URL_DO_SEU_REPOSITORIO>
cd <NOME_DO_REPOSITORIO>
```

### 4) Configure o ambiente

Crie o arquivo `.env` a partir do exemplo:

```bash
cp .env.example .env
```

Edite o `.env` e preencha as credenciais do banco e tokens.

### 5) Suba o container

```bash
docker compose up --build -d
```

A aplicação estará disponível em: `http://localhost:5000`.

### 6) Ver logs

```bash
docker compose logs -f
```

## Subir o ambiente (resumo rápido)

```bash
docker compose up --build
```

A aplicação estará disponível em: `http://localhost:5000`.

## Configurações

As credenciais do banco e tokens foram movidos para variáveis de ambiente (veja `.env.example`):

- `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`
- `BOT_TOKEN`, `BOT_TOKEN_TECX`, `BOT_TOKEN_GOFIBRA`
- `GRUPO_1`, `GRUPO_2`, `GRUPO_3`, `GRUPO_ALERTAS`
- `MONITOR_BASE_DIR` (padrão: `/opt/monitor_os`)

Os logs persistem em `./logs` e o histórico em `./historico`.

## Próximos passos sugeridos

### Ideias de evolução

- Tela de status com indicadores (O.S. abertas, em execução, pendentes).
- Filtros por setor, técnico ou data.
- Exportação de relatórios para CSV/Excel.
- Autenticação na UI.
- Alertas por e-mail/Telegram além do WhatsApp.
- Health-checks específicos para o banco de dados.

### Ajustes recomendados

- Ajustar os grupos/ramais e regras de alerta conforme sua operação.
- Ajustar os caminhos de histórico para backups externos.
- Separar módulos em pacotes menores conforme necessidade.
