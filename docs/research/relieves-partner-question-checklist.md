# Checklist de Preguntas para Relieves de Colombia

(Documento de conversación / No definitivo)

## Estado MVP

PlacamIA confirmó Path A para el MVP: checkout directo solo para productos y
kits 100% parametrizables, con precio calculado por backend y disponibilidad
operativa semanal. Relieves acepta o rechaza la orden después de que el pago del
cliente esté verificado.

Este checklist está diseñado para validar ese flujo con Relieves. Las preguntas
RFQ quedan para una fase futura de productos manuales/custom.

## Resultado Esperado de la Reunión

Al final de la conversación deberíamos poder responder:

- qué productos pueden venderse por checkout directo
- qué productos requieren cotización manual y quedan fuera del MVP
- qué variables de precio son parametrizables
- qué estados de disponibilidad semanal son suficientes
- qué tiempos de aceptación, producción y despacho puede cumplir Relieves
- cómo funcionará el QR o el fallback operativo de despacho
- qué política de cancelación, garantía y reembolso verá el cliente
- qué estructura de facturación y pago a Relieves debe revisar legal/contable

## 1. Catálogo MVP Directo

### 1.1 Productos Parametrizables

**Pregunta:** ¿Qué productos del catálogo se pueden vender sin revisión manual
de Relieves antes del pago?

**Por qué importa:** Solo estos productos pueden entrar al checkout directo del
MVP.

**Respuesta:**

### 1.2 Productos Fuera del MVP Directo

**Pregunta:** ¿Qué productos o trabajos requieren cotización manual, revisión de
archivo, tercerización incierta o criterio humano antes de precio final?

**Por qué importa:** Estos productos deben ocultarse del checkout directo o
quedar para una fase futura.

**Respuesta:**

### 1.3 Kits Iniciales

**Pregunta:** ¿Qué kits sectoriales puede Relieves producir de forma confiable
con productos parametrizables?

Ejemplos:

- oficina
- restaurante
- bodega
- obra
- institucional

**Respuesta:**

### 1.4 Cantidades en Kits

**Pregunta:** ¿Las cantidades de cada kit pueden ser fijas/editables por reglas
simples, o dependen de asesoría caso por caso?

**Respuesta:**

## 2. Tabla de Precios

### 2.1 Variables de Precio

**Pregunta:** ¿Qué variables cambian el precio y pueden parametrizarse?

Ejemplos:

- material
- tamaño
- cantidad
- impresión
- grabado
- color
- tipo de letra
- fluorescencia
- acabado especial

**Respuesta:**

### 2.2 Combinaciones Válidas

**Pregunta:** ¿Qué combinaciones de material, tamaño, impresión, grabado o
acabado no son válidas?

**Respuesta:**

### 2.3 Descuentos

**Pregunta:** ¿Los descuentos por volumen o por kit siguen reglas claras?

**Respuesta:**

### 2.4 Revisión de Precios

**Pregunta:** ¿Cada cuánto se debe revisar la tabla de precios?

Ejemplos:

- mensual
- trimestral
- cuando cambien costos de material
- cuando Relieves lo notifique con anticipación

**Respuesta:**

### 2.5 Responsable de Precio

**Pregunta:** ¿Quién en Relieves aprueba y mantiene la tabla de precios que
usará PlacamIA?

**Respuesta:**

## 3. Inventario y Disponibilidad

### 3.1 Proceso Semanal

**Pregunta:** ¿Relieves puede responder semanalmente un formulario simple de
disponibilidad del catálogo activo?

**Respuesta:**

### 3.2 Estados de Disponibilidad

**Pregunta:** ¿Estos estados son suficientes para el MVP?

- disponible
- bajo pedido parametrizable
- temporalmente no disponible
- requiere cotización manual
- tercerizado/no apto para MVP directo

**Respuesta:**

### 3.3 Separación de Inventario

**Pregunta:** ¿Relieves puede separar una porción del inventario disponible para
órdenes de PlacamIA durante la semana?

**Respuesta:**

### 3.4 Productos Bajo Pedido

**Pregunta:** Para productos bajo pedido pero parametrizables, ¿qué tiempo de
producción se puede prometer con margen de seguridad?

**Respuesta:**

## 4. SLA y Producción

### 4.1 Aceptación de Orden Pagada

