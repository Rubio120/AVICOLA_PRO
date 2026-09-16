# AVÍCOLA PRO

Sistema empresarial para la gestión integral de una empresa avícola. El proyecto se encuentra en fase de arquitectura y planificación; todavía no contiene código de aplicación.

## Alcance de V1

- Una sola empresa, sin aislamiento multiempresa.
- Producción por granjas, galpones y lotes; las aves se administran como cantidades por lote.
- Inventario trazable, sin stock negativo y valorizado por promedio ponderado móvil.
- Compras, proveedores, recepciones y cuentas por pagar.
- Ventas, clientes, pedidos, documentos comerciales internos, cuentas por cobrar y pagos.
- Caja auditable con aperturas, cierres y reversiones compensatorias.
- Costos por lote y ave, rentabilidad, dashboard y reportes.
- Usuarios, roles, permisos granulares y auditoría.
- IVA configurable con operaciones exentas, 5 % y 10 %.
- Timbrado y numeración configurables como datos internos.
- Sin integración SIFEN real. El límite fiscal queda preparado mediante puertos y adaptadores.

## Arquitectura

Monolito modular con arquitectura hexagonal por contexto, API REST FastAPI, frontend Next.js y PostgreSQL. Los módulos comparten despliegue y base de datos, pero no acceden directamente a repositorios o tablas ajenas.

Documentación principal:

- [Arquitectura](ARCHITECTURE.md)
- [Base de datos](DATABASE.md)
- [Seguridad](SECURITY.md)
- [Estrategia de pruebas](TESTING_STRATEGY.md)
- [Plan de implementación](IMPLEMENTATION_PLAN.md)
- [Instalación prevista](INSTALLATION.md)
- [Estado del proyecto](PROJECT_STATUS.md)
- [Cambios](CHANGELOG.md)

## Estado

Arquitectura base aprobada por el usuario y documentación sometida a revisión arquitectónica. El siguiente incremento recomendado es la base técnica y el módulo de Identidad y Acceso. Ninguna fase se considera terminada con revisión pendiente, pruebas fallidas o defectos críticos/altos conocidos.

## Reglas de contribución

- Trabajar con entregas pequeñas, TDD y commits verificables.
- No editar ni borrar operaciones confirmadas; usar anulaciones o reversiones.
- Toda mutación crítica exitosa debe autorizarse y auditarse en la misma transacción; fallos y denegaciones usan un canal durable independiente.
- Usar migraciones Alembic para todo cambio de esquema.
- Ejecutar las pruebas requeridas por la fase antes de cerrarla.
- Actualizar `PROJECT_STATUS.md` y `CHANGELOG.md` en cada entrega.
