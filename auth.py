"""
Módulo de Autenticación y Autorización basada en Roles y Permisos por Módulo.
"""
import streamlit as st
import bcrypt
from datetime import datetime
from db_connection import query_one, query_all, execute_stmt

def hash_password(password: str) -> str:
    """Genera hash seguro con bcrypt."""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifica una contraseña en texto plano contra el hash almacenado."""
    try:
        return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))
    except Exception:
        return False

def init_auth_state():
    """Inicializa las variables de estado de sesión para autenticación."""
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False
    if "user" not in st.session_state:
        st.session_state.user = None
    if "permissions" not in st.session_state:
        st.session_state.permissions = {}

def get_current_user():
    """Retorna el usuario actual autenticado o None."""
    init_auth_state()
    return st.session_state.user

def is_authenticated() -> bool:
    """Verifica si hay un usuario autenticado en sesión."""
    init_auth_state()
    return st.session_state.authenticated

def has_permission(modulo_id: str, action: str = "ver") -> bool:
    """
    Verifica si el usuario autenticado tiene permiso para la acción solicitada.
    Acciones: 'ver', 'crear', 'editar', 'eliminar'.
    """
    init_auth_state()
    if not st.session_state.authenticated or not st.session_state.user:
        return False
    
    # Rol ADMIN tiene acceso total irrestricto
    if st.session_state.user.get("rol_id") == "ADMIN":
        return True
    
    perm = st.session_state.permissions.get(modulo_id, {})
    key_map = {
        "ver": "puede_ver",
        "crear": "puede_crear",
        "editar": "puede_editar",
        "eliminar": "puede_eliminar"
    }
    col_name = key_map.get(action, "puede_ver")
    return bool(perm.get(col_name, False))

def login(username: str, password: str) -> tuple[bool, str]:
    """Intenta autenticar las credenciales del usuario."""
    init_auth_state()
    username = username.strip()
    
    sql = """
        SELECT u.usuario_id, u.username, u.password_hash, u.nombre_completo,
               u.email, u.rol_id, u.activo, r.nombre AS rol_nombre
          FROM transmetro.usuario u
          JOIN transmetro.rol r ON r.rol_id = u.rol_id
         WHERE u.username = %s;
    """
    user_record = query_one(sql, (username,))
    
    if not user_record:
        return False, "Usuario o contraseña incorrectos."
    
    if not user_record.get("activo"):
        return False, "La cuenta de usuario está desactivada. Contacte al Administrador."
    
    if not verify_password(password, user_record["password_hash"]):
        return False, "Usuario o contraseña incorrectos."
    
    # Cargar permisos del rol para cada módulo
    perm_sql = """
        SELECT modulo_id, puede_ver, puede_crear, puede_editar, puede_eliminar
          FROM transmetro.rol_modulo_permiso
         WHERE rol_id = %s;
    """
    perms_list = query_all(perm_sql, (user_record["rol_id"],))
    perms_dict = {p["modulo_id"]: p for p in perms_list}
    
    # Actualizar último inicio de sesión
    execute_stmt(
        "UPDATE transmetro.usuario SET ultimo_login = LOCALTIMESTAMP WHERE usuario_id = %s;",
        (user_record["usuario_id"],)
    )
    
    # Guardar en sesión
    st.session_state.authenticated = True
    st.session_state.user = {
        "usuario_id": user_record["usuario_id"],
        "username": user_record["username"],
        "nombre_completo": user_record["nombre_completo"],
        "email": user_record["email"],
        "rol_id": user_record["rol_id"],
        "rol_nombre": user_record["rol_nombre"]
    }
    st.session_state.permissions = perms_dict
    
    return True, "Inicio de sesión exitoso."

def logout():
    """Cierra la sesión del usuario actual."""
    st.session_state.authenticated = False
    st.session_state.user = None
    st.session_state.permissions = {}
    st.rerun()

def render_login_page():
    """Renderiza la pantalla de autenticación de usuario."""
    init_auth_state()
    
    col1, col2, col3 = st.columns([1, 1.8, 1])
    with col2:
        try:
            with open("resources/minimalist_transmetro_animation.html", "r", encoding="utf-8") as f:
                animation_html = f.read()
        except FileNotFoundError:
            animation_html = "<p style='color: #ffcccc; font-size: 0.9rem;'>[Animación no encontrada en la ruta especificada]</p>"

        # 2. Renderizar el login combinando el diseño y la animación
        st.html(
            f"""
                <div style="display: flex; justify-content: center; align-items: center; margin-bottom: 15px;">
                    {animation_html}
                </div>
                
            """
        )
        
        with st.container(border=True):
            st.subheader("🔐 Iniciar Sesión")
            username = st.text_input("Usuario:", placeholder="Ej. admin", key="login_username")
            password = st.text_input("Contraseña:", type="password", placeholder="••••••••", key="login_password")
            
            remember = st.checkbox("Recordar sesión en este equipo", value=True)
            
            btn_login = st.button("Ingresar al Sistema 🚀", type="primary", use_container_width=True)
            
            if btn_login:
                if not username or not password:
                    st.error("Por favor ingresa usuario y contraseña.")
                else:
                    success, msg = login(username, password)
                    if success:
                        st.success(f"¡Bienvenido, {st.session_state.user['nombre_completo']}!")
                        st.rerun()
                    else:
                        st.error(msg)
