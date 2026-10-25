# Miners Kick e Twitch (simplificado)

Uma forma simples de acumular **pontos de canal** na Kick e na Twitch sem deixar o navegador aberto.
Uma janela com dois botões (**Iniciar** e **Parar**) controla os dois miners em segundo plano, e um
painel no navegador mostra os pontos da Kick, com o status real de cada conexão.

Este projeto **não criou os miners**. Ele junta e simplifica dois projetos de código aberto,
listados em [Créditos](#créditos). Todo o trabalho pesado é dos autores originais.

> [!WARNING]
> Automatizar a coleta de pontos provavelmente viola os termos de uso da Kick e da Twitch.
> Use por sua conta e risco: a conta pode perder os pontos do canal ou ser suspensa.
> Este projeto não tem relação com a Kick, a Twitch ou os autores dos miners originais.

## Créditos

| Projeto | Autor | Licença | Uso aqui |
|---|---|---|---|
| [Kick_Channel_Points_Miner](https://github.com/Baillora/Kick_Channel_Points_Miner) | [Baillora](https://github.com/Baillora) | MIT | Base deste repositório (fork, com o histórico original preservado) |
| [Twitch-Channel-Points-Miner-v2](https://github.com/rdavydov/Twitch-Channel-Points-Miner-v2) | [rdavydov](https://github.com/rdavydov), baseado no projeto de [Tkd-Alex](https://github.com/Tkd-Alex/Twitch-Channel-Points-Miner-v2) | GPL-3.0 | Baixado do repositório original pelo instalador. O código dele **não** está aqui. |

O README original do miner da Kick está em [README_ORIGINAL.md](README_ORIGINAL.md) (e em russo em [README_RU.md](README_RU.md)).

## O que este fork muda

Em relação ao miner da Kick original (commit `c5e5053`):

- **Painel novo** (`painel.html`, em `http://localhost:5000`): pontos totais e por canal, ganho na sessão, contagem regressiva até a próxima leitura e filtros. O painel antigo continua em `/antigo`.
- **Status confirmado:** um canal só aparece como "Assistindo" se a Kick respondeu na conexão nos últimos 90 segundos. Os outros estados são "Conectando", "Reconectando", "Sem resposta", "Ao vivo" e "Offline" (`_websockets/ws_connect.py`, `account_manager.py`).
- **Botões no painel:** "Verificar status" (pergunta agora para a Kick quem está ao vivo), "Reconectar falhas" (só os canais com problema, usando um token de conexão novo) e "Reconectar todos".
- **Pontos lidos a cada 10 minutos**, o intervalo em que a Kick credita pontos. O original lia a cada 2 a 3 minutos.
- **Painel acessível só neste PC** (`127.0.0.1`). O original abria a porta 5000 para toda a rede local, sem senha.
- **Janela de controle** (`controle/controle_miners.pyw`): inicia e para os dois miners sem abrir terminais e mostra se cada um está rodando.
- **Instalador** (`instalar.ps1`) e uma configuração da Twitch **sem apostas** (`twitch/run.example.py`). O exemplo original aposta seus pontos em predictions.

## Requisitos

- Windows 10 ou 11
- [Python](https://www.python.org/downloads/) **3.10 a 3.13**, com tkinter (já vem no instalador oficial). Versões mais novas podem não ter as bibliotecas prontas.
- [Git](https://git-scm.com/)

Para instalar os dois pelo terminal:

```powershell
winget install Python.Python.3.12
```
```powershell
winget install Git.Git
```

## Instalação

1. Baixe este repositório:
   ```powershell
   git clone https://github.com/SEU_USUARIO/miners-simplificados.git
   ```
2. Rode o instalador dentro da pasta:
   ```powershell
   cd miners-simplificados
   ```
   ```powershell
   powershell -ExecutionPolicy Bypass -File .\instalar.ps1
   ```
   O instalador:
   - cria o ambiente Python do miner da Kick e instala as dependências;
   - baixa o miner da Twitch do repositório original, na versão `8a35f87`, e instala as dependências;
   - cria o `config.json` e o `run.py` a partir dos exemplos;
   - cria o atalho **Miners Kick e Twitch** na Área de Trabalho.

   Pode rodar o instalador de novo sem problema: o que já existe é mantido.

## Configuração

### Kick: `config.json`

1. Pegue o seu token, seguindo o passo a passo em [README_ORIGINAL.md](README_ORIGINAL.md#-how-to-get-your-kick-token): F12 no kick.com, aba Network, cabeçalho `authorization`, texto depois de `Bearer `.
2. No `config.json`, preencha `token` e a lista `streamers`, com os nomes como aparecem em `kick.com/<nome>`.
3. Deixe `"WebDashboard": { "enabled": true }` para usar o painel.

Os outros campos estão explicados no [README original](README_ORIGINAL.md#%EF%B8%8F-configuration-configjson).

### Twitch: `twitch/Twitch-Channel-Points-Miner-v2/run.py`

1. Troque `SEU_USUARIO_DA_TWITCH` pelo seu usuário e `canal1`, `canal2` pelos canais, como aparecem em `twitch.tv/<nome>`.
2. **Só na primeira vez**, faça o login com o terminal visível:
   ```powershell
   cd twitch\Twitch-Channel-Points-Miner-v2
   ```
   ```powershell
   .\.venv\Scripts\python.exe run.py
   ```
   Aparece um código de 8 letras: digite em [twitch.tv/activate](https://www.twitch.tv/activate). Depois do login, feche com `Ctrl+C`. O miner **não pede sua senha**.

A Twitch conta pontos de no máximo 2 canais ao mesmo tempo, na ordem da lista.

## Uso

Abra o atalho **Miners Kick e Twitch**:

- **▶ Iniciar**: liga os miners em segundo plano e abre o painel da Kick no navegador.
- **■ Parar**: encerra os dois.
- **Abrir painel da Kick**: abre `http://localhost:5000`.

Fechar a janela **não** para os miners. Use o botão Parar.

Para colocar um ícone próprio na janela e no atalho, salve um `miners.ico` na pasta `controle` e rode o instalador de novo.

### Onde ver os logs

Cada miner grava o que mostraria no terminal em um arquivo, recriado a cada início:

- Kick: `miner-log.txt` na raiz do repositório
- Twitch: `twitch/Twitch-Channel-Points-Miner-v2/miner-log.txt`

Se o login da Twitch expirar, o novo código para o `twitch.tv/activate` aparece no log da Twitch.

## Segurança

- **O `config.json` tem o seu token da Kick**, e a pasta `twitch/.../cookies/` tem o seu login da Twitch. Quem tiver esses arquivos consegue agir na sua conta. Não compartilhe e não publique esses arquivos. O `.gitignore` já os exclui.
- Se achar que o token vazou, faça logout na Kick. Na Twitch, desconecte o app em Configurações > Conexões.
- O painel só abre no seu PC (`127.0.0.1`), e os botões só aceitam pedidos do próprio painel.
- O miner da Twitch fica preso na versão revisada (`8a35f87`). Atualizar com `git pull` traz código que não foi revisado.

## Limitações conhecidas

- Testado só no Windows 11, com Python 3.12.
- O Docker do projeto original não foi testado com estas mudanças. Com o painel em `127.0.0.1`, o mapeamento de porta do container não funciona.
- Reconectar um canal pode reiniciar o ciclo de 10 minutos daquele canal na Kick.
- O painel mostra o saldo como 0 quando a consulta de pontos da Kick falha.

## Licença

- O código do miner da Kick e as mudanças deste fork estão sob a licença **MIT**: veja [LICENSE](LICENSE), com o copyright original mantido.
- `controle/` e `instalar.ps1` também estão sob a licença MIT.
- `twitch/run.example.py` é derivado do projeto da Twitch e está sob a **GPL-3.0**: veja [twitch/LICENSE-GPL-3.0.md](twitch/LICENSE-GPL-3.0.md).
