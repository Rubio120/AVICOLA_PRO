# AVICOLA PRO — Diseño de paridad funcional con la propuesta

**Estado:** alcance funcional aprobado; reglas de negocio enumeradas como pendientes cuando la propuesta no las define
**Fecha:** 2026-09-23
**Documento de referencia:** `Propuesta de Desarrollo.pdf`
**Alcance aprobado en conversación:** igualar las funciones de negocio descritas en la propuesta, conservar FastAPI/PostgreSQL/Next.js y el estilo visual actual; no rehacer la pantalla para copiar la captura.

## 1. Objetivo

Completar las capacidades avícolas y gerenciales de AVICOLA PRO para cubrir la propuesta de desarrollo, extendiendo los módulos existentes y conservando las decisiones de arquitectura y seguridad vigentes. El resultado permitirá registrar producción diaria de huevos, seguir el alimento y el inventario de huevos, gestionar ventas por canal y calcular indicadores de eficiencia y rentabilidad sustentados en movimientos confirmados.

Este documento define el comportamiento esperado y los límites de diseño. El usuario autorizó la implementación del alcance; esa autorización no reemplaza la aprobación de reglas de negocio que la propuesta no especifica. Cada regla pendiente debe resolverse antes de implementar el cálculo que dependa de ella.

## 2. Entendimiento acordado

- El objetivo es la paridad **funcional** con la propuesta, no una réplica visual.
- Se mantienen FastAPI, PostgreSQL y Next.js, la arquitectura modular existente y el estilo actual de interfaz. Se permiten formularios y controles mínimos para las nuevas tareas, sin rediseño visual.
- El modelo vigente de una empresa con varias granjas se conserva; no se introduce multiempresa.
- Se reutilizan producción, inventario, ventas, costing y reporting siempre que sus responsabilidades actuales lo permitan.
- Las categorías de huevo, presentaciones/conversiones y fórmulas no se inventan: se documentan como configurables o como decisiones por confirmar.
- D11 y D12 (preparación técnica y gate de release) son un frente separado. Su CI debe quedar verde para certificar la preparación de release, pero no sustituye la aceptación funcional descrita aquí.

## 3. Alcance funcional

### 3.1 Producción diaria de huevos

Permitir registrar la producción por fecha, lote y galpón, con cantidades en unidades de huevo. El registro debe poder asociarse a categorías configurables cuando estas estén aprobadas. Debe validarse contra el lote y la asignación de galpón vigentes para la fecha, rechazar cantidades inválidas y evitar duplicaciones accidentales mediante una clave de idempotencia o una regla de unicidad aprobada.

El conteo acepta cero para registrar explícitamente un día sin producción; la ausencia de un registro no se interpreta como cero. Los conteos son enteros no negativos, dentro del rango soportado por persistencia. Se permiten varios eventos por lote/galpón/fecha; las repeticiones de una misma solicitud se controlan por clave de idempotencia.

Los registros confirmados se conservan como hechos trazables. Las correcciones deben seguir el patrón existente de corrección compensatoria/auditable; no se sobrescribe silenciosamente producción ya confirmada.

### 3.2 Eficiencia y alimentación

Reutilizar el registro existente de consumo de alimento por lote, galpón, producto y fecha. Exponer agregados por periodo y por unidad productiva, y añadir las métricas de eficiencia solicitadas únicamente después de confirmar unidad, denominador, periodo y tratamiento de alimento devuelto o corregido.

La propuesta nombra consumo por ave, conversión alimenticia y costo de alimento por huevo, pero no especifica las ecuaciones operativas completas. No se presentará ninguna como indicador oficial hasta que el usuario/negocio las confirme.

### 3.3 Inventario avícola de huevos

Incorporar existencias de huevos por categoría y presentación, integradas con el ledger de inventario y con movimientos de entrada/salida trazables. Producción aceptada puede originar una entrada de stock; ventas y bajas autorizadas originan salidas; las cantidades no pueden quedar negativas. La clasificación y la conversión entre unidad base, bandeja u otra presentación deben ser configurables y validadas.

No se asume que una bandeja contiene una cantidad fija ni que existan categorías predeterminadas. Los insumos veterinarios y alimento continúan dentro del inventario general existente.

### 3.4 Ventas, clientes y canales

Extender ventas existentes para identificar el canal mayorista/minorista descrito en la propuesta, conservar la relación con cliente/cuenta por cobrar y calcular ventas por canal, cantidad de documentos, clientes nuevos y ticket promedio. Los ajustes, anulaciones y notas de crédito deben tratarse de acuerdo con el ledger/documentos confirmados actuales y no contarse como ventas positivas duplicadas.

La taxonomía exacta de canales, la definición de “cliente nuevo” y el cálculo del ticket promedio requieren quedar explícitos en los criterios de aceptación antes de implementación.

### 3.5 Costos, margen y rentabilidad

