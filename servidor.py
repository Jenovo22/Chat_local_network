import socket
import threading
from datetime import datetime


# ============================================================
# CONFIGURACIÓN DEL SERVIDOR
# ============================================================

HOST = "0.0.0.0"
PORT = 5000
MAX_CLIENTES = 10


# ============================================================
# VARIABLES GLOBALES
# ============================================================

# Diccionario:
# socket_cliente -> nombre_usuario
clientes = {}

# Locks para evitar problemas entre múltiples hilos
clientes_lock = threading.Lock()
historial_lock = threading.Lock()


# ============================================================
# ARCHIVO DE HISTORIAL
# ============================================================

fecha_actual = datetime.now().strftime("%Y-%m-%d")

ARCHIVO_HISTORIAL = f"historial_{fecha_actual}.txt"


# ============================================================
# GUARDAR MENSAJES EN EL HISTORIAL
# ============================================================

def guardar_historial(mensaje):
    hora = datetime.now().strftime("%H:%M:%S")

    linea = f"[{hora}] {mensaje}"

    with historial_lock:
        with open(
            ARCHIVO_HISTORIAL,
            "a",
            encoding="utf-8"
        ) as archivo:
            archivo.write(linea + "\n")


# ============================================================
# ENVIAR UN MENSAJE TCP
# ============================================================

def enviar_mensaje(cliente, mensaje):
    """
    Cada mensaje termina con \n.

    Esto nos permitirá separar correctamente los mensajes
    cuando construyamos cliente.py.
    """

    datos = (mensaje + "\n").encode("utf-8")

    cliente.sendall(datos)


# ============================================================
# ENVIAR MENSAJE A TODOS LOS CLIENTES
# ============================================================

def enviar_a_todos(mensaje, excluir=None):

    with clientes_lock:
        clientes_actuales = list(clientes.keys())

    clientes_con_error = []

    for cliente in clientes_actuales:

        if cliente == excluir:
            continue

        try:
            enviar_mensaje(cliente, mensaje)

        except (ConnectionResetError, BrokenPipeError, OSError):
            clientes_con_error.append(cliente)

    for cliente in clientes_con_error:
        eliminar_cliente(cliente)


# ============================================================
# ELIMINAR CLIENTE
# ============================================================

def eliminar_cliente(cliente):

    with clientes_lock:
        nombre = clientes.pop(cliente, None)

    try:
        cliente.close()
    except OSError:
        pass

    if nombre:

        mensaje = f"{nombre} se ha desconectado."

        print(mensaje)

        guardar_historial(mensaje)

        enviar_a_todos(
            f"SISTEMA: {nombre} se ha desconectado."
        )


# ============================================================
# MANEJAR CADA CLIENTE
# ============================================================

def manejar_cliente(cliente, direccion):

    nombre = None

    try:

        # ----------------------------------------------------
        # 1. Solicitar nombre
        # ----------------------------------------------------

        enviar_mensaje(
            cliente,
            "NOMBRE"
        )

        # Creamos un lector para trabajar línea por línea.
        lector = cliente.makefile(
            "r",
            encoding="utf-8",
            newline="\n"
        )

        nombre = lector.readline().strip()


        # ----------------------------------------------------
        # 2. Validar nombre
        # ----------------------------------------------------

        if not nombre:

            enviar_mensaje(
                cliente,
                "ERROR:NOMBRE_INVALIDO"
            )

            return


        # Limitamos longitud para evitar nombres enormes
        if len(nombre) > 30:

            enviar_mensaje(
                cliente,
                "ERROR:NOMBRE_DEMASIADO_LARGO"
            )

            return


        # ----------------------------------------------------
        # 3. Revisar si el nombre ya existe
        # ----------------------------------------------------

        with clientes_lock:

            nombres_actuales = [
                nombre_actual.lower()
                for nombre_actual in clientes.values()
            ]

            if nombre.lower() in nombres_actuales:

                enviar_mensaje(
                    cliente,
                    "ERROR:NOMBRE_EN_USO"
                )

                return

            clientes[cliente] = nombre


        # ----------------------------------------------------
        # 4. Registrar conexión
        # ----------------------------------------------------

        mensaje_conexion = (
            f"{nombre} se ha conectado "
            f"desde {direccion[0]}:{direccion[1]}."
        )

        print(mensaje_conexion)

        guardar_historial(
            mensaje_conexion
        )


        # ----------------------------------------------------
        # 5. Confirmar al cliente
        # ----------------------------------------------------

        enviar_mensaje(
            cliente,
            "OK:CONECTADO"
        )


        # ----------------------------------------------------
        # 6. Avisar a los demás
        # ----------------------------------------------------

        enviar_a_todos(
            f"SISTEMA: {nombre} se ha unido al chat.",
            excluir=cliente
        )


        # ----------------------------------------------------
        # 7. Mostrar usuarios conectados
        # ----------------------------------------------------

        with clientes_lock:
            numero_conectados = len(clientes)

        print(
            f"Usuarios conectados: "
            f"{numero_conectados}/{MAX_CLIENTES}"
        )


        # ----------------------------------------------------
        # 8. Recibir mensajes
        # ----------------------------------------------------

        while True:

            mensaje = lector.readline()

            # Si readline devuelve "", se cerró la conexión.
            if mensaje == "":
                break

            mensaje = mensaje.strip()

            if not mensaje:
                continue


            # ------------------------------------------------
            # Comando para salir
            # ------------------------------------------------

            if mensaje.lower() == "/salir":
                break


            # ------------------------------------------------
            # Mensaje normal
            # ------------------------------------------------

            mensaje_completo = (
                f"{nombre}: {mensaje}"
            )


            # Mostrarlo en el servidor
            print(mensaje_completo)


            # Guardarlo
            guardar_historial(
                mensaje_completo
            )


            # Mandarlo a todos
            enviar_a_todos(
                mensaje_completo
            )


    except ConnectionResetError:

        pass


    except BrokenPipeError:

        pass


    except Exception as error:

        print(
            f"Error con "
            f"{direccion[0]}:{direccion[1]} -> "
            f"{error}"
        )


    finally:

        eliminar_cliente(
            cliente
        )


