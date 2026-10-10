"""
Componentes de visualización gráfica analítica interactiva con Plotly.
Representaciones visuales para reglas R1, R5, R6, R10, R12, R13, R14, R15.
"""
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import streamlit as st

def chart_regla_buses_linea(df_buses_linea: pd.DataFrame):
    """
    R5: Gráfico comparativo de la regla N <= buses <= 2N.
    Muestra para cada línea el mínimo (N), buses actuales y máximo (2N).
    """
    if df_buses_linea.empty:
        st.info("No hay datos de líneas para graficar.")
        return

    fig = go.Figure()
    
    # Líneas de referencia
    fig.add_trace(go.Bar(
        name='Estaciones (Mínimo N)',
        x=df_buses_linea['codigo'],
        y=df_buses_linea['minimo_buses'],
        marker_color='#95a5a6',
        opacity=0.65
    ))
    
    # Buses asignados (color verde si cumple, rojo si viola la regla)
    colores_buses = [
        '#2ecc71' if cumple else '#e74c3c'
        for cumple in df_buses_linea['cumple_regla']
    ]
    
    fig.add_trace(go.Bar(
        name='Buses Asignados',
        x=df_buses_linea['codigo'],
        y=df_buses_linea['buses'],
        marker_color=colores_buses,
        text=df_buses_linea['buses'],
        textposition='auto'
    ))
    
    fig.add_trace(go.Bar(
        name='Máximo Permitido (2N)',
        x=df_buses_linea['codigo'],
        y=df_buses_linea['maximo_buses'],
        marker_color='#34495e',
        opacity=0.45
    ))
    
    fig.update_layout(
        title="<b>Regla R5: Cantidad de Buses Asignados vs Límites [N, 2N] por Línea</b>",
        barmode='group',
        xaxis_title="Línea",
        yaxis_title="Cantidad de Unidades",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        template="plotly_white",
        height=380,
        margin=dict(l=40, r=20, t=60, b=40)
    )
    
    st.plotly_chart(fig, use_container_width=True)

def chart_distancia_acumulada_linea(df_ruta: pd.DataFrame, linea_codigo: str):
    """
    R12 y R13: Perfil de distancia acumulada a lo largo de las estaciones de la línea.
    """
    if df_ruta.empty:
        st.info("No hay datos de ruta disponibles.")
        return

    fig = go.Figure()
    
    fig.add_trace(go.Scatter(
        x=df_ruta['estacion_nombre'],
        y=df_ruta['distancia_acumulada_km'],
        mode='lines+markers+text',
        name='Distancia Acumulada (km)',
        line=dict(color='#2980b9', width=3, shape='spline'),
        marker=dict(size=9, color='#e67e22', symbol='diamond'),
        text=[f"{d:.2f} km" for d in df_ruta['distancia_acumulada_km']],
        textposition='top center'
    ))
    
    fig.update_layout(
        title=f"<b>R12/R13: Perfil de Ruta y Distancia Acumulada - {linea_codigo}</b>",
        xaxis_title="Estaciones en Orden de Recorrido",
        yaxis_title="Distancia Acumulada (km)",
        template="plotly_white",
        height=350,
        margin=dict(l=40, r=20, t=50, b=60)
    )
    
    st.plotly_chart(fig, use_container_width=True)

def chart_ocupacion_parqueos(df_parqueos: pd.DataFrame):
    """
    R6 y R7: Visualización de capacidad vs ocupación en parqueos.
    """
    if df_parqueos.empty:
        st.info("No hay datos de parqueos disponibles.")
        return

    fig = go.Figure()
    
    fig.add_trace(go.Bar(
        name='Buses Asignados',
        x=df_parqueos['nombre'],
        y=df_parqueos['buses_asignados'],
        marker_color='#3498db',
        text=df_parqueos['buses_asignados'],
        textposition='auto'
    ))
    
    fig.add_trace(go.Bar(
        name='Espacios Libres',
        x=df_parqueos['nombre'],
        y=df_parqueos['espacios_disponibles'],
        marker_color='#2ecc71',
        text=df_parqueos['espacios_disponibles'],
        textposition='auto'
    ))
    
    fig.update_layout(
        title="<b>R6/R7: Ocupación y Capacidad de Parqueos de Estaciones</b>",
        barmode='stack',
        xaxis_title="Parqueo / Predio",
        yaxis_title="Cantidad de Buses",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        template="plotly_white",
        height=350,
        margin=dict(l=40, r=20, t=60, b=40)
    )
    
    st.plotly_chart(fig, use_container_width=True)

def chart_afluencia_alerta(pasajeros: int, capacidad_ref: int, estacion_nombre: str = ""):
    """
    R14: Medidor / Comparativa de afluencia vs umbral del 150%.
    """
    umbral = capacidad_ref * 1.5
    porcentaje = round(100.0 * pasajeros / capacidad_ref, 1) if capacidad_ref > 0 else 0
    alerta_activa = pasajeros >= umbral

    fig = go.Figure(go.Indicator(
        mode="gauge+number+delta",
        value=pasajeros,
        delta={'reference': umbral, 'increasing': {'color': "#c0392b"}},
        number={'suffix': f" ({porcentaje}%)"},
        title={'text': f"<b>R14: Pasajeros en Espera - {estacion_nombre}</b><br><span style='font-size:0.8em;color:gray'>Capacidad Bus: {capacidad_ref} | Alerta (150%): {int(umbral)}</span>"},
        gauge={
            'axis': {'range': [None, max(umbral * 1.3, pasajeros * 1.2)]},
            'bar': {'color': "#e74c3c" if alerta_activa else "#27ae60"},
            'steps': [
                {'range': [0, capacidad_ref], 'color': "#e8f8f5"},
                {'range': [capacidad_ref, umbral], 'color': "#fef9e7"},
                {'range': [umbral, max(umbral * 1.3, pasajeros * 1.2)], 'color': "#fadbd8"}
            ],
            'threshold': {
                'line': {'color': "red", 'width': 4},
                'thickness': 0.75,
                'value': umbral
            }
        }
    ))
    
    fig.update_layout(height=300, margin=dict(l=30, r=30, t=50, b=20))
    st.plotly_chart(fig, use_container_width=True)

def chart_visitas_ocupacion(df_visitas: pd.DataFrame):
    """
    R15: Ocupación en cada visita y verificación de regla < 25%.
    """
    if df_visitas.empty:
        st.info("No hay visitas para graficar.")
        return

    fig = go.Figure()
    
    colores = [
        '#e74c3c' if row['espera_extra_aplicada'] else '#2ecc71'
        for _, row in df_visitas.iterrows()
    ]
    
    fig.add_trace(go.Bar(
        x=df_visitas['estacion'],
        y=df_visitas['porcentaje_ocupacion'],
        marker_color=colores,
        text=[f"{p:.1f}% (+{row['minutos_espera']}m)" if pd.notnull(p) else "N/A" for p, row in zip(df_visitas['porcentaje_ocupacion'], df_visitas.to_dict('records'))],
        textposition='auto',
        name='Ocupación Real (%)'
    ))
    
    # Línea de umbral del 25%
    fig.add_hline(
        y=25,
        line_dash="dot",
        line_color="#e67e22",
        annotation_text="Umbral Mínimo 25% (R15: +5 min extra si es menor)",
        annotation_position="bottom right"
    )
    
    fig.update_layout(
        title="<b>R15: Ocupación de Pasajeros por Estación y Detección de Espera Extra</b>",
        xaxis_title="Estación de Parada",
        yaxis_title="Porcentaje de Ocupación (%)",
        yaxis=dict(range=[0, 110]),
        template="plotly_white",
        height=360,
        margin=dict(l=40, r=20, t=50, b=40)
    )
    
    st.plotly_chart(fig, use_container_width=True)
