import os
from flask import Flask, render_template, request, redirect, url_for, session, flash, send_file
from flask_sqlalchemy import SQLAlchemy
import pandas as pd
import io
from datetime import datetime, timezone, timedelta
from werkzeug.utils import secure_filename

# --- CONFIGURAÇÃO DO FUSO HORÁRIO DO BRASIL (UTC-3) ---
fuso_brasil = timezone(timedelta(hours=-3))

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///veiculos.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.secret_key = 'chave_secreta_fundacao_123'

# --- CREDENCIAIS DO GESTOR (ADMIN) ---
ADMIN_PASS = 'fundacao123'

# Configuração para upload de Fotos (Tanto do Checklist quanto dos Carros)
UPLOAD_FOLDER = os.path.join('static', 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

db = SQLAlchemy(app)

# --- MODELOS DE DADOS ---

class Usuario(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    login = db.Column(db.String(50), unique=True, nullable=False)
    setor = db.Column(db.String(50), nullable=False)
    senha = db.Column(db.String(50), nullable=False)
    cnh_validade = db.Column(db.String(15), nullable=True) # NOVO CAMPO: Validade CNH

class Veiculo(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    modelo = db.Column(db.String(50), nullable=False)
    placa = db.Column(db.String(10), nullable=False, unique=True)
    foto = db.Column(db.String(500), nullable=True) # NOVA COLUNA: Foto do Veículo
    status = db.Column(db.String(20), default='Disponível')
    usuario_atual = db.Column(db.String(50), nullable=True)
    setor_atual = db.Column(db.String(50), nullable=True)
    km_atual = db.Column(db.Integer, default=0)
    nivel_combustivel = db.Column(db.String(20), default='Cheio')
    ativo = db.Column(db.Boolean, default=True)

class Historico(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    veiculo_id = db.Column(db.Integer, db.ForeignKey('veiculo.id'), nullable=False)
    usuario = db.Column(db.String(50), nullable=False)

    # AJUSTADO: Agora salva a saída cravada no horário de Brasília
    data_saida = db.Column(db.DateTime, default=lambda: datetime.now(fuso_brasil))
    km_saida = db.Column(db.Integer, nullable=False)
    obs_saida = db.Column(db.Text, nullable=True)
    fotos_saida = db.Column(db.String(500), nullable=True)

    data_entrada = db.Column(db.DateTime, nullable=True)
    km_entrada = db.Column(db.Integer, nullable=True)
    obs_entrada = db.Column(db.Text, nullable=True)
    fotos_entrada = db.Column(db.String(500), nullable=True)

    itinerario = db.Column(db.Text, nullable=True)

    veiculo = db.relationship('Veiculo', backref=db.backref('historicos', lazy=True))

# --- LISTA MESTRA DE CHECKLIST ---
LISTA_CHECKLIST = [
    'CRLV', 'CNH', 'Óleo de Motor', 'Óleo do Freio', 'Água do Radiador',
    'Faróis', 'Lanternas Dianteiras', 'Setas', 'Pára-brisa', 'Vidros Laterais',
    'Vidro Traseiro (Vigia)', 'Retrovisores Externos', 'Lanternas Traseiras', 'Luzes de Ré',
    'Placas de Licença', 'Limpeza Externa', 'Limpeza Interna', 'Bancos',
    'Cinto de Segurança', 'Espelho Retrovisor Interno', 'Freio de Pé',
    'Freio de Mão', 'Vidros Elétricos', 'Pneus Calibrados', 'Estepe',
    'Chave de Roda', 'Macaco', 'Triângulo de Segurança'
]

@app.route('/cadastro', methods=['GET', 'POST'])
def cadastro():
    if request.method == 'POST':
        nome = request.form.get('nome')
        login = request.form.get('login')
        setor = request.form.get('setor')
        senha = request.form.get('senha')
        cnh_validade = request.form.get('cnh_validade')

        # 1ª TRAVA: Verifica se o NOME já existe (ignorando maiúsculas/minúsculas)
        if Usuario.query.filter(Usuario.nome.ilike(nome)).first():
            flash('Você já possui um cadastro! Fale com o gestor para alterar ou excluir sua conta.', 'warning')

        # 2ª TRAVA: Verifica se o LOGIN já existe
        elif Usuario.query.filter_by(login=login).first():
            flash(f'Erro: O login "{login}" já está em uso. Tente outro.', 'danger')

        # Se passar pelas duas travas, cria o cadastro
        else:
            novo_usuario = Usuario(nome=nome, login=login, setor=setor, senha=senha, cnh_validade=cnh_validade)
            db.session.add(novo_usuario)
            db.session.commit()
            flash('Cadastro realizado com sucesso! Faça login para continuar.', 'success')
            return redirect(url_for('login'))

    return render_template('cadastro.html')

# --- ROTAS DE AUTENTICAÇÃO ---

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        login_digitado = request.form.get('login')
        senha_digitada = request.form.get('senha')
        user = Usuario.query.filter_by(login=login_digitado, senha=senha_digitada).first()

        if user:
            session['usuario_id'] = user.id
            session['usuario_nome'] = user.nome
            session['usuario_setor'] = user.setor
            return redirect(url_for('motorista'))
        else:
            flash('Login ou senha incorretos!', 'danger')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('motorista'))

@app.route('/login_admin', methods=['GET', 'POST'])
def login_admin():
    if request.method == 'POST':
        senha_digitada = request.form.get('senha')

        # Agora o sistema verifica APENAS a senha
        if senha_digitada == ADMIN_PASS:
            session['admin_logado'] = True
            return redirect(url_for('gestor'))
        else:
            flash('Senha do gestor incorreta!', 'danger')

    return render_template('login_admin.html')

@app.route('/logout_admin')
def logout_admin():
    session.pop('admin_logado', None)
    return redirect(url_for('login_admin'))

# --- ROTAS PRINCIPAIS (ADMIN) ---

@app.route('/', methods=['GET', 'POST'])
def gestor():
    # TRAVA DE SEGURANÇA
    if not session.get('admin_logado'):
        return redirect(url_for('login_admin'))

    if request.method == 'POST':
        if 'acao_veiculo' in request.form:
            modelo = request.form.get('modelo')
            placa = request.form.get('placa')

            # --- PROCESSAMENTO DA FOTO DO CARRO ---
            foto_file = request.files.get('foto')
            nome_foto = None
            if foto_file and foto_file.filename:
                filename = secure_filename(foto_file.filename)
                unique_name = f"carro_{datetime.now().strftime('%Y%m%d%H%M%S')}_{filename}"
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], unique_name)
                foto_file.save(filepath)
                nome_foto = unique_name
            # ----------------------------------------

            veiculo_existente = Veiculo.query.filter_by(placa=placa).first()
            if veiculo_existente:
                if veiculo_existente.ativo:
                    flash(f'Erro: O veículo com placa {placa} já está no sistema!', 'danger')
                else:
                    veiculo_existente.ativo = True
                    veiculo_existente.modelo = modelo
                    if nome_foto:
                        veiculo_existente.foto = nome_foto # Atualiza foto se enviar nova
                    db.session.commit()
                    flash(f'O veículo {placa} que estava excluído foi reativado com sucesso!', 'success')
            else:
                novo_veiculo = Veiculo(modelo=modelo, placa=placa, foto=nome_foto)
                db.session.add(novo_veiculo)
                db.session.commit()
                flash('Veículo cadastrado com sucesso!', 'success')

        elif 'acao_usuario' in request.form:
            nome = request.form.get('nome')
            login = request.form.get('login')
            setor = request.form.get('setor')
            senha = request.form.get('senha')
            cnh_validade = request.form.get('cnh_validade') # CAPTURA CNH

            usuario_existente = Usuario.query.filter_by(login=login).first()
            if usuario_existente:
                flash(f'Erro: O login "{login}" já está em uso!', 'danger')
            else:
                # ADICIONA NO BANCO COM A CNH
                novo_usuario = Usuario(nome=nome, login=login, setor=setor, senha=senha, cnh_validade=cnh_validade)
                db.session.add(novo_usuario)
                db.session.commit()
                flash('Usuário cadastrado com sucesso!', 'success')
        return redirect(url_for('gestor'))

    veiculos = Veiculo.query.filter_by(ativo=True).all()
    usuarios = Usuario.query.all()

    # --- NOVO: LÓGICA DE VALIDADE DA CNH PARA O ADMIN ---
    hoje = datetime.now().date()
    cnh_status = {}
    for u in usuarios:
        if u.cnh_validade:
            try:
                data_cnh = datetime.strptime(u.cnh_validade, '%Y-%m-%d').date()
                dias = (data_cnh - hoje).days
                if dias < 0:
                    cnh_status[u.nome] = {'classe': 'bg-dark text-white', 'texto': 'CNH Vencida'} # Atualizado
                elif dias <= 30:
                    cnh_status[u.nome] = {'classe': 'bg-warning text-dark', 'texto': f'CNH Vence em {dias}d'} # Atualizado
                else:
                    cnh_status[u.nome] = {'classe': 'bg-success text-white border border-light', 'texto': 'CNH OK'} # Atualizado
            except:
                cnh_status[u.nome] = {'classe': 'bg-secondary text-white', 'texto': 'Inválida'}
        else:
            cnh_status[u.nome] = {'classe': 'bg-secondary text-white', 'texto': 'Sem CNH'}

    return render_template('admin.html', veiculos=veiculos, usuarios=usuarios, cnh_status=cnh_status)

@app.route('/usuarios')
def painel_usuarios():
    # TRAVA DE SEGURANÇA
    if not session.get('admin_logado'):
        return redirect(url_for('login_admin'))

    usuarios = Usuario.query.all()
    todos_registros = Historico.query.all()
    viagens_por_motorista = {}
    for reg in todos_registros:
        if reg.usuario:
            viagens_por_motorista[reg.usuario] = viagens_por_motorista.get(reg.usuario, 0) + 1
    motorista_destaque = "Nenhum"
    ranking_motoristas = []
    if viagens_por_motorista:
        motorista_destaque = max(viagens_por_motorista, key=viagens_por_motorista.get)
        ranking_motoristas = sorted(viagens_por_motorista.items(), key=lambda item: item[1], reverse=True)
    return render_template('usuarios.html', usuarios=usuarios, motorista_destaque=motorista_destaque, ranking=ranking_motoristas)

@app.route('/historico')
def painel_historico():
    # TRAVA DE SEGURANÇA
    if not session.get('admin_logado'):
        return redirect(url_for('login_admin'))

    page = request.args.get('page', 1, type=int)
    historico = Historico.query.order_by(Historico.id.desc()).paginate(page=page, per_page=20, error_out=False)

    # Busca todos os registros de histórico que já foram finalizados (possuem km_entrada)
    todos_registros = Historico.query.filter(Historico.km_entrada != None).all()

    km_por_carro = {}
    for reg in todos_registros:
        if reg.veiculo and reg.km_saida is not None and reg.km_entrada is not None:
            # Garante que não calcule KM negativo se alguém digitar errado
            km_rodado_na_viagem = reg.km_entrada - reg.km_saida
            if km_rodado_na_viagem > 0:
                nome_carro = f"{reg.veiculo.modelo} ({reg.veiculo.placa})"
                # Soma acumulativa: Pega o valor atual (ou 0 se não existir) e soma com a nova viagem
                km_por_carro[nome_carro] = km_por_carro.get(nome_carro, 0) + km_rodado_na_viagem

    # Ordena do maior pro menor
    ranking_carros = sorted(km_por_carro.items(), key=lambda item: item[1], reverse=True)
    return render_template('historico.html', historico=historico, ranking_carros=ranking_carros)

# --- ROTAS DO MOTORISTA ---

@app.route('/veiculos') # <-- MUDE APENAS AQUI! (De /motorista para /veiculos)
def motorista():
    # NOVA TRAVA: Verifica se o cookie do navegador pertence a um usuário que ainda existe no Banco
    if 'usuario_id' in session:
        usuario_valido = Usuario.query.get(session['usuario_id'])
        if not usuario_valido:
            session.clear() # Destrói a sessão fantasma se o usuário foi apagado do .db

    veiculos = Veiculo.query.filter_by(ativo=True).all()

    # --- NOVO: LÓGICA DE VALIDADE DA CNH PARA O INDEX ---
    usuarios = Usuario.query.all()
    hoje = datetime.now().date()
    cnh_status = {}
    for u in usuarios:
        if u.cnh_validade:
            try:
                data_cnh = datetime.strptime(u.cnh_validade, '%Y-%m-%d').date()
                dias = (data_cnh - hoje).days
                if dias < 0:
                    cnh_status[u.nome] = {'classe': 'bg-dark text-white', 'texto': 'CNH Vencida'}
                elif dias <= 30:
                    cnh_status[u.nome] = {'classe': 'bg-warning text-dark', 'texto': f'CNH Vence em {dias}d'}
                else:
                    cnh_status[u.nome] = {'classe': 'bg-success text-white border border-light', 'texto': 'CNH OK'}
            except:
                cnh_status[u.nome] = {'classe': 'bg-secondary text-white', 'texto': 'Inválida'}
        else:
            cnh_status[u.nome] = {'classe': 'bg-secondary text-white', 'texto': 'Sem CNH'}

    return render_template('index.html', veiculos=veiculos, session=session, cnh_status=cnh_status)

def processar_fotos(lista_arquivos):
    nomes_salvos = []
    for foto in lista_arquivos:
        if foto and foto.filename:
            filename = secure_filename(foto.filename)
            unique_name = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{filename}"
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], unique_name)
            foto.save(filepath)
            nomes_salvos.append(unique_name)
    return ",".join(nomes_salvos) if nomes_salvos else None

