import streamlit as st
import easyocr
import numpy as np
from PIL import Image
import re
import streamlit.components.v1 as components
import gspread
from google.oauth2.service_account import Credentials
import json
from datetime import datetime
import pytz

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Expedição SPA1", page_icon="🚚", layout="wide")

# --- NOME NO TOPO ---
st.markdown('<div style="text-align: right; color: grey; font-weight: bold;">Ezequiel Miranda</div>', unsafe_allow_html=True)

# --- 1. CONEXÃO COM GOOGLE SHEETS (EM SUBSTITUIÇÃO AO FIREBASE) ---
@st.cache_resource
def get_sheets_client():
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    key_dict = st.secrets["firestore_key"]
    if isinstance(key_dict, str):
        key_dict = json.loads(key_dict)
    creds = Credentials.from_service_account_info(key_dict, scopes=scope)
    return gspread.authorize(creds)

def salvar_no_sheets():
    try:
        client = get_sheets_client()
        sh = client.open("Expedicao_SPA1")
        worksheet = sh.get_worksheet(0)
        dados_json = json.dumps(st.session_state.dados_controle)
        worksheet.update_acell('A1', dados_json)
    except Exception as e:
        st.error(f"Erro ao salvar na nuvem: {e}")

def carregar_do_sheets():
    try:
        client = get_sheets_client()
        sh = client.open("Expedicao_SPA1")
        worksheet = sh.get_worksheet(0)
        conteudo = worksheet.acell('A1').value
        return json.loads(conteudo) if conteudo else None
    except:
        return None

# --- 2. NOTIFICAÇÃO PÓS-SYNC ---
if st.session_state.get('sync_ok'):
    st.toast("Sincronizado com o Google Sheets! ☁️✅", icon="🔄")
    st.session_state['sync_ok'] = False

# --- 3. DATA AUTOMÁTICA (Brasília) ---
fuso_br = pytz.timezone('America/Sao_Paulo')
data_hoje = datetime.now(fuso_br).strftime('%d/%m/%Y')

# --- 4. FUNÇÕES DE CALLBACK ---
def atualizar_ilha(rota):
    novo_valor = st.session_state[f"l_{rota}"]
    st.session_state.dados_controle[rota]['letra'] = novo_valor
    salvar_no_sheets()

def atualizar_hora(rota):
    novo_valor = st.session_state[f"h_{rota}"]
    st.session_state.dados_controle[rota]['janela'] = novo_valor
    salvar_no_sheets()

# --- 5. ESTILIZAÇÃO CSS (IGUAL AO ORIGINAL) ---
st.markdown("""
    <style>
    #MainMenu {visibility: hidden;} footer {visibility: hidden;} header {visibility: hidden;}
    .stDeployButton {display:none;}
    div[data-testid="stHorizontalBlock"] > div:nth-child(2) button[kind="secondary"] {
        background-color: #ff4b4b !important; color: white !important; border: none !important;
    }
    div.stButton > button:first-child[kind="primary"] {
        background-color: #007bff !important; border: none;
    }
    </style>
    """, unsafe_allow_html=True)

# --- 6. TÍTULO PRINCIPAL ---
st.title("📦 Controle de Carregamento XPT SPA1 - AM/MM")
st.write(f"Analista: **Ezequiel Miranda**")

@st.cache_resource
def load_ocr():
    return easyocr.Reader(['pt'])

reader = load_ocr()

# --- 7. INICIALIZAÇÃO DE DADOS ---
def organizar_dados(dados_brutos):
    ordem_fixa = ["EPA1", "EPA9", "EMN1", "EPA2", "EPA6"]
    dados_ordenados = {}
    for rota in ordem_fixa:
        if rota in dados_brutos:
            dados_ordenados[rota] = dados_brutos[rota]
    for rota in dados_brutos:
        if rota not in dados_ordenados:
            dados_ordenados[rota] = dados_brutos[rota]
    return dados_ordenados

