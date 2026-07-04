"""Integraciones externas de Estación de Pedidos.

Contiene las fachadas a servicios de terceros (SUNAT, PedidosYa, etc.).
Estos módulos no acceden directamente a la base de datos; las rutas que los
consumen se encargan de persistir los resultados cuando corresponde.
"""
