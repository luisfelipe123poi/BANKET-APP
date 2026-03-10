# server_stripe.py
# Servidor Flask para integrar Stripe Checkout + Webhooks + Licencias (SQLite)
# Ahora con gestión centralizada de créditos y endpoint /usage para decrementar créditos.
# Requisitos: flask, stripe, python-dotenv
# CONFIGURACIÓN: establecer STRIPE_SECRET_KEY, STRIPE_WEBHOOK_SECRET, PUBLIC_DOMAIN, PRICE_ID_* en variables de entorno.

import os
import json
import uuid
import sqlite3
import stripe
from datetime import datetime, timedelta
from flask import Flask, request, jsonify, abort
from urllib.parse import urljoin
import jwt
import time
from flask import redirect
from flask import Flask, request, jsonify, render_template
from flask import Flask, render_template
import sqlite3
import mercadopago
from flask import Flask
from flask_cors import CORS



import os
import sib_api_v3_sdk
from sib_api_v3_sdk import Configuration, ApiClient, TransactionalEmailsApi
from sib_api_v3_sdk.models import SendSmtpEmail

import os
import stripe

print("🔍 AZURE KEY:", bool(os.getenv("AZURE_SPEECH_KEY")))
print("🔍 AZURE REGION:", os.getenv("AZURE_SPEECH_REGION"))


import os

DATA_DIR = "/var/data"

if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)

app = Flask(__name__, template_folder="templates")

# CONFIGURACIÓN MAESTRA DE CORS (Una sola llamada)
# Esto permite que cualquier origen acceda a tus rutas /api/
CORS(app, resources={r"/*": {"origins": "*"}})


STRIPE_SECRET_KEY = os.environ.get("STRIPE_SECRET_KEY")

if not STRIPE_SECRET_KEY:
    raise RuntimeError("❌ STRIPE_SECRET_KEY NO está definida en Render")

stripe.api_key = STRIPE_SECRET_KEY

print("✅ Stripe key cargada:", STRIPE_SECRET_KEY[:12], "...OK")

# ======================
# 🔐 BREVO CONFIG
# ======================

BREVO_API_KEY = os.getenv("BREVO_API_KEY")

BREVO_SENDER_EMAIL = "turboclipsapp@gmail.com"
BREVO_SENDER_NAME = "TurboClips"

# Configuración Brevo
configuration = Configuration()
configuration.api_key["api-key"] = BREVO_API_KEY

# Cliente Brevo
brevo_client = ApiClient(configuration)
brevo_email_api = TransactionalEmailsApi(brevo_client)

DB_PATH = os.path.join(DATA_DIR, "database.db")

SECRET_KEY = "2dh3921-92jk1h82-92jh1929-1k28j192"



# Carga de .env si existe
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

STRIPE_SECRET_KEY = os.environ.get("STRIPE_SECRET_KEY", None)
STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET", None)
PUBLIC_DOMAIN = os.environ.get("PUBLIC_DOMAIN", "https://stripe-backend-r14f.onrender.com")

if not STRIPE_SECRET_KEY:
    raise RuntimeError("Necesitas establecer STRIPE_SECRET_KEY en tus variables de entorno.")



# Default price IDs (puedes setear en env)
PRICE_ID_PRO = ("price_1ScJlCGznS3gtqcWGFG56OBX")
PRICE_ID_STARTER = ("price_1ScJkpGznS3gtqcWsGC3ELYs")
PRICE_ID_AGENCY = ("price_1ScJlhGznS3gtqcWheD5Qk15")
# Precios anuales
PRICE_ID_STARTER_ANNUAL = "price_xxxxx_starter_year"
PRICE_ID_PRO_ANNUAL = "price_xxxxx_pro_year"
PRICE_ID_AGENCY_ANNUAL = "price_xxxxx_agency_year"
# Mapping default credits by plan key (fallback)
PLAN_DEFAULT_CREDITS = {
    "starter": 100,
    "pro": 300,
    "agency": 1200
}

EVENTS_VALIDOS = {
    "generation_start",
    "generation_success",
    "generation_error"
}

# ======================
# 💳 MERCADOPAGO CONFIG
# ======================

MP_ACCESS_TOKEN = os.getenv("MP_ACCESS_TOKEN")
MP_PUBLIC_KEY = os.getenv("MP_PUBLIC_KEY")

if not MP_ACCESS_TOKEN:
    print("⚠️ MP_ACCESS_TOKEN no configurado")

mp_sdk = mercadopago.SDK(MP_ACCESS_TOKEN)

MP_PLANS = {
    "starter": os.getenv("MP_PLAN_STARTER"),
    "pro": os.getenv("MP_PLAN_PRO"),
    "agency": os.getenv("MP_PLAN_AGENCY"),
}







# ------------------------------------------------------------
# RUTA PARA SALUD DE RENDER — EVITA SPAM DE GET /
# ------------------------------------------------------------
@app.route("/", methods=["GET"])
def home():
    return jsonify({"ok": True, "service": "stripe-backend-running"}), 200

# ======================================
# SISTEMA DE TOKENS PARA EMAIL
# ======================================
tokens_db = {}

def generar_token():
    return uuid.uuid4().hex


def sign_token(email):
    exp = int(time.time()) + 60  # 1 min
    token = jwt.encode({"email": email, "exp": exp}, SECRET_KEY, algorithm="HS256")
    return token, exp


def enviar_correo_verificacion(email, token):
    link = f"https://stripe-backend-r14f.onrender.com/auth/verify?token={token}"



    html = f"""
<html>
  <body style="font-family: Arial; line-height: 1.6;">
    <h2>Confirma tu correo para continuar</h2>
    <p>Haz clic en el siguiente botón para verificar tu email:</p>

    <p>
      <a href="{link}"
         target="_blank"
         style="display:inline-block;
                padding:14px 22px;
                background-color:#4CAF50;
                color:white;
                text-decoration:none;
                font-size:16px;
                border-radius:8px;">
        Confirmar Email
      </a>
    </p>

    <p>Si no solicitaste esto, puedes ignorar este mensaje.</p>

    <p style="margin-top:20px; font-size:12px; color:#666;">
      Si el botón no funciona, copia y pega este enlace en tu navegador:<br>
      {link}
    </p>
  </body>
</html>
"""


    email_content = SendSmtpEmail(
        to=[{"email": email}],
        html_content=html,
        subject="Confirma tu correo",
        sender={"name": BREVO_SENDER_NAME, "email": BREVO_SENDER_EMAIL},
    )

    try:
        response = brevo_email_api.send_transac_email(email_content)
        print("📨 Email enviado:", response)
    except Exception as e:
        print("❌ Error enviando correo con Brevo:")
        print(e)


# -------------------------
# DATABASE HELPERS
# -------------------------
def get_db_connection():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

@app.route("/_debug/metrics", methods=["GET"])
def debug_metrics():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT 
           DATE(created_at) as dia,
           COUNT(CASE WHEN event = 'generation_start' THEN 1 END) as total,
           COUNT(CASE WHEN event = 'generation_success' THEN 1 END) as exitos,
           COUNT(CASE WHEN event = 'generation_error' THEN 1 END) as errores

        FROM metrics
        GROUP BY dia
        ORDER BY dia DESC
    """)
    rows = cur.fetchall()
    conn.close()

    return jsonify([dict(r) for r in rows])

@app.route("/dashboard/metrics")
def dashboard_metrics():
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT 
           DATE(created_at) as dia,
           COUNT(CASE WHEN event = 'generation_start' THEN 1 END) as total,
           COUNT(CASE WHEN event = 'generation_success' THEN 1 END) as exitos,
           COUNT(CASE WHEN event = 'generation_error' THEN 1 END) as errores,
           COUNT(DISTINCT email) as usuarios
        FROM metrics
        GROUP BY dia
        ORDER BY dia DESC


    """)

    rows = cur.fetchall()
    conn.close()

    return render_template("dashboard_metrics.html", data=rows)

@app.route("/health", methods=["GET"])
def health():
    return {"ok": True, "status": "online"}, 200


    