if 'dados_controle' not in st.session_state:
    dados_nuvem = carregar_do_sheets()
    if dados_nuvem:
        st.session_state.dados_controle = organizar_dados(dados_nuvem)
    else:
        st.session_state.dados_controle = {
            "EPA1": {"local": "CAPANEMA", "janela": "04:30 às 06:30", "letra": "?", "veiculos": []},
            "EPA9": {"local": "SANTA LUZIA", "janela": "04:30 às 06:30", "letra": "?", "veiculos": []},
            "EMN1": {"local": "IMPERATRIZ", "janela": "06:00 às 08:00", "letra": "?", "veiculos": []},
            "EPA2": {"local": "ABAETETUBA", "janela": "06:00 às 08:00", "letra": "?", "veiculos": []},
            "EPA6": {"local": "BARCARENA", "janela": "06:00 às 08:00", "letra": "?", "veiculos": []},
        }

# --- 8. BOTÕES DE AÇÃO ---
col_sync, col_clear, col_add = st.columns([1, 1, 1])
with col_sync:
    if st.button("🔄 Sincronizar", use_container_width=True, type="primary"):
        st.cache_data.clear()
        dados_novos = carregar_do_sheets()
        if dados_novos:
            st.session_state.dados_controle = organizar_dados(dados_novos)
            st.session_state['sync_ok'] = True
            st.rerun()

with col_clear:
    if st.button("🗑️ Limpar Tudo", use_container_width=True, type="secondary"):
        for rota in st.session_state.dados_controle:
            st.session_state.dados_controle[rota]["veiculos"] = []
            st.session_state.dados_controle[rota]["letra"] = "?"
        salvar_no_sheets()
        st.rerun()

with col_add:
    with st.popover("➕ Nova Rota", use_container_width=True):
        nova_id = st.text_input("ID da Rota").upper()
        nova_cid = st.text_input("Cidade").upper()
        if st.button("Confirmar Adição"):
            if nova_id and nova_cid:
                st.session_state.dados_controle[nova_id] = {"local": nova_cid, "janela": "00:00 às 00:00", "letra": "?", "veiculos": []}
                salvar_no_sheets()
                st.rerun()

# --- 9. CABEÇALHO ---
col_h1, col_h2 = st.columns(2)
with col_h1:
    titulo_geral = st.text_input("Título", "CARREGAMENTO AM/MM")
with col_h2:
    data_carregamento = st.text_input("Data", data_hoje)

# --- 10. EXTRAÇÃO INTELIGENTE ---
uploaded_file = st.file_uploader("Upload do Print", type=["jpg", "png", "jpeg"])
if uploaded_file:
    img = Image.open(uploaded_file)
    if st.button("🔍 EXTRAIR DADOS"):
        with st.spinner("Lendo print..."):
            resultados = reader.readtext(np.array(img))
            padrao_placa = re.compile(r'[A-Z]{3}[0-9][A-Z0-9][0-9]{2}')
            for res in resultados:
                texto = res[1].upper()
                for id_rota, info in st.session_state.dados_controle.items():
                    if id_rota in texto or info['local'] in texto:
                        match = padrao_placa.search(texto.replace(" ", ""))
                        if match:
                            placa = match.group(0)
                            if not any(v['placa'] == placa for v in info['veiculos']):
                                info['veiculos'].append({"placa": placa, "status": "PENDENTE", "doca": ""})
            salvar_no_sheets()
            st.rerun()

