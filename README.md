# Sistema de Gestão de Veiculos - Fundação 🚗

## 📌 Visão Geral
Sistema web desenvolvido para automatizar o controle de entrada e saída (check-in/check-out) dos veículos da frota. Substitui o controle de papel por um ambiente digital responsivo, com geração automática de relatórios em Excel e PDF, além de registro fotográfico de avarias.

## 🛠️ Tecnologias Utilizadas
* **Backend:** Python 3, Flask, SQLAlchemy.
* **Banco de Dados:** SQLite (`veiculos.db`).
* **Frontend:** HTML5, Bootstrap 5, CSS/JavaScript nativo.
* **Infraestrutura:** Hospedado em nuvem (PythonAnywhere), fuso horário configurado para UTC-3 (São Paulo).
* **Processamento:** Pandas e OpenPyXL (Relatórios), Pillow (Otimização de Imagens).

## 📂 Estrutura do Projeto
* `/app.py`: Arquivo principal com todas as rotas e regras de negócio.
* `/veiculos.db`: Banco de dados relacional.
* `/templates/`: Telas do sistema.
* `/static/uploads/`: Onde as fotos anexadas pelo motorista e fotos dos carros são salvas.

## ⚙️ Manutenção e Rotinas

1. **Renovação do Servidor (PythonAnywhere):**
   * O plano gratuito exige um clique mensal de renovação. Faça login no PythonAnywhere, vá ao Dashboard e clique no botão amarelo "Run until 1 month from today".
   
2. **Backup do Banco de Dados:**
   * Acesse a aba **Files** no PythonAnywhere, vá na raiz do projeto e faça o download do arquivo `veiculos.db` semanalmente ou mensalmente.

3. **Como zerar ou corrigir KM errado:**
   * Faça o download do arquivo `veiculos.db`.
   * Abra-o localmente usando o software gratuito **DB Browser for SQLite**.
   * Faça as edições necessárias na tabela `historico`, salve e faça o upload substituindo o arquivo antigo na nuvem.
   * Vá na aba **Web** e clique no botão verde **Reload** para aplicar.

4. **Gerenciamento de Espaço (Limite de 512MB):**
   * Como o sistema salva fotos de avarias, monitore o espaço em disco no Dashboard. O sistema já usa a biblioteca Pillow para compactar as imagens para o formato `.jpg` otimizado. Se o limite apertar, faça backup das fotos antigas da pasta `/static/uploads` e apague-as do servidor.