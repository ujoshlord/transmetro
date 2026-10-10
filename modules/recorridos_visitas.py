"""
Módulo de Gestión de Recorridos en Vivo, Visitas Ordenadas y Regla de Espera por Baja Ocupación.
Requerimientos: R1, R15.
"""
import time
import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from db_connection import query_df, query_one, execute_sp, execute_stmt
from components.ui_helpers import render_header, render_rule_badge
from components.charts import chart_visitas_ocupacion
from auth import has_permission

def render():
    render_header(
        title="Operación de Recorridos y Registro de Visitas",
        subtitle="Seguimiento paso a paso del viaje, orden de visitas y regla de espera extra por ocupación < 25%",
        icon="⏱️"
    )
    render_rule_badge("R1, R15", "Trazabilidad de visitas en orden estricto de la ruta; si un bus no llena el 25% de su capacidad, deberá esperar 5 minutos adicionales en la estación.")

    tab_en_curso, tab_nuevo, tab_historial = st.tabs([
        "🚍 Recorridos en Curso y Registro de Visitas",
        "🚀 Iniciar Nuevo Recorrido (Despacho)",
        "📜 Historial de Recorridos Finalizados"
    ])

    # --- PESTAÑA 1: RECORRIDOS EN CURSO ---
    with tab_en_curso:
        st.subheader("Viajes Actualmente en Tránsito")
        df_recorridos = query_df("""
            SELECT r.recorrido_id, l.codigo AS linea, b.numero_unidad, b.capacidad_maxima,
                   p.nombres || ' ' || p.apellidos AS piloto, r.sentido, r.fecha_hora_inicio,
                   (SELECT COUNT(*) FROM transmetro.visita v WHERE v.recorrido_id = r.recorrido_id AND v.estado = 'COMPLETADA') AS visitas_completadas,
                   (SELECT COUNT(*) FROM transmetro.visita v WHERE v.recorrido_id = r.recorrido_id) AS total_visitas
              FROM transmetro.recorrido r
              JOIN transmetro.linea l ON l.linea_id = r.linea_id
              JOIN transmetro.bus b ON b.bus_id = r.bus_id
              JOIN transmetro.piloto p ON p.piloto_id = r.piloto_id
             WHERE r.estado = 'EN_CURSO'
             ORDER BY r.fecha_hora_inicio DESC;
        """)

        if df_recorridos.empty:
            st.info("No hay recorridos en curso en este momento. Puede despachar uno en la pestaña 'Iniciar Nuevo Recorrido'.")
        else:
            rec_opts = {
                f"Viaje #{row['recorrido_id']}: {row['linea']} - Unidad {row['numero_unidad']} ({row['sentido']}) | Piloto: {row['piloto']} [{row['visitas_completadas']}/{row['total_visitas']} paradas]": row['recorrido_id']
                for _, row in df_recorridos.iterrows()
            }
            sel_rec_txt = st.selectbox("Seleccione el Recorrido para Monitorear o Registrar Paradas:", list(rec_opts.keys()))
            sel_rec_id = rec_opts[sel_rec_txt]

            # Información y visitas de este recorrido
            df_visitas = query_df("""
                SELECT orden, estacion, hora_llegada_programada, hora_llegada_real,
                       hora_salida_programada, hora_salida_real,
                       pasajeros_suben, pasajeros_bajan, pasajeros_a_bordo,
                       porcentaje_ocupacion, minutos_espera, espera_extra_aplicada,
                       estado_visita, estacion_id, linea_id, bus_id, capacidad_maxima,
                       personas_en_espera
                  FROM transmetro.vw_visitas_recorrido
                 WHERE recorrido_id = %s
                 ORDER BY orden;
            """, (sel_rec_id,))

            st.markdown("#### Progreso de Visitas por Estación (R1, R14, R15)")
            df_disp = df_visitas[[
                'orden', 'estacion', 'estado_visita', 'personas_en_espera',
                'pasajeros_suben', 'pasajeros_bajan', 'pasajeros_a_bordo',
                'porcentaje_ocupacion', 'minutos_espera', 'espera_extra_aplicada',
                'hora_llegada_real', 'hora_salida_real'
            ]].rename(columns={
                'orden': 'Orden',
                'estacion': 'Estación',
                'estado_visita': 'Estado',
                'personas_en_espera': 'En Espera (Andén)',
                'pasajeros_suben': 'Subieron',
                'pasajeros_bajan': 'Bajaron',
                'pasajeros_a_bordo': 'A Bordo',
                'porcentaje_ocupacion': '% Ocupación',
                'minutos_espera': 'Min. Espera',
                'espera_extra_aplicada': 'Espera Extra (R15)',
                'hora_llegada_real': 'Llegada Real',
                'hora_salida_real': 'Salida Real'
            })
            st.dataframe(df_disp, use_container_width=True, hide_index=True)

            # Gráfico de ocupación y alerta R15
            chart_visitas_ocupacion(df_visitas)

            # Acciones operativas: Registrar Llegada / Salida
            if has_permission("recorridos_visitas", "editar"):
                st.markdown("---")
                st.subheader("Registro Operativo en Estación")
                
                # Identificar la siguiente visita
                visita_en_estacion = df_visitas[df_visitas['estado_visita'] == 'EN_ESTACION']
                visita_pendiente = df_visitas[df_visitas['estado_visita'] == 'PENDIENTE']
                
                col_lle, col_sal = st.columns(2)
                
                # 1. Registrar Llegada (Solo registra salidas; personas en espera suben en automático)
                with col_lle:
                    with st.container(border=True):
                        st.write("📥 **Registrar Llegada a Estación (R1, R14, R15)**")
                        if not visita_en_estacion.empty:
                            st.warning(f"El bus se encuentra actualmente en estación: **{visita_en_estacion.iloc[0]['estacion']}**. Registre su salida antes de la siguiente llegada.")
                        elif not visita_pendiente.empty:
                            prox = visita_pendiente.iloc[0]
                            st.markdown(f"**Próxima Parada:** #{prox['orden']} - **{prox['estacion']}**")
                            st.caption(f"Llegada Programada: {prox['hora_llegada_programada']}")
                            
                            # Pasajeros a bordo actualmente (antes de llegar a esta parada)
                            visitas_previas = df_visitas[(df_visitas['orden'] < prox['orden']) & (df_visitas['estado_visita'] == 'COMPLETADA')]
                            v_previos = int(visitas_previas.iloc[-1]['pasajeros_a_bordo']) if not visitas_previas.empty else 0
                            cap_max = int(prox['capacidad_maxima'])
                            
                            # Personas en espera actuales en la estación
                            res_le = query_one("""
                                SELECT personas_en_espera FROM transmetro.linea_estacion
                                 WHERE linea_id = %s AND estacion_id = %s
                            """, (int(prox['linea_id']), int(prox['estacion_id'])))
                            personas_en_espera_db = int(res_le['personas_en_espera']) if res_le else int(prox['personas_en_espera'])

                            # Entrada 1: Personas en espera en el andén
                            personas_espera_input = st.number_input(
                                "Personas en espera en la estación (Andén):",
                                min_value=0,
                                value=personas_en_espera_db,
                                step=1,
                                key=f"esp_lle_{prox['estacion_id']}",
                                help="Cantidad de personas esperando en el andén de esta estación."
                            )

                            # Entrada 2: Pasajeros que bajan (único registro de salida del bus en llegada)
                            bajan = st.number_input(
                                "Pasajeros que bajan del bus (Salidas):",
                                min_value=0,
                                max_value=v_previos,
                                value=min(5, v_previos),
                                step=1,
                                key=f"bajan_{prox['estacion_id']}",
                                help="Pasajeros que descienden del bus en esta estación."
                            )

                            # Cálculo automático de abordaje
                            a_bordo_tras_bajan = v_previos - bajan
                            cupo_disponible = max(0, cap_max - a_bordo_tras_bajan)
                            suben_auto = min(personas_espera_input, cupo_disponible)
                            quedan_espera = personas_espera_input - suben_auto
                            nuevo_a_bordo = a_bordo_tras_bajan + suben_auto
                            nuevo_pct = round(100.0 * nuevo_a_bordo / cap_max, 1) if cap_max > 0 else 0

                            # Desglose en tiempo real
                            st.markdown(f"""
                            **Simulación en Vivo de Operación y Abordaje Automático:**
                            - 🚌 **A bordo antes de llegar:** `{v_previos}` pasajeros
                            - 🔻 **Bajan (Salidas):** `{bajan}` pasajeros
                            - 👥 **En espera en andén:** `{personas_espera_input}` personas
                            - 🔺 **Suben automáticamente:** `+{suben_auto}` personas (cupo libre: `{cupo_disponible}`)
                            - 🚍 **A bordo resultante:** `{nuevo_a_bordo}/{cap_max}` ({nuevo_pct}%)
                            - ⏳ **Quedan en espera en andén:** `{quedan_espera}` personas
                            """)

                            if nuevo_a_bordo >= cap_max:
                                st.info("⚡ **¡Capacidad máxima alcanzada (100%)!** El bus saldrá de inmediato.")
                            
                            if quedan_espera >= int(1.5 * cap_max):
                                st.warning(f"🚨 **Alerta R14 inminente:** Quedarán {quedan_espera} personas en espera (≥150% de la capacidad {cap_max}). Se activará alerta inmediata para despacho de apoyo.")

                            hora_llegada_real = st.time_input("Hora de Llegada Real:", value=datetime.now().time(), key=f"hlleg_{prox['estacion_id']}")

                            if st.button("Registrar Llegada", type="primary", key=f"btn_lle_{prox['estacion_id']}"):
                                dt_llegada = datetime.combine(datetime.today(), hora_llegada_real)
                                
                                # Actualizar personas_en_espera en linea_estacion si difiere
                                execute_stmt("""
                                    UPDATE transmetro.linea_estacion
                                       SET personas_en_espera = %s
                                     WHERE linea_id = %s AND estacion_id = %s
                                """, (personas_espera_input, int(prox['linea_id']), int(prox['estacion_id'])))

                                # 1. Registrar llegada en el SP con suben_auto y bajan
                                ok, msg, _ = execute_sp("sp_registrar_llegada", (
                                    sel_rec_id,
                                    int(prox['estacion_id']),
                                    int(suben_auto),
                                    int(bajan),
                                    dt_llegada
                                ))

                                if ok:
                                    # 2. Actualizar personas que quedan en espera en linea_estacion y visita
                                    execute_stmt("""
                                        UPDATE transmetro.linea_estacion
                                           SET personas_en_espera = %s
                                         WHERE linea_id = %s AND estacion_id = %s
                                    """, (quedan_espera, int(prox['linea_id']), int(prox['estacion_id'])))
                                    execute_stmt("""
                                        UPDATE transmetro.visita
                                           SET personas_en_espera = %s
                                         WHERE recorrido_id = %s AND estacion_id = %s
                                    """, (quedan_espera, sel_rec_id, int(prox['estacion_id'])))

                                    # 3. Si alcanza su capacidad máxima saldrá de inmediato
                                    if nuevo_a_bordo >= cap_max:
                                        ok_sal, msg_sal, _ = execute_sp("sp_registrar_salida", (
                                            sel_rec_id,
                                            int(prox['estacion_id']),
                                            0,
                                            dt_llegada
                                        ))
                                        if ok_sal:
                                            st.success(f"¡Bus al 100% de capacidad ({nuevo_a_bordo}/{cap_max})! Salida inmediata ejecutada.")
                                        else:
                                            st.warning(f"Llegada registrada, pero aviso en salida inmediata: {msg_sal}")
                                    else:
                                        st.success(f"Llegada registrada. Subieron {suben_auto} pasajeros automáticamente ({nuevo_a_bordo}/{cap_max}).")

                                    # 4. Alerta R14 si personas en espera >= 150% de la capacidad
                                    if quedan_espera >= int(1.5 * cap_max):
                                        execute_sp("sp_registrar_afluencia", (
                                            int(prox['estacion_id']),
                                            int(prox['linea_id']),
                                            int(quedan_espera),
                                            dt_llegada
                                        ))
                                        st.warning(f"🚨 ALERTA R14 GENERADA: {quedan_espera} personas en espera (≥150%). Visible en Alertas de Afluencia.")

                                    time.sleep(1)
                                    st.rerun()
                                else:
                                    st.error(f"Error al registrar llegada: {msg}")
                        else:
                            st.success("🎉 Todas las paradas del recorrido han sido completadas.")

                # 2. Registrar Salida (Solo registra entradas y campo de personas en espera para la próxima salida)
                with col_sal:
                    with st.container(border=True):
                        st.write("📤 **Registrar Salida de Estación (R14, R15)**")
                        if not visita_en_estacion.empty:
                            en_curso_vis = visita_en_estacion.iloc[0]
                            st.markdown(f"**Estación Actual:** {en_curso_vis['estacion']}")
                            
                            cap_max_sal = int(en_curso_vis['capacidad_maxima'])
                            a_bordo_actual = int(en_curso_vis['pasajeros_a_bordo'])
                            cupo_disponible_sal = max(0, cap_max_sal - a_bordo_actual)
                            
                            # Personas en espera actuales en la estación
                            res_le_sal = query_one("""
                                SELECT personas_en_espera FROM transmetro.linea_estacion
                                 WHERE linea_id = %s AND estacion_id = %s
                            """, (int(en_curso_vis['linea_id']), int(en_curso_vis['estacion_id'])))
                            personas_en_espera_sal = int(res_le_sal['personas_en_espera']) if res_le_sal else int(en_curso_vis['personas_en_espera'])

                            # Entrada 1: Pasajeros que suben durante el tiempo de espera (entradas)
                            suben_espera = st.number_input(
                                "Pasajeros que suben durante la espera (Entradas):",
                                min_value=0,
                                max_value=cupo_disponible_sal,
                                value=0,
                                step=1,
                                key=f"suben_sal_{en_curso_vis['estacion_id']}",
                                help="Pasajeros que ingresan al bus durante el tiempo de espera en la parada."
                            )

                            # Entrada 2: Personas en espera para la próxima salida (próximo bus)
                            personas_espera_nueva = st.number_input(
                                "Personas en espera en la estación (Subirán en la próxima salida):",
                                min_value=0,
                                value=personas_en_espera_sal,
                                step=1,
                                key=f"esp_sal_{en_curso_vis['estacion_id']}",
                                help="Cantidad de personas esperando en el andén para el próximo bus."
                            )

                            a_bordo_final = a_bordo_actual + suben_espera
                            pct_final = round(100.0 * a_bordo_final / cap_max_sal, 1) if cap_max_sal > 0 else 0

                            st.markdown(f"""
                            **Balance de Salida:**
                            - 🚌 **A bordo al llegar:** `{a_bordo_actual}` pasajeros
                            - 🔺 **Entradas adicionales:** `+{suben_espera}` pasajeros (cupo disponible: `{cupo_disponible_sal}`)
                            - 🚍 **A bordo final al salir:** `{a_bordo_final}/{cap_max_sal}` ({pct_final}%)
                            - ⏳ **En espera para próxima salida:** `{personas_espera_nueva}` personas
                            """)

                            if en_curso_vis['espera_extra_aplicada']:
                                st.error(f"⚠️ **REGLA R15 APLICADA:** Ocupación inferior al 25% ({en_curso_vis['porcentaje_ocupacion']}%). Espera total: **{en_curso_vis['minutos_espera']} minutos**.")
                            else:
                                st.info(f"Ocupación normal (≥25%). Espera estándar: **{en_curso_vis['minutos_espera']} minutos**.")
                                
                            st.markdown(f"**Hora Mínima Permitida de Salida:** `{en_curso_vis['hora_salida_programada']}`")

                            if personas_espera_nueva >= int(1.5 * cap_max_sal):
                                st.error(f"🚨 **Alerta R14:** {personas_espera_nueva} personas esperando (≥150% de {cap_max_sal}). Se generará alerta inmediata de sobrecupo.")

                            h_sug = datetime.now().time()
                            if en_curso_vis['hora_salida_programada']:
                                h_prog = en_curso_vis['hora_salida_programada']
                                if isinstance(h_prog, datetime):
                                    h_sug = max(h_sug, h_prog.time())
                            hora_salida_real = st.time_input("Hora de Salida Real:", value=h_sug, key=f"hsal_{en_curso_vis['estacion_id']}")

                            if st.button("Registrar Salida y Continuar Ruta", type="primary", key=f"btn_sal_{en_curso_vis['estacion_id']}"):
                                dt_salida = datetime.combine(datetime.today(), hora_salida_real)
                                ok, msg, _ = execute_sp("sp_registrar_salida", (
                                    sel_rec_id,
                                    int(en_curso_vis['estacion_id']),
                                    int(suben_espera),
                                    dt_salida
                                ))
                                if ok:
                                    # 1. Actualizar personas en espera en la estación y visita
                                    execute_stmt("""
                                        UPDATE transmetro.linea_estacion
                                           SET personas_en_espera = %s
                                         WHERE linea_id = %s AND estacion_id = %s
                                    """, (personas_espera_nueva, int(en_curso_vis['linea_id']), int(en_curso_vis['estacion_id'])))
                                    execute_stmt("""
                                        UPDATE transmetro.visita
                                           SET personas_en_espera = %s
                                         WHERE recorrido_id = %s AND estacion_id = %s
                                    """, (personas_espera_nueva, sel_rec_id, int(en_curso_vis['estacion_id'])))

                                    # 2. Generar alerta R14 si personas en espera >= 150% de la capacidad
                                    if personas_espera_nueva >= int(1.5 * cap_max_sal):
                                        execute_sp("sp_registrar_afluencia", (
                                            int(en_curso_vis['estacion_id']),
                                            int(en_curso_vis['linea_id']),
                                            int(personas_espera_nueva),
                                            dt_salida
                                        ))
                                        st.warning(f"🚨 ALERTA R14 GENERADA: {personas_espera_nueva} personas en espera (≥150%). Visible en Alertas de Afluencia.")

                                    st.success("Salida autorizada y registrada. Bus en camino a la siguiente estación.")
                                    time.sleep(1)
                                    st.rerun()
                                else:
                                    st.error(f"Bloqueo de salida (Regla R15): {msg}")
                        else:
                            st.info("No hay bus esperando salida en estación.")

    # --- PESTAÑA 2: INICIAR NUEVO RECORRIDO ---
    with tab_nuevo:
        st.subheader("Despacho de Nuevo Recorrido")
        st.info("💡 **Regla R1:** Al iniciar un recorrido se programa la secuencia estricta de visitas según el orden definido en la línea.")

        if has_permission("recorridos_visitas", "crear"):
            with st.form("form_nuevo_recorrido"):
                # Buses activos asignados a líneas operativas que no tengan recorrido en curso
                buses_disp = query_df("""
                    SELECT b.bus_id, b.numero_unidad, l.codigo AS linea_codigo, l.nombre AS linea_nombre, b.capacidad_maxima
                      FROM transmetro.bus b
                      JOIN transmetro.linea l ON l.linea_id = b.linea_id
                     WHERE b.estado = 'ACTIVO' AND l.estado = 'OPERATIVA'
                       AND b.bus_id NOT IN (SELECT bus_id FROM transmetro.recorrido WHERE estado = 'EN_CURSO')
                     ORDER BY l.codigo, b.numero_unidad;
                """)
                
                pilotos_disp = query_df("""
                    SELECT p.piloto_id, p.dpi, p.nombres || ' ' || p.apellidos AS nombre, p.vencimiento_licencia
                      FROM transmetro.piloto p
                     WHERE p.activo AND p.vencimiento_licencia >= CURRENT_DATE
                       AND p.piloto_id NOT IN (SELECT piloto_id FROM transmetro.recorrido WHERE estado = 'EN_CURSO')
                     ORDER BY p.nombres;
                """)

                rc1, rc2 = st.columns(2)
                with rc1:
                    if not buses_disp.empty:
                        b_opts = {f"{r['linea_codigo']} - Unidad {r['numero_unidad']} (Capacidad: {r['capacidad_maxima']})": r['bus_id'] for _, r in buses_disp.iterrows()}
                        sel_b_desp = st.selectbox("Bus y Línea Asignada:", list(b_opts.keys()))
                    else:
                        st.warning("No hay buses disponibles en líneas operativas sin recorrido en curso.")
                        sel_b_desp = None

                    sentido = st.selectbox("Sentido del Recorrido:", ["IDA", "VUELTA"])

                with rc2:
                    if not pilotos_disp.empty:
                        p_opts = {f"{r['nombre']} (Licencia vig: {r['vencimiento_licencia']})": r['piloto_id'] for _, r in pilotos_disp.iterrows()}
                        sel_p_desp = st.selectbox("Piloto Designado:", list(p_opts.keys()))
                    else:
                        st.warning("No hay pilotos disponibles con licencia vigente.")
                        sel_p_desp = None

                    hora_inicio = st.time_input("Hora de Inicio del Viaje:", value=datetime.now().time())

                sub_rec = st.form_submit_button("Despachar Recorrido 🚍💨", type="primary")
                if sub_rec:
                    if not sel_b_desp or not sel_p_desp:
                        st.error("Debe seleccionar un bus y un piloto disponibles.")
                    else:
                        dt_ini = datetime.combine(datetime.today(), hora_inicio)
                        ok, msg, _ = execute_sp("sp_iniciar_recorrido", (
                            b_opts[sel_b_desp],
                            p_opts[sel_p_desp],
                            sentido,
                            dt_ini
                        ))
                        if ok:
                            st.success("Recorrido iniciado con éxito. Las visitas han sido generadas en el orden de la ruta.")
                            st.rerun()
                        else:
                            st.error(f"Error al iniciar recorrido: {msg}")
        else:
            st.info("No cuenta con permisos para despachar recorridos.")

    # --- PESTAÑA 3: HISTORIAL DE RECORRIDOS ---
    with tab_historial:
        st.subheader("Historial de Recorridos Completados")
        df_hist = query_df("""
            SELECT r.recorrido_id, l.codigo AS linea, b.numero_unidad,
                   p.nombres || ' ' || p.apellidos AS piloto, r.sentido,
                   r.fecha_hora_inicio, r.fecha_hora_fin, r.estado,
                   (SELECT COUNT(*) FROM transmetro.visita v WHERE v.recorrido_id = r.recorrido_id) AS total_estaciones,
                   (SELECT COUNT(*) FROM transmetro.visita v WHERE v.recorrido_id = r.recorrido_id AND v.espera_extra_aplicada) AS paradas_con_espera_extra
              FROM transmetro.recorrido r
              JOIN transmetro.linea l ON l.linea_id = r.linea_id
              JOIN transmetro.bus b ON b.bus_id = r.bus_id
              JOIN transmetro.piloto p ON p.piloto_id = r.piloto_id
             WHERE r.estado <> 'EN_CURSO'
             ORDER BY r.fecha_hora_inicio DESC;
        """)
        st.dataframe(df_hist, use_container_width=True, hide_index=True)
