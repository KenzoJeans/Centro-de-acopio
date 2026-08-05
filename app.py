import streamlit as st
import pandas as pd
import plotly.express as px

# Configuración de página
st.set_page_config(page_title="Control de Acopio | SGA", layout="wide", page_icon="♻️")

# Estilos CSS personalizados (Manteniendo la estética oscura y limpia)
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
st.markdown("Monitor de trazabilidad de entradas y salidas divido por clasificación de manejo.")

# ==========================================
# 1. CARGA Y PREPARACIÓN DE DATOS
# ==========================================
@st.cache_data(ttl=60)
def cargar_datos():
    # URL de exportación CSV de tu Google Sheet (Reemplazar ID)
    # ID_HOJA = "TU_ID_AQUI"
    # url = f"https://docs.google.com/spreadsheets/d/{ID_HOJA}/export?format=csv"
    
    # DATOS DE PRUEBA BASADOS EN TU IMAGEN PARA QUE PUEDAS EJECUTARLO YA MISMO
    data = {
        'Marca temporal': ['5/08/2026 7:48:59', '5/08/2026 7:50:20', '5/08/2026 7:50:56', '5/08/2026 7:51:55', '5/08/2026 7:52:38', '6/08/2026 8:00:00', '7/08/2026 9:15:00'],
        'FECHA DEL MOVIMIENTO:': ['4/02/2026', '1/04/2026', '11/03/2026', '27/02/2026', '27/03/2026', '10/05/2026', '15/06/2026'],
        'TIPO DE MOVIMIENTO:': ['Ingreso al centro de acopio']*7,
        'NOMBRE DEL RESIDUO:': ['BATERIAS USADAS', 'BATERIAS USADAS', 'BATERIAS USADAS', 'ENVASES CONTAMINADOS C', 'ENVASES CONTAMINADOS C', 'CARTON', 'PLASTICO'],
        'CANTIDAD:': [45, 50, 45, 10, 11.2, 120, 85],
        'UNIDAD DE MEDIDA:': ['KG']*7,
        'ÁREA GENERADORA:': ['SISTEMAS', 'SISTEMAS', 'SISTEMAS', 'CUARTO DE QUÍMICOS', 'CUARTO DE QUÍMICOS', 'CORTE', 'EMPAQUE'],
        'RESPONSABLE:': ['RAÚL JAIMES', 'FRANCINIED CHICUÉ', 'RAÚL JAIMES', 'RAÚL JAIMES', 'SAÚL GALVIS', 'MARIA PEREZ', 'JUAN LÓPEZ']
    }
    df = pd.DataFrame(data)
    
    # Limpieza y conversión de fechas
    df['FECHA DEL MOVIMIENTO:'] = pd.to_datetime(df['FECHA DEL MOVIMIENTO:'], format='%d/%m/%Y', errors='coerce')
    df['CANTIDAD:'] = pd.to_numeric(df['CANTIDAD:'], errors='coerce').fillna(0)
    
    # MOTOR DE CLASIFICACIÓN (Identifica automáticamente si es Peligroso o Aprovechable)
    def clasificar_residuo(nombre):
        peligrosos_keywords = ['BATERIA', 'ENVASE CONTAMINADO', 'ACEITE', 'QUIMICO', 'TINTA', 'LUMINARIA', 'WIPE']
        nombre_upper = str(nombre).upper()
        if any(keyword in nombre_upper for keyword in peligrosos_keywords):
            return 'Peligroso'
        return 'Aprovechable'
    
    df['CATEGORIA'] = df['NOMBRE DEL RESIDUO:'].apply(clasificar_residuo)
    return df

df = cargar_datos()

# Separar DataFrames por categoría
df_aprovechables = df[df['CATEGORIA'] == 'Aprovechable']
df_peligrosos = df[df['CATEGORIA'] == 'Peligroso']

# ==========================================
# 2. INTERFAZ DE PESTAÑAS (TABS)
# ==========================================
tab_aprov, tab_pelig = st.tabs(["♻️ Residuos Aprovechables", "☢️ Residuos Peligrosos (RESPEL)"])

