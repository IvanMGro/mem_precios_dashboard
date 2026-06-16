import streamlit as st
import pandas as pd
import numpy as np
import requests
import plotly.express as px
from datetime import datetime, timedelta
import json

# ==================== CONFIGURACIÓN DE LA PÁGINA ====================
st.set_page_config(
    page_title="Consultor de Precios CENACE",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ==================== TÍTULO Y DESCRIPCIÓN ====================
st.title("⚡ Consultor de Precios del Mercado Eléctrico - CENACE")
st.markdown("""
Esta aplicación permite consultar los precios zonales del Sistema Interconectado Nacional (SIN) 
a través de los webservices del CENACE.
""")
st.markdown("---")

# ==================== FUNCIONES ====================
@st.cache_data(ttl=3600)  # Cache por 1 hora
def consultar_precios(zona, año_i, mes_i, dia_i, año_f, mes_f, dia_f):
    """
    Consulta los precios del CENACE para una zona y periodo específico
    """
    base_url = 'https://ws01.cenace.gob.mx:8082/SWPEND/SIM/SIN/'
    mercados = ['MDA', 'MTR']
    plot_df = pd.DataFrame()
    
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    for idx, mercado in enumerate(mercados):
        status_text.text(f"Consultando {mercado}...")
        
        # Construir petición
        peticion = (base_url + mercado + '/' + zona + '/' + 
                   año_i + '/' + mes_i + '/' + dia_i + '/' + 
                   año_f + '/' + mes_f + '/' + dia_f + '/JSON')
        
        try:
            response = requests.get(peticion, timeout=30)
            response.raise_for_status()
            
            x = response.json()
            
            # Verificar status de la respuesta
            if x.get('status') != 'OK':
                st.error(f"Error en la consulta de {mercado}: {x.get('status')}")
                continue
            
            results = x['Resultados'][0]
            pml_zone = results['Valores']
            mem_df = pd.DataFrame(pml_zone)
            
            # Formatear datos
            mem_df['fecha'] = pd.to_datetime(mem_df['fecha'])
            mem_df['pz'] = mem_df['pz'].astype(float)
            mem_df['pz_ene'] = mem_df['pz_ene'].astype(float)
            mem_df['pz_per'] = mem_df['pz_per'].astype(float)
            mem_df['pz_cng'] = mem_df['pz_cng'].astype(float)
            mem_df['periodo'] = mem_df['fecha'].astype(str) + ' : H' + mem_df['hora'].astype(str)
            
            # Renombrar columna
            mem_df.rename(columns={'pz': 'Precio Zonal (MXN/MWh)'}, inplace=True)
            
            # Agregar columna de mercado
            mem_df['mercado'] = mercado
            
            # Concatenar
            plot_df = pd.concat([plot_df, mem_df], ignore_index=True)
            
        except requests.exceptions.RequestException as e:
            st.error(f"Error al consultar {mercado}: {str(e)}")
        
        progress_bar.progress((idx + 1) / len(mercados))
    
    status_text.empty()
    progress_bar.empty()
    
    if plot_df.empty:
        st.warning("No se obtuvieron datos para los parámetros seleccionados")
        return None
    
    return plot_df

def crear_grafico(df, zona, tipo_grafico='lineas'):
    """
    Crea el gráfico interactivo con los datos
    """
    if df is None or df.empty:
        return None
    
    if tipo_grafico == 'lineas':
        fig = px.line(
            df, 
            x='periodo', 
            y='Precio Zonal (MXN/MWh)', 
            color='mercado',
            title=f'Precios Zonales - {zona}',
            labels={'periodo': 'Período', 'Precio Zonal (MXN/MWh)': 'Precio (MXN/MWh)'},
            template='plotly_white'
        )
    else:  # barras
        # Agrupar por fecha y mercado para barras
        df_agrupado = df.groupby(['fecha', 'mercado'])['Precio Zonal (MXN/MWh)'].mean().reset_index()
        fig = px.bar(
            df_agrupado,
            x='fecha',
            y='Precio Zonal (MXN/MWh)',
            color='mercado',
            barmode='group',
            title=f'Precios Promedio Diarios - {zona}',
            labels={'fecha': 'Fecha', 'Precio Zonal (MXN/MWh)': 'Precio Promedio (MXN/MWh)'},
            template='plotly_white'
        )
    
    # Mejorar layout
    fig.update_layout(
        height=500,
        hovermode='x unified',
        legend=dict(
            yanchor="top",
            y=0.99,
            xanchor="left",
            x=0.01
        )
    )
    
    # Añadir línea de referencia en 0
    fig.add_hline(y=0, line_dash="dash", line_color="gray", opacity=0.5)
    
    return fig

def mostrar_estadisticas(df):
    """
    Muestra estadísticas descriptivas de los datos
    """
    if df is None or df.empty:
        return
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            "Total de registros",
            f"{len(df):,}"
        )
    
    with col2:
        precio_promedio = df['Precio Zonal (MXN/MWh)'].mean()
        st.metric(
            "Precio promedio",
            f"${precio_promedio:,.2f} MXN/MWh"
        )
    
    with col3:
        precio_max = df['Precio Zonal (MXN/MWh)'].max()
        st.metric(
            "Precio máximo",
            f"${precio_max:,.2f} MXN/MWh"
        )
    
    with col4:
        precio_min = df['Precio Zonal (MXN/MWh)'].min()
        st.metric(
            "Precio mínimo",
            f"${precio_min:,.2f} MXN/MWh"
        )

def mostrar_tabla_datos(df):
    """
    Muestra tabla interactiva con los datos
    """
    if df is None or df.empty:
        return
    
    # Seleccionar columnas para mostrar
    columnas_mostrar = ['fecha', 'hora', 'Precio Zonal (MXN/MWh)', 'pz_ene', 'pz_per', 'pz_cng', 'mercado']
    df_mostrar = df[columnas_mostrar].copy()
    
    # Renombrar columnas para mejor visualización
    df_mostrar.columns = ['Fecha', 'Hora', 'Precio Zonal', 'Precio ENERGÍA', 'Precio PER', 'Precio CNG', 'Mercado']
    
    # Formatear números
    for col in ['Precio Zonal', 'Precio ENERGÍA', 'Precio PER', 'Precio CNG']:
        df_mostrar[col] = df_mostrar[col].apply(lambda x: f"{x:,.2f}")
    
    st.dataframe(
        df_mostrar,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Fecha": st.column_config.DateColumn("Fecha", width="small"),
            "Hora": st.column_config.TextColumn("Hora", width="small"),
            "Precio Zonal": st.column_config.TextColumn("Precio Zonal", width="medium"),
            "Precio ENERGÍA": st.column_config.TextColumn("Precio ENERGÍA", width="medium"),
            "Precio PER": st.column_config.TextColumn("Precio PER", width="medium"),
            "Precio CNG": st.column_config.TextColumn("Precio CNG", width="medium"),
            "Mercado": st.column_config.TextColumn("Mercado", width="small")
        }
    )

def descargar_datos(df):
    """
    Permite descargar los datos en CSV
    """
    if df is None or df.empty:
        return
    
    csv = df.to_csv(index=False)
    st.download_button(
        label="📥 Descargar datos (CSV)",
        data=csv,
        file_name=f"precios_cenace_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
        mime="text/csv",
        use_container_width=True
    )

# ==================== ZONAS DISPONIBLES ====================
ZONAS = [
    'MONTERREY', 'HERMOSILLO', 'CHIHUAHUA', 'SALTILLO', 'DURANGO',
    'CDMX', 'GUADALAJARA', 'PUEBLA', 'QUERETARO', 'MERIDA',
    'BAJA_CALIFORNIA', 'BAJA_CALIFORNIA_SUR', 'SINALOA', 'SONORA'
]

# ==================== SIDEBAR - CONTROLES ====================
st.sidebar.header("🎛️ Parámetros de Consulta")

# Selección de zona
zona = st.sidebar.selectbox(
    "Selecciona la zona:",
    ZONAS,
    index=0
)

# Selección de fechas
st.sidebar.subheader("📅 Rango de fechas")

# Fechas por defecto (última semana)
fecha_fin = datetime.now() - timedelta(days=1)
fecha_inicio = fecha_fin - timedelta(days=6)

col1, col2 = st.sidebar.columns(2)

with col1:
    fecha_inicio = st.date_input(
        "Fecha inicio",
        value=fecha_inicio,
        max_value=datetime.now()
    )

with col2:
    fecha_fin = st.date_input(
        "Fecha fin",
        value=fecha_fin,
        max_value=datetime.now()
    )

# Validar fechas
if fecha_inicio > fecha_fin:
    st.sidebar.error("⚠️ La fecha inicio debe ser anterior a la fecha fin")

# Tipo de gráfico
tipo_grafico = st.sidebar.radio(
    "Tipo de gráfico:",
    ['Lineas', 'Barras'],
    index=0
)

# Botón de consulta
consultar = st.sidebar.button(
    "🔍 Consultar Precios",
    type="primary",
    use_container_width=True
)

# Información adicional en sidebar
st.sidebar.markdown("---")
st.sidebar.info("""
**ℹ️ Información:**
- **MDA:** Mercado de Día Adelantado
- **MTR:** Mercado de Tiempo Real
- Los precios están en MXN/MWh
""")

