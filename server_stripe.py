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


import os
import sib_api_v3_sdk
from sib_api_v3_sdk import Configuration, ApiClient, TransactionalEmailsApi
from sib_api_v3_sdk.models import SendSmtpEmail

import os
import stripe

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



DB_PATH = os.path.join(os.path.dirname(__file__), "stripe_licenses.db")

# Default price IDs (puedes setear en env)
PRICE_ID_PRO = ("price_1ScJlCGznS3gtqcWGFG56OBX")
PRICE_ID_STARTER = ("price_1ScJkpGznS3gtqcWsGC3ELYs")
PRICE_ID_AGENCY = ("price_1ScJlhGznS3gtqcWheD5Qk15")
PRICE_ID_STARTER_ANNUAL = os.environ.get("PRICE_ID_STARTER_ANNUAL", "")
PRICE_ID_PRO_ANNUAL = os.environ.get("PRICE_ID_PRO_ANNUAL", "")
PRICE_ID_AGENCY_ANNUAL = os.environ.get("PRICE_ID_AGENCY_ANNUAL", "")

# Mapping default credits by plan key (fallback)
PLAN_DEFAULT_CREDITS = {
    "starter": 100,
    "pro": 300,
    "agency": 1200
}

app = Flask(__name__)

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


def init_db():
    conn = get_db_connection()
    cur = conn.cursor()

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
            created_at TEXT,
            expires_at TEXT,
            metadata TEXT,
            credits INTEGER DEFAULT 0,
            credits_left INTEGER DEFAULT 0
        );
    """)

    # -----------------------------------------
    # Tabla de tokens para verificación de email
    # -----------------------------------------
    cur.execute("""
        CREATE TABLE IF NOT EXISTS email_verification_tokens (
            email TEXT PRIMARY KEY,
            token TEXT,
            used INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)

    conn.commit()
    conn.close()


# Inicializar DB al arrancar
init_db()

# -------------------------
# UTILITIES
# -------------------------
def gen_license():
    return "LIC-" + uuid.uuid4().hex.upper()

def now_iso():
    return datetime.utcnow().isoformat()

