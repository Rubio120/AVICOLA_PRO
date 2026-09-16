# Modelo de datos de AVÍCOLA PRO

## Principios

- PostgreSQL 16+.
- UUIDv7 generado por aplicación para claves primarias.
- `date` para fecha operativa y `timestamptz` UTC para instantes.
- `numeric(18,2)` para importes, `numeric(18,4)` para cantidades y `numeric(9,6)` para tasas.
- V1 opera transaccionalmente solo en moneda base PYG. Se conserva `currency_code` como snapshot y catálogo para evolución; tipos de cambio, ganancias FX y pagos multimoneda están fuera de V1.
- `version integer not null default 1` donde se use bloqueo optimista.
- Estados evolutivos como `varchar` con `CHECK`, no enum PostgreSQL.
- FK indexadas; sin `ON DELETE CASCADE` para transacciones.
- Maestros usados se desactivan. Documentos confirmados no se borran.
- Totales e impuestos se calculan en backend y se almacenan como snapshot.
- Todo confirmado contiene `confirmed_at/by`; todo reversible, `reversed_at/by`, `reversal_of_id` y `reversal_reason`. Un índice único parcial limita una reversión total efectiva por original; notas de crédito parciales usan relaciones N:1 separadas.

## Identidad y configuración

| Entidad | Campos principales | Restricciones e índices |
|---|---|---|
| `company_profile` | `singleton_key smallint default 1`, razón social, RUC, nombre comercial, dirección, moneda, zona horaria | PK y `CHECK(singleton_key=1)`; seed por upsert y test concurrente |
| `app_settings` | `key`, `value jsonb`, `version` | PK/unique `key`; nunca secretos |
| `users` | username/email normalizados, hash, nombre, estado, fallos, bloqueo, `token_version` | unique case-insensitive; estado válido |
| `roles` | código, nombre, sistema, activo | código único |
| `permissions` | clave `modulo.recurso.accion`, descripción | clave única |
| `user_roles` | usuario, rol | PK compuesta; FK restrictivas |
| `role_permissions` | rol, permiso | PK compuesta; cambios auditados |
| `refresh_sessions` | hash, familia, emisión, expiración, revocación, IP, agent | índice usuario/activa y expiración |
| `security_events` | actor, tipo, resultado, IP, correlación | índices actor/fecha y tipo/fecha |
| `document_sequences` | tipo, serie, prefijo, actual, padding, vigencia, `stamp_id` | unique `(document_type,series)`; `current_number>=0` |
| `tax_rates` | código, tasa, vigencia, activo | unique `(code,valid_from)`; tasa 0..1 |
| `stamps` | número, vigencia, establecimiento, expedición | número/vigencia únicos según regla |
| `currencies` | código ISO, decimales, activo | código único |
| `units_of_measure` | código, nombre, precisión | código único |
| `payment_methods` | código, tipo, activo | código único |

La numeración se asigna al emitir mediante lock de la secuencia y no se reutiliza.

## Terceros y catálogo

| Entidad | Campos principales | Restricciones e índices |
|---|---|---|
| `customers` | código, tipo/número documento, nombre, contactos, crédito, plazo | código único; índice documento y nombre |
| `suppliers` | código, RUC/documento, razón social, contactos, condiciones | código único; índice documento y nombre |
| `product_categories` | código, nombre, activo | código único |
| `products` | SKU, nombre, tipo, unidad base, lote/vencimiento, activo | SKU único; índices tipo/nombre |
| `warehouses` | código, nombre, ubicación, activo | código único |
| `inventory_lots` | producto, lote, fabricación, vencimiento, proveedor | unique `(product_id,lot_code)` |

Los maestros no alteran históricos: documentos confirmados conservan descripción, unidad, precio, tasa y datos del tercero como snapshots.

## Producción avícola