# ------------------------------------------
# PESTAÑA 1: APROVECHABLES
# ------------------------------------------
with tab_aprov:
    st.subheader("Gestión de Materiales Reciclables")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        total_kg_aprov = df_aprovechables['CANTIDAD:'].sum()
        st.markdown(f"<div class='kpi-card'><div class='kpi-label'>Total Acopiado</div><div class='kpi-value'>{total_kg_aprov:,.1f} KG</div></div>", unsafe_allow_html=True)
    with col2:
        movimientos_aprov = len(df_aprovechables)
        st.markdown(f"<div class='kpi-card'><div class='kpi-label'>Ingresos Registrados</div><div class='kpi-value'>{movimientos_aprov}</div></div>", unsafe_allow_html=True)
    with col3:
        # Espacio ideal para programar recolecciones
        st.markdown(f"<div class='kpi-card'><div class='kpi-label'>Estado de Ruta</div><div class='kpi-value' style='color:#4ade80;'>Óptimo</div></div>", unsafe_allow_html=True)
        
    st.write("---")
    
    col_graf1, col_graf2 = st.columns(2)
    with col_graf1:
        if not df_aprovechables.empty:
            fig1 = px.pie(df_aprovechables, values='CANTIDAD:', names='NOMBRE DEL RESIDUO:', 
                          title="Distribución de Materiales", template="plotly_dark", hole=0.4)
            st.plotly_chart(fig1, use_container_width=True)
            
    with col_graf2:
        if not df_aprovechables.empty:
            fig2 = px.bar(df_aprovechables.groupby('ÁREA GENERADORA:')['CANTIDAD:'].sum().reset_index(), 
                          x='ÁREA GENERADORA:', y='CANTIDAD:', title="Generación por Área", 
                          template="plotly_dark", color_discrete_sequence=['#4ade80'])
            st.plotly_chart(fig2, use_container_width=True)
            
    st.dataframe(df_aprovechables.drop(columns=['Marca temporal', 'CATEGORIA']), use_container_width=True)
    
    # Nota operativa
    st.info("💡 **Recordatorio Operativo:** Coordinar los cronogramas de recolección de este mes con sus proveedores (ej. Ambiente & Soluciones SAS) para evitar saturación del cuarto.")

# ------------------------------------------
# PESTAÑA 2: PELIGROSOS (RESPEL)
# ------------------------------------------
with tab_pelig:
    st.subheader("Auditoría y Control de Sustancias Peligrosas")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        total_kg_pelig = df_peligrosos['CANTIDAD:'].sum()
        st.markdown(f"<div class='kpi-card'><div style='border-left: 4px solid #ef4444;'><div class='kpi-label'>Masa Total (RESPEL)</div><div class='kpi-value'>{total_kg_pelig:,.1f} KG</div></div></div>", unsafe_allow_html=True)
    with col2:
        areas_involucradas = df_peligrosos['ÁREA GENERADORA:'].nunique()
        st.markdown(f"<div class='kpi-card'><div style='border-left: 4px solid #f59e0b;'><div class='kpi-label'>Áreas Críticas Generadoras</div><div class='kpi-value'>{areas_involucradas}</div></div></div>", unsafe_allow_html=True)
    with col3:
        st.markdown(f"<div class='kpi-card'><div style='border-left: 4px solid #3b82f6;'><div class='kpi-label'>Estado Matriz Legal</div><div class='kpi-value' style='color:#3b82f6;'>Vigente</div></div></div>", unsafe_allow_html=True)

    st.write("---")
    
    if not df_peligrosos.empty:
        # Gráfico de serie de tiempo para ingresos
        ingresos_tiempo = df_peligrosos.groupby('FECHA DEL MOVIMIENTO:')['CANTIDAD:'].sum().reset_index()
        fig3 = px.line(ingresos_tiempo, x='FECHA DEL MOVIMIENTO:', y='CANTIDAD:', 
                       title="Tendencia de Ingreso al Cuarto (Año en curso)", markers=True, template="plotly_dark", 
                       color_discrete_sequence=['#ef4444'])
        st.plotly_chart(fig3, use_container_width=True)
        
    st.dataframe(df_peligrosos.drop(columns=['Marca temporal', 'CATEGORIA']), use_container_width=True)

    # Integración con el sistema de rotulado
    st.warning("⚠️ **Análisis de Vulnerabilidad:** Asegúrese de que los 'ENVASES CONTAMINADOS C' cuenten con su rótulo estandarizado y código QR asociado a la hoja de seguridad digital en la zona de acopio.")

# Footer corporativo
st.markdown("<div class='footer'>SGA v2.0 · Kenzo Jeans SAS</div>", unsafe_allow_html=True)
