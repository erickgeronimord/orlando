import pandas as pd
import streamlit as st
import plotly.express as px
import numpy as np
from datetime import datetime
from fpdf import FPDF
import base64
from io import BytesIO
from pathlib import Path
import warnings
import plotly.graph_objects as go
warnings.filterwarnings('ignore')

# Configuración inicial
st.set_page_config(
    page_title="Dashboard Financiero",
    page_icon="💰",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Paleta de colores constante
COLORES = {
    'ingresos': '#4CAF50',  # Verde
    'gastos': '#F44336',    # Rojo
    'beneficio': '#2196F3', # Azul
    'margen': '#9C27B0',    # Morado
    'destacado': '#FFC107', # Amarillo
    'linea': '#607D8B'      # Gris azulado
}

# Funciones auxiliares
def cargar_datos():
    try:
        # ID del archivo de Google Drive (extraído de la URL)
        file_id = "1Rg8wMJPbQAo7g3Pp6_NyIbVsE27sYESB"
        
        # URL de exportación directa (formato Excel)
        url = f"https://docs.google.com/spreadsheets/d/{file_id}/export?format=xlsx"
        
        # Leer el archivo directamente
        df = pd.read_excel(
            url,
            sheet_name=0,
            parse_dates=['Fecha'],
            thousands=',',
            converters={'Monto': lambda x: float(x.replace('$','').replace(',','')) 
                       if isinstance(x, str) else x}
        )
        
        cols_requeridas = {'Fecha', 'Tipo', 'Monto'}
        if not cols_requeridas.issubset(df.columns):
            faltantes = cols_requeridas - set(df.columns)
            st.error(f"Columnas faltantes: {faltantes}")
            return pd.DataFrame()
        
        # Procesamiento de fechas y años
        df['Año_Fiscal'] = df['Fecha'].apply(lambda x: x.year + 1 if x.month >= 10 else x.year)
        df['Año_Real'] = df['Fecha'].dt.year
        df['Mes_num'] = df['Fecha'].dt.month
        df['Mes_nombre'] = df['Fecha'].dt.strftime('%B')
        
        # Intentar cargar la hoja de presupuesto
        try:
            presupuesto = pd.read_excel(url, sheet_name="Presupuesto")
            presupuesto['Mes'] = pd.to_datetime(presupuesto['Mes'])
            presupuesto['Año'] = presupuesto['Mes'].dt.year
            presupuesto['Mes_num'] = presupuesto['Mes'].dt.month
            presupuesto['Año_Fiscal'] = presupuesto['Mes'].apply(
                lambda x: x.year + 1 if x.month >= 10 else x.year
            )
            return df, presupuesto
        except:
            return df, None
            
    except Exception as e:
        st.error(f"Error al cargar datos: {str(e)}")
        return pd.DataFrame(), None

def format_number(x, is_currency=True):
    if pd.isna(x):
        return ""
    try:
        num = float(x)
        if is_currency:
            return "${:,.2f}".format(num).replace(",", "X").replace(".", ",").replace("X", ".")
        return "{:,.2f}".format(num).replace(",", "X").replace(".", ",").replace("X", ".")
    except:
        return str(x)
    
@st.cache_data
def cargar_datos():
    try:
        # ID del archivo de Google Drive (extraído de la URL)
        file_id = "1Rg8wMJPbQAo7g3Pp6_NyIbVsE27sYESB"
        
        # URL de exportación directa (formato Excel)
        url = f"https://docs.google.com/spreadsheets/d/{file_id}/export?format=xlsx"
        
        # Leer el archivo directamente
        df = pd.read_excel(
            url,
            sheet_name=0,
            parse_dates=['Fecha'],
            thousands=',',
            converters={'Monto': lambda x: float(x.replace('$','').replace(',','')) 
                       if isinstance(x, str) else x}
        )
        
        # Verificar columnas requeridas
        cols_requeridas = {'Fecha', 'Tipo', 'Monto'}
        if not cols_requeridas.issubset(df.columns):
            faltantes = cols_requeridas - set(df.columns)
            st.error(f"Columnas faltantes: {faltantes}")
            return pd.DataFrame()
        
        # Procesamiento de fechas y años
        df['Año_Fiscal'] = df['Fecha'].apply(lambda x: x.year + 1 if x.month >= 10 else x.year)
        df['Año_Real'] = df['Fecha'].dt.year
        df['Mes_num'] = df['Fecha'].dt.month
        df['Mes_nombre'] = df['Fecha'].dt.strftime('%B')
        
        return df
        
    except Exception as e:
        st.error(f"Error al cargar datos: {str(e)}")
        return pd.DataFrame()

# Modificamos la función calcular_resumen para incluir Año_Real
@st.cache_data
def calcular_resumen(_df, año_fiscal=None):
    if _df.empty:
        return pd.DataFrame()
    
    try:
        # Verificar columnas requeridas
        required_cols = ['Fecha', 'Tipo', 'Monto']
        if not all(col in _df.columns for col in required_cols):
            missing = [col for col in required_cols if col not in _df.columns]
            st.error(f"Columnas faltantes: {missing}")
            return pd.DataFrame()
        
        # Crear columnas necesarias si no existen
        if 'Año_Fiscal' not in _df.columns:
            _df['Año_Fiscal'] = _df['Fecha'].apply(lambda x: x.year + 1 if x.month >= 10 else x.year)
        if 'Año_Real' not in _df.columns:
            _df['Año_Real'] = _df['Fecha'].dt.year
        if 'Mes_num' not in _df.columns:
            _df['Mes_num'] = _df['Fecha'].dt.month
        if 'Mes_nombre' not in _df.columns:
            _df['Mes_nombre'] = _df['Fecha'].dt.strftime('%B')
        
        # Filtrar por año fiscal
        if año_fiscal is not None:
            _df = _df[_df['Año_Fiscal'] == año_fiscal].copy()
        
        # Calcular métricas
        resumen = _df.groupby(['Año_Fiscal', 'Año_Real', 'Mes_num', 'Mes_nombre']).apply(
            lambda x: pd.Series({
                'Ingreso': x[x['Tipo'].str.contains('ingreso', case=False, na=False)]['Monto'].sum(),
                'Gasto': x[x['Tipo'].str.contains('gasto|costo', case=False, na=False, regex=True)]['Monto'].sum(),
                'Beneficio': (x[x['Tipo'].str.contains('ingreso', case=False, na=False)]['Monto'].sum() - 
                             x[x['Tipo'].str.contains('gasto|costo', case=False, na=False, regex=True)]['Monto'].sum())
            })
        ).reset_index()
        
        # Calcular margen (evitando división por cero)
        resumen['Margen'] = resumen.apply(
            lambda x: (x['Beneficio'] / x['Ingreso'] * 100) if x['Ingreso'] != 0 else 0,
            axis=1
        )
        
        # Agregar fila de totales
        if not resumen.empty:
            total_row = pd.DataFrame({
                'Mes_nombre': ['Total'],
                'Ingreso': [resumen['Ingreso'].sum()],
                'Gasto': [resumen['Gasto'].sum()],
                'Beneficio': [resumen['Beneficio'].sum()],
                'Margen': [
                    (resumen['Beneficio'].sum() / resumen['Ingreso'].sum() * 100) 
                    if resumen['Ingreso'].sum() > 0 else 0
                ]
            })
            
            # Mantener todas las columnas
            for col in resumen.columns:
                if col not in total_row:
                    total_row[col] = None
            
            resumen = pd.concat([resumen, total_row], ignore_index=True)
        
        return resumen.sort_values('Mes_num')
    
    except Exception as e:
        st.error(f"Error en calcular_resumen(): {str(e)}")
        return pd.DataFrame()

def crear_pdf(data, titulo):
    try:
        # Verificación inicial de datos
        if data is None or data.empty:
            st.warning("No hay datos para generar el PDF")
            return None
            
        # Verificar columnas requeridas
        required_columns = {
            'Mes': ['Mes_nombre', 'Mes', 'Fecha'],
            'Ingreso': ['Ingreso'],
            'Gasto': ['Gasto'],
            'Beneficio': ['Beneficio'],
            'Margen': ['Margen']
        }
        
        # Encontrar los nombres reales de las columnas
        column_mapping = {}
        for col_type, possible_names in required_columns.items():
            found = False
            for name in possible_names:
                if name in data.columns:
                    column_mapping[col_type] = name
                    found = True
                    break
            if not found:
                st.error(f"No se encontró columna para: {col_type}. Columnas disponibles: {list(data.columns)}")
                return None

        # Crear PDF
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", size=12)
        pdf.cell(200, 10, txt=titulo, ln=1, align='C')
        
        # Configuración de la tabla
        col_widths = [40, 30, 30, 30, 30]
        row_height = pdf.font_size * 1.5
        
        # Encabezados
        headers = ["Mes", "Ingreso", "Gasto", "Beneficio", "Margen (%)"]
        pdf.set_font("Arial", size=10, style='B')
        
        for i, header in enumerate(headers):
            pdf.cell(col_widths[i], row_height, txt=header, border=1)
        pdf.ln(row_height)
        
        # Datos
        pdf.set_font("Arial", size=10)
        for _, row in data.iterrows():
            # Texto para el mes
            mes_col = column_mapping['Mes']
            if mes_col == 'Fecha':
                mes_text = row['Fecha'].strftime('%B %Y') if pd.notna(row['Fecha']) else 'N/A'
            else:
                mes_text = str(row[mes_col]) if pd.notna(row[mes_col]) else 'N/A'
            
            # Formatear valores
            ingreso = format_number(row[column_mapping['Ingreso']]) if pd.notna(row[column_mapping['Ingreso']]) else "N/A"
            gasto = format_number(row[column_mapping['Gasto']]) if pd.notna(row[column_mapping['Gasto']]) else "N/A"
            beneficio = format_number(row[column_mapping['Beneficio']]) if pd.notna(row[column_mapping['Beneficio']]) else "N/A"
            
            margen_val = row[column_mapping['Margen']] if pd.notna(row[column_mapping['Margen']]) else 0
            margen = f"{margen_val:.2f}%" if isinstance(margen_val, (int, float)) else str(margen_val)
            
            # Añadir fila al PDF
            pdf.cell(col_widths[0], row_height, txt=mes_text, border=1)
            pdf.cell(col_widths[1], row_height, txt=ingreso, border=1)
            pdf.cell(col_widths[2], row_height, txt=gasto, border=1)
            pdf.cell(col_widths[3], row_height, txt=beneficio, border=1)
            pdf.cell(col_widths[4], row_height, txt=margen, border=1)
            pdf.ln(row_height)
        
        return pdf
        
    except Exception as e:
        st.error(f"Error crítico al crear PDF: {str(e)}")
        st.error(f"Tipo de error: {type(e).__name__}")
        return None

def download_pdf(pdf, filename):
    try:
        if pdf is None:
            st.warning("No hay PDF disponible para descargar")
            return
            
        # Generar bytes del PDF
        pdf_output = pdf.output(dest='S')
        if not pdf_output:
            st.error("La generación del PDF no produjo ningún resultado")
            return
            
        pdf_bytes = pdf_output.encode('latin-1')
        
        # Crear botón de descarga
        st.download_button(
            label="📥 Descargar Reporte",
            data=pdf_bytes,
            file_name=f"{filename}.pdf",
            mime="application/pdf",
            key=f"btn_{filename}"  # Clave única para evitar duplicados
        )
        
    except Exception as e:
        st.error(f"Error al preparar la descarga del PDF: {str(e)}")
        st.error(f"Tipo de error: {type(e).__name__}")
        
# Funciones de visualización
def mostrar_resumen_general(df, año_fiscal, resumen_ly=None):
    st.title(f"📊 Resumen General Año Fiscal {año_fiscal} (Oct {año_fiscal-1} - Sep {año_fiscal})")
    
    resumen = calcular_resumen(df, año_fiscal)
    if resumen.empty:
        st.warning("No hay datos para mostrar")
        return
    
    # KPIs principales con comparación LY si está disponible
    cols = st.columns(4)
    
    if resumen_ly is not None and not resumen_ly.empty:
        año_fiscal_anterior = año_fiscal - 1
        with cols[0]:
            ingreso_ly = resumen_ly['Ingreso'].sum()
            delta_ing = ((resumen['Ingreso'].sum() - ingreso_ly) / ingreso_ly * 100) if ingreso_ly != 0 else 0
            st.metric("💰 Ingresos Totales", 
                     format_number(resumen['Ingreso'].sum()), 
                     delta=f"{delta_ing:.1f}% vs {año_fiscal_anterior}",
                     help=f"Comparación con Año Fiscal {año_fiscal_anterior}")
        
        with cols[1]:
            gasto_ly = resumen_ly['Gasto'].sum()
            delta_gas = ((resumen['Gasto'].sum() - gasto_ly) / gasto_ly * 100) if gasto_ly != 0 else 0
            st.metric("🏷️ Gastos Totales", 
                     format_number(resumen['Gasto'].sum()), 
                     delta=f"{delta_gas:.1f}% vs {año_fiscal_anterior}",
                     help=f"Comparación con Año Fiscal {año_fiscal_anterior}")
        
        with cols[2]:
            beneficio_ly = resumen_ly['Beneficio'].sum()
            delta_ben = ((resumen['Beneficio'].sum() - beneficio_ly)) / abs(beneficio_ly) * 100 if beneficio_ly != 0 else 0
            st.metric("📈 Beneficio Total", 
                     format_number(resumen['Beneficio'].sum()), 
                     delta=f"{delta_ben:.1f}% vs {año_fiscal_anterior}",
                     help=f"Comparación con Año Fiscal {año_fiscal_anterior}")
        
        with cols[3]:
            margen = (resumen['Beneficio'].sum() / resumen['Ingreso'].sum() * 100) if resumen['Ingreso'].sum() != 0 else 0
            margen_ly = (resumen_ly['Beneficio'].sum() / resumen_ly['Ingreso'].sum() * 100) if resumen_ly['Ingreso'].sum() != 0 else 0
            delta_mar = margen - margen_ly
            st.metric("📊 Margen Total", 
                     f"{margen:.2f}%", 
                     delta=f"{delta_mar:.1f}pp vs {año_fiscal_anterior}",
                     help=f"Puntos porcentuales vs Año Fiscal {año_fiscal_anterior}")
    else:
        with cols[0]:
            st.metric("💰 Ingresos Totales", format_number(resumen['Ingreso'].sum()))
        with cols[1]:
            st.metric("🏷️ Gastos Totales", format_number(resumen['Gasto'].sum()))
        with cols[2]:
            st.metric("📈 Beneficio Total", format_number(resumen['Beneficio'].sum()))
        with cols[3]:
            margen = (resumen['Beneficio'].sum() / resumen['Ingreso'].sum() * 100) if resumen['Ingreso'].sum() != 0 else 0
            st.metric("📊 Margen Total", f"{margen:.2f}%")

    st.markdown("---")
    
    # Gráficos de resumen (excluyendo el total)
    resumen_meses = resumen[resumen['Mes_nombre'] != 'Total']
    
    # Agregar año al nombre del mes
    resumen_meses['Mes_Año'] = resumen_meses.apply(
        lambda x: f"{x['Mes_nombre']} {int(x['Año_Real'])}", 
        axis=1
    )
    
    st.subheader(f"📈 Tendencias Mensuales Año Fiscal {año_fiscal}")
    
    col1, col2 = st.columns(2)
    
    with col1:
        fig_ingresos = px.bar(resumen_meses, x='Mes_Año', y='Ingreso',
                             title=f'Ingresos por Mes {año_fiscal}',
                             color_discrete_sequence=[COLORES['ingresos']])
        st.plotly_chart(fig_ingresos, use_container_width=True)

    with col2:
        fig_gastos = px.bar(resumen_meses, x='Mes_Año', y='Gasto',
                           title=f'Gastos por Mes {año_fiscal}',
                           color_discrete_sequence=[COLORES['gastos']])
        st.plotly_chart(fig_gastos, use_container_width=True)
    
    with col1:
        fig_beneficios = px.bar(resumen_meses, x='Mes_Año', y='Beneficio',
                               title=f'Beneficios por Mes {año_fiscal}',
                               color_discrete_sequence=[COLORES['beneficio']])
        st.plotly_chart(fig_beneficios, use_container_width=True)
    
    with col2:
        fig_margen = px.line(resumen_meses, x='Mes_Año', y='Margen',
                            title=f'Evolución del Margen (%) {año_fiscal}',
                            markers=True,
                            color_discrete_sequence=[COLORES['margen']])
        st.plotly_chart(fig_margen, use_container_width=True)
    
    st.markdown("---")
    
    # Tabla detallada con colores
    st.subheader(f"📋 Detalle Mensual Año Fiscal {año_fiscal}")
    
    resumen_show = resumen_meses.copy()
    resumen_show['Ingreso'] = resumen_show['Ingreso'].apply(lambda x: format_number(x))
    resumen_show['Gasto'] = resumen_show['Gasto'].apply(lambda x: format_number(x))
    resumen_show['Beneficio'] = resumen_show['Beneficio'].apply(lambda x: format_number(x))
    resumen_show['Margen'] = resumen_show['Margen'].apply(lambda x: f"{x:.2f}%")
    
    st.dataframe(
        resumen_show[['Mes_Año', 'Ingreso', 'Gasto', 'Beneficio', 'Margen']],
        column_config={
            "Mes_Año": "Mes y Año",
            "Ingreso": st.column_config.NumberColumn("Ingresos", format="$%.2f"),
            "Gasto": st.column_config.NumberColumn("Gastos", format="$%.2f"),
            "Beneficio": st.column_config.NumberColumn("Beneficio", format="$%.2f"),
            "Margen": st.column_config.NumberColumn("Margen (%)", format="%.2f%%")
        },
        hide_index=True,
        use_container_width=True
    )
    
    pdf = crear_pdf(resumen, f"Resumen General Año Fiscal {año_fiscal}")
    download_pdf(pdf, f"resumen_general_{año_fiscal}")


def mostrar_evolucion(df, año_fiscal):
    st.title(f"📈 Evolución Mensual Año Fiscal {año_fiscal} (Oct {año_fiscal-1} - Sep {año_fiscal})")
    
    resumen = calcular_resumen(df, año_fiscal)
    if resumen.empty:
        st.warning("No hay datos para mostrar")
        return
    
    # Excluir el total para los gráficos
    resumen_meses = resumen[resumen['Mes_nombre'] != 'Total']
    
    # Agregar año al nombre del mes
    resumen_meses['Mes_Año'] = resumen_meses.apply(
        lambda x: f"{x['Mes_nombre']} {x['Año_Real']}", 
        axis=1
    )
    
    fig = px.line(
        resumen_meses,
        x='Mes_Año',
        y=['Ingreso', 'Gasto', 'Beneficio'],
        title=f'Evolución Financiera (Año Fiscal {año_fiscal})',
        markers=True,
        labels={'Mes_Año': 'Mes y Año', 'value': 'Monto ($)'}
    )
    st.plotly_chart(fig, use_container_width=True)
    
    st.subheader(f"Análisis Detallado Año Fiscal {año_fiscal}")
    col1, col2 = st.columns(2)
    
    with col1:
        fig_ben = px.bar(
            resumen_meses,
            x='Mes_Año',
            y='Beneficio',
            title=f'Beneficio por Mes - Año Fiscal {año_fiscal}',
            color='Beneficio',
            color_continuous_scale='balance',
            labels={'Mes_Año': 'Mes y Año', 'Beneficio': 'Beneficio ($)'}
        )
        st.plotly_chart(fig_ben, use_container_width=True)
    
    with col2:
        fig_pie = px.pie(
            resumen_meses,
            names='Mes_Año',
            values='Ingreso',
            title=f'Distribución de Ingresos - Año Fiscal {año_fiscal}',
            labels={'Mes_Año': 'Mes y Año', 'Ingreso': 'Ingresos ($)'}
        )
        st.plotly_chart(fig_pie, use_container_width=True)

def mostrar_analisis_presupuesto(df, presupuesto, año_fiscal):
    st.title(f"📉 Análisis Presupuestario Año Fiscal {año_fiscal} (Oct {año_fiscal-1} - Sep {año_fiscal})")
    
    if presupuesto is None:
        st.warning("No se encontraron datos de presupuesto")
        return
    
    resumen_real = calcular_resumen(df, año_fiscal)
    resumen_presupuesto = presupuesto[presupuesto['Año_Fiscal'] == año_fiscal]
    
    if resumen_real.empty or resumen_presupuesto.empty:
        st.warning("Datos insuficientes para comparación")
        return
    
    # Excluir el total para la comparación
    resumen_real = resumen_real[resumen_real['Mes_nombre'] != 'Total']
    
    # Mostrar mes y año real para datos reales
    resumen_real['Mes_Año'] = resumen_real.apply(
        lambda x: f"{x['Mes_nombre']} {int(x['Año_Real'])}", 
        axis=1
    )
    
    # Para presupuesto, mostrar mes y año real también
    resumen_presupuesto['Mes_Año'] = resumen_presupuesto['Mes'].dt.strftime('%B %Y')
    
    comparacion = pd.merge(
        resumen_real,
        resumen_presupuesto,
        on=['Año', 'Mes_num'],
        suffixes=('_Real', '_Presupuesto'),
        how='left'
    )
    
    comparacion['Var_Ingreso'] = comparacion['Ingreso_Real'] - comparacion['Ingreso_Presupuesto']
    comparacion['Var_Gasto'] = comparacion['Gasto_Real'] - comparacion['Gasto_Presupuesto']
    
    st.subheader(f"Comparativo Real vs Presupuesto Año Fiscal {año_fiscal}")
    
    # Formatear números para mostrar
    comparacion_show = comparacion.copy()
    cols_monetarias = ['Ingreso_Real', 'Ingreso_Presupuesto', 'Var_Ingreso',
                      'Gasto_Real', 'Gasto_Presupuesto', 'Var_Gasto']
    
    for col in cols_monetarias:
        comparacion_show[col] = comparacion_show[col].apply(lambda x: format_number(x))
    
    st.dataframe(
        comparacion_show[
            ['Mes_Año_Real', 'Ingreso_Real', 'Ingreso_Presupuesto', 'Var_Ingreso',
             'Gasto_Real', 'Gasto_Presupuesto', 'Var_Gasto']
        ],
        column_config={
            "Mes_Año_Real": "Mes y Año",
            "Ingreso_Real": st.column_config.TextColumn("Ingreso Real"),
            "Ingreso_Presupuesto": st.column_config.TextColumn("Ingreso Presupuesto"),
            "Var_Ingreso": st.column_config.TextColumn("Variación Ingreso"),
            "Gasto_Real": st.column_config.TextColumn("Gasto Real"),
            "Gasto_Presupuesto": st.column_config.TextColumn("Gasto Presupuesto"),
            "Var_Gasto": st.column_config.TextColumn("Variación Gasto")
        },
        hide_index=True,
        use_container_width=True
    )
    
    fig = px.bar(
        comparacion,
        x='Mes_Año_Real',
        y=['Var_Ingreso', 'Var_Gasto'],
        barmode='group',
        title=f'Variaciones vs Presupuesto - Año Fiscal {año_fiscal}',
        labels={'Mes_Año_Real': 'Mes y Año', 'value': 'Variación ($)'}
    )
    st.plotly_chart(fig, use_container_width=True)

# ... (continuar con las actualizaciones similares para las demás funciones)

def mostrar_comparacion_anios(df, año_fiscal_actual):
    st.title("🔍 Comparación entre Años Fiscales")
    
    # Verificar columnas requeridas
    required_cols = ['Año_Fiscal', 'Fecha', 'Tipo', 'Monto']
    if not all(col in df.columns for col in required_cols):
        missing = [col for col in required_cols if col not in df.columns]
        st.error(f"Columnas faltantes en los datos: {missing}")
        return
    
    # Extraer años fiscales disponibles
    años_fiscales_disponibles = sorted(df['Año_Fiscal'].unique(), reverse=True)
    
    if len(años_fiscales_disponibles) < 2:
        st.warning("Se necesitan al menos 2 años de datos para comparar")
        return
    
    # Crear selectores para elegir los años a comparar
    col1, col2 = st.columns(2)
    
    with col1:
        año_fiscal_base = st.selectbox(
            "Seleccione el año fiscal base",
            options=años_fiscales_disponibles,
            index=0,
            key="año_base"
        )
    
    with col2:
        # Excluir el año ya seleccionado en el primer selector
        años_restantes = [a for a in años_fiscales_disponibles if a != año_fiscal_base]
        año_fiscal_comparar = st.selectbox(
            "Seleccione el año fiscal a comparar",
            options=años_restantes,
            index=0 if len(años_restantes) > 0 else None,
            key="año_comparar"
        )
    
    if año_fiscal_base == año_fiscal_comparar:
        st.warning("Por favor seleccione dos años diferentes para comparar")
        return
    
    # Filtrar y calcular resúmenes para cada año fiscal
    df_base = df[df['Año_Fiscal'] == año_fiscal_base]
    df_comparar = df[df['Año_Fiscal'] == año_fiscal_comparar]
    
    resumen_base = calcular_resumen(df_base, año_fiscal_base)
    resumen_comparar = calcular_resumen(df_comparar, año_fiscal_comparar)
    
    # Verificar que hay datos para ambos años fiscales
    if resumen_base.empty or resumen_comparar.empty:
        st.warning("No hay suficientes datos para realizar la comparación")
        return
    
    # Obtener datos mensuales (excluyendo la fila 'Total')
    meses_base = resumen_base[resumen_base['Mes_nombre'] != 'Total'].copy()
    meses_comparar = resumen_comparar[resumen_comparar['Mes_nombre'] != 'Total'].copy()
    
    # Asegurar que tenemos las columnas necesarias
    for df_temp in [meses_base, meses_comparar]:
        if 'Mes_nombre' not in df_temp.columns:
            if 'Fecha' in df_temp.columns:
                df_temp['Mes_nombre'] = df_temp['Fecha'].dt.strftime('%B')
            else:
                st.error("No se encontró columna de mes en los datos")
                return
    
    # Crear columna Mes_Año con el año real
    meses_base['Mes_Año'] = meses_base.apply(
        lambda x: f"{x['Mes_nombre']} {int(x['Año_Real'])}", 
        axis=1
    )
    
    meses_comparar['Mes_Año'] = meses_comparar.apply(
        lambda x: f"{x['Mes_nombre']} {int(x['Año_Real'])}", 
        axis=1
    )
        
    # Calcular totales anuales
    total_ingreso_base = meses_base['Ingreso'].sum()
    total_ingreso_comparar = meses_comparar['Ingreso'].sum()
    total_gasto_base = meses_base['Gasto'].sum()
    total_gasto_comparar = meses_comparar['Gasto'].sum()
    total_beneficio_base = meses_base['Beneficio'].sum()
    total_beneficio_comparar = meses_comparar['Beneficio'].sum()
    
    # Calcular márgenes
    margen_base = (total_beneficio_base / total_ingreso_base * 100) if total_ingreso_base != 0 else 0
    margen_comparar = (total_beneficio_comparar / total_ingreso_comparar * 100) if total_ingreso_comparar != 0 else 0
    
    # Calcular variaciones porcentuales
    def calc_variacion(valor_base, valor_comparar):
        if valor_comparar == 0:
            return 0
        return ((valor_base - valor_comparar) / valor_comparar) * 100
    
    var_ingreso = calc_variacion(total_ingreso_base, total_ingreso_comparar)
    var_gasto = calc_variacion(total_gasto_base, total_gasto_comparar)
    var_beneficio = calc_variacion(total_beneficio_base, total_beneficio_comparar)
    var_margen = margen_base - margen_comparar  # Diferencia en puntos porcentuales
    
    # Mostrar KPIs comparativos
    st.subheader(f"📊 Comparación Anual: Año Fiscal {año_fiscal_base} vs {año_fiscal_comparar}")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            f"Ingresos {año_fiscal_base}",
            format_number(total_ingreso_base),
            delta=f"{var_ingreso:.1f}% vs {año_fiscal_comparar}",
            help=f"Comparación con Año Fiscal {año_fiscal_comparar}"
        )
    
    with col2:
        st.metric(
            f"Gastos {año_fiscal_base}",
            format_number(total_gasto_base),
            delta=f"{var_gasto:.1f}% vs {año_fiscal_comparar}",
            help=f"Comparación con Año Fiscal {año_fiscal_comparar}"
        )
    
    with col3:
        st.metric(
            f"Beneficio {año_fiscal_base}",
            format_number(total_beneficio_base),
            delta=f"{var_beneficio:.1f}% vs {año_fiscal_comparar}",
            help=f"Comparación con Año Fiscal {año_fiscal_comparar}"
        )
    
    with col4:
        st.metric(
            f"Margen {año_fiscal_base}",
            f"{margen_base:.1f}%",
            delta=f"{var_margen:.1f}pp vs {año_fiscal_comparar}",
            help=f"Diferencia en puntos porcentuales vs Año Fiscal {año_fiscal_comparar}"
        )
    
    st.markdown("---")
    
    # Crear DataFrame combinado para gráficos
    df_comparativo = pd.concat([
        meses_base.assign(Periodo=f"Año Fiscal {año_fiscal_base}"),
        meses_comparar.assign(Periodo=f"Año Fiscal {año_fiscal_comparar}")
    ])
    
    # Gráfico de ingresos
    fig_ingresos = px.bar(
        df_comparativo, 
        x='Mes_Año', 
        y='Ingreso',
        color='Periodo', 
        barmode='group',
        title=f'Ingresos Mensuales: {año_fiscal_base} vs {año_fiscal_comparar}',
        color_discrete_sequence=[COLORES['ingresos'], COLORES['destacado']]
    )
    
    fig_gastos = px.bar(
        df_comparativo, 
        x='Mes_Año', 
        y='Gasto',
        color='Periodo', 
        barmode='group',
        title=f'Gastos Mensuales: {año_fiscal_base} vs {año_fiscal_comparar}',
        color_discrete_sequence=[COLORES['gastos'], COLORES['destacado']]
    )
    st.plotly_chart(fig_gastos, use_container_width=True)
    
    # Gráfico de beneficios
    fig_beneficios = px.bar(
        df_comparativo, 
        x='Mes_nombre', 
        y='Beneficio',
        color='Periodo', 
        barmode='group',
        title=f'Beneficios Mensuales: {año_fiscal_base} vs {año_fiscal_comparar}',
        labels={'Beneficio': 'Beneficio ($)', 'Mes_nombre': 'Mes'}
    )
    st.plotly_chart(fig_beneficios, use_container_width=True)
    
    # Gráfico de margen
    fig_margen = px.line(
        df_comparativo, 
        x='Mes_nombre', 
        y='Margen',
        color='Periodo',
        title=f'Margen Mensual (%): {año_fiscal_base} vs {año_fiscal_comparar}',
        labels={'Margen': 'Margen (%)', 'Mes_nombre': 'Mes'},
        markers=True
    )
    st.plotly_chart(fig_margen, use_container_width=True)
    
    st.markdown("---")
    
    # Tabla comparativa detallada
    st.subheader("📋 Tabla Comparativa Detallada por Mes")
    
    # Hacer merge de los datos mensuales
    comparacion = pd.merge(
        meses_base,
        meses_comparar,
        on='Mes_num',
        suffixes=(f'_{año_fiscal_base}', f'_{año_fiscal_comparar}'),
        how='outer'
    ).sort_values('Mes_num')
    
    # Calcular variaciones
    comparacion['Var_Ingreso_$'] = comparacion[f'Ingreso_{año_fiscal_base}'].fillna(0) - comparacion[f'Ingreso_{año_fiscal_comparar}'].fillna(0)
    comparacion['Var_Ingreso_%'] = (comparacion['Var_Ingreso_$'] / comparacion[f'Ingreso_{año_fiscal_comparar}'].replace(0, np.nan)) * 100
    comparacion['Var_Gasto_$'] = comparacion[f'Gasto_{año_fiscal_base}'].fillna(0) - comparacion[f'Gasto_{año_fiscal_comparar}'].fillna(0)
    comparacion['Var_Gasto_%'] = (comparacion['Var_Gasto_$'] / comparacion[f'Gasto_{año_fiscal_comparar}'].replace(0, np.nan)) * 100
    comparacion['Var_Beneficio_$'] = comparacion[f'Beneficio_{año_fiscal_base}'].fillna(0) - comparacion[f'Beneficio_{año_fiscal_comparar}'].fillna(0)
    comparacion['Var_Beneficio_%'] = (comparacion['Var_Beneficio_$'] / comparacion[f'Beneficio_{año_fiscal_comparar}'].replace(0, np.nan).abs()) * 100
    comparacion['Var_Margen_pp'] = comparacion[f'Margen_{año_fiscal_base}'].fillna(0) - comparacion[f'Margen_{año_fiscal_comparar}'].fillna(0)
    
    # Formatear valores para mostrar
    def formatear_valor(x, es_moneda=True):
        if pd.isna(x):
            return "-"
        try:
            if es_moneda:
                return format_number(x)
            return f"{x:.1f}%" if "%" not in str(x) else str(x)
        except:
            return str(x)
    
    # Aplicar formato
    for col in comparacion.columns:
        if '_$' in col or col in [f'Ingreso_{año_fiscal_base}', f'Ingreso_{año_fiscal_comparar}', 
                                f'Gasto_{año_fiscal_base}', f'Gasto_{año_fiscal_comparar}', 
                                f'Beneficio_{año_fiscal_base}', f'Beneficio_{año_fiscal_comparar}']:
            comparacion[col] = comparacion[col].apply(lambda x: formatear_valor(x, True))
        elif '_%' in col or '_pp' in col or col in [f'Margen_{año_fiscal_base}', f'Margen_{año_fiscal_comparar}']:
            comparacion[col] = comparacion[col].apply(lambda x: formatear_valor(x, False))
    
    # Mostrar tabla
    st.dataframe(
        comparacion[[f'Mes_nombre_{año_fiscal_base}',
                    f'Ingreso_{año_fiscal_base}', f'Ingreso_{año_fiscal_comparar}', 'Var_Ingreso_$', 'Var_Ingreso_%',
                    f'Gasto_{año_fiscal_base}', f'Gasto_{año_fiscal_comparar}', 'Var_Gasto_$', 'Var_Gasto_%',
                    f'Beneficio_{año_fiscal_base}', f'Beneficio_{año_fiscal_comparar}', 'Var_Beneficio_$', 'Var_Beneficio_%',
                    f'Margen_{año_fiscal_base}', f'Margen_{año_fiscal_comparar}', 'Var_Margen_pp']],
        column_config={
            f"Mes_nombre_{año_fiscal_base}": "Mes",
            f"Ingreso_{año_fiscal_base}": f"Ingreso {año_fiscal_base}",
            f"Ingreso_{año_fiscal_comparar}": f"Ingreso {año_fiscal_comparar}",
            "Var_Ingreso_$": "Variación ($)",
            "Var_Ingreso_%": "Variación (%)",
            f"Gasto_{año_fiscal_base}": f"Gasto {año_fiscal_base}",
            f"Gasto_{año_fiscal_comparar}": f"Gasto {año_fiscal_comparar}",
            "Var_Gasto_$": "Variación ($)",
            "Var_Gasto_%": "Variación (%)",
            f"Beneficio_{año_fiscal_base}": f"Beneficio {año_fiscal_base}",
            f"Beneficio_{año_fiscal_comparar}": f"Beneficio {año_fiscal_comparar}",
            "Var_Beneficio_$": "Variación ($)",
            "Var_Beneficio_%": "Variación (%)",
            f"Margen_{año_fiscal_base}": f"Margen {año_fiscal_base} (%)",
            f"Margen_{año_fiscal_comparar}": f"Margen {año_fiscal_comparar} (%)",
            "Var_Margen_pp": "Variación (pp)"
        },
        hide_index=True,
        use_container_width=True,
        height=600
    )
    
    # Generar PDF
    pdf = crear_pdf(comparacion, f"Comparativo {año_fiscal_base} vs {año_fiscal_comparar}")
    download_pdf(pdf, f"comparativo_{año_fiscal_base}_vs_{año_fiscal_comparar}")

