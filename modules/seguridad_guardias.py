"""
Módulo de Seguridad y Asignación de Guardias por Acceso.
Requerimiento: R10.
"""
import streamlit as st
import pandas as pd
from db_connection import query_df, execute_sp, execute_stmt
from components.ui_helpers import render_header, render_rule_badge
from auth import has_permission

def render():
    render_header(
        title="Seguridad y Control de Guardias por Acceso",
        subtitle="Monitoreo de cobertura de seguridad por acceso, turnos y personal asignado",
        icon="👮"
    )
    render_rule_badge("R10", "Cada acceso activo de cada estación debe contar por lo menos con un guardia de seguridad asignado.")

    tab_cobertura, tab_asignar, tab_guardias = st.tabs([
        "🛡️ Cobertura por Acceso (R10)",
        "📋 Asignar / Finalizar Turno",
        "👥 Catálogo de Guardias"
    ])

    # --- PESTAÑA 1: COBERTURA POR ACCESO (R10) ---
    with tab_cobertura:
        st.subheader("Auditoría de Cumplimiento de Guardias por Acceso")
        df_cobertura = query_df("SELECT * FROM transmetro.vw_guardias_por_acceso ORDER BY estacion, acceso_codigo;")
        
        sin_guardia = len(df_cobertura[~df_cobertura['cumple_regla']])
        if sin_guardia > 0:
            st.error(f"⚠️ **ALERTA DE SEGURIDAD:** Existen {sin_guardia} acceso(s) sin guardia de seguridad asignado.")
        else:
            st.success("✅ **COBERTURA TOTAL:** El 100% de los accesos cuenta con al menos un guardia asignado.")

        st.dataframe(
            df_cobertura[['estacion', 'acceso_codigo', 'acceso', 'guardias_vigentes', 'guardias', 'cumple_regla']],
            use_container_width=True,
            hide_index=True
        )

    # --- PESTAÑA 2: ASIGNAR / FINALIZAR TURNO ---
    with tab_asignar:
        st.subheader("Gestión Operativa de Turnos y Puestos")
        col_asig, col_fin = st.columns(2)
        
        with col_asig:
            with st.container(border=True):
                st.write("➕ **Asignar Guardia a Acceso**")
                
                guardias = query_df("SELECT guardia_id, dpi, nombres || ' ' || apellidos AS nombre FROM transmetro.guardia WHERE activo ORDER BY nombres;")
                g_dict = {f"{r['nombre']} (DPI: {r['dpi']})": r['guardia_id'] for _, r in guardias.iterrows()}
                sel_g = st.selectbox("Seleccione Guardia:", list(g_dict.keys()), key="sel_g_asig")
                
                accesos = query_df("""
                    SELECT a.acceso_id, a.codigo, a.nombre, e.nombre AS estacion
                      FROM transmetro.acceso a
                      JOIN transmetro.estacion e ON e.estacion_id = a.estacion_id
                     WHERE a.activo
                     ORDER BY e.nombre, a.codigo;
                """)
                acc_dict = {f"{r['estacion']} - {r['codigo']}: {r['nombre']}": r['acceso_id'] for _, r in accesos.iterrows()}
                sel_acc = st.selectbox("Acceso Destino:", list(acc_dict.keys()), key="sel_acc_asig")
                
                turno = st.selectbox("Turno de Asignación:", ["MATUTINO", "VESPERTINO", "NOCTURNO"])
                f_ini = st.date_input("Fecha Inicio:", value=pd.to_datetime("today"))
                
                if st.button("Guardar Asignación", type="primary", disabled=not has_permission("seguridad_guardias", "editar")):
                    ok, msg, _ = execute_sp("sp_asignar_guardia", (g_dict[sel_g], acc_dict[sel_acc], turno, f_ini))
                    if ok:
                        st.success("Guardia asignado exitosamente al acceso.")
                        st.rerun()
                    else:
                        st.error(f"Error al asignar: {msg}")

        with col_fin:
            with st.container(border=True):
                st.write("🛑 **Finalizar Asignación de Turno**")
                st.caption("Nota: El sistema rechazará la operación si el acceso queda sin ningún guardia asignado (Regla R10).")
                
                asigs_vigentes = query_df("""
                    SELECT ag.asignacion_id, g.nombres || ' ' || g.apellidos AS guardia,
                           e.nombre AS estacion, a.codigo AS acceso_codigo, ag.turno, ag.fecha_inicio
                      FROM transmetro.asignacion_guardia ag
                      JOIN transmetro.guardia g ON g.guardia_id = ag.guardia_id
                      JOIN transmetro.acceso a ON a.acceso_id = ag.acceso_id
                      JOIN transmetro.estacion e ON e.estacion_id = a.estacion_id
                     WHERE ag.fecha_fin IS NULL
                     ORDER BY e.nombre, ag.turno;
                """)
                
                if not asigs_vigentes.empty:
                    asig_dict = {
                        f"#{r['asignacion_id']}: {r['guardia']} en {r['estacion']} ({r['acceso_codigo']}) - Turno {r['turno']}": r['asignacion_id']
                        for _, r in asigs_vigentes.iterrows()
                    }
                    sel_asig = st.selectbox("Seleccione Asignación a Finalizar:", list(asig_dict.keys()), key="sel_asig_fin")
                    f_fin = st.date_input("Fecha de Finalización:", value=pd.to_datetime("today"), key="fin_asig_date")
                    
                    if st.button("Finalizar Asignación", type="secondary", disabled=not has_permission("seguridad_guardias", "editar")):
                        ok, msg, _ = execute_sp("sp_finalizar_asignacion_guardia", (asig_dict[sel_asig], f_fin))
                        if ok:
                            st.success("Asignación finalizada.")
                            st.rerun()
                        else:
                            st.error(f"Rechazado por regla de negocio: {msg}")
                else:
                    st.info("No hay asignaciones activas.")

    # --- PESTAÑA 3: CATÁLOGO DE GUARDIAS ---
    with tab_guardias:
        st.subheader("Personal de Guardias de Seguridad")
        df_g = query_df("SELECT guardia_id, dpi, nombres, apellidos, telefono, empresa, activo FROM transmetro.guardia ORDER BY nombres;")
        st.dataframe(df_g, use_container_width=True, hide_index=True)

        if has_permission("seguridad_guardias", "crear"):
            with st.expander("➕ Registrar Nuevo Guardia"):
                with st.form("form_nuevo_guardia"):
                    gc1, gc2 = st.columns(2)
                    with gc1:
                        dpi_g = st.text_input("DPI:", placeholder="Ej. 5000000000013")
                        noms_g = st.text_input("Nombres:", placeholder="Ej. Carlos Enrique")
                        apes_g = st.text_input("Apellidos:", placeholder="Ej. Gómez Pérez")
                    with gc2:
                        tel_g = st.text_input("Teléfono:", placeholder="Ej. 55112233")
                        emp_g = st.text_input("Empresa de Seguridad:", placeholder="Ej. Seguridad Metropolitana, S.A.")
                    
                    sub_g = st.form_submit_button("Registrar Personal de Seguridad")
                    if sub_g:
                        if not dpi_g or not noms_g or not apes_g:
                            st.error("DPI, nombres y apellidos son requeridos.")
                        else:
                            ok, msg, _ = execute_stmt("""
                                INSERT INTO transmetro.guardia (dpi, nombres, apellidos, telefono, empresa)
                                VALUES (%s, %s, %s, %s, %s);
                            """, (dpi_g.strip(), noms_g.strip(), apes_g.strip(), tel_g.strip(), emp_g.strip()))
                            if ok:
                                st.success("Guardia registrado exitosamente.")
                                st.rerun()
                            else:
                                st.error(f"Error: {msg}")
