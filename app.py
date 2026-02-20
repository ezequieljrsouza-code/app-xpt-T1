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
st.set_page_config(page_title="Expedição SPA1 - Sheets", page_icon="🚚", layout="wide")

# --- NOME NO TOPO ---
st.markdown('<div style="text-align: right; color: grey; font-weight: bold;">Ezequiel Miranda</div>', unsafe_allow_html=True)

# --- 1. CONEXÃO COM GOOGLE SHEETS ---
@st.cache_resource
def get_sheets_client():
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    # Usa o mesmo segredo que você já configurou
    key_dict = st.secrets["firestore_key"]
    if isinstance(key_dict, str):
        key_dict = json.loads(key_dict)
    
    creds = Credentials.from_service_account_info(key_dict, scopes=scope)
    return gspread.authorize(creds)

def salvar_no_sheets():
    try:
        client = get_sheets_client()
        # Substitua pelo NOME exato da sua planilha
        sh = client.open("Expedicao_SPA1") 
        worksheet = sh.get_worksheet(0)
        
        # Vamos salvar os dados como uma string JSON em uma célula específica (A1)
        # Isso mantém sua estrutura complexa de rotas e veículos intacta
        dados_json = json.dumps(st.session_state.dados_controle)
        worksheet.update_acell('A1', dados_json)
    except Exception as e:
        st.error(f"Erro ao salvar: {e}")

def carregar_do_sheets():
    try:
        client = get_sheets_client()
        sh = client.open("Expedicao_SPA1")
        worksheet = sh.get_worksheet(0)
        conteudo = worksheet.acell('A1').value
        return json.loads(conteudo) if conteudo else None
    except:
        return None

# --- 2. DATA E FUSO ---
fuso_br = pytz.timezone('America/Sao_Paulo')
data_hoje = datetime.now(fuso_br).strftime('%d/%m/%Y')

# --- 3. CALLBACKS ---
def atualizar_dados():
    salvar_no_sheets()

# --- 4. INICIALIZAÇÃO DE DADOS ---
if 'dados_controle' not in st.session_state:
    dados_nuvem = carregar_do_sheets()
    if dados_nuvem:
        st.session_state.dados_controle = dados_nuvem
    else:
        st.session_state.dados_controle = {
            "EPA1": {"local": "CAPANEMA", "janela": "04:30 às 06:30", "letra": "?", "veiculos": []},
            "EPA9": {"local": "SANTA LUZIA", "janela": "04:30 às 06:30", "letra": "?", "veiculos": []},
            "EMN1": {"local": "IMPERATRIZ", "janela": "06:00 às 08:00", "letra": "?", "veiculos": []},
            "EPA2": {"local": "ABAETETUBA", "janela": "06:00 às 08:00", "letra": "?", "veiculos": []},
            "EPA6": {"local": "BARCARENA", "janela": "06:00 às 08:00", "letra": "?", "veiculos": []},
        }

# --- 5. TÍTULO E ESTILO ---
st.title("📦 Controle XPT SPA1 (Google Sheets)")
st.markdown("<style>div.stButton > button:first-child { background-color: #007bff; color: white; }</style>", unsafe_allow_html=True)

# --- 6. BOTÕES DE CONTROLE ---
col_sync, col_clear = st.columns(2)
with col_sync:
    if st.button("🔄 Sincronizar Agora"):
        st.session_state.dados_controle = carregar_do_sheets()
        st.rerun()

with col_clear:
    if st.button("🗑️ Limpar Tudo"):
        for r in st.session_state.dados_controle:
            st.session_state.dados_controle[r]["veiculos"] = []
            st.session_state.dados_controle[r]["letra"] = "?"
        salvar_no_sheets()
        st.rerun()

# --- 7. EXTRAÇÃO OCR (MANTIDA) ---
@st.cache_resource
def load_ocr(): return easyocr.Reader(['pt'])
reader = load_ocr()

uploaded_file = st.file_uploader("Upload do Print", type=["jpg", "png", "jpeg"])
if uploaded_file:
    img = Image.open(uploaded_file)
    if st.button("🔍 EXTRAIR"):
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

# --- 8. INTERFACE DE EDIÇÃO ---
for rota, info in st.session_state.dados_controle.items():
    with st.expander(f"📍 {rota} | Ilha: {info['letra']} | {info['local']}"):
        c1, c2, c3 = st.columns([1, 1, 1])
        # Atualização automática ao mudar valor
        nova_ilha = c1.text_input("Ilha", info['letra'], key=f"l_{rota}")
        if nova_ilha != info['letra']:
            info['letra'] = nova_ilha
            salvar_no_sheets()
            
        if c3.button("➕ Placa", key=f"add_{rota}"):
            info['veiculos'].append({"placa": "", "status": "PENDENTE", "doca": ""})
            salvar_no_sheets()
            st.rerun()

        for idx, v in enumerate(info['veiculos']):
            cols = st.columns([2, 1, 2, 0.5])
            v['placa'] = cols[0].text_input("Placa", v['placa'], key=f"p_{rota}_{idx}").upper()
            v['doca'] = cols[1].text_input("Doca", v.get('doca',''), key=f"d_{rota}_{idx}").upper()
            
            status_opcoes = ["PENDENTE", "FINALIZADO", "EM CARREGAMENTO", "CANCELADO"]
            novo_s = cols[2].selectbox("Status", status_opcoes, index=status_opcoes.index(v['status']) if v['status'] in status_opcoes else 0, key=f"s_{rota}_{idx}")
            if novo_s != v['status']:
                v['status'] = novo_s
                if novo_s == "FINALIZADO": v['hora_finalizacao'] = datetime.now(fuso_br).strftime('%H:%M')
                salvar_no_sheets()
            
            if cols[3].button("❌", key=f"x_{rota}_{idx}"):
                info['veiculos'].pop(idx)
                salvar_no_sheets()
                st.rerun()

# --- 9. WHATSAPP (MANTIDO) ---
# ... (mesmo código de geração de texto que você já tinha)
