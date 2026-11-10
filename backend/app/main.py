from fastapi import FastAPI
from fastapi.responses import JSONResponse

from app.routers.vehiculos import router as vehiculos_router
from app.services.vehiculo import VehiculoError
from app.routers.celdas import router as celdas_router
from app.services.celda import CeldaError
from app.routers.operadores import router as operadores_router
from app.services.operador import OperadorError
from app.routers.estancias import router as estancias_router
from app.services.estancia import EstanciaError
from app.routers.clientes import router as clientes_router
from app.services.cliente import ClienteError
from app.routers.reportes import router as reportes_router
from app.services.reporte import ReporteError
from app.routers.autenticacion import router as autenticacion_router
from app.routers.cuentas import router as cuentas_router
from app.services.cuenta import CuentaError
from app.services.autenticacion import AutenticacionError

app = FastAPI(title="Autos Colombia API")
app.include_router(vehiculos_router)
app.include_router(celdas_router)
app.include_router(operadores_router)
app.include_router(estancias_router)
app.include_router(clientes_router)
app.include_router(reportes_router)
app.include_router(autenticacion_router)
app.include_router(cuentas_router)


@app.exception_handler(VehiculoError)
@app.exception_handler(CeldaError)
@app.exception_handler(OperadorError)
@app.exception_handler(EstanciaError)
@app.exception_handler(ClienteError)
@app.exception_handler(ReporteError)
@app.exception_handler(CuentaError)
async def entity_error_handler(
    request,
    error: VehiculoError | CeldaError | OperadorError | EstanciaError | ClienteError | ReporteError | CuentaError,
) -> JSONResponse:
    return JSONResponse(status_code=error.status_code, content={"detail": error.detail})


@app.exception_handler(AutenticacionError)
async def authentication_error_handler(request, error: AutenticacionError) -> JSONResponse:
    # 401 lleva WWW-Authenticate: Bearer, como indica el estándar HTTP para pedir credenciales.
    headers = {"WWW-Authenticate": "Bearer"} if error.status_code == 401 else None
    return JSONResponse(status_code=error.status_code, content={"detail": error.detail}, headers=headers)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