@app.route('/checkout/<int:id_veiculo>', methods=['GET', 'POST'])
def checkout(id_veiculo):
    if 'usuario_id' not in session:
        flash('Você precisa fazer login para pegar um veículo.', 'warning')
        return redirect(url_for('login'))

    # NOVA TRAVA DE SEGURANÇA NO CHECK-OUT
    usuario_valido = Usuario.query.get(session['usuario_id'])
    if not usuario_valido:
        session.clear()
        flash('Sessão expirada ou usuário inválido. Faça login novamente.', 'danger')
        return redirect(url_for('login'))

    veiculo = Veiculo.query.get_or_404(id_veiculo)

    if request.method == 'POST':
        usuario = session['usuario_nome']
        km_saida = int(request.form.get('quilometragem'))

        combustivel_val = request.form.get('combustivel')
        niveis = {"1": "Reserva", "2": "2", "3": "3", "4": "4", "5": "5", "6": "Meio", "7": "7", "8": "8", "9": "9", "10": "10", "11": "11", "12": "Cheio"}
        comb_texto = niveis.get(combustivel_val, "N/A")

        itens_marcados = request.form.getlist('checklist')
        resultado_chk = []
        for item in LISTA_CHECKLIST:
            status = "✅ OK" if item in itens_marcados else "❌ Ausente/Avariado"
            resultado_chk.append(f"{item}: {status}")

        avarias = request.form.get('avarias')
        obs_formatada = f"⛽ {comb_texto}\n📝 Observações: {avarias if avarias else 'Nenhuma'}\n\n📋 CHECKLIST:\n" + "\n".join(resultado_chk)

        fotos_str = processar_fotos(request.files.getlist('fotos'))

        novo_historico = Historico(veiculo_id=veiculo.id, usuario=usuario, km_saida=km_saida, obs_saida=obs_formatada, fotos_saida=fotos_str)
        db.session.add(novo_historico)

        veiculo.status = 'Em Uso'
        veiculo.usuario_atual = usuario
        veiculo.setor_atual = session.get('usuario_setor')
        veiculo.km_atual = km_saida
        veiculo.nivel_combustivel = comb_texto

        db.session.commit()
        return redirect(url_for('motorista'))

    return render_template('checkout.html', veiculo=veiculo)

