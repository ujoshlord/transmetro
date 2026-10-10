"""
Módulo de Dashboard Ejecutivo y Monitoreo Global del Sistema Transmetro.
"""
import streamlit as st
import pandas as pd
from db_connection import query_df, query_one
from components.ui_helpers import render_header, render_metric_card
from components.maps import render_transmetro_map
from components.charts import chart_regla_buses_linea, chart_ocupacion_parqueos

def render():
    render_header(
        title="Panel de Control y Monitoreo General",
        subtitle="Métricas operativas en tiempo real, estado de la red y cumplimiento de reglas",
        icon="📊"
    )

    # 1. Consultar métricas globales
    kpis = query_one("""
        SELECT
            (SELECT COUNT(*) FROM transmetro.linea WHERE estado = 'OPERATIVA') AS lineas_operativas,
            (SELECT COUNT(*) FROM transmetro.linea) AS total_lineas,
            (SELECT COUNT(*) FROM transmetro.estacion WHERE activa) AS total_estaciones,
            (SELECT COUNT(*) FROM transmetro.bus WHERE estado = 'ACTIVO') AS buses_activos,
            (SELECT COUNT(*) FROM transmetro.acceso WHERE activo) AS accesos_activos,
            (SELECT COUNT(DISTINCT guardia_id) FROM transmetro.asignacion_guardia WHERE fecha_fin IS NULL) AS guardias_activos,
            (SELECT COUNT(*) FROM transmetro.alerta WHERE estado = 'PENDIENTE') AS alertas_pendientes,
            (SELECT COUNT(*) FROM transmetro.recorrido WHERE estado = 'EN_CURSO') AS recorridos_en_curso;
    """)

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        render_metric_card(
            "Líneas Operativas",
            f"{kpis['lineas_operativas']} / {kpis['total_lineas']}",
            "Rutas configuradas",
            "#2980b9"
        )
    with c2:
        render_metric_card(
            "Estaciones Activas",
            str(kpis['total_estaciones']),
            f"{kpis['accesos_activos']} accesos totales",
            "#27ae60"
        )
    with c3:
        render_metric_card(
            "Flota Activa",
            str(kpis['buses_activos']),
            f"{kpis['recorridos_en_curso']} viajes en curso",
            "#f39c12"
        )
    with c4:
        color_alerta = "#c0392b" if kpis['alertas_pendientes'] > 0 else "#27ae60"
        render_metric_card(
            "Alertas Sobrecupo (R14)",
            str(kpis['alertas_pendientes']),
            "Estaciones >=150% cap." if kpis['alertas_pendientes'] > 0 else "Operación normal",
            color_alerta
        )

    # 2. Alertas pendientes destacadas (R14)
    if kpis['alertas_pendientes'] > 0:
        st.error(f"🚨 **ATENCIÓN: Existen {kpis['alertas_pendientes']} alerta(s) de sobrecupo pendiente(s) por atender.**")
        df_alertas = query_df("SELECT * FROM transmetro.vw_alertas_pendientes;")
        st.dataframe(
            df_alertas[['alerta_id', 'linea', 'estacion', 'pasajeros_esperando', 'capacidad_referencia', 'porcentaje_capacidad', 'minutos_sin_atender']],
            use_container_width=True,
            hide_index=True
        )

    st.markdown("---")

    # 3. Mapa de la Red Georreferenciada
    st.subheader("🗺️ Red Geográfica de Transporte Transmetro")
    render_transmetro_map(height=480)

    # 4. Gráficos de Cumplimiento Operativo
    col_g1, col_g2 = st.columns(2)
    
    with col_g1:
        st.subheader("🚌 Cumplimiento de Regla de Flota (R5)")
        df_buses_linea = query_df("SELECT * FROM transmetro.vw_buses_linea;")
        chart_regla_buses_linea(df_buses_linea)
        
    with col_g2:
        st.subheader("🅿️ Ocupación de Parqueos (R6 / R7)")
        df_parqueos = query_df("SELECT * FROM transmetro.vw_parqueo_ocupacion;")
        chart_ocupacion_parqueos(df_parqueos)

