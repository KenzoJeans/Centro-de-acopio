import streamlit as st
import pandas as pd
import plotly.express as px
import io
import urllib.request
import urllib.parse
from datetime import datetime

# 1. Configuración de la página
st.set_page_config(page_title="Control de Acopio | SGA", layout="wide", page_icon="♻️")

# Estilos CSS
st.markdown("""
    <style>
    .kpi-card { background-color: #1e2430; border: 1px solid #2d3748; padding: 15px; border-radius: 8px; text-align: center; }
    .kpi-value { font-size: 26px; font-weight: bold; color: #f8fafc; }
    .kpi-label { font-size: 12px; color: #94a3b8; text-transform: uppercase; letter-spacing: 1px;}
    .val-ingreso { color: #38bdf8; } .val-salida { color: #f472b6; } .val-stock { color: #4ade80; }
    .footer { text-align: center; color: #64748b; font-size: 12px; margin-top: 50px; }
    </style>
""", unsafe_allow_html=True)

st.title("📊 Control de Inventario y Centro de Acopio")
st.markdown("Monitor de trazabilidad de entradas y salidas por cuarto de acopio.")

# 2. FUNCIÓN PARA CARGAR Y LIMPIAR DATOS
@st.cache_data(ttl=60)
def cargar_datos_por_hoja(nombre_pestana):
    ID_HOJA = "12JIS1hNlIPypwbQ1SQ4OssQrCMoMhJ57hcr7MHDz1d8"
    nombre_encoded = urllib.parse.quote(nombre_pestana)
    url = f"https://docs.google.com/spreadsheets/d/{ID_HOJA}/gviz/tq?tqx=out:csv&sheet={nombre_encoded}"
    
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req) as response:
            df = pd.read_csv(io.BytesIO(response.read()))
            
        df.columns = df.columns.str.strip()
        
        # Fechas
        cols_fecha = [c for c in df.columns if 'FECHA' in c.upper()]
        if cols_fecha:
            df['FECHA_CLEAN'] = pd.to_datetime(df[cols_fecha[0]], format='%d/%m/%Y', errors='coerce')
            # Intentar formato alternativo si hay nulos (ej. 28-02-2026)
            if df['FECHA_CLEAN'].isnull().any():
                df['FECHA_CLEAN'] = df['FECHA_CLEAN'].fillna(pd.to_datetime(df[cols_fecha[0]], format='%d-%m-%Y', errors='coerce'))
        else:
            df['FECHA_CLEAN'] = pd.NaT

        # Cantidades
        cols_cant = [c for c in df.columns if 'CANTIDAD' in c.upper()]
        df['CANTIDAD_CLEAN'] = pd.to_numeric(df[cols_cant[0]], errors='coerce').fillna(0) if cols_cant else 0

        # Identificar Entradas vs Salidas
        cols_mov = [c for c in df.columns if 'MOVIMIENTO' in c.upper()]
        if cols_mov:
            df['TIPO_MOV_CLEAN'] = df[cols_mov[0]].astype(str).str.upper()
            df['ES_INGRESO'] = df['TIPO_MOV_CLEAN'].apply(lambda x: False if 'SALIDA' in x else True)
        else:
            df['ES_INGRESO'] = True

        # Residuo y Área
        cols_residuo = [c for c in df.columns if 'RESIDUO' in c.upper() or 'MATERIAL' in c.upper()]
        col_res = cols_residuo[0] if cols_residuo else "Residuo"
        
        cols_area = [c for c in df.columns if 'AREA' in c.upper() or 'ÁREA' in c.upper()]
        col_area = cols_area[0] if cols_area else None

        return df, col_res, col_area, None
        
    except Exception as e:
        return pd.DataFrame(), "", "", str(e)

# Cargar datos
df_peligrosos, col_res_pelig, col_area_pelig, err_respel = cargar_datos_por_hoja("Cuarto de respel")
df_aprov, col_res_aprov, col_area_aprov, err_aprov = cargar_datos_por_hoja("Cuarto de residuos aprovechables")

# 3. BARRA LATERAL (SIDEBAR) - FILTROS DE FECHA
st.sidebar.header("⚙️ Filtros Globales")
st.sidebar.markdown("Selecciona el rango de tiempo a consultar:")

# Obtener fechas de forma segura
fechas_disponibles = []
if not df_peligrosos.empty and 'FECHA_CLEAN' in df_peligrosos.columns:
    fechas_disponibles.append(df_peligrosos['FECHA_CLEAN'])