def mostrar_reporte_completo(df, año_fiscal):
    st.title(f"📑 Reporte Completo Año Fiscal {año_fiscal} (Oct {año_fiscal-1} - Sep {año_fiscal})")
    
    resumen = calcular_resumen(df, año_fiscal)
    if resumen.empty:
        st.warning("No hay datos para mostrar")
        return
    
    # Excluir el total para los gráficos
    resumen_meses = resumen[resumen['Mes_nombre'] != 'Total']
    
    # Mostrar mes con año real
    resumen_meses['Mes_Año'] = resumen_meses.apply(
        lambda x: f"{x['Mes_nombre']} {int(x['Año_Real'])}", 
        axis=1
    )
    
    # Resumen ejecutivo
    st.subheader("📌 Resumen Ejecutivo")
    
    total_ingresos = resumen['Ingreso'].sum()
    total_gastos = resumen['Gasto'].sum()
    total_beneficio = resumen['Beneficio'].sum()
    margen_promedio = resumen_meses['Margen'].mean()
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("Ingresos Totales", format_number(total_ingresos))
    with col2:
        st.metric("Gastos Totales", format_number(total_gastos))
    with col3:
        st.metric("Beneficio Total", format_number(total_beneficio))
    
    st.markdown(f"""
    - **Margen promedio anual**: {margen_promedio:.2f}%
    - **Meses con pérdidas**: {len(resumen_meses[resumen_meses['Beneficio'] < 0])}
    - **Mejor mes**: {resumen_meses.loc[resumen_meses['Beneficio'].idxmax(), 'Mes_Año']} ({format_number(resumen_meses['Beneficio'].max())})
    - **Peor mes**: {resumen_meses.loc[resumen_meses['Beneficio'].idxmin(), 'Mes_Año']} ({format_number(resumen_meses['Beneficio'].min())})
    """)
    
    st.markdown("---")
    
    # Gráficos de análisis
    st.subheader("📈 Análisis Detallado por Mes")
    
    fig_combinado = go.Figure()
    fig_combinado.add_trace(go.Bar(
        x=resumen_meses['Mes_Año'],
        y=resumen_meses['Ingreso'],
        name='Ingresos',
        marker_color=COLORES['ingresos']
    ))
    fig_combinado.add_trace(go.Bar(
        x=resumen_meses['Mes_Año'],
        y=resumen_meses['Gasto'],
        name='Gastos',
        marker_color=COLORES['gastos']
    ))
    fig_combinado.add_trace(go.Scatter(
        x=resumen_meses['Mes_Año'],
        y=resumen_meses['Beneficio'],
        name='Beneficio',
        mode='lines+markers',
        line=dict(color=COLORES['beneficio'], width=3),
        yaxis='y2'
    ))
    
    fig_combinado.update_layout(
        title=f'Ingresos, Gastos y Beneficio por Mes (Año Fiscal {año_fiscal})',
        barmode='group',
        yaxis=dict(title='Ingresos/Gastos ($)'),
        yaxis2=dict(
            title='Beneficio ($)',
            overlaying='y',
            side='right'
        ),
        hovermode='x unified'
    )
    
    st.plotly_chart(fig_combinado, use_container_width=True)
    
    # Gráfico de margen con objetivo
    fig_margen = go.Figure()
    fig_margen.add_trace(go.Bar(
        x=resumen_meses['Mes_Año'],
        y=resumen_meses['Margen'],
        name='Margen Real',
        marker_color=COLORES['margen']
    ))
    
    fig_margen.add_shape(
        type='line',
        x0=-0.5,
        y0=20,
        x1=len(resumen_meses)-0.5,
        y1=20,
        line=dict(color=COLORES['linea'], width=3, dash='dot'),
        name='Objetivo'
    )
    
    fig_margen.update_layout(
        title=f'Margen por Mes vs Objetivo (20%) (Año Fiscal {año_fiscal})',
        yaxis=dict(title='Margen (%)'),
        hovermode='x'
    )
    
    st.plotly_chart(fig_margen, use_container_width=True)
    
    st.markdown("---")
    
    # Tabla detallada para auditoría
    st.subheader("🔍 Tabla Detallada para Auditoría")
    
    resumen_audit = resumen_meses.copy()
    resumen_audit['Ingreso'] = resumen_audit['Ingreso'].apply(lambda x: format_number(x))
    resumen_audit['Gasto'] = resumen_audit['Gasto'].apply(lambda x: format_number(x))
    resumen_audit['Beneficio'] = resumen_audit['Beneficio'].apply(lambda x: format_number(x))
    resumen_audit['Margen'] = resumen_audit['Margen'].apply(lambda x: f"{x:.2f}%")
    
    st.dataframe(
        resumen_audit[['Mes_Año', 'Ingreso', 'Gasto', 'Beneficio', 'Margen']],
        column_config={
            "Mes_Año": "Mes y Año",
            "Ingreso": st.column_config.TextColumn("Ingresos"),
            "Gasto": st.column_config.TextColumn("Gastos"),
            "Beneficio": st.column_config.TextColumn("Beneficio"),
            "Margen": st.column_config.TextColumn("Margen (%)")
        },
        hide_index=True,
        use_container_width=True
    )
    
    # Información adicional para auditoría
    st.markdown("---")
    st.subheader("📌 Notas para Auditoría")
    
    with st.expander("Metodología de Cálculo"):
        st.markdown("""
        - **Ingresos**: Suma de todas las cuentas marcadas como 'Ingreso' o 'Ventas'
        - **Gastos**: Suma de todas las cuentas marcadas como 'Costo', 'Gasto', 'Material' o 'Producto'
        - **Beneficio**: Ingresos - Gastos
        - **Margen**: (Beneficio / Ingresos) * 100
        """)
    
    with st.expander("Supuestos y Limitaciones"):
        st.markdown("""
        - Los datos se obtienen directamente del archivo Excel proporcionado
        - No se realizan ajustes por inflación
        - Los cálculos son aproximados y dependen de la correcta clasificación de las cuentas
        - Los meses sin datos no aparecen en los análisis
        """)
    
    pdf = crear_pdf(resumen, f"Reporte Completo {año_fiscal}")
    download_pdf(pdf, f"reporte_completo_{año_fiscal}")