def save_license(license_key, stripe_customer_id, stripe_subscription_id, email, plan, status, expires_at=None, metadata=None, credits=None):
    conn = get_db_connection()
    cur = conn.cursor()
    # if license exists, update; else insert
    existing = cur.execute("SELECT * FROM licenses WHERE license_key = ?", (license_key,)).fetchone()
    meta_json = json.dumps(metadata or {})
    created_at = now_iso()
    expires_iso = expires_at.isoformat() if isinstance(expires_at, datetime) else expires_at
    if existing:
        cur.execute("""
    UPDATE licenses 
    SET stripe_customer_id=?, 
        stripe_subscription_id=?, 
        email=?, 
        plan=?, 
        status=?, 
        expires_at=?, 
        metadata=?, 
        credits=?, 
        credits_left=? 
    WHERE license_key=?
""", (
    stripe_customer_id,
    stripe_subscription_id,
    email,
    plan,
    status,
    expires_iso,
    meta_json,
    credits if credits is not None else existing["credits"],
    credits if credits is not None else existing["credits_left"],
    license_key
))
    else:
        cur.execute("""
            INSERT INTO licenses (license_key, stripe_customer_id, stripe_subscription_id, email, plan, status, created_at, expires_at, metadata, credits, credits_left)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (license_key, stripe_customer_id, stripe_subscription_id, email, plan, status, created_at, expires_iso, meta_json, credits or 0, credits or 0))
    conn.commit()
    conn.close()

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
    return dict(row) if row else None

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
        ON CONFLICT(email) DO UPDATE SET 
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
    conn = connect_db()
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


@app.route("/auth/verify", methods=["GET"])
def verify():
    token = request.args.get("token")

    # Buscar token en la base
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT email, used FROM email_verification_tokens WHERE token = ?", (token,))
    row = cur.fetchone()
    conn.close()

    if not row:
        return jsonify({"ok": False, "error": "token_not_found"})

    email = row["email"].strip().lower()
    used = row["used"]

    # 🔥 SI YA EXISTE LICENCIA → NO NOTIFICAR CREACIÓN
    existing = get_license_by_email(email)
    if existing:
        # Si ya está verificado → NO mandar ningún mensaje de creación
        return jsonify({
            "ok": True,
            "already_verified": True,
            "message": "Este correo ya fue verificado.",
            "license": existing
        })

    # 🔥 2. Marcar token como usado
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("UPDATE email_verification_tokens SET used = 1 WHERE token = ?", (token,))
    conn.commit()
    conn.close()

    # 🔥 3. SI YA EXISTE LICENCIA → NO CREAR OTRA
    existing = get_license_by_email(email)
    if existing:
        return jsonify({
            "ok": True,
            "message": "Correo ya verificado anteriormente",
            "email": email,
            "license": existing
        })

    # 🔥 4. SOLO si NO existe licencia → crear FREE
    new_license = create_free_license_internal(email)

    return jsonify({
        "ok": True,
        "message": "Correo verificado correctamente",
        "email": email,
        "license": new_license
    })


@app.route("/auth/check_status", methods=["GET"])
def check_status():
    email = request.args.get("email")
    
    lic = get_license_by_email(email)
    if not lic:
        return jsonify({"ok": False, "verified": False})

    return jsonify({
        "ok": True,
        "verified": True,
        "license": lic,
        "credits": lic.get("credits_left", 0)
    })


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
    cur.execute("SELECT * FROM licenses WHERE email = ? ORDER BY created_at DESC LIMIT 1", (email,))
    row = cur.fetchone()
    conn.close()
    if not row:
        return None
    d = dict(row)
    try:
        d["metadata"] = json.loads(d.get("metadata") or "{}")
    except Exception:
        d["metadata"] = d.get("metadata")
    return d

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
    data = request.get_json() or {}
    key = data.get("license_key") or data.get("key")

    if not key:
        return jsonify({"valid": False, "reason": "license_key_required"}), 400

    lic = get_license_by_key(key)
    if not lic:
        return jsonify({"valid": False, "reason": "not_found"}), 404

    # 🔁 SYNC PLAN CON STRIPE (SI TIENE CUSTOMER)
    if lic.get("stripe_customer_id"):
        try:
            subs = stripe.Subscription.list(
                customer=lic["stripe_customer_id"],
                status="all",
                limit=1
            )

            if subs.data:
                sub = subs.data[0]
                price_id = sub["items"]["data"][0]["price"]["id"]

                plan_map = {
                    "price_1ScJkpGznS3gtqcWsGC3ELYs": "starter",
                    "price_1ScJlCGznS3gtqcWGFG56OBX": "pro",
                    "price_1ScJlhGznS3gtqcWheD5Qk15": "agency"
                }

                new_plan = plan_map.get(price_id, "free")

                if lic.get("plan") != new_plan:
                    conn = get_db_connection()
                    cur = conn.cursor()
                    cur.execute(
                        "UPDATE licenses SET plan = ? WHERE license_key = ?",
                        (new_plan, key)
                    )
                    conn.commit()
                    conn.close()
                    lic["plan"] = new_plan

        except Exception as e:
            print("⚠️ Stripe sync error:", e)

    # ✅ LICENCIA ACTIVA AUNQUE NO TENGA CRÉDITOS
    if lic.get("status") not in ("active", "trialing"):
        return jsonify({"valid": False, "reason": "inactive"}), 403

    return jsonify({
        "valid": True,
        "license": {
            "license_key": lic["license_key"],
            "plan": lic.get("plan", "free"),
            "status": lic["status"]
        }
    })



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
            license_key,
            cust,
            sub,
            email,
            plan_key,
            status,
            expires_dt,
            metadata={"created_via": "webhook"},
            credits=credits
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

    if not key:
        return jsonify({"error": "license_key requerido"}), 400

    # Ensure license exists
    lic = get_license_by_key(key)
    if not lic:
        return jsonify({"error": "license_not_found"}), 404

    # If license status not active, reject
    if lic.get("status") not in ("active", "trialing"):
        return jsonify({"error": "license_inactive", "status": lic.get("status")}), 403

    # Decrement credits atomically
    new_left = adjust_credits_left(key, -cost)
    if new_left is None:
        return jsonify({"error": "db_error"}), 500

    return jsonify({"ok": True, "credits_left": new_left, "action": action})

# -------------------------
# Webhook handling
# -------------------------
@app.route("/webhook", methods=["POST"])
def webhook():
    payload = request.data
    sig = request.headers.get("Stripe-Signature")

    # Reemplaza por tu webhook secret real
    webhook_secret = "whsec_ACgNxemkNBo9SGjfWUckMiVWiX3XJRrA"


    try:
        event = stripe.Webhook.construct_event(payload, sig, webhook_secret)
    except Exception as e:
        print("❌ Webhook signature error:", e)
        return "Invalid signature", 400

    event_type = event["type"]
    print("Webhook received:", event_type)

    # -------------------------------------------------------
    # checkout.session.completed
    # -------------------------------------------------------
    if event_type == "checkout.session.completed":
        session = event["data"]["object"]
        email = session["customer_details"]["email"]
        subscription_id = session["subscription"]
        customer_id = session["customer"]

        print(f"🔔 Checkout completado para {email}")

        # Mapear price -> plan
        line_items = stripe.checkout.Session.list_line_items(session["id"])
        price_id = line_items.data[0].price.id

        plan_map = {
            "price_1ScJkpGznS3gtqcWsGC3ELYs": ("pro", 100),
            "price_1ScJlCGznS3gtqcWGFG56OBX": ("starter", 30),
            "price_1ScJlUGznS3gtqcWSlvrLQcI": ("agency", 300),
        }

        plan_key, credits = plan_map.get(price_id, ("pro", 100))

        # Buscar licencia existente del email
        existing = get_license_by_email(email)

        if existing:
            print(f"🔁 Actualizando licencia existente: {existing['license_key']}")

            conn = connect_db()
            cur = conn.cursor()
            cur.execute(
                """UPDATE licenses SET 
                    plan=?, 
                    stripe_customer_id=?, 
                    stripe_subscription_id=?,
                    credits=?, 
                    credits_left=?, 
                    status='active'
                WHERE email=?""",
                (plan_key, customer_id, subscription_id, credits, credits, email),
            )
            conn.commit()
            conn.close()

        else:
            # No debería pasar, pero por seguridad:
            new_license_key = gen_license()
            print(f"🆕 Creando nueva licencia PRO para {email}: {new_license_key}")

            save_license(
                license_key=new_license_key,
                stripe_customer_id=customer_id,
                stripe_subscription_id=subscription_id,
                email=email,
                plan=plan_key,
                status="active",
                expires_at=None,
                metadata={"source": "stripe"},
                credits=credits,
            )

    # -------------------------------------------------------
    # invoice.paid (renovación mensual)
    # -------------------------------------------------------
    if event_type == "invoice.paid":
        invoice = event["data"]["object"]
        subscription_id = invoice["subscription"]

        print(f"🔄 Renovación pagada para subscripción {subscription_id}")

        # Determinar plan según price_id
        price_id = invoice["lines"]["data"][0]["price"]["id"]

        plan_map = {
            "price_1ScJkpGznS3gtqcWsGC3ELYs": ("pro", 100),
            "price_1ScJlCGznS3gtqcWGFG56OBX": ("starter", 30),
            "price_1ScJlUGznS3gtqcWSlvrLQcI": ("agency", 300),
        }

        plan_key, credits = plan_map.get(price_id, ("pro", 100))

        # Obtener datos customer_id
        customer_id = invoice["customer"]

        # Buscar licencia de la subscripción
        conn = connect_db()
        cur = conn.cursor()
        cur.execute(
            "SELECT * FROM licenses WHERE stripe_subscription_id=?",
            (subscription_id,),
        )
        existing = cur.fetchone()

        if existing:
            print(f"🔁 Renovando licencia {existing['license_key']}")

            cur.execute(
                """UPDATE licenses SET 
                    plan=?, 
                    credits=?, 
                    credits_left=?, 
                    status='active'
                WHERE stripe_subscription_id=?""",
                (plan_key, credits, credits, subscription_id),
            )
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
            "image": "https://drive.google.com/uc?export=download&id=1FmzuVNOrZ62kN3Vhsq7y-Jr2rDnsmzjh",
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
            "image": "https://drive.google.com/uc?export=download&id=1Z5CTKCq79PcUaWycIJ_2898waMseWROD",
            "cta_url": "https://tusitio.com/oferta1"
        },
        {
            "image": "https://drive.google.com/uc?export=download&id=15JzTgtE7IFyW6zI2kxRiAx3OOc7CFb_J",
            "cta_url": "https://tusitio.com/oferta2"
        },
        {
            "image": "https://drive.google.com/uc?export=download&id=1WGs5_omS7-nlEJG4ItqJ8FRRNfybMgtu",
            "cta_url": "https://tusitio.com/oferta3"
        },
        {
            "image": "https://drive.google.com/uc?export=download&id=1T-9yS9iq9aK1zeh36aFSl5O-sfOIS7kj",
            "cta_url": "https://tusitio.com/oferta4"
        },
        {
            "image": "https://drive.google.com/uc?export=download&id=1CVycJrhDGUzXtmDef_897MYZ0DBCwOBy",
            "cta_url": "https://tusitio.com/oferta4"
        }

    ]

    return jsonify({"ads": ads})



@app.route("/success")
def success():
    return "<h1>✅ Pago completado con éxito</h1><p>Ya puedes cerrar esta página.</p>"

@app.route("/cancel")
def cancel():
    return "<h1>❌ Pago cancelado</h1><p>Intenta nuevamente.</p>"

   

    
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


if __name__ == "__main__":
    print("Server starting on port 4242")
    app.run(host="0.0.0.0", port=4242, debug=True)












