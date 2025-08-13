import streamlit as st
import pandas as pd
import xml.etree.ElementTree as ET
from io import BytesIO

def extrair_dados_nfe(xml_content):
    """
    Analisa o conteúdo de um XML de NF-e e extrai os dados relevantes.
    
    Args:
        xml_content (bytes): O conteúdo do arquivo XML.

    Returns:
        pandas.DataFrame: Um DataFrame com os dados extraídos ou None se ocorrer um erro.
    """
    try:
        root = ET.fromstring(xml_content)
        
        # O namespace é crucial para encontrar os elementos corretamente
        ns = {'nfe': 'http://www.portalfiscal.inf.br/nfe'}

        # --- Acessando o nó principal da NFe ---
        # A estrutura pode ser <nfeProc><NFe>... ou diretamente <NFe>
        nfe_node = root.find('nfe:NFe', ns)
        if nfe_node is None:
            st.error("Estrutura do XML não reconhecida. Não foi possível encontrar a tag <NFe>.")
            return None

        infNFe = nfe_node.find('nfe:infNFe', ns)
        
        # --- Dados do Destinatário (Comprador) ---
        dest = infNFe.find('nfe:dest', ns)
        enderDest = dest.find('nfe:enderDest', ns)
        
        nome_consumidor = dest.find('nfe:xNome', ns).text
        
        # Tenta encontrar o CPF ou CNPJ
        cpf_node = dest.find('nfe:CPF', ns)
        cnpj_node = dest.find('nfe:CNPJ', ns)
        documento_consumidor = cpf_node.text if cpf_node is not None else (cnpj_node.text if cnpj_node is not None else 'Não informado')

        # Monta o endereço completo
        logradouro = enderDest.find('nfe:xLgr', ns).text
        numero = enderDest.find('nfe:nro', ns).text
        bairro = enderDest.find('nfe:xBairro', ns).text
        cidade = enderDest.find('nfe:xMun', ns).text
        uf = enderDest.find('nfe:UF', ns).text
        cep = enderDest.find('nfe:CEP', ns).text
        endereco_completo = f"{logradouro}, {numero} - {bairro}, {cidade}/{uf} - CEP: {cep}"
        
        # O email é opcional no schema da NF-e, então tratamos sua ausência
        email_node = dest.find('nfe:email', ns)
        email_consumidor = email_node.text if email_node is not None else "Não informado"
        
        # O telefone também pode não estar presente
        fone_node = enderDest.find('nfe:fone', ns)
        telefone_consumidor = fone_node.text if fone_node is not None else "Não informado"

        # --- Dados Gerais da Venda ---
        ide = infNFe.find('nfe:ide', ns)
        nNF = ide.find('nfe:nNF', ns).text
        dhEmi = ide.find('nfe:dhEmi', ns).text
        
        total = infNFe.find('nfe:total/nfe:ICMSTot', ns)
        vNF = total.find('nfe:vNF', ns).text
        vProd = total.find('nfe:vProd', ns).text
        vFrete = total.find('nfe:vFrete', ns).text

        # --- Dados dos Produtos/Itens ---
        itens_data = []
        itens = infNFe.findall('nfe:det', ns)
        
        for item in itens:
            prod = item.find('nfe:prod', ns)
            item_data = {
                "NF Nº": nNF,
                "Data Emissão": dhEmi,
                "Nome do Consumidor": nome_consumidor,
                "Documento (CPF/CNPJ)": documento_consumidor,
                "Endereço": endereco_completo,
                "Telefone": telefone_consumidor,
                "Email": email_consumidor,
                "Código Produto": prod.find('nfe:cProd', ns).text,
                "Produto Comprado": prod.find('nfe:xProd', ns).text,
                "Quantidade": float(prod.find('nfe:qCom', ns).text),
                "Valor Unitário": float(prod.find('nfe:vUnCom', ns).text),
                "Valor Total Produtos": float(vProd),
                "Valor Frete": float(vFrete),
                "Valor Total da Nota": float(vNF),
            }
            itens_data.append(item_data)
            
        return pd.DataFrame(itens_data)

    except Exception as e:
        st.error(f"Ocorreu um erro ao processar o arquivo XML: {e}")
        return None

def to_excel(df: pd.DataFrame):
    """Converte um DataFrame para um objeto BytesIO em formato Excel."""
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Dados NFe')
    processed_data = output.getvalue()
    return processed_data

# --- Interface da Aplicação Streamlit ---

st.set_page_config(page_title="Extrator de Dados de NF-e", layout="wide")

st.title("📄 Extrator de Dados de Nota Fiscal Eletrônica (NF-e)")
st.write("Faça o upload de um arquivo XML de NF-e para extrair os dados do comprador e da venda.")

uploaded_file = st.file_uploader("Escolha o arquivo XML da NF-e", type=["xml"])

if uploaded_file is not None:
    # Lê o conteúdo do arquivo
    xml_content = uploaded_file.getvalue()
    
    # Extrai os dados
    df_nfe = extrair_dados_nfe(xml_content)
    
    if df_nfe is not None and not df_nfe.empty:
        st.success("Dados extraídos com sucesso!")
        
        # --- Pré-visualização ---
        st.subheader("👁️ Pré-visualização dos Dados")

        # Mostra os dados principais em formato de cartão
        # Pega os dados da primeira linha, já que são os mesmos para todos os itens da nota
        info = df_nfe.iloc[0]
        
        col1, col2 = st.columns(2)
        with col1:
            st.markdown(f"**Consumidor:** `{info['Nome do Consumidor']}`")
            st.markdown(f"**Documento:** `{info['Documento (CPF/CNPJ)']}`")
            st.markdown(f"**Telefone:** `{info['Telefone']}`")
            st.markdown(f"**Email:** `{info['Email']}`")
        
        with col2:
            st.markdown(f"**Endereço:** `{info['Endereço']}`")
            st.markdown(f"**Nota Fiscal Nº:** `{info['NF Nº']}`")
            st.metric(label="Valor Total da Nota", value=f"R$ {info['Valor Total da Nota']:.2f}")

        st.subheader("🛒 Itens da Nota")
        # Mostra a tabela com os produtos
        # Seleciona colunas relevantes para a visualização dos itens
        df_display = df_nfe[[
            "Código Produto", "Produto Comprado", "Quantidade", "Valor Unitário"
        ]].copy()
        df_display["Valor Unitário"] = df_display["Valor Unitário"].apply(lambda x: f"R$ {x:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
        st.dataframe(df_display, use_container_width=True)

        # --- Botão de Download ---
        st.subheader("📥 Download da Planilha")
        st.write("Clique no botão abaixo para baixar todos os dados extraídos em uma planilha Excel.")
        
        excel_data = to_excel(df_nfe)
        
        st.download_button(
            label="⬇️ Baixar Planilha Excel",
            data=excel_data,
            file_name=f"dados_nfe_{info['NF Nº']}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )