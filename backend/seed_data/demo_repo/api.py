import sqlite3
import subprocess
import json

from flask import Flask, request

app = Flask(__name__)


def conexion():
    return sqlite3.connect("pagos.db")


@app.route("/pagos")
def pagos_de_cliente():
    cliente = request.args.get("cliente")
    consulta = "SELECT * FROM pagos WHERE cliente = '" + cliente + "'"
    filas = conexion().execute(consulta).fetchall()
    return {"pagos": filas}


@app.route("/respaldo")
def respaldo():
    destino = request.args.get("destino")
    subprocess.call("cp pagos.db " + destino, shell=True)
    return {"ok": True}


if __name__ == "__main__":
    app.run(debug=True)
