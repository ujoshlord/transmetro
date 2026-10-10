"""
Módulo de Gestión de Recorridos en Vivo, Visitas Ordenadas y Regla de Espera por Baja Ocupación.
Requerimientos: R1, R15.
"""
import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from db_connection import query_df, query_one, execute_sp
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
                       estado_visita, estacion_id, capacidad_maxima
                  FROM transmetro.vw_visitas_recorrido
                 WHERE recorrido_id = %s
                 ORDER BY orden;
            """, (sel_rec_id,))

            st.markdown("#### Progreso de Visitas por Estación (R1)")
            st.dataframe(
                df_visitas[['orden', 'estacion', 'estado_visita', 'hora_llegada_programada', 'hora_llegada_real', 'pasajeros_suben', 'pasajeros_bajan', 'pasajeros_a_bordo', 'porcentaje_ocupacion', 'minutos_espera', 'espera_extra_aplicada']],
                use_container_width=True,
                hide_index=True
            )

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
                
                # 1. Registrar Llegada
                with col_lle:
                    with st.container(border=True):
                        st.write("📥 **Registrar Llegada a Estación (R1, R15)**")
                        if not visita_en_estacion.empty:
                            st.warning(f"El bus se encuentra actualmente en estación: **{visita_en_estacion.iloc[0]['estacion']}**. Registre su salida antes de la siguiente llegada.")
                        elif not visita_pendiente.empty:
                            prox = visita_pendiente.iloc[0]
                            st.markdown(f"**Próxima Parada:** #{prox['orden']} - **{prox['estacion']}**")
                            st.markdown(f"*Llegada Programada:* {prox['hora_llegada_programada']}")
                            
                            suben = st.number_input("Pasajeros que Suben:", min_value=0, max_value=prox['capacidad_maxima'], value=12, step=1, key="suben_in")
                            bajan = st.number_input("Pasajeros que Bajan:", min_value=0, max_value=prox['capacidad_maxima'], value=0, step=1, key="bajan_in")
                            
                            hora_llegada_real = st.time_input("Hora de Llegada Real:", value=datetime.now().time(), key="hlleg_in")
                            
                            if st.button("Registrar Llegada", type="primary"):
                                dt_llegada = datetime.combine(datetime.today(), hora_llegada_real)
                                ok, msg, _ = execute_sp("sp_registrar_llegada", (
                                    sel_rec_id,
                                    int(prox['estacion_id']),
                                    int(suben),
                                    int(bajan),
                                    dt_llegada
                                ))
                                if ok:
                                    st.success(f"Llegada registrada. El sistema evaluó la ocupación y calculó los tiempos de espera.")
                                    st.rerun()
                                else:
                                    st.error(f"Error al registrar llegada: {msg}")
                        else:
                            st.success("🎉 Todas las paradas del recorrido han sido completadas.")

                # 2. Registrar Salida
                with col_sal:
                    with st.container(border=True):
                        st.write("📤 **Registrar Salida de Estación (R15)**")
                        if not visita_en_estacion.empty:
                            en_curso_vis = visita_en_estacion.iloc[0]
                            st.markdown(f"**Estación Actual:** {en_curso_vis['estacion']}")
                            st.markdown(f"**Ocupación:** {en_curso_vis['porcentaje_ocupacion']}% ({en_curso_vis['pasajeros_a_bordo']} pasajeros)")
                            
                            if en_curso_vis['espera_extra_aplicada']:
                                st.error(f"⚠️ **REGLA R15 APLICADA:** Ocupación inferior al 25%. Espera total: **{en_curso_vis['minutos_espera']} minutos**.")
                            else:
                                st.info(f"Ocupación normal (>=25%). Espera estándar: **{en_curso_vis['minutos_espera']} minutos**.")
                                
                            st.markdown(f"**Hora Mínima Permitida de Salida:** `{en_curso_vis['hora_salida_programada']}`")
                            
                            hora_salida_real = st.time_input("Hora de Salida Real:", value=datetime.now().time(), key="hsal_in")
                            
                            if st.button("Registrar Salida y Continuar Ruta", type="primary"):
                                dt_salida = datetime.combine(datetime.today(), hora_salida_real)
                                ok, msg, _ = execute_sp("sp_registrar_salida", (
                                    sel_rec_id,
                                    int(en_curso_vis['estacion_id']),
                                    dt_salida
                                ))
                                if ok:
                                    st.success("Salida autorizada y registrada. Bus en camino a la siguiente estación.")
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
