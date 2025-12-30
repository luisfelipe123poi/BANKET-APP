import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog, colorchooser # AÑADIDO: colorchooser
import os
import sys
import subprocess
import threading
import time
import shutil
from PIL import Image, ImageTk
from pydub import AudioSegment
import unicodedata
import re
import asyncio
import edge_tts
import sounddevice as sd
import numpy as np
import io
import wave
import requests
import json
import uuid
import webbrowser
from io import BytesIO

email_global = None
license_global = None
MAIN_LICENSE = {}
APP_VERSION = "1.3.0"
APP_NAME = "TurboClips.exe"
BASE_DIR = os.path.dirname(sys.executable)
VERSION_FILE = os.path.join(BASE_DIR, "version.json")
ONBOARD_FILE = os.path.join(BASE_DIR, "onboard.json")
toast_queue = []
toast_mostrando = False
toast_bloqueando = False
verification_handled = False
exceso_caracteres = {"estado": False}
AUTOSAVE_FILE = "autosave_guion.json"
AZUL_EDITOR = "#1078FF"
audio_source_mode = None
plan_global = ""





BAT_CONTENT = r"""
@echo off
timeout /t 2 >nul
move /y update_new.exe TurboClips.exe
start "" "TurboClips.exe"
"""




print("ESTA ES LA VERSION 1.3.0")


def is_first_run():
    return not os.path.exists(ONBOARD_FILE)


def abrir_comunidad_telegram():
    webbrowser.open("https://t.me/TuCanalTelegram")  # replace

def abrir_bot_telegram():
    webbrowser.open("https://t.me/TuBotDeSoporte")  # replace

def abrir_pagina_web():
    webbrowser.open("https://turboclips.com")  # replace

def abrir_correo_soporte():
    webbrowser.open("mailto:soporte@turboclips.com?subject=Soporte TurboClips")

def mostrar_menu_soporte(event):
    menu_soporte.tk_popup(event.x_root, event.y_root)



BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LICENSE_FILE = os.path.join(BASE_DIR, "license.json")
SERVER_URL = "https://stripe-backend-r14f.onrender.com"   # <-- CAMBIA si usas dominio
license_key_global = None
credits_left_global = 0
credits_global = 0


guiones_tts_pendientes = []


# ------------------------------------------------------------------
## CONFIGURACIÓN GLOBAL Y VARIABLES
# ------------------------------------------------------------------

# Definición de rutas base y directorios
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ENTRADA_DIR = os.path.join(BASE_DIR, "entrada")
GENERADOR_SCRIPT = os.path.join(BASE_DIR, "generador_editor.py") # El otro script

# Crear directorios si no existen
os.makedirs(ENTRADA_DIR, exist_ok=True)
os.makedirs(os.path.join(BASE_DIR, "salida"), exist_ok=True)

# 📣 RUTA DEL DIRECTORIO DE MODELOS DE PIPER (AJUSTA ESTA RUTA SI ES NECESARIO)
PIPER_DIR = r"C:\Users\LUIS CASTELLAR\Documents\selector de videos tiktok\tts_models"
os.makedirs(PIPER_DIR, exist_ok=True)

# Variables globales para el estado
lista_audios_pendientes = []
nombre_prefijo = "" # Variable global que almacena el prefijo establecido
salida_personalizada = os.path.join(BASE_DIR, "salida")
audio_generado_path = None # Variable para almacenar la ruta del último audio TTS generado

# Variables globales para TTS - PIPER
NOMBRE_MODELO_DEFECTO = "es_MX-laura-high.onnx" # Cambia esto si prefieres otro modelo por defecto
voz_seleccionada_path = os.path.join(PIPER_DIR, NOMBRE_MODELO_DEFECTO)
if not os.path.exists(voz_seleccionada_path):
    voz_seleccionada_path = None

# Variables globales para TTS - EDGE-TTS
EDGE_VOZ_DEFECTO = "es-MX-DaliaNeural"
voz_tts_activa = "PIPER" # Modo predeterminado (Puede ser "PIPER" o "EDGE-TTS")
voz_seleccionada_edge = EDGE_VOZ_DEFECTO

# Variables para la GUI
WINDOW_WIDTH = 600
WINDOW_HEIGHT = 770

# Variables para la animación (IDs para cancelación)
current_animation_id = None
current_cleanup_id = None
current_message_id = None
current_big_gif_id = None
current_text_animation_id = None
current_cycle_message_id = None


# Variables de configuración de subtítulos separadas
config_subtitulos_posicion = "abajo"          # Clave: arriba, centro, abajo
config_subtitulos_tamano = "medio"           # CAMBIO: Corregida a 'tamano' (sin tilde)
config_subtitulos_estilo = "resalte_color" # Clave: resalte_color, fondo_zoom, progressive_reveal
config_subtitulos_color_texto = "#FFFFFF"   # NUEVO: Color del texto (blanco por defecto)
config_subtitulos_color_resalte = "#FFC300" # NUEVO: Color de resalte/fondo (amarillo/naranja por defecto)
# ----------------------------------------------------------------

if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Crear otras carpetas necesarias
for folder in ["videos", "paquete_actual"]:
    os.makedirs(os.path.join(BASE_DIR, folder), exist_ok=True)


# ------------------------------------------------------------------
## FUNCIONES AUXILIARES DE LA GUI Y MANEJO DE ARCHIVOS
# ------------------------------------------------------------------

def cargar_licencia_local():
    global license_key_global, credits_left_global, credits_global
    global plan_global, email_global

    if not os.path.exists(LICENSE_FILE):
        email_global = None
        return None

    try:
        with open(LICENSE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)

        license_key_global = data.get("license_key")
        plan_global = data.get("plan")

        credits_global = data.get("credits", 0)
        credits_left_global = data.get("credits_left", 0)
        status = data.get("status", "active")


        email = data.get("email")

        # 🔥 FIX: reparar email vacío consultando servidor
        if (not email or not email.strip()) and license_key_global and SERVER_URL:

            try:
                r = requests.post(
                    f"{SERVER_URL}/license/validate",
                    json={"license_key": license_key_global},
                    timeout=6
                )
                resp = r.json()
                if resp.get("valid"):
                    email = resp["license"].get("email")
                    if email:
                        data["email"] = email
                        with open(LICENSE_FILE, "w", encoding="utf-8") as f:
                            json.dump(data, f, indent=2)
            except Exception:
                pass

        email_global = email if email else None
        return data

    except Exception as e:
        print("Error cargando licencia local:", e)
        email_global = None
        return None

def asegurar_email_obligatorio():
    global email_global

    print(">>> asegurar_email_obligatorio EJECUTADA <<<")
    print("EMAIL AL ENTRAR:", repr(email_global))

    # ------------------------------------------------------
    # 1) Cargar licencia local si existe
    # ------------------------------------------------------
    cargar_licencia_local()

    if email_global:
        return True

    # ------------------------------------------------------
    # 2) Pedir email obligatoriamente
    # ------------------------------------------------------
    while True:
        email = simpledialog.askstring(
            "Inicio de sesión requerido",
            "Ingresa tu correo para iniciar sesión:"
        )

        if not email:
            messagebox.showwarning(
                "Correo obligatorio",
                "Debes ingresar un correo para usar la aplicación."
            )
            continue

        # --------------------------------------------------
        # 3) Solicitar verificación (SOLO envía email)
        # --------------------------------------------------
        ok = solicitar_verificacion(email)

        if not ok:
            messagebox.showerror(
                "Error",
                "No se pudo iniciar la verificación.\nIntenta nuevamente."
            )
            continue

        # --------------------------------------------------
        # 4) Comprobar estado inmediatamente
        # --------------------------------------------------
        try:
            r = requests.get(
                f"{SERVER_URL}/auth/check_status",
                params={"email": email},
                timeout=5
            )
            status = r.json()
        except Exception as e:
            print("Error consultando estado:", e)
            status = {}

        # --------------------------------------------------
        # 5) SI YA ESTÁ VERIFICADO → SINCRONIZAR LICENCIA
        # --------------------------------------------------
        if status.get("verified") is True:
            license_obj = status.get("license")

            root.after(
                0,
                lambda: on_verification_success(email, license_obj)
            )

            return True

        # --------------------------------------------------
        # 6) NO verificado → informar y hacer polling
        # --------------------------------------------------
        

        for _ in range(30):  # ~60 segundos
            time.sleep(2)

            try:
                r = requests.get(
                    f"{SERVER_URL}/auth/check_status",
                    params={"email": email},
                    timeout=5
                )
                status = r.json()

                if status.get("verified"):
                    license_obj = status.get("license")

                    root.after(
                        0,
                        lambda: on_verification_success(email, license_obj)
                    )

                    return True
            except Exception as e:
                print("Error verificando estado:", e)

        messagebox.showwarning(
            "Tiempo agotado",
            "No se detectó la verificación.\n"
            "Puedes intentar nuevamente."
        )

def lanzar_login_si_necesario():
    cargar_licencia_local()

    if email_global:
        print("✔ Email encontrado, no se muestra login")
        return

    if is_first_run():
        root.after(500, mostrar_onboarding)


    print("❌ No hay email, mostrando login")
    mostrar_login_modal()

def es_email_valido(email: str) -> bool:
    if not email:
        return False

    email = email.strip()

    patron = r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$"
    return re.match(patron, email) is not None


def actualizar_ui_con_licencia():
    global plan_global, credits_left_global
    global lbl_plan_value, lbl_credits_value

    # 🔒 PROTECCIÓN: UI aún no creada o widgets no inicializados
    if 'lbl_plan_value' not in globals() or 'lbl_credits_value' not in globals():
        print("⏳ UI principal aún no inicializada, se actualizará luego")
        return

    if lbl_plan_value is None or lbl_credits_value is None:
        print("⏳ Widgets de licencia aún no listos")
        return

    # ✅ Actualizar UI
    lbl_plan_value.config(text=str(plan_global).upper())
    lbl_credits_value.config(text=str(credits_left_global))

def validar_licencia_en_servidor(): 
    global license_key_global, credits_left_global, credits_global, plan_global, email_global

    payload = {}

    if email_global:
        payload["email"] = email_global
    if license_key_global:
        payload["license_key"] = license_key_global

    if not payload:
        return False, "No hay email ni licencia guardada para validar."

    try:
        r = requests.post(f"{SERVER_URL}/license/validate", json=payload, timeout=10)

        if r.status_code == 404:
            return False, "endpoint_not_found"

        if r.status_code != 200:
            return False, "offline"
      
        if r.status_code != 200:
            return False, f"http_{r.status_code}"

        if "application/json" not in r.headers.get("Content-Type", ""):
            return False, "invalid_response"


        data = r.json()

        # ⛔ Licencia inválida explícita
        if data.get("valid") is False:
            reason = data.get("reason")

            if reason in ("revoked", "expired"):
                return False, f"Licencia inválida: {reason}"

            if reason == "not_found":
                return True, "Licencia no encontrada (backend OK)"

        # ✅ Backend OK, continuar sincronización
        lic = data.get("license")

        if not lic:
            return True, "Sincronización pendiente (backend OK)"


        # Actualizar memoria y archivo local
        license_key_global = lic.get("license_key")
        plan_global = lic.get("plan", "free")
        credits_global = lic.get("credits", lic.get("credits_left", 0))
        credits_left_global = lic.get("credits_left", 0)
        email_global = lic.get("email", email_global)

        global MAIN_LICENSE
        MAIN_LICENSE = {
            "email": email_global,
            "plan": plan_global,
            "credits": credits_global,
            "credits_left": credits_left_global,
            "license_key": license_key_global
        }

        with open(LICENSE_FILE, "w", encoding="utf-8") as f:
            json.dump({
                "license_key": license_key_global,
                "plan": plan_global,
                "credits": credits_global,
                "credits_left": credits_left_global,
                "email": email_global
            }, f, indent=2)

        return True, data.get("license", {})

    except Exception as e:
        print("⚠ Backend no disponible, usando licencia local:", e)
        return False, "offline"



def sincronizar_licencia_completa():
    """
    Valida licencia en servidor y sincroniza TODO:
    - license.json
    - globals
    - UI
    """
    try:
        ok, msg = validar_licencia_en_servidor()

        # ❌ backend caído / offline → NO fue sincronización
        if not ok:
            if msg == "endpoint_not_found":
                print("❌ ERROR: el backend NO tiene /license/validate")
                # esto NO se arregla reintentando
                return False

            if msg == "offline":
                print("⚠ Backend offline, reintentando luego")
                return False

            print("❌ Error desconocido de licencia:", msg)
            return False


        # ✅ backend OK → sincronización REAL
        actualizar_ui_con_licencia()
        print("✅ Licencia sincronizada automáticamente")
        return True

    except Exception as e:
        print("⚠ Error sincronizando licencia:", e)
        return False

def reintento_sync_licencia():
    try:
        exito = sincronizar_licencia_completa()

        # si ya sincronizó, no mostrar más warnings
        if exito:
            print("🔁 Sincronización establecida, esperando próximos cambios")

    finally:
        root.after(60000, reintento_sync_licencia)



def validar_creditos_para_generar(cantidad_videos):
    """
    Valida si hay suficientes credits_left para generar `cantidad_videos`.
    Backend si está vivo, fallback local si está dormido.
    """
    global license_key_global, credits_left_global

    if not license_key_global:
        return False, "No hay licencia local. Inicia sesión o activa una licencia."

    try:
        r = requests.post(
            f"{SERVER_URL}/license/validate",
            json={"license_key": license_key_global},
            timeout=6
        )
        data = r.json()

        # -------------------------------
        # 🔒 RESPUESTA NO VÁLIDA O INCOMPLETA
        # -------------------------------
        if not isinstance(data, dict):
            credits_left = int(credits_left_global or 0)
            return (cantidad_videos <= credits_left), credits_left

        if data.get("valid") is False:
            reason = data.get("reason")

            # ❌ INVALIDAR SOLO SI ES REAL
            if reason in ("not_found", "revoked", "expired"):
                return False, reason

            # ⚠️ BACKEND INESTABLE / REINICIANDO
            credits_left = int(credits_left_global or 0)
            if cantidad_videos > credits_left:
                return False, credits_left
            return True, credits_left

        # -------------------------------
        # ✅ BACKEND OK → USAR DATOS REALES
        # -------------------------------
        license_data = data.get("license") or {}
        credits_left = int(license_data.get("credits_left", credits_left_global or 0))
        credits_left_global = credits_left  # sincroniza memoria

        if cantidad_videos > credits_left:
            return False, credits_left

        return True, credits_left

    except requests.exceptions.RequestException:
        # ⚠️ Backend caído → usar local
        credits_left = int(credits_left_global or 0)
        if cantidad_videos > credits_left:
            return False, credits_left
        return True, credits_left

    except Exception as e:
        # ⚠️ Error inesperado ≠ licencia inválida
        print("⚠ Error validando créditos, usando fallback local:", e)
        credits_left = int(credits_left_global or 0)
        if cantidad_videos > credits_left:
            return False, credits_left
        return True, credits_left


def descontar_credito():

    if generacion_ilimitada_activa():
        print("♾️ Ilimitado activo → NO se llama al servidor para descontar créditos")
        return

    r = requests.post(
        f"{SERVER_URL}/usage",
        json={
            "license_key": license_key_global,
            "action": "video",
            "cost": 1
        }
    )

    try:
        data = r.json()
        print(f"🟩 Crédito descontado exitosamente. Créditos restantes: {data.get('credits_left')}")
    except:
        print("⚠ Error interpretando respuesta del servidor")



# -------------------------------
# CREAR LICENCIA FREE (ENDPOINT /license/free) + GUARDAR LOCAL
# -------------------------------
def crear_licencia_free_remota(email):
    """
    Llama al endpoint /license/free del servidor y devuelve (True, payload) o (False, error)
    """
    url = STRIPE_SERVER_BASE.rstrip("/") + "/license/free"
    try:
        r = requests.post(url, json={"email": email}, timeout=12)
        r.raise_for_status()
        data = r.json()
        # Esperamos: {"ok": True, "license_key": "...", "credits": 10}
        return True, data
    except Exception as e:
        try:
            return False, r.json()
        except Exception:
            return False, {"error": str(e)}


def solicitar_verificacion(email):
    if not email or not email.strip():
        messagebox.showwarning("Correo requerido", "Por favor escribe tu correo para continuar.")
        return False

    try:
        resp = requests.post(
            f"{SERVER_URL}/auth/request_verification",
            json={"email": email},
            timeout=6
        )
    except requests.exceptions.RequestException as e:
        messagebox.showerror("Error de conexión", f"No se pudo contactar el servidor:\n{e}")
        return False

    try:
        data = resp.json()
    except Exception:
        messagebox.showerror("Error", "Respuesta inválida del servidor.")
        return False

    # -----------------------------------
    #     🔥 LÓGICA CORRECTA DE UI
    # -----------------------------------

    # 1. Si YA está verificado (NO mostrar notificaciones de envío)
    if data.get("already_verified"):
                license_obj = data.get("license")

                # detener polling completamente si existe
                if _polling_threads.get(email):
                       _polling_threads[email] = False
                       _polling_threads.pop(email, None)

                # 🔥 NUEVO: guardar licencia local inmediatamente
                if license_obj:
                       try:
                               guardar_licencia_local_desde_server(license_obj)
                       except Exception as e:
                               print("Error guardando licencia local:", e)

                        # 🔥🔥🔥 FIX CRÍTICO: asegurar globals ANTES de validar
                       try:
                               license_key = (
                                         license_obj.get("license_key")
                                         or license_obj.get("key")
                                         or license_obj.get("id")
                                )
                               if license_key:
                                       global license_key_global
                                       license_key_global = license_key
                       except Exception as e:
                                 print("⚠ Error sincronizando license_key_global:", e)

                # 🔥 NUEVO: validar y sincronizar TODO automáticamente
                try:
                        def _sync_after_already_verified():
                              ok, _ = validar_licencia_en_servidor()
                              if ok:
                                      actualizar_ui_con_licencia()

                                      print("\n━━━━━━━━━━ LICENCIA ACTIVA ━━━━━━━━━━")
                                      print("Email:", email_global)
                                      print("Plan:", plan_global)
                                      print("Créditos disponibles:", credits_left_global)

                                      try:
                                               print("Licencia:", license_key_global)
                                      except:
                                                pass

                                      try:
                                               print("Expira:", license_expiry_global)
                                      except:
                                                pass

                                      print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n")

                                      print("✅ Licencia sincronizada automáticamente (correo ya verificado)")

                              else:
                                      print("⚠ No se pudo validar licencia automáticamente")

                        root.after(0, _sync_after_already_verified)
                except Exception as e:
                         print("⚠ Error en sincronización automática:", e)

                mostrar_toast(
                                                  "ℹ️ Correo ya verificado\n\n"
                                                  "La licencia fue cargada automáticamente.",
                                                  tipo="info",
                                                  duracion=4000,
                                                  bloqueante=False
                                        )
                return True





    # 2. Si es la PRIMERA vez → sí mostrar “correo enviado”
    if data.get("ok") and data.get("message") == "Correo de verificación enviado.":
        mostrar_toast(
                           "📧 Correo enviado\n\n"
                           "Te enviamos un enlace a tu correo.\n"
                           "Abre tu bandeja y confirma tu email.",
                           tipo="info",
                           duracion=6000
                  )

        _polling_threads[email] = False

        start_polling_verification(email)
        return True

    # 3. Si ok == False → mostrar error normal
    messagebox.showerror("Error", data.get("message", data.get("error", "Error al enviar verificación.")))
    return False


def verificar_estado(email):
    """
    Comprueba una vez si el email ya fue verificado (GET /auth/check_status).
    Devuelve True si verificado y la licencia (si existe), False en otro caso.
    """
    if not email:
        return False, None

    try:
       r = requests.get(f"{SERVER_URL}/auth/check_status", params={"email": email}, timeout=6)

       print("STATUS:", r.status_code)
       print("RAW RESPONSE:", r.text)

       data = r.json()

    except requests.exceptions.RequestException as e:
        # No mostrar popups frecuentes aquí; devolvemos False para reintentar en el polling
        print("Error verificando estado:", e)
        return False, None
    except Exception as e:
        print("Respuesta inválida al verificar estado:", e)
        return False, None

    if data.get("ok") and data.get("verified"):
        return True, data.get("license")
    return False, None


# Control del polling
_polling_threads = {}  # email -> contador/flag

def start_polling_verification(email, interval=4, max_attempts=45):
    """
    Inicia un hilo que cada `interval` segundos consulta /auth/check_status.
    max_attempts controla cuanto tiempo (interval*max_attempts) se esperará.
    """
    # Evitar lanzar varios pollings para el mismo email
    if _polling_threads.get(email):
        return

    def runner():
        attempts = 0
        while attempts < max_attempts:
            verified, license_obj = verificar_estado(email)
            if verified:
                # notificar en el hilo principal de Tk
                root.after(0, lambda: on_verification_success(email, license_obj))
                _polling_threads.pop(email, None)
                return
            attempts += 1
            time.sleep(interval)
        if not _polling_threads.get(email):
            return  # salir sin mostrar mensajes

        # Si llegamos aquí: no verificado en el tiempo esperado
        _polling_threads.pop(email, None)
        root.after(0, lambda: messagebox.showwarning("Pendiente", "Aún no has hecho clic en el enlace de verificación. Revisa tu correo."))
    # marcar y lanzar thread
    _polling_threads[email] = True
    t = threading.Thread(target=runner, daemon=True)
    t.start()

def on_verification_success(email, license_obj):
        global email_global, license_global

        # Guardar en variables globales
        email_global = email
        license_global = license_obj

        sync_usage_with_license(license_obj)  # 🔒 inicializa si no existe
        load_usage()                           # 🔄 carga uso local

        # 🔥 FIX CRÍTICO: persistir licencia recuperada del backend
        if license_obj:
            try:
                guardar_licencia_local_desde_server(license_obj)
            except Exception as e:
                print("Error guardando licencia local:", e)

        # 🔥🔥🔥 NUEVO: sincronización COMPLETA automática (SIN DAÑOS COLATERALES)
        try:
            def _sync_after_verify():
                ok, _ = validar_licencia_en_servidor()
                if ok:
                    actualizar_ui_con_licencia()
                    print("✅ Licencia validada y sincronizada automáticamente tras verificación")
                else:
                    print("⚠ No se pudo validar licencia automáticamente")

            root.after(0, _sync_after_verify)
        except Exception as e:
            print("⚠ Error en sincronización automática de licencia:", e)

        # Mensaje al usuario
        messagebox.showinfo(
            "Verificado",
            f"Correo {email} verificado correctamente. Bienvenido."
        )

        # Si la API devolvió la licencia: cargar la app principal
        if license_obj:
            try:
                cargar_aplicacion_principal(license_obj)
            except Exception as e:
                print("Error al cargar la app principal:", e)
        else:
            # Si no hay licencia aún, refrescar UI o esperar creación
            pass


# ============================================================
#     🔧 GENERAR LICENCIA LOCAL DESDE MODO DEV (LOCAL-CREATE)
# ============================================================

def cta_local_update_generic(plan, credits):
    """
    Llama al endpoint local /license/local-create para generar una licencia
    totalmente nueva desde el modo desarrollador.

    Retorna:
        (True, payload_del_servidor)
    O:
        (False, error)
    """

    url = STRIPE_SERVER_BASE.rstrip("/") + "/license/local-create"

    payload = {
        "license_key": f"DEV-{plan.upper()}",
        "plan": plan,
        "credits": credits
    }

    try:
        r = requests.post(url, json=payload, timeout=10)

        try:
            data = r.json()
        except:
            data = {"error": "Respuesta no válida del servidor", "raw": r.text}

        if r.status_code == 200:
            # El backend devuelve: { ok: True, license: {...} }
            if data.get("ok"):
                return True, data
            else:
                return False, data

        return False, data

    except Exception as e:
        return False, {"error": str(e)}




def guardar_licencia_local_desde_server(payload):
    """
    Guarda license.json uniforme para toda la app.
    """
    try:
        lic = payload.get("license", payload)

        to_save = {
            "license_key": lic.get("license_key") or lic.get("key") or lic.get("id"),
            "email": lic.get("email"),
            "plan": lic.get("plan"),
            "credits": int(lic.get("credits", 0)),
            "credits_left": int(lic.get("credits_left", 0)),
            "status": lic.get("status", "active"),
            "last_sync": datetime.utcnow().isoformat()
        }

        license_path = os.path.join(BASE_DIR, "license.json")

        with open(license_path, "w", encoding="utf-8") as f:
            json.dump(to_save, f, indent=2, ensure_ascii=False)

        return True

    except Exception as e:
        print("Error guardando license.json:", e)
        return False



# --- EDITOR DE GUION MODERNO ---
# 🔑 REEMPLAZO 1: Función modificada para soportar múltiples guiones con delimitador.
def pedir_guion_moderno(titulo, mensaje, texto_inicial=""):
        

        dialogo = tk.Toplevel(root)
        dialogo.title(titulo)
        dialogo.geometry("760x760")
        dialogo.configure(bg="#1e1e1e")
        dialogo.resizable(False, False)
        dialogo.grab_set()

        

        resultado = {"texto": None}
        exceso_caracteres = {
                   "estado": False,
                   "guiones_excedidos": []
        }

        placeholder_text = (
            "Escribe aquí tu guion...\n\n"
            "• Usa el signo + en una línea separada para múltiples guiones\n"
            "• Cada bloque generará un audio independiente\n\n"
            "Ejemplo:\n"
            "Hola, este es el primer guion.\n"
            "+\n"
            "Este es el segundo guion."
        )

        def limpiar_placeholder_si_existe(event=None):
                                nonlocal placeholder_activo
                                if placeholder_activo:
                                          text.delete("1.0", "end")
                                          text.tag_remove("placeholder", "1.0", "end")
                                          placeholder_activo = False


        # ---------------- TÍTULO ----------------
        tk.Label(
            dialogo,
            text=titulo,
            font=("Segoe UI", 15, "bold"),
            fg="white",
            bg="#1e1e1e"
        ).pack(pady=(15, 5))

        # ---------------- MENSAJE ----------------
        tk.Label(
            dialogo,
            text=mensaje,
            font=("Segoe UI", 10),
            fg="#bdbdbd",
            bg="#1e1e1e",
            wraplength=720,
            justify="left"
        ).pack(pady=(0, 10))

        # ---------------- TEXT ----------------
        frame_text = tk.Frame(dialogo, bg="#1e1e1e")
        frame_text.pack(padx=15, pady=(0, 5), fill="both", expand=True)

                      # Scrollbar vertical
        scrollbar = ttk.Scrollbar(
                                 frame_text,
                                 orient="vertical",
                                 style="Modern.Vertical.TScrollbar"
                      )

        scrollbar.pack(side="right", fill="y")

        text = tk.Text(
                                frame_text,
                                font=("Segoe UI", 11),
                                 bg="#252525",
                                fg="white",
                                insertbackground="white",
                                wrap="word",
                                relief="flat",
                                highlightthickness=2,
                                highlightbackground="#333333",
                                highlightcolor=AZUL_EDITOR,

                                yscrollcommand=scrollbar.set,
                                undo=True
                      )
        text.pack(side="left", fill="both", expand=True)

        scrollbar.config(command=text.yview)

                      # Tags existentes
        text.tag_configure("placeholder", foreground="#777777")
        text.tag_configure(
                                "separator",
                                foreground=AZUL_EDITOR,
                                font=("Segoe UI", 12, "bold")
                      )

                     # Tag nuevo: guion excedido
        text.tag_configure(
                                "error_guion",
                                 background="#3a1c1c",
                                 foreground=AZUL_EDITOR,
                       )

                      # ---------- CARGAR AUTOSAVE ----------
        if os.path.exists(AUTOSAVE_FILE):
                               with open(AUTOSAVE_FILE, "r", encoding="utf-8") as f:
                                         contenido_guardado = f.read().strip()

                               if contenido_guardado:
                                        text.delete("1.0", "end")
                                        text.insert("1.0", contenido_guardado)
                                        placeholder_activo = False

        
        

                      

        def programar_autosave(event=None):
                               if autosave_job["id"]:
                                        text.after_cancel(autosave_job["id"])
                               autosave_job["id"] = text.after(
                                          800,
                                          lambda: guardar_autosave(text.get("1.0", "end-1c"))
                               )

        text.bind("<KeyRelease>", programar_autosave)
        text.bind("<Button-1>", limpiar_placeholder_si_existe)
        text.bind("<KeyPress>", limpiar_placeholder_si_existe)



        # ---------- CARGA INICIAL DEL EDITOR ----------
        contenido_guardado = ""
        if os.path.exists(AUTOSAVE_FILE):
                             with open(AUTOSAVE_FILE, "r", encoding="utf-8") as f:
                                       contenido_guardado = f.read().strip()

        if contenido_guardado:
                               text.insert("1.0", contenido_guardado)
                               placeholder_activo = False
        else:
                               text.insert("1.0", placeholder_text, "placeholder")
                               placeholder_activo = True

        # ---------------- CONTADOR Y RESALTADO ----------------
        info_label = tk.Label(
            dialogo,
            text="🧩 Guiones: 0 | 📝 Caracteres: 0",
            font=("Segoe UI", 9),
            fg="#9e9e9e",
            bg="#1e1e1e"
        )
        info_label.pack(pady=(5, 5))

        def actualizar_info(event=None):
                 contenido = text.get("1.0", "end").strip()

                 if placeholder_activo:
                          info_label.config(text="🧩 Guiones: 0 | 📝 Caracteres: 0", fg="#9e9e9e")
                          exceso_caracteres["estado"] = False  # 🔴
                          return

                 # -------- RESALTAR TODOS LOS + --------
                 text.tag_remove("separator", "1.0", "end")
                 lineas = contenido.splitlines()

                 for i, linea in enumerate(lineas, start=1):
                          if linea.strip() == "+":
                                   text.tag_add("separator", f"{i}.0", f"{i}.end")

                  # -------- DIVIDIR GUIONES --------
                 guiones = [g.strip() for g in re.split(r'\n\s*\+\s*\n', contenido) if g.strip()]
                 total_guiones = len(guiones)
                 total_caracteres = len(contenido)

                  # -------- VALIDAR LIMITE POR GUION --------

                 max_len = 1500
                 guiones_fuera = []

                 for idx, g in enumerate(guiones, start=1):
                                                        if len(g) > max_len:
                                                                 guiones_fuera.append(idx)

                 exceso_caracteres["estado"] = len(guiones_fuera) > 0
                 exceso_caracteres["guiones_excedidos"] = guiones_fuera

                 # -------- RESALTAR GUIONES EXCEDIDOS --------
                 text.tag_remove("error_guion", "1.0", "end")

                 inicio = "1.0"
                 for idx, g in enumerate(guiones, start=1):
                                                        fin = text.search(r'\n\s*\+\s*\n', inicio, stopindex="end", regexp=True)
                                                        if not fin:
                                                                 fin = "end"

                                                        if idx in exceso_caracteres["guiones_excedidos"]:
                                                                 text.tag_add("error_guion", inicio, fin)

                                                        inicio = text.index(f"{fin}+1c")




                 # -------- TEXTO INFO --------
                 texto_info = (
                             f"🧩 Guiones: {total_guiones} | "
                             f"📝 Caracteres totales: {total_caracteres}"
                             f"Máx 1500 caract./guion"
                   )

                 if exceso_caracteres["estado"]:
                                                        lista = ", ".join(f"#{i}" for i in exceso_caracteres["guiones_excedidos"])
                                                        texto_info += f" | ⚠️ Guiones {lista} superan el límite"
                                                        info_label.config(text=texto_info, fg="#ff9800")
                 else:
                                                        info_label.config(text=texto_info, fg="#9e9e9e")



        text.bind("<KeyRelease>", actualizar_info)

        # ---------------- AYUDA ----------------
        tk.Label(
                 dialogo,
                 text="ℹ️ Tip: cada bloque separado por '+' generará un audio distinto.",
                 font=("Segoe UI", 9),
                 fg=AZUL_EDITOR,

                 bg="#1e1e1e"
         ).pack(pady=(0, 10))

        # ---------------- BOTONES ----------------
        frame_btn = tk.Frame(dialogo, bg="#1e1e1e")
        frame_btn.pack(pady=10)

        def confirmar():
                  contenido = text.get("1.0", "end").strip()

                  if placeholder_activo or not contenido:
                            resultado["texto"] = None
                            dialogo.destroy()
                            return

                  if exceso_caracteres["estado"]:
                                                           lista = ", ".join(f"#{i}" for i in exceso_caracteres["guiones_excedidos"])

                                                           mostrar_toast(
                                                                      "⚠️ No se puede continuar.\n\n"
                                                                      f"Los siguientes guiones superan 1500 caracteres:\n"
                                                                      f"{lista}\n\n"
                                                                      "Reduce su longitud para poder guardar y continuar.",
                                                                      tipo="warning",
                                                                      duracion=7500,
                                                                      bloqueante=False
                                                           )
                                                           return



                  # ✅ SOLO SI TODO ESTÁ BIEN
                  resultado["texto"] = contenido
                  dialogo.destroy()



        def cancelar():
                  exceso_caracteres["estado"] = False  # 🔑 RESET
                  resultado["texto"] = None
                  dialogo.destroy()


        tk.Button(
                 frame_btn,
                 text="Guardar guiones",
                 command=confirmar,
                 bg=AZUL_EDITOR,
                 fg="white",
                 font=("Segoe UI", 10, "bold"),
                 relief="flat",
                 width=18
        ).pack(side="left", padx=10)

        tk.Button(
                 frame_btn,
                 text="Cancelar",
                 command=cancelar,
                 bg="#3a3a3a",
                 fg="white",
                 font=("Segoe UI", 10),
                 relief="flat",
                 width=14
        ).pack(side="left")

        dialogo.wait_window()
        return resultado["texto"]

# --------------------------------------------------------------------

# --- LIMPIEZA AGRESIVA DE CARACTERES ---
def limpiar_caracteres_piper(text):
    """
    Realiza una limpieza para eliminar caracteres Unicode problemáticos 
    que causan 'surrogates not allowed' en Piper/subprocesos.
    """
    text = unicodedata.normalize('NFC', text)
    text = text.replace('“', '"').replace('”', '"') 
    text = text.replace('‘', "'").replace('’', "'")
    text = text.replace('—', '--') 
    text = text.replace('…', '...')
    
    caracteres_seguros = r'[^\w\d\s\.,;:\?\¿!\¡\-\(\)/%$&@#*+=áéíóúÁÉÍÓÚñÑ]'
    text = re.sub(caracteres_seguros, '', text, flags=re.UNICODE)
    
    text = re.sub(r'\s+', ' ', text).strip()
    
    return text
# --------------------------------------------------

# FUNCIONES DE ANIMACIÓN
def mostrar_animacion_gif(label, ruta_gif):
    """Muestra un GIF pequeño en una etiqueta."""
    global current_animation_id
    if current_animation_id:
        try: label.after_cancel(current_animation_id)
        except ValueError: pass

    def update_frame(frame_index):
        global current_animation_id
        try:
            frame = frames_anim[frame_index]
            label.config(image=frame)
            frame_index = (frame_index + 1) % len(frames_anim)
            current_animation_id = label.after(50, lambda: update_frame(frame_index))
        except IndexError:
            pass

    try:
        gif_pil = Image.open(ruta_gif)
        frames_anim = []
        for i in range(0, gif_pil.n_frames):
            gif_pil.seek(i)
            frame_resized = gif_pil.copy().resize((100, 100), Image.Resampling.LANCZOS)
            frames_anim.append(ImageTk.PhotoImage(frame_resized))
        
        label.config(image=frames_anim[0])
        # Usamos pack() para el label dentro de su Frame contenedor
        label.pack(pady=5)
        update_frame(0)

    except FileNotFoundError:
        print(f"Advertencia: Archivo GIF no encontrado: {ruta_gif}")
        label.pack_forget()
    except Exception as e:
        print(f"Error al cargar GIF de animación: {e}")
        label.pack_forget()

def mostrar_gif_grande(label, ruta_gif):
    """Muestra un GIF grande de finalización."""
    global current_big_gif_id
    if current_big_gif_id:
        try: label.after_cancel(current_big_gif_id)
        except ValueError: pass
        
    def update_frame(frame_index):
        global current_big_gif_id
        try:
            frame = frames_big[frame_index]
            label.config(image=frame)
            frame_index = (frame_index + 1) % len(frames_big)
            current_big_gif_id = label.after(100, lambda: update_frame(frame_index))
        except IndexError:
            pass
            
    try:
        gif_pil = Image.open(ruta_gif)
        frames_big = []
        target_width_gif_grande = int(WINDOW_WIDTH * 0.8)
        aspect_ratio_gif_grande = gif_pil.height / gif_pil.width
        target_height_gif_grande = int(target_width_gif_grande * aspect_ratio_gif_grande)

        if target_height_gif_grande > WINDOW_HEIGHT * 0.4:
            target_height_gif_grande = int(WINDOW_HEIGHT * 0.4)
            target_width_gif_grande = int(target_height_gif_grande / aspect_ratio_gif_grande)

        for i in range(0, gif_pil.n_frames):
            gif_pil.seek(i)
            frame_resized = gif_pil.copy().resize((target_width_gif_grande, target_height_gif_grande), Image.Resampling.LANCZOS)
            frames_big.append(ImageTk.PhotoImage(frame_resized))
        
        label.config(image=frames_big[0])
        # Usamos place para el GIF grande para que no desordene el layout de 'pack'
        center_x_gif_grande = (WINDOW_WIDTH - target_width_gif_grande) // 2
        center_y_gif_grande = 300 
        label.place(x=center_x_gif_grande, y=center_y_gif_grande)
        label.lower() 
        update_frame(0)
        
    except Exception as e:
        print(f"Error al cargar GIF grande: {e}")
        label.place_forget()

def limpiar_done_animacion(anim_label):
    """Limpia la animación 'done.gif' o 'loading.gif' de la GUI."""
    global current_animation_id, current_cleanup_id
    # Intentar cancelar la limpieza automática del anterior
    if current_cleanup_id:
        try: root.after_cancel(current_cleanup_id)
        except ValueError: pass
        current_cleanup_id = None
        
    if current_animation_id:
        try: anim_label.after_cancel(current_animation_id)
        except ValueError: pass
        current_animation_id = None
        
    anim_label.config(image='')
    anim_label.pack_forget()

def limpiar_big_gif(big_gif_label):
    """Limpia el GIF grande de la GUI y detiene su bucle."""
    global current_big_gif_id
    if current_big_gif_id:
        try: big_gif_label.after_cancel(current_big_gif_id)
        except ValueError: pass
        current_big_gif_id = None
        
    big_gif_label.config(image='')
    # Aseguramos que se quite el elemento fijado con place()
    big_gif_label.place_forget()

# FUNCIÓN DE ANIMACIÓN DE PUNTOS
def animar_puntos_secuencial(label, indice):
    """Muestra una animación de texto de progreso con puntos, manteniendo el mensaje base."""
    global current_text_animation_id
    
    mensajes = [".", "..", "..."]
    
    if current_text_animation_id:
        try: label.after_cancel(current_text_animation_id)
        except ValueError: pass
    
    try:
        # Extraemos el mensaje base que está antes de los puntos
        parts = label.cget("text").split("🔄")
        if len(parts) > 1:
            base_text_with_spaces = parts[1].split(".")[0].strip()
            # Aseguramos que el base_text tenga el prefijo "🔄" para la siguiente iteración
            base_text = f"🔄 {base_text_with_spaces}"
        else:
              # Si no hay "🔄", usamos el texto completo como base (primera ejecución o error)
            base_text = label.cget("text")
            
    except Exception:
        base_text = "🔄 Procesando" 
    
    # Construimos el texto con el mensaje base y el punto de animación
    new_text = base_text.split("...")[-1].strip() 
    if new_text.startswith("🔄"):
        base_text = new_text
    else:
        base_text = f"🔄 {new_text}"
    
    label.config(text=f"{base_text}{mensajes[indice]}")
    
    indice = (indice + 1) % len(mensajes)
    current_text_animation_id = label.after(500, lambda: animar_puntos_secuencial(label, indice))


# NUEVA FUNCIÓN: CICLO DE MENSAJES LARGOS
def ciclo_mensajes_progreso(progress_label, mensajes, indice):
    """Muestra un mensaje de la lista por 5 segundos y luego cambia al siguiente."""
    global current_cycle_message_id, current_text_animation_id
    
    if current_cycle_message_id:
        try: progress_label.after_cancel(current_cycle_message_id)
        except ValueError: pass

    if not mensajes:
        progress_label.config(text="🔄 Procesando...")
        return
    
    # Establece el mensaje base del ciclo
    base_text = mensajes[indice]
    progress_label.config(text=f"🔄 {base_text}") 
    
    # Reinicia o asegura la animación de puntos
    if not current_text_animation_id:
        animar_puntos_secuencial(progress_label, 0)
    
    # Prepara la siguiente iteración del ciclo de mensajes
    siguiente_indice = (indice + 1) % len(mensajes)
    # Llama a sí misma después de 5000 ms (5 segundos)
    current_cycle_message_id = progress_label.after(5000, lambda: ciclo_mensajes_progreso(progress_label, mensajes, siguiente_indice))


def detener_animacion_puntos():
    """Detiene la animación de puntos."""
    global current_text_animation_id
    if current_text_animation_id:
        try: root.after_cancel(current_text_animation_id)
        except ValueError: pass
        current_text_animation_id = None
        
def detener_ciclo_mensajes():
    """Detiene el ciclo de mensajes largos."""
    global current_cycle_message_id
    if current_cycle_message_id:
        try: root.after_cancel(current_cycle_message_id)
        except ValueError: pass
        current_cycle_message_id = None

    # ─── ###DEF CONFIGURAR SUBTITULOS## ─────────────────────────────────────────────

def configurar_subtitulos(var_subtitulos, checkbutton):
        global config_subtitulos_posicion
        global config_subtitulos_tamano
        global config_subtitulos_estilo
        global config_subtitulos_color_texto
        global config_subtitulos_color_resalte

        if var_subtitulos.get() != 1:
                return

        dialogo = tk.Toplevel(root)
        dialogo.title("Configurar Subtítulos")
        dialogo.geometry("520x820")
        dialogo.configure(bg="#1e1e1e")
        dialogo.resizable(False, False)
        dialogo.grab_set()

    # ─── TÍTULO ─────────────────────────────────────────────
        tk.Label(
                 dialogo,
                 text="✍️ Configuración de Subtítulos",
                 font=("Segoe UI", 15, "bold"),
                 fg="white",
                 bg="#1e1e1e"
          ).pack(pady=(15, 10))

    # ─── FUNCIÓN CARD ───────────────────────────────────────
        def card(titulo):
                 frame = tk.Frame(dialogo, bg="#252525", bd=0)
                 frame.pack(fill="x", padx=20, pady=8)
                 tk.Label(
                         frame,
                         text=titulo,
                         font=("Segoe UI", 11, "bold"),
                         fg="white",
                         bg="#252525"
                  ).pack(anchor="w", padx=12, pady=(10, 6))
                 return frame

    # ─── 1. POSICIÓN ───────────────────────────────────────
        posicion_var = tk.StringVar(value=config_subtitulos_posicion)
        frame_pos = card("📍 Posición vertical")

        for txt, val in [
                   ("Abajo (TikTok)", "abajo"),
                   ("Centro", "centro"),
                   ("Arriba", "arriba"),
           ]:
                   tk.Radiobutton(
                           frame_pos,
                           text=txt,
                           variable=posicion_var,
                           value=val,
                           bg="#252525",
                           fg="white",
                           selectcolor="#1e1e1e",
                           font=("Segoe UI", 10),
                           activebackground="#252525",
                           activeforeground="white"
                   ).pack(anchor="w", padx=20, pady=2)

    # ─── 2. TAMAÑO ─────────────────────────────────────────
        tamano_var = tk.StringVar(value=config_subtitulos_tamano)
        frame_size = card("🔠 Tamaño del texto")

        for txt, val in [
                    ("Pequeño", "pequeno"),
                    ("Medio (recomendado)", "medio"),
                    ("Grande (impacto)", "grande"),
            ]:
                    tk.Radiobutton(
                            frame_size,
                            text=txt,
                            variable=tamano_var,
                            value=val,
                            bg="#252525",
                            fg="white",
                            selectcolor="#1e1e1e",
                            font=("Segoe UI", 10)
                     ).pack(anchor="w", padx=20, pady=2)

    # ─── 3. ESTILO ─────────────────────────────────────────
        estilo_var = tk.StringVar(value=config_subtitulos_estilo)
        frame_style = card("🎬 Estilo de animación")

        for txt, val in [
                    ("Resalte por palabra", "resalte_color"),
                    ("Fondo TikTok (zoom)", "fondo_zoom"),
                    ("Letra progresiva", "progressive_reveal"),
             ]:
                    tk.Radiobutton(
                            frame_style,
                            text=txt,
                            variable=estilo_var,
                            value=val,
                            bg="#252525",
                            fg="white",
                            selectcolor="#1e1e1e",
                            font=("Segoe UI", 10)
               ).pack(anchor="w", padx=20, pady=2)

    # ─── 4. COLORES ────────────────────────────────────────
        frame_color = card("🎨 Colores")
      
        def color_row(titulo, valor_inicial):
            row = tk.Frame(dialogo, bg="#1e1e1e")
            row.pack(fill="x", padx=20, pady=6)

            tk.Label(
                row,
                text=titulo,
                bg="#1e1e1e",
                fg="white",
                font=("Segoe UI", 10)
            ).pack(side="left")

            entry = tk.Entry(
                row,
                width=10,
                bg="#2b2b2b",
                fg="white",
                insertbackground="white",
                relief="flat"
            )
            entry.insert(0, valor_inicial)
            entry.pack(side="left", padx=8)

            preview = tk.Label(
                row,
                bg=valor_inicial,
                width=2,
                height=1
            )
            preview.pack(side="left", padx=4)

            def pick_color():
                color = colorchooser.askcolor(initialcolor=entry.get())
                if color and color[1]:
                    entry.delete(0, tk.END)
                    entry.insert(0, color[1].upper())
                    preview.config(bg=color[1])

            tk.Button(
                row,
                text="🎨",
                command=pick_color,
                bg="#3a3a3a",
                fg="white",
                relief="flat",
                width=3
            ).pack(side="left", padx=6)

            return entry

                

    # ─── BOTONES ───────────────────────────────────────────
        

        entry_texto = color_row("Color del texto", config_subtitulos_color_texto)
        entry_fondo = color_row("Color de fondo/resalte", config_subtitulos_color_resalte)

        frame_btn = tk.Frame(dialogo, bg="#1e1e1e")
        frame_btn.pack(pady=18)
      
        def guardar():
            global config_subtitulos_color_texto
            global config_subtitulos_color_resalte

            config_subtitulos_color_texto = entry_texto.get().upper()
            config_subtitulos_color_resalte = entry_fondo.get().upper()
            dialogo.destroy()


        def cancelar():
            var_subtitulos.set(0)
            checkbutton.configure(state="normal")
            dialogo.destroy()

        tk.Button(
            frame_btn, text="💾 Guardar",
            command=guardar,
            
            bg="#1078FF", fg="white",
            font=("Segoe UI", 10, "bold"),
            relief="flat", width=12
        ).pack(side="left", padx=8)

        tk.Button(
            frame_btn, text="Cancelar",
            command=cancelar,
            bg="#2e2e2e", fg="white",
            font=("Segoe UI", 10),
            relief="flat", width=12
        ).pack(side="left", padx=8)

        dialogo.protocol("WM_DELETE_WINDOW", cancelar)
