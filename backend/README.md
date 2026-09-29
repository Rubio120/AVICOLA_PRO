# AVÍCOLA PRO Backend

Base FastAPI del monolito modular. Consulte `../INSTALLATION.md` para instalación y ejecución.

## Bootstrap del administrador inicial

Con la base migrada y las variables `AVICOLA_DATABASE_URL` y `AVICOLA_SESSION_HMAC_KEY` configuradas,
ejecute una sola vez:

```powershell
uv run avicola-pro bootstrap-admin --username <usuario> --email <correo> --name <nombre>
```

El comando valida y normaliza los datos, crea el usuario activo con el rol `administrator` y muestra una
contraseña temporal una sola vez. Debe guardarse inmediatamente por un canal seguro; no se registra ni se
puede recuperar. Una segunda ejecución termina con error sin crear ni modificar datos.
