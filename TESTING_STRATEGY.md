# Estrategia de pruebas

## Principios

- TDD para reglas y defectos: prueba fallida, implementación mínima y refactor.
- PostgreSQL real en integración; SQLite no sustituye semántica, locks ni constraints.
- Pruebas deterministas, reloj inyectable y sin esperas arbitrarias.
- Cobertura orientativa: 80 % global y 90 % en reglas críticas, con ramas y casos negativos.
- Ninguna fase cierra con pruebas fallidas, `skip/xfail` sin incidencia o defectos críticos/altos.

## Capas

### Unitarias

Reglas puras de IVA 0/5/10, redondeo, dinero, estados, permisos, numeración, costos, saldos, aplicaciones, anulaciones y promedio ponderado. Se usarán pruebas tabulares y property-based para invariantes.

### Integración PostgreSQL

Base efímera por suite/worker mediante Testcontainers. Se aplican migraciones reales y se validan PK, FK, `CHECK`, `UNIQUE`, índices, locks, rollback, idempotencia y auditoría atómica.

### API/contrato

- OpenAPI estable y cliente tipado.
- 400/401/403/404/409/422 coherentes.
- Matriz permiso-endpoint.
- IDOR/BOLA y manipulación de campos de servidor.
- Paginación, filtros y límites.
- Cookies, CSRF, CORS e idempotencia.
- Errores sin stack trace ni secretos.

### Frontend

Componentes, formularios, accesibilidad, permisos visuales, tablas, filtros, paginación y estados loading/empty/error. Los permisos de UI nunca sustituyen pruebas de backend.

### E2E

Pocos flujos completos de alto valor:

1. Login, renovación, logout y expiración.
2. Compra -> recepción -> stock -> AP -> pago.
3. Pedido -> entrega -> documento interno -> AR -> cobro.
4. Alimentación -> stock -> costo de lote.
5. Mortalidad -> saldo de aves.
6. Transferencia y ajuste de inventario.
7. Apertura -> movimientos -> cierre/reversión de caja.
8. Nota de crédito/anulación con compensaciones.
9. Usuario sin permiso intentando cada acción sensible.

### Concurrencia

Coordinación con barreras/eventos, nunca `sleep`:

- dos salidas del mismo stock;
- numeración simultánea;
- confirmación duplicada;
- dos pagos sobre una deuda;
- cierre frente a movimiento concurrente;
- NC acumulada superior al original;
- reintento con la misma clave idempotente.

Invariantes: stock y aves no negativos, número único, una sola operación efectiva, pagos no sobreaplicados y ledger igual a proyección.

Casos transversales obligatorios:

- `UPDATE/DELETE` SQL directo contra cada tipo confirmado y contra auditoría;
- reconciliación de cantidad y valor tras cadenas de entrada, salida, transferencia y reversión;
- doble reversión y compensaciones concurrentes;
- salida, traslado y cierre de lote avícola;
- creación concurrente del singleton empresarial;
- fallo de auditoría/outbox y rollback de la UoW;
- claim concurrente de outbox, lease vencido, caída tras publicación e idempotencia del consumidor;
- contract tests entre módulos y comprobación del grafo de dependencias;
- `DisabledFiscalProvider` sin red, DNS ni fila fiscal;
- fechas en UTC/local, corte de caja y cambios de offset aplicables;
- overflow, precisión y redondeo monetario;
- golden case de moving average con reversión y variación de costo que termina cantidad/valor en cero;
- backup corrupto, clave incorrecta y versión/extensión incompatible.

### Migración e instalación

En CI:

1. Crear base vacía.
2. Ejecutar todas las migraciones.
3. Verificar esquema y drift ORM.
4. Cargar seed mínimo idempotente.
5. Arrancar servicios.
6. Ejecutar smoke tests.
7. Probar upgrade desde la versión anterior soportada.

### Backup/restore

Crear fixture representativo, generar copia cifrada, moverla a almacenamiento externo, recuperar ese artefacto, restaurar en nueva instancia, comprobar hashes/versiones/extensiones/configuración, conteos e invariantes, arrancar la aplicación y registrar RPO/RTO observados. Antes del piloto se fijan RPO, RTO, retención, owner y aprobador.

### Seguridad y rendimiento

- Ruff/type checking, SAST, dependency scan, secret scan e image scan.
- Revisión manual de autorización y auditoría.
- Presupuesto inicial: endpoints operativos p95 < 500 ms con volumen de prueba acordado; reportes pesados se evalúan por separado.
- Explain/analyze de consultas críticas y detección de N+1.

## Datos y fixtures

- Factories por módulo, sin dependencias globales ocultas.
- Fechas y UUID controlables.
- Conjuntos con exentas, IVA 5/10, pagos parciales, lotes vencidos, stocks límite y reversiones.
- Datos sintéticos; nunca copias productivas.

## Gates por fase

| Gate | Evidencia requerida |
|---|---|
| Arquitectura | ADR, modelo, amenazas, dependencias e invariantes revisados |
| Base técnica | lint, tipos, unitarias, migración limpia, health checks |
| Módulo | aceptación, permisos negativos, auditoría y errores probados |
| Módulo crítico | integración PostgreSQL, idempotencia, concurrencia y reversión |
| Release candidate | E2E, seguridad, performance, upgrade y backup/restore |
| Piloto | instalación limpia, restore drill, runbooks y cero críticos/altos |

La evidencia se guarda bajo `artifacts/quality/<release>/` en CI o almacenamiento equivalente: resultados, cobertura, migraciones, escaneos, explain plans y acta de restore. El responsable técnico produce evidencia y el architect/comprehensive reviewer aprueba el gate.

## Responsabilidad de agentes

- TDD/test automator diseña matriz y fixtures antes del código.
- Especialista de dominio verifica invariantes.
- Security auditor revisa casos negativos.
- Debugger investiga cualquier fallo antes de cambiar implementación.
- Comprehensive reviewer valida evidencias de cierre.