# ----------------------------------------------------------------




# FUNCIÓN DE SELECCIÓN DE AUDIO
# 🔑 REEMPLAZO 2: Función modificada para limpiar el modo TTS temporal al subir audios manuales.
def seleccionar_audio(num_audios_label):
    """Abre un diálogo para seleccionar múltiples archivos MP3 de audio y pide el prefijo inmediatamente."""
    global lista_audios_pendientes, audio_generado_path, nombre_prefijo
    global audio_source_mode

    file_paths = filedialog.askopenfilenames(
        title="Selecciona archivos de audio (MP3, WAV o cualquier formato soportado por pydub)",
        filetypes=[
            ("Archivos de Audio", "*.mp3 *.wav *.ogg *.flac"),
            ("Todos los archivos", "*.*")
        ]
    )

    if file_paths:
        # 1. Limpiar y establecer audios
        lista_audios_pendientes.clear()
        lista_audios_pendientes.extend(file_paths)
        audio_source_mode = "upload"
        
        # AJUSTE CLAVE: Aseguramos que el modo TTS temporal se desactive y limpiamos cualquier ruta temporal.
        audio_generado_path = None 
        try:
              # Limpiamos los archivos temporales de voz si existen
            temp_files = [
                os.path.join(ENTRADA_DIR, f) for f in os.listdir(ENTRADA_DIR) 
                if f.startswith(nombre_prefijo) or f.startswith("voz_generada_temp") or f.startswith("voz_piper_temp") or f.endswith(".wav") # Mejorado para limpiar más archivos TTS
            ]
            for f in temp_files:
                try: os.remove(f)
                except Exception: pass
        except Exception:
            pass
        # -------------------------------------------------------------

        total_audios = len(lista_audios_pendientes)

        # 2. Lógica de solicitud de prefijo inmediata
        if total_audios == 1:
            # Caso 1: Audio Individual (Sugerir nombre del archivo)
            audio_basename = os.path.splitext(os.path.basename(file_paths[0]))[0]
            
            # Limpiamos sugerencias automáticas de copia
            clean_name = re.sub(r'(\s*-\s*copia\s*(\(\d+\))?|\s*\(\d+\))$', '', audio_basename, flags=re.IGNORECASE).strip()
            if not clean_name: clean_name = audio_basename

            prefijo = pedir_texto_moderno(
                                        "Nombre de Video Único",
                                        f"Ingresa un Nombre para tu video con el audio '{audio_basename}'.",
                                        placeholder=f"ej: {clean_name}"
                               )

            dialog_title = "Audio Individual"
        else:
            # Caso 2: Lote de Audios (Prefijo único para el lote)
            prefijo = pedir_texto_moderno(
                "Prefijo de Nombres para Lote",
                f"Ingresa el prefijo de nombre para el lote de {total_audios} videos.",
                
            )
            dialog_title = "Lote de Audios"

        # 3. Guardar el prefijo o cancelar
        if prefijo:
            # Asigna el prefijo global que se usará en 'ejecutar_generacion'
            nombre_prefijo = prefijo.strip().replace(" ", "_").replace(".", "_")
            
            # Feedback actualizado en la etiqueta
            num_audios_label.config(
                text=f"🎙️ Audios cargados: {total_audios}. Prefijo: '{nombre_prefijo}' ({dialog_title})"
            )

        else:
                            # Si el usuario cancela la selección de prefijo, limpiamos los audios.
                            lista_audios_pendientes.clear()
                            nombre_prefijo = ""

                            num_audios_label.config(
                                     text="🎙️ Audios cargados: 0 (Prefijo cancelado)"
                            )

                            mostrar_toast(
                                      "⚠️ Se requiere un Nombre.\n\n"
                                      "La carga de audios fue cancelada.",
                                      tipo="warning",
                                      duracion=5000
                            )


    else:
        num_audios_label.config(text=f"🎙️ Audios cargados: {len(lista_audios_pendientes)}.")

def generacion_ilimitada_activa():
    if plan_global in ("pro", "agency") and audio_source_mode == "upload":
        return True
    return False
        


def solicitar_nombre_videos(num_audios_label):
    """Solicita un prefijo para nombrar los archivos de video (Usado para lotes)."""
    global nombre_prefijo

    prefijo = simpledialog.askstring(
        "Prefijo de Nombres para Lote",
        "Ingresa el prefijo de nombre para los videos (ej: 'momentos_de_historia').",
        parent=root
    )

    if prefijo:
        nombre_prefijo = prefijo.strip().replace(" ", "_").replace(".", "_")
        if lista_audios_pendientes:
            num_audios_label.config(text=f"🎙️ Audios cargados: {len(lista_audios_pendientes)}. Prefijo: '{nombre_prefijo}'")
    else:
        nombre_prefijo = ""


# FUNCIÓN DE SELECCIÓN DE SALIDA
def seleccionar_salida():
    """Permite al usuario elegir la carpeta de salida para los videos finales."""
    global salida_personalizada
    
    folder_selected = filedialog.askdirectory(title="Selecciona la carpeta de salida para los videos")
    
    if folder_selected:
        salida_personalizada = folder_selected

# --------------------------------------------------------------------------------
# 🎤 Funciones de Edge-TTS (Texto a Voz y Previsualización)
# --------------------------------------------------------------------------------

def previsualizar_voz_edge(voz_tts_id):
        """Genera y reproduce un fragmento de audio usando la voz de Edge-TTS."""
        texto_prueba = "Hola, esta es una prueba de voz. La calidad es muy alta."
    
        def run_async_task(coro):
                try:
                       loop = asyncio.new_event_loop()
                       asyncio.set_event_loop(loop)
                       loop.run_until_complete(coro)
                except Exception as e:
                          pass

        threading.Thread(target=run_async_task, args=(generar_y_reproducir(voz_tts_id, texto_prueba),)).start()

async def generar_y_reproducir(voz_tts_id, texto):
           """Corrutina que genera el audio, lo carga con PyDub y lo reproduce."""
           try:
                   communicate = edge_tts.Communicate(texto, voz_tts_id)
        
                   audio_data = b''
                   async for chunk in communicate.stream():
                             if chunk["type"] == "audio":
                                     audio_data += chunk["data"]

                   if audio_data:
                           audio_segment = AudioSegment.from_file(io.BytesIO(audio_data), format="mp3") 
                           audio_segment = audio_segment.set_frame_rate(44100).set_channels(1).set_sample_width(2)

                           audio_array = np.array(audio_segment.get_array_of_samples(), dtype=np.int16)
                           rate = audio_segment.frame_rate

                           sd.play(audio_array, rate)
                           sd.wait() 
                   else:
                           raise ValueError("No se generó audio. La voz podría no ser compatible.")
           except Exception as e:
                     error_msg = str(e)
                     root.after(
                               0,
                               lambda msg=error_msg: messagebox.showerror(
                                         "Error de Previsualización",
                                         "Error al reproducir la voz.\n\n"
                                         "La voz no devolvió audio.\n"
                                         "Esto suele ocurrir cuando Edge-TTS limita la IP "
                                         "por exceso de solicitudes.\n\n"
                                         f"Detalle técnico:\n{msg}"
                                )
                       )


# ------------------------------------------------------------------
## FUNCIONES CLAVE DE SELECCIÓN DE VOZ TTS
# ------------------------------------------------------------------

def seleccionar_voz_edge(num_audios_label):
         global voz_seleccionada_edge, voz_tts_activa

         voces_espanol = {
                    "Dalia (MX, Femenina, Amigable)": "es-MX-DaliaNeural",
                    "Jorge (MX, Masculina, Seria)": "es-MX-JorgeNeural",
                    "Salome (CO, Femenina, Suave)": "es-CO-SalomeNeural",
                    "Gonzalo (CO, Masculina, Autoridad)": "es-CO-GonzaloNeural",
                    "Elvira (ES, Femenina, Clara)": "es-ES-ElviraNeural",
                    "Alvaro (ES, Masculina, Formal)": "es-ES-AlvaroNeural",
         }

         dialogo = tk.Toplevel(root)
         dialogo.title("Seleccionar Voz Edge-TTS")
         dialogo.geometry("520x500")
         dialogo.configure(bg="#1e1e1e")
         dialogo.resizable(False, False)
         dialogo.grab_set()

        # ─── TÍTULO ─────────────────────────────────────────────
         tk.Label(
                  dialogo,
                  text="🎙 Seleccionar voz Edge-TTS",
                  font=("Segoe UI", 14, "bold"),
                  fg="white",
                  bg="#1e1e1e"
         ).pack(pady=(15, 8))

        # ─── BUSCADOR ───────────────────────────────────────────
         search_var = tk.StringVar()

         entry_search = tk.Entry(
                    dialogo,
                    textvariable=search_var,
                    font=("Segoe UI", 10),
                    bg="#252525",
                    fg="white",
                    insertbackground="white",
                    relief="flat"
         )
         entry_search.pack(fill="x", padx=20, pady=(0, 10))

        # ─── LISTA ──────────────────────────────────────────────
         frame_lista = tk.Frame(dialogo, bg="#252525")
         frame_lista.pack(fill="both", expand=True, padx=20)

         scrollbar = ttk.Scrollbar(frame_lista)
         scrollbar.pack(side="right", fill="y")

         listbox = tk.Listbox(
                    frame_lista,
                    font=("Segoe UI", 10),
                     bg="#252525",
                     fg="white",
                     selectbackground="#1078FF",
                     highlightthickness=0,
                     relief="flat",
                     yscrollcommand=scrollbar.set
         )
         listbox.pack(fill="both", expand=True)
         scrollbar.config(command=listbox.yview)

         def refrescar_lista(*args):
                  listbox.delete(0, "end")
                  filtro = search_var.get().lower()
                  for nombre in voces_espanol:
                          if filtro in nombre.lower():
                                   listbox.insert("end", nombre)

         search_var.trace_add("write", refrescar_lista)
         refrescar_lista()

         # Preselección
         for i, (_, voz_id) in enumerate(voces_espanol.items()):
             if voz_id == voz_seleccionada_edge:
                 listbox.selection_set(i)
                 listbox.see(i)
                 break

        # ─── BOTONES ────────────────────────────────────────────
         frame_btn = tk.Frame(dialogo, bg="#1e1e1e")
         frame_btn.pack(pady=15)

         def preview():
                  sel = listbox.curselection()
                  if not sel:
                           return
                  nombre = listbox.get(sel[0])
                  voz_id = voces_espanol[nombre]
                  threading.Thread(
                             target=lambda: previsualizar_voz_edge(voz_id),
                             daemon=True
                   ).start()

         def guardar():
                  global voz_seleccionada_edge, voz_tts_activa

                  sel = listbox.curselection()
                  if not sel:
                           return

                  nombre = listbox.get(sel[0])
                  voz_seleccionada_edge = voces_espanol[nombre]
                  voz_tts_activa = "EDGE-TTS"

                  try:
                           region = nombre.split("(")[1].split(",")[0]
                  except:
                           region = "Global"

                  num_audios_label.config(
                            text=f"🗣️ MODO TTS ACTIVO: Edge-TTS ({region})"
                  )
                  dialogo.destroy()

         tk.Button(
                  frame_btn,
                  text="▶ Probar",
                  command=preview,
                  bg="#3a3a3a",
                  fg="white",
                  font=("Segoe UI", 10),
                  relief="flat",
                  width=10
         ).pack(side="left", padx=6)

         tk.Button(
                  frame_btn,
                  text="💾 Guardar",
                  command=guardar,
                  bg="#1078FF",
                  fg="white",
                  font=("Segoe UI", 10, "bold"),
                  relief="flat",
                  width=10
         ).pack(side="left", padx=6)

         tk.Button(
                  frame_btn,
                  text="Cancelar",
                  command=dialogo.destroy,
                  bg="#2e2e2e",
                  fg="white",
                  font=("Segoe UI", 10),
                  relief="flat",
                  width=10
         ).pack(side="left", padx=6)


# FUNCIÓN DE SELECCIÓN DE PIPER
def seleccionar_voz_piper(num_audios_label):
    """Abre un diálogo para que el usuario elija el modelo de voz de Piper (.onnx) y activa el modo PIPER."""
    global voz_seleccionada_path, voz_tts_activa

    model_path = filedialog.askopenfilename(
        title="Selecciona el archivo de modelo de Piper (.onnx)",
        initialdir=PIPER_DIR,
        filetypes=[("Modelo ONNX", "*.onnx")]
    )

    if model_path:
        config_path = os.path.splitext(model_path)[0] + ".json"
        if not os.path.exists(config_path):
            messagebox.showerror("Error de Modelo", "No se encontró el archivo de configuración (.json) asociado. Asegúrate de tener ambos archivos en la misma ubicación.")
            return

        voz_seleccionada_path = model_path
        voz_tts_activa = "PIPER"
        num_audios_label.config(text=f"🗣️ MODO TTS ACTIVO: Piper ({os.path.basename(model_path).split('-')[1]})") 
    else:
        messagebox.showwarning("Advertencia", "No se seleccionó un nuevo modelo. Usando el modelo actual o Ninguno.")

# ------------------------------------------------------------------
## FUNCIÓN CLAVE: Preparación de Guiones TTS (NO genera audio)
# ------------------------------------------------------------------

def generar_audio_tts(num_audios_label):
    """
    Guarda los guiones TTS preparados desde el editor.
    NO genera audio.
    El audio se generará ÚNICAMENTE al presionar 'GENERAR VIDEOS'.
    """

    global guiones_tts_pendientes
    global nombre_prefijo
    global voz_seleccionada_path
    global voz_tts_activa
    global voz_seleccionada_edge
    global audio_generado_path
    global lista_audios_pendientes
    global audio_source_mode

    # ---------------------------------------------------------
    # RESET SEGURO
    # ---------------------------------------------------------
    audio_generado_path = None
    lista_audios_pendientes.clear()
    guiones_tts_pendientes.clear()
    audio_source_mode = "tts"

    # ---------------------------------------------------------
    # 1. VALIDAR VOZ
    # ---------------------------------------------------------
    if voz_tts_activa == "PIPER":
        if not voz_seleccionada_path or not os.path.exists(voz_seleccionada_path):
            messagebox.showinfo(
                "Modelo requerido",
                "El modelo Piper no está configurado."
            )
            return
        voz_activa_nombre = os.path.basename(voz_seleccionada_path).replace(".onnx", "")

    elif voz_tts_activa == "EDGE-TTS":
        voz_activa_nombre = voz_seleccionada_edge

    else:
        messagebox.showerror(
            "Error",
            "No hay un motor TTS activo. Selecciona Piper o Edge-TTS."
        )
        return

    # ---------------------------------------------------------
    # 2. PEDIR GUIÓN
    # ---------------------------------------------------------
    guion_completo = pedir_guion_moderno(
        titulo="Editor de Guiones",
        mensaje=f"MODO: {voz_tts_activa} | VOZ: {voz_activa_nombre}\n\n"
                "Usa '+' en una línea separada para múltiples guiones.",
        texto_inicial=""
    )

    if not guion_completo:
                    return



    # ---------------------------------------------------------
    # 3. DIVIDIR GUIONES
    # ---------------------------------------------------------
    guiones_individuales = [
        g.strip()
        for g in re.split(r'\n\s*\+\s*\n', guion_completo)
        if g.strip()
    ]

    if not guiones_individuales:
        messagebox.showwarning(
            "Advertencia",
            "No se encontraron guiones válidos.\n"
            "Usa '+' en una línea separada."
        )
        return

    # ---------------------------------------------------------
    # 4. PEDIR PREFIJO
    # ---------------------------------------------------------
    nombre_base = pedir_texto_moderno(
                    "Nombre base",
                    "Ingresa un nombre para el o los video(s):",
                    placeholder="video_tiktok"
          )


    if not nombre_base:
                   mostrar_toast(
                             "⚠️ Debes ingresar un nombre para continuar, debes pegar nuevamente el/los guiones",
                             tipo="warning",
                             duracion=4000
                    )
                   return


    nombre_prefijo = nombre_base.strip().replace(" ", "_").replace(".", "_")

    # ---------------------------------------------------------
    # 5. GUARDAR GUIONES LIMPIOS (SIN GENERAR AUDIO)
    # ---------------------------------------------------------
    for guion in guiones_individuales:
        guion_limpio = limpiar_caracteres_piper(guion).replace("\n", " ")
        if guion_limpio.strip():
            guiones_tts_pendientes.append(guion_limpio)

    # ---------------------------------------------------------
    # 6. FEEDBACK FINAL
    # ---------------------------------------------------------
    num_audios_label.config(
        text=f"📝 Guiones preparados: {len(guiones_tts_pendientes)} | "
             f"Audio aún NO generado"
    )

    mostrar_toast(
                    "✅ Guiones preparados correctamente.\n\n"
                    "🎧 El audio se generará SOLO cuando presiones:\n"
                    "▶ 'GENERAR VIDEOS'",
                    tipo="success",
                    duracion=4000,
                    bloqueante=True
           )

def generar_audios_desde_guiones_tts(progress_label):
    global lista_audios_pendientes

    lista_audios_pendientes.clear()

    for i, texto in enumerate(guiones_tts_pendientes, start=1):
        progress_label.config(text=f"🗣️ Generando audio TTS {i}...")
        root.update_idletasks()

        ruta_audio = os.path.join(ENTRADA_DIR, f"voz_tts_{i}.mp3")

        try:
            generar_audio_tts(texto, ruta_audio)  # ✅ TU FUNCIÓN EXISTENTE
            lista_audios_pendientes.append(ruta_audio)
        except Exception as e:
            raise RuntimeError(f"Error generando TTS {i}: {e}")


def validar_creditos_y_generar(progress_label, boton_generar, anim_label, big_gif_label, num_audios_label):
    global credits_left_global

    try:
        # ---------------------------------------------------------
        # 1️⃣ Validar créditos cargados
        # ---------------------------------------------------------
        if credits_left_global is None:
            messagebox.showerror("Error", "No se pudieron cargar los créditos.")
            return

        # ---------------------------------------------------------
        # 2️⃣ Validar existencia de contenido
        # ---------------------------------------------------------
        hay_audios = len(lista_audios_pendientes) > 0
        hay_guiones = len(guiones_tts_pendientes) > 0

        if not hay_audios and not hay_guiones:
                  mostrar_toast(
                            "⚠️ Sin contenido\n\n"
                            "No hay audios ni guiones listos para generar videos.\n\n"
                            "✅ Sube audios manualmente\n"
                            "✅ O agrega guiones y genera de texto a voz con IA",
                            tipo="info",
                           duracion=7000,
           bloqueante=True
                  )
                  return  # 🔥 OBLIGATORIO


        # ---------------------------------------------------------
        # 3️⃣ Si hay guiones, generar audios TTS AUTOMÁTICAMENTE
        # ---------------------------------------------------------
        if hay_guiones and not hay_audios:
            progress_label.config(text="🎙️ Generando audios desde Texto a Voz...")
            root.update_idletasks()

            generar_audios_desde_guiones_tts(progress_label)

            if not lista_audios_pendientes:
                messagebox.showerror(
                    "Error TTS",
                    "No se pudieron generar los audios desde los guiones."
                )
                return

        # ---------------------------------------------------------
        # 4️⃣ Validar cantidad de videos vs créditos
        # ---------------------------------------------------------
        cantidad_videos = len(lista_audios_pendientes)
        creditos_disponibles = int(credits_left_global)

        if cantidad_videos > creditos_disponibles:
            popup_creditos_agotados(root)
            return

        # ---------------------------------------------------------
        # 5️⃣ Ejecutar generación de videos
        # ---------------------------------------------------------
        ejecutar_generacion(
            progress_label,
            boton_generar,
            anim_label,
            big_gif_label,
            num_audios_label
        )

        # ---------------------------------------------------------
        # 6️⃣ Descontar créditos
        # ---------------------------------------------------------
    except Exception as e:
        print("❌ Error general en generación:", e)
        messagebox.showerror(
            "Error",
            f"Ocurrió un error inesperado:\n{e}"
        )
    

def descontar_credito_backend():
    if generacion_ilimitada_activa():
        print("♾️ Ilimitado activo → backend NO llamado")
        return

    try:
        r = requests.post(
            f"{SERVER_URL}/usage",
            json={
                "license_key": license_key_global,
                "action": "video",
                "cost": 1,
                "modo": "audio_upload"
            },
            timeout=8
        )

        if not r.content:
            print("⚠ Backend respondió vacío, no se descuenta")
            return

        try:
            data = r.json()
        except Exception:
            print("⚠ Respuesta no JSON del backend, no se descuenta")
            return

        if data.get("unlimited"):
            print("♾️ Backend confirmó ilimitado → NO se descuentan créditos")
            return

        if data.get("ok"):
            print(f"🟩 Crédito descontado exitosamente. Créditos restantes: {data.get('credits_left')}")
        else:
            print("⚠ Backend respondió error:", data)

    except Exception as e:
        print("⚠ Backend dormido, no se pudo descontar crédito ahora:", e)



def generar_audios_desde_guiones_tts(progress_label):
    global lista_audios_pendientes

    lista_audios_pendientes.clear()

    for i, texto in enumerate(guiones_tts_pendientes, start=1):
        progress_label.config(text=f"🗣️ Generando audio TTS {i}...")
        root.update_idletasks()

        ruta_audio = os.path.join(ENTRADA_DIR, f"voz_tts_{i}.mp3")

        try:
            # -------------------------------------------------
            # ✅ PIPER
            # -------------------------------------------------
            if voz_tts_activa == "PIPER":
                config_path = os.path.splitext(voz_seleccionada_path)[0] + ".json"

                subprocess.run(
                    [
                        "piper",
                        "--model", voz_seleccionada_path,
                        "--config", config_path,
                        "--output_file", ruta_audio
                    ],
                    input=texto.encode("utf-8", errors="ignore"),
                    check=True
                )

            # -------------------------------------------------
            # ✅ EDGE-TTS
            # -------------------------------------------------
            elif voz_tts_activa == "EDGE-TTS":
                subprocess.run(
                    [
                        "edge-tts",
                        "--text", texto,
                        "--voice", voz_seleccionada_edge,
                        "--write-media", ruta_audio
                    ],
                    check=True
                )

            else:
                raise RuntimeError("No hay motor TTS activo")

            if not os.path.exists(ruta_audio):
                raise RuntimeError("El archivo de audio no se generó")

            lista_audios_pendientes.append(ruta_audio)

        except Exception as e:
            raise RuntimeError(f"Error generando TTS {i}: {e}")


# ------------------------------------------------------------------
## FUNCIÓN CLAVE: Ejecución con manejo de audio TTS (WAV a MP3)
# ------------------------------------------------------------------

def ejecutar_generacion(progress_label, boton_generar, anim_label, big_gif_label, num_audios_label):

    
    # --- VALIDAR LICENCIA ANTES DE GENERAR ---
    cargar_licencia_local()
    ok, msg = validar_licencia_en_servidor()

    if not ok:
                  mostrar_toast(
                            f"❌ Licencia inválida\n\n{msg}",
                            tipo="error",
                            duracion=6000,
                            bloqueante=True

                  )
                  return  # ⛔ DETIENE GENERACIÓN (igual que messagebox)

          # ✔ Licencia válida (NO bloquear flujo)
    info = msg if isinstance(msg, dict) else {}

    global plan_global
    plan = info.get("plan", "").lower()



    mostrar_toast(
                    "✅ Licencia válida\n\n"
                    f"📦 Plan: {info.get('plan')}\n"
                    f"🎯 Créditos disponibles: {info.get('credits_left')}",
                    tipo="success",
                   duracion=4000,
                   bloqueante=False
          )

    # 2️⃣ Comenzando generación
    mostrar_toast(
                    "▶ Comenzando la generación...\n\n"
                    "Esto puede tardar unos minutos.",
                    tipo="success",
                    duracion=2500,
                    bloqueante=False
          )

   
  
     
    global lista_audios_pendientes, nombre_prefijo, audio_generado_path 
    # CAMBIO: Usar config_subtitulos_tamano sin tilde y añadir colores
    global config_subtitulos_posicion, config_subtitulos_tamano, config_subtitulos_estilo
    global config_subtitulos_color_texto, config_subtitulos_color_resalte
    global subtitulos_var 
    global current_cleanup_id 

        # ------------------------------------------------------------
    # VALIDAR CANTIDAD DE VIDEOS VS CRÉDITOS DISPONIBLES
    # ------------------------------------------------------------
    if not generacion_ilimitada_activa():

        try:
            creditos_disponibles = int(credits_left_global)
        except:
            creditos_disponibles = 0

        cantidad_videos = len(lista_audios_pendientes)

        if cantidad_videos > creditos_disponibles:
            messagebox.showerror(
                "Créditos insuficientes",
                f"Solo tienes {creditos_disponibles} créditos disponibles.\n"
                f"Has intentado generar {cantidad_videos} videos.\n\n"
                "Ajusta la cantidad o compra más créditos."
            )
            return

    else:
        print("♾️ Generación ilimitada activa (Plan Pro/Agency + audio subido)")



    

    if not lista_audios_pendientes:
        messagebox.showwarning("Advertencia", "Por favor, carga un archivo MP3 o genera un audio TTS antes de continuar.")
        return
    
    if not nombre_prefijo:
          messagebox.showerror("Error", "No se ha definido un prefijo para el video. Por favor, vuelve a cargar los audios.")
          return

    # DEFINICIÓN DINÁMICA DE LA LISTA DE MENSAJES
    PROGRESS_MESSAGES = [
        "Iniciando el proceso de creación",
        "Recortando audios",
        "Cortando silencios",
        "Voz procesada y normalizada",
        "Audio procesado",
    ]
    
    # CONDICIONAL PARA INCLUIR MENSAJES DE SUBTÍTULOS
    if subtitulos_var.get() == 1:
        PROGRESS_MESSAGES.append("Generando subtítulos automáticos")
        PROGRESS_MESSAGES.append("Aplicando estilos y efectos")
    else:
        # Si no hay subtítulos, mantenemos un mensaje de procesamiento visual
        PROGRESS_MESSAGES.append("Aplicando efectos de video y transiciones")
        
    PROGRESS_MESSAGES.extend([
        "Uniendo partes de video",
        "Procesando video",
        "¡Casi listo!"
    ])
    # ------------------------------------------------------------

    total_audios = len(lista_audios_pendientes)

    def run():
        global audio_generado_path, nombre_prefijo, current_cleanup_id

        exitosos = 0
        boton_generar.config(state="disabled") # DESHABILITA EL BOTÓN
        
        def reset_progress_style():
            progress_label.config(style="TLabel")
            progress_label.config(text="🎬 ¡Disfruta generando tus videos!")
            
        # 1. LIMPIEZA INICIAL
        limpiar_big_gif(big_gif_label)
        if current_cleanup_id:
            try: root.after_cancel(current_cleanup_id)
            except ValueError: pass
            current_cleanup_id = None
            
        limpiar_done_animacion(anim_label) # Limpia cualquier GIF que se esté mostrando
        detener_animacion_puntos()
        detener_ciclo_mensajes()
        

        for i, audio_path_origen in enumerate(lista_audios_pendientes):
            indice_diferencial = i + 1 
            audio_basename = os.path.splitext(os.path.basename(audio_path_origen))[0]

            # 2. INICIO DE ANIMACIONES
            progress_label.config(text=f"🔄 Procesando {i+1} de {total_audios}: {audio_basename}")
            num_audios_label.config(text=f"🟢 En progreso: {i+1} de {total_audios}")

            # INICIAMOS EL CICLO DE MENSAJES DESCRIPTIVOS CON LA LISTA FILTRADA
            ciclo_mensajes_progreso(progress_label, PROGRESS_MESSAGES, 0)
            
            # Se muestra el GIF de loading
            ruta_loading = os.path.join(BASE_DIR, "loading.gif")
            if os.path.exists(ruta_loading):
                mostrar_animacion_gif(anim_label, ruta_loading)
                root.update_idletasks() 
            
            # -------------------------------------------------------
            # 3. PROCESAMIENTO  ✅ CORREGIDO (voz única por iteración)
            # -------------------------------------------------------

            # ✅ AUDIO TEMPORAL ÚNICO POR VIDEO
            destino_voz = os.path.join(ENTRADA_DIR, f"voz_{i+1}.mp3")
            voz_generador = os.path.join(ENTRADA_DIR, "voz.mp3")

            try:
                # --- MANEJO DE AUDIO DE ENTRADA (Conversión WAV → MP3) ---
                if audio_path_origen.lower().endswith(".wav"):
                    progress_label.config(
                        text=f"🔄 [Conversión] {i+1} de {total_audios}: WAV → MP3"
                    )
                    audio_segment = AudioSegment.from_file(audio_path_origen, format="wav")
                    audio_segment.export(destino_voz, format="mp3")
                else:
                    shutil.copy(audio_path_origen, destino_voz)
                # -------------------------------------------------------

                # ✅ COPIA CLAVE PARA EL GENERADOR (🔴 SOLUCIÓN TOTAL)
                shutil.copy(destino_voz, voz_generador)
   
                # --- INICIO CONFIGURACIÓN GENERADOR ---
                comando = [
                    sys.executable,
                    GENERADOR_SCRIPT,
                    "--subtitulos", str(subtitulos_var.get()),
                    "--plan", plan_global,
                    "--modo", "audio_upload"  # 🔑 SOLO cuando es audio subido
                ]


                if subtitulos_var.get() == 1:
                    comando.extend([
                        "--posicion_sub", config_subtitulos_posicion,
                        "--tamano_sub", config_subtitulos_tamano,
                        "--estilo_sub", config_subtitulos_estilo,
                        "--color_texto", config_subtitulos_color_texto,
                        "--color_resalte_fondo", config_subtitulos_color_resalte,
                    ])
                # --- FIN CONFIGURACIÓN GENERADOR ---

                # 🚀 EJECUCIÓN PRINCIPAL
                subprocess.run(comando, check=True)
                exitosos += 1



                
                # 4. LIMPIEZA INTERMEDIA DE ANIMACIONES
                detener_ciclo_mensajes()
                detener_animacion_puntos()
                
                # Lógica de renombrar/mover el archivo de salida (se mantiene igual)
                salida_original = os.path.join(BASE_DIR, "salida")
                archivos_salida = sorted([f for f in os.listdir(salida_original) if f.startswith("video_final_") and f.endswith(".mp4")], reverse=True)
                if archivos_salida:
                    ruta_final_original = os.path.join(salida_original, archivos_salida[0])
                    
                    base_nombre_con_indice = f"{nombre_prefijo}_{indice_diferencial}"
                    nuevo_nombre = f"{base_nombre_con_indice}.mp4"
                    
                    ruta_final_destino = os.path.join(salida_personalizada, nuevo_nombre)

                    contador = 0
                    while os.path.exists(ruta_final_destino):
                        contador += 1
                        nuevo_nombre = f"{base_nombre_con_indice}_v{contador}.mp4"
                        ruta_final_destino = os.path.join(salida_personalizada, nuevo_nombre)
                    
                    if not os.path.exists(salida_personalizada):
                        os.makedirs(salida_personalizada)
                    if salida_personalizada == salida_original:
                        os.rename(ruta_final_original, ruta_final_destino)
                    else:
                        shutil.move(ruta_final_original, ruta_final_destino)

                # 5. Lógica de animación de finalización (Sincronización de GIF)
                
                # **🔑 CORRECCIÓN CLAVE 1: Limpiamos el loading.gif justo antes de mostrar el done.gif**
                limpiar_done_animacion(anim_label) 

                ruta_done = os.path.join(BASE_DIR, "done.gif")
                if os.path.exists(ruta_done):
                    # **🔑 CORRECCIÓN CLAVE 2: Mostramos el done.gif inmediatamente**
                    mostrar_animacion_gif(anim_label, ruta_done)
                    
                    if total_audios == 1:
                        # Si es un único video, dejamos el GIF grande y el done.gif por 20s
                        ruta_final_grande = os.path.join(BASE_DIR, "final_grande.gif")
                        if os.path.exists(ruta_final_grande):
                            mostrar_gif_grande(big_gif_label, ruta_final_grande)
                            big_gif_label.after(20000, lambda: limpiar_big_gif(big_gif_label))
                            
                        progress_label.config(text=f"✅ Video {i+1} generado con éxito. ({exitosos}/{total_audios})")
                        # La limpieza final del done.gif (20s) se maneja en el paso 6.
                    else:
                        # Si es un lote, limpiamos el done.gif muy rápido (1s) para no estorbar el siguiente loading
                        anim_label.after(1000, lambda: limpiar_done_animacion(anim_label)) 
                        progress_label.config(text=f"✅ Video {i+1} de {total_audios} completado. Siguiente... 🎬")
                
                else: # Si no hay done.gif, solo actualizamos el mensaje.
                    progress_label.config(text=f"✅ Video {i+1} de {total_audios} completado. Siguiente... 🎬")

            except subprocess.CalledProcessError as e:
                # Se mantiene la limpieza en caso de error
                detener_ciclo_mensajes()
                detener_animacion_puntos()
                limpiar_done_animacion(anim_label) 
                progress_label.config(text=f"❌ Error procesando video {i+1}. Revisar logs. ({exitosos}/{total_audios})")
                # 🔑 CORRECCIÓN DEL NAMEERROR: Capturamos 'e' en el lambda
                root.after(0, lambda error_e=e: messagebox.showerror(
                    "❌ Error fatal al exportar el video",
                    "❌ ERROR FATAL DURANTE LA EXPORTACIÓN DEL VIDEO.\n\n"
                    "No se pudo generar el video.\n\n"
                    f"Archivo: {os.path.basename(audio_path_origen)}\n\n"
                    f"Razón:\n{error_e}\n\n"
                    "📌 Esto suele ocurrir por:\n"
                    "   • El clip de video está corrupto\n"
                    "   • MoviePy no pudo leer el primer frame\n"
                    "   • FFMPEG está desactualizado o dañado\n\n"
                    "🧹 Se limpiaron los recursos y puedes intentar de nuevo."
                ))

            except Exception as e:
                # Se mantiene la limpieza en caso de error
                detener_ciclo_mensajes()
                detener_animacion_puntos()
                limpiar_done_animacion(anim_label) 
                progress_label.config(text=f"❌ Error inesperado con audio {i+1}. ({exitosos}/{total_audios})")
                # 🔑 CORRECCIÓN DEL NAMEERROR: Capturamos 'e' en el lambda
                root.after(0, lambda error_e=e: messagebox.showerror(f"Error inesperado", f"Error general con el archivo {os.path.basename(audio_path_origen)}:\n{error_e}"))

            time.sleep(2)

        # 6. LÓGICA FINAL Y LIMPIEZA TOTAL
        limpiar_big_gif(big_gif_label) 

        if total_audios > 0:
            ruta_done = os.path.join(BASE_DIR, "done.gif")
            if os.path.exists(ruta_done) and total_audios == 1:
                # Si es un solo video, el done.gif ya está puesto y su temporizador es el que reactiva el botón
                def final_cleanup_and_enable():
                    limpiar_done_animacion(anim_label) 
                    boton_generar.config(state="normal") 
                
                # Si ya se estaba mostrando el done.gif de un solo video, reiniciamos el temporizador de 20s.
                if current_cleanup_id:
                      try: root.after_cancel(current_cleanup_id)
                      except ValueError: pass
                
                current_cleanup_id = anim_label.after(4000, final_cleanup_and_enable) 
            elif os.path.exists(ruta_done) and total_audios > 1:
                      # Si es un lote, se activa inmediatamente después de la última iteración
                      boton_generar.config(state="normal")
            else:
                # Si no hay done.gif, reactivar inmediatamente
                boton_generar.config(state="normal") 
                
            progress_label.config(style="Success.TLabel", text=f"🎉 PROCESO FINALIZADO. {exitosos} de {total_audios} videos generados. 🎬")
        else:
            progress_label.config(style="Success.TLabel", text=f"🎉 PROCESO FINALIZADO. {exitosos} de {total_audios} videos generados. 🎬")
            boton_generar.config(state="normal") 

        audio_generado_path = None 
        nombre_prefijo = "" 

        progress_label.after(7000, reset_progress_style)
        
        lista_audios_pendientes.clear()
        num_audios_label.config(text="🎙️ Audios cargados: 0.")
        root.update_idletasks()

        if not generacion_ilimitada_activa():
            descontar_credito_backend()



    threading.Thread(target=run).start()
# ------------------------------------------------------------------

def check_update():
        try:
            r = requests.get(f"{SERVER_URL}/app/version", timeout=5)
            data = r.json()

            remote_version = data["version"]

            if remote_version != APP_VERSION:
                return data
            return None
        except Exception as e:
            print("No se pudo verificar actualización:", e)
            return None

def descargar_update(url):
        tmp_path = os.path.join(BASE_DIR, "update_new.exe")

        with requests.get(url, stream=True) as r:
            r.raise_for_status()
            with open(tmp_path, "wb") as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)

        return tmp_path

def ejecutar_update():
        # 🔒 BACKUP DE SEGURIDAD (CRÍTICO)
        backup_current_exe()

        bat_path = os.path.join(BASE_DIR, "update.bat")

        with open(bat_path, "w") as f:
            f.write(BAT_CONTENT)

        subprocess.Popen(["cmd", "/c", bat_path], shell=True)
        sys.exit(0)


def write_version_state(status="starting"):
        data = {
            "version": APP_VERSION,
            "status": status,
            "timestamp": time.time()
        }
        with open(VERSION_FILE, "w") as f:
            json.dump(data, f)

def check_previous_state():
        if not os.path.exists(VERSION_FILE):
            return

        try:
            with open(VERSION_FILE, "r") as f:
                data = json.load(f)

            if data["status"] != "healthy":
                trigger_local_rollback()

        except Exception as e:
            print("Error leyendo estado de versión:", e)

# =========================
# 🔥 CHECK CRÍTICO DE ROLLBACK
# =========================
check_previous_state()
write_version_state("starting")


def trigger_local_rollback():
        old_exe = os.path.join(BASE_DIR, "TurboClips_old.exe")
        current_exe = os.path.join(BASE_DIR, APP_NAME)

        if not os.path.exists(old_exe):
            return

        write_version_state("rollback")

        bat = f"""
        @echo off
        timeout /t 2 >nul
        del "{current_exe}"
        move "{old_exe}" "{current_exe}"
        start "" "{current_exe}"
        """

        bat_path = os.path.join(BASE_DIR, "rollback.bat")
        with open(bat_path, "w") as f:
            f.write(bat)

        subprocess.Popen(["cmd", "/c", bat_path], shell=True)
        sys.exit(0)

def backup_current_exe():
        current = os.path.join(BASE_DIR, APP_NAME)
        backup = os.path.join(BASE_DIR, "TurboClips_old.exe")

        if os.path.exists(current):
            shutil.copy(current, backup)


def cargar_anuncio_toast_imagen():
    anuncios = []

    def mostrar_toast(ad):
        toast = tk.Toplevel()
        toast.overrideredirect(True)  # Sin bordes
        toast.attributes("-topmost", True)

        # Tamaño del toast (cuadrado)
        ancho = 320
        alto = 320

        # Posición: esquina inferior derecha
        x = root.winfo_screenwidth() - ancho - 30
        y = root.winfo_screenheight() - alto - 80
        toast.geometry(f"{ancho}x{alto}+{x}+{y}")

        # Contenedor principal
        frame = tk.Frame(toast, bg="black", bd=0)
        frame.pack(fill="both", expand=True)

        # IMAGEN COMPLETA
        try:
            img_data = requests.get(ad["image"], timeout=5).content
            img = Image.open(BytesIO(img_data))
            img = img.resize((ancho, alto))
            img_tk = ImageTk.PhotoImage(img)

            lbl_img = tk.Label(frame, image=img_tk, bd=0)
            lbl_img.image = img_tk
            lbl_img.pack(fill="both", expand=True)

        except Exception as e:
            print("Error cargando imagen toast:", e)
            toast.destroy()
            return

        # CLICK EN IMAGEN → abrir link
        def abrir_url(event=None):
            webbrowser.open(ad["cta_url"])

            # 🔥 CUANDO EL USUARIO SALE A STRIPE Y LUEGO REGRESA
            cargar_y_mostrar_licencia()

            toast.destroy()


        lbl_img.bind("<Button-1>", abrir_url)
        frame.bind("<Button-1>", abrir_url)

        # 🔥 BOTÓN "X" PARA CERRAR (arriba a la derecha)
        boton_cerrar = tk.Label(
            toast,
            text="✕",
            fg="white",
            bg="#333333",  # negro sólido (compatibilidad total)
            font=("Arial", 12, "bold")
        )

        boton_cerrar.place(x=ancho - 28, y=5, width=24, height=24)

        def cerrar(event=None):
            toast.destroy()

        boton_cerrar.bind("<Button-1>", cerrar)

        # Auto-cerrar después de 20s
        toast.after(20000, toast.destroy)

        # Fade-in suave
        try:
            for i in range(0, 10):
                toast.attributes("-alpha", i / 10)
                toast.update()
                time.sleep(0.02)
        except:
            pass

    # OBTENER ANUNCIOS
    def obtener_ads():
        try:
            url = "https://stripe-backend-r14f.onrender.com/ads/banner"
            data = requests.get(url, timeout=5).json()

            for ad in data["ads"]:
                if ad["active"]:
                    anuncios.append(ad)

            if anuncios:
                root.after(2000, lambda: mostrar_toast(anuncios[0]))

        except Exception as e:
            print("Error cargando anuncios:", e)

    obtener_ads()





# --- INTERFAZ PRINCIPAL ---
root = tk.Tk()

notificacion_lbl = tk.Label(
         root,
        text="",
        font=("Segoe UI", 10),
        fg="#333",
        bg="#FFF3CD",
        wraplength=480,
        justify="center",
        anchor="center"
)

notificacion_lbl.pack(fill="x", padx=10, pady=(5, 0))
notificacion_lbl.pack_forget()

def mostrar_notificacion(texto, tipo="info", auto_ocultar=True):
        colores = {
            "info": ("#FFF3CD", "#856404"),
            "success": ("#D4EDDA", "#155724"),
            "error": ("#F8D7DA", "#721C24")
        }

        bg, fg = colores.get(tipo, colores["info"])

        notificacion_lbl.config(text=texto, bg=bg, fg=fg)
        notificacion_lbl.pack(fill="x", padx=10, pady=(5, 0))

        if auto_ocultar:
                root.after(5000, notificacion_lbl.pack_forget)

