import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path
from datetime import date, datetime
import uuid, shutil
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle, PageBreak
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import cm

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / 'data'
PHOTO_DIR = BASE_DIR / 'photos'
REPORT_DIR = BASE_DIR / 'reports'
CHART_DIR = BASE_DIR / 'charts'
ASSETS_DIR = BASE_DIR / 'assets'
for folder in [DATA_DIR, PHOTO_DIR, REPORT_DIR, CHART_DIR]:
    folder.mkdir(exist_ok=True)

INSPECOES_FILE = DATA_DIR / 'inspecoes.csv'
PONTOS_FILE = DATA_DIR / 'pontos_teste.csv'
PRESSOES_PADRAO = [30, 80, 125, 180, 250, 300]
COMPONENTES = [
    'Bomba de engrenagem simples', 'Bomba de engrenagem dupla', 'Bomba de engrenagem tripla', 'Bomba de engrenagem quadrupla',
    'Bomba de pistão simples', 'Bomba de pistão dupla', 'Bomba de pistão tripla',
    'Motor orbital', 'Motor radial', 'Comando hidráulico', 'Válvula', 'Acessórios'
]

def quantidade_estagios(componente):
    c = componente.lower()
    if 'quadrupla' in c: return 4
    if 'tripla' in c: return 3
    if 'dupla' in c: return 2
    return 1

def nome_estagio(i):
    return {1:'Primeiro estágio',2:'Segundo estágio',3:'Terceiro estágio',4:'Quarto estágio'}.get(i, f'Estágio {i}')

def vazao_teorica(deslocamento, rpm):
    return (deslocamento * rpm) / 1000 if deslocamento and rpm else 0

def eficiencia(vazao, vazao_teor):
    return (vazao / vazao_teor) * 100 if vazao_teor else 0

def potencia(pressao, vazao):
    return (pressao * vazao) / 600 if pressao and vazao else 0

def torque(pot_kw, rpm):
    return (9550 * pot_kw) / rpm if rpm else 0

def carregar_csv(path):
    return pd.read_csv(path) if path.exists() else pd.DataFrame()

def salvar_append(path, linha):
    novo = pd.DataFrame([linha])
    if path.exists():
        df = pd.read_csv(path)
        df = pd.concat([df, novo], ignore_index=True)
    else:
        df = novo
    df.to_csv(path, index=False)

def salvar_pontos(linhas):
    novo = pd.DataFrame(linhas)
    if PONTOS_FILE.exists():
        df = pd.read_csv(PONTOS_FILE)
        df = pd.concat([df, novo], ignore_index=True)
    else:
        df = novo
    df.to_csv(PONTOS_FILE, index=False)

def excluir_inspecao(id_inspecao):
    for path in [INSPECOES_FILE, PONTOS_FILE]:
        if path.exists():
            df = pd.read_csv(path)
            if 'id_inspecao' in df.columns:
                df = df[df['id_inspecao'] != id_inspecao]
                df.to_csv(path, index=False)
    pasta = PHOTO_DIR / id_inspecao
    if pasta.exists(): shutil.rmtree(pasta)
    for arq in REPORT_DIR.glob(f'*{id_inspecao}*.pdf'):
        try: arq.unlink()
        except Exception: pass

def grafico(df, id_inspecao, tipo):
    path = CHART_DIR / f'{tipo}_{id_inspecao}.png'
    fig, ax = plt.subplots(figsize=(7,4))
    for estagio, grupo in df.groupby('estagio'):
        grupo = grupo.sort_values('pressao')
        y = grupo['vazao_medida'] if tipo == 'vazao' else grupo['eficiencia']
        ax.plot(grupo['pressao'], y, marker='o', label=estagio)
    ax.set_xlabel('Pressão (bar)')
    ax.set_ylabel('Vazão (L/min)' if tipo == 'vazao' else 'Eficiência volumétrica (%)')
    ax.set_title('Pressão x Vazão' if tipo == 'vazao' else 'Pressão x Eficiência Volumétrica')
    ax.grid(True); ax.legend(); fig.tight_layout(); fig.savefig(path, dpi=180); plt.close(fig)
    return path

