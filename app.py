import streamlit as st
import pandas as pd
import plotly.express as px
import io
import urllib.request
import urllib.parse

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
st.markdown("Monitor de trazabilidad de entradas y salidas por cuarto de acopio.")

# 2. FUNCIÓN PARA CARGAR PESTAÑAS ESPECÍFICAS DE GOOGLE SHEETS
def cargar_datos_por_hoja(nombre_pestana):
    ID_HOJA = "12JIS1hNlIPypwbQ1SQ4OssQrCMoMhJ57hcr7MHDz1d8"
    # Codificar el nombre de la pestaña para la URL
    nombre_encoded = urllib.parse.quote(nombre_pestana)
    url = f"https://docs.google.com/spreadsheets/d/{ID_HOJA}/gviz/tq?tqx=out:csv&sheet={nombre_encoded}"
    
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req) as response:
            csv_data = response.read()
            
        df = pd.read_csv(io.BytesIO(csv_data))
        df.columns = df.columns.str.strip()
        
        # Limpieza de fechas
        cols_fecha = [c for c in df.columns if 'FECHA' in c.upper()]
        if cols_fecha:
            df['FECHA_CLEAN'] = pd.to_datetime(df[cols_fecha[0]], errors='coerce')
        else:
            df['FECHA_CLEAN'] = pd.NaT

        # Limpieza de cantidades
        cols_cant = [c for c in df.columns if 'CANTIDAD' in c.upper()]
        if cols_cant:
            df['CANTIDAD_CLEAN'] = pd.to_numeric(df[cols_cant[0]], errors='coerce').fillna(0)
        else:
            df['CANTIDAD_CLEAN'] = 0

        # Columna de residuo / material
        cols_residuo = [c for c in df.columns if 'RESIDUO' in c.upper() or 'MATERIAL' in c.upper()]
        col_nombre_residuo = cols_residuo[0] if cols_residuo else (df.columns[0] if not df.empty else "")
        
        return df, col_nombre_residuo, None
        
    except Exception as e:
        return pd.DataFrame(), "", str(e)

# Carga independiente de cada hoja
df_peligrosos, col_respel, err_respel = cargar_datos_por_hoja("Cuarto de respel")
df_aprovechables, col_aprov, err_aprov = cargar_datos_por_hoja("Cuarto de residuos aprovechables")

# 3. INTERFAZ DE PESTAÑAS (TABS)
tab_aprov, tab_pelig = st.tabs(["♻️ Residuos Aprovechables", "☢️ Residuos Peligrosos (RESPEL)"])

# ------------------------------------------
# PESTAÑA 1: APROVECHABLES (ALIMENTACIÓN MANUAL)
# ------------------------------------------
with tab_aprov:
    st.subheader("Gestión de Materiales Reciclables / Aprovechables")
    if err_aprov:
        st.error(f"⚠️ Error al conectar con la pestaña 'Cuarto de residuos aprovechables': `{err_aprov}`")
    elif df_aprovechables.empty:
        st.info("ℹ️ La pestaña 'Cuarto de residuos aprovechables' está lista para recibir datos manuales.")
    else:
        col1, col2, col3 = st.columns(3)
        with col1:
            total_kg_aprov = df_aprovechables['CANTIDAD_CLEAN'].sum()
            st.markdown(f"<div class='kpi-card'><div class='kpi-label'>Total Acopiado</div><div class='kpi-value'>{total_kg_aprov:,.1f} KG</div></div>", unsafe_allow_html=True)
        with col2:
            movimientos_aprov = len(df_aprovechables)
            st.markdown(f"<div class='kpi-card'><div class='kpi-label'>Movimientos Registrados</div><div class='kpi-value'>{movimientos_aprov}</div></div>", unsafe_allow_html=True)
        with col3:
            st.markdown(f"<div class='kpi-card'><div class='kpi-label'>Estado de Ruta</div><div class='kpi-value' style='color:#4ade80;'>Óptimo</div></div>", unsafe_allow_html=True)
            
        st.write("---")
        
        col_graf1, col_graf2 = st.columns(2)
        with col_graf1:
            if col_aprov in df_aprovechables.columns:
                fig1 = px.pie(df_aprovechables, values='CANTIDAD_CLEAN', names=col_aprov, 
                              title="Distribución por Tipo de Material", template="plotly_dark", hole=0.4)
                st.plotly_chart(fig1, use_container_width=True)
                
        with col_graf2:
            cols_area = [c for c in df_aprovechables.columns if 'AREA' in c.upper() or 'ÁREA' in c.upper()]
            if cols_area:
                fig2 = px.bar(df_aprovechables.groupby(cols_area[0])['CANTIDAD_CLEAN'].sum().reset_index(), 
                              x=cols_area[0], y='CANTIDAD_CLEAN', title="Generación por Área", 
                              template="plotly_dark", color_discrete_sequence=['#4ade80'])
                st.plotly_chart(fig2, use_container_width=True)
                
        st.dataframe(df_aprovechables.drop(columns=['CANTIDAD_CLEAN', 'FECHA_CLEAN'], errors='ignore'), use_container_width=True)