@app.route("/metrics/event", methods=["POST"])
def metrics_event():
    data = request.get_json() or {}

    email = data.get("email")
    event = data.get("event")

    if not email or not event:
        return jsonify({"error": "email_and_event_required"}), 400

    if event not in EVENTS_VALIDOS:
        return jsonify({"error": "invalid_event"}), 400

    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute(
        "INSERT INTO metrics (email, event, created_at) VALUES (?, ?, datetime('now'))",
        (email, event)
    )

    conn.commit()
    conn.close()

    return jsonify({"ok": True})

# --- AUTOFIX: borrar BD corrupta si falta alguna columna ---
def ensure_db_schema():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # Obtener columnas actuales para no duplicar
    cur.execute("PRAGMA table_info(licenses)")
    cols = [c[1] for c in cur.fetchall()]

    # --- TUS LOGICAS ORIGINALES (NO TOCAR) ---
    if "credits_left" not in cols:
        print("🛠️ Agregando columna credits_left")
        cur.execute("ALTER TABLE licenses ADD COLUMN credits_left INTEGER DEFAULT 0")

    if "expires_at" not in cols:
        print("🛠️ Agregando columna expires_at")
        cur.execute("ALTER TABLE licenses ADD COLUMN expires_at TEXT")

    # --- NUEVAS MÉTRICAS TIKTOK (AGREGADAS SIN ELIMINAR NADA) ---
    
    # 1. Columna de vinculación (El puente con TikTok)
    if "tiktok_id" not in cols:
        print("🛠️ Agregando columna tiktok_id")
        cur.execute("ALTER TABLE licenses ADD COLUMN tiktok_id TEXT")

    # 2. Métricas de interacción y rendimiento
    metricas_nuevas = [
        ("views", "INTEGER DEFAULT 0"),
        ("likes", "INTEGER DEFAULT 0"),
        ("comentarios", "INTEGER DEFAULT 0"),
        ("compartidos", "INTEGER DEFAULT 0"),
        ("guardados", "INTEGER DEFAULT 0"),
        ("seguidores", "INTEGER DEFAULT 0"),
        ("duracion", "REAL DEFAULT 0"),
        ("retencion", "REAL DEFAULT 0"),
        ("completado", "REAL DEFAULT 0"),
        ("t_avg", "REAL DEFAULT 0"),
        ("watchtime_total", "REAL DEFAULT 0")
    ]

    for nombre, tipo in metricas_nuevas:
        if nombre not in cols:
            print(f"🛠️ Agregando métrica: {nombre}")
            cur.execute(f"ALTER TABLE licenses ADD COLUMN {nombre} {tipo}")

    conn.commit()
    conn.close()
    print("✅ Base de datos verificada y actualizada correctamente.")    
    
    