# ==================== CONTENIDO PRINCIPAL ====================
if consultar:
    if fecha_inicio > fecha_fin:
        st.error("❌ La fecha inicio debe ser anterior a la fecha fin")
    else:
        with st.spinner("Consultando datos del CENACE..."):
            # Preparar parámetros
            año_i = fecha_inicio.strftime('%Y')
            mes_i = fecha_inicio.strftime('%m')
            dia_i = fecha_inicio.strftime('%d')
            año_f = fecha_fin.strftime('%Y')
            mes_f = fecha_fin.strftime('%m')
            dia_f = fecha_fin.strftime('%d')
            
            # Consultar datos
            df = consultar_precios(zona, año_i, mes_i, dia_i, año_f, mes_f, dia_f)
            
            if df is not None and not df.empty:
                st.success(f"✅ Datos consultados exitosamente - {len(df)} registros")
                
                # Mostrar estadísticas
                mostrar_estadisticas(df)
                
                # Crear pestañas
                tab1, tab2, tab3 = st.tabs(["📊 Gráfico", "📋 Tabla de Datos", "📈 Análisis"])
                
                with tab1:
                    # Gráfico
                    fig = crear_grafico(df, zona, tipo_grafico.lower())
                    if fig:
                        st.plotly_chart(fig, use_container_width=True)
                    
                    # Botón de descarga
                    descargar_datos(df)
                
                with tab2:
                    mostrar_tabla_datos(df)
                
                with tab3:
                    st.subheader("📈 Análisis por Mercado")
                    
                    # Análisis por mercado
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.markdown("**MDA (Día Adelantado)**")
                        df_mda = df[df['mercado'] == 'MDA']
                        if not df_mda.empty:
                            st.metric("Promedio", f"${df_mda['Precio Zonal (MXN/MWh)'].mean():,.2f}")
                            st.metric("Máximo", f"${df_mda['Precio Zonal (MXN/MWh)'].max():,.2f}")
                            st.metric("Mínimo", f"${df_mda['Precio Zonal (MXN/MWh)'].min():,.2f}")
                    
                    with col2:
                        st.markdown("**MTR (Tiempo Real)**")
                        df_mtr = df[df['mercado'] == 'MTR']
                        if not df_mtr.empty:
                            st.metric("Promedio", f"${df_mtr['Precio Zonal (MXN/MWh)'].mean():,.2f}")
                            st.metric("Máximo", f"${df_mtr['Precio Zonal (MXN/MWh)'].max():,.2f}")
                            st.metric("Mínimo", f"${df_mtr['Precio Zonal (MXN/MWh)'].min():,.2f}")
                    
                    # Comparación MDA vs MTR
                    if not df_mda.empty and not df_mtr.empty:
                        st.subheader("📊 Comparación MDA vs MTR")
                        comparacion = pd.DataFrame({
                            'Métrica': ['Promedio', 'Máximo', 'Mínimo', 'Desv. Estándar'],
                            'MDA': [
                                df_mda['Precio Zonal (MXN/MWh)'].mean(),
                                df_mda['Precio Zonal (MXN/MWh)'].max(),
                                df_mda['Precio Zonal (MXN/MWh)'].min(),
                                df_mda['Precio Zonal (MXN/MWh)'].std()
                            ],
                            'MTR': [
                                df_mtr['Precio Zonal (MXN/MWh)'].mean(),
                                df_mtr['Precio Zonal (MXN/MWh)'].max(),
                                df_mtr['Precio Zonal (MXN/MWh)'].min(),
                                df_mtr['Precio Zonal (MXN/MWh)'].std()
                            ]
                        })
                        
                        # Formatear valores
                        for col in ['MDA', 'MTR']:
                            comparacion[col] = comparacion[col].apply(lambda x: f"${x:,.2f}")
                        
                        st.dataframe(comparacion, hide_index=True, use_container_width=True)
                        
                        # Diferencia porcentual
                        diff_pct = ((df_mda['Precio Zonal (MXN/MWh)'].mean() - 
                                   df_mtr['Precio Zonal (MXN/MWh)'].mean()) / 
                                   df_mtr['Precio Zonal (MXN/MWh)'].mean()) * 100
                        
                        st.metric(
                            "Diferencia promedio MDA vs MTR",
                            f"{diff_pct:+.1f}%",
                            delta=f"{diff_pct:+.1f}%",
                            delta_color="inverse"
                        )
                        
            else:
                st.warning("No se encontraron datos para los parámetros seleccionados")

else:
    # Mensaje inicial
    st.info("👈 Selecciona los parámetros en el panel lateral y presiona 'Consultar Precios'")
    
    # Mostrar ejemplo
    st.markdown("""
    ### 📋 Ejemplo de consulta
    
    Para consultar precios:
    1. Selecciona una **zona** (ej. MONTERREY)
    2. Define el **rango de fechas** (máximo 7 días)
    3. Elige el **tipo de gráfico** (Líneas o Barras)
    4. Presiona **Consultar Precios**
    
    ### 📊 Datos disponibles
    
    La consulta devuelve:
    - **Precio Zonal**: Precio en MXN/MWh
    - **Precio ENERGÍA**: Componente de energía
    - **Precio PER**: Componente de pérdidas
    - **Precio CNG**: Componente de congestión
    - **Mercado**: MDA (Día Adelantado) o MTR (Tiempo Real)
    """)

# ==================== FOOTER ====================
st.markdown("---")
st.markdown("""
<div style='text-align: center; color: #666; padding: 20px;'>
    <p>⚡ Datos obtenidos de los webservices del CENACE</p>
    <p style='font-size: 12px;'>Sistema Interconectado Nacional (SIN) - Mercado Eléctrico Mayorista</p>
</div>
""", unsafe_allow_html=True)