Extender los reportes para calcular el costo por huevo vendible/producido, ingreso diario, utilidad estimada y margen por canal usando costos confirmados y ventas confirmadas. La asignación de costos a lote, galpón, categoría y periodo debe ser determinista, reproducible y explicable.

La propuesta no define qué partidas integran el costo total del huevo, cómo distribuir costos indirectos entre granjas/lotes, ni cómo tratar pérdidas, huevos no vendibles, notas de crédito y periodos sin producción. Estas reglas se dejan como decisiones de negocio obligatorias; el sistema no debe inventar una fórmula ni etiquetar como “real” una estimación no aprobada.

### 3.6 Dashboard y reportes

Ampliar el dashboard/reporting existente con métricas confirmadas de producción (huevos, porcentaje de postura, mortalidad y edad del lote), eficiencia (consumo y conversión), rentabilidad (costo por huevo, ingreso/utilidad estimada, margen por canal), ventas/clientes e inventario/cobertura. Las consultas deben aceptar periodos consistentes, mostrar unidades y distinguir valores reales confirmados de estimaciones.

Añadir exportación de reportes en formato de libro Excel `.xlsx`, además del CSV vigente, protegida por RBAC y registrada en auditoría. El reporte debe respetar los filtros/permiso del solicitante y los límites de volumen existentes.

## 4. Fuera de alcance

- Migrar a Laravel, Filament, MySQL/MariaDB o Blade/Livewire.
- Rediseñar el dashboard o copiar la apariencia de la captura de referencia.
- Multiempresa/aislamiento de múltiples compañías.
- SIFEN u otra integración fiscal externa.
- Despliegue productivo, publicación de imágenes o aprobación del piloto.
- Inventar datos históricos de huevos o métricas. Cualquier carga/backfill histórica requerirá fuente y aprobación del usuario.

## 5. Arquitectura y límites entre módulos

Se conserva la arquitectura modular documentada en `ARCHITECTURE.md`, PostgreSQL como fuente transaccional y el BFF same-origin del frontend. La propuesta inicial de tecnología se considera referencia, no requisito, dado el acuerdo explícito de mantener el stack.

- `production` es dueño de registros diarios de producción avícola y del vínculo con lote/galpón.
- `inventory` es dueño de existencias y movimientos de huevo; no se mantiene un saldo paralelo fuera del ledger.
- `sales` es dueño del canal de venta y de los documentos/clientes/cuentas por cobrar.
- `costing` es dueño de costos confirmados, corridas y asignaciones; no se duplican costos calculados en reporting.
- `reporting` consume consultas de lectura de los módulos, no comandos ni modelos internos, y arma indicadores/exportaciones sin escribir saldos operativos.
- El frontend consume la API mediante el BFF same-origin; no conoce credenciales ni conecta directamente a PostgreSQL.

Las escrituras que coordinan producción, existencias y/o ventas deben usar la unidad de trabajo transaccional existente. Se mantienen idempotencia, restricciones de base, correlación, CSRF, sesión/RBAC, auditoría, separación de funciones y prohibición de ciclos de dependencias. Las nuevas capacidades requieren permisos explícitos y eventos de auditoría compatibles con la matriz de autorización; esa matriz continúa necesitando revisión del responsable del negocio.

## 6. Flujos de datos y comportamiento

1. Un usuario autorizado registra y confirma cantidades diarias por lote/galpón/fecha.
2. El dominio valida la asignación vigente y conserva el hecho confirmado con actor, fecha, correlación e idempotencia.
3. La clasificación aprobada determina la entrada a las existencias de huevo en unidad base; conversiones de presentación son explícitas y configurables.
4. Consumos de alimento e inventario existentes proveen los hechos para eficiencia; ventas emitidas y ajustes confirmados proveen los hechos comerciales.
5. Costing asigna los costos permitidos bajo una regla aprobada. Reporting solo agrega esos hechos confirmados para periodo/canal/granja/lote y etiqueta toda estimación.
6. API, dashboard y XLSX aplican el mismo filtro de periodo, autorización y reglas de inclusión/exclusión.

Los errores de validación deben conservar respuestas API estables sin cambios parciales. Una falla al coordinar movimientos revierte la unidad de trabajo completa. Reintentar una solicitud idempotente no duplica producción, stock, venta ni auditoría funcional. Las correcciones se registran como compensaciones trazables conforme a las reglas de cada módulo.

## 7. Reglas de cálculo pendientes de aceptación

El plan no debe implementar los indicadores siguientes como oficiales hasta definir sus entradas, unidades, redondeo, periodo y ejemplos verificables:

| Indicador | Definición que falta acordar |
|---|---|
| Porcentaje de postura | Numerador (huevos vendibles o todos los huevos) y denominador de aves (saldo puntual, promedio diario u otro). |
| Consumo por ave | Peso/unidad del alimento, aves promedio y tratamiento de entradas/salidas de lote en el periodo. |
| Conversión alimenticia | Si se expresa como alimento por huevo, docena o masa de huevo; hace falta saber si se capturará peso de huevos. |
| Costo de alimento por huevo | Categorías de alimento/costo incluidas, periodo y base de huevos vendibles o producidos. |
| Costo total por huevo | Partidas directas/indirectas, asignación entre lote/galpón/granja, huevos rotos/no vendibles y redondeo. |
| Margen/ganancia por canal | Ingresos netos, descuentos, notas de crédito y costos asignados a cada canal. |
| Días de cobertura | Existencia utilizable dividida por consumo/ventas diarios promedio y ventana de referencia. |
| Cliente nuevo / ticket promedio | Evento que cuenta como alta y base de conteo/documentos/periodo para el promedio. |

La especificación final puede enumerar estas decisiones con ejemplos una vez que el usuario provea las reglas. Si aún no están definidas, las métricas afectadas permanecen identificadas como “pendiente de definición” y no se fabrican valores.

## 8. Seguridad, datos y migraciones

- Toda acción nueva se autentica, autoriza en backend y verifica CSRF según los patrones existentes; ocultar controles en UI nunca sustituye autorización.
- Las denegaciones deben conservar la respuesta funcional esperada y generar la evidencia `authorization.denied` requerida por el diseño vigente.
- Se minimizan datos personales; las exportaciones son acotadas y auditadas.
- Cualquier esquema nuevo lleva migración Alembic revisada desde base vacía y upgrade/rollback en base desechable. No se borran movimientos históricos ni se simula una migración de datos inexistentes.
- Los cambios de stock/costos/documentos respetan inmutabilidad de hechos confirmados y reversión compensatoria.
- No se guardan secretos ni información real de granja en fixtures, artefactos o paquetes de release.

## 9. Pruebas y criterios de aceptación

Cada etapa debe incluir:

1. Pruebas unitarias deterministas para validaciones, unidades, fórmulas y redondeo una vez aprobados.
2. Integración en PostgreSQL real/sintético de migraciones, restricciones, concurrencia, idempotencia, ledger, reversión y consistencia transaccional.
3. Pruebas API de sesión, CSRF, RBAC, autorización denegada/auditada, filtros, errores y auditoría de exportaciones.
4. Pruebas frontend de flujos/estados de carga, error, validación y ausencia de datos, manteniendo el estilo actual.
5. Pruebas de reporting con fixture sintético cuya respuesta se calcula manualmente, incluyendo notas de crédito, periodos sin datos, clasificación y valores de borde.
6. Verificación de archivo XLSX: hojas/cabeceras, filtros, formato numérico, límite de filas, permisos y ausencia de fórmulas interpretables originadas en datos de usuario.
7. CI completo verde para el SHA candidato; los jobs omitidos no cuentan como aprobados. D11/D12 y el gate de attestation siguen siendo requisitos separados para declarar listo un release candidate.

La aceptación funcional requiere demostrar, con datos sintéticos conocidos, que producción, inventario, consumo, ventas y reportes concilian sin diferencias inexplicadas; las unidades y fórmulas aparecen claras; no se crean cantidades/saldos negativos; la exportación refleja los mismos filtros/valores autorizados de la API; y no hay regresiones en los módulos existentes. No se declara producción ni piloto aprobado con pruebas locales solamente.

## 10. Secuencia propuesta

El orden acordado es:

1. Frente independiente D11/D12: corregir el test de permisos de Restic, ejecutar todos los jobs exigidos para el SHA exacto y verificar el bundle firmado si CI queda completamente verde.
2. Producción diaria de huevos por lote/galpón, con migración, API/BFF, permisos, auditoría y pruebas.
3. Clasificación y existencias de huevos con conversiones aprobadas, integradas al ledger de inventario.
4. Ventas por canal y métricas de cliente, conectadas con el flujo comercial existente.
5. Eficiencia/costos con reglas de negocio aceptadas; completar KPIs, reportes y `.xlsx`.
6. Regresión de extremo a extremo y aceptación del usuario con datos sintéticos.

Este orden no asigna todavía números oficiales de entrega posteriores a D12 ni fechas; ambos se definirán en el plan tras la aprobación de esta especificación.

## 11. Riesgos y dependencias

- Sin definición de categorías/presentaciones y conversiones no se puede aceptar el inventario de huevo.
- Sin fórmulas y asignación de costos aprobadas, “costo real por huevo”, margen y conversión no pueden afirmarse como valores oficiales.
- Los datos históricos no existen necesariamente; el reporte comenzará desde la activación, salvo importación autorizada y conciliada.
- El mapa de permisos por rol todavía requiere aceptación del negocio.
- La aprobación CI de D11/D12 sigue condicionada a un run completo verde del SHA final; la evidencia local no equivale a CI, staging ni restore off-host.

## 12. Aprobaciones requeridas

1. Revisar este documento y pedir correcciones o aprobarlo.
2. Resolver las reglas de negocio enumeradas antes de implementar las métricas afectadas.
3. Tras aprobar el documento, elaborar un plan de implementación por tareas y pruebas; el usuario revisará y escogerá el método de ejecución antes de modificar el producto.