def save_license(
    license_key,
    email,
    plan="free",
    credits=0,
    credits_left=None,
    stripe_customer_id=None,
    stripe_subscription_id=None,
    status="active",
    expires_at=None,
    metadata=None
):
    """
    Guarda una licencia nueva en la base de datos.
    Si ya existe el email o license_key, la sobrescribe automáticamente.
    """

    # Si no viene credits_left → iniciar igual a credits
    if credits_left is None:
        credits_left = credits

    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
        INSERT OR REPLACE INTO licenses (
            license_key,
            email,
            plan,
            credits,
            credits_left,
            status,
            stripe_customer_id,
            stripe_subscription_id,
            expires_at,
            metadata
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)

    """, (
        license_key,
        email,
        plan,
        credits,
        credits_left if credits_left is not None else credits,
        status,
        stripe_customer_id,
        stripe_subscription_id,
        expires_at,
        json.dumps(metadata or {})
    ))


    conn.commit()
    conn.close()


def init_db():
    conn = get_db_connection()
    cur = conn.cursor()
    ensure_db_schema()

    # -----------------------------
    # Tabla principal de licencias
    # -----------------------------
    cur.execute("""
        CREATE TABLE IF NOT EXISTS licenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            license_key TEXT UNIQUE,
            stripe_customer_id TEXT,
            stripe_subscription_id TEXT,
            email TEXT,
            plan TEXT,
            status TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            expires_at TEXT,
            metadata TEXT,
            credits INTEGER DEFAULT 0,
            credits_left INTEGER DEFAULT 0

        );
    """)

    # -----------------------------
    # Tabla de métricas
    # -----------------------------
    cur.execute("""
        CREATE TABLE IF NOT EXISTS metrics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT,
            event TEXT,
            error TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)

    # -----------------------------------------
    # Tabla de tokens para verificación de email
    # -----------------------------------------
    cur.execute("""
        CREATE TABLE IF NOT EXISTS email_verification_tokens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT,
            token TEXT UNIQUE,
            used INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)


    conn.commit()
    conn.close()


# Inicializar DB al arrancar
init_db()





@app.route("/api/update_metrics", methods=["POST"])
def update_metrics():
    data = request.json
    tiktok_id = data.get('tiktok_id')
    
    if not tiktok_id:
        return jsonify({"ok": False, "error": "No TikTok ID"}), 400

    # Construimos la consulta dinámicamente según lo que mande la extensión
    campos = []
    valores = []
    for clave, valor in data.items():
        if clave != 'tiktok_id':
            campos.append(f"{clave} = ?")
            valores.append(valor)
    
    if not campos:
        return jsonify({"ok": True, "message": "Nada que actualizar"})

    valores.append(tiktok_id)
    query = f"UPDATE licenses SET {', '.join(campos)} WHERE tiktok_id = ?"

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(query, valores)
    conn.commit()
    conn.close()
    
    return jsonify({"ok": True})

    


# -------------------------
# UTILITIES
# -------------------------
def gen_license():
    return "LIC-" + uuid.uuid4().hex.upper()

def now_iso():
    return datetime.utcnow().isoformat

def add_credits_to_license(email, extra_credits):
    conn = get_db_connection()
    cur = conn.cursor()

    # Obtener licencia más reciente
    cur.execute(
        "SELECT license_key, credits, credits_left FROM licenses WHERE email = ? ORDER BY created_at DESC LIMIT 1",
        (email,)
    )
    lic = cur.fetchone()

    if not lic:
        conn.close()
        return False, "Licencia no encontrada"

    new_credits = (lic["credits"] or 0) + extra_credits
    new_credits_left = (lic["credits_left"] or 0) + extra_credits

    cur.execute(
        """
        UPDATE licenses
        SET credits = ?, credits_left = ?, updated_at = CURRENT_TIMESTAMP
        WHERE license_key = ?
        """,
        (new_credits, new_credits_left, lic["license_key"])
    )

    conn.commit()
    conn.close()
    return True, new_credits_left
    



def update_license_by_subscription(sub_id, **kwargs):
    if not kwargs:
        return
    conn = get_db_connection()
    cur = conn.cursor()
    sets = ", ".join([f"{k} = ?" for k in kwargs.keys()])
    vals = list(kwargs.values())
    vals.append(sub_id)
    cur.execute(f"UPDATE licenses SET {sets} WHERE stripe_subscription_id = ?", vals)
    conn.commit()
    conn.close()

def get_license_by_key(key):
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("SELECT * FROM licenses WHERE license_key = ?", (key,))
    row = cur.fetchone()
    conn.close()

    if not row:
        return None

    lic = dict(row)

    # Cargar metadata
    try:
        lic["metadata"] = json.loads(lic.get("metadata") or "{}")
    except Exception:
        lic["metadata"] = lic.get("metadata")

    return lic

def get_license_by_subscription(sub_id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM licenses WHERE stripe_subscription_id = ?", (sub_id,))
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None

def get_license_by_customer(customer_id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM licenses WHERE stripe_customer_id = ?", (customer_id,))
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None

def set_credits_for_license(license_key, credits_total):
    conn = get_db_connection()
    cur = conn.cursor()
    # If license exists set credits and credits_left only if not set
    cur.execute("UPDATE licenses SET credits = ?, credits_left = ? WHERE license_key = ?", (credits_total, credits_total, license_key))
    conn.commit()
    conn.close()

def adjust_credits_left(license_key, delta):
    """Atomically adjust credits_left by delta (negative to consume). Returns new credits_left or None on error."""
    conn = get_db_connection()
    cur = conn.cursor()
    # fetch current
    cur.execute("SELECT credits_left FROM licenses WHERE license_key = ?", (license_key,))
    row = cur.fetchone()
    if not row:
        conn.close()
        return None
    current = row["credits_left"] or 0
    new = max(0, current + delta)
    cur.execute("UPDATE licenses SET credits_left = ? WHERE license_key = ?", (new, license_key))
    conn.commit()
    conn.close()
    return new

@app.route("/auth/request_verification", methods=["POST"])
def request_verification():
    data = request.json
    email = (data.get("email") or "").strip().lower()

    if not email:
        return jsonify({"ok": False, "error": "missing_email"})

    # 🔥 SI YA EXISTE LICENCIA → NO reenviar correo, NO insertar token
    existing = get_license_by_email(email)
    if existing:
        return jsonify({
            "ok": True,
            "already_verified": True,
            "message": "Este correo ya fue verificado.",
            "license": existing
        })

    # Enviar token SOLO si NO existe licencia
    token = generar_token()

    conn = get_db_connection()
    cur = conn.cursor()

    # 🔥 SOLUCIÓN: insertar o actualizar token si el email ya existe
    cur.execute("""
        INSERT INTO email_verification_tokens (email, token, used, created_at)
        VALUES (?, ?, 0, CURRENT_TIMESTAMP)
        ON CONFLICT(token) DO UPDATE SET  
            token = excluded.token,
            used = 0,
            created_at = CURRENT_TIMESTAMP;
    """, (email, token))

    conn.commit()
    conn.close()

    enviar_correo_verificacion(email, token)

    return jsonify({
        "ok": True,
        "message": "Correo de verificación enviado."
    })

def create_free_license_internal(email):
    """
    Crea una licencia FREE cuando un usuario verifica su correo.
    Si ya existe una licencia (free o de pago), NO crea otra.
    Solo devuelve la licencia existente.
    """
    email = email.strip().lower()

    # 🔍 1. Revisar si ya existe una licencia previa por email
    existing = get_license_by_email(email)
    if existing:
        # → Si ya existe, NO crear una nueva
        print(f"⚠️ Licencia ya existente encontrada para {email}: {existing['license_key']}")
        return {
            "ok": True,
            "license_key": existing["license_key"],
            "email": existing["email"],
            "plan": existing["plan"],
            "credits": existing.get("credits_left", existing.get("credits", 0))
        }

    # 🆕 2. Si no existe licencia, crear una nueva FREE
    license_key = gen_license()
    credits = 10  # créditos del plan free

    save_license(
        license_key=license_key,
        stripe_customer_id=None,
        stripe_subscription_id=None,
        email=email,
        plan="free",
        status="active",
        expires_at=None,
        metadata={"source": "email_verification"},
        credits=credits
    )

    print(f"🎁 Licencia FREE creada para {email}: {license_key}")

    return {
        "ok": True,
        "license_key": license_key,
        "email": email,
        "plan": "free",
        "credits": credits
    }

@app.route("/auth/request_code", methods=["POST"])
def request_code():
    data = request.json
    email = data.get("email")

    if not email:
        return jsonify({"ok": False, "error": "Email requerido"}), 400

    print(f"🟢 Código enviado (simulado) a {email}")

    return jsonify({"ok": True, "msg": "Código enviado"})

@app.route("/mp/create_preference", methods=["POST"])
def mp_create_preference():
    data = request.json or {}

    email = data.get("email")
    plan = data.get("plan")  # starter | pro | agency

    if not email or plan not in MP_PLANS:
        return jsonify({"error": "invalid_data"}), 400

    plan_id = MP_PLANS.get(plan)

    preference_data = {
        "payer": {
            "email": email
        },
        "items": [
            {
                "title": f"TurboClips Plan {plan.capitalize()}",
                "quantity": 1,
                "unit_price": 1  # ⚠️ NO importa si usas plan_id
            }
        ],
        "subscription_plan_id": plan_id,
        "back_urls": {
            "success": f"{PUBLIC_DOMAIN}/success",
            "failure": f"{PUBLIC_DOMAIN}/cancel"
        },
        "auto_return": "approved",

        "notification_url": f"{PUBLIC_DOMAIN}/mp/webhook"
    }

    preference = mp_sdk.preference().create(preference_data)

    return jsonify({
        "init_point": preference["response"]["init_point"],
        "id": preference["response"]["id"]
    })

@app.route("/mp/webhook", methods=["POST"])
def mp_webhook():
    data = request.json

    if not data:
        return "ok", 200

    topic = data.get("type") or data.get("topic")

    if topic not in ("payment", "subscription"):
        return "ok", 200

    resource_id = data.get("data", {}).get("id")

    try:
        payment = mp_sdk.payment().get(resource_id)
        payment_data = payment["response"]

        if payment_data.get("status") != "approved":
            return "ok", 200

        email = payment_data["payer"]["email"]
        plan = payment_data["description"].lower()

        # MAPEAR plan
        if "starter" in plan:
            plan_key = "starter"
            credits = 100
        elif "pro" in plan:
            plan_key = "pro"
            credits = 300
        elif "agency" in plan:
            plan_key = "agency"
            credits = 1200
        else:
            return "ok", 200

        license_key = gen_license()

        save_license(
            license_key=license_key,
            email=email,
            plan=plan_key,
            credits=credits,
            status="active",
            metadata={"source": "mercadopago"}
        )

        print(f"✅ Licencia creada vía MercadoPago: {email} | {plan_key}")

    except Exception as e:
        print("❌ Error MP webhook:", e)

    return "ok", 200


@app.route("/license/info", methods=["GET"])
def license_info():
    key = request.args.get("key")

    if not key:
        return jsonify({"ok": False, "error": "license key requerido"}), 400

    lic = get_license_by_key(key)

    if not lic:
        return jsonify({"ok": False, "error": "Licencia no encontrada"}), 404

    return jsonify({
        "ok": True,
        "data": lic
    })
@app.route("/license/use-credit", methods=["POST"])
def use_credit():
    data = request.json
    key = data.get("license_key")

    if not key:
        return jsonify({"ok": False, "error": "license_key requerido"}), 400

    lic = get_license_by_key(key)
    if not lic:
        return jsonify({"ok": False, "error": "Licencia no encontrada"}), 404

    if lic["credits_left"] <= 0:
        return jsonify({"ok": False, "error": "Sin créditos disponibles"}), 403

    # Descontar crédito
    conn = get_db_connection()

    cur = conn.cursor()
    cur.execute(
        "UPDATE licenses SET credits_left = credits_left - 1 WHERE license_key = ?",
        (key,)
    )
    conn.commit()
    conn.close()

    return jsonify({
        "ok": True,
        "credits_left": lic["credits_left"] - 1
    })

@app.route("/mp/success")
def mp_success():
    return redirect("/success")

@app.route("/mp/failure")
def mp_failure():
    return redirect("/cancel")


@app.route("/api/test_inject/<video_id>")
def test_inject(video_id):
    # Valores por defecto si no se pasan por URL
    v = request.args.get('v', 12500)
    l = request.args.get('l', 850)
    r = request.args.get('r', 65)
    
    # EL CORREO MAESTRO PARA LA PRUEBA
    target_email = "luisfe507@gmail.com"

    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Intentamos actualizar por si ya existe
        cur.execute("""
            UPDATE licenses 
            SET views = ?, likes = ?, retencion = ? 
            WHERE license_key = ? AND email = ?
        """, (v, l, r, video_id, target_email))
        
        # Si no actualizó nada (rowcount == 0), es porque el video no existe para ese correo, lo insertamos
        if cur.rowcount == 0:
            cur.execute("""
                INSERT INTO licenses (license_key, email, plan, status, views, likes, retencion)
                VALUES (?, ?, 'pro', 'active', ?, ?, ?)
            """, (video_id, target_email, v, l, r))
        
        conn.commit()
        conn.close()
        
        return f"✅ Éxito: Video {video_id} vinculado a {target_email} con {v} views."
    except Exception as e:
        return f"❌ Error: {str(e)}"

@app.route("/api/license/info", methods=["GET"])
def get_license_info_dashboard():
    video_id = request.args.get("key", "").strip()
    user_email = request.args.get("email", "").strip().lower()

    if not video_id or not user_email:
        return jsonify({"ok": False, "error": "Faltan parámetros"}), 400

    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    
    # Buscamos el video que pertenezca a este correo
    cur.execute("SELECT * FROM licenses WHERE email = ? AND license_key = ?", (user_email, video_id))
    row = cur.fetchone()
    conn.close()
    
    if not row:
        return jsonify({
            "ok": False, 
            "error": f"El video {video_id} no está registrado bajo el correo {user_email}"
        }), 404
    
    return jsonify({"ok": True, "license": dict(row)})

@app.route("/api/debug_db")
def debug_db():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT email, license_key FROM licenses")
    rows = cur.fetchall()
    conn.close()
    return jsonify([dict(ix) for ix in rows])        

@app.route("/create-checkout-session", methods=["GET"])
def create_checkout():
    email = request.args.get("email")
    price_id = request.args.get("priceId")

    if not email or not price_id:
        return jsonify({"ok": False, "error": "email y priceId son requeridos"}), 400

    try:
        session = stripe.checkout.Session.create(
            customer_email=email,
            line_items=[{"price": price_id, "quantity": 1}],
            mode="subscription",
            success_url="https://stripe-backend-r14f.onrender.com/success?session_id={CHECKOUT_SESSION_ID}",
            cancel_url="https://stripe-backend-r14f.onrender.com/cancel",
        )
        return redirect(session.url, code=302)

    except Exception as e:
        print("❌ Error creando checkout:", e)
        return jsonify({"ok": False, "error": str(e)}), 500

@app.route("/create-customer", methods=["POST"])
def create_customer():
    data = request.json or {}
    license_key = data.get("license_key")
    email = data.get("email")

    if not license_key or not email:
        return jsonify({"error": "missing_data"}), 400

    lic = get_license_by_key(license_key)
    if not lic:
        return jsonify({"error": "license_not_found"}), 404

    if lic.get("stripe_customer_id"):
        return jsonify({"customer_id": lic["stripe_customer_id"]})

    customer = stripe.Customer.create(
        email=email,
        metadata={"license_key": license_key}
    )

    update_license_by_key(
        license_key,
        stripe_customer_id=customer.id
    )

    return jsonify({"customer_id": customer.id})


@app.route("/auth/verify", methods=["GET"])
def verify():
    token = request.args.get("token")

    # Buscar token
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT email, used FROM email_verification_tokens WHERE token = ?", (token,))
    row = cur.fetchone()
    conn.close()

    if not row:
        return jsonify({"ok": False, "error": "token_not_found"})

    email = row["email"].strip().lower()
    used = row["used"]

    # Si ya fue usado antes → correo ya verificado
    if used:
        existing = get_license_by_email(email)

        # Convertir Row → dict
        if existing and not isinstance(existing, dict):
            existing = dict(existing)

        return jsonify({
            "ok": True,
            "already_verified": True,
            "message": "Este correo ya fue verificado anteriormente.",
            "email": email,
            "license": existing
        })

    # Marcar token como usado
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("UPDATE email_verification_tokens SET used = 1 WHERE token = ?", (token,))
    conn.commit()
    conn.close()

    # Revisar si ya existe licencia
    existing = get_license_by_email(email)
    if existing:
        if not isinstance(existing, dict):
            existing = dict(existing)

        return jsonify({
            "ok": True,
            "message": "Correo verificado.",
            "email": email,
            "license": existing
        })

    # ---------------------------------------------------------
    # SI NO EXISTE LICENCIA → CREAR LICENCIA FREE CON 30 DÍAS
    # ---------------------------------------------------------
    from datetime import datetime, timedelta
    expires_at = (datetime.utcnow() + timedelta(days=30)).strftime("%Y-%m-%d")

    new_key = gen_license()
    save_license(
        license_key=new_key,
        email=email,
        plan="free",
        credits=10,
        credits_left=10,
        status="active",
        expires_at=expires_at   # ← AGREGADO
    )

    lic = get_license_by_email(email)
    if lic and not isinstance(lic, dict):
        lic = dict(lic)

    return f"""
    <html>
    <head>
        <meta charset="UTF-8">
        <title>Correo verificado</title>
        <style>
            body {{
                font-family: Arial, sans-serif;
                background-color: #0f0f0f;
                color: white;
                text-align: center;
                padding: 50px;
            }}
            .card {{
                background-color: #1c1c1c;
                padding: 30px;
                border-radius: 12px;
                display: inline-block;
                max-width: 500px;
                box-shadow: 0 0 20px rgba(255, 140, 66, 0.3);
            }}
            .title {{
                font-size: 28px;
                margin-bottom: 10px;
                color: #4CD964;
            }}
            .subtitle {{
                font-size: 18px;
                margin-bottom: 20px;
                color: #cccccc;
            }}
            .body-text {{
                font-size: 15px;
                margin-bottom: 30px;
                color: #aaaaaa;
                line-height: 1.6;
            }}
            .cta {{
                display: inline-block;
                background-color: #FF8C42;
                color: white;
                padding: 12px 25px;
                border-radius: 8px;
                font-size: 16px;
                text-decoration: none;
                transition: 0.2s;
            }}
            .cta:hover {{
                background-color: #ff7a1f;
            }}
        </style>
    </head>
    <body>
        <div class="card">
            <h1 class="title">🎉 ¡Correo verificado con éxito!</h1>
            <div class="subtitle">Tu licencia FREE ha sido activada.</div>
            <div class="body-text">
                Ya puedes comenzar a generar tus videos.<br><br>
                Hemos añadido <b>10 créditos gratuitos</b> a tu cuenta para que explores todas las funciones principales.
            </div>
            
        </div>
    </body>
    </html>
    """

    return html




@app.route("/auth/check_status")
def check_status():
    email = request.args.get("email")
    if not email:
        return jsonify({"ok": False, "error": "Email requerido"}), 400

    email = email.strip().lower()

    # Verificar si el email ya fue confirmado
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT used FROM email_verification_tokens WHERE email = ?", (email,))
    row = cur.fetchone()
    conn.close()

    verified = False
    if row and row["used"] == 1:
        verified = True

    # Buscar la licencia
    lic = get_license_by_email(email)

    return jsonify({
        "ok": True,
        "verified": verified,
        "email": email,
        "license": {
            "license_key": lic.get("license_key") if lic else None,
            "plan": lic.get("plan") if lic else None,
            "credits": lic.get("credits") if lic else None,
            "credits_left": lic.get("credits_left") if lic else None,
            "status": lic.get("status") if lic else None
        }
    })

import os
import azure.cognitiveservices.speech as speechsdk
import uuid

def generar_audio_neural(texto, voz_id):
    speech_key = os.getenv("AZURE_SPEECH_KEY")
    region = os.getenv("AZURE_SPEECH_REGION")

    if not speech_key or not region:
        raise Exception("Azure Speech no configurado")

    speech_config = speechsdk.SpeechConfig(
        subscription=speech_key,
        region=region
    )

    speech_config.speech_synthesis_voice_name = voz_id
    speech_config.set_speech_synthesis_output_format(
        speechsdk.SpeechSynthesisOutputFormat.Audio16Khz32KBitRateMonoMp3
    )

    filename = f"audio_{uuid.uuid4().hex}.mp3"
    path = f"/tmp/{filename}"

    audio_config = speechsdk.audio.AudioOutputConfig(filename=path)

    synthesizer = speechsdk.SpeechSynthesizer(
        speech_config=speech_config,
        audio_config=audio_config
    )

    result = synthesizer.speak_text_async(texto).get()

    if result.reason != speechsdk.ResultReason.SynthesizingAudioCompleted:
        raise Exception("Error Azure TTS")

    return path

from flask import request, send_file

@app.route("/tts/neural", methods=["POST"])
def tts_neural():
    data = request.json or {}

    texto = data.get("text")
    voz = data.get("voice")

    if not texto or not voz:
        return {"ok": False, "error": "Texto y voz requeridos"}, 400

    # 🔐 VALIDACIÓN CORRECTA (SIN DESEMPAQUETAR)
    resp = validate_license()
    if resp.status_code != 200:
        return resp

    audio_path = generar_audio_neural(texto, voz)

    return send_file(
        audio_path,
        mimetype="audio/mpeg",
        as_attachment=True
    )


# ========================================
# 🔐 Endpoint para detectar conexión
# ========================================

@app.route("/ping")
def ping():
    return {"online": True}


# -------------------------
# New helpers: load_all_licenses + get by email/ip/device
# -------------------------
def load_all_licenses():
    """
    Return list of license dicts (metadata parsed).
    """
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM licenses ORDER BY created_at DESC")
    rows = cur.fetchall()
    conn.close()
    out = []
    for r in rows:
        d = dict(r)
        try:
            d["metadata"] = json.loads(d.get("metadata") or "{}")
        except Exception:
            d["metadata"] = d.get("metadata")
        out.append(d)
    return out

def get_license_by_email(email):
    """
    Return the most recent license for this email or None.
    """
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute(
        "SELECT * FROM licenses WHERE email = ? ORDER BY created_at DESC LIMIT 1",
        (email,)
    )

    row = cur.fetchone()   # <-- obtenemos SOLO una fila, la más reciente
    conn.close()

    if not row:
        return None

    lic = dict(row)        # <-- convertimos sqlite.Row -> dict

    # Cargar metadata
    try:
        lic["metadata"] = json.loads(lic.get("metadata") or "{}")
    except Exception:
        lic["metadata"] = lic.get("metadata")

    return lic

def get_license_by_ip(ip):
    """
    Return the first license that has metadata.ip == ip (or None).
    Scans metadata because metadata is stored as JSON.
    """
    all_lic = load_all_licenses()
    for lic in all_lic:
        meta = lic.get("metadata") or {}
        if isinstance(meta, dict) and meta.get("ip") == ip:
            return lic
    return None

def get_license_by_device(device_id):
    """
    Return the first license that has metadata.device_id == device_id (or None).
    """
    all_lic = load_all_licenses()
    for lic in all_lic:
        meta = lic.get("metadata") or {}
        if isinstance(meta, dict) and meta.get("device_id") == device_id:
            return lic
    return None


@app.route("/metrics/generation-start", methods=["POST"])
def metric_generation_start():
    data = request.get_json() or {}
    email = data.get("email")

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO metrics (email, event) VALUES (?, ?)",
        (email, "start")
    )
    conn.commit()
    conn.close()

    return jsonify({"ok": True})


@app.route("/metrics/generation-success", methods=["POST"])
def metric_generation_success():
    data = request.get_json() or {}
    email = data.get("email")

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO metrics (email, event) VALUES (?, ?)",
        (email, "success")
    )
    conn.commit()
    conn.close()

    return jsonify({"ok": True})
    
@app.route('/api/guardar_guiones_app', methods=['POST'])
def guardar_guiones_app():
    data = request.json
    email = data.get('email')
    guiones = data.get('guiones') # Esto es el array de 10 guiones que envió la Web

    conn = sqlite3.connect(os.path.join(DATA_DIR, 'database.db'))
    cursor = conn.cursor()
    
    # Los insertamos en la cola para que la App los lea
    for texto in guiones:
        cursor.execute('''
            INSERT INTO videos_cola (email, tipo, estado_bot, hora, metadata)
            VALUES (?, ?, ?, ?, ?)
        ''', (email, "Guion IA", "pendiente", datetime.now().strftime("%H:%M"), texto))
    
    conn.commit()
    conn.close()
    return jsonify({"ok": True})

@app.route("/metrics/generation-error", methods=["POST"])
def metric_generation_error():
    data = request.get_json() or {}
    email = data.get("email")
    error = data.get("error")

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO metrics (email, event, error) VALUES (?, ?, ?)",
        (email, "error", error)
    )
    conn.commit()
    conn.close()

    return jsonify({"ok": True})

# -------------------------
# Endpoints
# -------------------------

from flask import redirect

@app.route("/create-checkout-session", methods=["GET", "POST"])
def create_checkout_session():
    price_id = None
    email = None
    plan = "pro"

    if request.method == "GET":
        price_id = request.args.get("price_id")
        email = request.args.get("email")
        plan = request.args.get("plan", "pro")

    elif request.method == "POST":
        data = request.get_json(silent=True) or {}
        price_id = data.get("price_id")
        email = data.get("email")
        plan = data.get("plan", "pro")

    if not price_id:
        price_id = PRICE_ID_PRO

    if not email:
        return jsonify({"ok": False, "error": "Se requiere email."}), 400

    try:
        customers = stripe.Customer.list(email=email, limit=1)
        if customers and customers.data:
            customer = customers.data[0]
        else:
            customer = stripe.Customer.create(email=email)

        session = stripe.checkout.Session.create(
            success_url=urljoin(PUBLIC_DOMAIN, "/success?session_id={CHECKOUT_SESSION_ID}"),
            cancel_url=urljoin(PUBLIC_DOMAIN, "/cancel"),
            payment_method_types=["card"],
            mode="subscription",
            line_items=[{"price": price_id, "quantity": 1}],
            customer=customer.id,
            metadata={"email": email, "plan": plan}
        )

        #  🔥 CORRECTO → devolver JSON con la URL
        return jsonify({"ok": True, "url": session.url})

    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/portal-session", methods=["POST"])
def create_portal_session():
    data = request.get_json() or {}
    customer_id = data.get("customer_id")
    if not customer_id:
        return jsonify({"error": "customer_id requerido"}), 400
    try:
        session = stripe.billing_portal.Session.create(
            customer=customer_id,
            return_url=PUBLIC_DOMAIN
        )
        return jsonify({"url": session.url})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/license/validate", methods=["POST"])
def validate_license():
    data = request.get_json(silent=True) or {}

    key = data.get("license_key") or data.get("key")
    email = data.get("email")

    # ---------------------------------------------------
    # Obtener licencia por key o email
    # ---------------------------------------------------
    if email and not key:
        lic = get_license_by_email(email)
    else:
        lic = get_license_by_key(key)

    if not lic:
        return jsonify({"valid": False, "reason": "not_found"}), 200

    # ---------------------------------------------------
    # Convertir Row → dict SIEMPRE
    # ---------------------------------------------------
    if not isinstance(lic, dict):
        lic = dict(lic)

    # 🔒 aseguramos siempre el campo aunque sea FREE
    lic["current_period_end"] = None

    print("DEBUG license stripe_subscription_id:", lic.get("stripe_subscription_id"))

    # ============================================================
    # SINCRONIZACIÓN REAL CON STRIPE
    # ============================================================
    if lic.get("stripe_subscription_id"):
        try:
            sub = stripe.Subscription.retrieve(
                lic["stripe_subscription_id"],
                expand=["latest_invoice"]
            )

            print("DEBUG Stripe subscription status:", sub.get("status"))
            print("DEBUG Stripe current_period_end:", sub.get("current_period_end"))


            # 🔥 FECHA REAL DE RENOVACIÓN (Stripe)
            lic["current_period_end"] = sub.get("current_period_end")

            price_id = sub["items"]["data"][0]["price"]["id"]
            status = sub["status"]

            # Mapear plan
            plan_map = {
                PRICE_ID_STARTER: "starter",
                PRICE_ID_PRO: "pro",
                PRICE_ID_AGENCY: "agency",
                PRICE_ID_STARTER_ANNUAL: "starter",
                PRICE_ID_PRO_ANNUAL: "pro",
                PRICE_ID_AGENCY_ANNUAL: "agency"
            }

            new_plan = plan_map.get(price_id, lic["plan"])

            credits_map = {
                "starter": 100,
                "pro": 300,
                "agency": 1200,
                "free": 10
            }

            new_credits = credits_map[new_plan]

            # Mantener créditos usados siempre
            credits_left = lic.get("credits_left", new_credits)

            # Si la suscripción está cancelada / pausada / vencida
            if status not in ("active", "trialing"):
                lic["status"] = "inactive"

                conn = get_db_connection()
                cur = conn.cursor()
                cur.execute("""
                    UPDATE licenses SET 
                        status='inactive'
                    WHERE license_key=?
                """, (lic["license_key"],))
                conn.commit()
                conn.close()

                return jsonify({"valid": False, "reason": "inactive"}), 200

            # Guardar actualización normal
            conn = get_db_connection()
            cur = conn.cursor()
            cur.execute("""
                UPDATE licenses SET 
                    plan=?, 
                    credits=?, 
                    credits_left=?, 
                    status=?
                WHERE license_key=?
            """, (new_plan, new_credits, credits_left, status, lic["license_key"]))
            conn.commit()
            conn.close()

            # Actualizar en memoria
            lic["plan"] = new_plan
            lic["credits"] = new_credits
            lic["credits_left"] = credits_left
            lic["status"] = status

        except Exception as e:
            print("⚠️ Stripe sync error:", e)
            
    if lic and "expires_at" not in lic:
        lic["expires_at"] = None

    expires_at = lic.get("expires_at")

    if expires_at and not isinstance(expires_at, str):
        expires_at = str(expires_at)


    # ============================================================
    # RESPUESTA
    # ============================================================
    return jsonify({
        "valid": True,
        "license": {
            "license_key": lic["license_key"],
            "email": lic.get("email"),
            "plan": lic.get("plan", "free"),
            "status": lic.get("status", "active"),
            "credits": lic.get("credits", 0),
            "credits_left": lic.get("credits_left", 0),
            "expires_at": lic.get("expires_at")

        }
    })


@app.route("/license/by-email", methods=["POST"])
def license_by_email():
    data = request.get_json() or {}
    email = data.get("email")

    if not email:
        return jsonify({"error": "email_required"}), 400

    lic = get_license_by_email(email)

    if not lic:
        return jsonify({"exists": False}), 200

    return jsonify({
        "exists": True,
        "license": {
            "license_key": lic["license_key"],
            "email": lic["email"],
            "plan": lic["plan"],
            "credits": lic["credits"],
            "credits_left": lic["credits_left"],
            "status": lic["status"]
        }
    }), 200


@app.route("/license/redeem", methods=["POST"])
def redeem_license():
    data = request.get_json() or {}
    cust = data.get("stripe_customer_id")
    sub = data.get("stripe_subscription_id")
    email = (data.get("email") or "").strip().lower()
    plan = data.get("plan", "pro")
    expires = data.get("expires_at")
    credits = data.get("credits", None)

    if not (cust and sub and email):
        return jsonify({"error": "stripe_customer_id, stripe_subscription_id y email son requeridos"}), 400

    status = "active"
    expires_dt = None
    if expires:
        try:
            expires_dt = datetime.fromisoformat(expires)
        except Exception:
            expires_dt = None

    # Normalizar plan
    plan_key = plan.lower().split("_")[0]

    # Si no vienen créditos, usar defaults
    if credits is None:
        credits = PLAN_DEFAULT_CREDITS.get(plan_key, 100)

    # 🔍 Buscar licencia existente por email
    existing = get_license_by_email(email)

    if existing:
        # ✅ ACTUALIZAR licencia existente
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            UPDATE licenses 
            SET 
                stripe_customer_id = ?,
                stripe_subscription_id = ?,
                plan = ?,
                status = ?,
                expires_at = ?,
                credits = ?,
                credits_left = ?
            WHERE email = ?
        """, (
            cust,
            sub,
            plan_key,
            status,
            expires_dt.isoformat() if expires_dt else None,
            credits,
            credits,
            email
        ))
        conn.commit()
        conn.close()

        license_key = existing["license_key"]

    else:
        # 🆕 Crear licencia solo si no existe
        license_key = gen_license()
        save_license(
            license_key=new_key,
            email=email,
            plan=plan_key,
            credits=credits,
            stripe_customer_id=customer_id,
            stripe_subscription_id=subscription_id,
            status="active",
        )


    return jsonify({
        "ok": True,
        "license_key": license_key,
        "plan": plan_key,
        "email": email
    })

