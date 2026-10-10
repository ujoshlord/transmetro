"""
Módulo de Administración de Usuarios, Roles y Permisos Granulares por Módulo.
"""
import streamlit as st
import pandas as pd
from db_connection import query_df, execute_stmt
from components.ui_helpers import render_header, render_rule_badge
from auth import hash_password, has_permission

def render():
    render_header(
        title="Administración de Usuarios y Permisos",
        subtitle="Control de acceso, cuentas de usuario, roles y matriz de permisos por módulo",
        icon="⚙️"
    )
    render_rule_badge("Seguridad", "Autenticación segura con bcrypt, control de roles (ADMIN, OPERADOR, RRHH, SUPERVISOR) y permisos por módulo.")

    if not has_permission("admin_usuarios", "ver"):
        st.error("No cuenta con permisos de Administrador para acceder a este módulo.")
        return

    tab_usuarios, tab_nuevo_u, tab_permisos = st.tabs([
        "👥 Cuentas de Usuario",
        "➕ Crear Nuevo Usuario",
        "🛡️ Matriz de Permisos por Rol"
    ])

    # --- PESTAÑA 1: CUENTAS DE USUARIO ---
    with tab_usuarios:
        st.subheader("Usuarios Registrados en el Sistema")
        df_users = query_df("""
            SELECT u.usuario_id, u.username, u.nombre_completo, u.email,
                   r.nombre AS rol, u.activo, u.ultimo_login, u.fecha_creacion
              FROM transmetro.usuario u
              JOIN transmetro.rol r ON r.rol_id = u.rol_id
             ORDER BY u.usuario_id;
        """)
        st.dataframe(df_users, use_container_width=True, hide_index=True)

        st.markdown("---")
        st.subheader("Gestión de Estado y Contraseñas")
        
        col_pwd, col_act = st.columns(2)
        
        with col_pwd:
            with st.container(border=True):
                st.write("🔑 **Restablecer Contraseña de Usuario**")
                user_dict = {f"{r['username']} ({r['nombre_completo']})": r['usuario_id'] for _, r in df_users.iterrows()}
                u_sel = st.selectbox("Seleccione Usuario:", list(user_dict.keys()), key="reset_u_sel")
                new_pwd = st.text_input("Nueva Contraseña:", type="password", key="reset_new_pwd")
                
                if st.button("Actualizar Contraseña"):
                    if not new_pwd:
                        st.error("Ingrese la nueva contraseña.")
                    else:
                        h_pwd = hash_password(new_pwd)
                        ok, msg, _ = execute_stmt(
                            "UPDATE transmetro.usuario SET password_hash = %s WHERE usuario_id = %s;",
                            (h_pwd, user_dict[u_sel])
                        )
                        if ok:
                            st.success("Contraseña actualizada exitosamente.")
                        else:
                            st.error(f"Error: {msg}")

        with col_act:
            with st.container(border=True):
                st.write("🔒 **Activar / Desactivar Cuenta**")
                u_act_sel = st.selectbox("Seleccione Usuario:", list(user_dict.keys()), key="toggle_u_sel")
                current_active = bool(df_users[df_users['usuario_id'] == user_dict[u_act_sel]]['activo'].iloc[0])
                st.write(f"Estado actual: **{'Activo' if current_active else 'Desactivado'}**")
                
                btn_label = "Desactivar Cuenta" if current_active else "Activar Cuenta"
                if st.button(btn_label):
                    ok, msg, _ = execute_stmt(
                        "UPDATE transmetro.usuario SET activo = %s WHERE usuario_id = %s;",
                        (not current_active, user_dict[u_act_sel])
                    )
                    if ok:
                        st.success(f"Cuenta actualizada a {'Activa' if not current_active else 'Desactivada'}.")
                        st.rerun()
                    else:
                        st.error(f"Error: {msg}")

    # --- PESTAÑA 2: CREAR NUEVO USUARIO ---
    with tab_nuevo_u:
        st.subheader("Crear Nueva Cuenta de Usuario")
        with st.form("form_nuevo_usuario"):
            c1, c2 = st.columns(2)
            with c1:
                new_username = st.text_input("Nombre de Usuario (Username):", placeholder="Ej. jperez")
                new_fullname = st.text_input("Nombre Completo:", placeholder="Ej. Juan Pérez González")
                new_password = st.text_input("Contraseña:", type="password", placeholder="••••••••")
            with c2:
                new_email = st.text_input("Correo Electrónico:", placeholder="Ej. jperez@transmetro.gob.gt")
                roles_df = query_df("SELECT rol_id, nombre, descripcion FROM transmetro.rol;")
                roles_dict = {f"{r['rol_id']} - {r['nombre']}": r['rol_id'] for _, r in roles_df.iterrows()}
                sel_rol = st.selectbox("Rol Asignado:", list(roles_dict.keys()))
            
            sub_u = st.form_submit_button("Crear Usuario", type="primary")
            if sub_u:
                if not new_username or not new_password or not new_fullname:
                    st.error("Username, contraseña y nombre completo son obligatorios.")
                else:
                    h_pwd = hash_password(new_password)
                    ok, msg, _ = execute_stmt("""
                        INSERT INTO transmetro.usuario (username, password_hash, nombre_completo, email, rol_id, activo)
                        VALUES (%s, %s, %s, %s, %s, TRUE);
                    """, (new_username.strip(), h_pwd, new_fullname.strip(), new_email.strip() if new_email else None, roles_dict[sel_rol]))
                    if ok:
                        st.success(f"Usuario '{new_username}' creado exitosamente con rol {roles_dict[sel_rol]}.")
                        st.rerun()
                    else:
                        st.error(f"Error al crear usuario: {msg}")

    # --- PESTAÑA 3: MATRIZ DE PERMISOS POR ROL ---
    with tab_permisos:
        st.subheader("Matriz de Permisos por Rol y Módulo")
        df_matriz = query_df("""
            SELECT r.nombre AS rol, m.icono || ' ' || m.nombre AS modulo,
                   rmp.puede_ver, rmp.puede_crear, rmp.puede_editar, rmp.puede_eliminar
              FROM transmetro.rol_modulo_permiso rmp
              JOIN transmetro.rol r ON r.rol_id = rmp.rol_id
              JOIN transmetro.modulo m ON m.modulo_id = rmp.modulo_id
             ORDER BY r.rol_id, m.orden;
        """)
        st.dataframe(df_matriz, use_container_width=True, hide_index=True)