# Función principal
def main():
    # Cargar datos
    df = cargar_datos()
    
    if df.empty:
        st.error("No se pudieron cargar los datos principales")
        st.stop()

    # Sidebar - Filtros
    with st.sidebar:
        st.title("⚙️ Panel de Control")
        
        tabs = ["📊 Resumen General", "📈 Evolución Mensual", "🔍 Comparación entre Años", "📑 Reporte Completo"]
        seccion = st.radio("Navegación", tabs)
        
        st.subheader("Filtros")
        año_fiscal = st.selectbox(
            "Año Fiscal",
            options=sorted(df['Año_Fiscal'].unique(), reverse=True),
            index=0,
            help="Año fiscal va de Octubre a Septiembre (ej. 2024 = Oct2023-Sep2024)"
        )
        
        tipos = df['Tipo'].unique()
        tipos_sel = st.multiselect(
            "Tipos de transacción",
            options=tipos,
            default=tipos
        )

    # Filtrar datos
    df_filtrado = df[(df['Año_Fiscal'] == año_fiscal) & (df['Tipo'].isin(tipos_sel))]
    
    # Mostrar sección seleccionada
    if seccion == "📊 Resumen General":
        mostrar_resumen_general(df_filtrado, año_fiscal)
    elif seccion == "📈 Evolución Mensual":
        mostrar_evolucion(df_filtrado, año_fiscal)
    elif seccion == "🔍 Comparación entre Años":
        mostrar_comparacion_anios(df[df['Tipo'].isin(tipos_sel)], año_fiscal)
    elif seccion == "📑 Reporte Completo":
        mostrar_reporte_completo(df_filtrado, año_fiscal)
    # Mensaje final
    st.markdown("---")
    st.markdown("""
    <div style="text-align: center; padding: 20px; background-color: #f8f9fa; border-radius: 10px;">
        <h4>Dashboard Financiero con Gráficos y Filtros</h4>
        <p>Herramienta desarrollada para análisis financiero integral</p>
    </div>
    """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()
