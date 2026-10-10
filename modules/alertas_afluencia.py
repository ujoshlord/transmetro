"""
Módulo de Monitoreo de Afluencia y Centro de Alertas en Tiempo Real.
Requerimiento: R14 (Alerta automática si afluencia >= 150% de la capacidad del bus).
Monitoreo puro con auto-actualización cada 5 segundos que se detiene ante alertas activas.
"""
import time
import streamlit as st
import pandas as pd
from datetime import datetime
from db_connection import query_df, query_one, execute_sp
from components.ui_helpers import render_header, render_rule_badge
from components.charts import chart_afluencia_alerta
from auth import has_permission

def render():
    render_header(
        title="Centro de Monitoreo de Afluencia y Alertas en Tiempo Real",
        subtitle="Monitoreo continuo cada 5 segundos; detección automática de sobrecupo (>=150%) y despacho de apoyo",
        icon="🚨"
    )
    render_rule_badge("R14", "En el momento en que una estación tiene por lo menos un 50% más de la capacidad de pasajeros del bus (>=150%), se genera una alerta inmediata. El monitoreo se detiene al detectar una alerta activa para permitir el despacho de apoyo si existen buses disponibles.")

    tab_alertas, tab_historial = st.tabs([
        "🚨 Centro de Alertas en Vivo (Monitoreo)",
        "📜 Historial de Alertas Atendidas"
    ])

    # --- PESTAÑA 1: CENTRO DE ALERTAS EN VIVO ---
    with tab_alertas:
        st.subheader("Monitoreo Operativo en Tiempo Real")

        # Consultar alertas pendientes en la base de datos
        df_alertas = query_df("SELECT * FROM transmetro.vw_alertas_pendientes ORDER BY fecha_hora DESC;")
        hay_alertas = not df_alertas.empty

        if not hay_alertas:
            # Estado normal: auto-actualización cada 5 segundos
            st.success("✅ **Red en Operación Normal:** Todas las estaciones operan dentro de los parámetros seguros de afluencia.")
            
            c_mon1, c_mon2 = st.columns([3, 1])
            with c_mon1:
                st.info("🟢 **Monitoreo en vivo activo:** Verificando el estado de la red cada 5 segundos automáticamente...")
            with c_mon2:
                if st.button("Actualizar Ahora 🔄", use_container_width=True):
                    st.rerun()

            # Vista general rápida de afluencia actual en estaciones
            st.markdown("#### Estado Actual de Pasajeros en Espera por Estación")
            df_estaciones_afluencia = query_df("""
                SELECT l.codigo AS linea, e.nombre AS estacion,
                       le.personas_en_espera,
                       ROUND(AVG(b.capacidad_maxima))::INT AS capacidad_bus_referencia,
                       ROUND(1.5 * AVG(b.capacidad_maxima))::INT AS umbral_alerta_150pct,
                       CASE 
                           WHEN le.personas_en_espera >= 1.5 * AVG(b.capacidad_maxima) THEN '🚨 SOBRECUPO'
                           WHEN le.personas_en_espera >= AVG(b.capacidad_maxima) THEN '⚠️ ALTA'
                           ELSE '🟢 NORMAL'
                       END AS nivel_congestion
                  FROM transmetro.linea_estacion le
                  JOIN transmetro.linea l ON l.linea_id = le.linea_id
                  JOIN transmetro.estacion e ON e.estacion_id = le.estacion_id
                  LEFT JOIN transmetro.bus b ON b.linea_id = l.linea_id AND b.estado = 'ACTIVO'
                 GROUP BY l.codigo, e.nombre, le.personas_en_espera, le.orden
                 ORDER BY l.codigo, le.orden;
            """)
            st.dataframe(df_estaciones_afluencia, use_container_width=True, hide_index=True)

            # Auto-actualización cada 5 segundos (se detendrá automáticamente en cuanto surja una alerta)
            time.sleep(5)
            st.rerun()

        else:
            # Estado con alerta en curso: SE DETIENE LA AUTO-ACTUALIZACIÓN
            st.error(f"🚨 **ALERTA CRÍTICA: Se detectaron {len(df_alertas)} estación(es) en estado de sobrecupo (>=150%).**")
            st.warning("⏸️ **Monitoreo automático detenido:** Hay alertas activas que requieren atención operativa inmediata.")

            st.dataframe(
                df_alertas[['alerta_id', 'linea', 'estacion', 'pasajeros_esperando', 'capacidad_referencia', 'porcentaje_capacidad', 'minutos_sin_atender']],
                use_container_width=True,
                hide_index=True
            )

            st.markdown("---")
            st.subheader("🚒 Despacho de Apoyo para Mitigar Sobrecupo")

            alerta_opts = {
                f"Alerta #{r['alerta_id']}: Estación {r['estacion']} ({r['linea']}) - {r['pasajeros_esperando']} personas esperando ({r['porcentaje_capacidad']}%)": r
                for _, r in df_alertas.iterrows()
            }
            sel_alerta_txt = st.selectbox("Seleccione Alerta a resolver:", list(alerta_opts.keys()))
            alerta_sel_row = alerta_opts[sel_alerta_txt]
            alerta_id = int(alerta_sel_row['alerta_id'])
            linea_alerta = alerta_sel_row['linea']

            # Gráfico de saturación
            chart_afluencia_alerta(
                int(alerta_sel_row['pasajeros_esperando']),
                int(alerta_sel_row['capacidad_referencia']),
                alerta_sel_row['estacion']
            )

            # 1. Consultar buses disponibles para enviar apoyo
            buses_disp = query_df("""
                SELECT b.bus_id, b.numero_unidad, b.capacidad_maxima, p.nombre AS parqueo
                  FROM transmetro.bus b
                  JOIN transmetro.linea l ON l.linea_id = b.linea_id
                  JOIN transmetro.parqueo p ON p.parqueo_id = b.parqueo_id
                 WHERE l.codigo = %s AND b.estado = 'ACTIVO'
                   AND b.bus_id NOT IN (SELECT bus_id FROM transmetro.recorrido WHERE estado = 'EN_CURSO')
                 ORDER BY b.numero_unidad;
            """, (linea_alerta,))

            # 2. Consultar pilotos disponibles con licencia vigente
            pilotos_disp = query_df("""
                SELECT p.piloto_id, p.nombres || ' ' || p.apellidos AS nombre
                  FROM transmetro.piloto p
                 WHERE p.activo AND p.vencimiento_licencia >= CURRENT_DATE
                   AND p.piloto_id NOT IN (SELECT piloto_id FROM transmetro.recorrido WHERE estado = 'EN_CURSO')
                 ORDER BY p.nombres;
            """)

            # Validación estricta: Solo se enviará apoyo si existen buses disponibles
            if buses_disp.empty:
                st.error(f"❌ **No es posible enviar apoyo:** No existen buses disponibles en la línea {linea_alerta} en este momento. Todas las unidades asignadas se encuentran en viaje activo.")
            elif pilotos_disp.empty:
                st.error("❌ **No es posible enviar apoyo:** No existen pilotos disponibles en turno sin viaje en curso.")
            else:
                st.success(f"🚌 Se encontraron **{len(buses_disp)} bus(es)** y **{len(pilotos_disp)} piloto(s)** disponibles para enviar apoyo.")

                with st.container(border=True):
                    col_ap1, col_ap2 = st.columns(2)
                    with col_ap1:
                        b_opts = {f"Unidad {r['numero_unidad']} (Cap: {r['capacidad_maxima']}) - Predio {r['parqueo']}": r['bus_id'] for _, r in buses_disp.iterrows()}
                        sel_bus_apoyo = st.selectbox("Seleccione Bus de Apoyo a Despachar:", list(b_opts.keys()))
                        sentido_apoyo = st.selectbox("Sentido del Viaje de Apoyo:", ["IDA", "VUELTA"])
                    with col_ap2:
                        p_opts = {r['nombre']: r['piloto_id'] for _, r in pilotos_disp.iterrows()}
                        sel_piloto_apoyo = st.selectbox("Piloto Designado:", list(p_opts.keys()))
                        obs = st.text_input("Observación del Despacho:", value=f"Apoyo enviado por saturación en estación {alerta_sel_row['estacion']}")

                    if st.button("🚨 Enviar Apoyo Inmediato 🚌💨", type="primary", use_container_width=True, disabled=not has_permission("alertas_afluencia", "editar")):
                        bus_id_target = b_opts[sel_bus_apoyo]
                        piloto_id_target = p_opts[sel_piloto_apoyo]

                        try:
                            # 1. Iniciar el nuevo recorrido (se refleja inmediatamente en los viajes)
                            execute_sp("sp_iniciar_recorrido", (
                                bus_id_target,
                                piloto_id_target,
                                sentido_apoyo,
                                datetime.now()
                            ))

                            # Obtener el ID del nuevo recorrido generado
                            res_rec = query_one("""
                                SELECT recorrido_id FROM transmetro.recorrido
                                 WHERE bus_id = %s AND estado = 'EN_CURSO';
                            """, (bus_id_target,))
                            nuevo_rec_id = res_rec['recorrido_id'] if res_rec else "N/A"

                            # 2. Atender y cerrar la alerta vinculándola al bus despachado
                            execute_sp("sp_atender_alerta", (
                                alerta_id,
                                bus_id_target,
                                f"Apoyo despachado exitosamente en Viaje #{nuevo_rec_id} ({obs})"
                            ))

                            st.success(f"🎉 **¡Apoyo enviado exitosamente!** Se despachó el bus **{sel_bus_apoyo}** con el **Viaje #{nuevo_rec_id}**. Este nuevo recorrido ya se encuentra en tránsito y está reflejado en el módulo de Recorridos y Operación.")
                            time.sleep(2)
                            st.rerun()

                        except Exception as ex:
                            st.error(f"Error al despachar apoyo: {ex}")

    # --- PESTAÑA 2: HISTORIAL DE ALERTAS ATENDIDAS ---
    with tab_historial:
        st.subheader("Historial de Alertas Atendidas y Descartadas")
        df_hist_alertas = query_df("""
            SELECT a.alerta_id, a.fecha_hora, l.codigo AS linea, e.nombre AS estacion,
                   a.pasajeros_esperando, a.capacidad_referencia, a.porcentaje_capacidad,
                   a.estado, b.numero_unidad AS bus_despachado, a.fecha_atencion, a.observacion
              FROM transmetro.alerta a
              JOIN transmetro.linea l ON l.linea_id = a.linea_id
              JOIN transmetro.estacion e ON e.estacion_id = a.estacion_id
              LEFT JOIN transmetro.bus b ON b.bus_id = a.bus_asignado_id
             WHERE a.estado <> 'PENDIENTE'
             ORDER BY a.fecha_hora DESC;
        """)
        st.dataframe(df_hist_alertas, use_container_width=True, hide_index=True)