# ------------------------------------------
# PESTAÑA 2: PELIGROSOS (RESPEL - GOOGLE FORM)
# ------------------------------------------
with tab_pelig:
    st.subheader("Auditoría y Control de Sustancias Peligrosas (RESPEL)")
    if err_respel:
        st.error(f"⚠️ Error al conectar con la pestaña 'Cuarto de respel': `{err_respel}`")
    elif df_peligrosos.empty:
        st.info("ℹ️ Esperando datos en la pestaña 'Cuarto de respel'...")
    else:
        col1, col2, col3 = st.columns(3)
        with col1:
            total_kg_pelig = df_peligrosos['CANTIDAD_CLEAN'].sum()
            st.markdown(f"<div class='kpi-card'><div style='border-left: 4px solid #ef4444;'><div class='kpi-label'>Masa Total (RESPEL)</div><div class='kpi-value'>{total_kg_pelig:,.1f} KG</div></div></div>", unsafe_allow_html=True)
        with col2:
            cols_area = [c for c in df_peligrosos.columns if 'AREA' in c.upper() or 'ÁREA' in c.upper()]
            areas_cnt = df_peligrosos[cols_area[0]].nunique() if cols_area else 0
            st.markdown(f"<div class='kpi-card'><div style='border-left: 4px solid #f59e0b;'><div class='kpi-label'>Áreas Críticas Generadoras</div><div class='kpi-value'>{areas_cnt}</div></div></div>", unsafe_allow_html=True)
        with col3:
            st.markdown(f"<div class='kpi-card'><div style='border-left: 4px solid #3b82f6;'><div class='kpi-label'>Estado Matriz Legal</div><div class='kpi-value' style='color:#3b82f6;'>Vigente</div></div></div>", unsafe_allow_html=True)

        st.write("---")
        
        col_graf1, col_graf2 = st.columns(2)
        with col_graf1:
            if col_respel in df_peligrosos.columns:
                fig_respel_pie = px.pie(df_peligrosos, values='CANTIDAD_CLEAN', names=col_respel, 
                                        title="Distribución de Residuos Peligrosos", template="plotly_dark", hole=0.4)
                st.plotly_chart(fig_respel_pie, use_container_width=True)

        with col_graf2:
            if 'FECHA_CLEAN' in df_peligrosos.columns and not df_peligrosos['FECHA_CLEAN'].dropna().empty:
                ingresos_tiempo = df_peligrosos.groupby('FECHA_CLEAN')['CANTIDAD_CLEAN'].sum().reset_index()
                fig3 = px.line(ingresos_tiempo, x='FECHA_CLEAN', y='CANTIDAD_CLEAN', 
                               title="Tendencia de Ingreso al Cuarto de RESPEL", markers=True, template="plotly_dark", 
                               color_discrete_sequence=['#ef4444'])
                st.plotly_chart(fig3, use_container_width=True)
            
        st.dataframe(df_peligrosos.drop(columns=['CANTIDAD_CLEAN', 'FECHA_CLEAN'], errors='ignore'), use_container_width=True)
        st.warning("⚠️ **Análisis de Vulnerabilidad:** Verifique que los residuos peligrosos mantengan su etiquetado estandarizado y el código QR visible para la hoja de seguridad.")

st.markdown("<div class='footer'>SGA v2.0 · Kenzo Jeans SAS</div>", unsafe_allow_html=True)