def gerar_pdf(dados, df_pontos, fotos):
    pdf = REPORT_DIR / f"Relatorio_{dados['cliente'].replace(' ','_')}_{dados['id_inspecao']}.pdf"
    g1, g2 = grafico(df_pontos, dados['id_inspecao'], 'vazao'), grafico(df_pontos, dados['id_inspecao'], 'eficiencia')
    styles = getSampleStyleSheet()
    doc = SimpleDocTemplate(str(pdf), pagesize=A4, rightMargin=1.5*cm, leftMargin=1.5*cm, topMargin=1.5*cm, bottomMargin=1.5*cm)
    story = []
    logo = ASSETS_DIR / 'logo_vista.png'
    if logo.exists():
        story.append(Image(str(logo), width=6*cm, height=2.2*cm)); story.append(Spacer(1,10))
    story += [Paragraph('<b>Vista Field Service</b>', styles['Title']), Paragraph('Technical Inspection Platform', styles['Heading2']), Spacer(1,16), Paragraph('<b>Relatório Técnico de Visita</b>', styles['Heading1']), Spacer(1,12)]
    dados_tab = [['Cliente',dados['cliente']],['Máquina / Equipamento',dados['maquina']],['Componente',dados['componente']],['Modelo',dados['modelo']],['Data',dados['data']],['Técnico',dados['tecnico']],['Óleo / especificação',dados['oleo']],['Temperatura do óleo',f"{dados['temperatura']} °C"],['Observações',dados['observacoes'] or 'Sem observações adicionais.']]
    t = Table(dados_tab, colWidths=[5*cm,10*cm]); t.setStyle(TableStyle([('BACKGROUND',(0,0),(0,-1),colors.lightgrey),('GRID',(0,0),(-1,-1),0.5,colors.grey),('FONTNAME',(0,0),(0,-1),'Helvetica-Bold'),('VALIGN',(0,0),(-1,-1),'TOP')]))
    story += [t, Spacer(1,18), Paragraph('<b>Medições por estágio</b>', styles['Heading2'])]
    for estagio, grupo in df_pontos.groupby('estagio'):
        story += [Spacer(1,8), Paragraph(f'<b>{estagio}</b>', styles['Heading3'])]
        resumo = [['Deslocamento',f"{grupo['deslocamento'].iloc[0]:.2f} cm³/rev"],['Rotação',f"{grupo['rpm'].iloc[0]:.0f} rpm"],['Vazão teórica',f"{grupo['vazao_teorica'].iloc[0]:.2f} L/min"]]
        tr = Table(resumo, colWidths=[5*cm,5*cm]); tr.setStyle(TableStyle([('GRID',(0,0),(-1,-1),0.5,colors.grey),('BACKGROUND',(0,0),(0,-1),colors.lightgrey)])); story += [tr, Spacer(1,8)]
        linhas = [['Pressão (bar)','Vazão medida (L/min)','Eficiência (%)','Potência (kW)','Torque (Nm)']]
        for _, row in grupo.sort_values('pressao').iterrows():
            linhas.append([f"{row['pressao']:.0f}", f"{row['vazao_medida']:.2f}", f"{row['eficiencia']:.1f}", f"{row['potencia']:.2f}", f"{row['torque']:.1f}"])
        tm = Table(linhas, colWidths=[3*cm,4*cm,3*cm,3*cm,3*cm]); tm.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.lightgrey),('GRID',(0,0),(-1,-1),0.5,colors.grey),('FONTNAME',(0,0),(-1,0),'Helvetica-Bold'),('ALIGN',(0,0),(-1,-1),'CENTER')]))
        story.append(tm)
    story += [PageBreak(), Paragraph('<b>Gráficos da inspeção</b>', styles['Heading1']), Spacer(1,10), Image(str(g1), width=16*cm, height=9*cm), Spacer(1,14), Image(str(g2), width=16*cm, height=9*cm), PageBreak(), Paragraph('<b>Conclusão técnica preliminar</b>', styles['Heading1'])]
    med = df_pontos['eficiencia'].mean()
    if med >= 92: conc = 'A eficiência volumétrica média encontrada está em faixa considerada boa para as condições informadas.'
    elif med >= 85: conc = 'A eficiência volumétrica média está em faixa aceitável, porém recomenda-se acompanhar as condições de operação, temperatura do óleo, sucção, filtragem e rotação real.'
    else: conc = 'A eficiência volumétrica média está abaixo do esperado. Recomenda-se investigar sucção, rotação real, temperatura do óleo, válvulas de alívio, contaminação e possível desgaste interno do componente.'
    story.append(Paragraph(conc, styles['BodyText']))
    if fotos:
        story += [PageBreak(), Paragraph('<b>Registros fotográficos</b>', styles['Heading1'])]
        for fp in fotos:
            try: story += [Spacer(1,12), Image(str(fp), width=14*cm, height=9*cm), Paragraph(Path(fp).name, styles['BodyText'])]
            except Exception: pass
    doc.build(story)
    return pdf

