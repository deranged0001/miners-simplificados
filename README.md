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
- **Instalador de dois cliques** (`instalar.bat`): instala o Python se faltar e baixa o miner da Twitch, sem precisar de Git.
- **Tela Configurar e botão Login da Twitch** na janela de controle: ninguém precisa editar arquivos.
- Configuração da Twitch **sem apostas** (`twitch/run.example.py`). O exemplo original aposta seus pontos em predictions.

## Instalação (para quem não é programador)

Precisa de Windows 10 ou 11. Não precisa instalar nada antes.

1. No topo desta página, clique no botão verde **Code** e depois em **Download ZIP**.
2. Extraia o ZIP para uma pasta fixa, por exemplo `Documentos\miners-simplificados`.
   Não rode de dentro do ZIP e não mova a pasta depois: o atalho aponta para ela.
3. Dê dois cliques em **`instalar.bat`**.
   - Se o Windows mostrar "O Windows protegeu o computador", clique em **Mais informações** e depois em **Executar assim mesmo**.
   - Se você não tiver o Python, o instalador baixa o Python 3.12 sozinho pelo `winget`.
   - Leva alguns minutos. No fim aparece **Pronto!**.
4. Abra o atalho **Miners Kick e Twitch** que apareceu na Área de Trabalho.
5. Clique em **⚙ Configurar** e preencha a Kick, a Twitch ou as duas (veja abaixo).
6. Se usar a Twitch, clique em **Login da Twitch** (só na primeira vez).
7. Clique em **▶ Iniciar**.

O que o instalador faz:
- cria o ambiente Python do miner da Kick e instala as dependências;
- baixa o miner da Twitch do repositório original, exatamente na versão `8a35f87`, e instala as dependências;
- cria o atalho na Área de Trabalho.

Pode rodar o `instalar.bat` de novo sem problema: o que já existe é mantido, inclusive a sua configuração.

## Configuração

Tudo é feito pelo botão **⚙ Configurar**. Ele grava os arquivos para você.

### Kick

O miner da Kick precisa do **token** da sua conta. É como uma senha temporária: **não mande para ninguém**.

Como pegar o token (no computador, pelo Chrome, Edge ou Firefox):

