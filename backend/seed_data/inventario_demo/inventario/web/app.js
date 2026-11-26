"use strict";
/*
 * Interfaz del inventario. Sin dependencias ni compilación: usa la API de siempre (token Bearer).
 * Qué botones ve cada rol sale de la matriz de permisos del documento de requisitos (§8.1): la API es la que
 * decide de verdad, esta pantalla solo no ofrece lo que el rol no debe hacer.
 */

const PERMISOS = {
  catalogo: ["gerente", "almacenista"], // alta y edición de datos del producto
  precios: ["gerente"], // precio, costo e impuestos
  eliminar: ["gerente"],
  receta: ["gerente"],
  compras: ["gerente", "almacenista"],
  ventas: ["cajero", "barista", "gerente"],
  mermas: ["gerente", "almacenista"],
  ajustes: ["gerente"],
  auditoria: ["gerente"],
  ingresos: ["gerente"],
};
const SECCIONES = [
  ["productos", "Productos"],
  ["venta", "Venta", "ventas"],
  ["compras", "Compras", "compras"],
  ["mermas", "Mermas y ajustes", "mermas"],
  ["alertas", "Alertas"],
  ["bitacora", "Bitácora", "auditoria"],
  ["ingresos", "Ingresos", "ingresos"],
];

const estado = { token: sessionStorage.getItem("token"), rol: sessionStorage.getItem("rol"), nombre: sessionStorage.getItem("nombre"), seccion: "productos", productos: [] };
const $ = (id) => document.getElementById(id);
const puede = (permiso) => PERMISOS[permiso].includes(estado.rol);
const esc = (t) => String(t ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
const dinero = (v) => Number(v).toLocaleString("es-MX", { style: "currency", currency: "MXN" });
const cantidad = (v) => Number(v).toLocaleString("es-MX", { maximumFractionDigits: 3 });
const fecha = (v) => new Date(v).toLocaleString("es-MX", { dateStyle: "short", timeStyle: "short" });

function avisar(texto, tipo = "") {
  const caja = document.createElement("div");
  caja.className = tipo;
  caja.textContent = texto;
  $("aviso").append(caja);
  setTimeout(() => caja.remove(), tipo === "error" ? 8000 : 4000);
}

/** Texto legible de un error de la API (409 con `detail` o 422 con la lista de campos). */
function mensajeDe(cuerpo) {
  const d = cuerpo?.detail;
  if (Array.isArray(d)) return d.map((e) => `${(e.loc ?? []).slice(1).join(".") || "dato"}: ${e.msg}`).join(" · ");
  return d || "No se pudo completar la operación";
}

async function api(ruta, { metodo = "GET", cuerpo } = {}) {
  const res = await fetch(ruta, {
    method: metodo,
    headers: { Authorization: `Bearer ${estado.token}`, ...(cuerpo ? { "Content-Type": "application/json" } : {}) },
    body: cuerpo ? JSON.stringify(cuerpo) : undefined,
  });
  if (res.status === 401) {
    salir();
    throw new Error("La sesión ya no es válida");
  }
  if (res.status === 204) return null;
  const datos = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(mensajeDe(datos));
  return datos;
}

/** Ejecuta una acción y avisa el resultado; el error de la API se muestra tal cual. */
async function hacer(accion, exito) {
  try {
    const resultado = await accion();
    if (exito) avisar(exito);
    return resultado ?? true;
  } catch (e) {
    avisar(e.message, "error");
    return false;
  }
}

// ───────────────────────── Entrada ─────────────────────────

async function pantallaEntrada() {
  $("menu").innerHTML = "";
  $("sesion").innerHTML = "";
  let usuarios = [];
  try {
    usuarios = await (await fetch("/demo/usuarios")).json();
  } catch {
    usuarios = [];
  }
  const vista = $("vista");
  vista.innerHTML = `<section class="tarjeta entrada"><h2>Entrar</h2>
    ${usuarios.length
      ? `<p class="suave">Elige con qué rol quieres probar el sistema.</p><div class="roles">${usuarios
          .map((u) => `<button class="principal" data-rol="${esc(u.rol)}" data-token="${esc(u.token)}" data-nombre="${esc(u.nombre)}">${esc(u.nombre)} <small>(${esc(u.rol)})</small></button>`)
          .join("")}</div>`
      : `<p class="suave">Pega el token de tu usuario (se imprime al arrancar la API) y elige su rol.</p>`}
    <form id="entrar" class="fila">
      <label>Token<input name="token" autocomplete="off" required></label>
      <label>Rol<select name="rol">${["gerente", "almacenista", "cajero", "barista"].map((r) => `<option>${r}</option>`).join("")}</select></label>
      <button class="suave" type="submit">Entrar con token</button>
    </form></section>`;
  vista.querySelectorAll("[data-token]").forEach((b) => b.addEventListener("click", () => entrar(b.dataset.token, b.dataset.rol, b.dataset.nombre)));
  $("entrar").addEventListener("submit", (e) => {
    e.preventDefault();
    const f = new FormData(e.target);
    entrar(f.get("token").trim(), f.get("rol"), f.get("rol"));
  });
}

function entrar(token, rol, nombre) {
  Object.assign(estado, { token, rol, nombre, seccion: "productos" });
  sessionStorage.setItem("token", token);
  sessionStorage.setItem("rol", rol);
  sessionStorage.setItem("nombre", nombre);
  iniciar();
}

function salir() {
  sessionStorage.clear();
  Object.assign(estado, { token: null, rol: null, nombre: null });
  pantallaEntrada();
}

// ───────────────────────── Estructura ─────────────────────────

function dibujarMarco() {
  $("menu").innerHTML = SECCIONES.filter(([, , permiso]) => !permiso || puede(permiso))
    .map(([id, texto]) => `<button data-seccion="${id}" ${id === estado.seccion ? 'aria-current="page"' : ""}>${texto}</button>`)
    .join("");
  $("menu").querySelectorAll("button").forEach((b) => b.addEventListener("click", () => ir(b.dataset.seccion)));
  $("sesion").innerHTML = `<span>${esc(estado.nombre)} · <strong>${esc(estado.rol)}</strong></span><button class="suave" id="salir">Salir</button>`;
  $("salir").addEventListener("click", salir);
}

async function ir(seccion) {
  estado.seccion = seccion;
  dibujarMarco();
  const vistas = { productos, venta, compras, mermas, alertas, bitacora, ingresos };
  try {
    await vistas[seccion]();
  } catch (e) {
    $("vista").innerHTML = `<p class="vacio">${esc(e.message)}</p>`;
  }
  $("vista").focus();
}

async function cargarProductos(inactivos = false) {
  estado.productos = await api(`/productos${inactivos ? "?incluir_inactivos=true" : ""}`);
  return estado.productos;
}

const opciones = (lista, filtro = () => true) => lista.filter(filtro).map((p) => `<option value="${p.id}">${esc(p.nombre_interno)} (${esc(p.sku)})</option>`).join("");

// ───────────────────────── Productos ─────────────────────────

async function productos() {
  const inactivos = $("vista").dataset.inactivos === "1";
  const lista = await cargarProductos(inactivos);
  const filas = lista
    .map((p) => `<tr>
      <td><button class="suave" data-ver="${p.id}">${esc(p.nombre_interno)}</button><div class="suave">${esc(p.sku)} · ${esc(p.codigo_barras)}</div></td>
      <td>${esc(p.tipo)}</td>
      <td class="num">${cantidad(p.stock_actual)} ${esc(p.unidad_base)}<div class="suave">mín. ${cantidad(p.stock_minimo)}</div></td>
      <td class="num">${dinero(p.precio_base)}<div class="suave">con impuestos ${dinero(p.precio_con_impuestos)}</div></td>
      <td class="num">${dinero(p.costo_unitario)}</td>
      <td>${p.estado === "activo" ? "" : '<span class="etiqueta error">Inactivo</span> '}${p.requiere_reabastecer ? '<span class="etiqueta alerta">Reabastecer</span>' : ""}${(p.avisos ?? []).map((a) => `<div class="suave">${esc(a)}</div>`).join("")}</td>
    </tr>`)
    .join("");
  $("vista").innerHTML = `
    <section class="tarjeta"><div class="fila" style="justify-content:space-between"><h2>Catálogo</h2>
      <label style="grid-auto-flow:column;align-items:center"><input type="checkbox" id="ver-inactivos" ${inactivos ? "checked" : ""}> Ver inactivos</label></div>
      ${lista.length ? `<table><thead><tr><th>Producto</th><th>Tipo</th><th class="num">Existencias</th><th class="num">Precio</th><th class="num">Costo</th><th>Estado</th></tr></thead><tbody>${filas}</tbody></table>` : '<p class="vacio">No hay productos todavía.</p>'}
    </section>
    ${puede("catalogo") ? formularioProducto() : ""}`;
  $("ver-inactivos").addEventListener("change", (e) => {
    $("vista").dataset.inactivos = e.target.checked ? "1" : "0";
    productos();
  });
  $("vista").querySelectorAll("[data-ver]").forEach((b) => b.addEventListener("click", () => detalleProducto(Number(b.dataset.ver))));
  $("nuevo")?.addEventListener("submit", crearProducto);
}

function formularioProducto() {
  return `<section class="tarjeta"><h2>Nuevo producto</h2>
    <form id="nuevo" class="fila">
      <label>SKU<input name="sku" required maxlength="40"></label>
      <label>Código de barras<input name="codigo_barras" required maxlength="40"></label>
      <label>Nombre interno<input name="nombre_interno" required maxlength="120"></label>
      <label>Tipo<select name="tipo"><option value="reventa">Reventa</option><option value="compuesto">Compuesto (con receta)</option><option value="insumo">Insumo</option></select></label>
      <label>Unidad base<select name="unidad_base"><option value="pieza">pieza</option><option value="g">g</option><option value="ml">ml</option></select></label>
      <label>Unidad de compra<input name="unidad_compra" value="pieza" required maxlength="20"></label>
      <label>Factor de compra<input name="factor_compra" type="number" step="any" value="1" title="Unidades base que trae una unidad de compra"></label>
      <label>Precio base<input name="precio_base" type="number" step="0.01" required></label>
      <label>IVA<input name="iva_tasa" type="number" step="0.01" value="0.16"></label>
      <label>IEPS<input name="ieps_tasa" type="number" step="0.01" value="0"></label>
      <label>Costo<input name="costo_unitario" type="number" step="0.01" value="0"></label>
      <label>Stock mínimo<input name="stock_minimo" type="number" step="any" value="0"></label>
      <button class="principal" type="submit">Crear producto</button>
    </form></section>`;
}

async function crearProducto(e) {
  e.preventDefault();
  const datos = Object.fromEntries(new FormData(e.target));
  const bien = await hacer(() => api("/productos", { metodo: "POST", cuerpo: datos }), "Producto creado");
  if (bien) productos();
}

async function detalleProducto(id) {
  const [p, lotes, kardex] = await Promise.all([api(`/productos/${id}`), api(`/productos/${id}/lotes`), api(`/productos/${id}/kardex`)]);
  const dlg = $("detalle");
  dlg.innerHTML = `
    <div class="fila" style="justify-content:space-between"><h2>${esc(p.nombre_interno)}</h2><button class="suave" id="cerrar">Cerrar</button></div>
    <p class="suave">${esc(p.sku)} · ${esc(p.tipo)} · ${cantidad(p.stock_actual)} ${esc(p.unidad_base)} en existencia · IVA ${Number(p.impuestos.iva_tasa) * 100}% IEPS ${Number(p.impuestos.ieps_tasa) * 100}%</p>
    ${puede("precios") ? `<form id="precios" class="fila"><label>Precio base<input name="precio_base" type="number" step="0.01" value="${p.precio_base}"></label><label>Costo<input name="costo_unitario" type="number" step="0.01" value="${p.costo_unitario}"></label><button class="principal">Guardar precios</button></form>` : ""}
    ${puede("catalogo") ? `<form id="datos" class="fila"><label>Nombre interno<input name="nombre_interno" value="${esc(p.nombre_interno)}"></label><label>Stock mínimo<input name="stock_minimo" type="number" step="any" value="${p.stock_minimo}"></label><button class="suave">Guardar datos</button></form>` : ""}
    <h3>Lotes (salen en orden PEPS: el que entró primero)</h3>
    ${lotes.length ? `<table><thead><tr><th>Entrada</th><th>Caducidad</th><th class="num">Inicial</th><th class="num">Disponible</th><th class="num">Costo</th></tr></thead><tbody>${lotes
      .map((l) => `<tr><td>${fecha(l.fecha_entrada)}</td><td>${l.caducidad ?? "—"}</td><td class="num">${cantidad(l.cantidad_inicial)}</td><td class="num">${cantidad(l.cantidad_disponible)}</td><td class="num">${dinero(l.costo_unitario)}</td></tr>`)
      .join("")}</tbody></table>` : '<p class="vacio">Sin lotes.</p>'}
    <h3>Kardex</h3>
    ${kardex.length ? `<table><thead><tr><th>Fecha</th><th>Movimiento</th><th class="num">Cantidad</th><th class="num">Saldo</th><th>Usuario</th><th>Motivo</th></tr></thead><tbody>${kardex
      .map((m) => `<tr><td>${fecha(m.fecha)}</td><td>${esc(m.tipo)}</td><td class="num">${cantidad(m.cantidad)}</td><td class="num">${cantidad(m.saldo)}</td><td>${esc(m.usuario)}</td><td>${esc(m.motivo ?? "")}</td></tr>`)
      .join("")}</tbody></table>` : '<p class="vacio">Sin movimientos.</p>'}
    ${p.tipo === "compuesto" && puede("receta") ? formularioReceta(p) : ""}
    ${puede("eliminar") ? `<p><button class="suave peligro" id="eliminar">Eliminar producto</button> <span class="suave">Con historial pasa a inactivo; sin historial se borra.</span></p>` : ""}`;
  dlg.showModal();
  $("cerrar").addEventListener("click", () => dlg.close());
  const cambiar = (formulario, claves) => async (ev) => {
    ev.preventDefault();
    const cuerpo = {};
    for (const k of claves) {
      const v = new FormData(ev.target).get(k);
      if (v !== "" && v !== null) cuerpo[k] = v;
    }
    if (await hacer(() => api(`/productos/${id}`, { metodo: "PATCH", cuerpo }), "Producto actualizado")) {
      dlg.close();
      productos();
    }
  };
  $("precios")?.addEventListener("submit", cambiar("precios", ["precio_base", "costo_unitario"]));
  $("datos")?.addEventListener("submit", cambiar("datos", ["nombre_interno", "stock_minimo"]));
  $("receta")?.addEventListener("submit", async (ev) => {
    ev.preventDefault();
    const f = new FormData(ev.target);
    const cuerpo = { insumos: [{ insumo_id: Number(f.get("insumo_id")), cantidad: f.get("cantidad") }] };
    if (await hacer(() => api(`/productos/${id}/receta`, { metodo: "PUT", cuerpo }), "Receta guardada")) dlg.close();
  });
  $("eliminar")?.addEventListener("click", async () => {
    if (!confirm(`¿Eliminar ${p.nombre_interno}?`)) return;
    if (await hacer(() => api(`/productos/${id}`, { metodo: "DELETE" }), "Producto eliminado")) {
      dlg.close();
      productos();
    }
  });
}

function formularioReceta(p) {
  return `<h3>Receta</h3><p class="suave">Lo que descuenta cada venta (un insumo por guardado: reemplaza la receta anterior).</p>
    <form id="receta" class="fila"><label>Insumo<select name="insumo_id">${opciones(estado.productos, (x) => x.tipo !== "compuesto" && x.id !== p.id)}</select></label>
    <label>Cantidad por unidad<input name="cantidad" type="number" step="any" min="0" required></label><button class="suave">Guardar receta</button></form>`;
}

// ───────────────────────── Venta ─────────────────────────

const carrito = [];

async function venta() {
  await cargarProductos();
  dibujarVenta();
}

function dibujarVenta() {
  const total = carrito.reduce((t, l) => t + Number(l.producto.precio_con_impuestos) * Number(l.cantidad), 0);
  $("vista").innerHTML = `<section class="tarjeta"><h2>Nueva venta</h2>
    <form id="linea" class="fila"><label>Producto<select name="producto">${opciones(estado.productos)}</select></label>
      <label>Cantidad<input name="cantidad" type="number" step="any" min="0" value="1" required></label><button class="suave">Agregar</button></form>
    ${carrito.length ? `<table><thead><tr><th>Producto</th><th class="num">Cantidad</th><th class="num">Precio con impuestos</th><th class="num">Importe</th><th></th></tr></thead><tbody>${carrito
      .map((l, i) => `<tr><td>${esc(l.producto.nombre_interno)}</td><td class="num">${cantidad(l.cantidad)}</td><td class="num">${dinero(l.producto.precio_con_impuestos)}</td><td class="num">${dinero(Number(l.producto.precio_con_impuestos) * Number(l.cantidad))}</td><td><button class="suave" data-quitar="${i}">Quitar</button></td></tr>`)
      .join("")}</tbody></table><p><strong>Total ${dinero(total)}</strong> <button class="principal" id="cobrar">Cobrar</button></p>` : '<p class="vacio">Agrega productos a la venta.</p>'}
  </section>`;
  $("linea").addEventListener("submit", (e) => {
    e.preventDefault();
    const f = new FormData(e.target);
    const producto = estado.productos.find((p) => p.id === Number(f.get("producto")));
    if (producto) carrito.push({ producto, cantidad: f.get("cantidad") });
    dibujarVenta();
  });
  $("vista").querySelectorAll("[data-quitar]").forEach((b) => b.addEventListener("click", () => { carrito.splice(Number(b.dataset.quitar), 1); dibujarVenta(); }));
  $("cobrar")?.addEventListener("click", async () => {
    const cuerpo = { lineas: carrito.map((l) => ({ producto_id: l.producto.id, cantidad: l.cantidad })) };
    const res = await hacer(() => api("/ventas", { metodo: "POST", cuerpo }));
    if (res) {
      avisar(`Venta #${res.venta_id} registrada por ${dinero(res.total)}`);
      carrito.length = 0;
      venta();
    }
  });
}

// ───────────────────────── Compras ─────────────────────────

async function compras() {
  await cargarProductos();
  const comprables = estado.productos.filter((p) => p.tipo !== "compuesto");
  $("vista").innerHTML = `<section class="tarjeta"><h2>Registrar compra</h2>
    <p class="suave">La cantidad va en unidades de compra (cajas, costales…); el sistema la convierte a la unidad base con el factor del producto.</p>
    <form id="compra" class="fila"><label>Producto<select name="producto_id">${opciones(comprables)}</select></label>
      <label>Cantidad<input name="cantidad" type="number" step="any" min="0" required></label>
      <label>Costo por unidad de compra<input name="costo_unitario" type="number" step="0.01" min="0" required></label>
      <label>Caducidad<input name="caducidad" type="date"></label><button class="principal">Registrar compra</button></form></section>`;
  $("compra").addEventListener("submit", async (e) => {
    e.preventDefault();
    const cuerpo = Object.fromEntries([...new FormData(e.target)].filter(([, v]) => v !== ""));
    cuerpo.producto_id = Number(cuerpo.producto_id);
    const res = await hacer(() => api("/compras", { metodo: "POST", cuerpo }));
    if (res) {
      avisar(`Compra registrada: ${res.producto.nombre_interno} ahora tiene ${cantidad(res.producto.stock_actual)} ${res.producto.unidad_base} y costo ${dinero(res.producto.costo_unitario)}`);
      e.target.reset();
    }
  });
}

// ───────────────────────── Mermas y ajustes ─────────────────────────

async function mermas() {
  await cargarProductos();
  $("vista").innerHTML = `
    <section class="tarjeta"><h2>Registrar merma</h2><p class="suave">Producto que se tira o se echa a perder: sale del stock y no genera ingreso.</p>
      <form id="merma" class="fila"><label>Producto<select name="producto_id">${opciones(estado.productos.filter((p) => p.tipo !== "compuesto"))}</select></label>
        <label>Cantidad<input name="cantidad" type="number" step="any" min="0" required></label><label>Motivo<input name="motivo" required maxlength="200"></label><button class="principal">Registrar merma</button></form></section>
    ${puede("ajustes") ? `<section class="tarjeta"><h2>Ajuste por conteo físico</h2><p class="suave">Positivo si sobra, negativo si falta. Queda en la bitácora con el valor anterior y el nuevo.</p>
      <form id="ajuste" class="fila"><label>Producto<select name="producto_id">${opciones(estado.productos.filter((p) => p.tipo !== "compuesto"))}</select></label>
        <label>Cantidad<input name="cantidad" type="number" step="any" required></label><label>Motivo<input name="motivo" required maxlength="200"></label><button class="principal">Registrar ajuste</button></form></section>` : ""}`;
  const enviar = (ruta, texto) => async (e) => {
    e.preventDefault();
    const cuerpo = Object.fromEntries(new FormData(e.target));
    cuerpo.producto_id = Number(cuerpo.producto_id);
    if (await hacer(() => api(ruta, { metodo: "POST", cuerpo }), texto)) e.target.reset();
  };
  $("merma").addEventListener("submit", enviar("/mermas", "Merma registrada"));
  $("ajuste")?.addEventListener("submit", enviar("/ajustes", "Ajuste registrado"));
}

// ───────────────────────── Alertas, bitácora e ingresos ─────────────────────────

async function alertas() {
  const pendientes = $("vista").dataset.todas !== "1";
  const lista = await api(`/alertas?pendientes=${pendientes}`);
  $("vista").innerHTML = `<section class="tarjeta"><div class="fila" style="justify-content:space-between"><h2>Alertas de reabastecimiento</h2>
    <label style="grid-auto-flow:column;align-items:center"><input type="checkbox" id="todas" ${pendientes ? "" : "checked"}> Incluir atendidas</label></div>
    ${lista.length ? `<table><thead><tr><th>Fecha</th><th>Mensaje</th><th>Estado</th></tr></thead><tbody>${lista
      .map((a) => `<tr><td>${fecha(a.fecha)}</td><td>${esc(a.mensaje)}</td><td>${a.atendida ? '<span class="etiqueta ok">Atendida</span>' : '<span class="etiqueta alerta">Pendiente</span>'}</td></tr>`)
      .join("")}</tbody></table>` : '<p class="vacio">Sin alertas.</p>'}</section>`;
  $("todas").addEventListener("change", (e) => {
    $("vista").dataset.todas = e.target.checked ? "1" : "0";
    alertas();
  });
}

async function bitacora() {
  const lista = await api("/auditoria");
  $("vista").innerHTML = `<section class="tarjeta"><h2>Bitácora de cambios</h2><p class="suave">Quién cambió qué, con el valor anterior y el nuevo.</p>
    ${lista.length ? `<table><thead><tr><th>Fecha</th><th>Entidad</th><th>Campo</th><th>Antes</th><th>Después</th><th>Usuario</th></tr></thead><tbody>${[...lista].reverse()
      .map((a) => `<tr><td>${fecha(a.fecha)}</td><td>${esc(a.entidad)} #${a.entidad_id}</td><td>${esc(a.campo)}</td><td>${esc(a.valor_anterior ?? "—")}</td><td>${esc(a.valor_nuevo ?? "—")}</td><td>#${a.usuario_id}</td></tr>`)
      .join("")}</tbody></table>` : '<p class="vacio">Todavía no hay cambios registrados.</p>'}</section>`;
}

async function ingresos() {
  const r = await api("/ingresos");
  $("vista").innerHTML = `<section class="tarjeta"><h2>Ingresos</h2><p><strong>${dinero(r.total)}</strong> en ${r.ventas} venta(s).</p></section>`;
}

// ───────────────────────── Arranque ─────────────────────────

// Al cerrar el detalle se vacía: así sus formularios no quedan duplicados en la página
$("detalle").addEventListener("close", () => {
  $("detalle").innerHTML = "";
});

function iniciar() {
  if (!estado.token) return pantallaEntrada();
  ir(estado.seccion);
}

iniciar();
