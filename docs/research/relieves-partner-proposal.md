# Propuesta de Integración Relieves de Colombia + PlacamIA

(Documento de conversación / No definitivo)

## Estado MVP

PlacamIA confirmó Path A para el MVP: checkout directo solo para productos y
kits 100% parametrizables, con precios calculados por el backend y
disponibilidad operativa actualizada de forma simple.

Este documento reemplaza la propuesta RFQ como conversación MVP con Relieves.
Los flujos RFQ quedan como investigación futura para productos manuales,
custom, con archivos complejos o que requieran cotización humana.

## Propósito

Definir una integración práctica entre Relieves de Colombia y PlacamIA que
permita vender señalización estándar y parametrizable sin exigir que Relieves
cambie su operación interna.

La premisa central es:

- PlacamIA asume la relación con el cliente, el checkout, el cobro, las
  notificaciones, reclamos y coordinación logística.
- Relieves actúa como proveedor manufacturero.
- Relieves no necesita inventario digital exacto ni portal avanzado para el
  MVP.
- Relieves sí debe comprometer por escrito precios parametrizables,
  disponibilidad semanal, tiempos de servicio y políticas de cancelación,
  garantía y facturación.

## Flujo MVP Propuesto

```text
Cliente selecciona producto o kit parametrizable
    ->
PlacamIA valida opciones, disponibilidad y precio backend
    ->
Cliente acepta condiciones de cancelación/devolución
    ->
Cliente paga el 100%
    ->
PlacamIA envía orden pagada a Relieves
    ->
Relieves acepta o rechaza la orden pagada
    ->
Relieves produce, prepara paquete y adhiere QR
    ->
Transportista escanea QR al recoger
    ->
PlacamIA actualiza despacho y notifica al cliente
```

Relieves puede rechazar una orden pagada si hay una imposibilidad real de
producción o disponibilidad. Ese caso debe activar manejo de cancelación,
reembolso y compensación según la política acordada.

## Alcance Inicial

El MVP solo debe vender por checkout directo:

- productos activos del catálogo
- kits activos compuestos por productos activos
- materiales, tamaños, cantidades, acabados y campos de plantilla permitidos
- configuraciones que puedan tener precio final calculado por reglas backend
- productos con disponibilidad semanal compatible con venta

Debe quedar fuera del checkout directo:

- productos que requieren cotización manual
- trabajos con archivos complejos que Relieves deba revisar antes del pago
- productos tercerizados sin precio o tiempo claro
- configuraciones no soportadas por la tabla de precios
- productos temporalmente no disponibles
- recomendaciones normativas que no estén traducidas a kit/producto
  parametrizable

## Inventario y Disponibilidad

Relieves no necesita inventario exacto en tiempo real para iniciar.

La propuesta MVP es una sincronización semanal:

1. PlacamIA envía a Relieves un formulario simple con el catálogo activo.
2. Relieves responde disponibilidad por producto o familia.
3. PlacamIA actualiza qué productos/kits se pueden mostrar como comprables.
4. Si un producto queda incierto, se oculta del checkout directo o se deja para
   flujo futuro/manual.

Estados iniciales sugeridos:

- disponible
- bajo pedido parametrizable
- temporalmente no disponible
- requiere cotización manual
- tercerizado/no apto para MVP directo

Para Path A, "requiere cotización manual" no es un estado comprable. Sirve para
clasificar trabajo futuro.

## Precios

El backend de PlacamIA es la fuente de verdad del precio al cliente.

Para que un producto entre al MVP directo, Relieves debe entregar una tabla de
precios parametrizable por las variables necesarias, por ejemplo:

- material
- tamaño
- cantidad
- tipo de impresión o grabado
- color
- tipo de letra
- fluorescencia o acabado especial
- descuentos por volumen si aplican

PlacamIA agrega su margen sobre la base acordada con Relieves. El cliente ve el
precio final calculado por PlacamIA, no un precio enviado por el frontend.