1. Entre em [kick.com](https://kick.com) e faça login normalmente.
2. Aperte **F12**. Abre um painel de desenvolvedor do lado ou embaixo da página.
3. No topo desse painel, clique na aba **Network** (em português: **Rede**). Se não aparecer, clique em `>>` para ver mais abas.
4. Aperte **F5** para recarregar a página. A lista do painel enche de linhas.
5. Na caixa de filtro do painel (escrito **Filter** ou **Filtrar**), digite `api`.
6. Clique em uma das linhas da lista. Do lado, abre um quadro com detalhes.
7. Nesse quadro, fique na aba **Headers** (**Cabeçalhos**) e desça até **Request Headers** (**Cabeçalhos de solicitação**).
8. Procure a linha **authorization**. Ela começa com `Bearer` seguido de um texto parecido com `123456789|AbCdEf...`.
   Se essa linha não aparecer, clique em outra linha da lista e repita.
9. Copie esse valor. Pode copiar com ou sem a palavra `Bearer`: o app tira sozinho.
10. Cole no campo **Token** da tela Configurar.

Outra forma: no mesmo painel F12, aba **Application** (**Aplicativo**) no Chrome/Edge ou **Storage** (**Armazenamento**) no Firefox, abra **Cookies** > `https://kick.com` e copie o valor de `session_token`. Ele costuma ter o mesmo token, com `%7C` no lugar do `|`. O app converte. Se o miner não conectar com esse valor, use o passo a passo acima.

Depois, em **Canais da Kick**, coloque um canal por linha, com o nome que aparece em `kick.com/<nome>`. Pode colar o link inteiro do canal.

O token vale enquanto você não sair (logout) da Kick naquele navegador. Se o miner parar de funcionar depois de um logout, pegue um token novo e salve de novo.

### Twitch

1. Em **Configurar**, coloque o seu **usuário da Twitch** e os canais, um por linha, com o nome que aparece em `twitch.tv/<nome>`. A ordem é a prioridade: a Twitch conta pontos de no máximo 2 canais ao mesmo tempo.
2. Clique em **Login da Twitch**. Abre uma janela preta e o site [twitch.tv/activate](https://www.twitch.tv/activate) no navegador.
3. Na janela preta aparece um código de 8 letras. Digite esse código no site e autorize.
4. A janela preta diz **Login feito!**. Pode fechá-la.

O miner **não pede a sua senha**: o login é o mesmo usado por apps de TV. Ele fica salvo na pasta `twitch/Twitch-Channel-Points-Miner-v2/cookies/`.

Se você mudar só os canais, não precisa fazer o login de novo. Se trocar o usuário, faça.

### Configuração avançada

A tela Configurar cuida do básico. Para o resto (Telegram, Discord, proxy), edite o `config.json` à mão, com o miner parado.
Os campos estão explicados no [README original](README_ORIGINAL.md#%EF%B8%8F-configuration-configjson). A tela Configurar mantém esses campos quando salva.

## Uso

Abra o atalho **Miners Kick e Twitch**:

- **▶ Iniciar**: liga em segundo plano os miners que estão configurados e abre o painel da Kick no navegador.
- **■ Parar**: encerra os dois.
- **Abrir painel da Kick**: abre `http://localhost:5000`.
- **⚙ Configurar** e **Login da Twitch**: veja [Configuração](#configuração).

O status de cada miner aparece na janela: **rodando**, **parado**, **falta configurar**, **falta o login** ou **não instalado**.

Fechar a janela **não** para os miners. Use o botão Parar. Mudou a configuração com os miners rodando? Clique em Parar e depois em Iniciar.

Para colocar um ícone próprio na janela e no atalho, salve um `miners.ico` na pasta `controle` e rode o `instalar.bat` de novo.

### Instalação pelo terminal (opcional)

Quem já usa Git pode clonar em vez de baixar o ZIP:

```powershell
git clone https://github.com/deranged0001/miners-simplificados.git
```
```powershell
powershell -ExecutionPolicy Bypass -File .\miners-simplificados\instalar.ps1
```

### Onde ver os logs

Cada miner grava o que mostraria no terminal em um arquivo, recriado a cada início:

- Kick: `miner-log.txt` na raiz do repositório
- Twitch: `twitch/Twitch-Channel-Points-Miner-v2/miner-log.txt`

Se o login da Twitch expirar, o status mostra **falta o login**: clique em **Login da Twitch** de novo.

## Segurança

- **O `config.json` tem o seu token da Kick**, o `config_twitch.json` tem o seu usuário da Twitch, e a pasta `twitch/.../cookies/` tem o seu login da Twitch. Quem tiver esses arquivos consegue agir na sua conta. Não compartilhe e não publique esses arquivos. O `.gitignore` já os exclui.
- Se achar que o token vazou, faça logout na Kick. Na Twitch, desconecte o app em Configurações > Conexões.
- O painel só abre no seu PC (`127.0.0.1`), e os botões só aceitam pedidos do próprio painel.
- O miner da Twitch fica preso na versão revisada (`8a35f87`); o instalador confere a versão toda vez. Trocar a pasta por outra versão traz código que não foi revisado.

## Limitações conhecidas

- Testado só no Windows 11, com Python 3.12.
- O Docker do projeto original não foi testado com estas mudanças. Com o painel em `127.0.0.1`, o mapeamento de porta do container não funciona.
- Reconectar um canal pode reiniciar o ciclo de 10 minutos daquele canal na Kick.
- O painel mostra o saldo como 0 quando a consulta de pontos da Kick falha.

## Licença

- O código do miner da Kick e as mudanças deste fork estão sob a licença **MIT**: veja [LICENSE](LICENSE), com o copyright original mantido.
- `controle/`, `instalar.bat` e `instalar.ps1` também estão sob a licença MIT.
- `twitch/run.example.py` e `twitch/login_twitch.py` usam o projeto da Twitch e estão sob a **GPL-3.0**: veja [twitch/LICENSE-GPL-3.0.md](twitch/LICENSE-GPL-3.0.md).
