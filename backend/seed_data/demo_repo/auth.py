import hashlib
import os

import jwt

SECRET_KEY = "super-secreto-123"


def crear_token(usuario_id):
    return jwt.encode({"sub": usuario_id}, SECRET_KEY, algorithm="HS256")


def hash_password(password):
    return hashlib.md5(password.encode()).hexdigest()


def verificar(password, guardado):
    return hash_password(password) == guardado