@app.route('/checkin/<int:id_veiculo>', methods=['GET', 'POST'])
def checkin(id_veiculo):
    if 'usuario_id' not in session:
        flash('Você precisa fazer login para devolver um veículo.', 'warning')
        return redirect(url_for('login'))

    # NOVA TRAVA DE SEGURANÇA NO CHECK-IN
    usuario_valido = Usuario.query.get(session['usuario_id'])
    if not usuario_valido:
        session.clear()
        flash('Sessão expirada ou usuário inválido. Faça login novamente.', 'danger')
        return redirect(url_for('login'))

    veiculo = Veiculo.query.get_or_404(id_veiculo)

    if session['usuario_nome'] != veiculo.usuario_atual:
        flash(f'Erro: Apenas {veiculo.usuario_atual} pode fazer o check-in deste veículo.', 'danger')
        return redirect(url_for('motorista'))

    if request.method == 'POST':
        km_entrada = int(request.form.get('quilometragem'))

        combustivel_val = request.form.get('combustivel')
        niveis = {"1": "Reserva", "2": "2", "3": "3", "4": "4", "5": "5", "6": "Meio", "7": "7", "8": "8", "9": "9", "10": "10", "11": "11", "12": "Cheio"}
        comb_texto = niveis.get(combustivel_val, "N/A")

        itens_marcados = request.form.getlist('checklist')
        resultado_chk = []
        for item in LISTA_CHECKLIST:
            status = "✅ OK" if item in itens_marcados else "❌ Ausente/Avariado"
            resultado_chk.append(f"{item}: {status}")

        avarias = request.form.get('avarias')
        itinerario_texto = request.form.get('itinerario')

        obs_formatada = f"⛽ {comb_texto}\n📝 Observações: {avarias if avarias else 'Nenhuma'}\n\n📋 CHECKLIST:\n" + "\n".join(resultado_chk)

        fotos_str = processar_fotos(request.files.getlist('fotos'))

        viagem_atual = Historico.query.filter_by(veiculo_id=veiculo.id, data_entrada=None).order_by(Historico.id.desc()).first()

        if viagem_atual:
            viagem_atual.km_entrada = km_entrada
            viagem_atual.obs_entrada = obs_formatada
            viagem_atual.itinerario = itinerario_texto
            viagem_atual.fotos_entrada = fotos_str
            # AJUSTADO: Agora salva a devolução cravada no horário de Brasília
            viagem_atual.data_entrada = datetime.now(fuso_brasil)

        veiculo.status = 'Disponível'
        veiculo.usuario_atual = None
        veiculo.setor_atual = None
        veiculo.km_atual = km_entrada
        veiculo.nivel_combustivel = comb_texto

        db.session.commit()
        return redirect(url_for('motorista'))

    return render_template('checkin.html', veiculo=veiculo)

