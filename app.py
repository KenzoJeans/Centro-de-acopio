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
        
        # Gráficos en ancho completo
        if col_aprov in df_aprovechables.columns:
            resumen_aprov = df_aprovechables.groupby(col_aprov)['CANTIDAD_CLEAN'].sum().reset_index()
            resumen_aprov = resumen_aprov.sort_values(by='CANTIDAD_CLEAN', ascending=True)
            
            fig_aprov = px.bar(
                resumen_aprov, 
                x='CANTIDAD_CLEAN', 
                y=col_aprov, 
                orientation='h',
                title="<b>Masa Total por Tipo de Material Aprovechable (KG)</b>",
                labels={'CANTIDAD_CLEAN': 'Cantidad Acopiada (KG)', col_aprov: 'Material'},
                template="plotly_dark",
                color='CANTIDAD_CLEAN',
                color_continuous_scale='Greens'
            )
            fig_aprov.update_layout(showlegend=False, height=400)
            st.plotly_chart(fig_aprov, use_container_width=True)
            
        cols_area_aprov = [c for c in df_aprovechables.columns if 'AREA' in c.upper() or 'ÁREA' in c.upper()]
        if cols_area_aprov:
            area_aprov = df_aprovechables.groupby(cols_area_aprov[0])['CANTIDAD_CLEAN'].sum().reset_index()
            area_aprov = area_aprov.sort_values(by='CANTIDAD_CLEAN', ascending=False)
            
            fig_area_aprov = px.bar(
                area_aprov,
                x=cols_area_aprov[0],
                y='CANTIDAD_CLEAN',
                title="<b>Generación de Aprovechables por Área</b>",
                labels={'CANTIDAD_CLEAN': 'Total Generado (KG)', cols_area_aprov[0]: 'Área Generadora'},
                template="plotly_dark",
                color_discrete_sequence=['#4ade80']
            )
            fig_area_aprov.update_layout(height=400)
            st.plotly_chart(fig_area_aprov, use_container_width=True)
                
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
        cols_area = [c for c in df_peligrosos.columns if 'AREA' in c.upper() or 'ÁREA' in c.upper()]
        
        col1, col2, col3 = st.columns(3)
        with col1:
            total_kg_pelig = df_peligrosos['CANTIDAD_CLEAN'].sum()
            st.markdown(f"<div class='kpi-card'><div style='border-left: 4px solid #ef4444;'><div class='kpi-label'>Masa Total (RESPEL)</div><div class='kpi-value'>{total_kg_pelig:,.1f} KG</div></div></div>", unsafe_allow_html=True)
        with col2:
            areas_cnt = df_peligrosos[cols_area[0]].nunique() if cols_area else 0
            st.markdown(f"<div class='kpi-card'><div style='border-left: 4px solid #f59e0b;'><div class='kpi-label'>Áreas Críticas Generadoras</div><div class='kpi-value'>{areas_cnt}</div></div></div>", unsafe_allow_html=True)
        with col3:
            st.markdown(f"<div class='kpi-card'><div style='border-left: 4px solid #3b82f6;'><div class='kpi-label'>Estado Matriz Legal</div><div class='kpi-value' style='color:#3b82f6;'>Vigente</div></div></div>", unsafe_allow_html=True)

        st.write("---")
        
        # 1. Gráfico de Barras Horizontales para Tipos de RESPEL (Ancho Completo)
        if col_respel in df_peligrosos.columns:
            resumen_respel = df_peligrosos.groupby(col_respel)['CANTIDAD_CLEAN'].sum().reset_index()
            resumen_respel = resumen_respel.sort_values(by='CANTIDAD_CLEAN', ascending=True)
            
            fig_respel_bar = px.bar(
                resumen_respel, 
                x='CANTIDAD_CLEAN', 
                y=col_respel, 
                orientation='h',
                title="<b>Distribución Total por Tipo de Residuo Peligroso (KG)</b>",
                labels={'CANTIDAD_CLEAN': 'Cantidad Acopiada (KG)', col_respel: 'Tipo de Residuo'},
                template="plotly_dark",
                color='CANTIDAD_CLEAN',
                color_continuous_scale='Reds'
            )
            fig_respel_bar.update_layout(showlegend=False, height=450)
            st.plotly_chart(fig_respel_bar, use_container_width=True)

        st.write("---")

        # 2. Gráfico por Áreas Generadoras (Participación % y KG)
        if cols_area:
            area_respel = df_peligrosos.groupby(cols_area[0])['CANTIDAD_CLEAN'].sum().reset_index()
            total_gen = area_respel['CANTIDAD_CLEAN'].sum()
            area_respel['PORCENTAJE'] = (area_respel['CANTIDAD_CLEAN'] / total_gen * 100).round(1) if total_gen > 0 else 0
            area_respel = area_respel.sort_values(by='CANTIDAD_CLEAN', ascending=False)

            fig_area = px.bar(
                area_respel,
                x=cols_area[0],
                y='CANTIDAD_CLEAN',
                text='PORCENTAJE',
                title="<b>Participación de Generación por Área Generadora (KG y %)</b>",
                labels={'CANTIDAD_CLEAN': 'Total Generado (KG)', cols_area[0]: 'Área / Sección', 'PORCENTAJE': '% Generación'},
                template="plotly_dark",
                color_discrete_sequence=['#f59e0b']
            )
            fig_area.update_traces(texttemplate='%{text}%', textposition='outside')
            fig_area.update_layout(height=450)
            st.plotly_chart(fig_area, use_container_width=True)
            
        st.dataframe(df_peligrosos.drop(columns=['CANTIDAD_CLEAN', 'FECHA_CLEAN'], errors='ignore'), use_container_width=True)
        st.warning("⚠️ **Análisis de Vulnerabilidad:** Verifique que los residuos peligrosos mantengan su etiquetado estandarizado y el código QR visible para la hoja de seguridad.")

st.markdown("<div class='footer'>SGA v2.0 · Kenzo Jeans SAS</div>", unsafe_allow_html=True)