# -------------------------
# Usage endpoint: decrement credits atomically
# POST /usage
# Body: { "license_key": "LIC-...", "action": "audio" (or "subtitle"), "cost": 1 }
# Returns: { "ok": True, "credits_left": n }
# -------------------------
@app.route("/usage", methods=["POST"])
def post_usage():
    data = request.get_json() or {}
    key = data.get("license_key")
    action = data.get("action", "generic")
    cost = int(data.get("cost", 1))
    modo = data.get("modo")  # "audio_upload" | "tts"


    if not key:
        return jsonify({"error": "license_key requerido"}), 400

    # Ensure license exists
    lic = get_license_by_key(key)
    

    if not lic:
        return jsonify({"error": "license_not_found"}), 404

    plan = (lic.get("plan") or "").lower()    

    # If license status not active, reject
    if lic.get("status") not in ("active", "trialing"):
        return jsonify({"error": "license_inactive", "status": lic.get("status")}), 403

    # ♾️ Generación ilimitada: PRO / AGENCY + audio subido
    if plan in ("pro", "agency") and modo == "audio_upload":
        print("♾️ [SERVER] Ilimitado activo → NO se descuentan créditos")
        return jsonify({
            "ok": True,
            "credits_left": lic.get("credits_left"),
            "unlimited": True,
            "action": action
        })
    

    # Decrement credits atomically
    # ♾️ PRO / AGENCY + audio subido → NO descontar
    if plan in ("pro", "agency") and modo == "audio_upload":
        return jsonify({
            "ok": True,
            "credits_left": lic.get("credits_left"),
            "unlimited": True,
            "action": action
        })

    new_left = adjust_credits_left(key, -cost)

    return jsonify({
        "ok": True,
        "credits_left": new_left,
        "action": action
    })