def mostrar_toast(texto, tipo="info", duracion=5000, bloqueante=False):
        global toast_mostrando, toast_bloqueando, toast_queue

        # Si hay uno activo, poner en cola
        if toast_mostrando:
            toast_queue.append((texto, tipo, duracion, bloqueante))
            return

        toast_mostrando = True
        toast_bloqueando = bloqueante

        colores = {
            "info": ("#FFF3CD", "#856404"),
            "success": ("#D4EDDA", "#155724"),
            "error": ("#F8D7DA", "#721C24")
        }

        bg, fg = colores.get(tipo, colores["info"])

        toast = tk.Toplevel(root)
        toast.overrideredirect(True)
        toast.attributes("-topmost", True)
        toast.configure(bg=bg)

        ancho = 520
        alto = 180

        x = root.winfo_x() + (root.winfo_width() // 2) - (ancho // 2)
        y = root.winfo_y() + 40
        toast.geometry(f"{ancho}x{alto}+{x}+{y}")

        label = tk.Label(
            toast,
            text=texto,
            font=("Segoe UI", 10),
            bg=bg,
            fg=fg,
            wraplength=480,
            justify="center"
        )
        label.pack(expand=True, fill="both", padx=20, pady=20)

        def cerrar_toast():
                 global toast_mostrando, toast_bloqueando

                 if toast.winfo_exists():
                          toast.destroy()

                 toast_mostrando = False
                 toast_bloqueando = False

                 # Mostrar siguiente en cola
                 if toast_queue:
                          siguiente = toast_queue.pop(0)
                          root.after(150, lambda: mostrar_toast(*siguiente))

        toast.after(duracion, cerrar_toast)

# 🔄 reintento automático cada 60s
root.after(60000, reintento_sync_licencia)





cargar_anuncio_toast_imagen()







# Variable global del overlay
overlay = None





# --- BLOQUEO DE USO SI NO HAY INTERNET ---
def check_internet():
    try:
        import requests
        requests.get("https://stripe-backend-r14f.onrender.com", timeout=3)
        return True
    except:
        return False


def bloquear_ui():
    global overlay

    # Si ya está bloqueado, no vuelvas a crearlo
    if overlay is not None:
        return

    overlay = tk.Frame(root, bg="black")
    overlay.place(relx=0, rely=0, relwidth=1, relheight=1)


# ---------- GIF ANIMADO ----------
    gif_path = os.path.join(BASE_DIR, "desconectado.gif")

    try:
        gif_pil = Image.open(gif_path)
        overlay.gif_frames = []

        for i in range(gif_pil.n_frames):
            gif_pil.seek(i)
            img = gif_pil.copy().resize((180, 180), Image.Resampling.LANCZOS)
            overlay.gif_frames.append(ImageTk.PhotoImage(img))

        overlay.gif_label = tk.Label(overlay, bg="black")
        overlay.gif_label.pack(pady=(150, 20))


        def animar(idx=0):
            if overlay is None:
                return
            overlay.gif_label.config(image=overlay.gif_frames[idx])
            overlay.after(90, lambda: animar((idx + 1) % len(overlay.gif_frames)))

        animar()

    except Exception as e:
        print("No se pudo cargar desconectado.gif:", e)


    mensaje = tk.Label(
        overlay,
        text="🚫 No hay conexión a internet.\n\nLa aplicación no puede funcionar sin conexión.",
        fg="white",
        bg="black",
        font=("Arial", 16, "bold"),
        justify="center"
    )
    mensaje.pack(expand=True)

    overlay.lift()
    overlay.grab_set()  # Bloquea interacción


def desbloquear_ui():
    global overlay

    # Si está bloqueado, eliminar overlay y permitir interacción
    if overlay is not None:
        overlay.grab_release()
        overlay.destroy()
        overlay = None


# --- VERIFICACIÓN INICIAL ---
if not check_internet():
    bloquear_ui()
# -----------------------------------------


# --- VERIFICACIÓN PERIÓDICA CADA 5 SEG ---
def check_internet_loop():
    if check_internet():
        desbloquear_ui()   # Si hay internet → desbloquear
    else:
        bloquear_ui()      # Si no hay → bloquear

    root.after(5000, check_internet_loop)  # Revisar cada 5 segundos


# Iniciar monitoreo constante
root.after(5000, check_internet_loop)



subtitulos_var = tk.IntVar(value=0)

root.title("TurboClips")
root.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}")
root.config(bg="#1e1e1e")
root.resizable(False, False)



# --- ESTILOS ---
style = ttk.Style()
style.theme_use("clam")
BUTTON_BG_NORMAL = "white"
BUTTON_FG_NORMAL = "black"
BUTTON_ACTIVE_NORMAL = "#ecf0f1"
BUTTON_BG_GENERATE = "#2ecc71"
BUTTON_ACTIVE_GENERATE = "#27ae60"
BUTTON_FG_GENERATE = "white"
style.configure("TButton",
    font=("Arial", 10, "bold"), padding=6, background=BUTTON_BG_NORMAL, foreground=BUTTON_FG_NORMAL, relief="raised", borderwidth=1, focuscolor=BUTTON_BG_NORMAL, borderradius=6
)
style.map("TButton", background=[('active', BUTTON_ACTIVE_NORMAL)], foreground=[('disabled', '#bdc3c7')])
style.configure("TLabel", background="#1e1e1e", foreground="white", font=("Arial", 12))
style.configure("Success.TLabel", background="#1e1e1e", foreground="#2ecc71", font=("Arial", 12, "bold"))
style.configure("Title.TLabel", font=("Arial", 16, "bold"), background="#1e1e1e", foreground="white")
style.configure("TCheckbutton", background="#1e1e1e", foreground="white", font=("Arial", 12), indicatorcolor="white")
style.map("TCheckbutton", background=[('focus', '#1e1e1e')], relief=[('focus', 'flat')])
style.configure("Generate.TButton", font=("Arial", 11, "bold"), padding=4, background=BUTTON_BG_GENERATE, foreground=BUTTON_FG_GENERATE, relief="raised", borderwidth=1, borderradius=6)
style.map("Generate.TButton", background=[('active', BUTTON_ACTIVE_GENERATE), ('disabled', '#7f8c8d')])
# -----------------------------------


# --- TÍTULO ---
ttk.Label(root, text="🎬 Produce videos en minutos, olvídate de las horas.",
          style="Title.TLabel").pack(pady=10)

# --- FEEDBACK DE AUDIOS ---
num_audios_label = ttk.Label(root, text="🎙️ Audios cargados: 0.", style="TLabel", font=("Arial", 11, "bold"))
num_audios_label.pack(pady=5)

# --- BOTONES DE ACCIÓN ---
ttk.Button(root, text="🎙️ SUBIR AUDIOS (Selecciona uno o varios MP3)", command=lambda: seleccionar_audio(num_audios_label), style="TButton").pack(pady=5)

# NUEVO FRAME PARA AGRUPAR OPCIONES DE TTS
frame_tts = ttk.Frame(root, style="TLabel")
frame_tts.pack(pady=5)

# Botón para SELECCIONAR Edge-TTS (Online)
ttk.Button(frame_tts, text="🌐 GENERA DE TEXTO A VOZ", command=lambda: seleccionar_voz_edge(num_audios_label), style="TButton").pack(side=tk.LEFT, padx=5)


# Primera línea de la guía
ttk.Label(root, text="--- Selecciona la voz deseada y luego haz clic en el botón", 
          style="TLabel", font=("Arial", 9, "italic")).pack(pady=(15, 0)) # pady superior más grande, inferior a 0

# Segunda línea de la guía (Continuación)
ttk.Label(root, text="'INGRESA EL GUION' para ingresar tu guion. ---", 
          style="TLabel", font=("Arial", 9, "italic")).pack(pady=(0, 15)) # pady superior a 0, inferior más grande

# Botón para GENERAR AUDIO (Unifica las dos opciones)
ttk.Button(root, text="INGRESA EL GUION", command=lambda: generar_audio_tts(num_audios_label), style="Generate.TButton").pack(pady=10)

menu_soporte = tk.Menu(root, tearoff=0)
menu_soporte.add_command(label="Comunidad Telegram", command=abrir_comunidad_telegram)
menu_soporte.add_command(label="Bot de Soporte", command=abrir_bot_telegram)
menu_soporte.add_command(label="Página Web", command=abrir_pagina_web)
menu_soporte.add_command(label="Correo Soporte", command=abrir_correo_soporte)


boton_soporte = ttk.Button(root, text="SOPORTE ▼", style="Support.TButton")
boton_soporte.place(x=20, y=720)
boton_soporte.bind("<Button-1>", mostrar_menu_soporte)



# BOTÓN DE SALIDA (EXISTENTE)
ttk.Button(root, text="📂 Seleccionar carpeta destino", command=seleccionar_salida, style="TButton").pack(pady=5)

# --- CASILLA DE SUBTÍTULOS ---
check_subtitulos = ttk.Checkbutton(root,
    text=" Generar subtítulos automáticos",
    variable=subtitulos_var,
    onvalue=1,
    offvalue=0,
    style="TCheckbutton",
    takefocus=0,
    cursor="arrow"
)
check_subtitulos.config(
    command=lambda: configurar_subtitulos(subtitulos_var, check_subtitulos)
)
check_subtitulos.pack(pady=10)





# FRAME DE ALTURA FIJA PARA FEEDBACK Y ANIMACIONES
# ----------------------------------------------------------------------
frame_feedback = ttk.Frame(root, style="TLabel", height=150, width=WINDOW_WIDTH)
frame_feedback.pack_propagate(False) 
frame_feedback.pack(pady=5, fill="x")

# Widgets de animación y progreso DENTRO del frame_feedback
anim_label = ttk.Label(frame_feedback, background="#1e1e1e")
# Nota: anim_label.pack() se llama dentro de mostrar_animacion_gif o limpiar_done_animacion

progress_label = ttk.Label(frame_feedback, text="🎬 ¡Disfruta generando tus videos!", style="TLabel", wraplength=480)
progress_label.pack(pady=5) # Lo ponemos centrado en el frame

# El GIF grande sigue siendo global (NO SE COLOCA CON PACK)
big_gif_label = tk.Label(root, bg="#1e1e1e") 
# ----------------------------------------------------------------------


boton_generar = ttk.Button(
         root,
         text="▶ GENERAR VIDEOS",
         command=lambda: on_click_generar(
                   progress_label,
                   boton_generar,
                   anim_label,
                   big_gif_label,
                   num_audios_label
          ),
          style="Generate.TButton"
)
boton_generar.pack(pady=10, padx=20)

# --- FUNCION DE ABRIR SALIDA ---
def abrir_salida():
    try:
        if os.name == 'nt': 
            os.startfile(salida_personalizada)
        elif sys.platform == 'darwin': 
            subprocess.run(['open', salida_personalizada])
        else: 
            subprocess.run(['xdg-open', salida_personalizada])

    except Exception as e:
        messagebox.showerror("Error", f"No se pudo abrir la carpeta de salida:\n{e}")

# Añadir el botón de abrir salida 
ttk.Button(root, text="🗂️ Abrir carpeta destino", command=abrir_salida, style="TButton").pack(pady=5)


def cargar_y_mostrar_licencia():
    """
    Carga license.json local → valida contra el servidor → actualiza la UI.
    Maneja verificaciones de email, licencias free, pagadas y errores.
    Retorna (plan, credits)
    """
    global license_key_global, credits_left_global

    # 🔒 PROTECCIÓN: UI aún no creada
    if 'lbl_plan_value' not in globals() or 'lbl_credits' not in globals():
        return None, 0

    # ------------------------------------------------------
    # 1) Cargar licencia local (license.json o fallback)
    # ------------------------------------------------------
    lic_local = None

    try:
        if os.path.exists(LICENSE_FILE):
            lic_local = json.load(open(LICENSE_FILE, "r", encoding="utf-8"))
    except:
        lic_local = None

    if not lic_local:
        lic_local = leer_licencia_local()  # ~/.mi_app_license.json

    # ------------------------------------------------------
    # Si no hay licencia → mostrar vacío
    # ------------------------------------------------------
    if not lic_local:
        lbl_plan_value.config(text="NINGUNO")
        lbl_credits.config(text="Créditos: 0")
        return None, 0

    # ------------------------------------------------------
    # 2) Comprobar verificación de email (solo bloquea FREE)
    # ------------------------------------------------------
    email = lic_local.get("email")
    plan_local = lic_local.get("plan", "free")

    if email:
        try:
            r = requests.get(
                f"{SERVER_URL}/auth/check_status",
                params={"email": email},
                timeout=5
            )
            status = r.json()

            verificado = status.get("verified", False)

            # FREE sin verificar → bloquear
            if not verificado and plan_local == "free":
                messagebox.showwarning(
                    "Verificación requerida",
                    "Tu email aún no está verificado.\n"
                    "Debes verificarlo antes de usar la licencia FREE."
                )

                try:
                    os.remove(LICENSE_FILE)
                except:
                    pass

                lbl_plan_value.config(text="---")
                lbl_credits.config(text="Créditos: ---")
                return None, 0

            # PAGADO sin verificar → permitir
            if not verificado and plan_local != "free":
                messagebox.showwarning(
                    "Email no verificado",
                    "Tu email no está verificado, pero tu licencia es PAGA.\n"
                    "Puedes usar la app sin problemas."
                )
        except:
            # modo offline: permitir
            pass

    # ------------------------------------------------------
    # 3) Validar en servidor
    # ------------------------------------------------------
    if lic_local.get("license_key"):
        license_key_global = lic_local["license_key"]

        ok, info = validar_licencia_en_servidor()

        # --- PROTECCIÓN: si info NO es dict, abortar ---
        if ok and not isinstance(info, dict):
            print("⚠ Error: info llegó como string o formato inválido:", info)
            lbl_plan_value.config(text="ERROR")
            lbl_credits.config(text="Créditos: 0")
            return None, 0

        if ok:
            # Cargar valores actualizados
            plan = info.get("plan", plan_local)
            credits = info.get("credits_left", 0)

            credits_left_global = credits

            if lbl_plan_value.winfo_exists():
                lbl_plan_value.config(text=plan.upper())

            if lbl_credits.winfo_exists():
                lbl_credits.config(text=f"Créditos: {credits}")


            return plan, credits
        else:
            # Licencia rechazada por el servidor
            lbl_plan_value.config(text="INVÁLIDO")
            lbl_credits.config(text="Créditos: 0")
            return None, 0


    # ------------------------------------------------------
    # Si no hay license_key → no activado
    # ------------------------------------------------------
    lbl_plan_value.config(text="NO ACTIVADO")
    lbl_credits.config(text="Créditos: 0")
    return None, 0



# ----------------------------
# WIDGETS RÁPIDOS: Plan / Créditos + Botón Obtener Free Trial
# ----------------------------


def fue_already_verified(email):
    try:
        r = requests.get(f"{SERVER_URL}/auth/check_status", params={"email": email}, timeout=5)
        data = r.json()
        return data.get("verified") is True
    except:
        return False


def obtener_prueba_gratis():
    """
    Nueva versión con verificación por correo.
    Ya NO crea la licencia directamente.
    1. Pide el email
    2. Envía verificación al correo
    3. Espera a que el usuario haga clic en el correo (polling)
    4. Cuando está verificado → se crea la licencia y se carga en la app
    """

    email = simpledialog.askstring(
        "Prueba gratis",
        "Ingresa tu email para activar tu prueba gratis (recibirás un enlace de verificación):",
        parent=root
    )

    if not email:
        return

    if not check_internet():
        messagebox.showerror("Sin conexión", "Necesitas conexión para solicitar la verificación.")
        return

    # Desactivar botón mientras se envía el email
    btn_free.config(state="disabled")
    global lbl_plan_value
    lbl_plan_value.config(text="Plan: esperando verificación...")
    global lbl_credits
    lbl_credits.config(text="Créditos: ---")

    root.update_idletasks()

    # 1. Solicitar verificación al servidor
    ok = solicitar_verificacion(email)

    if not ok:
        # Algo falló → reactivar botón y refrescar estado
        btn_free.config(state="normal")
        cargar_y_mostrar_licencia()
        return

    # 2. Si el correo se envió bien, el polling se encargará del resto.
    # PERO si el correo ya estaba verificado, NO mostrar popup de envío
    if not fue_already_verified(email):
        messagebox.showinfo(
            "Verificación enviada",
            "Te enviamos un enlace a tu correo.\nHaz clic en 'Confirmar Email' para activar tu prueba gratis."
        )


#btn_free = ttk.Button(root, text="🎁 Obtener prueba gratis (10 créditos)", command=obtener_prueba_gratis)
# btn_free.pack(pady=(4,8))  # <-- ya no lo mostramos

# Ocultar si estaba mostrado
try:
    btn_free.pack_forget()
except:
    pass



# --- LOGO Y FOOTER ---
# Aseguramos que el logo se coloque ABSOLUTAMENTE en la parte inferior para no interferir con pack()
logo_img = None
TARGET_WIDTH = 270

try:
    ruta_logo = os.path.join(BASE_DIR, "logo.png")
    img_pil_logo = Image.open(ruta_logo)

    original_width, original_height = img_pil_logo.size
    aspect_ratio = original_height / original_width
    new_height = int(TARGET_WIDTH * aspect_ratio)

    img_pil_logo = img_pil_logo.resize((TARGET_WIDTH, new_height), Image.Resampling.LANCZOS)

    logo_img = ImageTk.PhotoImage(img_pil_logo)

    logo_label = tk.Label(root, image=logo_img, bg="#1e1e1e")
    logo_label.image = logo_img

    center_x = (WINDOW_WIDTH / 2) - (TARGET_WIDTH / 2)
    center_y = WINDOW_HEIGHT - new_height - 30 

    logo_label.place(x=center_x, y=center_y) 

except FileNotFoundError:
    pass
except Exception as e:
    print(f"Error cargando imagen del logo: {e}")


# El footer se pone con pack() al fondo.
ttk.Label(root, text="© 2025 TurboClips. Todos los derechos reservados.", font=("Arial", 10), style="TLabel").pack(side="bottom", pady=10)

# ----------------------------
# CLIENTE: Integración con server_stripe.py (central credits + usage)
# ----------------------------
import webbrowser
import requests
import pathlib
import json
import os
from tkinter import messagebox, simpledialog

STRIPE_SERVER_BASE = os.environ.get("STRIPE_SERVER_BASE", "https://stripe-backend-r14f.onrender.com")
LOCAL_LICENSE_PATH = os.path.join(os.path.expanduser("~"), ".mi_app_license.json")
LOCAL_USAGE_FALLBACK = os.path.join(os.path.expanduser("~"), ".mi_app_usage_fallback.json")

# --- Local helpers (fallback if server unreachable) ---

def guardar_autosave(texto):
         try:
                  with open(AUTOSAVE_FILE, "w", encoding="utf-8") as f:
                            json.dump({"contenido": texto}, f, ensure_ascii=False, indent=2)
         except Exception:
      
                    pass  # autosave nunca debe romper la app


def cargar_autosave():
         if not os.path.exists(AUTOSAVE_FILE):
                   return ""
         try:
                  with open(AUTOSAVE_FILE, "r", encoding="utf-8") as f:
                             return json.load(f).get("contenido", "")
         except Exception:
                    return ""

def entry_con_placeholder(parent, placeholder):
        entry = tk.Entry(
            parent,
            font=("Segoe UI", 12),
            bg="#2b2b2b",
            fg="#888888",
            insertbackground="white",
            relief="flat",
            highlightthickness=2,
            highlightbackground="#3a3a3a",
            highlightcolor="#00c896"
        )

        entry.insert(0, placeholder)
        entry._placeholder = placeholder
        entry._placeholder_activo = True

        def on_focus_in(event):
                 if entry._placeholder_activo:
                         entry.delete(0, tk.END)
                         entry.config(fg="white")
                         entry._placeholder_activo = False

        def on_focus_out(event):
                 if not entry.get():
                          entry.insert(0, entry._placeholder)
                          entry.config(fg="#888888")
                          entry._placeholder_activo = True

        entry.bind("<FocusIn>", on_focus_in)
        entry.bind("<FocusOut>", on_focus_out)

        return entry


def pedir_texto_moderno(titulo, mensaje, placeholder=""):
        dialogo = tk.Toplevel(root)
        dialogo.title(titulo)
        dialogo.geometry("420x220")
        dialogo.resizable(False, False)
        dialogo.configure(bg="#1e1e1e")
        dialogo.grab_set()

        resultado = {"valor": None}

        ttk.Label(
            dialogo,
            text=titulo,
            font=("Segoe UI", 14, "bold"),
            foreground="white",
            background="#1e1e1e"
        ).pack(pady=(15, 5))

        ttk.Label(
            dialogo,
            text=mensaje,
            font=("Segoe UI", 10),
            foreground="#cccccc",
            background="#1e1e1e",
            wraplength=380
        ).pack(pady=(0, 10))

        entry = entry_con_placeholder(dialogo, placeholder)
        entry.pack(ipady=6, padx=30, fill="x")
        entry.focus()

        frame_btn = tk.Frame(dialogo, bg="#1e1e1e")
        frame_btn.pack(pady=20)

        def aceptar():
                if entry._placeholder_activo:
                         resultado["valor"] = ""
                else:
                         resultado["valor"] = entry.get().strip()
                dialogo.destroy()

        def cancelar():
                 dialogo.destroy()

        tk.Button(
            frame_btn,
            text="OK",
            command=aceptar,
            bg=AZUL_EDITOR,
            fg="white",
            font=("Segoe UI", 10, "bold"),
            relief="flat",
            width=10
        ).pack(side="left", padx=10)

        tk.Button(
            frame_btn,
            text="Cancelar",
            command=cancelar,
            bg=AZUL_EDITOR,
            fg="white",
            font=("Segoe UI", 10),
            relief="flat",
            width=10
        ).pack(side="left")

        dialogo.wait_window()
        return resultado["valor"]


def save_local_fallback(data):
    try:
        pathlib.Path(LOCAL_USAGE_FALLBACK).write_text(json.dumps(data))
    except Exception as e:
        print("Error saving fallback usage:", e)

def load_local_fallback():
    try:
        if pathlib.Path(LOCAL_USAGE_FALLBACK).exists():
            return json.loads(pathlib.Path(LOCAL_USAGE_FALLBACK).read_text())
    except Exception as e:
        print("Error loading fallback usage:", e)
    return {"credits_left": 0, "month_used": 0, "month_start": None}

# --- License local storage (only license key + email) ---
def guardar_licencia_local(license_key, email):
    try:
        data = {"license_key": license_key, "email": email}
        pathlib.Path(LOCAL_LICENSE_PATH).write_text(json.dumps(data))
        return True
    except Exception as e:
        print("Error guardando licencia local:", e)
        return False

def leer_licencia_local():
    try:
        p = pathlib.Path(LOCAL_LICENSE_PATH)
        if p.exists():
            return json.loads(p.read_text())
    except Exception as e:
        print("Error leyendo licencia local:", e)
    return None