| Entidad | Campos principales | Restricciones e índices |
|---|---|---|
| `farms` | código, nombre, ubicación, estado | código único |
| `houses` | granja, código, capacidad, estado | unique `(farm_id,code)`; capacidad > 0 |
| `flocks` | código, propósito, raza, ingreso, `planned_initial_quantity`, estado, cierre | código único; cantidad planificada > 0; índice estado/ingreso; no integra el saldo |
| `flock_house_assignments` | lote, galpón, desde/hasta, cantidad | no solapamiento incompatible; cantidad > 0 |
| `flock_balances` | lote, aves vivas, versión | one-to-one; saldo >= 0 |
| `flock_daily_records` | lote, fecha, aves, peso, métricas | unique `(flock_id,record_date)` |
| `mortality_events` | lote, galpón, fecha, cantidad, causa, estado, reversión | cantidad > 0; original reversible una vez |
| `bird_movement_events` | lote, galpón origen/destino, tipo `INITIAL/TRANSFER_IN/TRANSFER_OUT/SALE/SLAUGHTER/OTHER`, fecha, cantidad, estado, reversión, idempotencia | cantidad > 0; unique parcial: un `INITIAL` confirmado por lote; pares de traslado enlazados |
| `bird_adjustment_events` | lote, tipo `CORRECTION_IN/CORRECTION_OUT`, cantidad, motivo, estado, reversión | cantidad > 0; permiso de ajuste; no sustituye movimientos operativos |
| `feed_consumption` | lote, galpón, producto, depósito, cantidad, movimiento | cantidad > 0; movimiento único al confirmar |
| `production_events` | lote, tipo, fecha, cantidad, unidad, metadata | índice `(flock_id,type,occurred_at)` |

Invariante:

```text
aves_vivas = INITIAL_confirmado + ajustes_entrada - mortalidad - salidas
aves_vivas >= 0
```

`mortality_events`, `bird_movement_events` y `bird_adjustment_events` forman el ledger. Al activar un lote se crea exactamente un evento `INITIAL` idempotente desde `planned_initial_quantity`; ese evento es la única fuente del saldo inicial. Revertirlo solo se permite si no existen eventos posteriores; cerrar el lote exige saldo cero o ajuste autorizado. `flock_balances` es proyección bloqueable. `flock_daily_records` es observación y nunca modifica el saldo.

## Inventario

| Entidad | Campos principales | Restricciones e índices |
|---|---|---|
| `inventory_documents` | tipo, número, fecha, estado, origen, observación, confirmación/reversión | unique tipo/serie/número; índice estado/fecha |
| `inventory_document_lines` | documento, producto, lote, origen/destino, cantidad, costo, ordinal | cantidad > 0; unique documento/ordinal |
| `inventory_movements` | línea, producto, lote, depósito, tipo, `quantity_delta`, `unit_cost`, `value_delta`, fecha efectiva/ocurrencia, usuario, reversión | cantidad/valor snapshots; append-only; índices saldo/origen/fecha |
| `inventory_balances` | depósito, producto, lote, cantidad, `inventory_value`, costo promedio, versión | unique NULLS NOT DISTINCT en clave; cantidad/valor >= 0 |

Índices críticos:

- `(product_id, warehouse_id, inventory_lot_id, occurred_at desc)`.
- `(source_type, source_id)` para trazabilidad.
- parcial para documentos borrador/pendientes.
- unique parcial para una reversión efectiva por movimiento.

Confirmación: crear saldo faltante, bloquear claves ordenadas, validar disponibilidad, calcular promedio, insertar movimientos, actualizar proyección y registrar auditoría/outbox en una transacción.

El bucket oficial de valoración es `(warehouse_id, product_id, inventory_lot_id)`. Precisión interna: cantidades 4 decimales, costos unitarios 6 e importes 2; cálculos usan Decimal con precisión ampliada y redondeo monetario HALF_UP al persistir valor. Promedio ponderado móvil para entradas:

```text
nuevo_costo = (cantidad_actual*costo_actual + cantidad_entrada*costo_entrada)
              / (cantidad_actual + cantidad_entrada)
```

Reglas adicionales:

- Las salidas copian el costo vigente a `unit_cost` y `value_delta`; no cambian el promedio restante.
- Al quedar cantidad cero, valor y promedio quedan cero.
- Entrada gratuita usa costo cero y participa del promedio; requiere motivo.
- Toda reversión conserva `original_unit_cost`/`original_value_delta` como evidencia. Para la proyección se valora la salida compensatoria al promedio vigente del bucket, no al costo histórico aislado.
- Una transferencia sale al costo snapshot del origen y entra con ese mismo costo en el bucket destino.
- No se permiten retrofechas que reordenen movimientos de un período cerrado.
- Revertir una entrada exige cantidad suficiente. La cantidad se compensa al promedio vigente; la diferencia frente al valor original se registra como `inventory_cost_variance` enlazada al original y fluye a costos. Nunca se reescribe historia ni se deja valor residual al quedar cantidad cero.
- Invariantes por bucket: suma de `quantity_delta` = saldo y suma de `value_delta` = valor, sujetas a tolerancia monetaria documentada.

Ejemplo dorado: `+10@10`, `+10@20`, salida `-10@15`, reversión de la primera entrada con salida `-10@15` deja cantidad 0 y valor 0; la diferencia de 50 respecto del costo histórico de la entrada se registra como variación de costo. Una reversión inversa repone usando snapshots de la compensación y su variación enlazada.

## Compras y cuentas por pagar

| Entidad | Relaciones y reglas |
|---|---|
| `purchase_orders` | N:1 proveedor; estado, fechas, moneda y totales |
| `purchase_order_lines` | producto, cantidad, recibido, precio, descuento e impuesto snapshot; unique orden/ordinal |
| `purchase_receipts` | N:1 orden y depósito; permite parciales; lifecycle común y confirmación inmutable |
| `purchase_receipt_lines` | referencia a línea OC, producto/lote/vencimiento, cantidad y costo |
| `supplier_documents` | N:1 proveedor; número externo y totales; unique proveedor/tipo/número |
| `supplier_document_lines` | snapshots de descripción, precio e impuestos |
| `supplier_document_receipts` | N:M documento/recepción |
| `accounts_payable` | documento, original, aplicado, saldo, vencimiento, estado |
| `supplier_payments` | propiedad de Compras: proveedor, importe, medio, estado y `cash_movement_id` de Tesorería |
| `supplier_payment_allocations` | N:M pago/AP; suma aplicada no excede pago ni saldo |

La sobre-recepción está prohibida en V1. Para confirmar se bloquean las líneas de la orden.

## Ventas y cuentas por cobrar

| Entidad | Relaciones y reglas |
|---|---|
| `sales_orders` | N:1 cliente; estado, moneda, totales estimados |
| `sales_order_lines` | producto, cantidad, precio, descuento e impuesto estimado |
| `sales_deliveries` | N:1 cliente/pedido; confirmación genera salida de stock |
| `sales_delivery_lines` | producto/lote/cantidad; no exceder pendiente |
| `commercial_documents` | documento interno, serie/número, cliente+snapshot, fechas, moneda, IVA, total, estado, timbrado snapshot |
| `commercial_document_lines` | producto/servicio, descripción, cantidad, precio, descuento, tasa/base/IVA/total snapshot |
| `commercial_document_relations` | relaciones tipadas pedido-entrega-factura-NC |
| `accounts_receivable` | documento, original, aplicado, saldo, vencimiento, estado |
| `customer_payments` | propiedad de Ventas: cliente, importe, medio, estado y `cash_movement_id` de Tesorería |
| `customer_payment_allocations` | N:M cobro/AR; no sobreaplicar |

Totales de `commercial_documents`:

- `exempt_subtotal`;
- `vat_5_base`, `vat_5_amount`;
- `vat_10_base`, `vat_10_amount`;
- descuentos, subtotal y total;
- política de redondeo versionada.

Unique `(document_type,series,number)`. NC y anulaciones referencian el original; el crédito acumulado no puede exceder el neto original. Una devolución física genera además un documento de inventario relacionado.

## Documento fiscal externo futuro

| Entidad | Campos/reglas |
|---|---|
| `fiscal_submissions` | documento comercial, proveedor, ambiente, versión, estado, external ID/CDC, hash, intentos, errores y timestamps |
| `fiscal_events` | historial append-only de solicitudes, respuestas y cambios |
| `fiscal_provider_config` | configuración pública; credenciales/certificados fuera de BD |

Un documento puede tener varios intentos, pero como máximo un envío aceptado por proveedor/ambiente mediante índice único parcial. En V1 el proveedor deshabilitado no crea filas ni realiza red/DNS. Número y timbrado internos no equivalen a CDC ni aprobación fiscal.

## Caja y tesorería

| Entidad | Relaciones y reglas |
|---|---|
| `cash_accounts` | código, tipo, moneda, activo; código único |
| `cash_sessions` | caja, usuario, apertura/cierre, saldo inicial/esperado/contado/diferencia, estado |
| `cash_movements` | sesión/cuenta, tipo, importe, dirección, medio, origen, estado, reversión; append-only |
| `cash_transfers` | agrupa egreso e ingreso atómicos entre cuentas |

Índice único parcial garantiza una sola sesión abierta por caja. Un cierre congela el período; correcciones requieren reapertura autorizada/auditada o compensación en sesión vigente.

## Costos y rentabilidad

| Entidad | Relaciones y reglas |
|---|---|
| `cost_centers` | granja, galpón, lote u operación |
| `cost_events` | categoría, importe, cantidad, lote/centro, origen, estado/reversión |
| `cost_allocations` | distribución a lotes/centros; suma = evento origen |
| `costing_runs` | período, método, versión, parámetros, estado y ejecutor |
| `flock_cost_snapshots` | lote/período, alimento, otros, total, costo por ave y versión |

Una corrida cerrada no se sobrescribe. Rentabilidad relaciona ingresos confirmados y costos versionados mediante consultas/vistas.

## Auditoría, outbox e idempotencia

| Entidad | Campos/reglas |
|---|---|
| `audit_events` | actor+snapshot, acción, entidad, fecha, resultado, motivo, IP/agent, correlación, before/after redactado; append-only |
| `outbox_events` | agregado, tipo, payload versionado, estado, intentos, lease/worker y fechas; índice parcial pendientes |
| `idempotency_keys` | scope, key, request hash, estado/respuesta y expiración; unique scope/key |

La auditoría de negocio exitosa y outbox se insertan en la misma UoW del cambio. Fallos, login fallido y denegaciones se persisten después del resultado en `security_events` con una transacción independiente. El rol runtime no puede actualizar/borrar auditoría; lectura/exportación tiene permisos propios.

Auditoría y outbox no comparten política de mutación: `audit_events` no se actualiza ni borra; un rol worker mínimo puede reclamar outbox mediante compare-and-swap/lease y transicionar `PENDING -> PROCESSING -> PUBLISHED/FAILED`, incrementando intentos. Payload/agregado no se modifican. Lease vencido permite reintento y consumidores usan `event_id` idempotente. Se prueban dos claims concurrentes, caída tras publicar y reintento.

## Matriz de lifecycle e inmutabilidad

| Agregado | Confirmación | Estado terminal/corrección | Defensa DB |
|---|---|---|---|
| Inventario | congela líneas y crea movimientos | `REVERSED` por documento compensatorio | trigger/privilegio bloquea update/delete |
| Mortalidad/aves | actualiza proyección | evento de reversión único | unique parcial `reversal_of_id` |
| Recepción/entrega | actualiza orden/pedido y stock | compensación relacionada | campos confirmación + trigger |
| Documento comercial | numera, congela snapshots y crea AR | NC/anulación más efectos compensatorios | número único y trigger |
| Pago/cobro | aplica deuda y crea caja | pago inverso y desasignaciones | locks deuda + reversión única |
| Movimiento/cierre caja | congela ledger/período | reversión/reapertura autorizada | append-only + unique sesión |
| Evento/corrida costo | crea snapshot versionado | reversión o corrida nueva | append-only/version unique |
| Auditoría | inserción | sin mutación | deny update/delete al runtime |
| Outbox | inserción en UoW; claim por worker | publicación/reintento idempotente | rol worker solo actualiza estado/lease/intentos |

Cada implementación añade pruebas SQL directas de `UPDATE/DELETE`, transición tabular, doble reversión y compensación concurrente.

## Fronteras transaccionales

- Recepción: compra + stock + orden + auditoría/outbox.
- Despacho: entrega + stock + pedido + auditoría/outbox.
- Alimentación: producción + stock + costo.
- Mortalidad: evento + saldo de aves + indicadores.
- Emisión: secuencia + documento + AR + auditoría/outbox.
- Cobro/pago: pago + asignaciones + AR/AP + caja.
- NC/devolución: crédito + cuenta + inventario/caja cuando corresponda.
- Transferencia: egreso e ingreso inseparables.
- Reversión: compensación y enlace, nunca eliminación.

## Máquinas de estado normativas

| Agregado | Transiciones permitidas | Permiso/efecto principal |
|---|---|---|
| Orden compra | `DRAFT -> APPROVED -> PARTIALLY_RECEIVED -> RECEIVED/CLOSED`; `DRAFT/APPROVED -> CANCELLED` sin recepción | aprobar separado; recepción cambia progreso |
| Recepción | `DRAFT -> CONFIRMED -> REVERSED` | confirmar crea stock; revertir lo compensa |
| Pedido venta | `DRAFT -> CONFIRMED -> PARTIALLY_FULFILLED -> FULFILLED`; cancelación solo por pendiente | entrega cambia progreso |
| Entrega | `DRAFT -> CONFIRMED -> REVERSED` | confirmar descuenta stock |
| Documento comercial | `DRAFT -> ISSUED -> PARTIALLY_PAID -> PAID`; `ISSUED/PARTIALLY_PAID -> CREDITED/CANCELLED` mediante documentos/efectos compensatorios | emitir numera y crea AR |
| Pago/cobro | `DRAFT -> CONFIRMED -> REVERSED` | confirmar aplica deuda y crea caja |
| Inventario/aves/costo | `DRAFT -> CONFIRMED -> REVERSED` | confirmar crea ledger/proyección |
| Sesión caja | `OPEN -> CLOSED -> REOPENED -> CLOSED` | cerrar fija corte; reapertura requiere permiso/motivo |
| Corrida costo | `DRAFT -> RUNNING -> COMPLETED/FAILED`; una completada se sustituye con nueva versión | snapshot inmutable |

Toda transición recibe fecha efectiva, actor, permiso, motivo cuando corresponda e `Idempotency-Key` en confirmaciones. Estados terminales no retornan a borrador. Los períodos cerrados impiden retrofecha; las correcciones se reconocen en período abierto y referencian el original.

## Estrategia de migraciones

- Alembic es la única vía de modificación del esquema.
- Cada migración se prueba desde base vacía y desde la versión anterior soportada.
- Cambios riesgosos usan expand/migrate/contract.
- Columnas nuevas se agregan primero tolerantes; se rellenan y luego se endurecen.
- Índices grandes se crean concurrentemente en operación productiva cuando aplique.
- Antes de una migración productiva se verifica backup restaurable.
- Drift entre ORM y migraciones falla CI.