# --- 11. EDIÇÃO INSTANTÂNEA (LAYOUT ORIGINAL) ---
for rota, info in st.session_state.dados_controle.items():
    with st.expander(f"📍 {rota} | Ilha: {info['letra']} | {info['local']}", expanded=True):
        c_l, c_h, c_a = st.columns([1, 2, 1])
        c_l.text_input("Ilha", value=info['letra'], key=f"l_{rota}", on_change=atualizar_ilha, args=(rota,))
        c_h.text_input("Hora", value=info['janela'], key=f"h_{rota}", on_change=atualizar_hora, args=(rota,))
        
        if c_a.button("➕ Placa", key=f"add_{rota}"):
            info['veiculos'].append({"placa": "", "status": "PENDENTE", "doca": ""})
            salvar_no_sheets()
            st.rerun()

        for idx, v in enumerate(info['veiculos']):
            c1, c_doca, c2, c_move, c3 = st.columns([2, 1, 2, 0.5, 0.5])
            
            nova_p = c1.text_input("Placa", v['placa'], key=f"p_{rota}_{idx}").upper()
            nova_d = c_doca.text_input("Doca", v.get('doca',''), key=f"d_{rota}_{idx}").upper()
            
            if nova_p != v['placa'] or nova_d != v.get('doca',''):
                v['placa'] = nova_p
                v['doca'] = nova_d
                salvar_no_sheets()

            status_opcoes = ["PENDENTE", "FINALIZADO", "EM CARREGAMENTO", "CANCELADO", "AGUARDANDO CARREGAMENTO"]
            novo_s = c2.selectbox("Status", status_opcoes, index=status_opcoes.index(v['status']) if v['status'] in status_opcoes else 0, key=f"s_{rota}_{idx}")
            
            if novo_s != v['status']:
                v['status'] = novo_s
                if novo_s == "FINALIZADO":
                    v['hora_finalizacao'] = datetime.now(fuso_br).strftime('%H:%M')
                salvar_no_sheets()
            
            with c_move:
                st.markdown('<div style="margin-top: 28px;"></div>', unsafe_allow_html=True)
                with st.popover("🔄"):
                    for dest in st.session_state.dados_controle.keys():
                        if dest != rota and st.button(dest, key=f"mv_{rota}_{dest}_{idx}"):
                            st.session_state.dados_controle[dest]["veiculos"].append(v.copy())
                            info['veiculos'].pop(idx)
                            salvar_no_sheets()
                            st.rerun()

            with c3:
                st.markdown('<div style="margin-top: 28px;"></div>', unsafe_allow_html=True)
                if st.button("❌", key=f"x_{rota}_{idx}", use_container_width=True):
                    info['veiculos'].pop(idx)
                    salvar_no_sheets()
                    st.rerun()
            st.divider()

# --- 12. WHATSAPP ---
res_texto = f"*{titulo_geral} {data_carregamento}*\n\n"
tem_placa = False
for rota, info in st.session_state.dados_controle.items():
    v_validos = [v for v in info['veiculos'] if v['placa'].strip()]
    if v_validos:
        tem_placa = True
        res_texto += f"*{rota}* ({info['local']}) ({info['janela']})\nLetra: *{info['letra']}*\n"
        for v in v_validos:
            status_emoji = "🟡"
            if v['status'] == "FINALIZADO": status_emoji = f"✅ {v.get('hora_finalizacao', '')}"
            elif v['status'] == "CANCELADO": status_emoji = "❌"
            elif "CARREGAMENTO" in v['status']: status_emoji = "⏳"
            
            doca_txt = f" [Doca: {v['doca']}]" if v.get('doca') else ""
            res_texto += f"🚚 {v['placa']}{doca_txt} - {v['status']} {status_emoji}\n"
        res_texto += "\n"

if tem_placa:
    st.divider()
    st.text_area("Texto para Copiar", res_texto, height=400)
    js_code = f"""
    <script>
    function copiarTexto() {{
        const textToCopy = `{res_texto}`;
        navigator.clipboard.writeText(textToCopy).then(() => {{
            alert("Texto copiado para o WhatsApp com sucesso! ✅");
        }});
    }}
    </script>
    <button style="width:100%; background:#25D366; color:white; border:none; padding:12px; border-radius:8px; font-weight:bold; cursor:pointer;" onclick="copiarTexto()">COPIAR PARA WHATSAPP</button>
    """
    components.html(js_code, height=70)