st.set_page_config(page_title='Vista Field Service', page_icon='🔧', layout='wide')
if 'pagina' not in st.session_state: st.session_state.pagina = 'Início'
def ir(p): st.session_state.pagina = p
def botao_inicio():
    if st.button('🏠 Início'):
        ir('Início'); st.rerun()

col_logo, col_title = st.columns([1,4])
with col_logo:
    logo = ASSETS_DIR / 'logo_vista.png'
    if logo.exists(): st.image(str(logo), width=170)
with col_title:
    st.title('Vista Field Service'); st.subheader('Technical Inspection Platform')
st.divider()

if st.session_state.pagina == 'Início':
    st.header('Menu principal')
    c1,c2,c3 = st.columns(3)
    with c1:
        if st.button('➕ Nova inspeção', use_container_width=True): ir('Nova inspeção'); st.rerun()
    with c2:
        if st.button('📋 Histórico', use_container_width=True): ir('Histórico'); st.rerun()
    with c3:
        if st.button('📊 Dashboard', use_container_width=True): ir('Dashboard'); st.rerun()

elif st.session_state.pagina == 'Nova inspeção':
    botao_inicio(); st.header('Nova inspeção técnica')
    col1,col2 = st.columns(2)
    with col1:
        cliente = st.text_input('Cliente')
        maquina = st.text_input('Máquina / Equipamento')
        tecnico = st.text_input('Técnico', value='Alon')
        data_visita = st.date_input('Data', value=date.today())
        componente = st.selectbox('Componente', COMPONENTES)
        modelo = st.text_input('Modelo', value='VBH365 / PGP365')
    with col2:
        oleo = st.text_input('Especificação do óleo', value='Óleo hidráulico mineral')
        temperatura = st.number_input('Temperatura do óleo (°C)', min_value=0.0, value=55.0, step=1.0)
        observacoes = st.text_area('Observações técnicas')
    qtd = quantidade_estagios(componente)
    st.info(f'Componente selecionado: {componente}. Quantidade de estágios: {qtd}.')
    todos = []
    st.subheader('Medições por pressão')
    for i in range(1, qtd+1):
        estagio = nome_estagio(i)
        with st.expander(estagio, expanded=True):
            c1,c2 = st.columns(2)
            with c1: desloc = st.number_input(f'Deslocamento {estagio} (cm³/rev)', min_value=0.0, value=118.0 if i == 1 else 132.8 if i == 2 else 0.0, step=0.1, key=f'desloc_{i}')
            with c2: rpm = st.number_input(f'Rotação {estagio} (rpm)', min_value=0.0, value=540.0, step=1.0, key=f'rpm_{i}')
            qt = vazao_teorica(desloc, rpm)
            st.caption(f'Vazão teórica calculada para {estagio}: {qt:.2f} L/min')
            tabela = pd.DataFrame({'pressao':PRESSOES_PADRAO, 'vazao_medida':[0.0]*len(PRESSOES_PADRAO)})
            edit = st.data_editor(tabela, key=f'tabela_{i}', use_container_width=True, hide_index=True, column_config={'pressao': st.column_config.NumberColumn('Pressão (bar)', disabled=True), 'vazao_medida': st.column_config.NumberColumn('Vazão medida (L/min)', min_value=0.0, step=0.1)})
            prev = edit.copy(); prev['eficiencia'] = prev['vazao_medida'].apply(lambda x: eficiencia(float(x), qt))
            st.write('Prévia de eficiência:')
            st.dataframe(prev.rename(columns={'pressao':'Pressão (bar)','vazao_medida':'Vazão medida (L/min)','eficiencia':'Eficiência (%)'}), use_container_width=True, hide_index=True)
            for _, row in edit.iterrows():
                vaz = float(row['vazao_medida']); pres = float(row['pressao']); eff = eficiencia(vaz, qt); pot = potencia(pres, vaz); tor = torque(pot, rpm)
                todos.append({'estagio':estagio,'deslocamento':desloc,'rpm':rpm,'pressao':pres,'vazao_medida':vaz,'vazao_teorica':qt,'eficiencia':eff,'potencia':pot,'torque':tor})
    st.subheader('Fotos da visita')
    fotos = st.file_uploader('Adicionar fotos', type=['png','jpg','jpeg'], accept_multiple_files=True)
    col_calc,col_save = st.columns(2)
    with col_calc: calcular = st.button('🧮 Calcular / atualizar prévia', use_container_width=True)
    with col_save: salvar = st.button('💾 Salvar inspeção e gerar relatório', use_container_width=True)
    df_prev = pd.DataFrame(todos)
    if calcular:
        st.subheader('Resultado geral da prévia')
        st.dataframe(df_prev, use_container_width=True, hide_index=True)
        if not df_prev.empty:
            st.metric('Eficiência média', f"{df_prev['eficiencia'].mean():.1f} %")
            fig, ax = plt.subplots()
            for est, grupo in df_prev.groupby('estagio'):
                grupo = grupo.sort_values('pressao'); ax.plot(grupo['pressao'], grupo['vazao_medida'], marker='o', label=est)
            ax.set_xlabel('Pressão (bar)'); ax.set_ylabel('Vazão (L/min)'); ax.grid(True); ax.legend(); st.pyplot(fig)
    if salvar:
        if not cliente.strip(): st.error('Preencha o cliente antes de salvar.')
        else:
            id_ins = str(uuid.uuid4())[:8]
            dados = {'id_inspecao':id_ins,'cliente':cliente,'maquina':maquina,'tecnico':tecnico,'data':str(data_visita),'componente':componente,'modelo':modelo,'oleo':oleo,'temperatura':temperatura,'observacoes':observacoes,'criado_em':datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
            salvar_append(INSPECOES_FILE, dados)
            pontos = []
            for p in todos:
                x = p.copy(); x['id_inspecao'] = id_ins; x['cliente'] = cliente; x['componente'] = componente; pontos.append(x)
            salvar_pontos(pontos); df_pontos = pd.DataFrame(pontos)
            foto_paths = []; pasta = PHOTO_DIR / id_ins; pasta.mkdir(exist_ok=True)
            for foto in fotos:
                path = pasta / foto.name
                with open(path, 'wb') as f: f.write(foto.getbuffer())
                foto_paths.append(path)
            pdf = gerar_pdf(dados, df_pontos, foto_paths)
            st.success('Inspeção salva e relatório gerado com sucesso.')
            with open(pdf, 'rb') as f: st.download_button('📄 Baixar relatório PDF', data=f, file_name=pdf.name, mime='application/pdf', use_container_width=True)

elif st.session_state.pagina == 'Histórico':
    botao_inicio(); st.header('Histórico de inspeções')
    df_ins = carregar_csv(INSPECOES_FILE); df_pts = carregar_csv(PONTOS_FILE)
    if df_ins.empty: st.info('Ainda não há inspeções salvas.')
    else:
        clientes = ['Todos'] + sorted(df_ins['cliente'].dropna().unique().tolist())
        filtro = st.selectbox('Filtrar por cliente', clientes)
        df_view = df_ins if filtro == 'Todos' else df_ins[df_ins['cliente'] == filtro]
        st.dataframe(df_view, use_container_width=True, hide_index=True)
        st.subheader('Abrir / excluir inspeção')
        opcoes = [f"{r['id_inspecao']} | {r['cliente']} | {r['data']} | {r['componente']}" for _, r in df_view.iterrows()]
        if opcoes:
            sel = st.selectbox('Selecione uma inspeção', opcoes); id_sel = sel.split(' | ')[0]
            c1,c2 = st.columns(2)
            with c1:
                if st.button('🔍 Ver detalhes', use_container_width=True):
                    st.write('Dados da inspeção:'); st.dataframe(df_ins[df_ins['id_inspecao']==id_sel], use_container_width=True, hide_index=True)
                    st.write('Pontos de teste:')
                    if not df_pts.empty: st.dataframe(df_pts[df_pts['id_inspecao']==id_sel], use_container_width=True, hide_index=True)
            with c2:
                confirmar = st.checkbox('Confirmar exclusão desta inspeção')
                if st.button('🗑️ Excluir inspeção selecionada', use_container_width=True):
                    if confirmar: excluir_inspecao(id_sel); st.success('Inspeção excluída.'); st.rerun()
                    else: st.warning('Marque a confirmação antes de excluir.')

elif st.session_state.pagina == 'Dashboard':
    botao_inicio(); st.header('Dashboard')
    df_ins = carregar_csv(INSPECOES_FILE); df_pts = carregar_csv(PONTOS_FILE)
    if df_ins.empty or df_pts.empty: st.info('Ainda não há dados suficientes para gráficos.')
    else:
        clientes = ['Todos'] + sorted(df_ins['cliente'].dropna().unique().tolist())
        filtro = st.selectbox('Cliente', clientes)
        df_view = df_pts.copy()
        if filtro != 'Todos':
            ids = df_ins[df_ins['cliente']==filtro]['id_inspecao'].tolist(); df_view = df_view[df_view['id_inspecao'].isin(ids)]
        c1,c2,c3 = st.columns(3)
        c1.metric('Inspeções salvas', df_ins['id_inspecao'].nunique()); c2.metric('Pontos de teste', len(df_view)); c3.metric('Eficiência média', f"{df_view['eficiencia'].mean():.1f} %")
        st.subheader('Gráfico 1 — Pressão x Vazão')
        fig, ax = plt.subplots()
        for id_ins, grupo_id in df_view.groupby('id_inspecao'):
            cliente_label = grupo_id['cliente'].iloc[0] if 'cliente' in grupo_id.columns else id_ins
            for est, grupo in grupo_id.groupby('estagio'):
                grupo = grupo.sort_values('pressao'); ax.plot(grupo['pressao'], grupo['vazao_medida'], marker='o', label=f'{cliente_label} - {est}')
        ax.set_xlabel('Pressão (bar)'); ax.set_ylabel('Vazão (L/min)'); ax.grid(True); ax.legend(fontsize=8); st.pyplot(fig)
        st.subheader('Gráfico 2 — Pressão x Eficiência volumétrica')
        fig2, ax2 = plt.subplots()
        for id_ins, grupo_id in df_view.groupby('id_inspecao'):
            cliente_label = grupo_id['cliente'].iloc[0] if 'cliente' in grupo_id.columns else id_ins
            for est, grupo in grupo_id.groupby('estagio'):
                grupo = grupo.sort_values('pressao'); ax2.plot(grupo['pressao'], grupo['eficiencia'], marker='o', label=f'{cliente_label} - {est}')
        ax2.set_xlabel('Pressão (bar)'); ax2.set_ylabel('Eficiência volumétrica (%)'); ax2.grid(True); ax2.legend(fontsize=8); st.pyplot(fig2)
