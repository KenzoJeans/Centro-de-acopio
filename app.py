import streamlit as st
import pandas as pd
import plotly.express as px

# 1. Configuración de la página
st.set_page_config(page_title="Control de Acopio | SGA", layout="wide", page_icon="♻️")

# Estilos CSS personalizados
st.markdown("""
    <style>
    .kpi-card {
        background-color: #1e2430; border: 1px solid #2d3748;
        padding: 20px; border-radius: 10px; text-align: center;
    }
    .kpi-value { font-size: 28px; font-weight: bold; color: #38bdf8; }
    .kpi-label { font-size: 14px; color: #94a3b8; text-transform: uppercase; letter-spacing: 1px;}
    .footer { text-align: center; color: #64748b; font-size: 12px; margin-top: 50px; }
    </style>
""", unsafe_allow_html=True)

st.title("📊 Control de Ingreso de Residuos al Centro de Acopio")
st.markdown("Monitor de trazabilidad de entradas y salidas dividido por clasificación de manejo.")

# 2. CARGA Y PREPARACIÓN DE DATOS (CONEXIÓN GOOGLE SHEETS)
@st.cache_data(ttl=30)
def cargar_datos():
    ID_HOJA = "12JIS1hNlIPypwbQ1SQ4OssQrCMoMhJ57hcr7MHDz1d8"
    url = f"https://docs.google.com/spreadsheets/d/{ID_HOJA}/export?format=csv"
    
    try:
        df = pd.read_csv(url)
        df.columns = df.columns.str.strip()
        
        # Limpieza y conversión de datos
        col_fecha = [c for c in df.columns if 'FECHA' in c.upper()]
        if col_fecha:
            df['FECHA_CLEAN'] = pd.to_datetime(df[col_fecha[0]], errors='coerce')
        
        col_cant = [c for c in df.columns if 'CANTIDAD' in c.upper()]
        if col_cant:
            df['CANTIDAD_CLEAN'] = pd.to_numeric(df[col_cant[0]], errors='coerce').fillna(0)
        else:
            df['CANTIDAD_CLEAN'] = 0

        col_residuo = [c for c in df.columns if 'RESIDUO' in c.upper()]
        nombre_col_residuo = col_residuo[0] if col_residuo else df.columns[0]
        
        # Clasificador automático de residuos
        def clasificar_residuo(nombre):
            peligrosos_keywords = ['BATERIA', 'ENVASE CONTAMINADO', 'ACEITE', 'QUIMICO', 'TINTA', 'LUMINARIA', 'WIPE', 'TÓNER', 'BATERIAS']
            nombre_upper = str(nombre).upper()
            if any(keyword in nombre_upper for keyword in peligrosos_keywords):
                return 'Peligroso'
            return 'Aprovechable'
        
        df['CATEGORIA'] = df[nombre_col_residuo].apply(clasificar_residuo)
        return df, nombre_col_residuo
        
    except Exception as e:
        st.error(f"⚠️ Error conectando con Google Sheets: {e}")
        return pd.DataFrame(), ""

df, col_nombre_residuo = cargar_datos()

