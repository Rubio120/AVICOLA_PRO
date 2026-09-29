# Entrega 4 — Inventario transaccional

## Alcance

Implementar el módulo `inventory` sobre PostgreSQL real, respetando el ledger inmutable y la
proyección de saldos definidos en `DATABASE.md` y `ARCHITECTURE.md`. La entrega cubre lotes,
documentos de entrada/salida/transferencia/ajuste, promedio ponderado móvil, confirmación
idempotente, reversión compensatoria, permisos, auditoría y una pantalla operativa mínima.

## Diseño

- `inventory/domain/rules.py` contiene únicamente reglas Decimal: cuantización, promedio,
  salidas, transferencias y reversión.
- `inventory/infrastructure/models.py` contiene `InventoryLot`, documentos, líneas, movimientos,
  saldos y variaciones de costo.
- La migración `0004_inventory` añade constraints, índices, unique parcial de reversión y
  triggers append-only para movimientos confirmados.
- `inventory/api/routes.py` es el adaptador HTTP: DTOs estrictos, sesión opaca, CSRF, permisos
  granulares, paginación y auditoría en la misma UoW.
- La confirmación bloquea balances en orden determinista, valida disponibilidad y actualiza
  ledger/proyección en una transacción; una transferencia crea salida y entrada inseparables.
- Los documentos confirmados no se editan. Revertir crea un documento compensatorio enlazado y
  conserva snapshots de costo/valor originales.

## Verificación

1. TDD unitario para reglas de Decimal y estados.
2. Tests PostgreSQL para migración limpia/roundtrip, constraints, append-only, reconciliación,
   transferencia, idempotencia, doble reversión y concurrencia de dos salidas.
3. Suite backend, cobertura, Ruff/formato, Mypy y auditoría de dependencias.
4. ESLint, TypeScript, Vitest (si el sandbox bloquea esbuild, delegación explícita al gate
   externo), build y smoke de health/API.
5. Revisión de seguridad e independiente; corregir hallazgos importantes con TDD.
