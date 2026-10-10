"""
Módulo de Gestión de Pilotos y Ficha Integral.
Requerimiento: R9 (Historial Educativo, Residencia y Comunicación).
"""
import streamlit as st
import pandas as pd
from db_connection import query_df, execute_sp, execute_stmt
from components.ui_helpers import render_header, render_rule_badge
from auth import has_permission

def render():
    render_header(
        title="Gestión de Pilotos y Personal de Conducción",
        subtitle="Expediente digital 360°, historial académico, datos de residencia y comunicación",
        icon="👨‍✈️"
    )
    render_rule_badge("R9", "Conocer historial educativo completo, datos de residencia histórica y actual, y canales de comunicación y emergencia.")

    tab_directorio, tab_ficha, tab_nuevo = st.tabs([
        "📋 Directorio de Pilotos",
        "🪪 Ficha Integral 360° (R9)",
        "➕ Registrar Nuevo Piloto"
    ])

    # --- PESTAÑA 1: DIRECTORIO DE PILOTOS ---
    with tab_directorio:
        st.subheader("Personal de Pilotos Activos")
        df_pilotos = query_df("SELECT * FROM transmetro.vw_ficha_piloto ORDER BY nombre_completo;")
        
        st.dataframe(
            df_pilotos[['dpi', 'nombre_completo', 'edad', 'numero_licencia', 'tipo_licencia', 'vencimiento_licencia', 'nivel_educativo_maximo', 'municipio_residencia', 'contacto_principal']],
            use_container_width=True,
            hide_index=True
        )

    # --- PESTAÑA 2: FICHA INTEGRAL 360° ---
    with tab_ficha:
        st.subheader("Expediente Digital del Piloto")
        pilotos_list = query_df("SELECT piloto_id, dpi, nombres, apellidos FROM transmetro.piloto ORDER BY nombres;")
        p_dict = {f"{r['nombres']} {r['apellidos']} (DPI: {r['dpi']})": r['piloto_id'] for _, r in pilotos_list.iterrows()}
        sel_piloto = st.selectbox("Seleccione un Piloto para consultar:", list(p_dict.keys()))
        sel_piloto_id = p_dict[sel_piloto]

        # Datos Generales
        p_info = query_df("SELECT * FROM transmetro.vw_ficha_piloto WHERE piloto_id = %s;", (sel_piloto_id,)).iloc[0]
        
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            st.metric("DPI", p_info['dpi'])
        with c2:
            st.metric("Edad", f"{p_info['edad']} años")
        with c3:
            st.metric("Licencia", f"Tipo {p_info['tipo_licencia']} ({p_info['numero_licencia']})")
        with c4:
            vig = "🟢 Vigente" if p_info['licencia_vigente'] else "🔴 Vencida"
            st.metric("Vigencia Licencia", str(p_info['vencimiento_licencia']), vig)

        st.markdown("---")
        
        # Sub-secciones de la Ficha: Educación, Residencia, Comunicación
        col_edu, col_res_com = st.columns([1.2, 1])
        
        # 1. HISTORIAL EDUCATIVO (R9)
        with col_edu:
            st.markdown("#### 🎓 Historial Educativo (R9)")
            df_edu = query_df("""
                SELECT n.nombre AS nivel, pe.institucion, pe.titulo_obtenido,
                       pe.fecha_inicio, pe.fecha_fin, pe.estado
                  FROM transmetro.piloto_educacion pe
                  JOIN transmetro.nivel_educativo n ON n.nivel_id = pe.nivel_id
                 WHERE pe.piloto_id = %s
                 ORDER BY n.jerarquia;
            """, (sel_piloto_id,))
            
            if not df_edu.empty:
                st.dataframe(df_edu, use_container_width=True, hide_index=True)
            else:
                st.warning("No hay registros educativos asociados a este piloto.")

            # Formulario para agregar educación
            if has_permission("pilotos", "editar"):
                with st.expander("➕ Agregar Grado Académico"):
                    with st.form("form_add_edu"):
                        niveles = query_df("SELECT nivel_id, nombre FROM transmetro.nivel_educativo ORDER BY jerarquia;")
                        niv_map = {r['nombre']: r['nivel_id'] for _, r in niveles.iterrows()}
                        sel_niv = st.selectbox("Nivel Educativo:", list(niv_map.keys()))
                        inst_edu = st.text_input("Institución Educativa:", placeholder="Ej. Instituto Nacional Central")
                        tit_edu = st.text_input("Título Obtenido:", placeholder="Ej. Perito en Mecánica Automotriz")
                        f_ini = st.date_input("Fecha Inicio:")
                        f_fin = st.date_input("Fecha Fin:")
                        est_edu = st.selectbox("Estado:", ["COMPLETADO", "EN_CURSO", "INCONCLUSO"])
                        
                        sub_edu = st.form_submit_button("Guardar Estudio")
                        if sub_edu:
                            ok, msg, _ = execute_stmt("""
                                INSERT INTO transmetro.piloto_educacion (piloto_id, nivel_id, institucion, titulo_obtenido, fecha_inicio, fecha_fin, estado)
                                VALUES (%s, %s, %s, %s, %s, %s, %s);
                            """, (sel_piloto_id, niv_map[sel_niv], inst_edu.strip(), tit_edu.strip(), f_ini, f_fin, est_edu))
                            if ok:
                                st.success("Estudio agregado exitosamente.")
                                st.rerun()
                            else:
                                st.error(f"Error: {msg}")

        # 2. RESIDENCIA Y COMUNICACIÓN (R9)
        with col_res_com:
            st.markdown("#### 🏠 Datos de Residencia (R9)")
            st.markdown(f"**Dirección Actual:** {p_info['direccion_actual'] or 'No registrada'}")
            st.markdown(f"**Municipio:** {p_info['municipio_residencia']} ({p_info['departamento_residencia']})")
            
            # Historial de residencias
            df_res = query_df("""
                SELECT m.nombre AS municipalidad, r.direccion, r.zona, r.fecha_desde, r.fecha_hasta, r.es_actual
                  FROM transmetro.piloto_residencia r
                  JOIN transmetro.municipalidad m ON m.municipalidad_id = r.municipalidad_id
                 WHERE r.piloto_id = %s
                 ORDER BY r.es_actual DESC, r.fecha_desde DESC;
            """, (sel_piloto_id,))
            
            with st.expander("Ver Historial de Residencias"):
                st.dataframe(df_res, use_container_width=True, hide_index=True)

            # Actualizar residencia
            if has_permission("pilotos", "editar"):
                with st.expander("🔄 Actualizar Residencia Actual"):
                    with st.form("form_cambio_res"):
                        munis = query_df("SELECT municipalidad_id, nombre FROM transmetro.municipalidad ORDER BY nombre;")
                        muni_dict = {r['nombre']: r['municipalidad_id'] for _, r in munis.iterrows()}
                        sel_m = st.selectbox("Municipio:", list(muni_dict.keys()))
                        n_dir = st.text_input("Nueva Dirección:", placeholder="Ej. 14 avenida 5-20")
                        n_zona = st.text_input("Zona:", placeholder="Ej. 11")
                        n_ref = st.text_input("Referencia:", placeholder="Ej. Colonia Mariscal")
                        
                        sub_res = st.form_submit_button("Actualizar Residencia")
                        if sub_res:
                            ok, msg, _ = execute_sp("sp_actualizar_residencia_piloto", (sel_piloto_id, muni_dict[sel_m], n_dir, n_zona, n_ref))
                            if ok:
                                st.success("Residencia actualizada correctamente.")
                                st.rerun()
                            else:
                                st.error(f"Error: {msg}")

            st.markdown("---")
            st.markdown("#### 📞 Medios de Comunicación y Emergencia (R9)")
            df_contactos = query_df("""
                SELECT tipo, valor, COALESCE(nombre_contacto, 'Personal') AS contacto,
                       COALESCE(parentesco, 'N/A') AS parentesco, es_principal
                  FROM transmetro.piloto_contacto
                 WHERE piloto_id = %s
                 ORDER BY es_principal DESC, tipo;
            """, (sel_piloto_id,))
            st.dataframe(df_contactos, use_container_width=True, hide_index=True)

            # Agregar medio de comunicación
            if has_permission("pilotos", "editar"):
                with st.expander("➕ Agregar Contacto / Emergencia"):
                    with st.form("form_add_cont"):
                        tipo_c = st.selectbox("Tipo de Contacto:", ["CELULAR", "TELEFONO_CASA", "EMAIL", "EMERGENCIA"])
                        val_c = st.text_input("Número o Correo:", placeholder="Ej. 55123456 o correo@mail.com")
                        nom_c = st.text_input("Nombre de Referencia (Obligatorio en Emergencia):", placeholder="Ej. María de Pérez")
                        par_c = st.text_input("Parentesco:", placeholder="Ej. Esposa, Hermano")
                        es_p = st.checkbox("¿Es el contacto principal?")
                        
                        sub_cont = st.form_submit_button("Guardar Contacto")
                        if sub_cont:
                            ok, msg, _ = execute_stmt("""
                                INSERT INTO transmetro.piloto_contacto (piloto_id, tipo, valor, nombre_contacto, parentesco, es_principal)
                                VALUES (%s, %s, %s, %s, %s, %s);
                            """, (sel_piloto_id, tipo_c, val_c.strip(), nom_c.strip() if nom_c else None, par_c.strip() if par_c else None, es_p))
                            if ok:
                                st.success("Contacto registrado exitosamente.")
                                st.rerun()
                            else:
                                st.error(f"Error: {msg}")

    # --- PESTAÑA 3: REGISTRAR NUEVO PILOTO ---
    with tab_nuevo:
        st.subheader("Registrar Nuevo Piloto")
        if has_permission("pilotos", "crear"):
            with st.form("form_nuevo_piloto"):
                p1, p2 = st.columns(2)
                with p1:
                    dpi_p = st.text_input("DPI (13 dígitos):", placeholder="Ej. 2541789630101")
                    noms_p = st.text_input("Nombres:", placeholder="Ej. Juan Carlos")
                    apes_p = st.text_input("Apellidos:", placeholder="Ej. López González")
                    fnac_p = st.date_input("Fecha de Nacimiento:", value=pd.to_datetime("1990-01-01"))
                    gen_p = st.selectbox("Género:", ["M", "F"])
                with p2:
                    lic_num = st.text_input("Número de Licencia:", placeholder="Ej. LIC-A-400912")
                    lic_tipo = st.selectbox("Tipo de Licencia (Requerido: A o B):", ["A", "B", "C"])
                    lic_venc = st.date_input("Fecha de Vencimiento de Licencia:", value=pd.to_datetime("2028-12-31"))
                    f_cont = st.date_input("Fecha de Contratación:", value=pd.to_datetime("today"))

                sub_piloto = st.form_submit_button("Registrar Piloto")
                if sub_piloto:
                    if not dpi_p or not noms_p or not apes_p or not lic_num:
                        st.error("DPI, Nombres, Apellidos y Licencia son requeridos.")
                    else:
                        ok, msg, res = execute_stmt("""
                            INSERT INTO transmetro.piloto (dpi, nombres, apellidos, fecha_nacimiento, genero, numero_licencia, tipo_licencia, vencimiento_licencia, fecha_contratacion)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                            RETURNING piloto_id;
                        """, (dpi_p.strip(), noms_p.strip(), apes_p.strip(), fnac_p, gen_p, lic_num.strip(), lic_tipo, lic_venc, f_cont))
                        if ok:
                            st.success(f"Piloto '{noms_p} {apes_p}' registrado con éxito. Ahora puede completar su historial educativo, residencia y contactos en la pestaña Ficha.")
                            st.rerun()
                        else:
                            st.error(f"Error al registrar piloto: {msg}")
        else:
            st.info("No cuenta con permisos para registrar nuevos pilotos.")