if not df_aprov.empty and 'FECHA_CLEAN' in df_aprov.columns:
    fechas_disponibles.append(df_aprov['FECHA_CLEAN'])

if fechas_disponibles:
    todas_las_fechas = pd.concat(fechas_disponibles).dropna()
    if not todas_las_fechas.empty:
        min_date = todas_las_fechas.min().date()
        max_date = todas_las_fechas.max().date()
    else:
        min_date, max_date = datetime.today().date(), datetime.today().date()
else:
    min_date, max_date = datetime.today().date(), datetime.today().date()

fecha_rango = st.sidebar.date_input("Rango de Fechas", [min_date, max_date], min_value=min_date, max_value=max_date)

# Aplicar filtro de fechas a los DataFrames
if len(fecha_rango) == 2:
    start_date, end_date = fecha_rango
    if not df_peligrosos.empty and 'FECHA_CLEAN' in df_peligrosos.columns:
        mask_pelig = (df_peligrosos['FECHA_CLEAN'].dt.date >= start_date) & (df_peligrosos['FECHA_CLEAN'].dt.date <= end_date)
        df_peligrosos = df_peligrosos.loc[mask_pelig]
    
    if not df_aprov.empty and 'FECHA_CLEAN' in df_aprov.columns:
        mask_aprov = (df_aprov['FECHA_CLEAN'].dt.date >= start_date) & (df_aprov['FECHA_CLEAN'].dt.date <= end_date)
        df_aprov = df_aprov.loc[mask_aprov]

st.sidebar.markdown("---")
st.sidebar.info("💡 **Tip:** Usa el filtro superior para evaluar los certificados de disposición y aprovechamiento en un trimestre o semestre específico.")

# 4. FUNCIÓN PARA CÁLCULO DE INVENTARIO (Solo para RESPEL ahora)
def calcular_inventario(df, col_residuo):
    if df.empty:
        return 0, 0, 0, pd.DataFrame(), pd.DataFrame()
    
    df_ingresos = df[df['ES_INGRESO'] == True]
    df_salidas = df[df['ES_INGRESO'] == False]
    
    total_generado = df_ingresos['CANTIDAD_CLEAN'].sum() if not df_ingresos.empty else 0
    total_salidas = df_salidas['CANTIDAD_CLEAN'].sum() if not df_salidas.empty else 0
    stock_actual = total_generado - total_salidas
    
    if not df_ingresos.empty:
        ingresos_por_res = df_ingresos.groupby(col_residuo)['CANTIDAD_CLEAN'].sum().reset_index().rename(columns={'CANTIDAD_CLEAN': 'Ingresos'})
    else:
        ingresos_por_res = pd.DataFrame(columns=[col_residuo, 'Ingresos'])
        
    if not df_salidas.empty:
        salidas_por_res = df_salidas.groupby(col_residuo)['CANTIDAD_CLEAN'].sum().reset_index().rename(columns={'CANTIDAD_CLEAN': 'Salidas'})
    else:
        salidas_por_res = pd.DataFrame(columns=[col_residuo, 'Salidas'])
    
    if not ingresos_por_res.empty or not salidas_por_res.empty:
        stock_df = pd.merge(ingresos_por_res, salidas_por_res, on=col_residuo, how='outer').fillna(0)
        stock_df['Stock Actual'] = stock_df['Ingresos'] - stock_df['Salidas']
        stock_df = stock_df.sort_values(by='Stock Actual', ascending=True)
    else:
        stock_df = pd.DataFrame()
    
    return total_generado, total_salidas, stock_actual, stock_df, df_ingresos

# 5. INTERFAZ DE PESTAÑAS (TABS)
tab_aprov, tab_pelig = st.tabs(["♻️ Aprovechables Certificados", "☢️ Peligrosos (RESPEL)"])

# --- PESTAÑA 1: APROVECHABLES (MODIFICADA PARA SALIDAS) ---
with tab_aprov:
    st.subheader("Total de Materiales Aprovechados (Salidas Certificadas)")
    if err_aprov: st.error(err_aprov)
    elif df_aprov.empty: st.info("No hay registros en el rango de fechas seleccionado.")
    else:
        total_aprovechado = df_aprov['CANTIDAD_CLEAN'].sum()
        entregas_certificadas = len(df_aprov)
        materiales_unicos = df_aprov[col_res_aprov].nunique() if col_res_aprov in df_aprov.columns else 0
        
        c1, c2, c3 = st.columns(3)
        c1.markdown(f"<div class='kpi-card'><div style='border-bottom: 3px solid #4ade80;'><div class='kpi-label'>Total Recuperado</div><div class='kpi-value val-stock'>{total_aprovechado:,.1f} KG</div></div></div>", unsafe_allow_html=True)
        c2.markdown(f"<div class='kpi-card'><div class='kpi-label'>Tipos de Materiales</div><div class='kpi-value' style='color:#38bdf8;'>{materiales_unicos}</div></div>", unsafe_allow_html=True)
        c3.markdown(f"<div class='kpi-card'><div class='kpi-label'>Registros de Salida</div><div class='kpi-value' style='color:#f8fafc;'>{entregas_certificadas}</div></div>", unsafe_allow_html=True)
        st.write("---")
        
        if col_res_aprov in df_aprov.columns:
            resumen_aprov = df_aprov.groupby(col_res_aprov)['CANTIDAD_CLEAN'].sum().reset_index()
            resumen_aprov = resumen_aprov.sort_values(by='CANTIDAD_CLEAN', ascending=True)
            
            fig_aprov = px.bar(
                resumen_aprov, 
                x='CANTIDAD_CLEAN', 
                y=col_res_aprov, 
                orientation='h', 
                title="<b>Volumen Histórico por Tipo de Material Aprovechado (KG)</b>", 
                labels={'CANTIDAD_CLEAN': 'Cantidad Certificada (KG)', col_res_aprov: 'Material'},
                template="plotly_dark", 
                color='CANTIDAD_CLEAN',
                color_continuous_scale='Greens'
            )
            fig_aprov.update_layout(showlegend=False, height=450)
            st.plotly_chart(fig_aprov, use_container_width=True)
                
        st.dataframe(df_aprov.drop(columns=['CANTIDAD_CLEAN', 'FECHA_CLEAN', 'TIPO_MOV_CLEAN', 'ES_INGRESO'], errors='ignore'), use_container_width=True)

# --- PESTAÑA 2: PELIGROSOS (SE MANTIENE INVENTARIO) ---
with tab_pelig:
    st.subheader("Auditoría y Control de Sustancias Peligrosas (RESPEL)")
    if err_respel: st.error(err_respel)
    elif df_peligrosos.empty: st.info("No hay registros en el rango de fechas seleccionado.")
    else:
        generado_p, salidas_p, stock_p, stock_df_p, df_ingresos_pelig = calcular_inventario(df_peligrosos, col_res_pelig)
        
        c1, c2, c3 = st.columns(3)
        c1.markdown(f"<div class='kpi-card'><div class='kpi-label'>Generación Histórica</div><div class='kpi-value val-ingreso'>{generado_p:,.1f} KG</div></div>", unsafe_allow_html=True)
        c2.markdown(f"<div class='kpi-card'><div class='kpi-label'>Salidas con Manifiesto</div><div class='kpi-value val-salida'>{salidas_p:,.1f} KG</div></div>", unsafe_allow_html=True)
        c3.markdown(f"<div class='kpi-card'><div style='border-bottom: 3px solid #ef4444;'><div class='kpi-label'>Stock Actual en Cuarto</div><div class='kpi-value' style='color:#ef4444;'>{stock_p:,.1f} KG</div></div></div>", unsafe_allow_html=True)
        st.write("---")
        
        if not stock_df_p.empty:
            fig_respel = px.bar(stock_df_p, x='Stock Actual', y=col_res_pelig, orientation='h', title="<b>Inventario Físico Actual de RESPEL (KG)</b>", template="plotly_dark", color_discrete_sequence=['#ef4444'])
            st.plotly_chart(fig_respel, use_container_width=True)
            
        if not df_ingresos_pelig.empty and col_area_pelig and col_area_pelig in df_ingresos_pelig.columns:
            gen_area_p = df_ingresos_pelig.groupby(col_area_pelig)['CANTIDAD_CLEAN'].sum().reset_index().sort_values(by='CANTIDAD_CLEAN', ascending=False)
            gen_area_p['PORCENTAJE'] = (gen_area_p['CANTIDAD_CLEAN'] / generado_p * 100).round(1) if generado_p > 0 else 0
            fig_area_p = px.bar(gen_area_p, x=col_area_pelig, y='CANTIDAD_CLEAN', text='PORCENTAJE', title="<b>Participación de Generación de RESPEL por Área</b>", template="plotly_dark", color_discrete_sequence=['#f59e0b'])
            fig_area_p.update_traces(texttemplate='%{text}%', textposition='outside')
            st.plotly_chart(fig_area_p, use_container_width=True)

st.markdown("<div class='footer'>SGA v2.0 · Kenzo Jeans SAS</div>", unsafe_allow_html=True)