**Pregunta:** Después de recibir una orden pagada, ¿cuánto tiempo máximo necesita
Relieves para aceptarla o rechazarla?

**Respuesta:**

### 4.2 Producción

**Pregunta:** ¿Cuánto demora una orden estándar desde aceptación hasta lista
para recogida?

**Respuesta:**

### 4.3 Problemas de Producción

**Pregunta:** Si Relieves acepta una orden pagada y luego detecta que no puede
cumplirla, ¿qué proceso debe seguir?

**Respuesta:**

### 4.4 Consecuencias por Incumplimiento

**Pregunta:** ¿Qué consecuencia comercial aplica si Relieves no cumple los
tiempos acordados o no puede entregar una orden aceptada?

**Respuesta:**

## 5. Logística y QR

### 5.1 Transportista

**Pregunta:** ¿Quién coordina hoy los envíos y qué empresa de mensajería se
usaría para PlacamIA?

**Respuesta:**

### 5.2 QR en Paquete

**Pregunta:** ¿Relieves puede imprimir/adherir un QR único al paquete antes de
entregarlo al transportista?

**Respuesta:**

### 5.3 Escaneo en Recogida

**Pregunta:** ¿La empresa de mensajería puede escanear el QR al recoger el
paquete?

**Respuesta:**

### 5.4 Fallback Operativo

**Pregunta:** Si el QR no está listo para MVP, ¿quién puede registrar
manualmente que la orden fue despachada?

**Respuesta:**

## 6. Cancelaciones, Garantías y Reembolsos

### 6.1 Cancelación Después del Pago

**Pregunta:** ¿Relieves acepta que una orden pagada no sea cancelable
automáticamente por el cliente?

**Respuesta:**

### 6.2 Solicitud de Cancelación

**Pregunta:** ¿En qué estados una solicitud de cancelación podría aprobarse?

Ejemplos:

- pagada pero no aceptada por Relieves
- aceptada pero no producida
- en producción
- lista para recogida
- despachada

**Respuesta:**

### 6.3 Garantías

**Pregunta:** ¿Qué política aplica si el cliente reporta defecto de fabricación,
error de producción o daño en entrega?

**Respuesta:**

### 6.4 Reembolso por Incumplimiento de Relieves

**Pregunta:** Si Relieves no puede cumplir una orden, ¿cómo se compensa a
PlacamIA y cómo se maneja el reembolso al cliente?

**Respuesta:**

## 7. Facturación y Relación Comercial

Estas preguntas requieren revisión legal, contable o gerencial.

### 7.1 Factura al Cliente

**Pregunta:** ¿Quién debe facturar al cliente final?

**Respuesta:**

### 7.2 Factura de Relieves a PlacamIA

**Pregunta:** ¿Relieves factura a PlacamIA al despacho, a la entrega o en otro
momento?

**Respuesta:**

### 7.3 Pago a Relieves

**Pregunta:** ¿Relieves espera pago inmediato, pago contra factura, pago a X
días o conciliación periódica?

**Respuesta:**

### 7.4 Responsabilidad ante Reclamos

**Pregunta:** ¿Qué responsabilidades asume PlacamIA ante el cliente y cuáles
asume Relieves ante PlacamIA?

**Respuesta:**

## 8. Cumplimiento Normativo y Recomendaciones

### 8.1 Lenguaje Permitido

**Pregunta:** ¿Qué puede decir PlacamIA sobre cumplimiento normativo sin
prometer aprobación de inspecciones?

**Respuesta:**

### 8.2 Uso del Workbook

**Pregunta:** ¿El workbook NSR10 debe usarse como referencia interna,
herramienta de asesoría futura o fuente autorizada para kits del MVP?

**Respuesta:**

## 9. Decisiones Que Buscamos Cerrar

Después de la reunión, intentar cerrar:

- lista de productos/kits que entran al checkout directo
- lista de productos que quedan fuera por cotización manual
- tabla inicial de precios parametrizable
- estados y proceso semanal de disponibilidad
- SLA de aceptación, producción y despacho
- viabilidad del QR o fallback manual
- política de cancelación, garantía y reembolso
- estructura preliminar de facturación y pago a Relieves
- puntos que requieren revisión legal/contable

## Notas de Reunión

Fecha:

Participantes:

Resumen:

Pendientes:
