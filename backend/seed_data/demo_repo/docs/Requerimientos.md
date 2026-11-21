# Documento de requerimientos · API de pagos

Versión 1.0 · Equipo backend

> Documento de ejemplo para probar "Sacar reglas del documento" en IA voy
> (docs/PLAN_IMPORTAR_REGLAS_DOCUMENTO.md). Contiene reglas de negocio mezcladas con secciones que no son
> reglas (objetivo, alcance, tecnología) y una ambigüedad a propósito (§3.4).

## 1. Objetivo

Ofrecer a las tiendas afiliadas una API para registrar y cobrar pagos de sus clientes en pesos mexicanos y en
otras monedas.

## 2. Alcance y tecnología

- La API se construye con Flask y SQLite.
- Las pruebas se escriben con pytest.
- Fuera de alcance: reembolsos y conciliación bancaria.

## 3. Reglas de cobro

### 3.1 Montos exactos

Todo cobro se calcula exacto al centavo. Si un pago de $0.10 tiene una comisión del 10 %, el monto cobrado debe
ser exactamente $0.09.

### 3.2 Pagos sobre el límite

Los pagos que excedan el límite de crédito del cliente deberán contar con la aprobación del área de
Administración o de Finanzas; cualquier otra aprobación será rechazada con el motivo «autorizador». Un pago sobre
el límite sin aprobación se rechaza con el motivo «límite».

### 3.3 Pagos sin datos

Un pago que llega sin monto se rechaza con el motivo «sin monto». Un pago con monto cero o negativo se rechaza con
el motivo «monto inválido».

### 3.4 Monedas

Un pago en una moneda distinta al peso se convierte con el tipo de cambio del día. Los pagos grandes en moneda
extranjera requieren una revisión adicional.

## 4. Seguridad

### 4.1 Consulta de pagos

El nombre del cliente que se recibe en la consulta de pagos se usa solo como dato: nunca debe poder cambiar la
consulta para ver los pagos de otros clientes.

### 4.2 Clave de las sesiones

La clave con la que se firman los tokens de sesión se lee de la configuración del servidor y no se guarda en el
código fuente.

## 5. Glosario

- **Límite de crédito**: monto máximo que un cliente puede pagar sin aprobación.
- **Comisión**: porcentaje que se descuenta del pago.