# ============================================================
# INICIAR SERVIDOR
# ============================================================

def iniciar_servidor():

    servidor = socket.socket(
        socket.AF_INET,
        socket.SOCK_STREAM
    )


    # Permite reiniciar rápidamente el servidor
    servidor.setsockopt(
        socket.SOL_SOCKET,
        socket.SO_REUSEADDR,
        1
    )


    # Asociar socket al puerto
    servidor.bind(
        (HOST, PORT)
    )


    # Esperar conexiones
    servidor.listen(
        MAX_CLIENTES
    )


    # --------------------------------------------------------
    # Información
    # --------------------------------------------------------

    print("=" * 60)
    print("               SERVIDOR DE CHAT TCP")
    print("=" * 60)

    print(f"HOST: {HOST}")
    print(f"PUERTO: {PORT}")
    print(f"Máximo de clientes: {MAX_CLIENTES}")

    print(
        f"Historial: {ARCHIVO_HISTORIAL}"
    )

    print("-" * 60)

    print(
        "IP que usarán los clientes: "
        "172.20.10.5"
    )

    print(
        f"Dirección del servidor: "
        f"172.20.10.5:{PORT}"
    )

    print("=" * 60)

    guardar_historial(
        "SERVIDOR INICIADO"
    )

    print(
        "\nEsperando conexiones...\n"
    )


    # --------------------------------------------------------
    # Aceptar conexiones
    # --------------------------------------------------------

    try:

        while True:

            cliente, direccion = servidor.accept()


            # ------------------------------------------------
            # Comprobar límite de clientes
            # ------------------------------------------------

            with clientes_lock:
                numero_clientes = len(clientes)


            if numero_clientes >= MAX_CLIENTES:

                try:

                    enviar_mensaje(
                        cliente,
                        "ERROR:SERVIDOR_LLENO"
                    )

                finally:

                    cliente.close()

                print(
                    "Conexión rechazada: "
                    "servidor lleno."
                )

                continue


            # ------------------------------------------------
            # Crear hilo para el cliente
            # ------------------------------------------------

            hilo = threading.Thread(
                target=manejar_cliente,
                args=(
                    cliente,
                    direccion
                ),
                daemon=True
            )

            hilo.start()


    # --------------------------------------------------------
    # Ctrl + C
    # --------------------------------------------------------

    except KeyboardInterrupt:

        print(
            "\nServidor detenido por el usuario."
        )

        guardar_historial(
            "SERVIDOR DETENIDO"
        )


    finally:

        with clientes_lock:
            clientes_actuales = list(
                clientes.keys()
            )


        for cliente in clientes_actuales:

            try:

                enviar_mensaje(
                    cliente,
                    "SISTEMA: El servidor se está cerrando."
                )

                cliente.close()

            except OSError:

                pass


        servidor.close()


# ============================================================
# PROGRAMA PRINCIPAL
# ============================================================

if __name__ == "__main__":

    iniciar_servidor()