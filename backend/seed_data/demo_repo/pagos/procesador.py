from decimal import Decimal


def procesar(pagos, tasa_cambio, comision, limite, moneda_base="MXN"):
    resultado = {"ok": [], "rechazados": [], "total": Decimal(0)}
    for pago in pagos:
        if pago.get("monto") is None:
            resultado["rechazados"].append({"id": pago.get("id"), "motivo": "sin monto"})
            continue
        monto = Decimal(str(pago["monto"]))
        if pago.get("moneda") != moneda_base:
            if pago.get("moneda") in tasa_cambio:
                monto = monto * Decimal(str(tasa_cambio[pago["moneda"]]))
            else:
                resultado["rechazados"].append({"id": pago["id"], "motivo": "moneda"})
                continue
        if monto <= 0:
            resultado["rechazados"].append({"id": pago["id"], "motivo": "monto inválido"})
            continue
        if monto > limite:
            if pago.get("autorizado"):
                if pago.get("autorizado_por") in ("admin", "finanzas"):
                    pass
                else:
                    resultado["rechazados"].append({"id": pago["id"], "motivo": "autorizador"})
                    continue
            else:
                resultado["rechazados"].append({"id": pago["id"], "motivo": "límite"})
                continue
        if comision:
            monto = monto - monto * Decimal(str(comision))
        resultado["ok"].append({"id": pago["id"], "monto": monto, "moneda": moneda_base, "estado": "cobrado"})
        resultado["total"] += monto
    return resultado


def resumen(resultado):
    return f"{len(resultado['ok'])} cobrados, {len(resultado['rechazados'])} rechazados, total {resultado['total']}"
