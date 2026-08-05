import streamlit as st
import pandas as pd
import plotly.express as px
import io
import urllib.request
import urllib.parse
from datetime import datetime, timedelta

# 1. Configuración de la página
st.set_page_config(page_title="Control de Acopio | SGA", layout="wide", page_icon="♻️")

# Estilos CSS
st.markdown("""
    <style>
    .kpi-card { background-color: #1e2430; border: 1px solid #2d3748; padding: 15px; border-radius: 8px; text-align: center; }
    .kpi-value { font-size: 26px; font-weight: bold; color: #f8fafc; }
    .kpi-label { font-size: 12px; color: #94a3b8; text-transform: uppercase; letter-spacing: 1px;}
    .val-ingreso { color: #38bdf8; } .val-salida { color: #f472b6; } .val-stock { color: #4ade80; }
    .val-alerta { color: #ef4444; }
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

# Cargar datos (sin filtrar aún — se guarda una copia completa para calcular antigüedad de stock)
df_peligrosos_full, col_res_pelig, col_area_pelig, err_respel = cargar_datos_por_hoja("Cuarto de respel")
df_aprov_full, col_res_aprov, col_area_aprov, err_aprov = cargar_datos_por_hoja("Cuarto de residuos aprovechables")

# 3. BARRA LATERAL (SIDEBAR) - FILTROS DE FECHA
st.sidebar.header("⚙️ Filtros Globales")
st.sidebar.markdown("Selecciona el rango de tiempo a consultar:")

hoy = datetime.today().date()

# Obtener fechas reales de los datos (para el valor por defecto del widget)
fechas_disponibles = []
if not df_peligrosos_full.empty and 'FECHA_CLEAN' in df_peligrosos_full.columns:
    fechas_disponibles.append(df_peligrosos_full['FECHA_CLEAN'])
if not df_aprov_full.empty and 'FECHA_CLEAN' in df_aprov_full.columns:
    fechas_disponibles.append(df_aprov_full['FECHA_CLEAN'])

if fechas_disponibles:
    todas_las_fechas = pd.concat(fechas_disponibles).dropna()
    if not todas_las_fechas.empty:
        min_date_datos = todas_las_fechas.min().date()
        max_date_datos = todas_las_fechas.max().date()
    else:
        min_date_datos, max_date_datos = hoy, hoy
else:
    min_date_datos, max_date_datos = hoy, hoy

# --- CORRECCIÓN CLAVE ---
# Antes: min_value/max_value quedaban atados a los datos, así que el calendario
# no dejaba elegir periodos sin registros (ej. meses futuros o anteriores al primer dato).
# Ahora el rango seleccionable es más amplio; el valor por defecto sigue siendo el rango real de los datos.
min_selec = min(min_date_datos, datetime(2020, 1, 1).date())
max_selec = max(max_date_datos, hoy) + timedelta(days=365)

fecha_rango = st.sidebar.date_input(
    "Rango de Fechas",
    value=[min_date_datos, max_date_datos],
    min_value=min_selec,
    max_value=max_selec
)

st.sidebar.markdown("---")
umbral_alerta_dias = st.sidebar.number_input(
    "Umbral de alerta de almacenamiento RESPEL (días)",
    min_value=1, value=180, step=1,
    help="Se usará para resaltar en rojo el material más antiguo aún almacenado en el cuarto de RESPEL. Ajusta este valor según la normativa/política aplicable."
)
st.sidebar.info("💡 **Tip:** Usa el filtro superior para evaluar los certificados de disposición y aprovechamiento en un trimestre o semestre específico.")

# Aplicar filtro de fechas — solo si el usuario ya seleccionó un rango completo (2 fechas)
df_peligrosos, df_aprov = df_peligrosos_full.copy(), df_aprov_full.copy()
if len(fecha_rango) == 2:
    start_date, end_date = fecha_rango
    if not df_peligrosos.empty and 'FECHA_CLEAN' in df_peligrosos.columns:
        mask_pelig = (df_peligrosos['FECHA_CLEAN'].dt.date >= start_date) & (df_peligrosos['FECHA_CLEAN'].dt.date <= end_date)
        df_peligrosos = df_peligrosos.loc[mask_pelig]

    if not df_aprov.empty and 'FECHA_CLEAN' in df_aprov.columns:
        mask_aprov = (df_aprov['FECHA_CLEAN'].dt.date >= start_date) & (df_aprov['FECHA_CLEAN'].dt.date <= end_date)
        df_aprov = df_aprov.loc[mask_aprov]
else:
    st.sidebar.warning("⏳ Selecciona una fecha de inicio y una de fin para aplicar el filtro.")

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

# Nueva función: antigüedad aproximada del stock en cuarto (usa TODO el historial, no el filtro de fecha)
def calcular_antiguedad_stock(df_full):
    if df_full.empty or 'FECHA_CLEAN' not in df_full.columns:
        return None
    ingresos = df_full[df_full['ES_INGRESO'] == True].dropna(subset=['FECHA_CLEAN'])
    if ingresos.empty:
        return None
    # Aproximación: si aún hay stock positivo, se asume que el ingreso más antiguo
    # es el que sigue pendiente de disposición final.
    return ingresos['FECHA_CLEAN'].min().date()

# 5. INTERFAZ DE PESTAÑAS (TABS)
tab_aprov, tab_pelig = st.tabs(["♻️ Aprovechables Certificados", "☢️ Peligrosos (RESPEL)"])

# --- PESTAÑA 1: APROVECHABLES ---
with tab_aprov:
    st.subheader("Total de Materiales Aprovechados (Salidas Certificadas)")
    if err_aprov:
        st.error(err_aprov)
    elif df_aprov.empty:
        st.info("No hay registros en el rango de fechas seleccionado.")
    else:
        total_aprovechado = df_aprov['CANTIDAD_CLEAN'].sum()
        entregas_certificadas = len(df_aprov)
        materiales_unicos = df_aprov[col_res_aprov].nunique() if col_res_aprov in df_aprov.columns else 0

        c1, c2, c3 = st.columns(3)
        c1.markdown(f"<div class='kpi-card'><div style='border-bottom: 3px solid #4ade80;'><div class='kpi-label'>Total Recuperado</div><div class='kpi-value val-stock'>{total_aprovechado:,.1f} KG</div></div></div>", unsafe_allow_html=True)
        c2.markdown(f"<div class='kpi-card'><div class='kpi-label'>Tipos de Materiales</div><div class='kpi-value' style='color:#38bdf8;'>{materiales_unicos}</div></div>", unsafe_allow_html=True)
        c3.markdown(f"<div class='kpi-card'><div class='kpi-label'>Registros de Salida</div><div class='kpi-value' style='color:#f8fafc;'>{entregas_certificadas}</div></div>", unsafe_allow_html=True)
        st.write("---")

        col_izq, col_der = st.columns([2, 1])

        with col_izq:
            if col_res_aprov in df_aprov.columns:
                resumen_aprov = df_aprov.groupby(col_res_aprov)['CANTIDAD_CLEAN'].sum().reset_index()
                resumen_aprov = resumen_aprov.sort_values(by='CANTIDAD_CLEAN', ascending=True)

                fig_aprov = px.bar(
                    resumen_aprov,
                    x='CANTIDAD_CLEAN',
                    y=col_res_aprov,
                    orientation='h',
                    title="<b>Volumen por Tipo de Material Aprovechado (KG)</b>",
                    labels={'CANTIDAD_CLEAN': 'Cantidad Certificada (KG)', col_res_aprov: 'Material'},
                    template="plotly_dark",
                    color='CANTIDAD_CLEAN',
                    color_continuous_scale='Greens'
                )
                fig_aprov.update_layout(showlegend=False, height=420)
                st.plotly_chart(fig_aprov, use_container_width=True)

        with col_der:
            # Nuevo: gráfico de participación (dona) para ver proporciones de un vistazo
            if col_res_aprov in df_aprov.columns:
                fig_dona = px.pie(
                    resumen_aprov, values='CANTIDAD_CLEAN', names=col_res_aprov,
                    title="<b>Participación por Material</b>", template="plotly_dark", hole=0.5
                )
                fig_dona.update_layout(height=420, showlegend=True)
                st.plotly_chart(fig_dona, use_container_width=True)

        # Nuevo: tendencia mensual — antes no existía ninguna vista de evolución en el tiempo
        if 'FECHA_CLEAN' in df_aprov.columns and df_aprov['FECHA_CLEAN'].notna().any():
            tendencia_aprov = (
                df_aprov.dropna(subset=['FECHA_CLEAN'])
                .set_index('FECHA_CLEAN')['CANTIDAD_CLEAN']
                .resample('ME').sum().reset_index()
            )
            fig_tend_aprov = px.line(
                tendencia_aprov, x='FECHA_CLEAN', y='CANTIDAD_CLEAN', markers=True,
                title="<b>Tendencia Mensual de Aprovechamiento (KG)</b>",
                labels={'FECHA_CLEAN': 'Mes', 'CANTIDAD_CLEAN': 'KG Aprovechados'},
                template="plotly_dark"
            )
            fig_tend_aprov.update_traces(line_color='#4ade80')
            st.plotly_chart(fig_tend_aprov, use_container_width=True)

        st.write("---")
        df_mostrar_aprov = df_aprov.drop(columns=['CANTIDAD_CLEAN', 'FECHA_CLEAN', 'TIPO_MOV_CLEAN', 'ES_INGRESO'], errors='ignore')

        # Nuevo: botón de descarga de certificado por registro.
        # Busca una columna con el link al PDF (ej. compartido desde Google Drive).
        cols_cert = [c for c in df_mostrar_aprov.columns if any(k in c.upper() for k in ['CERTIF', 'LINK', 'URL', 'SOPORTE'])]

        if cols_cert:
            col_cert = cols_cert[0]
            st.dataframe(
                df_mostrar_aprov,
                use_container_width=True,
                column_config={
                    col_cert: st.column_config.LinkColumn(
                        "Certificado", display_text="📄 Descargar"
                    )
                }
            )
        else:
            st.dataframe(df_mostrar_aprov, use_container_width=True)
            st.info(
                "ℹ️ Para habilitar la descarga de certificados por registro: sube los PDF a una carpeta de "
                "Google Drive (con acceso 'cualquiera con el enlace puede ver'), y agrega en la hoja de "
                "'Cuarto de residuos aprovechables' una columna llamada por ejemplo **Certificado** con el "
                "link de cada archivo. La app la detectará automáticamente."
            )

        st.download_button(
            "⬇️ Descargar tabla filtrada (CSV)",
            data=df_mostrar_aprov.to_csv(index=False).encode('utf-8-sig'),
            file_name="aprovechables_filtrado.csv",
            mime="text/csv"
        )

# --- PESTAÑA 2: PELIGROSOS (RESPEL) ---
with tab_pelig:
    st.subheader("Auditoría y Control de Sustancias Peligrosas (RESPEL)")
    if err_respel:
        st.error(err_respel)
    elif df_peligrosos.empty:
        st.info("No hay registros en el rango de fechas seleccionado.")
    else:
        generado_p, salidas_p, stock_p, stock_df_p, df_ingresos_pelig = calcular_inventario(df_peligrosos, col_res_pelig)

        c1, c2, c3, c4 = st.columns(4)
        c1.markdown(f"<div class='kpi-card'><div class='kpi-label'>Generación Histórica</div><div class='kpi-value val-ingreso'>{generado_p:,.1f} KG</div></div>", unsafe_allow_html=True)
        c2.markdown(f"<div class='kpi-card'><div class='kpi-label'>Salidas con Manifiesto</div><div class='kpi-value val-salida'>{salidas_p:,.1f} KG</div></div>", unsafe_allow_html=True)
        c3.markdown(f"<div class='kpi-card'><div style='border-bottom: 3px solid #ef4444;'><div class='kpi-label'>Stock Actual en Cuarto</div><div class='kpi-value' style='color:#ef4444;'>{stock_p:,.1f} KG</div></div></div>", unsafe_allow_html=True)

        # Nuevo: KPI de antigüedad del residuo más antiguo aún en stock (alerta de tiempo de almacenamiento)
        fecha_mas_antigua = calcular_antiguedad_stock(df_peligrosos_full)
        if stock_p > 0 and fecha_mas_antigua:
            dias_almacenado = (hoy - fecha_mas_antigua).days
            color_alerta = "#ef4444" if dias_almacenado >= umbral_alerta_dias else "#4ade80"
            c4.markdown(f"<div class='kpi-card'><div class='kpi-label'>Antigüedad Máx. en Cuarto</div><div class='kpi-value' style='color:{color_alerta};'>{dias_almacenado} días</div></div>", unsafe_allow_html=True)
        else:
            c4.markdown(f"<div class='kpi-card'><div class='kpi-label'>Antigüedad Máx. en Cuarto</div><div class='kpi-value' style='color:#94a3b8;'>N/A</div></div>", unsafe_allow_html=True)

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

        # Nuevo: tendencia mensual generación vs. salidas — permite ver si el cuarto se está vaciando o acumulando
        if 'FECHA_CLEAN' in df_peligrosos.columns and df_peligrosos['FECHA_CLEAN'].notna().any():
            df_tmp = df_peligrosos.dropna(subset=['FECHA_CLEAN']).copy()
            df_tmp['MES'] = df_tmp['FECHA_CLEAN'].dt.to_period('M').dt.to_timestamp()
            df_tmp['TIPO'] = df_tmp['ES_INGRESO'].map({True: 'Generación', False: 'Salida'})
            tendencia_p = df_tmp.groupby(['MES', 'TIPO'])['CANTIDAD_CLEAN'].sum().reset_index()

            fig_tend_p = px.line(
                tendencia_p, x='MES', y='CANTIDAD_CLEAN', color='TIPO', markers=True,
                title="<b>Tendencia Mensual: Generación vs. Salidas (KG)</b>",
                labels={'MES': 'Mes', 'CANTIDAD_CLEAN': 'KG', 'TIPO': ''},
                template="plotly_dark",
                color_discrete_map={'Generación': '#38bdf8', 'Salida': '#f472b6'}
            )
            st.plotly_chart(fig_tend_p, use_container_width=True)

        st.write("---")
        df_mostrar_pelig = df_peligrosos.drop(columns=['CANTIDAD_CLEAN', 'FECHA_CLEAN', 'TIPO_MOV_CLEAN', 'ES_INGRESO'], errors='ignore')
        st.dataframe(df_mostrar_pelig, use_container_width=True)
        st.download_button(
            "⬇️ Descargar tabla filtrada (CSV)",
            data=df_mostrar_pelig.to_csv(index=False).encode('utf-8-sig'),
            file_name="respel_filtrado.csv",
            mime="text/csv"
        )

st.markdown("<div class='footer'>SGA v2.1 · Kenzo Jeans SAS</div>", unsafe_allow_html=True)
