import random
from datetime import datetime

ESTADOS = [
    "PENDIENTE",
    "ACEPTADO",
    "PREPARANDO",
    "LISTO",
    "EN CAMINO",
    "ENTREGADO"
]


class PedidosYaAPI:

    pedidos = {}

    @classmethod
    def nuevo_pedido(cls):

        pedido = random.randint(1000,9999)

        cls.pedidos[pedido] = {
            "pedido":pedido,
            "cliente":"Cliente Demo",
            "telefono":"999999999",
            "direccion":"Av. Demo 123",
            "estado":"PENDIENTE",
            "fecha":datetime.now().strftime("%d/%m/%Y %H:%M"),
            "productos":[
                {
                    "nombre":"Pizza Familiar",
                    "cantidad":2,
                    "precio":45
                },
                {
                    "nombre":"Gaseosa",
                    "cantidad":1,
                    "precio":8
                }
            ],
            "total":98
        }

        return cls.pedidos[pedido]

    @classmethod
    def obtener_pedidos(cls):
        return list(cls.pedidos.values())

    @classmethod
    def obtener_pedido(cls,idPedido):

        if idPedido not in cls.pedidos:
            return None

        return cls.pedidos[idPedido]

    @classmethod
    def actualizar_estado(cls,idPedido,estado):

        if idPedido not in cls.pedidos:
            return None

        cls.pedidos[idPedido]["estado"] = estado

        return cls.pedidos[idPedido]

    @classmethod
    def aceptar(cls,idPedido):
        return cls.actualizar_estado(idPedido,"ACEPTADO")

    @classmethod
    def preparar(cls,idPedido):
        return cls.actualizar_estado(idPedido,"PREPARANDO")

    @classmethod
    def listo(cls,idPedido):
        return cls.actualizar_estado(idPedido,"LISTO")

    @classmethod
    def camino(cls,idPedido):
        return cls.actualizar_estado(idPedido,"EN CAMINO")

    @classmethod
    def entregar(cls,idPedido):
        return cls.actualizar_estado(idPedido,"ENTREGADO")