# --- ROTAS DE EDIÇÃO E EXCLUSÃO ---

@app.route('/excluir_veiculo/<int:id>')
def excluir_veiculo(id):
    # TRAVA DE SEGURANÇA
    if not session.get('admin_logado'):
        return redirect(url_for('login_admin'))

    veiculo = Veiculo.query.get_or_404(id)
    veiculo.ativo = False
    db.session.commit()
    return redirect(url_for('gestor'))

@app.route('/editar_veiculo/<int:id>', methods=['GET', 'POST'])
def editar_veiculo(id):
    # TRAVA DE SEGURANÇA
    if not session.get('admin_logado'):
        return redirect(url_for('login_admin'))

    veiculo = Veiculo.query.get_or_404(id)
    if request.method == 'POST':
        veiculo.modelo = request.form.get('modelo')
        veiculo.placa = request.form.get('placa')
        novo_km = request.form.get('km_atual')
        novo_nivel = request.form.get('nivel_combustivel')

        if request.files.get('foto') and request.files.get('foto').filename:
            foto_file = request.files.get('foto')
            filename = secure_filename(foto_file.filename)
            unique_name = f"carro_{datetime.now().strftime('%Y%m%d%H%M%S')}_{filename}"
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], unique_name)
            foto_file.save(filepath)
            veiculo.foto = unique_name

        if novo_km:
            veiculo.km_atual = int(novo_km)
        if novo_nivel:
            veiculo.nivel_combustivel = novo_nivel
        db.session.commit()
        flash(f'Dados do veículo {veiculo.placa} atualizados com sucesso!', 'success')
        return redirect(url_for('gestor'))
    return render_template('editar_veiculo.html', veiculo=veiculo)

