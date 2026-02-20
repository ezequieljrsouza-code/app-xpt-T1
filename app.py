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

st.markdown('<div style="text-align: right; color: grey; font-weight: bold;">Ezequiel Miranda</div>', unsafe_allow_html=True)

# --- 1. CONEXÃO GOOGLE SHEETS ---
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
def atualizar_ilha(rota):
    st.session_state.dados_controle[rota]['letra'] = st.session_state[f"l_{rota}"]
    salvar_no_sheets()

def atualizar_hora(rota):
    st.session_state.dados_controle[rota]['janela'] = st.session_state[f"h_{rota}"]
    salvar_no_sheets()

# --- 4. CSS ---
st.markdown("""
    <style>
    #MainMenu {visibility: hidden;} footer {visibility: hidden;} header {visibility: hidden;}
    div[data-testid="stHorizontalBlock"] > div:nth-child(2) button { background-color: #ff4b4b !important; color: white !important; }
    div.stButton > button:first-child[kind="primary"] { background-color: #007bff !important; }
    </style>
    """, unsafe_allow_html=True)

# --- 5. INICIALIZAÇÃO ---
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

# --- 6. BOTÕES DE AÇÃO ---
col_sync, col_clear, col_add = st.columns([1, 1, 1])
with col_sync:
    if st.button("🔄 Sincronizar", use_container_width=True, type="primary"):
        st.cache_data.clear()
        dados = carregar_do_sheets()
        if dados: st.session_state.dados_controle = dados
        st.toast("Dados atualizados! ☁️")
        st.rerun()

with col_clear:
    if st.button("🗑️ Limpar Tudo", use_container_width=True):
        for r in st.session_state.dados_controle:
            st.session_state.dados_controle[r]["veiculos"] = []
            st.session_state.dados_controle[r]["letra"] = "?"
        salvar_no_sheets()
        st.toast("Painel limpo! 🗑️")
        st.rerun()

with col_add:
    with st.popover("➕ Nova Rota", use_container_width=True):
        n_id = st.text_input("ID Rota").upper()
        n_cid = st.text_input("Cidade").upper()
        if st.button("Adicionar"):
            if n_id and n_cid:
                st.session_state.dados_controle[n_id] = {"local": n_cid, "janela": "00:00 às 00:00", "letra": "?", "veiculos": []}
                salvar_no_sheets()
                st.rerun()

# --- 7. EXTRAÇÃO AJUSTADA PARA A IMAGEM OVERVIEW ---
@st.cache_resource
def load_ocr(): return easyocr.Reader(['pt'])
reader = load_ocr()

st.title("📦 Controle de Carregamento XPT SPA1")
uploaded_file = st.file_uploader("Upload do Print Overview", type=["jpg", "png", "jpeg"])

if uploaded_file:
    img = Image.open(uploaded_file)
    if st.button("🔍 EXTRAIR DADOS DA TABELA"):
        with st.spinner("Analisando colunas..."):
            # OCR lê o texto e a posição (bbox)
            resultados = reader.readtext(np.array(img))
            
            # Padrão de Placa Mercosul e Antiga
            padrao_placa = re.compile(r'[A-Z]{3}[0-9][A-Z0-9][0-9]{2}')
            
            # Agrupar por linhas aproximadas (Y)
            linhas = {}
            for (bbox, texto, prob) in resultados:
                y_center = int((bbox[0][1] + bbox[2][1]) / 2)
                encontrado = False
                for y_ref in linhas.keys():
                    if abs(y_center - y_ref) < 20:
                        linhas[y_ref].append(texto.upper())
                        encontrado = True
                        break
                if not encontrado:
                    linhas[y_center] = [texto.upper()]

            for y in linhas:
                row_text = " ".join(linhas[y])
                
                # Identifica a Rota (ex: EPA1) ou Local (ex: CAPANEMA)
                for id_rota, info in st.session_state.dados_controle.items():
                    if id_rota in row_text or info['local'] in row_text:
                        # Busca Placa na mesma linha
                        match = padrao_placa.search(row_text.replace(" ", ""))
                        if match:
                            placa = match.group(0)
                            # Verifica se já existe
                            if not any(v['placa'] == placa for v in info['veiculos']):
                                # Define Status inicial baseado na imagem
                                status_img = "FINALIZADO" if "FINALIZADO" in row_text else "PENDENTE"
                                info['veiculos'].append({
                                    "placa": placa, 
                                    "status": status_img, 
                                    "doca": "",
                                    "hora_finalizacao": datetime.now(fuso_br).strftime('%H:%M') if status_img == "FINALIZADO" else ""
                                })
            
            salvar_no_sheets()
            st.toast("Dados extraídos com sucesso! ✅")
            st.rerun()

# --- 8. LAYOUT DE EDIÇÃO ---
for rota, info in st.session_state.dados_controle.items():
    with st.expander(f"📍 {rota} | {info['local']} | Ilha: {info['letra']}", expanded=True):
        c_l, c_h, c_a = st.columns([1, 2, 1])
        c_l.text_input("Ilha", value=info['letra'], key=f"l_{rota}", on_change=atualizar_ilha, args=(rota,))
        c_h.text_input("Hora", value=info['janela'], key=f"h_{rota}", on_change=atualizar_hora, args=(rota,))
        
        if c_a.button("➕ Placa", key=f"add_{rota}"):
            info['veiculos'].append({"placa": "", "status": "PENDENTE", "doca": ""})
            salvar_no_sheets()
            st.rerun()

        for idx, v in enumerate(info['veiculos']):
            c1, c_doca, c2, c_move, c3 = st.columns([2, 1, 2, 0.5, 0.5])
            
            v['placa'] = c1.text_input("Placa", v['placa'], key=f"p_{rota}_{idx}").upper()
            v['doca'] = c_doca.text_input("Doca", v.get('doca',''), key=f"d_{rota}_{idx}").upper()
            
            status_opcoes = ["PENDENTE", "FINALIZADO", "EM CARREGAMENTO", "CANCELADO", "AGUARDANDO"]
            novo_s = c2.selectbox("Status", status_opcoes, index=status_opcoes.index(v['status']) if v['status'] in status_opcoes else 0, key=f"s_{rota}_{idx}")
            
            if novo_s != v['status']:
                v['status'] = novo_s
                if novo_s == "FINALIZADO": v['hora_finalizacao'] = datetime.now(fuso_br).strftime('%H:%M')
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

            if c3.button("❌", key=f"x_{rota}_{idx}"):
                info['veiculos'].pop(idx)
                salvar_no_sheets()
                st.rerun()
            st.divider()

# --- 9. WHATSAPP ---
res_texto = f"*CARREGAMENTO {data_hoje}*\n\n"
for rota, info in st.session_state.dados_controle.items():
    if info['veiculos']:
        res_texto += f"*{rota}* ({info['local']})\n"
        for v in info['veiculos']:
            emoji = "✅" if v['status'] == "FINALIZADO" else "⏳"
            res_texto += f"🚚 {v['placa']} - {v['status']} {emoji}\n"
        res_texto += "\n"

st.text_area("Texto WhatsApp", res_texto, height=200)
components.html(f"""
    <button style="width:100%; background:#25D366; color:white; border:none; padding:12px; border-radius:8px; font-weight:bold; cursor:pointer;" 
    onclick="navigator.clipboard.writeText(`{res_texto}`).then(()=>alert('Copiado!'))">COPIAR PARA WHATSAPP</button>
""", height=70)