# --- Checkout opener ---
def abrir_checkout_en_navegador(email, plan="pro", price_id=None):
    """
    Abre el checkout de Stripe → y después de abrirlo,
    intenta sincronizar la licencia automáticamente cada 5 segundos
    durante hasta 60 segundos.
    """

    # -----------------------------
    # MAPEO PLAN → PRICE ID
    # -----------------------------
    price_map = {
        "starter": "price_1ScJlCGznS3gtqcWGFG56OBX",
        "pro":     "price_1ScJkpGznS3gtqcWsGC3ELYs",
        "agency":  "price_1ScJlUGznS3gtqcWSlvrLQcI",
    }

    if not price_id:
        price_id = price_map.get(plan.lower())

    if not price_id:
        messagebox.showerror("Error", f"Plan inválido: {plan}")
        return None

    url = STRIPE_SERVER_BASE.rstrip("/") + "/create-checkout-session"
    payload = {
        "email": email,
        "plan": plan,
        "price_id": price_id
    }

    try:
        r = requests.post(url, json=payload, timeout=15)
        data = r.json()

        if not data.get("ok"):
            messagebox.showerror("Error Checkout", f"No se pudo crear la sesión: {data}")
            return None

        # -----------------------------
        # 1) ABRIR CHECKOUT
        # -----------------------------
        webbrowser.open(data["url"])
        messagebox.showinfo(
            "Checkout",
            "Se abrió el checkout en tu navegador.\n"
            "Después de pagar, la app sincronizará tu licencia automáticamente."
        )

        # -----------------------------
        # 2) INICIAR PROCESO DE SINCRONIZACIÓN AUTOMÁTICA
        # -----------------------------
        intentar_sincronizar_licencia(email, intentos=0)

        return data.get("id")

    except Exception as e:
        messagebox.showerror("Error Checkout", f"Error conectando con servidor:\n{e}")
        return None



def intentar_sincronizar_licencia(email, intentos=0):
    """
    Intenta sincronizar la licencia cada 5 segundos, hasta 12 intentos (1 minuto).
    """

    MAX_INTENTOS = 12  # 12 intentos → 60 segundos
    INTERVALO = 5000   # 5 segundos

    # Llamar a la función original que ya tienes
    plan, credits = cargar_y_mostrar_licencia()

    # Si ya hay plan pagado → éxito inmediato
    if plan in ("starter", "pro", "agency"):
        messagebox.showinfo(
            "Licencia activada",
            f"Tu plan {plan.upper()} ha sido activado.\n"
            f"Créditos disponibles: {credits}"
        )
        return

    # Si no se logró → volver a intentar
    if intentos < MAX_INTENTOS:
        root.after(INTERVALO, lambda: intentar_sincronizar_licencia(email, intentos + 1))
    else:
        messagebox.showwarning(
            "No confirmado aún",
            "No se pudo confirmar la compra automáticamente.\n"
            "Si ya pagaste, cierra y abre la app para sincronizar tu licencia."
        )

# --- Validate license remotely (returns (ok, payload)) ---
def validar_licencia_remota(license_key):
    url = STRIPE_SERVER_BASE.rstrip("/") + "/license/validate"
    try:
        r = requests.post(url, json={"license_key": license_key}, timeout=10)
        if r.status_code == 200:
            return True, r.json().get("license")
        else:
            try:
                return False, r.json()
            except Exception:
                return False, {"error": "invalid_response"}
    except Exception as e:
        return False, {"error": str(e)}

def validar_por_email(email):
    url = STRIPE_SERVER_BASE.rstrip("/") + "/license/validate"
    try:
        r = requests.post(url, json={"email": email}, timeout=10)
        if r.status_code == 200:
            return True, r.json().get("license")
        else:
            return False, r.json()
    except Exception as e:
        return False, {"error": str(e)}

# --- Usage: call /usage to decrement credits centrally ---
def consume_remote_credit(license_key, action="audio", cost=1):
    url = STRIPE_SERVER_BASE.rstrip("/") + "/usage"
    try:
        r = requests.post(url, json={"license_key": license_key, "action": action, "cost": cost}, timeout=8)
        if r.status_code == 200:
            body = r.json()
            return True, body.get("credits_left")
        else:
            return False, {"error": r.text}
    except Exception as e:
        return False, {"error": str(e)}

# --- Fallback consume local if server fails ---
def consume_local_fallback(cost=1):
    data = load_local_fallback()
    data["month_used"] = data.get("month_used", 0) + cost
    data["credits_left"] = max(0, data.get("credits_left", 0) - cost)
    if not data.get("month_start"):
        data["month_start"] = datetime.utcnow().isoformat()
    save_local_fallback(data)
    return data.get("credits_left")

# --- High level function for actions that cost credits ---
def perform_credited_action(action="audio", cost=1):
    """
    Steps:
    1) read local license
    2) try consume_remote_credit
    3) if success -> return True, new_credits_left
    4) if failure -> consume_local_fallback and warn user
    """
    lic_local = leer_licencia_local()
    if not lic_local or not lic_local.get("license_key"):
        messagebox.showwarning("Sin licencia", "No se encontró una licencia activa. Compra un plan para usar esta función.")
        return False, None

    ok, resp = consume_remote_credit(lic_local["license_key"], action=action, cost=cost)
    if ok:
        return True, resp
    else:
        # fallback
        new_left = consume_local_fallback(cost)
        messagebox.showwarning("Conexión fallida", "No fue posible contactar el servidor; se usará modo limitado offline. Créditos locales actualizados.")
        return True, new_left

# --- Check license on app start (call this at GUI init) ---
def checkear_licencia_inicio():
    local = leer_licencia_local()
    if local and local.get("license_key"):
        ok, info = validar_licencia_remota(local["license_key"])
        if ok:
            # sync local fallback credits with server info for UI convenience
            try:
                credits = int(info.get("credits_left") or info.get("credits") or 0)
                fallback = load_local_fallback()
                fallback["credits_left"] = credits
                if not fallback.get("month_start"):
                    fallback["month_start"] = datetime.utcnow().isoformat()
                save_local_fallback(fallback)
            except Exception:
                pass
            print("Licencia validada:", local["license_key"])
            return True
        else:
            # invalid remotely: remove local
            try:
                pathlib.Path(LOCAL_LICENSE_PATH).unlink()
            except Exception:
                pass
            messagebox.showinfo("Licencia inválida", "La licencia no es válida o expiró. Se requerirá activación.")
    # If no local license, prompt
    resp = messagebox.askquestion("Licencia requerida", "No se encontró una licencia válida. ¿Deseas abrir el pago para activar la app ahora?", icon="question")
    if resp == "yes":
        email = simpledialog.askstring("Pagar Suscripción", "Ingresa tu email para generar la sesión de pago:")
        if email:
            abrir_checkout_en_navegador(email)
    return False

# --- Manual license input (admin/manual) ---
def ingresar_licencia_manual_dialog():
    lic = simpledialog.askstring("Ingresar licencia", "Pega tu licencia (ej: LIC-...):")
    if not lic:
        return
    ok, info = validar_licencia_remota(lic)
    if ok:
        guardar_licencia_local(lic, info.get("email"))
        # sync fallback usage credits
        try:
            credits = int(info.get("credits_left") or info.get("credits") or 0)
            fb = load_local_fallback()
            fb["credits_left"] = credits
            if not fb.get("month_start"):
                fb["month_start"] = datetime.utcnow().isoformat()
            save_local_fallback(fb)
        except Exception:
            pass
        messagebox.showinfo("Licencia válida", "Licencia verificada y guardada localmente.")
    else:
        messagebox.showerror("Licencia inválida", f"No válida: {info}")

# ----------------------------
# END CLIENTE (usa endpoints /license/validate y /usage)
# ----------------------------

# ----------------------------
# VENTANA: PLANES Y SUSCRIPCIONES (DARK MODE - LISTO PARA INTEGRACIÓN REAL, SYNC SERVER)
# ----------------------------
import tkinter as tk
from tkinter import ttk, messagebox
import math
import json
import os
import time
from datetime import datetime, timedelta
import requests  # Necesario para hacer llamadas a la API (fetch_remote_license_info/portal)
import webbrowser  # Necesario para abrir el navegador
from tkinter import simpledialog  # Necesario para prompt_email

# --- CONSTANTES DE COLOR DARK MODE ---
BG_DARK = "#1E1E1E"  # Fondo principal
BG_CARD = "#2D2D2D"  # Fondo de las tarjetas y frames secundarios
FG_LIGHT = "#FFFFFF"  # Color del texto principal
FG_ACCENT_TEXT = "#CCCCCC"  # Color del texto secundario
ACCENT_STARTER = "#22A55A"
ACCENT_PRO = "#1078FF"
ACCENT_AGENCY = "#D64545"

# Rutas locales para uso (seguimiento de créditos)
USAGE_PATH = os.path.join(os.path.expanduser("~"), ".mi_app_usage.json")
# Asegúrate de que esta variable de entorno esté configurada
STRIPE_SERVER_BASE = os.environ.get("STRIPE_SERVER_BASE", "https://stripe-backend-r14f.onrender.com")

# Price IDs (Estos deben estar configurados en el entorno o en el código)
PRICE_ID_STARTER = ("price_1ScJkpGznS3gtqcWsGC3ELYs")
PRICE_ID_PRO = ("price_1ScJlCGznS3gtqcWGFG56OBX")
PRICE_ID_AGENCY = ("price_1ScJlhGznS3gtqcWheD5Qk15")
PRICE_ID_STARTER_ANNUAL = os.environ.get("PRICE_ID_STARTER_ANNUAL", "price_1O...StarterA")
PRICE_ID_PRO_ANNUAL = os.environ.get("PRICE_ID_PRO_ANNUAL", "price_1O...ProA")
PRICE_ID_AGENCY_ANNUAL = os.environ.get("PRICE_ID_AGENCY_ANNUAL", "price_1O...AgencyA")

# Plan -> default credits mapping (solo fallback cuando el servidor NO provea datos)
PLAN_CREDITS = {
    "starter": 100,
    "pro": 300,
    "agency": 1200
}

# Plan limits mapping (para lógica local)
PLAN_LIMITS = {
    "starter": {"videos_per_day": 10, "max_chars": 2000, "batch": False, "export_4k": False},
    "pro": {"videos_per_day": 30, "max_chars": 6000, "batch": True, "batch_limit": 10, "export_4k": True},
    "agency": {"videos_per_day": 9999, "max_chars": 999999, "batch": True, "batch_limit": None, "export_4k": True, "byot": True}
}

