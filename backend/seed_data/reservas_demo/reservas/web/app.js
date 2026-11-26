"use strict";
/*
 * Interfaz de Reservas Sereno. Sin dependencias ni compilación: usa la API de siempre (token Bearer).
 * Lo que ve cada rol sale de la matriz de permisos del documento de requisitos; la API es la que decide de verdad.
 */

const SECCIONES = [
  ["reservar", "Reservar", ["cliente", "recepcion", "admin"]],
  ["citas", "Mis citas", ["cliente"]],
  ["todas", "Todas las citas", ["recepcion", "admin"]],
  ["agenda", "Agenda", ["recepcion", "admin"]],
  ["servicios", "Servicios", ["admin"]],
  ["personas", "Clientes y equipo", ["admin"]],
  ["anticipos", "Anticipos", ["admin"]],
  ["correos", "Correos (demo)", ["cliente", "recepcion", "admin"]],
];
const LIMITE_HORAS = 24;
const LIMITE_HORAS_PREMIUM = 12;
const ANTICIPO = 0.3;

const sesion = JSON.parse(sessionStorage.getItem("sesion") || "null");
const estado = { sesion, seccion: "reservar", servicios: [], profesionales: [] };
const $ = (id) => document.getElementById(id);
const esc = (t) => String(t ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
const dinero = (v) => Number(v).toLocaleString("es-MX", { style: "currency", currency: "MXN" });
const fecha = (v) => new Date(v).toLocaleString("es-MX", { weekday: "short", day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" });
const rolEs = () => estado.sesion?.rol;
const esPersonal = () => ["recepcion", "admin"].includes(rolEs());

function avisar(texto, tipo = "") {
  const caja = document.createElement("div");
  caja.className = tipo;
  caja.textContent = texto;
  $("aviso").append(caja);
  setTimeout(() => caja.remove(), tipo === "error" ? 8000 : 4000);
}

async function api(ruta, { metodo = "GET", cuerpo, sinToken } = {}) {
  const cabeceras = {};
  if (cuerpo) cabeceras["Content-Type"] = "application/json";
  if (estado.sesion && !sinToken) cabeceras.Authorization = `Bearer ${estado.sesion.token}`;
  const res = await fetch(ruta, { method: metodo, headers: cabeceras, body: cuerpo ? JSON.stringify(cuerpo) : undefined });
  const datos = await res.json().catch(() => ({}));
  if (res.status === 401 && !sinToken && estado.sesion) {
    salir();
    throw new Error("La sesión ya no es válida");
  }
  if (!res.ok) throw new Error(datos.error || "No se pudo completar la operación");
  return datos;
}

async function hacer(accion, exito) {
  try {
    const r = await accion();
    if (exito) avisar(exito);
    return r ?? true;
  } catch (e) {
    avisar(e.message, "error");
    return false;
  }
}

// ───────────────────────── Entrada ─────────────────────────

function pantallaEntrada(modo = "entrar") {
  $("menu").innerHTML = "";
  $("sesion").innerHTML = "";
  const registro = modo === "registro";
  $("vista").innerHTML = `<section class="tarjeta entrada"><h2>${registro ? "Crear cuenta" : "Entrar"}</h2>
    <form id="acceso" class="fila" style="display:grid">
      ${registro ? '<label>Nombre<input name="nombre" required maxlength="80"></label>' : ""}
      <label>Correo<input name="email" type="email" required autocomplete="email"></label>
      <label>Contraseña${registro ? " (mínimo 8 caracteres)" : ""}<input name="clave" type="password" required autocomplete="${registro ? "new-password" : "current-password"}"></label>
      <button class="principal" type="submit">${registro ? "Crear cuenta y entrar" : "Entrar"}</button>
    </form>
    <p><button class="suave" id="cambiar">${registro ? "Ya tengo cuenta" : "Soy cliente nuevo: crear cuenta"}</button></p></section>`;
  $("cambiar").addEventListener("click", () => pantallaEntrada(registro ? "entrar" : "registro"));
  $("acceso").addEventListener("submit", async (e) => {
    e.preventDefault();
    const d = Object.fromEntries(new FormData(e.target));
    const ok = await hacer(async () => {
      if (registro) await api("/clientes", { metodo: "POST", cuerpo: d, sinToken: true });
      const s = await api("/login", { metodo: "POST", cuerpo: { email: d.email, clave: d.clave }, sinToken: true });
      estado.sesion = s;
      sessionStorage.setItem("sesion", JSON.stringify(s));
    });
    if (ok) iniciar();
  });
}

function salir() {
  sessionStorage.clear();
  estado.sesion = null;
  pantallaEntrada();
}

// ───────────────────────── Estructura ─────────────────────────

function dibujarMarco() {
  $("menu").innerHTML = SECCIONES.filter(([, , roles]) => roles.includes(rolEs()))
    .map(([id, texto]) => `<button data-seccion="${id}" ${id === estado.seccion ? 'aria-current="page"' : ""}>${texto}</button>`)
    .join("");
  $("menu").querySelectorAll("button").forEach((b) => b.addEventListener("click", () => ir(b.dataset.seccion)));
  $("sesion").innerHTML = `<span>${esc(estado.sesion.nombre)} · <strong>${esc(rolEs())}</strong>${estado.sesion.premium ? ' <span class="etiqueta ok">Premium</span>' : ""}</span><button class="suave" id="salir">Salir</button>`;
  $("salir").addEventListener("click", salir);
}

async function ir(seccion) {
  estado.seccion = seccion;
  dibujarMarco();
  const vistas = { reservar, citas, todas, agenda, servicios, personas, anticipos, correos };
  try {
    await vistas[seccion]();
  } catch (e) {
    $("vista").innerHTML = `<p class="vacio">${esc(e.message)}</p>`;
  }
  $("vista").focus();
}

async function catalogos() {
  [estado.servicios, estado.profesionales] = await Promise.all([api("/servicios", { sinToken: true }), api("/profesionales", { sinToken: true })]);
}

const opciones = (lista, texto) => lista.map((x) => `<option value="${x.id}">${esc(texto(x))}</option>`).join("");

/** `datetime-local` de la próxima hora en punto, un mínimo razonable para reservar (la regla pide 2 h de anticipación). */
function proximaHora(horas = 3) {
  const d = new Date(Date.now() + horas * 3600_000);
  d.setMinutes(0, 0, 0);
  d.setMinutes(d.getMinutes() - d.getTimezoneOffset());
  return d.toISOString().slice(0, 16);
}

// ───────────────────────── Reservar ─────────────────────────

async function reservar() {
  await catalogos();
  const servicio = estado.servicios[0];
  $("vista").innerHTML = `<section class="tarjeta"><h2>Reservar una cita</h2>
    <p class="suave">Atendemos de lunes a sábado, de 9:00 a 20:00. Se reserva con al menos 2 horas de anticipación y se pagan el 30 % como anticipo. Máximo 3 citas activas por cliente.</p>
    ${estado.servicios.length && estado.profesionales.length ? `<form id="reserva" class="fila">
      <label>Servicio<select name="servicio_id">${opciones(estado.servicios, (s) => `${s.nombre} · ${s.duracion_min} min · ${dinero(s.precio)}`)}</select></label>
      <label>Profesional<select name="profesional_id">${opciones(estado.profesionales, (p) => p.nombre)}</select></label>
      <label>Fecha y hora<input name="inicio" type="datetime-local" step="900" value="${proximaHora()}" required></label>
      ${esPersonal() ? '<label>ID del cliente<input name="cliente_id" type="number" min="1" required></label>' : ""}
      <button class="principal" type="submit">Reservar</button></form>
      <p class="suave" id="anticipo">Anticipo: ${dinero(Number(servicio.precio) * ANTICIPO)}</p>`
      : '<p class="vacio">Todavía no hay servicios o profesionales: el administrador debe darlos de alta.</p>'}</section>`;
  $("reserva")?.addEventListener("change", (e) => {
    const s = estado.servicios.find((x) => x.id === Number(new FormData(e.currentTarget).get("servicio_id")));
    $("anticipo").textContent = `Anticipo: ${dinero(Number(s.precio) * ANTICIPO)}`;
  });
  $("reserva")?.addEventListener("submit", async (e) => {
    e.preventDefault();
    const d = Object.fromEntries(new FormData(e.target));
    const cuerpo = { servicio_id: Number(d.servicio_id), profesional_id: Number(d.profesional_id), inicio: d.inicio };
    if (d.cliente_id) cuerpo.cliente_id = Number(d.cliente_id);
    const c = await hacer(() => api("/citas", { metodo: "POST", cuerpo }));
    if (c) {
      avisar(`Cita confirmada · folio ${c.folio} · anticipo ${dinero(c.anticipo)}. Te enviamos un correo.`);
      ir(rolEs() === "cliente" ? "citas" : "todas");
    }
  });
}

// ───────────────────────── Citas ─────────────────────────

/** Lo que pasaría si se cancela ahora (misma regla que la API: más de 24 h, o 12 h si es premium, devuelve todo el anticipo). */
function consecuencia(c, premium) {
  const horas = (new Date(c.inicio) - Date.now()) / 3600_000;
  const limite = premium ? LIMITE_HORAS_PREMIUM : LIMITE_HORAS;
  return horas > limite ? `Se reembolsa el anticipo (${dinero(c.anticipo)})` : "Sin reembolso: ya pasó el plazo para cancelar";
}

function tablaCitas(lista, { cancelar = true, cliente = false } = {}) {
  if (!lista.length) return '<p class="vacio">No hay citas.</p>';
  return `<table><thead><tr><th>Folio</th>${cliente ? "<th>Cliente</th>" : ""}<th>Servicio</th><th>Cuándo</th><th>Estado</th><th class="num">Anticipo</th><th></th></tr></thead><tbody>${lista
    .map((c) => `<tr><td>${esc(c.folio)}</td>${cliente ? `<td>#${c.cliente_id}</td>` : ""}<td>${esc(c.servicio)}</td><td>${fecha(c.inicio)} – ${new Date(c.fin).toLocaleTimeString("es-MX", { hour: "2-digit", minute: "2-digit" })}</td>
      <td>${c.estado === "confirmada" ? '<span class="etiqueta ok">Confirmada</span>' : `<span class="etiqueta">Cancelada</span><div class="suave">Reembolso ${dinero(c.reembolso ?? 0)}</div>`}</td>
      <td class="num">${dinero(c.anticipo)}</td>
      <td>${cancelar && c.estado === "confirmada" ? `<button class="suave peligro" data-cancelar="${c.id}" title="${esc(consecuencia(c, estado.sesion.premium))}">Cancelar</button><div class="suave">${esc(consecuencia(c, estado.sesion.premium))}</div>` : ""}</td></tr>`)
    .join("")}</tbody></table>`;
}

function enlazarCancelar(volver) {
  $("vista").querySelectorAll("[data-cancelar]").forEach((b) => b.addEventListener("click", async () => {
    if (!confirm("¿Cancelar la cita?")) return;
    const c = await hacer(() => api(`/citas/${b.dataset.cancelar}/cancelar`, { metodo: "POST" }));
    if (c) {
      avisar(`Cita cancelada. Reembolso: ${dinero(c.reembolso)}`, Number(c.reembolso) > 0 ? "" : "alerta");
      volver();
    }
  }));
}

async function citas() {
  const lista = await api("/citas");
  const activas = lista.filter((c) => c.estado === "confirmada" && new Date(c.inicio) > Date.now()).length;
  $("vista").innerHTML = `<section class="tarjeta"><h2>Mis citas</h2><p class="suave">${activas} de 3 citas activas.</p>${tablaCitas(lista)}</section>`;
  enlazarCancelar(citas);
}

async function todas() {
  const lista = await api("/citas");
  $("vista").innerHTML = `<section class="tarjeta"><div class="fila" style="justify-content:space-between"><h2>Todas las citas</h2>
    <button class="suave" id="recordar">Enviar recordatorios (próximas 24 h)</button></div>${tablaCitas(lista, { cliente: true })}</section>`;
  enlazarCancelar(todas);
  $("recordar").addEventListener("click", async () => {
    const r = await hacer(() => api("/tareas/recordatorios", { metodo: "POST" }));
    if (r) avisar(`Recordatorios enviados: ${r.enviados}`);
  });
}

async function agenda() {
  await catalogos();
  const id = Number($("vista").dataset.profesional || estado.profesionales[0]?.id || 0);
  const lista = id ? await api(`/profesionales/${id}/agenda`) : [];
  $("vista").dataset.profesional = id;
  $("vista").innerHTML = `<section class="tarjeta"><div class="fila" style="justify-content:space-between"><h2>Agenda por profesional</h2>
    <label>Profesional<select id="quien">${opciones(estado.profesionales, (p) => p.nombre).replace(`value="${id}"`, `value="${id}" selected`)}</select></label></div>${tablaCitas(lista, { cancelar: false, cliente: true })}</section>`;
  $("quien").addEventListener("change", (e) => {
    $("vista").dataset.profesional = e.target.value;
    agenda();
  });
}

// ───────────────────────── Administración ─────────────────────────

async function servicios() {
  await catalogos();
  $("vista").innerHTML = `
    <section class="tarjeta"><h2>Servicios</h2>${estado.servicios.length ? `<table><thead><tr><th>Servicio</th><th class="num">Duración</th><th class="num">Precio</th><th></th></tr></thead><tbody>${estado.servicios
      .map((s) => `<tr><td>${esc(s.nombre)}</td><td class="num">${s.duracion_min} min</td><td class="num">${dinero(s.precio)}</td>
        <td><form class="fila" data-precio="${s.id}"><input name="precio" type="number" step="0.01" min="0" placeholder="Nuevo precio" required style="width:9em"><button class="suave">Cambiar precio</button></form></td></tr>`)
      .join("")}</tbody></table>` : '<p class="vacio">Sin servicios.</p>'}</section>
    <section class="tarjeta"><h2>Nuevo servicio</h2><form id="servicio" class="fila"><label>Nombre<input name="nombre" required></label>
      <label>Duración (min)<input name="duracion_min" type="number" min="1" required></label><label>Precio<input name="precio" type="number" step="0.01" min="0" required></label><button class="principal">Crear servicio</button></form></section>
    <section class="tarjeta"><h2>Profesionales</h2><p class="suave">${estado.profesionales.map((p) => esc(p.nombre)).join(", ") || "Sin profesionales."}</p>
      <form id="profesional" class="fila"><label>Nombre<input name="nombre" required></label><button class="principal">Agregar profesional</button></form></section>`;
  $("vista").querySelectorAll("[data-precio]").forEach((f) => f.addEventListener("submit", async (e) => {
    e.preventDefault();
    if (await hacer(() => api(`/servicios/${f.dataset.precio}`, { metodo: "PATCH", cuerpo: { precio: new FormData(f).get("precio") } }), "Precio actualizado")) servicios();
  }));
  $("servicio").addEventListener("submit", async (e) => {
    e.preventDefault();
    if (await hacer(() => api("/servicios", { metodo: "POST", cuerpo: Object.fromEntries(new FormData(e.target)) }), "Servicio creado")) servicios();
  });
  $("profesional").addEventListener("submit", async (e) => {
    e.preventDefault();
    if (await hacer(() => api("/profesionales", { metodo: "POST", cuerpo: Object.fromEntries(new FormData(e.target)) }), "Profesional agregado")) servicios();
  });
}

async function personas() {
  $("vista").innerHTML = `<section class="tarjeta"><h2>Cliente premium</h2>
    <p class="suave">Un cliente premium cancela sin cargo hasta 12 horas antes (el resto, hasta 24). El ID del cliente se ve en «Todas las citas».</p>
    <form id="premium" class="fila"><label>ID del cliente<input name="id" type="number" min="1" required></label>
      <label>Premium<select name="premium"><option value="true">Sí</option><option value="false">No</option></select></label><button class="principal">Guardar</button></form></section>`;
  $("premium").addEventListener("submit", async (e) => {
    e.preventDefault();
    const f = new FormData(e.target);
    const c = await hacer(() => api(`/clientes/${f.get("id")}`, { metodo: "PATCH", cuerpo: { premium: f.get("premium") === "true" } }));
    if (c) avisar(`${c.nombre}: ${c.premium ? "ahora es premium" : "ya no es premium"}`);
  });
}

async function anticipos() {
  const r = await api("/reportes/anticipos");
  $("vista").innerHTML = `<section class="tarjeta"><h2>Anticipos</h2>
    <table><tbody><tr><th>Cobrado</th><td class="num">${dinero(r.cobrado)}</td></tr><tr><th>Reembolsado</th><td class="num">${dinero(r.reembolsado)}</td></tr><tr><th>Neto</th><td class="num"><strong>${dinero(r.neto)}</strong></td></tr></tbody></table></section>`;
}

async function correos() {
  const lista = await api("/demo/correos", { sinToken: true });
  $("vista").innerHTML = `<section class="tarjeta"><h2>Correos enviados (demostración)</h2>
    <p class="suave">En una instalación real salen por SMTP. Aquí se ven los últimos para comprobar confirmaciones, cancelaciones y recordatorios. Requiere RESERVAS_DEMO=1.</p>
    ${lista.length ? lista.map((m) => `<div class="tarjeta"><strong>${esc(m.asunto)}</strong><div class="suave">Para ${esc(m.para)}</div><p>${esc(m.cuerpo)}</p></div>`).join("") : '<p class="vacio">Todavía no hay correos.</p>'}</section>`;
}

// ───────────────────────── Arranque ─────────────────────────

function iniciar() {
  if (!estado.sesion) return pantallaEntrada();
  const permitidas = SECCIONES.filter(([, , roles]) => roles.includes(rolEs())).map(([id]) => id);
  if (!permitidas.includes(estado.seccion)) estado.seccion = permitidas[0];
  ir(estado.seccion);
}

iniciar();