Si Relieves no puede convertir una familia de producto a tabla de precios
estable, esa familia no debe entrar al checkout directo del MVP.

## Tiempos de Servicio

Relieves debe definir tiempos realistas para:

- aceptación o rechazo de una orden pagada
- producción de productos estándar
- preparación de paquete para recogida
- ventana de recolección con transportista
- manejo de problemas de producción

PlacamIA debe comunicar tiempos al cliente con margen de seguridad. Las
consecuencias por incumplimiento de SLA deben acordarse antes de automatizar
compensaciones o promesas comerciales.

## Logística y QR

La propuesta operativa es:

1. PlacamIA envía a Relieves la orden pagada con identificador único y QR.
2. Relieves imprime o recibe el QR y lo adhiere al paquete.
3. El transportista escanea el QR al recoger.
4. PlacamIA usa ese evento para marcar la orden como despachada.

El mecanismo QR depende de validación técnica con la empresa de mensajería. Si
no está listo para MVP, un operador autorizado puede registrar el evento de
despacho como fallback.

## Cancelaciones, Garantías y Reembolsos

Para simplificar el MVP:

- el cliente paga el 100% antes de producción
- una orden pagada no se cancela automáticamente por solicitud del cliente
- el cliente puede solicitar cancelación
- la aprobación depende del estado de la orden y la política acordada
- si Relieves no puede cumplir una orden, PlacamIA reembolsa al cliente según
  la política definida
- las condiciones deben mostrarse antes del pago

La política exacta requiere revisión legal, contable y comercial.

## Facturación y Relación Comercial

La propuesta operativa es:

- PlacamIA factura o gestiona la factura al cliente, según definición legal y
  contable.
- Relieves factura a PlacamIA.
- PlacamIA paga a Relieves contra factura y cumplimiento del proceso acordado.
- PlacamIA responde ante el cliente.
- Relieves responde ante PlacamIA por producción, calidad y garantías según
  contrato.

La estructura legal, tributaria y contable debe ser revisada antes de lanzar
pagos reales.

## Notificaciones

MVP:

- cliente recibe notificaciones por correo e in-app
- Relieves recibe notificación por correo cuando llega una orden pagada
- WhatsApp queda fuera del MVP como canal automatizado

Eventos mínimos:

- orden confirmada/pagada
- orden enviada a Relieves
- orden aceptada o rechazada por Relieves
- orden en producción
- lista para recogida
- despachada
- entregada
- cancelación solicitada/resuelta

## Fases Futuras

### Futuro 1: Productos Manuales o RFQ

Para productos que no sean 100% parametrizables:

- solicitud estructurada
- revisión de Relieves
- precio/viabilidad confirmados
- aceptación del cliente
- checkout posterior

### Futuro 2: Herramientas para Relieves

- enlaces seguros para aceptar/rechazar órdenes
- carga CSV de disponibilidad
- portal de proveedor
- API o integración más automatizada

## Decisiones Que Debemos Cerrar con Relieves

- Qué productos entran al MVP directo.
- Qué productos quedan fuera por requerir cotización manual.
- Tabla de precios parametrizable por producto/familia.
- Estados de disponibilidad semanal.
- Frecuencia y responsable de actualización de disponibilidad.
- Tiempos de aceptación, producción y preparación.
- Viabilidad del QR con mensajería.
- Política de cancelación, garantía y reembolso.
- Estructura de facturación cliente-PlacamIA-Relieves.
- Consecuencias por incumplimiento de SLA.

## Resumen

La recomendación MVP es vender solo lo que pueda operar como ecommerce
confiable:

```text
Catálogo parametrizable
    ->
Precio backend
    ->
Pago completo
    ->
Orden pagada a Relieves
    ->
Producción y despacho
```

Este modelo reduce fricción para el cliente y evita construir un RFQ completo
antes de validar demanda. Lo que no sea parametrizable se conserva como trabajo
futuro, no como promesa del MVP.