@app.route('/detalhe_historico/<int:id>')
def detalhe_historico(id):
    log = Historico.query.get_or_404(id)

    # NOVO: Busca o usuário no banco de dados para descobrir o setor dele
    usuario_banco = Usuario.query.filter_by(nome=log.usuario).first()
    setor_motorista = usuario_banco.setor if usuario_banco else "Não informado"

    return render_template('detalhe.html', log=log, setor=setor_motorista)

@app.route('/exportar_excel', methods=['GET', 'POST'])
def exportar_excel():
    # TRAVA DE SEGURANÇA
    if not session.get('admin_logado'):
        return redirect(url_for('login_admin'))

    # NOVO: Recebe o filtro de mês do formulário (Exemplo: '2026-08')
    mes_filtro = request.form.get('mes_filtro')

    historico_completo = Historico.query.order_by(Historico.data_saida.asc()).all()

    # Se o gestor escolheu um mês específico, o Python filtra a lista
    if mes_filtro:
        historico = [log for log in historico_completo if log.data_saida.strftime('%Y-%m') == mes_filtro]
        if not historico:
            flash(f'Nenhum registro encontrado para o mês selecionado ({mes_filtro}).', 'warning')
            return redirect(url_for('painel_historico'))
    else:
        # Se não escolheu mês (ou clicou em exportar tudo), puxa todo mundo
        historico = historico_completo

    dados = []

    # FUNÇÃO NOVA: Quebra o texto salvo no banco em partes separadas
    def extrair_dados_obs(obs_texto):
        if not obs_texto:
            return "", "", {}

        combustivel = ""
        observacoes = ""
        checklist_dict = {}

        # Divide o bloco entre Cabeçalho (Combustível e Obs) e o Checklist
        if "📋 CHECKLIST:\n" in obs_texto:
            partes = obs_texto.split("\n\n📋 CHECKLIST:\n")
            cabecalho = partes[0]
            checklist_texto = partes[1] if len(partes) > 1 else ""
        else:
            cabecalho = obs_texto
            checklist_texto = ""

        # Extrai o Combustível
        for linha in cabecalho.split('\n'):
            if linha.startswith("⛽ "):
                combustivel = linha.replace("⛽ ", "").strip()

                # --- NOVO: Traduz o texto para incluir o número no Excel ---
                if combustivel == "Cheio":
                    combustivel = "12 (Cheio)"
                elif combustivel == "Meio":
                    combustivel = "6 (Meio)"
                elif combustivel == "Reserva":
                    combustivel = "1 (Reserva)"

        # Extrai as Observações (Pega tudo que vem depois de "📝 Observações: ")
        if "📝 Observações: " in cabecalho:
            observacoes = cabecalho.split("📝 Observações: ")[1].strip()

        # Extrai o Checklist em colunas separadas
        for linha in checklist_texto.split('\n'):
            if ": " in linha:
                item, status = linha.split(": ", 1)
                # Removemos os emojis para o Excel ficar limpo para filtros
                status_limpo = status.replace("✅ ", "").replace("❌ ", "").strip()
                checklist_dict[item.strip()] = status_limpo

        return combustivel, observacoes, checklist_dict

    # Monta a tabela linha por linha
    for log in historico:
        # Busca a validade da CNH do motorista responsável por esta viagem
        motorista = Usuario.query.filter_by(nome=log.usuario).first()
        validade_cnh = motorista.cnh_validade if motorista and motorista.cnh_validade else 'Não cadastrada'

        # Captura o setor para o Excel
        setor_motorista = motorista.setor if motorista else 'Não informado'

        # Quebra os dados de saída e entrada
        comb_saida, obs_saida_limpa, chk_saida = extrair_dados_obs(log.obs_saida)
        comb_entrada, obs_entrada_limpa, chk_entrada = extrair_dados_obs(log.obs_entrada)

        # --- NOVO: CÁLCULO DO TOTAL RODADO NA VIAGEM ---
        if log.km_entrada and log.km_saida:
            total_rodado = log.km_entrada - log.km_saida
        else:
            total_rodado = "" # Fica em branco se a viagem ainda estiver em andamento

        linha_dados = {
            'ID Viagem': log.id,
            'Veículo': log.veiculo.modelo,
            'Placa': log.veiculo.placa,
            'Motorista': log.usuario,
            'Setor': setor_motorista,
            'Validade CNH': validade_cnh,
            'Trajeto Realizado': log.itinerario if log.itinerario else 'Não informado',

            # --- DADOS DE SAÍDA ---
            'Data Saída': log.data_saida.strftime('%d/%m/%Y'),
            'Hora Saída': log.data_saida.strftime('%H:%M'),
            'KM Saída': log.km_saida,
            'Combustível Saída': comb_saida,
            'Observação Saída': obs_saida_limpa,
            'Fotos Saída': 'Sim' if log.fotos_saida else 'Não',

            # --- DADOS DE ENTRADA ---
            'Data Entrada': log.data_entrada.strftime('%d/%m/%Y') if log.data_entrada else 'Em andamento',
            'Hora Entrada': log.data_entrada.strftime('%H:%M') if log.data_entrada else '',
            'KM Entrada': log.km_entrada if log.km_entrada else '',

            # --- A NOVA COLUNA AQUI ---
            'Total Rodado (KM)': total_rodado,

            'Combustível Entrada': comb_entrada,
            'Observação Entrada': obs_entrada_limpa,
            'Fotos Entrada': 'Sim' if log.fotos_entrada else 'Não'
        }

        # Adiciona automaticamente TODAS as colunas do Checklist (Apenas para a Saída)
        for item in LISTA_CHECKLIST:
            nome_coluna = f"[Saída] {item}"
            linha_dados[nome_coluna] = chk_saida.get(item, "")

        dados.append(linha_dados)

    df = pd.DataFrame(dados)
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Histórico de Uso')
    output.seek(0)
    return send_file(output, download_name='Historico_Veiculos.xlsx', as_attachment=True)

@app.route('/relatorio_impresso', methods=['POST'])
def relatorio_impresso():
    # TRAVA DE SEGURANÇA
    if not session.get('admin_logado'):
        return redirect(url_for('login_admin'))

    mes_filtro = request.form.get('mes_filtro')
    historico_completo = Historico.query.order_by(Historico.data_saida.desc()).all()

    if mes_filtro:
        historico = [log for log in historico_completo if log.data_saida.strftime('%Y-%m') == mes_filtro]
        if not historico:
            flash(f'Nenhum registro encontrado para {mes_filtro}.', 'warning')
            return redirect(url_for('painel_historico'))
    else:
        historico = historico_completo

    return render_template('relatorio_impresso.html', historico=historico, mes=mes_filtro)

@app.route('/excluir_usuario/<int:id>')
def excluir_usuario(id):
    # TRAVA DE SEGURANÇA
    if not session.get('admin_logado'):
        return redirect(url_for('login_admin'))

    usuario = Usuario.query.get_or_404(id)
    db.session.delete(usuario)
    db.session.commit()
    return redirect(url_for('painel_usuarios'))

@app.route('/excluir_historico_lote', methods=['POST'])
def excluir_historico_lote():
    # TRAVA DE SEGURANÇA
    if not session.get('admin_logado'):
        return redirect(url_for('login_admin'))

    # Pega todos os IDs que foram marcados na caixinha (checkbox)
    log_ids = request.form.getlist('log_ids')

    if log_ids:
        # Passa por cada ID marcado e exclui do banco
        for log_id in log_ids:
            log = Historico.query.get(int(log_id))
            if log:
                db.session.delete(log)
        db.session.commit()
        flash(f'{len(log_ids)} registro(s) de viagem excluído(s) com sucesso!', 'success')
    else:
        flash('Nenhum registro foi selecionado para exclusão.', 'warning')

    return redirect(url_for('painel_historico'))