# -------------------------------------------------------------------
# LECTURA DE LICENCIA LOCAL (CONEXIÓN A LICENSE.JSON REAL)
# -------------------------------------------------------------------
def leer_licencia_local():
    """Lee license.json real (el mismo que usa tu app)."""
    try:
        license_path = os.path.join(os.path.dirname(__file__), "license.json")
        if os.path.exists(license_path):
            with open(license_path, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return {}

# -------------------------------------------------------------------
# VALIDACIÓN REAL CONTRA TU BACKEND (server_stripe.py)
# -------------------------------------------------------------------
def validar_licencia_remota(license_key):
    """
    Envía license_key a tu backend REAL (server_stripe.py).
    Retorna (True, license_dict) o (False, error_message_or_dict)
    """
    global credits_left_global  # <<< IMPORTANTE
    global credits_total_global # por si lo usas

    try:
        r = requests.post(
            STRIPE_SERVER_BASE.rstrip("/") + "/license/validate",
            json={"license_key": license_key},
            timeout=10
        )
        try:
            data = r.json()
        except Exception:
            data = {"error": "invalid_json_response", "raw": r.text}

        # -------------------------------------------------
        # ✔ CASO VÁLIDO CONFIRMADO POR EL SERVIDOR
        # -------------------------------------------------
        if r.status_code == 200 and data.get("valid"):
            lic = data.get("license")

            try:
                credits_left_global = int(lic.get("credits_left", 0))
            except:
                credits_left_global = 0

            try:
                credits_total_global = int(lic.get("credits", 0))
            except:
                credits_total_global = credits_left_global

            return True, lic

        # -------------------------------------------------
        # 🔒 CASO EXPLÍCITAMENTE INVÁLIDO (ÚNICO QUE FALLA)
        # -------------------------------------------------
        if data.get("valid") is False:
            reason = data.get("reason") or "invalid"
            return False, reason

        # -------------------------------------------------
        # ⚠ BACKEND RESPONDE RARO / NOT_FOUND / PARCIAL
        # → NO invalidar, confiar en local
        # -------------------------------------------------
        print("⚠ Backend no confirmó licencia, usando licencia local")
        return True, None

    except Exception as e:
        # -------------------------------------------------
        # 🔥 BACKEND DORMIDO / TIMEOUT / SIN CONEXIÓN
        # → NO INVALIDAR
        # -------------------------------------------------
        print("⚠ Backend no disponible, modo offline:", e)
        return True, None


def on_verification_success(email, license_obj):
    """
    Se ejecuta cuando el servidor indica que el email YA fue verificado.
    - Si ya existe licencia en el servidor → la recupera
    - Si NO existe licencia → crea la FREE
    - Guarda todo localmente
    - Refresca la UI cuando exista
    """
    global verification_handled
    email_global = email

    if verification_handled:
                  return  # ⛔ YA SE EJECUTÓ, NO REPETIR

    verification_handled = True

    # ------------------------------------------------------
    # 1) Informar al usuario
    # ------------------------------------------------------
    mostrar_toast(
                    f"✅ Email verificado\n\n"
                    f"El correo {email} ya fue verificado correctamente.\n"
                    f"Sincronizando tu licencia...",
                    tipo="success",
                    duracion=6000
          )


    # ------------------------------------------------------
    # 2) Intentar recuperar licencia existente del servidor
    # ------------------------------------------------------
    licencia = None

    if isinstance(license_obj, dict) and license_obj.get("license_key"):
        licencia = license_obj
    else:
        try:
            r = requests.get(
                f"{SERVER_URL}/license/by_email",
                params={"email": email},
                timeout=8
            )
            if r.status_code == 200:
                data = r.json()
                print("STATUS:", r.status_code)
                print("RAW RESPONSE:", data)  # Aquí vemos la respuesta en consola
                if data.get("ok") and isinstance(data.get("license"), dict):
                    licencia = data["license"]
        except Exception as e:
            print("⚠ Error recuperando licencia remota:", e)

    # 🔥🔥🔥 FIX CRÍTICO: inyectar licencia en memoria
    if isinstance(licencia, dict):
                   try:
                           license_key = (
                                     licencia.get("license_key")
                                     or licencia.get("key")
                                     or licencia.get("id")
                            )
                           if license_key:
                                   global license_key_global
                                   license_key_global = license_key
                   except Exception as e:
                             print("⚠ Error sincronizando license_key_global:", e)

    # ------------------------------------------------------
    # 3) Si NO hay licencia → crear FREE
    # ------------------------------------------------------
    if not licencia:
        ok, resp = crear_licencia_free_remota(email)

        if not ok:
            messagebox.showerror(
                "Error al crear licencia",
                "Tu email fue verificado, pero ocurrió un error creando la licencia gratuita.\n"
                "Intenta nuevamente."
            )
            if 'btn_free' in globals():
                btn_free.config(state="normal")
            return

        licencia = resp.get("license", resp)

    # ------------------------------------------------------
    # 4) Guardar licencia localmente
    # ------------------------------------------------------
    saved = guardar_licencia_local_desde_server(licencia)

    if saved:
                   mostrar_toast(
                             "🎉 Licencia activada\n\n"
                             "Tu licencia ha sido sincronizada y activada correctamente.\n"
                             "¡Ya puedes usar la aplicación!",
                             tipo="success",
                             duracion=7000
                    )
    else:
                   mostrar_toast(
                             "⚠️ Problema local\n\n"
                             "La licencia existe en el servidor, pero no se pudo guardar localmente.\n"
                             "Revisa permisos de la carpeta.",
                             tipo="error",
                             duracion=8000
                     )


    # ------------------------------------------------------
    # 5) Reactivar botón (si existe)
    # ------------------------------------------------------
    if 'btn_free' in globals():
        btn_free.config(state="normal")

    # ------------------------------------------------------
    # 6) Refrescar UI SOLO si ya existe
    # ------------------------------------------------------
    if 'lbl_plan_value' in globals() and 'lbl_credits' in globals():
        cargar_y_mostrar_licencia()


# -------------------------------------------------------------------

import re

def mostrar_login_modal():
        modal = tk.Toplevel(root)
        modal.title("Inicio de sesión")
        modal.geometry("420x260")
        modal.resizable(False, False)
        modal.transient(root)
        modal.grab_set()  # BLOQUEA la app hasta cerrar

        # Centrar ventana
        modal.update_idletasks()
        x = root.winfo_x() + (root.winfo_width() // 2) - 210
        y = root.winfo_y() + (root.winfo_height() // 2) - 130
        modal.geometry(f"+{x}+{y}")

        # ---------------- UI ----------------
        frame = tk.Frame(modal, padx=25, pady=25)
        frame.pack(expand=True, fill="both")

        tk.Label(
            frame,
            text="Inicia sesión para utilizar TurboClip",
            font=("Segoe UI", 13, "bold")
        ).pack(pady=(0, 15))

        tk.Label(
            frame,
            text="Ingresa tu correo electrónico\npara continuar",
            font=("Segoe UI", 10),
            fg="#555"
        ).pack(pady=(0, 10))

        email_var = tk.StringVar()

        entry = tk.Entry(
            frame,
            textvariable=email_var,
            font=("Segoe UI", 11),
            width=35
        )
        entry.pack(pady=8)
        entry.focus()

        status_lbl = tk.Label(
            frame,
            text="",
            fg="red",
            font=("Segoe UI", 9)
        )
        status_lbl.pack(pady=(5, 0))

        # 🔒 VALIDACIÓN DE EMAIL
        def es_email_valido(email: str) -> bool:
            if not email:
                return False
            patron = r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$"
            return re.match(patron, email.strip()) is not None

        def confirmar():
            email = email_var.get().strip()

            if not es_email_valido(email):
                status_lbl.config(text="Ingresa un correo electrónico válido")
                entry.focus()
                return  # ⛔ NO CIERRA EL MODAL

            # ✅ EMAIL VÁLIDO → CONTINUAR
            modal.destroy()
            root.after(100, lambda: asegurar_email_obligatorio_desde_ui(email))

        btn = tk.Button(
            frame,
            text="Continuar",
            font=("Segoe UI", 11),
            width=18,
            command=confirmar
        )
        btn.pack(pady=15)

        def cerrar_sin_login():
            print("ℹ Login cerrado sin ingresar correo")
            modal.destroy()

        modal.protocol("WM_DELETE_WINDOW", cerrar_sin_login)

def on_click_generar(progress_label, boton_generar, anim_label, big_gif_label, num_audios_label):
        if toast_bloqueando:
                             return

        if not license_key_global:
            mostrar_toast(
                "🔒 Para generar videos necesitas iniciar sesión\n\n👇 Ingresa tu correo cuando quieras continuar\n\n✨ Así accederás a la licencia gratis y podrás generar tus primeros 10 videos",
                tipo="info"
            )

            root.after(200, mostrar_login_modal)
            return  # ⛔ ESTO ES LO QUE FALTABA

        

        # ✔ YA HAY LICENCIA → CONTINUAR NORMAL
        validar_creditos_y_generar(
            progress_label,
            boton_generar,
            anim_label,
            big_gif_label,
            num_audios_label
        )

        
def asegurar_email_obligatorio_desde_ui(email):
    global email_global

    email_global = None

    # Lanza exactamente el mismo flujo que ya funciona
    root.after(0, lambda: asegurar_email_obligatorio_con_email(email))

def asegurar_email_obligatorio_con_email(email):
        global email_global

        # 1) Solicitar verificación
        ok = solicitar_verificacion(email)
        if not ok:
            mostrar_toast(
                "❌ No se pudo iniciar la verificación.\n\nIntenta nuevamente.",
                tipo="error",
                duracion=6000
            )
            mostrar_login_modal()
            return
 
        # 2) Check inmediato
        try:
            r = requests.get(
                f"{SERVER_URL}/auth/check_status",
                params={"email": email},
                timeout=5
            )
            status = r.json()
        except:
            status = {}

        if status.get("verified"):
            try:
                r = requests.post(
                    f"{SERVER_URL}/license/by-email",
                    json={"email": email},
                    timeout=6
                )
                resp = r.json()

                if resp.get("exists"):
                    on_verification_success(email, resp.get("license"))
                    return
            except:
                pass

            # Crear licencia FREE si no existe
            on_verification_success(email, None)
            return

        # 3) Avisar (TOAST)
        mostrar_toast(
            "📧 Verificación enviada\n\n"
            "Te hemos enviado un correo de verificación.\n"
            "Por favor confirma el enlace.",
            tipo="info",
            duracion=6000
        )

        # 4) Polling NO bloqueante (cada 2 segundos)
        root.after(2000, lambda: _poll_verificacion(email, intentos=30))


def _poll_verificacion(email, intentos):
        if intentos <= 0:
            mostrar_toast(
                "⏱ Tiempo agotado\n\n"
                "No se detectó la verificación.\n"
                "Intenta nuevamente.",
                tipo="error",
                duracion=7000
            )
            mostrar_login_modal()
            return

        try:
            r = requests.get(
                f"{SERVER_URL}/auth/check_status",
                params={"email": email},
                timeout=5
            )
            status = r.json()

            if status.get("verified"):
                try:
                    r = requests.post(
                        f"{SERVER_URL}/license/by-email",
                        json={"email": email},
                        timeout=6
                    )
                    resp = r.json()

                    if resp.get("exists"):
                        on_verification_success(email, resp.get("license"))
                        return
                except:
                    pass

                # Crear licencia FREE si no existe
                on_verification_success(email, None)
                return

        except:
            pass

        # Reintentar sin bloquear UI
        root.after(2000, lambda: _poll_verificacion(email, intentos - 1))

# ---------- Helpers de uso local (Gestión de créditos fallback) ----------
def load_usage():
    try:
        if os.path.exists(USAGE_PATH):
            with open(USAGE_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                if "month_start" in data:
                    month_start = datetime.fromisoformat(data["month_start"]) 
                    if month_start.month != datetime.utcnow().month or (datetime.utcnow() - month_start).days > 40:
                        leftover = data.get("credits_left", 0)
                        roll = int(leftover * 0.15)
                        data = {"month_start": datetime.utcnow().isoformat(), "credits_left": roll, "month_used": 0}
                        save_usage(data)
                return data
    except Exception as e:
        print("Error cargando uso local:", e)
    
    # 🔒 CAMBIO CLAVE: no asumir 0 definitivo
    data = {
        "month_start": datetime.utcnow().isoformat(),
        "credits_left": credits_left_global or 0,
        "month_used": 0
    }
    save_usage(data)
    return data


def save_usage(data):
    try:
        with open(USAGE_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f)
    except Exception as e:
        print("Error guardando uso local:", e)

def sync_usage_with_license(license_obj):
    """
    Inicializa usage.json desde la licencia SOLO si no existe.
    """
    try:
        if not license_obj:
            return

        if os.path.exists(USAGE_PATH):
            return  # ya existe → no tocar

        credits = int(
            license_obj.get("credits_left", license_obj.get("credits", 0))
        )

        data = {
            "month_start": datetime.utcnow().isoformat(),
            "credits_left": credits,
            "month_used": 0
        }

        save_usage(data)

    except Exception as e:
        print("Error sincronizando usage con licencia:", e)



def credit_cost_for_action(action):
    if action in ("audio", "subtitle"):
        return 1
    return 0


def consume_credits(amount):
    if generacion_ilimitada_activa():
        print("♾️ Ilimitado activo → usage.json no se modifica")
        return

    usage = load_usage()
    usage["month_used"] = usage.get("month_used", 0) + amount
    usage["credits_left"] = max(0, usage.get("credits_left", 0) - amount)
    save_usage(usage)



def add_credits(amount):
    usage = load_usage()
    usage["credits_left"] = usage.get("credits_left", 0) + amount
    save_usage(usage)

# ---------- UI Components (Adaptado a Dark Mode) ----------
def make_card(parent, title, price_text, bullets, cta_text, cta_cmd, recommended=False, accent=ACCENT_PRO, width=360):
    card = tk.Frame(parent, bd=1, relief="flat", padx=14, pady=10, bg=BG_CARD, highlightbackground="#3A3A3A", highlightthickness=1)
    
    header = tk.Frame(card, bg=BG_CARD)
    header.pack(fill="x")
    if recommended:
        tag = tk.Label(header, text="⭐ MÁS POPULAR", bg=accent, fg="#ffffff", font=("Arial", 9, "bold"), padx=8, pady=3)
        tag.pack(side="top", anchor="e")
    
    title_lbl = tk.Label(card, text=title, font=("Arial", 14, "bold"), bg=BG_CARD, fg=FG_LIGHT)
    title_lbl.pack(anchor="w", pady=(6,4))
    price_lbl = tk.Label(card, text=price_text, font=("Arial", 12, "bold"), fg=accent, bg=BG_CARD)
    price_lbl.pack(anchor="w")

    bullets_frame = tk.Frame(card, bg=BG_CARD)
    bullets_frame.pack(anchor="w", pady=(8,6))
    for b in bullets:
        row = tk.Frame(bullets_frame, bg=BG_CARD)
        row.pack(anchor="w", pady=2)
        bullet = tk.Label(row, text="•", font=("Arial", 12, "bold"), bg=BG_CARD, fg=accent)
        bullet.pack(side="left")
        label = tk.Label(row, text=b, bg=BG_CARD, fg=FG_ACCENT_TEXT, font=("Arial", 10))
        label.pack(side="left", padx=6)

    foot = tk.Label(card, text="", bg=BG_CARD, font=("Arial", 9), fg="#999999")
    foot.pack(anchor="w", pady=(6,8))
    btn = tk.Button(card, text=cta_text, command=cta_cmd, bg=accent, fg="#fff", bd=0, padx=14, pady=8, cursor="hand2")
    btn.pack(anchor="center", pady=(2,0))
    return card

# ---------- Logic: map plan -> price_id ----------
def get_price_id_for(plan_key, annual=False):
    plan_key = plan_key.lower()
    if plan_key == "starter":
        return PRICE_ID_STARTER_ANNUAL if annual and PRICE_ID_STARTER_ANNUAL else PRICE_ID_STARTER
    if plan_key == "pro":
        return PRICE_ID_PRO_ANNUAL if annual and PRICE_ID_PRO_ANNUAL else PRICE_ID_PRO
    if plan_key == "agency":
        return PRICE_ID_AGENCY_ANNUAL if annual and PRICE_ID_AGENCY_ANNUAL else PRICE_ID_AGENCY
    return ""

# -------------------------------------------------------------------
# NUEVO: Actualiza automáticamente la UI del plan al iniciar la app
# -------------------------------------------------------------------
def checkear_licencia_inicio():
    local = leer_licencia_local()
    if not local or "license_key" not in local:
        print("Sin licencia local.")
        return

    ok, data = validar_licencia_remota(local["license_key"])
    if ok:
        print("Licencia activa:", data)
        # sincronizamos fallback local para que el GUI muestre los mismos números si se queda offline
        try:
            credits_total = int(data.get("credits") or PLAN_CREDITS.get((data.get("plan") or "starter"), 0))
            credits_left = int(data.get("credits_left") if data.get("credits_left") is not None else credits_total)
            fb = load_usage()
            fb["credits_left"] = credits_left
            if not fb.get("month_start"):
                fb["month_start"] = datetime.utcnow().isoformat()
            save_usage(fb)
        except Exception:
            pass
    else:
        # 🔒 FIX CRÍTICO: backend dormido ≠ licencia inválida
        if isinstance(data, str) and data in ("not_found", "timeout", "connection_error"):
            print("⚠ Backend dormido, se usa licencia local")
            return  # ← NO bloquear app

        print("Licencia inválida o no encontrada:", data)

# -------------------------------------------------------------------
# VALIDACIÓN + OBTENER ESTADO REMOTO PARA LA UI (RETORNA ESTRICTO)
# -------------------------------------------------------------------
def fetch_remote_license_info():
    """
    Llama al backend y devuelve:
    { valid: bool, license: dict or None, error: str or None }
    NOTA: Para la opción A, mostramos siempre credits y credits_left que provengan del servidor.
    """
    local = None
    try:
        local = leer_licencia_local()
    except Exception:
        local = None

    if local and local.get("license_key"):
        ok, data = validar_licencia_remota(local["license_key"])
        if ok:
            # data es el dict de license tal como lo devuelve el servidor
            return {"valid": True, "license": data}
        else:
            return {"valid": False, "license": None, "error": data}

    return {"valid": False, "license": None, "error": "no_local_license"}

# ---------- Helpers: abrir checkout ----------
def abrir_checkout_en_navegador(email, plan, price_id):
    if not STRIPE_SERVER_BASE:
        messagebox.showerror("Error de Configuración", "STRIPE_SERVER_BASE no está configurado. No se puede iniciar el checkout.")
        return

    checkout_url = f"{STRIPE_SERVER_BASE.rstrip('/')}/create-checkout-session?email={email}&priceId={price_id}"

    try:
        webbrowser.open(checkout_url)
    except Exception as e:
        messagebox.showerror("Error", f"Error al abrir el navegador: {e}")

# ---------- POPUP PREMIUM - CRÉDITOS AGOTADOS (SE DEFINE AQUÍ) ----------
def popup_creditos_agotados(win_parent):
    """
    Pop-up mejorado con:
    - Card 1: Comprar créditos adicionales (100, 300, 1000) cada una con su botón
    - Card 2: Pasarte al plan PRO (botón que abre la ventana de pricing / checkout)
    Usa variables de entorno para links de compra:
      CREDIT_LINK_100, CREDIT_LINK_300, CREDIT_LINK_1000
    Si no existen, se construyen URLs fallback con STRIPE_SERVER_BASE.
    """
    popup = tk.Toplevel(win_parent)
    popup.title("Créditos agotados")
    popup.configure(bg=BG_DARK)
    popup.geometry("760x420")
    popup.resizable(False, False)
    popup.transient(win_parent)
    popup.grab_set()

    try:
        popup.iconbitmap("icon.ico")
    except Exception:
        pass

    # ------------ LINKS PARA COMPRAR CRÉDITOS -------------
    CREDIT_LINK_100 = os.environ.get("CREDIT_LINK_100", "").strip()
    CREDIT_LINK_300 = os.environ.get("CREDIT_LINK_300", "").strip()
    CREDIT_LINK_1000 = os.environ.get("CREDIT_LINK_1000", "").strip()

    # Obtener email del backend (única fuente segura)
    # Obtener email desde la licencia ya cargada al inicio
    email_user = MAIN_LICENSE.get("email", "")
    print("EMAIL DETECTADO EN POPUP:", repr(email_user))



 
    # -------------------------
    # Fallbacks con email REAL
    # -------------------------
    CREDIT_LINK_100 = f"{STRIPE_SERVER_BASE.rstrip('/')}/buy-credits?email={email_user}&pack=100"
    CREDIT_LINK_300 = f"{STRIPE_SERVER_BASE.rstrip('/')}/buy-credits?email={email_user}&pack=300"
    CREDIT_LINK_1000 = f"{STRIPE_SERVER_BASE.rstrip('/')}/buy-credits?email={email_user}&pack=1000"

    print("URL FINAL 100:", CREDIT_LINK_100)
    print("URL FINAL 300:", CREDIT_LINK_300)
    print("URL FINAL 1000:", CREDIT_LINK_1000)


    # contenedor principal
    container = tk.Frame(popup, bg=BG_DARK)
    container.pack(expand=True, fill="both", padx=18, pady=18)

    title = tk.Label(container, text="Créditos agotados", fg="#FF4C4C", bg=BG_DARK, font=("Arial", 20, "bold"))
    title.pack(anchor="w", pady=(0,6))

    subtitle = tk.Label(container, text="No puedes generar videos hasta adquirir más créditos. Elige una opción para continuar.", fg=FG_ACCENT_TEXT, bg=BG_DARK, font=("Arial", 10))
    subtitle.pack(anchor="w", pady=(0,12))

    # layout de dos columnas
    cols = tk.Frame(container, bg=BG_DARK)
    cols.pack(fill="both", expand=True)

    # ----------------------------------------
    # CARD 1: Comprar créditos adicionales
    # ----------------------------------------
    card1 = tk.Frame(cols, bg=BG_CARD, bd=0, relief="flat", padx=12, pady=12)
    card1.pack(side="left", fill="both", expand=True, padx=(0,10))

    tk.Label(card1, text="💳 Comprar créditos adicionales", font=("Arial", 14, "bold"), bg=BG_CARD, fg=FG_LIGHT).pack(anchor="w", pady=(0,6))
    tk.Label(card1, text="Compra paquetes de créditos para seguir publicando sin interrupciones. Recomendado: 300 créditos.", font=("Arial", 10), bg=BG_CARD, fg=FG_ACCENT_TEXT, wraplength=320, justify="left").pack(anchor="w")

    plans_frame = tk.Frame(card1, bg=BG_CARD)
    plans_frame.pack(fill="x", pady=(10,6))

    def open_link(url):
        try:
            webbrowser.open(url)
        except Exception:
            try:
                # Intento alternativo
                webbrowser.open_new(url)
            except Exception:
                messagebox.showerror("Error", "No se pudo abrir el enlace de compra.")

    # cada fila para plan
    def make_credit_row(parent, label_text, price_text, url, recommended=False):
        row = tk.Frame(parent, bg=BG_CARD)
        row.pack(fill="x", pady=8, padx=(4,4))

        left = tk.Frame(row, bg=BG_CARD)
        left.pack(side="left", anchor="w")
        tk.Label(left, text=label_text, font=("Arial", 12, "bold"), bg=BG_CARD, fg=FG_LIGHT).pack(anchor="w")
        tk.Label(left, text=price_text, font=("Arial", 10), bg=BG_CARD, fg=FG_ACCENT_TEXT).pack(anchor="w")

        right = tk.Frame(row, bg=BG_CARD)
        right.pack(side="right", anchor="e")
        buy_btn = tk.Button(right, text="Comprar", font=("Arial", 10, "bold"), bg="#FF8C42", fg="white", bd=0, padx=12, pady=6, cursor="hand2", command=lambda u=url: open_link(u))
        buy_btn.pack(side="right")

        if recommended:
            tag = tk.Label(row, text="RECOMENDADO", bg="#22A55A", fg="white", font=("Arial", 8, "bold"), padx=6)
            tag.pack(side="right", padx=(0,8))

    make_credit_row(plans_frame, "100 créditos", "$9", CREDIT_LINK_100)
    make_credit_row(plans_frame, "300 créditos", "$19", CREDIT_LINK_300, recommended=True)
    make_credit_row(plans_frame, "1000 créditos", "$39", CREDIT_LINK_1000)

    note = tk.Label(card1, text="Los paquetes no obligan a cambiar de plan. Compra rápido y sigue creando.", font=("Arial", 9), bg=BG_CARD, fg="#999999", wraplength=320, justify="left")
    note.pack(anchor="w", pady=(8,0))

    # ----------------------------------------
    # CARD 2: Pasarte al Plan PRO (Upsell)
    # ----------------------------------------
    card2 = tk.Frame(cols, bg=BG_CARD, bd=0, relief="flat", padx=12, pady=12)
    card2.pack(side="left", fill="both", expand=True, padx=(10,0))

    tk.Label(card2, text="🔥 Pásate al Plan PRO", font=("Arial", 14, "bold"), bg=BG_CARD, fg=FG_LIGHT).pack(anchor="w", pady=(0,6))
    tk.Label(card2, text="300 créditos, voz neural premium, batch y prioridad en exportaciones.", font=("Arial", 10), bg=BG_CARD, fg=FG_ACCENT_TEXT, wraplength=320, justify="left").pack(anchor="w")

    perks = [
        "Genera como un PRO ",
        "Voz neural premium y más opciones de estilo",
        "Batching avanzado y export 1080",
        "Soporte prioritario"
    ]
    perks_frame = tk.Frame(card2, bg=BG_CARD)
    perks_frame.pack(anchor="w", pady=(10,6))
    for p in perks:
        r = tk.Frame(perks_frame, bg=BG_CARD)
        r.pack(anchor="w", pady=4)
        tk.Label(r, text="•", bg=BG_CARD, fg=ACCENT_PRO, font=("Arial", 12, "bold")).pack(side="left")
        tk.Label(r, text=p, bg=BG_CARD, fg=FG_ACCENT_TEXT, font=("Arial", 10)).pack(side="left", padx=6)

    # Botón para actualizar a PRO — intenta usar flow existente si está disponible
    def go_pro():
        try:
            popup.destroy()
        except Exception:
            pass

        # Intenta abrir el panel de upgrade de tu app:
        # 1) Si hay un endpoint STRIPE_SERVER_BASE que soporte create-checkout-session para plan PRO vía price id:
        try:
            # Si PRICE_ID_PRO está definido, abrimos checkout pidiendo email
            if PRICE_ID_PRO:
                # Intentar usar el email guardado o pedir uno
                parent_root = None
                try:
                    parent_root = win_parent.master
                except Exception:
                    parent_root = win_parent
                email = prompt_email(parent_root)
                if email:
                    abrir_checkout_en_navegador(email, plan="pro", price_id=PRICE_ID_PRO)
                    return
        except Exception:
            pass

        # 2) Si no funcionó el flow anterior, intentamos abrir un enlace directo correspondiente:
        PRO_FALLBACK = os.environ.get("PRO_PLAN_LINK", "").strip()
        if not PRO_FALLBACK:
            PRO_FALLBACK = f"{STRIPE_SERVER_BASE.rstrip('/')}/create-checkout-session?priceId={PRICE_ID_PRO}"
        try:
            webbrowser.open(PRO_FALLBACK)
        except Exception:
            try:
                webbrowser.open_new(PRO_FALLBACK)
            except Exception:
                messagebox.showinfo("Actualizar a PRO", "No se pudo abrir el flujo de compra. Intenta actualizar desde la ventana de Planes.")

    tk.Button(card2, text="Actualizar a PRO — $49 / mes", font=("Arial", 12, "bold"), bg=ACCENT_PRO, fg="white", bd=0, padx=14, pady=10, cursor="hand2", command=go_pro).pack(pady=(10,6))

    # Footer: CTA rápido y cerrar
    footer_frame = tk.Frame(container, bg=BG_DARK)
    footer_frame.pack(fill="x", pady=(12,0))

    help_lbl = tk.Label(footer_frame, text="¿Necesitas ayuda? Abre el panel de facturación o contáctanos.", bg=BG_DARK, fg="#999999", font=("Arial", 9))
    help_lbl.pack(side="left", padx=(0,6))

    def open_billing_panel():
        try:
            # intentamos abrir el portal usando el backend si hay customer id disponible
            licinfo = fetch_remote_license_info()
            if licinfo.get("valid") and licinfo.get("license"):
                lic = licinfo["license"]
                cust = lic.get("stripe_customer_id")
                if not cust:
                    messagebox.showinfo("Portal", "No se encontró customer_id para abrir el portal. ¿Tiene un plan activo?")
                    return
                
                try:
                    r = requests.post(STRIPE_SERVER_BASE.rstrip("/") + "/portal-session", json={"customer_id": cust}, timeout=10)
                    if r.status_code == 200:
                        data = r.json()
                        url = data.get("url")
                        if url:
                            webbrowser.open(url)
                            return
                    messagebox.showerror("Error", f"No se pudo abrir el portal: {r.text}")
                except:
                    messagebox.showerror("Error", "Error de conexión al crear portal.")
            else:
                # abrir ventana de planes si no hay licencia
                try:
                    open_pricing_window(win_parent.master)
                except Exception:
                    messagebox.showinfo("Portal", "No tienes un plan activo o la licencia no es válida.")
        except Exception:
            messagebox.showinfo("Portal", "No se pudo abrir el panel de facturación.")

    tk.Button(footer_frame, text="Abrir panel de facturación", bg="#444444", fg=FG_LIGHT, bd=0, padx=10, pady=6, cursor="hand2", command=open_billing_panel).pack(side="right")

    # Botón cerrar
    tk.Button(container, text="Cerrar", bg="#333333", fg="white", bd=0, padx=10, pady=6, cursor="hand2", command=popup.destroy).pack(pady=(8,0))

# ---------- UI window principal ----------
def open_pricing_window(root):
    for w in root.winfo_children():
        if isinstance(w, tk.Toplevel) and getattr(w, "_is_pricing_window", False):
            w.lift()
            return

    win = tk.Toplevel(root)
    win._is_pricing_window = True
    win.title("Planes y Suscripciones")
    win.geometry("980x720")
    win.config(bg=BG_DARK)
    win.transient(root)
    win.grab_set()

    style = ttk.Style()
    style.theme_use('clam')
    style.configure("TProgressbar", foreground=ACCENT_PRO, background=ACCENT_PRO, troughcolor=BG_CARD)

    header = tk.Frame(win, bg=BG_DARK, pady=12)
    header.pack(fill="x")
    tk.Label(header, text="Publica sin sufrir. Elige tu ritmo.", font=("Arial", 20, "bold"), bg=BG_DARK, fg=FG_LIGHT).pack(anchor="w", padx=20)
    tk.Label(header, text="Elige un plan que te permita crear contenido sin perder tiempo. Pro es la más escogida por nuestros usuarios.", font=("Arial", 11), bg=BG_DARK, fg=FG_ACCENT_TEXT).pack(anchor="w", padx=20, pady=(6,0))

    body = tk.Frame(win, bg=BG_DARK)
    body.pack(fill="both", expand=True, padx=20, pady=10)

    left = tk.Frame(body, bg=BG_DARK)
    left.pack(side="left", fill="both", expand=True, padx=(0,20))

    right = tk.Frame(body, width=320, bg=BG_CARD, bd=0, relief="flat", highlightbackground="#3A3A3A", highlightthickness=1)
    right.pack(side="right", fill="y")
    right.pack_propagate(False)

    cards_container = tk.Frame(left, bg=BG_DARK)
    cards_container.pack(fill="both", expand=True)

    # --- Tarjetas (CTA) ---
    def cta_starter_month(local_test=False):
        # --- MODO PRUEBA LOCAL (NO STRIPE) ---
        if local_test:
            try:
                r = requests.post(
                    STRIPE_SERVER_BASE.rstrip("/") + "/license/local-create",
                    json={"license_key": "TEST-BASICO", "plan": "starter", "credits": 1},
                    timeout=5
                )
                data = r.json()
            except Exception as e:
                messagebox.showerror("Error", f"No se pudo actualizar licencia local: {e}")
                return

            if not data.get("license"):
                messagebox.showerror("Error", "Respuesta inválida del servidor.")
                return

            guardar_licencia_local_desde_server(data["license"])
            cargar_y_mostrar_licencia()
            messagebox.showinfo("Actualizado", "Licencia local Starter lista.")
            return

        # --- MODO STRIPE NORMAL ---
        email = prompt_email(win)
        if not email:
            return

        price_id = get_price_id_for("starter", annual=False)
        abrir_checkout_en_navegador(email, plan="starter", price_id=price_id)


        
    def cta_pro_month():
        email = prompt_email(win)
        if not email: return
        price_id = get_price_id_for("pro", annual=False)
        abrir_checkout_en_navegador(email, plan="pro", price_id=price_id)

    def cta_agency_month():
        email = prompt_email(win)
        if not email: return
        price_id = get_price_id_for("agency", annual=False)
        abrir_checkout_en_navegador(email, plan="agency", price_id=price_id)

    card1 = make_card(cards_container,
                      title="🎯 Starter — Ideal para comenzar.",
                      price_text="Desde $19 / mes",
                      bullets=["100 créditos / mes", "1000–2000 caracteres por texto", "Subtítulos automáticos", "Exportación HD", "10 videos/día (máx)"],
                      cta_text="Comenzar por $19 / mes",
                      cta_cmd=cta_starter_month,
                      recommended=False,
                      accent=ACCENT_STARTER)
    card1.pack(side="left", padx=8, pady=8, ipadx=6, ipady=6)

    card2 = make_card(cards_container,
                      title="🚀 PRO — Crecimiento diario",
                      price_text="Desde $49 / mes",
                      bullets=["300 créditos / mes", "Voz neural premium", "Batch hasta 10 audios", "1080p / 4K básico", "Hooks automáticos"],
                      cta_text="Escalar por $49 / mes",
                      cta_cmd=cta_pro_month,
                      recommended=True,
                      accent=ACCENT_PRO)
    card2.pack(side="left", padx=8, pady=8, ipadx=6, ipady=6)

    card3 = make_card(cards_container,
                      title="🏢 Agencia — Equipo y volumen",
                      price_text="Desde $149 / mes",
                      bullets=["900–2000 créditos / mes", "Batch ilimitado (por créditos)", "4K / HDR export", "Marca blanca", "Multi perfil"],
                      cta_text="Producción PRO — $149 / mes",
                      cta_cmd=cta_agency_month,
                      recommended=False,
                      accent=ACCENT_AGENCY)
    card3.pack(side="left", padx=8, pady=8, ipadx=6, ipady=6)

        # ---------- Right side ----------
    status_frame = tk.Frame(right, bg=BG_CARD, padx=12, pady=12)
    status_frame.pack(fill="both", expand=True)

    lbl_plan_title = tk.Label(status_frame, text="Plan actual", font=("Arial", 12, "bold"), bg=BG_CARD, fg=FG_LIGHT)
    lbl_plan_title.pack(anchor="w")

    global lbl_plan_value
    lbl_plan_value = tk.Label(
        status_frame,
        text="No activado",
        font=("Arial", 10),
        bg=BG_CARD,
        fg=FG_ACCENT_TEXT
    )
    lbl_plan_value.pack(anchor="w", pady=(2, 6))


    global lbl_credits
    lbl_credits = tk.Label(
        status_frame,
        text="Créditos: — / —",
        font=("Arial", 11, "bold"),
        bg=BG_CARD,
        fg=FG_LIGHT
    )
    lbl_credits.pack(anchor="w", pady=(6,6))

    lic = cargar_licencia_local()

    if lic:
                  ok, msg = validar_licencia_en_servidor()

                  if msg and (
                          "not_found" in str(msg).lower()
                          or "offline" in str(msg).lower()
                          or "backend" in str(msg).lower()
                   ):
                          estado = "Licencia verificada localmente (modo offline)"
                  elif not ok:
                          estado = msg
                  else:
                          estado = "Licencia válida"

                  print("Estado licencia:", estado)


    else:
        print("No hay licencia local.")

    def popup_pro_upgrade(parent, title, message):
    	win = tk.Toplevel(parent)
    	win.title(title)
    	win.geometry("380x260")
    	win.configure(bg="#1E1E1E")
    	win.resizable(False, False)

    	tk.Label(win, text=title, font=("Arial", 16, "bold"), fg="white", bg="#1E1E1E").pack(pady=(20,5))
    	tk.Label(win, text=message, font=("Arial", 11), fg="#CCCCCC", bg="#1E1E1E", wraplength=340, justify="left").pack(pady=(5,20))

    def go_pro():
        win.destroy()
        cta_pro_month()  # abre el checkout del plan PRO



    # ===============================
    # 🔥 Carrusel de ADS (Popup) — MEJORADO
    # ===============================

    def cargar_carrusel_ads_popup():
        try:
            url = f"https://stripe-backend-r14f.onrender.com/ads/popup"
            data = requests.get(url, timeout=5).json()

            ads = data.get("ads", [])

            if not ads:
                print("No hay ADS para popup")
                return

            # Frame contenedor (tamaño real fijo)
            carrusel_frame = tk.Frame(left, bg="#000", width=900, height=230)
            carrusel_frame.pack(padx=12, pady=(10,15))
            carrusel_frame.pack_propagate(False)

            # Label imagen (ocupa todo el frame)
            lbl_img = tk.Label(carrusel_frame, bd=0, cursor="hand2", bg="#000")
            lbl_img.place(relx=0, rely=0, relwidth=1, relheight=1)

            # Variables de control
            index = {"i": 0}
            current_ad = {"url": None}
            current_image = {"img": None}

            # Función de resize automático
            def ajustar_imagen():
                try:
                    ad = ads[index["i"]]
                    img_data = requests.get(ad["image"], timeout=5).content
                    img = Image.open(BytesIO(img_data))

                    w = carrusel_frame.winfo_width()
                    h = carrusel_frame.winfo_height()

                    img = img.resize((w, h))
                    img_tk = ImageTk.PhotoImage(img)

                    lbl_img.config(image=img_tk)
                    lbl_img.image = img_tk

                    current_ad["url"] = ad["cta_url"]

                except Exception as e:
                    print("Error cargando imagen carrusel:", e)

            # Función de cambio de slide
            def mostrar_slide():
                ajustar_imagen()

                # siguiente slide cada 4 segundos
                index["i"] = (index["i"] + 1) % len(ads)
                win.after(4000, mostrar_slide)

            # Click en imagen
            def abrir_url(event):
                if current_ad["url"]:
                    import webbrowser
                    webbrowser.open(current_ad["url"])

            lbl_img.bind("<Button-1>", abrir_url)
  
            # Redimensionar al cambiar tamaño del frame
            carrusel_frame.bind("<Configure>", lambda e: ajustar_imagen())

            # Iniciar carrusel
            mostrar_slide()

        except Exception as e:
            print("Error cargando carrusel popup:", e)

    # Ejecutar carrusel
    cargar_carrusel_ads_popup()

    # Bloquear ventana
    win.grab_set()



    # ============================================================
    # 🔹 BOTÓN: Obtener prueba gratis (SIMPLE + ESTABLE)
    # ============================================================
    def obtener_prueba_gratis_desde_planes():
        email = simpledialog.askstring(
            "Prueba gratis",
            "Escribe tu correo para activar los 10 créditos de prueba:",
            parent=status_frame
        )
        if not email:
            return

        try:
            r = requests.post(
                STRIPE_SERVER_BASE.rstrip("/") + "/license/free",

                json={"email": email},
                timeout=10
            )
            data = r.json()

            if r.status_code == 200 and data.get("ok"):
                lg = data.get("license")
                if lg:
                    with open(LICENSE_FILE, "w", encoding="utf-8") as f:
                        json.dump(lg, f, indent=2)

                messagebox.showinfo("Prueba activada", "Tu prueba gratis ha sido activada.")
                refresh_status_ui()
            else:
                messagebox.showerror("Error", data.get("error", "No se pudo activar la prueba."))

        except Exception as e:
            messagebox.showerror("Error", f"No se pudo conectar al servidor:\n{e}")


    # BOTÓN: usar la MISMA función global obtener_prueba_gratis()
    #btn_free_trial = tk.Button(
    #	status_frame,
    #	text="🎁 Obtener prueba gratis (10 créditos)",
    #	bg="#6A5ACD",
    #	fg="white",
    #	bd=0,
    #	padx=8,
    #	pady=8,
    #	cursor="hand2",
    #	command=obtener_prueba_gratis   # 👈 MISMA FUNCIÓN DE LA UI PRINCIPAL
    #)
    #btn_free_trial.pack(fill="x", pady=(4,12))



    # ============================================================
    # Barra de progreso
    # ============================================================
    progress_container = tk.Frame(status_frame, bg=BG_CARD)
    progress_container.pack(fill="x", pady=(8,12))

    progress = ttk.Progressbar(
        progress_container,
        orient="horizontal",
        mode="determinate",
        maximum=100,
        style="TProgressbar"
    )
    progress.pack(fill="x")

    lbl_renew = tk.Label(status_frame, text="Renueva el: —", font=("Arial", 9), bg=BG_CARD, fg="#999")
    lbl_renew.pack(anchor="w", pady=(8,12))


    # ============================================================
    # Botones de facturación
    # ============================================================
    def open_portal_for_current():
        licinfo = fetch_remote_license_info()
        if licinfo.get("valid") and licinfo.get("license"):
            lic = licinfo["license"]
            cust = lic.get("stripe_customer_id")
            if not cust:
                messagebox.showinfo("Portal", "No se encontró customer_id para abrir el portal.")
                return
            
            try:
                r = requests.post(
                    STRIPE_SERVER_BASE.rstrip("/") + "/portal-session",
                    json={"customer_id": cust},
                    timeout=10
                )
                if r.status_code == 200:
                    url = r.json().get("url")
                    if url:
                        webbrowser.open(url)
                        return
                messagebox.showerror("Error", f"No se pudo abrir el portal: {r.text}")
            except:
                messagebox.showerror("Error", "Error de conexión al crear portal.")
        else:
            messagebox.showinfo("Portal", "No tienes un plan activo o la licencia no es válida.")


    portal_btn = tk.Button(
        status_frame,
        text="Abrir panel de facturación",
        command=open_portal_for_current,
        bg="#444444",
        fg=FG_LIGHT,
        bd=0,
        padx=8,
        pady=6,
        cursor="hand2"
    )
    portal_btn.pack(fill="x", pady=(6,8))


    btn_upgrade = tk.Button(
        status_frame,
        text="⚡ Subir a PRO",
        bg=ACCENT_PRO,
        fg="#fff",
        bd=0,
        padx=8,
        pady=10,
        command=cta_pro_month,
        cursor="hand2"
    )
    btn_upgrade.pack(fill="x", pady=(6,8))


    btn_agency = tk.Button(
        status_frame,
        text="🔥 Modo Agencia",
        bg=ACCENT_AGENCY,
        fg="#fff",
        bd=0,
        padx=8,
        pady=10,
        command=cta_agency_month,
        cursor="hand2"
    )
    btn_agency.pack(fill="x", pady=(6,8))

    


    # ---------- ACTUALIZACIÓN AUTOMÁTICA DEL PANEL ----------
    def refresh_status_ui():
        licinfo = fetch_remote_license_info()
        usage = load_usage()  # fallback local usage (no authoritative source)
        
        if licinfo.get("valid") and licinfo.get("license"):
            lic = licinfo["license"]
            plan = lic.get("plan", "starter")
            plan_key = plan.lower().split("_")[0]

            # Preferir los valores que vengan del servidor (opción A)
            try:
                credits_total = int(lic.get("credits")) if lic.get("credits") is not None else PLAN_CREDITS.get(plan_key, 0)
            except Exception:
                credits_total = PLAN_CREDITS.get(plan_key, 0)

            # credits_left: si el servidor proporciona 'credits_left' la usamos; si no, asumimos credits_total
            try:
                if lic.get("credits_left") is not None:
                    credits_left = int(lic.get("credits_left"))
                else:
                    credits_left = credits_total
            except Exception:
                credits_left = credits_total

            # sincronizamos el fallback local con el valor del servidor para consistencia UX offline
            try:
                usage["credits_left"] = credits_left
                if not usage.get("month_start"):
                    usage["month_start"] = datetime.utcnow().isoformat()
                save_usage(usage)
            except Exception:
                pass

            # ===========================
            #     ACTUALIZACIÓN UI
            # ===========================

            # ----- PLAN -----
            lbl_plan_value.config(text=f"{plan_key.upper()}  •  {lic.get('status','-')}")

            # ----- ESTILOS EXTRAS PARA LA BARRA ROJA -----
            style.configure("Red.Horizontal.TProgressbar", troughcolor=BG_CARD, background="#FF3B30")

            # ===========================================================
            #             🔥 ALERTAS ESPECIALES PARA PLAN FREE
            # ===========================================================
            if plan_key == "free":

                # 🟡 AVISO: SOLO QUEDA 1 CRÉDITO
                if credits_left == 1:
                    try:
                        if not hasattr(win, "_free_low_alert") or not win._free_low_alert:
                            messagebox.showinfo(
                                "Queda 1 crédito",
                                "Tu plan FREE está por agotarse.\n\n"
                                "Aún puedes generar 1 video más.\n\n"
                                "Para seguir creando sin límites, revisa nuestros planes Starter, PRO y Agencia."
                            )
                            win._free_low_alert = True
                    except:
                        pass

                # 🔴 AVISO: CRÉDITOS AGOTADOS (0)
                if credits_left <= 0:
                    try:
                        if not hasattr(win, "_free_zero_alert") or not win._free_zero_alert:
                            messagebox.showwarning(
                                "Créditos agotados",
                                "Has usado tus 10 créditos del plan FREE 🎁\n\n"
                                "Para continuar creando videos, puedes elegir uno de nuestros planes:\n\n"
                                "⭐ Starter\n🚀 PRO\n🏢 Agencia"
                            )
                            win._free_zero_alert = True
                    except:
                        pass

            # ===========================================================


            # ----- CREDITOS AGOTADOS (tus reglas anteriores) -----
            if credits_left <= 0:
                lbl_credits.config(text=f"Créditos: 0 / {credits_total}", fg="#FF4C4C")

                # Barra roja 100% usada
                progress.configure(style="Red.Horizontal.TProgressbar")
                progress['value'] = 100

                # Texto rojo en el plan
                lbl_plan_value.config(text=f"{plan_key.upper()} • CRÉDITOS AGOTADOS", fg="#FF4C4C")

                # ---- Popup automático (solo si no se ha mostrado antes) ----
                try:
                    if not hasattr(win, "_popup_shown") or not win._popup_shown:
                        popup_creditos_agotados(win)
                        win._popup_shown = True
                except Exception as e:
                    print("Error al mostrar popup:", e)

            else:
                # Créditos normales
                lbl_credits.config(text=f"Créditos: {credits_left} / {credits_total}", fg=FG_LIGHT)

                used = credits_total - credits_left if credits_total else 0
                pct = int((used / credits_total) * 100) if credits_total else 0
                progress['value'] = pct

                # Restaurar estilo normal
                progress.configure(style="TProgressbar")
                lbl_plan_value.config(fg=FG_LIGHT)

            # ----- FECHA DE RENOVACIÓN -----
            expires_text = "—"
            if lic.get("expires_at"):
                try:
                    expires_dt = datetime.fromisoformat(lic.get("expires_at"))
                    expires_text = expires_dt.strftime("%d %b %Y")
                except Exception:
                    expires_text = lic.get("expires_at")
            lbl_renew.config(text=f"Renueva el: {expires_text}")

            # ----- SUGERENCIA DE UPGRADE -----
            if credits_total and credits_left <= max(1, int(credits_total * 0.15)) and credits_left > 0:
                msg = "Parece que estás publicando mucho 👀\n¿Quieres desbloquear batch ilimitado y 4K?"
                if messagebox.askyesno("Créditos bajos", msg):
                    cta_pro_month()

        else:
            # Sin licencia o invalid
            lbl_plan_value.config(text="— No activado —", fg=FG_LIGHT)
            lbl_credits.config(text=f"Créditos: {usage.get('credits_left', 0)} / —", fg=FG_LIGHT)
            progress['value'] = 0
            lbl_renew.config(text="Renueva el: —")

        # Programar siguiente refresco si la ventana sigue abierta (cada 30s)
        try:
            if getattr(win, "_is_pricing_window", False):
                win.after(30000, refresh_status_ui)
        except Exception:
            pass

    # refresh inicial
    refresh_status_ui()

    # Botón Actualizar
    refresh_btn = tk.Button(status_frame, text="Actualizar estado", command=refresh_status_ui, bg="#444444", fg=FG_LIGHT, bd=0, cursor="hand2")
    refresh_btn.pack(fill="x", pady=(6,4))

    footer = tk.Frame(win, bg=BG_DARK)
    footer.pack(fill="x", padx=20, pady=(10,12))
    tk.Label(footer, text="HAZ VIDEOS EN MINUTOS, NO EN HORAS.", font=("Arial", 9), bg=BG_DARK, fg="#999").pack(anchor="w")

    win.update_idletasks()
    w_width = win.winfo_reqwidth()
    w_height = win.winfo_reqheight()
    x = (win.winfo_screenwidth() // 2) - (w_width // 2)
    y = (win.winfo_screenheight() // 2) - (w_height // 2)
    win.geometry(f"{w_width}x{w_height}+{x}+{y}")
    win.minsize(980, 720)

# ---------- Helper: prompt email ----------
def prompt_email(parent=None):
        try:
            local = leer_licencia_local()
        except:
            local = None

        # 🔒 Usar SIEMPRE el email de la licencia
        if local and local.get("email"):
            return local.get("email")

        # ❌ Si por alguna razón no hay email, no continuar
        mostrar_toast(
            "⚠️ No se pudo obtener el email de la licencia.\n\n"
            "Inicia sesión nuevamente para continuar.",
            tipo="error",
            duracion=6000,
            bloqueante=True
        )
        return None

# ---------- Attach pricing button ----------
def attach_pricing_button(root):
    btn = tk.Button(
        root,
        text="Planes",
        bg=ACCENT_PRO,
        fg="#fff",
        bd=0,
        font=("Arial", 12, "bold"),   # ⬅ más grande el texto
        padx=20,                      # ⬅ más ancho
        pady=10,                      # ⬅ más alto
        command=lambda: open_pricing_window(root),
        cursor="hand2"
    )
    btn.place(relx=0.98, rely=0.98, anchor="se")

# ----------------------------
# END BLOCK
# ----------------------------

attach_pricing_button(root)
checkear_licencia_inicio()
# (la ventana de planes se abrirá con open_pricing_window(root) cuando el usuario presione el botón)

# ============================================================
#   🔥 FUNCIÓN CENTRAL PARA APLICAR LICENCIAS DESDE MODO DEV
# ============================================================

def aplicar_licencia_desde_dev(payload):
    """
    Toma payload del server (local-create o remote-create),
    actualiza license.json, fallback y la UI.
    """
    try:
        # Guardar el license.json del servidor
        ok = guardar_licencia_local_desde_server(payload)
        if not ok:
            messagebox.showerror("Error", "No se pudo guardar license.json")
            return

        # Sincronizar fallback local
        try:
            usage = load_usage()
            usage["credits_left"] = int(
                payload.get("credits_left") or
                payload.get("credits") or
                payload.get("license", {}).get("credits_left", 0)
            )
            if not usage.get("month_start"):
                usage["month_start"] = datetime.utcnow().isoformat()
            save_usage(usage)
        except:
            pass

        # Refrescar labels de la UI
        try:
            cargar_y_mostrar_licencia()
        except:
            pass

        messagebox.showinfo(
            "Licencia actualizada",
            "Se aplicó correctamente la licencia del modo oculto.\n"
            "La app ahora usa los nuevos créditos / plan."
        )

    except Exception as e:
        messagebox.showerror("Error DEV", f"Error aplicando licencia: {e}")


# ============================================================
#           🔥 MENÚ OCULTO DE DESARROLLADOR (DEV MODE)
# ============================================================

def open_dev_menu():
    dev = tk.Toplevel(root)
    dev.title("Developer Tools — Modo Oculto")
    dev.configure(bg="#1e1e1e")
    dev.geometry("420x540")
    dev.resizable(False, False)

    tk.Label(
        dev, 
        text="🔧 Developer Tools",
        fg="white", bg="#1e1e1e",
        font=("Arial", 16, "bold")
    ).pack(pady=(10,5))

    # -------------------------------
    # Funciones helper dentro del menú
    # -------------------------------

    def show_current_license():
        try:
            lic = leer_licencia_local()
        except:
            lic = None

        text.delete("1.0", tk.END)
        if lic:
            text.insert(tk.END, json.dumps(lic, indent=4, ensure_ascii=False))
        else:
            text.insert(tk.END, "No hay license.json local.")

    def wipe_license():
        try:
            os.remove(LICENSE_FILE)
        except:
            pass
        try:
            path2 = os.path.expanduser("~/.mi_app_license.json")
            if os.path.exists(path2):
                os.remove(path2)
        except:
            pass

        text.delete("1.0", tk.END)
        text.insert(tk.END, "Licencia local eliminada.\n\nReinicia la app o genera una nueva.")
        messagebox.showinfo("OK", "License.json borrada (modo DEV).")

    # -------------------------------
    # FUNCIONES DEV USANDO LA FUNCIÓN NUEVA
    # -------------------------------

    def dev_starter():
        ok, data = cta_local_update_generic("starter", 5)
        if ok:
            aplicar_licencia_desde_dev(data)
        show_current_license()

    def dev_pro():
        ok, data = cta_local_update_generic("pro", 50)
        if ok:
            aplicar_licencia_desde_dev(data)
        show_current_license()

    def dev_agency():
        ok, data = cta_local_update_generic("agency", 150)
        if ok:
            aplicar_licencia_desde_dev(data)
        show_current_license()

    # -------------------------------
    #  CAMBIO MANUAL DE CRÉDITOS
    # -------------------------------

    def assign_manual_credits():
        value = simpledialog.askinteger("Asignar créditos", "Cantidad de créditos:", parent=dev)
        if value is None:
            return

        try:
            lic = leer_licencia_local()
            if not lic:
                messagebox.showerror("Error", "No hay licencia local.")
                return

            lic["credits_left"] = value
            with open(LICENSE_FILE, "w", encoding="utf-8") as f:
                json.dump(lic, f, indent=2)

            save_usage({"credits_left": value, "month_start": datetime.utcnow().isoformat()})

            cargar_y_mostrar_licencia()
            show_current_license()
            messagebox.showinfo("OK", f"Créditos asignados: {value}")

        except Exception as e:
            messagebox.showerror("Error", str(e))

    # -------------------------------
    #  CAMBIO MANUAL DE PLAN
    # -------------------------------

    def assign_manual_plan():
        plan = simpledialog.askstring(
            "Cambiar plan",
            "Plan nuevo (free, starter, pro, agency):",
            parent=dev
        )
        if not plan:
            return

        try:
            lic = leer_licencia_local()
            lic["plan"] = plan
            with open(LICENSE_FILE, "w", encoding="utf-8") as f:
                json.dump(lic, f, indent=2)

            cargar_y_mostrar_licencia()
            show_current_license()
            messagebox.showinfo("OK", f"Plan actualizado a: {plan}")

        except Exception as e:
            messagebox.showerror("Error", str(e))

    # -------------------------------
    #  BOTONES DEL PANEL DEV
    # -------------------------------

    frame = tk.Frame(dev, bg="#1e1e1e")
    frame.pack(pady=10)

    tk.Button(frame, text="Starter (5 cr)", bg="#5a5", fg="white",
              width=20, command=dev_starter).pack(pady=4)

    tk.Button(frame, text="PRO (50 cr)", bg="#36a", fg="white",
              width=20, command=dev_pro).pack(pady=4)

    tk.Button(frame, text="Agency (150 cr)", bg="#a63", fg="white",
              width=20, command=dev_agency).pack(pady=4)

    tk.Button(frame, text="Asignar créditos manual", bg="#555", fg="white",
              width=20, command=assign_manual_credits).pack(pady=10)

    tk.Button(frame, text="Cambiar plan manual", bg="#555", fg="white",
              width=20, command=assign_manual_plan).pack(pady=4)

    tk.Button(frame, text="Eliminar licencia local", bg="#800", fg="white",
              width=20, command=wipe_license).pack(pady=10)

    tk.Label(dev, text="Licencia actual:", fg="white", bg="#1e1e1e").pack()

    text = tk.Text(dev, height=14, bg="#111", fg="#0f0", insertbackground="white")
    text.pack(fill="both", padx=10, pady=5)

    show_current_license()

    dev.grab_set()


# ============================================================
#             HOTKEY PARA ABRIR EL MENÚ DEV (OCULTO)
# ============================================================

def _dev_hotkey(event):
    open_dev_menu()

def send_event(event, extra=None):
        payload = {
            "event": event,
            "version": APP_VERSION,
            "email": email_global,
            "license": license_key_global,
            "extra": extra or {}
        }
        try:
            requests.post(f"{SERVER_URL}/telemetry", json=payload, timeout=2)
        except:
            pass

def marcar_app_healthy():
        write_version_state("healthy")
        send_event("app_healthy", {"version": APP_VERSION})

root.bind("<Control-Shift-D>", _dev_hotkey)

root.after(300, lanzar_login_si_necesario)

# ⬇️ AQUÍ VA (JUSTO AQUÍ)
root.after(1500, marcar_app_healthy)

root.mainloop()
write_version_state("healthy")