# -------------------------
# Webhook handling
# -------------------------
@app.route("/webhook", methods=["POST"])
def webhook():
    payload = request.data
    sig = request.headers.get("Stripe-Signature")
    webhook_secret = "whsec_ACgNxemkNBo9SGjfWUckMiVWiX3XJRrA"

    try:
        event = stripe.Webhook.construct_event(payload, sig, webhook_secret)
    except Exception as e:
        print("❌ Error webhook:", e)
        return "Invalid", 400

    event_type = event["type"]
    session = event["data"]["object"]

    print("🔔 Webhook recibido:", event_type)

    # -------------------------
    # MAPEO PLANES
    # -------------------------
    plan_map = {
        PRICE_ID_STARTER: "starter",
        PRICE_ID_PRO: "pro",
        PRICE_ID_AGENCY: "agency",
        PRICE_ID_STARTER_ANNUAL: "starter",
        PRICE_ID_PRO_ANNUAL: "pro",
        PRICE_ID_AGENCY_ANNUAL: "agency",
    }

    credits_map = {
        "starter": 100,
        "pro": 300,
        "agency": 1200,
        "free": 10,
    }

    # ============================================================
    # CHECKOUT COMPLETED
    # ============================================================
    if event_type == "checkout.session.completed":

        # 🟩 SUSCRIPCIONES
        if session.get("mode") == "subscription":
            email = session["customer_details"]["email"]
            subscription_id = session.get("subscription")
            customer_id = session.get("customer")

            line_items = stripe.checkout.Session.list_line_items(session["id"])
            price_id = line_items.data[0].price.id

            plan = plan_map.get(price_id, "starter")
            plan_credits = credits_map[plan]

            print(f"🆕 Nueva SUSCRIPCIÓN {email} → {plan}")

            existing = get_license_by_email(email)

            conn = get_db_connection()
            cur = conn.cursor()

            if existing:
                # 🔥 SUMAR créditos existentes + créditos del plan
                existing_credits = int(existing.get("credits", 0) or 0)
                existing_credits_left = int(existing.get("credits_left", 0) or 0)

                new_total_credits = existing_credits + plan_credits
                new_credits_left = existing_credits_left + plan_credits

                cur.execute("""
                    UPDATE licenses SET 
                        plan=?,
                        credits=?,
                        credits_left=?,
                        status='active',
                        stripe_customer_id=?,
                        stripe_subscription_id=?
                    WHERE email=?
                """, (
                    plan,
                    new_total_credits,
                    new_credits_left,
                    customer_id,
                    subscription_id,
                    email
                ))

            else:
                new_key = gen_license()
                save_license(
                    license_key=new_key,
                    email=email,
                    plan=plan,
                    credits=plan_credits,
                    status="active",
                    stripe_customer_id=customer_id,
                    stripe_subscription_id=subscription_id
                )

            conn.commit()
            conn.close()


        # 🟦 PAGOS ÚNICOS (PACKS DE CRÉDITOS)
        elif session.get("mode") == "payment":
            email = session.get("customer_email")
            metadata = session.get("metadata", {})

            pack = metadata.get("pack")
            credits_to_add = metadata.get("credits") or pack

            print("🟦 Pago único detectado → pack:", pack, "credits:", credits_to_add)

            if email and credits_to_add:
                lic = get_license_by_email(email)

                if lic:
                    extra = int(credits_to_add)

                    new_credits = (lic["credits"] or 0) + extra
                    new_credits_left = (lic["credits_left"] or 0) + extra

                    conn = get_db_connection()
                    cur = conn.cursor()
                    cur.execute(
                        """
                        UPDATE licenses 
                        SET credits = ?, credits_left = ?, updated_at = CURRENT_TIMESTAMP
                        WHERE license_key = ?
                        """,
                        (new_credits, new_credits_left, lic["license_key"])
                    )
                    conn.commit()
                    conn.close()

                    print(f"🟩 Créditos sumados correctamente: +{extra} → {email}")
                else:
                    print("❌ Pago recibido pero no existe licencia para:", email)



    # ============================================================
    # OTROS EVENTOS → IGNORAR PERO RESPONDER OK
    # ============================================================
    else:
        print(f"ℹ Evento ignorado: {event_type}")

    # 🔥 ESTO ES OBLIGATORIO
    return "OK", 200


