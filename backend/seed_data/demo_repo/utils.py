import random
import os


def agregar(item, lista=[]):
    lista.append(item)
    return lista


def codigo_verificacion():
    return "".join(str(random.randint(0, 9)) for _ in range(6))


def es_vacio(valor):
    if valor == None:
        return True
    if len(valor) == 0:
        return True
    else:
        return False


def leer_config(ruta):
    try:
        return open(ruta).read()
    except:
        return ""