@app.route('/editar_usuario/<int:id>', methods=['GET', 'POST'])
def editar_usuario(id):
    # TRAVA DE SEGURANÇA
    if not session.get('admin_logado'):
        return redirect(url_for('login_admin'))

    usuario = Usuario.query.get_or_404(id)
    if request.method == 'POST':
        usuario.nome = request.form.get('nome')
        usuario.login = request.form.get('login')
        usuario.setor = request.form.get('setor')

        # NOVO: Captura e atualiza a CNH
        usuario.cnh_validade = request.form.get('cnh_validade')

        nova_senha = request.form.get('senha')
        if nova_senha:
            usuario.senha = nova_senha

        db.session.commit()
        flash(f'Dados do usuário {usuario.nome} atualizados com sucesso!', 'success')
        return redirect(url_for('painel_usuarios'))

    return render_template('editar_usuario.html', usuario=usuario)

from waitress import serve

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    # --- NOVO: Descobre o IP do computador na rede ---
    import socket
    nome_pc = socket.gethostname()
    ip_pc = socket.gethostbyname(nome_pc)
    
    print("="*50)
    print("🚗 SERVIDOR FUNCABES ATIVO E RODANDO!")
    print(f"👉 Acesso no próprio PC: http://localhost:5003")
    print(f"👉 Acesso para outros na rede: http://{ip_pc}:5003")
    print("="*50)
    
    # Roda o servidor de produção
    serve(app, host='0.0.0.0', port=5003)