@app.route("/buy-credits-success", methods=["GET"])
def buy_credits_success():
    return """
    <html>
        <body style="font-family: Arial; padding: 40px; text-align: center;">
            <h1 style="color: #22A55A;">✅ Compra completada</h1>
            <p>Tu paquete de créditos fue acreditado correctamente.</p>
            <p>Ya puedes cerrar esta pestaña y regresar a la aplicación.</p>
        </body>
    </html>
    """
@app.route("/buy-credits-cancel", methods=["GET"])
def buy_credits_cancel():
    return """
    <html>
        <body style="font-family: Arial; padding: 40px; text-align: center;">
            <h1 style="color: #FF4C4C;">❌ Pago cancelado</h1>
            <p>No se realizó ningún cargo.</p>
            <p>Puedes volver a la aplicación y seguir creando videos.</p>
        </body>
    </html>
    """

    # ============================================================
    # 2) invoice.paid → Renovación o cambio de plan
    # ============================================================
    if event_type == "invoice.paid":

        subscription_id = data.get("subscription")
        if not subscription_id:
            print("⚠️ invoice.paid sin subscription. Ignorado.")
            return jsonify({"ignored": True})

        email = stripe.Customer.retrieve(data["customer"]).email

        price_id = data["lines"]["data"][0]["price"]["id"]
        plan = plan_map.get(price_id, "starter")
        credits = credits_map[plan]

        conn = get_db_connection()
        cur = conn.cursor()

        cur.execute("""
            UPDATE licenses SET
                plan=?,
                credits=?, 
                credits_left=?,
                status='active'
            WHERE email=?
        """, (plan, credits, credits, email))

        conn.commit()
        conn.close()

    return jsonify({"received": True})

# Debug: list licenses
@app.route("/_debug/licenses", methods=["GET"])
def debug_list_licenses():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM licenses ORDER BY created_at DESC")
    rows = cur.fetchall()
    conn.close()
    data = [dict(r) for r in rows]
    return jsonify(data)


@app.route("/license/local-create", methods=["POST"])
def local_license_create():
    data = request.get_json() or {}
    license_key = data.get("license_key")
    plan = data.get("plan", "starter")
    credits = int(data.get("credits", 50))
    email = data.get("email", "local@test.com")

    if not license_key:
        return jsonify({"error": "license_key requerido"}), 400

    metadata = data.get("metadata") or {}
    # keep passed metadata and add a flag
    metadata.update({"local": True})

    expires_at = datetime.utcnow() + timedelta(days=30)

    save_license(
        license_key=license_key,
        stripe_customer_id="LOCAL",
        stripe_subscription_id="LOCAL",
        email=email,
        plan=plan,
        status="active",
        expires_at=expires_at,
        metadata=metadata,
        credits=credits
    )

    # Return the full license object (app expects license payload)
    lic = get_license_by_key(license_key)
    try:
        lic["metadata"] = json.loads(lic.get("metadata") or "{}")
    except:
        pass

    return jsonify({"ok": True, "license": lic, "license_key": license_key, "credits": credits})

# ==============================================================
# CONFIRMAR EMAIL DESDE EL LINK DEL CORREO
# ==============================================================



@app.route("/license/free", methods=["POST"])
def create_free_license():
    data = request.get_json() or {}
    email = (data.get("email") or "").strip().lower()
    device_id = data.get("device_id")
    user_ip = request.headers.get("X-Forwarded-For", request.remote_addr)

    if not email:
        return jsonify({
            "ok": False,
            "error": "email_required",
            "message": "Por favor ingresa un correo válido."
        })

    # 💥 1. SI YA EXISTE UNA LICENCIA → NO CREAR OTRA
    existing = get_license_by_email(email)
    if existing:
        return jsonify({
            "ok": True,
            "already_verified": True,
            "message": "Este correo ya tiene una licencia activa.",
            "license": existing
        })

    # 💥 2. ESTE ENDPOINT SOLO SE USA SI NO EXISTE LICENCIA PREVIA
    new_license = create_free_license_internal(email)

    return jsonify({
        "ok": True,
        "message": "Licencia free creada correctamente.",
        "license": new_license
    })

@app.route('/generar_guiones_ia', methods=['POST'])
def generar_guiones_ia():
    data = request.json
    email = data.get('email')
    nicho = data.get('nicho')
    avatar = data.get('avatar')
    edad = data.get('edad')
    cantidad = data.get('cantidad', 10)

    if not email or not nicho:
        return jsonify({"ok": False, "error": "Datos incompletos"}), 400

    # AQUÍ SE CONECTARÍA CON TU API DE LLAMA 3 / OPENAI
    # Por ahora, simulamos la creación de guiones para la cola
    guiones_generados = []
    for i in range(int(cantidad)):
        guiones_generados.append({
            "tipo": f"Video {i+1} - {nicho}",
            "estado_bot": "listo",
            "hora": datetime.now().strftime("%H:%M"),
            "prompt_usado": f"Target: {avatar}, Edad: {edad}"
        })

    # Guardar en SQLite para que TurboClips lo vea
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        for g in guiones_generados:
            cursor.execute('''
                INSERT INTO videos_cola (email, tipo, estado_bot, hora, metadata)
                VALUES (?, ?, ?, ?, ?)
            ''', (email, g['tipo'], g['estado_bot'], g['hora'], json.dumps(g)))
        conn.commit()
        conn.close()
        return jsonify({"ok": True, "message": "Guiones sincronizados con la cola"})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})    

@app.route("/buy-credits", methods=["GET"])
def buy_credits():
    pack = request.args.get("pack")
    email = request.args.get("email")  # 🔥 AHORA SÍ

    if pack not in ["100", "300", "1000"]:
        return jsonify({"ok": False, "error": "pack_invalido"}), 400

    if not email:
        return jsonify({"ok": False, "error": "email_requerido"}), 400

    PACK_PRICE_MAP = {
        "100": os.getenv("PRICE_PACK_100"),
        "300": os.getenv("PRICE_PACK_300"),
        "1000": os.getenv("PRICE_PACK_1000"),
    }

    price_id = PACK_PRICE_MAP.get(pack)
    if not price_id:
        return jsonify({"ok": False, "error": "price_no_configurado"}), 500

    session = stripe.checkout.Session.create(
        mode="payment",
        payment_method_types=["card"],

        # 🔥 CLAVE ABSOLUTA
        customer_email=email,

        line_items=[{
            "price": price_id,
            "quantity": 1
        }],
        metadata={
            "type": "credit_topup",
            "pack": pack,
            "credits": pack,
            "email": email
        },
        success_url=PUBLIC_DOMAIN + "/buy-credits-success",
        cancel_url=PUBLIC_DOMAIN + "/buy-credits-cancel"
    )

    return redirect(session.url, code=302)