if not df.empty:
    # Separar DataFrames por categoría
    df_aprovechables = df[df['CATEGORIA'] == 'Aprovechable']
    df_peligrosos = df[df['CATEGORIA'] == 'Peligroso']

    # 3. INTERFAZ DE PESTAÑAS (TABS)
    tab_aprov, tab_pelig = st.tabs(["♻️ Residuos Aprovechables", "☢️ Residuos Peligrosos (RESPEL)"])

    # ------------------------------------------
    # PESTAÑA 1: APROVECHABLES
    # ------------------------------------------
    with tab_aprov:
        st.subheader("Gestión de Materiales Reciclables")
        
        col1, col2, col3 = st.columns(3)
        with col1:
            total_kg_aprov = df_aprovechables['CANTIDAD_CLEAN'].sum()
            st.markdown(f"<div class='kpi-card'><div class='kpi-label'>Total Acopiado</div><div class='kpi-value'>{total_kg_aprov:,.1f} KG</div></div>", unsafe_allow_html=True)
        with col2:
            movimientos_aprov = len(df_aprovechables)
            st.markdown(f"<div class='kpi-card'><div class='kpi-label'>Ingresos Registrados</div><div class='kpi-value'>{movimientos_aprov}</div></div>", unsafe_allow_html=True)
        with col3:
            st.markdown(f"<div class='kpi-card'><div class='kpi-label'>Estado de Ruta</div><div class='kpi-value' style='color:#4ade80;'>Óptimo</div></div>", unsafe_allow_html=True)
            
        st.write("---")
        
        col_graf1, col_graf2 = st.columns(2)
        with col_graf1:
            if not df_aprovechables.empty:
                fig1 = px.pie(df_aprovechables, values='CANTIDAD_CLEAN', names=col_nombre_residuo, 
                              title="Distribución de Materiales", template="plotly_dark", hole=0.4)
                st.plotly_chart(fig1, use_container_width=True)
                
        with col_graf2:
            col_area = [c for c in df.columns if 'AREA' in c.upper() or 'ÁREA' in c.upper()]
            if col_area and not df_aprovechables.empty:
                fig2 = px.bar(df_aprovechables.groupby(col_area[0])['CANTIDAD_CLEAN'].sum().reset_index(), 
                              x=col_area[0], y='CANTIDAD_CLEAN', title="Generación por Área", 
                              template="plotly_dark", color_discrete_sequence=['#4ade80'])
                st.plotly_chart(fig2, use_container_width=True)
                
        st.dataframe(df_aprovechables.drop(columns=['CATEGORIA', 'CANTIDAD_CLEAN', 'FECHA_CLEAN'], errors='ignore'), use_container_width=True)

    # ------------------------------------------
    # PESTAÑA 2: PELIGROSOS (RESPEL)
    # ------------------------------------------
    with tab_pelig:
        st.subheader("Auditoría y Control de Sustancias Peligrosas")
        
        col1, col2, col3 = st.columns(3)
        with col1:
            total_kg_pelig = df_peligrosos['CANTIDAD_CLEAN'].sum()
            st.markdown(f"<div class='kpi-card'><div style='border-left: 4px solid #ef4444;'><div class='kpi-label'>Masa Total (RESPEL)</div><div class='kpi-value'>{total_kg_pelig:,.1f} KG</div></div></div>", unsafe_allow_html=True)
        with col2:
            col_area = [c for c in df.columns if 'AREA' in c.upper() or 'ÁREA' in c.upper()]
            areas_cnt = df_peligrosos[col_area[0]].nunique() if col_area else 0
            st.markdown(f"<div class='kpi-card'><div style='border-left: 4px solid #f59e0b;'><div class='kpi-label'>Áreas Críticas Generadoras</div><div class='kpi-value'>{areas_cnt}</div></div></div>", unsafe_allow_html=True)
        with col3:
            st.markdown(f"<div class='kpi-card'><div style='border-left: 4px solid #3b82f6;'><div class='kpi-label'>Estado Matriz Legal</div><div class='kpi-value' style='color:#3b82f6;'>Vigente</div></div></div>", unsafe_allow_html=True)

        st.write("---")
        
        if not df_peligrosos.empty and 'FECHA_CLEAN' in df_peligrosos.columns:
            ingresos_tiempo = df_peligrosos.groupby('FECHA_CLEAN')['CANTIDAD_CLEAN'].sum().reset_index()
            fig3 = px.line(ingresos_tiempo, x='FECHA_CLEAN', y='CANTIDAD_CLEAN', 
                           title="Tendencia de Ingreso al Cuarto de Acopio", markers=True, template="plotly_dark", 
                           color_discrete_sequence=['#ef4444'])
            st.plotly_chart(fig3, use_container_width=True)
            
        st.dataframe(df_peligrosos.drop(columns=['CATEGORIA', 'CANTIDAD_CLEAN', 'FECHA_CLEAN'], errors='ignore'), use_container_width=True)
        st.warning("⚠️ **Análisis de Vulnerabilidad:** Verifique que los residuos peligrosos mantengan su etiquetado estandarizado y el código QR visible para la hoja de seguridad.")

else:
    st.info("Cargando datos o esperando nuevos registros en la hoja de Google Sheets...")

st.markdown("<div class='footer'>SGA v2.0 · Kenzo Jeans SAS</div>", unsafe_allow_html=True)
