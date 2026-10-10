"""
Módulo de Monitoreo de Afluencia y Centro de Alertas de Sobrecupo.
Requerimiento: R14 (Alerta automática si afluencia >= 150% de la capacidad del bus).
"""
import streamlit as st
import pandas as pd
from db_connection import query_df, query_one, execute_sp
from components.ui_helpers import render_header, render_rule_badge
from components.charts import chart_afluencia_alerta
from auth import has_permission

def render():
    render_header(
        title="Monitoreo de Afluencia y Alertas de Sobrecupo",
        subtitle="Detección automática de saturación en estaciones (>=150% capacidad del bus) y despacho de refuerzos",
        icon="🚨"
    )
    render_rule_badge("R14", "En el momento en que una estación tiene por lo menos un 50% más de la capacidad de pasajeros del bus (>=150%), se genera una alerta inmediata para que otro bus llegue.")

    tab_alertas, tab_registro, tab_historial = st.tabs([
        "🚨 Centro de Alertas Activas (R14)",
        "📊 Registro y Simulación de Afluencia",
        "📜 Historial de Alertas Atendidas"
    ])

    # --- PESTAÑA 1: CENTRO DE ALERTAS ACTIVAS ---
    with tab_alertas:
        st.subheader("Alertas Pendientes de Atención")
        df_alertas = query_df("SELECT * FROM transmetro.vw_alertas_pendientes ORDER BY fecha_hora DESC;")
        
        if df_alertas.empty:
            st.success("✅ **Sin Alertas Activas:** Todas las estaciones operan dentro de los parámetros normales de capacidad.")
        else:
            st.error(f"🚨 **{len(df_alertas)} ALERTA(S) DE SATURACIÓN ACTIVA(S)**")
            st.dataframe(
                df_alertas[['alerta_id', 'linea', 'estacion', 'pasajeros_esperando', 'capacidad_referencia', 'porcentaje_capacidad', 'minutos_sin_atender']],
                use_container_width=True,
                hide_index=True
            )
            
            # Formulario de atención inmediata de la alerta
            st.markdown("---")
            st.subheader("🚒 Despachar Bus de Refuerzo para Atender Alerta")
            
            alerta_opts = {
                f"Alerta #{r['alerta_id']}: Estación {r['estacion']} ({r['linea']}) - {r['pasajeros_esperando']} pasajeros ({r['porcentaje_capacidad']}%)": r
                for _, r in df_alertas.iterrows()
            }
            sel_alerta_txt = st.selectbox("Seleccione Alerta a resolver:", list(alerta_opts.keys()))
            alerta_sel_row = alerta_opts[sel_alerta_txt]
            alerta_id = alerta_sel_row['alerta_id']
            
            # Mostrar medidor gráfico de la alerta seleccionada
            chart_afluencia_alerta(
                int(alerta_sel_row['pasajeros_esperando']),
                int(alerta_sel_row['capacidad_referencia']),
                alerta_sel_row['estacion']
            )

            # Buses disponibles en esa línea
            linea_alerta = alerta_sel_row['linea']
            buses_disp = query_df("""
                SELECT b.bus_id, b.numero_unidad, b.capacidad_maxima, p.nombre AS parqueo
                  FROM transmetro.bus b
                  JOIN transmetro.linea l ON l.linea_id = b.linea_id
                  JOIN transmetro.parqueo p ON p.parqueo_id = b.parqueo_id
                 WHERE l.codigo = %s AND b.estado = 'ACTIVO'
                 ORDER BY b.numero_unidad;
            """, (linea_alerta,))

            if not buses_disp.empty:
                b_map = {f"Unidad {r['numero_unidad']} (Cap: {r['capacidad_maxima']}) - Ubicada en {r['parqueo']}": r['bus_id'] for _, r in buses_disp.iterrows()}
                bus_refuerzo_sel = st.selectbox("Seleccione Bus de Refuerzo a Despachar:", list(b_map.keys()))
                obs = st.text_input("Observación del despacho:", value="Se despacha unidad de refuerzo para mitigar sobrecupo en estación.")

                col_b1, col_b2 = st.columns(2)
                with col_b1:
                    if st.button("Despachar Refuerzo y Cerrar Alerta 🚌💨", type="primary", disabled=not has_permission("alertas_afluencia", "editar")):
                        ok, msg, _ = execute_sp("sp_atender_alerta", (alerta_id, b_map[bus_refuerzo_sel], obs))
                        if ok:
                            st.success(f"Alerta #{alerta_id} atendida exitosamente con bus {bus_refuerzo_sel}.")
                            st.rerun()
                        else:
                            st.error(f"Error al atender alerta: {msg}")
                with col_b2:
                    if st.button("Descartar Alerta", type="secondary", disabled=not has_permission("alertas_afluencia", "editar")):
                        ok, msg, _ = execute_sp("sp_descartar_alerta", (alerta_id, "Descartada por normalización del flujo."))
                        if ok:
                            st.info(f"Alerta #{alerta_id} descartada.")
                            st.rerun()
                        else:
                            st.error(f"Error: {msg}")
            else:
                st.warning(f"No hay buses activos asignados a la línea {linea_alerta} para despachar de refuerzo.")

    # --- PESTAÑA 2: REGISTRO Y SIMULACIÓN DE AFLUENCIA ---
    with tab_registro:
        st.subheader("Registro de Conteo de Pasajeros en Estación")
        st.markdown(
            """
            *Prueba en vivo del requerimiento R14:*
            Al ingresar un conteo de pasajeros en espera que supere el **150%** de la capacidad del bus
            (ej. si el bus tiene capacidad de 80, una afluencia de 120 o más),
            el motor de base de datos **generará de inmediato la alerta** mediante el trigger `trg_afluencia_alerta`.
            """
        )

        with st.form("form_reg_afluencia"):
            ac1, ac2 = st.columns(2)
            with ac1:
                # Estaciones de líneas operativas
                estaciones_linea = query_df("""
                    SELECT le.linea_id, le.estacion_id, l.codigo AS linea_codigo, e.nombre AS estacion_nombre
                      FROM transmetro.linea_estacion le
                      JOIN transmetro.linea l ON l.linea_id = le.linea_id
                      JOIN transmetro.estacion e ON e.estacion_id = le.estacion_id
                     ORDER BY l.codigo, le.orden;
                """)
                est_lin_dict = {f"Línea {r['linea_codigo']} - Estación {r['estacion_nombre']}": (r['linea_id'], r['estacion_id']) for _, r in estaciones_linea.iterrows()}
                sel_el = st.selectbox("Estación y Línea:", list(est_lin_dict.keys()))
                
            with ac2:
                pasajeros_in = st.number_input("Cantidad de Pasajeros en Espera:", min_value=0, max_value=1000, value=125, step=5)
            
            sub_afl = st.form_submit_button("Registrar Conteo de Pasajeros", type="primary")
            if sub_afl:
                l_id, e_id = est_lin_dict[sel_el]
                ok, msg, _ = execute_sp("sp_registrar_afluencia", (e_id, l_id, int(pasajeros_in)))
                if ok:
                    st.success(f"Afluencia registrada ({pasajeros_in} personas). El sistema evaluó automáticamente el umbral de sobrecupo.")
                    st.rerun()
                else:
                    st.error(f"Error al registrar afluencia: {msg}")

    # --- PESTAÑA 3: HISTORIAL DE ALERTAS ---
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
