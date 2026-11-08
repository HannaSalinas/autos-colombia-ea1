"""Mapa de rol a permisos (D2, RF-20, RF-21). Es el ÚNICO lugar donde se define qué puede hacer cada rol.

- El backend lo usa para proteger cada endpoint (dependencia `requiere`).
- El frontend recibe la lista de permisos de la cuenta en GET /auth/yo y arma el menú con ella:
  así la pantalla nunca muestra algo que el servidor no permite.

El Administrador tiene todos los permisos del Operador y además los de administración (D2):
el rol superior contiene al inferior.
"""

ESTANCIAS = "estancias"                    # entradas, salidas, correcciones de celda y novedades
CONSULTAS = "consultas"                    # ocupación e historial
CELDAS_VER = "celdas:ver"
CELDAS_GESTIONAR = "celdas:gestionar"      # crear, editar, inhabilitar y rehabilitar celdas
VEHICULOS_VER = "vehiculos:ver"            # listado de vehículos y clientes (solo lectura)
VEHICULOS_GESTIONAR = "vehiculos:gestionar"
CUENTAS_GESTIONAR = "cuentas:gestionar"    # cuentas de usuario y personas

PERMISOS_OPERADOR = frozenset({ESTANCIAS, CONSULTAS, CELDAS_VER, VEHICULOS_VER})
PERMISOS_ADMINISTRADOR = PERMISOS_OPERADOR | {CELDAS_GESTIONAR, VEHICULOS_GESTIONAR, CUENTAS_GESTIONAR}

PERMISOS_POR_ROL: dict[str, frozenset[str]] = {
    "ADMINISTRADOR": PERMISOS_ADMINISTRADOR,
    "OPERADOR": PERMISOS_OPERADOR,
}


def permisos_de(rol: str) -> frozenset[str]:
    """Permisos de un rol. Un rol desconocido no tiene ninguno (nunca se conceden por defecto)."""
    return PERMISOS_POR_ROL.get(rol, frozenset())


def tiene_permiso(rol: str, permiso: str) -> bool:
    return permiso in permisos_de(rol)