@app.route("/ads/banner", methods=["GET"])
def get_banner_ads():

    # Aquí puedes conectar una BD real, pero para empezar está bien un diccionario
    anuncios = [
               {
            "id": "nuevo_editor",
            "active": True,
            "segment": "free",
            "title": "NUEVA FUNCIÓN: Editor PRO",
            "subtitle": "Los usuarios PRO ya lo están usando.",
            "image": "https://drive.google.com/uc?export=download&id=1_ruyZBqPja6QYF_YFSk3UQU7iliKZAjq",
            "cta_text": "Actualizar ahora",
            "cta_url": "https://tu-pagina.com/upgrade",
            "expires": "2026-02-15"
        }
    ]

    return jsonify({"ads": anuncios})



@app.route("/ads/popup")
def ads_popup():
    ads = [
        {
            "image": "https://drive.google.com/uc?export=download&id=1WQQOj5kguWDhyMe8SVaNFNMHqVIVCBxB",
            "cta_url": "https://tusitio.com/oferta1"
        },
        {
            "image": "https://drive.google.com/uc?export=download&id=1efR38e-qtgtrPRGuTC6HWOx_p9gVQfK6",
            "cta_url": "https://tusitio.com/oferta2"
        },
        {
            "image": "https://drive.google.com/uc?export=download&id=1hB3K5stcbBV8DWqk69Rez51rTYPmOKCc",
            "cta_url": "https://tusitio.com/oferta3"
        },
        {
            "image": "https://drive.google.com/uc?export=download&id=1mSChZOUDkZfmLDVlTIRiXZbWgDk-7t6M",
            "cta_url": "https://tusitio.com/oferta4"
        },
        {
            "image": "https://drive.google.com/uc?export=download&id=1-3r9jLKilue5pBUItsj8DuYE0x0coWjA",
            "cta_url": "https://tusitio.com/oferta4"
        }

    ]

    return jsonify({"ads": ads})



@app.route("/success")
def success():
    html = """
    <html>
    <head>
        <meta charset="UTF-8">
        <title>Pago completado</title>
        <style>
            body {
                font-family: Arial, sans-serif;
                background-color: #0f0f0f;
                color: white;
                text-align: center;
                padding: 50px;
            }
            .card {
                background-color: #1c1c1c;
                padding: 30px;
                border-radius: 12px;
                display: inline-block;
                text-align: center;
                max-width: 500px;
            }
            .title {
                font-size: 28px;
                margin-bottom: 10px;
                color: #4CD964;
            }
            .subtitle {
                font-size: 18px;
                margin-bottom: 20px;
                color: #cccccc;
            }
            .body-text {
                font-size: 15px;
                margin-bottom: 30px;
                color: #aaaaaa;
            }
            .cta {
                display: inline-block;
                background-color: #FF8C42;
                color: white;
                padding: 12px 25px;
                border-radius: 8px;
                font-size: 16px;
                text-decoration: none;
            }
        </style>
    </head>
    <body>
        <div class="card">
            <h1 class="title">✅ ¡Pago completado con éxito!</h1>
            <div class="subtitle">Tu suscripción ha sido activada correctamente.</div>
            <div class="body-text">
                Ya puedes cerrar esta ventana y volver a TurboClips.  
                Tu cuenta ha sido actualizada y tus beneficios están activos.
            </div>
            
        </div>
    </body>
    </html>
    """
    return html

@app.route("/app/version", methods=["GET"])
def app_version():
    return jsonify({
        "version": "1.3.1",
        "mandatory": False,
        "url": "https://tuservidor.com/downloads/TurboClips.exe",
        "changelog": [
            "Mejoras de rendimiento",
            "Corrección de errores de subtítulos",
            "Auto-update agregado"
        ]
    })

# ==========================================================
# ENDPOINTS PARA EXTENSIÓN (METRICLIPS)
# ==========================================================

@app.route("/api/vincular_video", methods=["POST"])
def vincular_video():
    data = request.json
    license_key = data.get("license_key")
    tiktok_id = data.get("tiktok_id")

    if not license_key or not tiktok_id:
        return jsonify({"ok": False, "error": "Faltan datos"}), 400

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("UPDATE licenses SET tiktok_id = ? WHERE license_key = ?", (tiktok_id, license_key))
    conn.commit()
    conn.close()
    return jsonify({"ok": True})


@app.route("/api/get_metrics/<license_key>", methods=["GET"])
def get_video_metrics(license_key):
    """
    Endpoint para obtener las métricas de un video específico.
    Se usa para rellenar los campos en blanco del editModal automáticamente.
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        
        # Buscamos los datos actuales en la base de datos
        cur.execute("SELECT views, likes, retencion FROM licenses WHERE license_key = ?", (license_key,))
        row = cur.fetchone()
        conn.close()
        
        if row:
            # Convertimos a diccionario (p.ej. {"views": 1500, "likes": 200, "retencion": 45})
            return jsonify(dict(row))
        
        # Si no existe, devolvemos valores en 0 para no romper el modal
        return jsonify({"views": 0, "likes": 0, "retencion": 0})
        
    except Exception as e:
        print(f"❌ Error en get_metrics: {str(e)}")
        return jsonify({"error": "Error interno del servidor", "views": 0, "likes": 0, "retencion": 0}), 500


@app.route("/cancel")
def cancel():
    html = """
    <html>
    <head>
        <meta charset="UTF-8">
        <title>Pago cancelado</title>
        <style>
            body {
                font-family: Arial, sans-serif;
                background-color: #0f0f0f;
                color: white;
                text-align: center;
                padding: 50px;
            }
            .card {
                background-color: #1c1c1c;
                padding: 30px;
                border-radius: 12px;
                display: inline-block;
                text-align: center;
                max-width: 500px;
            }
            .title {
                font-size: 28px;
                margin-bottom: 10px;
                color: #FF4C4C;
            }
            .subtitle {
                font-size: 18px;
                margin-bottom: 20px;
                color: #cccccc;
            }
            .body-text {
                font-size: 15px;
                margin-bottom: 30px;
                color: #aaaaaa;
            }
            .cta {
                display: inline-block;
                background-color: #FF8C42;
                color: white;
                padding: 12px 25px;
                border-radius: 8px;
                font-size: 16px;
                text-decoration: none;
            }
        </style>
    </head>
    <body>
        <div class="card">
            <h1 class="title">❌ Pago cancelado</h1>
            <div class="subtitle">No se ha realizado ningún cobro.</div>
            <div class="body-text">
                Puedes intentarlo nuevamente cuando estés listo.  
                Si necesitas ayuda, nuestro equipo está disponible para ayudarte.
            </div>
            
        </div>
    </body>
    </html>
    """
    return html



   

    
    # ==============================================================
    # 🔒 BLOQUEO SUAVE POR DEVICE ID
    # ==============================================================
    if device_id:
        previous_device = get_license_by_device(device_id)
        if previous_device and previous_device.get("plan") == "free":
            return jsonify({
                "ok": False,
                "error": "device_already_used_free",
                "message": "Este dispositivo ya utilizó la prueba gratuita."
            })

    # ==============================================================
    # 🎁 CREAR LA NUEVA LICENCIA FREE
    # ==============================================================
    license_key = gen_license()

    credits_total = 10

    metadata = {"type": "free_trial", "ip": user_ip}
    if device_id:
        metadata["device_id"] = device_id

    save_license(
        license_key,
        stripe_customer_id=None,
        stripe_subscription_id=None,
        email=email,
        plan="free",
        status="active",
        expires_at=None,
        metadata=metadata,
        credits=credits_total
    )

    # Return full license object for client use
    lic = get_license_by_key(license_key)
    try:
        lic["metadata"] = json.loads(lic.get("metadata") or "{}")
    except:
        pass

    return jsonify({
        "ok": True,
        "license": lic,
        "license_key": license_key,
        "credits": credits_total
    })







































































