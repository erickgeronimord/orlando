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

# Funciones auxiliares
@st.cache_data
def cargar_datos():
    try:
        # ID del archivo (extraído de la URL)
        file_id = "1Rg8wMJPbQAo7g3Pp6_NyIbVsE27sYESB"
        
        # Descargar como Excel
        url = f"https://docs.google.com/spreadsheets/d/{file_id}/export?format=xlsx"
        response = requests.get(url)
        
        # Leer el archivo en memoria
        excel_data = BytesIO(response.content)
        
        # Hoja principal
        df = pd.read_excel(
            excel_data,
            sheet_name=0,
            parse_dates=['Fecha'],
            thousands=',',
            converters={'Monto': lambda x: float(x.replace('$','').replace(',','')) 
                       if isinstance(x, str) else x}
        )
        
        # Procesamiento de columnas (igual que antes)
        df['Año'] = df['Year'] if 'Year' in df.columns else df['Fecha'].dt.year
        df['Mes_num'] = df['Fecha'].dt.month
        df['Mes_nombre'] = df['Mes'] if 'Mes' in df.columns else df['Fecha'].dt.strftime('%B')
        df['Monto'] = pd.to_numeric(df['Monto'])
        
        # Hoja de presupuesto (si existe)
        try:
            presupuesto = pd.read_excel(excel_data, sheet_name="Presupuesto")
            presupuesto['Mes'] = pd.to_datetime(presupuesto['Mes'])
            presupuesto['Año'] = presupuesto['Mes'].dt.year
            presupuesto['Mes_num'] = presupuesto['Mes'].dt.month
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
def calcular_resumen(_df, año=None):
    if _df.empty:
        return pd.DataFrame()
    
    try:
        # Filtrar por año si se especifica
        if año is not None:
            _df = _df[_df['Año'] == año]
        
        resumen = _df.groupby(['Año', 'Mes_num', 'Mes_nombre']).apply(
            lambda x: pd.Series({
                'Ingreso': x[x['Tipo'].str.contains('ingreso', case=False, na=False)]['Monto'].sum(),
                'Gasto': x[x['Tipo'].str.contains('gasto|costo', case=False, na=False, regex=True)]['Monto'].sum(),
                'Beneficio': x[x['Tipo'].str.contains('ingreso', case=False, na=False)]['Monto'].sum() - 
                            x[x['Tipo'].str.contains('gasto|costo', case=False, na=False, regex=True)]['Monto'].sum()
            })
        ).reset_index()
        
        resumen['Margen'] = (resumen['Beneficio'] / resumen['Ingreso'].replace(0, np.nan)) * 100
        
        # Solo agregar total si hay datos
        if not resumen.empty:
            totales = pd.DataFrame({
                'Mes_nombre': ['Total'],
                'Ingreso': [resumen['Ingreso'].sum()],
                'Gasto': [resumen['Gasto'].sum()],
                'Beneficio': [resumen['Beneficio'].sum()],
                'Margen': [(resumen['Beneficio'].sum() / resumen['Ingreso'].sum() * 100) 
                          if resumen['Ingreso'].sum() > 0 else 0]
            })
            resumen = pd.concat([resumen, totales], ignore_index=True)
        
        return resumen.sort_values('Mes_num')
    
    except Exception as e:
        st.error(f"Error al calcular resumen: {str(e)}")
        return pd.DataFrame()

def crear_pdf(data, titulo):
    try:
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", size=12)
        pdf.cell(200, 10, txt=titulo, ln=1, align='C')
        
        pdf.set_font("Arial", size=10, style='B')
        col_width = pdf.w / 4.5
        row_height = pdf.font_size * 1.5
        headers = ["Mes", "Ingreso", "Gasto", "Beneficio", "Margen (%)"]
        
        for header in headers:
            pdf.cell(col_width, row_height, txt=header, border=1)
        pdf.ln(row_height)
        
        pdf.set_font("Arial", size=10)
        for _, row in data.iterrows():
            pdf.cell(col_width, row_height, txt=str(row['Mes_nombre']), border=1)
            pdf.cell(col_width, row_height, txt=format_number(row['Ingreso']), border=1)
            pdf.cell(col_width, row_height, txt=format_number(row['Gasto']), border=1)
            pdf.cell(col_width, row_height, txt=format_number(row['Beneficio']), border=1)
            pdf.cell(col_width, row_height, txt=f"{row['Margen']:.2f}%", border=1)
            pdf.ln(row_height)
        
        return pdf
    except Exception as e:
        st.error(f"Error al crear PDF: {str(e)}")
        return None

def download_pdf(pdf, filename):
    if pdf:
        pdf_bytes = pdf.output(dest='S').encode('latin-1')
        st.download_button(
            label="📥 Descargar Reporte",
            data=pdf_bytes,
            file_name=f"{filename}.pdf",
            mime="application/pdf"
        )

# Funciones de visualización
def mostrar_resumen_general(df, año, resumen_ly=None):
    st.title(f"📊 Resumen General {año}")
    
    resumen = calcular_resumen(df, año)
    if resumen.empty:
        st.warning("No hay datos para mostrar")
        return
    
    # KPIs principales con comparación LY si está disponible
    cols = st.columns(4)
    
    if resumen_ly is not None and not resumen_ly.empty:
        año_anterior = año - 1
        with cols[0]:
            ingreso_ly = resumen_ly['Ingreso'].sum()
            delta_ing = ((resumen['Ingreso'].sum() - ingreso_ly) / ingreso_ly * 100) if ingreso_ly != 0 else 0
            st.metric("💰 Ingresos Totales", 
                     format_number(resumen['Ingreso'].sum()), 
                     delta=f"{delta_ing:.1f}% vs {año_anterior}",
                     help=f"Comparación con {año_anterior}")
        
        with cols[1]:
            gasto_ly = resumen_ly['Gasto'].sum()
            delta_gas = ((resumen['Gasto'].sum() - gasto_ly) / gasto_ly * 100) if gasto_ly != 0 else 0
            st.metric("🏷️ Gastos Totales", 
                     format_number(resumen['Gasto'].sum()), 
                     delta=f"{delta_gas:.1f}% vs {año_anterior}",
                     help=f"Comparación con {año_anterior}")
        
        with cols[2]:
            beneficio_ly = resumen_ly['Beneficio'].sum()
            delta_ben = ((resumen['Beneficio'].sum() - beneficio_ly)) / abs(beneficio_ly) * 100 if beneficio_ly != 0 else 0
            st.metric("📈 Beneficio Total", 
                     format_number(resumen['Beneficio'].sum()), 
                     delta=f"{delta_ben:.1f}% vs {año_anterior}",
                     help=f"Comparación con {año_anterior}")
        
        with cols[3]:
            margen = (resumen['Beneficio'].sum() / resumen['Ingreso'].sum() * 100) if resumen['Ingreso'].sum() != 0 else 0
            margen_ly = (resumen_ly['Beneficio'].sum() / resumen_ly['Ingreso'].sum() * 100) if resumen_ly['Ingreso'].sum() != 0 else 0
            delta_mar = margen - margen_ly
            st.metric("📊 Margen Total", 
                     f"{margen:.2f}%", 
                     delta=f"{delta_mar:.1f}pp vs {año_anterior}",
                     help=f"Puntos porcentuales vs {año_anterior}")
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
    
    st.subheader(f"📈 Tendencias Mensuales {año}")
    
    col1, col2 = st.columns(2)
    
    with col1:
        fig_ingresos = px.bar(resumen_meses, x='Mes_nombre', y='Ingreso',
                             title=f'Ingresos por Mes {año}',
                             color='Ingreso',
                             color_continuous_scale='Blues')
        st.plotly_chart(fig_ingresos, use_container_width=True)

    with col2:
        fig_gastos = px.bar(resumen_meses, x='Mes_nombre', y='Gasto',
                           title=f'Gastos por Mes {año}',
                           color='Gasto',
                           color_continuous_scale='Reds')
        st.plotly_chart(fig_gastos, use_container_width=True)
    
    col1, col2 = st.columns(2)
    
    with col1:
        fig_beneficios = px.bar(resumen_meses, x='Mes_nombre', y='Beneficio',
                               title=f'Beneficios por Mes {año}',
                               color='Beneficio',
                               color_continuous_scale=px.colors.diverging.Tealrose)
        st.plotly_chart(fig_beneficios, use_container_width=True)
    
    with col2:
        fig_margen = px.line(resumen_meses, x='Mes_nombre', y='Margen',
                            title=f'Evolución del Margen (%) {año}',
                            markers=True,
                            color_discrete_sequence=['#3498db'])
        st.plotly_chart(fig_margen, use_container_width=True)
    
    st.markdown("---")
    
    # Tabla detallada con colores
    st.subheader(f"📋 Detalle Mensual {año}")
    
    resumen_show = resumen_meses.copy()
    resumen_show['Ingreso'] = resumen_show['Ingreso'].apply(lambda x: format_number(x))
    resumen_show['Gasto'] = resumen_show['Gasto'].apply(lambda x: format_number(x))
    resumen_show['Beneficio'] = resumen_show['Beneficio'].apply(lambda x: format_number(x))
    resumen_show['Margen'] = resumen_show['Margen'].apply(lambda x: f"{x:.2f}%")
    
    st.dataframe(
        resumen_show[['Mes_nombre', 'Ingreso', 'Gasto', 'Beneficio', 'Margen']],
        column_config={
            "Mes_nombre": "Mes",
            "Ingreso": st.column_config.NumberColumn("Ingresos", format="$%.2f"),
            "Gasto": st.column_config.NumberColumn("Gastos", format="$%.2f"),
            "Beneficio": st.column_config.NumberColumn("Beneficio", format="$%.2f"),
            "Margen": st.column_config.NumberColumn("Margen (%)", format="%.2f%%")
        },
        hide_index=True,
        use_container_width=True
    )
    
    pdf = crear_pdf(resumen, f"Resumen General {año}")
    download_pdf(pdf, f"resumen_general_{año}")

def mostrar_evolucion(df, año):
    st.title(f"📈 Evolución Mensual {año}")
    
    resumen = calcular_resumen(df, año)
    if resumen.empty:
        st.warning("No hay datos para mostrar")
        return
    
    # Excluir el total para los gráficos
    resumen_meses = resumen[resumen['Mes_nombre'] != 'Total']
    
    fig = px.line(
        resumen_meses,
        x='Mes_nombre',
        y=['Ingreso', 'Gasto', 'Beneficio'],
        title=f'Evolución Financiera {año}',
        markers=True
    )
    st.plotly_chart(fig, use_container_width=True)
    
    st.subheader(f"Análisis Detallado {año}")
    col1, col2 = st.columns(2)
    
    with col1:
        fig_ben = px.bar(
            resumen_meses,
            x='Mes_nombre',
            y='Beneficio',
            title=f'Beneficio por Mes {año}',
            color='Beneficio',
            color_continuous_scale='balance'
        )
        st.plotly_chart(fig_ben, use_container_width=True)
    
    with col2:
        fig_pie = px.pie(
            resumen_meses,
            names='Mes_nombre',
            values='Ingreso',
            title=f'Distribución de Ingresos {año}'
        )
        st.plotly_chart(fig_pie, use_container_width=True)

def mostrar_analisis_presupuesto(df, presupuesto, año):
    st.title(f"📉 Análisis Presupuestario {año}")
    
    if presupuesto is None:
        st.warning("No se encontraron datos de presupuesto")
        return
    
    resumen_real = calcular_resumen(df, año)
    resumen_presupuesto = presupuesto[presupuesto['Año'] == año]
    
    if resumen_real.empty or resumen_presupuesto.empty:
        st.warning("Datos insuficientes para comparación")
        return
    
    # Excluir el total para la comparación
    resumen_real = resumen_real[resumen_real['Mes_nombre'] != 'Total']
    
    comparacion = pd.merge(
        resumen_real,
        resumen_presupuesto,
        on=['Año', 'Mes_num'],
        suffixes=('_Real', '_Presupuesto'),
        how='left'
    )
    
    comparacion['Var_Ingreso'] = comparacion['Ingreso_Real'] - comparacion['Ingreso_Presupuesto']
    comparacion['Var_Gasto'] = comparacion['Gasto_Real'] - comparacion['Gasto_Presupuesto']
    
    st.subheader(f"Comparativo Real vs Presupuesto {año}")
    
    # Formatear números para mostrar
    comparacion_show = comparacion.copy()
    cols_monetarias = ['Ingreso_Real', 'Ingreso_Presupuesto', 'Var_Ingreso',
                      'Gasto_Real', 'Gasto_Presupuesto', 'Var_Gasto']
    
    for col in cols_monetarias:
        comparacion_show[col] = comparacion_show[col].apply(lambda x: format_number(x))
    
    st.dataframe(
        comparacion_show[
            ['Mes_nombre_Real', 'Ingreso_Real', 'Ingreso_Presupuesto', 'Var_Ingreso',
             'Gasto_Real', 'Gasto_Presupuesto', 'Var_Gasto']
        ],
        column_config={
            "Mes_nombre_Real": "Mes",
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
        x='Mes_nombre_Real',
        y=['Var_Ingreso', 'Var_Gasto'],
        barmode='group',
        title=f'Variaciones vs Presupuesto {año}'
    )
    st.plotly_chart(fig, use_container_width=True)

def mostrar_comparacion_anios(df, año_actual):
    st.title("🔍 Comparación entre Años")
    
    años_disponibles = sorted(df['Año'].unique(), reverse=True)
    
    if len(años_disponibles) < 2:
        st.warning("Se necesitan al menos 2 años de datos para comparar")
        return
    
    # Crear selectores para elegir los años a comparar
    col1, col2 = st.columns(2)
    
    with col1:
        año_base = st.selectbox(
            "Seleccione el año base",
            options=años_disponibles,
            index=0,
            key="año_base"
        )
    
    with col2:
        # Excluir el año ya seleccionado en el primer selector
        años_restantes = [a for a in años_disponibles if a != año_base]
        año_comparar = st.selectbox(
            "Seleccione el año a comparar",
            options=años_restantes,
            index=0 if len(años_restantes) > 0 else None,
            key="año_comparar"
        )
    
    if año_base == año_comparar:
        st.warning("Por favor seleccione dos años diferentes para comparar")
        return
    
    # Filtrar y calcular resúmenes para cada año
    df_base = df[df['Año'] == año_base]
    df_comparar = df[df['Año'] == año_comparar]
    
    resumen_base = calcular_resumen(df, año_base)
    resumen_comparar = calcular_resumen(df, año_comparar)
    
    # Verificar que hay datos para ambos años
    if resumen_base.empty or resumen_comparar.empty:
        st.warning("No hay suficientes datos para realizar la comparación")
        return
    
    # Obtener datos mensuales (excluyendo la fila 'Total')
    meses_base = resumen_base[resumen_base['Mes_nombre'] != 'Total']
    meses_comparar = resumen_comparar[resumen_comparar['Mes_nombre'] != 'Total']
    
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
    st.subheader(f"📊 Comparación Anual: {año_base} vs {año_comparar}")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            f"Ingresos {año_base}",
            format_number(total_ingreso_base),
            delta=f"{var_ingreso:.1f}% vs {año_comparar}",
            help=f"Comparación con {año_comparar}"
        )
    
    with col2:
        st.metric(
            f"Gastos {año_base}",
            format_number(total_gasto_base),
            delta=f"{var_gasto:.1f}% vs {año_comparar}",
            help=f"Comparación con {año_comparar}"
        )
    
    with col3:
        st.metric(
            f"Beneficio {año_base}",
            format_number(total_beneficio_base),
            delta=f"{var_beneficio:.1f}% vs {año_comparar}",
            help=f"Comparación con {año_comparar}"
        )
    
    with col4:
        st.metric(
            f"Margen {año_base}",
            f"{margen_base:.1f}%",
            delta=f"{var_margen:.1f}pp vs {año_comparar}",
            help=f"Diferencia en puntos porcentuales vs {año_comparar}"
        )
    
    st.markdown("---")
    
    # Crear DataFrame combinado para gráficos
    df_comparativo = pd.concat([
        meses_base.assign(Periodo=str(año_base)),
        meses_comparar.assign(Periodo=str(año_comparar))
    ])
    
    # Gráfico de ingresos
    fig_ingresos = px.bar(
        df_comparativo, 
        x='Mes_nombre', 
        y='Ingreso',
        color='Periodo', 
        barmode='group',
        title=f'Ingresos Mensuales: {año_base} vs {año_comparar}',
        labels={'Ingreso': 'Ingresos ($)', 'Mes_nombre': 'Mes'}
    )
    st.plotly_chart(fig_ingresos, use_container_width=True)
    
    # Gráfico de gastos
    fig_gastos = px.bar(
        df_comparativo, 
        x='Mes_nombre', 
        y='Gasto',
        color='Periodo', 
        barmode='group',
        title=f'Gastos Mensuales: {año_base} vs {año_comparar}',
        labels={'Gasto': 'Gastos ($)', 'Mes_nombre': 'Mes'}
    )
    st.plotly_chart(fig_gastos, use_container_width=True)
    
    # Gráfico de beneficios
    fig_beneficios = px.bar(
        df_comparativo, 
        x='Mes_nombre', 
        y='Beneficio',
        color='Periodo', 
        barmode='group',
        title=f'Beneficios Mensuales: {año_base} vs {año_comparar}',
        labels={'Beneficio': 'Beneficio ($)', 'Mes_nombre': 'Mes'}
    )
    st.plotly_chart(fig_beneficios, use_container_width=True)
    
    # Gráfico de margen
    fig_margen = px.line(
        df_comparativo, 
        x='Mes_nombre', 
        y='Margen',
        color='Periodo',
        title=f'Margen Mensual (%): {año_base} vs {año_comparar}',
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
        suffixes=(f'_{año_base}', f'_{año_comparar}'),
        how='outer'
    ).sort_values('Mes_num')
    
    # Calcular variaciones
    comparacion['Var_Ingreso_$'] = comparacion[f'Ingreso_{año_base}'].fillna(0) - comparacion[f'Ingreso_{año_comparar}'].fillna(0)
    comparacion['Var_Ingreso_%'] = (comparacion['Var_Ingreso_$'] / comparacion[f'Ingreso_{año_comparar}'].replace(0, np.nan)) * 100
    comparacion['Var_Gasto_$'] = comparacion[f'Gasto_{año_base}'].fillna(0) - comparacion[f'Gasto_{año_comparar}'].fillna(0)
    comparacion['Var_Gasto_%'] = (comparacion['Var_Gasto_$'] / comparacion[f'Gasto_{año_comparar}'].replace(0, np.nan)) * 100
    comparacion['Var_Beneficio_$'] = comparacion[f'Beneficio_{año_base}'].fillna(0) - comparacion[f'Beneficio_{año_comparar}'].fillna(0)
    comparacion['Var_Beneficio_%'] = (comparacion['Var_Beneficio_$'] / comparacion[f'Beneficio_{año_comparar}'].replace(0, np.nan).abs()) * 100
    comparacion['Var_Margen_pp'] = comparacion[f'Margen_{año_base}'].fillna(0) - comparacion[f'Margen_{año_comparar}'].fillna(0)
    
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
        if '_$' in col or col in [f'Ingreso_{año_base}', f'Ingreso_{año_comparar}', 
                                f'Gasto_{año_base}', f'Gasto_{año_comparar}', 
                                f'Beneficio_{año_base}', f'Beneficio_{año_comparar}']:
            comparacion[col] = comparacion[col].apply(lambda x: formatear_valor(x, True))
        elif '_%' in col or '_pp' in col or col in [f'Margen_{año_base}', f'Margen_{año_comparar}']:
            comparacion[col] = comparacion[col].apply(lambda x: formatear_valor(x, False))
    
    # Mostrar tabla
    st.dataframe(
        comparacion[[f'Mes_nombre_{año_base}',
                    f'Ingreso_{año_base}', f'Ingreso_{año_comparar}', 'Var_Ingreso_$', 'Var_Ingreso_%',
                    f'Gasto_{año_base}', f'Gasto_{año_comparar}', 'Var_Gasto_$', 'Var_Gasto_%',
                    f'Beneficio_{año_base}', f'Beneficio_{año_comparar}', 'Var_Beneficio_$', 'Var_Beneficio_%',
                    f'Margen_{año_base}', f'Margen_{año_comparar}', 'Var_Margen_pp']],
        column_config={
            f"Mes_nombre_{año_base}": "Mes",
            f"Ingreso_{año_base}": f"Ingreso {año_base}",
            f"Ingreso_{año_comparar}": f"Ingreso {año_comparar}",
            "Var_Ingreso_$": "Variación ($)",
            "Var_Ingreso_%": "Variación (%)",
            f"Gasto_{año_base}": f"Gasto {año_base}",
            f"Gasto_{año_comparar}": f"Gasto {año_comparar}",
            "Var_Gasto_$": "Variación ($)",
            "Var_Gasto_%": "Variación (%)",
            f"Beneficio_{año_base}": f"Beneficio {año_base}",
            f"Beneficio_{año_comparar}": f"Beneficio {año_comparar}",
            "Var_Beneficio_$": "Variación ($)",
            "Var_Beneficio_%": "Variación (%)",
            f"Margen_{año_base}": f"Margen {año_base} (%)",
            f"Margen_{año_comparar}": f"Margen {año_comparar} (%)",
            "Var_Margen_pp": "Variación (pp)"
        },
        hide_index=True,
        use_container_width=True,
        height=600
    )
    
    # Generar PDF
    pdf = crear_pdf(comparacion, f"Comparativo {año_base} vs {año_comparar}")
    download_pdf(pdf, f"comparativo_{año_base}_vs_{año_comparar}")

def mostrar_reporte_completo(df, año, presupuesto=None):
    st.title(f"📑 Reporte Completo {año}")
    
    resumen = calcular_resumen(df, año)
    if resumen.empty:
        st.warning("No hay datos para mostrar")
        return
    
    # Excluir el total para los gráficos
    resumen_meses = resumen[resumen['Mes_nombre'] != 'Total']
    
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
    - **Mejor mes**: {resumen_meses.loc[resumen_meses['Beneficio'].idxmax(), 'Mes_nombre']} ({format_number(resumen_meses['Beneficio'].max())})
    - **Peor mes**: {resumen_meses.loc[resumen_meses['Beneficio'].idxmin(), 'Mes_nombre']} ({format_number(resumen_meses['Beneficio'].min())})
    """)
    
    st.markdown("---")
    
    # Análisis detallado por mes
    st.subheader("📈 Análisis Detallado por Mes")
    
    fig_combinado = go.Figure()
    fig_combinado.add_trace(go.Bar(
        x=resumen_meses['Mes_nombre'],
        y=resumen_meses['Ingreso'],
        name='Ingresos',
        marker_color='#2ecc71'
    ))
    fig_combinado.add_trace(go.Bar(
        x=resumen_meses['Mes_nombre'],
        y=resumen_meses['Gasto'],
        name='Gastos',
        marker_color='#e74c3c'
    ))
    fig_combinado.add_trace(go.Scatter(
        x=resumen_meses['Mes_nombre'],
        y=resumen_meses['Beneficio'],
        name='Beneficio',
        mode='lines+markers',
        line=dict(color='#3498db', width=3),
        yaxis='y2'
    ))
    
    fig_combinado.update_layout(
        title=f'Ingresos, Gastos y Beneficio por Mes {año}',
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
        x=resumen_meses['Mes_nombre'],
        y=resumen_meses['Margen'],
        name='Margen Real',
        marker_color='#9b59b6'
    ))
    
    # Línea de objetivo (20% como ejemplo)
    fig_margen.add_shape(
        type='line',
        x0=-0.5,
        y0=20,
        x1=len(resumen_meses)-0.5,
        y1=20,
        line=dict(color='#f39c12', width=3, dash='dot'),
        name='Objetivo'
    )
    
    fig_margen.update_layout(
        title=f'Margen por Mes vs Objetivo (20%) {año}',
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
        resumen_audit[['Mes_nombre', 'Ingreso', 'Gasto', 'Beneficio', 'Margen']],
        column_config={
            "Mes_nombre": "Mes",
            "Ingreso": st.column_config.TextColumn("Ingresos"),
            "Gasto": st.column_config.TextColumn("Gastos"),
            "Beneficio": st.column_config.TextColumn("Beneficio"),
            "Margen": st.column_config.TextColumn("Margen (%)")
        },
        hide_index=True,
        use_container_width=True
    )
    
    # Análisis presupuestario si hay datos
    if presupuesto is not None:
        st.markdown("---")
        st.subheader("📉 Análisis Presupuestario")
        
        resumen_presup = presupuesto[presupuesto['Año'] == año]
        
        if not resumen_presup.empty:
            comparacion_presup = pd.merge(
                resumen_meses,
                resumen_presup,
                on=['Año', 'Mes_num'],
                suffixes=('_Real', '_Presupuesto'),
                how='left'
            )
            
            comparacion_presup['Var_Ingreso_$'] = comparacion_presup['Ingreso_Real'] - comparacion_presup['Ingreso_Presupuesto']
            comparacion_presup['Var_Gasto_$'] = comparacion_presup['Gasto_Real'] - comparacion_presup['Gasto_Presupuesto']
            comparacion_presup['Var_Beneficio_$'] = (comparacion_presup['Ingreso_Real'] - comparacion_presup['Gasto_Real']) - (comparacion_presup['Ingreso_Presupuesto'] - comparacion_presup['Gasto_Presupuesto'])
            
            comparacion_presup['Var_Ingreso_%'] = (comparacion_presup['Var_Ingreso_$'] / comparacion_presup['Ingreso_Presupuesto']) * 100
            comparacion_presup['Var_Gasto_%'] = (comparacion_presup['Var_Gasto_$'] / comparacion_presup['Gasto_Presupuesto']) * 100
            comparacion_presup['Var_Beneficio_%'] = (comparacion_presup['Var_Beneficio_$'] / (comparacion_presup['Ingreso_Presupuesto'] - comparacion_presup['Gasto_Presupuesto'])) * 100
            
            st.markdown("---")
            
            # Gráficos comparativos
            st.subheader("📊 Comparativo Real vs Presupuesto")
            
            col1, col2 = st.columns(2)
            
            with col1:
                fig_ing = px.bar(comparacion_presup, x="Mes_nombre_Real", 
                                y=["Ingreso_Real", "Ingreso_Presupuesto"], 
                                barmode="group",
                                color_discrete_map={"Ingreso_Real": "#3498db", "Ingreso_Presupuesto": "#2980b9"},
                                labels={"value": "Monto ($)", "variable": "Tipo"})
                st.plotly_chart(fig_ing, use_container_width=True)

            with col2:
                fig_gasto = px.bar(comparacion_presup, x="Mes_nombre_Real", 
                                  y=["Gasto_Real", "Gasto_Presupuesto"], 
                                  barmode="group",
                                  color_discrete_map={"Gasto_Real": "#e74c3c", "Gasto_Presupuesto": "#c0392b"},
                                  labels={"value": "Monto ($)", "variable": "Tipo"})
                st.plotly_chart(fig_gasto, use_container_width=True)

            st.markdown("---")
            
            # Tabla comparativa con colores
            st.subheader("📋 Variaciones Respecto al Presupuesto")
            
            comparacion_show = comparacion_presup[[
                "Mes_nombre_Real", 
                "Ingreso_Real", "Ingreso_Presupuesto", "Var_Ingreso_$", "Var_Ingreso_%",
                "Gasto_Real", "Gasto_Presupuesto", "Var_Gasto_$", "Var_Gasto_%",
                "Beneficio_Real", "Beneficio_Presupuesto", "Var_Beneficio_$", "Var_Beneficio_%"
            ]].copy()
            
            currency_cols = ["Ingreso_Real", "Ingreso_Presupuesto", "Var_Ingreso_$", 
                            "Gasto_Real", "Gasto_Presupuesto", "Var_Gasto_$",
                            "Beneficio_Real", "Beneficio_Presupuesto", "Var_Beneficio_$"]
            
            percent_cols = ["Var_Ingreso_%", "Var_Gasto_%", "Var_Beneficio_%"]
            
            for col in currency_cols:
                comparacion_show[col] = comparacion_show[col].apply(lambda x: format_number(x) if not pd.isna(x) else "-")
            
            for col in percent_cols:
                comparacion_show[col] = comparacion_show[col].apply(lambda x: f"{x:.2f}%" if not pd.isna(x) else "-")
            
            st.dataframe(
                comparacion_show,
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
    
    pdf = crear_pdf(resumen, f"Reporte Completo {año}")
    download_pdf(pdf, f"reporte_completo_{año}")

# Función principal
def main():
    # Cargar datos
    df, presupuesto = cargar_datos()
    
    if df.empty:
        st.error("No se pudieron cargar los datos principales")
        st.stop()

    # Sidebar - Filtros
    with st.sidebar:
        st.title("⚙️ Panel de Control")
        
        tabs = [
            "📊 Resumen General",
            "📈 Evolución Mensual", 
            "📉 Análisis Presupuestario",
            "🔍 Comparación entre Años",
            "📑 Reporte Completo"
        ]
        seccion = st.radio("Navegación", tabs)
        
        st.subheader("Filtros")
        año = st.selectbox(
            "Año",
            options=sorted(df['Año'].unique(), reverse=True),
            index=0
        )
        
        tipos = df['Tipo'].unique()
        tipos_sel = st.multiselect(
            "Tipos de transacción",
            options=tipos,
            default=tipos
        )

    # Filtrar datos basado en los filtros actuales
    df_filtrado = df[(df['Año'] == año) & (df['Tipo'].isin(tipos_sel))]
    
    # Obtener datos del año anterior para comparación (solo para Resumen General)
    año_anterior = año - 1
    df_ly = df[(df['Año'] == año_anterior) & (df['Tipo'].isin(tipos_sel))]
    resumen_ly = calcular_resumen(df_ly) if not df_ly.empty else None
    
    # Mostrar sección seleccionada con datos filtrados
    if seccion == "📊 Resumen General":
        mostrar_resumen_general(df_filtrado, año, resumen_ly)
    elif seccion == "📈 Evolución Mensual":
        mostrar_evolucion(df_filtrado, año)
    elif seccion == "📉 Análisis Presupuestario":
        mostrar_analisis_presupuesto(df_filtrado, presupuesto, año)
    elif seccion == "🔍 Comparación entre Años":
        # Para comparación usamos todos los datos (sin filtrar por año) pero sí por tipos
        mostrar_comparacion_anios(df[df['Tipo'].isin(tipos_sel)], año)
    elif seccion == "📑 Reporte Completo":
        mostrar_reporte_completo(df_filtrado, año, presupuesto)

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
