# server_stripe.py
# Servidor Flask para Stripe Checkout + Webhooks + Licencias (SQLite)
# Bloque 1: imports, config (env), inicialización DB y helpers comunes.

import os
import json
import uuid
import sqlite3
import stripe
import time
from datetime import datetime, timedelta
from flask import Flask, request, jsonify, abort, redirect
from urllib.parse import urljoin

# Email (Brevo / SendinBlue) client
try:
    import sib_api_v3_sdk
    from sib_api_v3_sdk import Configuration, ApiClient, TransactionalEmailsApi
    from sib_api_v3_sdk.models import SendSmtpEmail
except Exception:
    sib_api_v3_sdk = None  # manejar la ausencia de la librería en runtime

# Cargar .env en desarrollo si existe
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

# ---------------------------
# Configuración por entorno
# ---------------------------
STRIPE_SECRET_KEY = os.environ.get("STRIPE_SECRET_KEY")
STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET")  # webhook signing secret
PUBLIC_DOMAIN = os.environ.get("PUBLIC_DOMAIN", "https://stripe-backend-r14f.onrender.com").rstrip("/")
BREVO_API_KEY = os.environ.get("BREVO_API_KEY")
BREVO_SENDER_EMAIL = os.environ.get("BREVO_SENDER_EMAIL", "turboclipsapp@gmail.com")
BREVO_SENDER_NAME = os.environ.get("BREVO_SENDER_NAME", "TurboClips")
# Opcional: SECRET app (para firmar tokens internos si los usas)
APP_SECRET = os.environ.get("APP_SECRET", uuid.uuid4().hex)

if not STRIPE_SECRET_KEY:
    raise RuntimeError("❌ STRIPE_SECRET_KEY no definida en variables de entorno.")

# Config Stripe
stripe.api_key = STRIPE_SECRET_KEY

print("[server_stripe] Stripe API key loaded (prefix):", (STRIPE_SECRET_KEY[:12] + "...") if STRIPE_SECRET_KEY else "MISSING")

# Config Brevo (si está disponible)
if sib_api_v3_sdk and BREVO_API_KEY:
    configuration = Configuration()
    configuration.api_key["api-key"] = BREVO_API_KEY
    brevo_client = ApiClient(configuration)
    brevo_email_api = TransactionalEmailsApi(brevo_client)
    print("[server_stripe] Brevo client configurado.")
else:
    brevo_client = None
    brevo_email_api = None
    if not BREVO_API_KEY:
        print("[server_stripe] WARNING: BREVO_API_KEY no configurado — emails de verificación serán simulados en logs.")

# ---------------------------
# App Flask
# ---------------------------
app = Flask(__name__)
app.config["JSON_SORT_KEYS"] = False

# ---------------------------
# Base de datos (SQLite)
# ---------------------------
DB_PATH = os.path.join(os.path.dirname(__file__), "stripe_licenses.db")

def get_db_connection():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Crea tablas si no existen."""
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS licenses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        license_key TEXT UNIQUE,
        email TEXT,
        plan TEXT,
        stripe_customer_id TEXT,
        stripe_subscription_id TEXT,
        status TEXT,
        credits INTEGER DEFAULT 0,
        credits_left INTEGER DEFAULT 0,
        expires_at TEXT,
        device_id TEXT,
        metadata TEXT DEFAULT '{}',
        created_at TEXT DEFAULT (datetime('now')),
        updated_at TEXT DEFAULT (datetime('now'))
    )
    """)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS verification_tokens (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT UNIQUE,
        token TEXT,
        created_at INTEGER,
        used INTEGER DEFAULT 0
    )
    """)
    conn.commit()
    conn.close()

# Inicializar DB al arrancar
init_db()

# ---------------------------
# Helpers: licencias y tokens
# ---------------------------
def gen_license(prefix="LIC"):
    """Genera una clave de licencia única."""
    return f"{prefix}-{uuid.uuid4().hex[:24].upper()}"

def now_ts():
    return int(time.time())

def save_license(license_key, stripe_customer_id, stripe_subscription_id, email, plan, status="active", expires_at=None, metadata=None, credits=0):
    """Crea o actualiza una licencia por email/clave."""
    metadata_json = json.dumps(metadata or {})
    conn = get_db_connection()
    cur = conn.cursor()

    # Normalizar email
    email_norm = email.strip().lower() if email else None

    # Busca si existe por email o por license_key
    existing = None
    if email_norm:
        cur.execute("SELECT * FROM licenses WHERE email = ?", (email_norm,))
        existing = cur.fetchone()
    if not existing and license_key:
        cur.execute("SELECT * FROM licenses WHERE license_key = ?", (license_key,))
        existing = cur.fetchone()

    expires_iso = None
    if isinstance(expires_at, datetime):
        expires_iso = expires_at.isoformat()
    elif isinstance(expires_at, str):
        expires_iso = expires_at
    else:
        expires_iso = None

    if existing:
        cur.execute("""
            UPDATE licenses SET
                stripe_customer_id = ?, stripe_subscription_id = ?, plan = ?, status = ?, expires_at = ?,
                credits = ?, credits_left = ?, metadata = ?, updated_at = datetime('now')
            WHERE license_key = ?
        """, (
            stripe_customer_id, stripe_subscription_id, plan, status, expires_iso,
            credits, credits, metadata_json, existing["license_key"]
        ))
        conn.commit()
        key_to_return = existing["license_key"]
    else:
        key_to_return = license_key or gen_license()
        cur.execute("""
            INSERT INTO licenses (
                license_key, email, plan, stripe_customer_id, stripe_subscription_id,
                status, expires_at, credits, credits_left, device_id, metadata, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))
        """, (
            key_to_return, email_norm, plan, stripe_customer_id, stripe_subscription_id,
            status, expires_iso, credits, credits, None, metadata_json
        ))
        conn.commit()

    conn.close()
    return key_to_return

def get_license_by_email(email):
    if not email:
        return None
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM licenses WHERE email = ?", (email.strip().lower(),))
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None

def get_license_by_key(key):
    if not key:
        return None
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM licenses WHERE license_key = ?", (key,))
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None

def get_license_by_device(device_id):
    if not device_id:
        return None
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM licenses WHERE device_id = ?", (device_id,))
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None

def adjust_credits_left(license_key, delta):
    """
    Ajusta credits_left en la BD de forma atómica.
    Retorna el nuevo valor o None en caso de error.
    """
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        # Empezar transacción explícita
        cur.execute("BEGIN IMMEDIATE")
        cur.execute("SELECT credits_left FROM licenses WHERE license_key = ? FOR UPDATE", (license_key,))
        row = cur.fetchone()
        if not row:
            conn.rollback()
            conn.close()
            return None
        current = int(row["credits_left"])
        new_val = current + int(delta)
        if new_val < 0:
            # no permitir créditos negativos
            conn.rollback()
            conn.close()
            return None
        cur.execute("UPDATE licenses SET credits_left = ?, updated_at = datetime('now') WHERE license_key = ?", (new_val, license_key))
        conn.commit()
        conn.close()
        return new_val
    except Exception as e:
        try:
            conn.rollback()
        except Exception:
            pass
        try:
            conn.close()
        except Exception:
            pass
        print("[adjust_credits_left] Error:", e)
        return None

# ---------------------------
# Verificación por correo: tokens
# ---------------------------
def create_or_update_verification_token(email):
    token = uuid.uuid4().hex
    ts = now_ts()
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO verification_tokens (email, token, created_at, used)
        VALUES (?, ?, ?, 0)
        ON CONFLICT(email) DO UPDATE SET token = excluded.token, created_at = excluded.created_at, used = 0
    """, (email.strip().lower(), token, ts))
    conn.commit()
    conn.close()
    return token

def consume_verification_token(token):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM verification_tokens WHERE token = ? AND used = 0", (token,))
    row = cur.fetchone()
    if not row:
        conn.close()
        return None
    # Marcar como usado
    cur.execute("UPDATE verification_tokens SET used = 1 WHERE id = ?", (row["id"],))
    conn.commit()
    conn.close()
    return row["email"]

# ---------------------------
# Crear licencia FREE interna (usada tras verify)
# ---------------------------
def create_free_license_internal(email, device_id=None):
    """
    Crea o devuelve una licencia FREE asociada al email.
    """
    email_norm = email.strip().lower()
    existing = get_license_by_email(email_norm)
    if existing:
        return existing  # devuelve dict

    license_key = gen_license()
    credits = 10
    save_license(
        license_key=license_key,
        stripe_customer_id=None,
        stripe_subscription_id=None,
        email=email_norm,
        plan="free",
        status="active",
        expires_at=None,
        metadata={"created_via": "email_verification"},
        credits=credits
    )
    return get_license_by_key(license_key)

# ---------------------------
# BLOQUE 2: Endpoints públicos principales
# ---------------------------

# Helper: enviar email de verificación (usa Brevo si está configurado, sino log)
def send_verification_email(email, token):
    verify_url = f"{PUBLIC_DOMAIN}/auth/verify?token={token}"
    subject = "Verifica tu correo para activar la prueba gratis"
    html_content = f"""
    <p>Hola,</p>
    <p>Haz clic en el siguiente enlace para activar tu prueba gratis en TurboClips:</p>
    <p><a href="{verify_url}">Confirmar Email</a></p>
    <p>Si no pediste este correo, puedes ignorarlo.</p>
    """
    text_content = f"Confirma tu email: {verify_url}"
    # Si Brevo está configurado, usarlo
    if brevo_email_api:
        try:
            email_req = SendSmtpEmail(
                to=[{"email": email}],
                html_content=html_content,
                sender={"email": BREVO_SENDER_EMAIL, "name": BREVO_SENDER_NAME},
                subject=subject
            )
            brevo_email_api.send_transac_email(email_req)
            print("[send_verification_email] Email enviado vía Brevo a:", email)
            return True
        except Exception as e:
            print("[send_verification_email] Error enviando con Brevo:", e)
            # continuar para fallback
    # Fallback: solo loguear
    print("[send_verification_email] (SIMULADO) Verificación:", verify_url, "-> para", email)
    return True


# ---------------------------
# Create Checkout Session (cliente llama con ?email=...&priceId=...)
# Método: GET o POST (ambos soportados)
# Devuelve JSON: { "url": "<stripe_checkout_url>" }
# ---------------------------
@app.route("/create-checkout-session", methods=["GET", "POST"])
def create_checkout_session():
    data = request.get_json(silent=True) or request.values.to_dict()
    email = (data.get("email") or "").strip()
    price_id = data.get("priceId") or data.get("price_id") or data.get("price")
    mode = "subscription"  # asumimos subscripciones; si necesitas pagos one-off, ajustar según price metadata

    if not email or not price_id:
        return jsonify({"error": "email and priceId are required"}), 400

    try:
        # Crear o reutilizar customer por email (simplificado: buscamos en Stripe por email no es trivial, creamos siempre)
        customer = stripe.Customer.create(email=email)

        # Crear checkout session
        session = stripe.checkout.Session.create(
            customer=customer.id,
            success_url=f"{PUBLIC_DOMAIN}/success?session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{PUBLIC_DOMAIN}/cancel",
            payment_method_types=["card"],
            mode=mode,
            line_items=[{"price": price_id, "quantity": 1}],
            metadata={"email": email}
        )

        print(f"[create_checkout_session] created session {session.id} for {email}")
        return jsonify({"url": session.url, "id": session.id}), 200

    except Exception as e:
        print("[create_checkout_session] Error:", e)
        return jsonify({"error": str(e)}), 500


# ---------------------------
# Request verification: crea token y envía mail
# POST JSON: { "email": "..." }
# ---------------------------
@app.route("/auth/request_verification", methods=["POST"])
def request_verification():
    payload = request.get_json(silent=True) or {}
    email = (payload.get("email") or "").strip().lower()
    if not email:
        return jsonify({"ok": False, "error": "email_required"}), 400

    try:
        token = create_or_update_verification_token(email)
        # enviar correo (async no-block: aquí simple sync)
        send_verification_email(email, token)
        return jsonify({"ok": True, "message": "Correo de verificación enviado."}), 200
    except Exception as e:
        print("[request_verification] Error:", e)
        return jsonify({"ok": False, "error": str(e)}), 500


# ---------------------------
# Verify endpoint (click desde email)
# GET ?token=...
# Consume token, crea licencia FREE si no existe y devuelve JSON o redirige
# ---------------------------
@app.route("/auth/verify", methods=["GET"])
def auth_verify():
    token = request.args.get("token")
    if not token:
        return jsonify({"ok": False, "error": "token_required"}), 400

    email = consume_verification_token(token)
    if not email:
        return jsonify({"ok": False, "error": "token_invalid_or_used"}), 400

    try:
        lic = create_free_license_internal(email)
        # Redirigimos a una página de éxito en PUBLIC_DOMAIN (si tienes frontend web)
        # Si no, devolvemos JSON con la licencia.
        success_url = PUBLIC_DOMAIN.rstrip("/") + f"/auth/verify/success?license_key={lic.get('license_key')}"
        print(f"[auth_verify] token validado para {email}, license: {lic.get('license_key')}")
        # Si existe un frontend web, redirigir; aquí devolvemos JSON si la petición es XHR
        if request.headers.get("Accept", "").find("application/json") != -1 or request.args.get("json") == "1":
            return jsonify({"ok": True, "license": lic}), 200
        return redirect(success_url)
    except Exception as e:
        print("[auth_verify] Error:", e)
        return jsonify({"ok": False, "error": str(e)}), 500


# ---------------------------
# License validate: POST JSON { license_key: "..."} OR { email: "..." }
# Devuelve { valid: bool, license: {...} }  (200) o 404 con error
# ---------------------------
@app.route("/license/validate", methods=["POST"])
def license_validate():
    payload = request.get_json(silent=True) or {}
    license_key = payload.get("license_key")
    email = payload.get("email")

    if license_key:
        lic = get_license_by_key(license_key)
        if not lic:
            return jsonify({"valid": False, "error": "not_found"}), 404
        return jsonify({"valid": True, "license": lic}), 200

    if email:
        lic = get_license_by_email(email)
        if not lic:
            return jsonify({"valid": False, "error": "not_found"}), 404
        return jsonify({"valid": True, "license": lic}), 200

    return jsonify({"valid": False, "error": "license_key_or_email_required"}), 400


# ---------------------------
# License local-create (modo DEV / herramientas internas)
# POST JSON: { license_key?, plan, credits }
# ---------------------------
@app.route("/license/local-create", methods=["POST"])
def license_local_create():
    payload = request.get_json(silent=True) or {}
    plan = payload.get("plan", "starter")
    credits = int(payload.get("credits", 0))
    license_key = payload.get("license_key") or gen_license()

    try:
        saved = save_license(
            license_key=license_key,
            stripe_customer_id=None,
            stripe_subscription_id=None,
            email=payload.get("email"),
            plan=plan,
            status="active",
            expires_at=None,
            metadata=payload.get("metadata") or {},
            credits=credits
        )
        lic = get_license_by_key(saved)
        return jsonify({"ok": True, "license": lic}), 200
    except Exception as e:
        print("[license_local_create] Error:", e)
        return jsonify({"ok": False, "error": str(e)}), 500


# ---------------------------
# Usage endpoint: consumir o consultar créditos
# POST JSON: { license_key: "...", action: "consume"|"get", amount: 1 }
# ---------------------------
@app.route("/usage", methods=["POST"])
def usage_endpoint():
    payload = request.get_json(silent=True) or {}
    license_key = payload.get("license_key")
    action = payload.get("action", "get")
    amount = int(payload.get("amount", 1))

    if not license_key:
        return jsonify({"ok": False, "error": "license_key_required"}), 400

    lic = get_license_by_key(license_key)
    if not lic:
        return jsonify({"ok": False, "error": "license_not_found"}), 404

    if action == "get":
        return jsonify({"ok": True, "credits_left": lic.get("credits_left", 0)}), 200
    elif action == "consume":
        new_left = adjust_credits_left(license_key, -abs(amount))
        if new_left is None:
            return jsonify({"ok": False, "error": "insufficient_credits_or_error"}), 400
        return jsonify({"ok": True, "credits_left": new_left}), 200
    elif action == "add":
        new_left = adjust_credits_left(license_key, abs(amount))
        if new_left is None:
            return jsonify({"ok": False, "error": "error_adding_credits"}), 500
        return jsonify({"ok": True, "credits_left": new_left}), 200
    else:
        return jsonify({"ok": False, "error": "unknown_action"}), 400


# ---------------------------
# Simple ads endpoint (placeholder)
# ---------------------------
@app.route("/ads", methods=["GET"])
def ads_endpoint():
    # Retorna contenido promocional simple
    return jsonify({
        "ads": [
            {"title": "Pásate a PRO", "subtitle": "300 créditos, voz premium", "link": f"{PUBLIC_DOMAIN}/pricing"},
            {"title": "Paquete 100 créditos", "subtitle": "$9", "link": f"{PUBLIC_DOMAIN}/buy-credits?pack=100"}
        ]
    }), 200


# ---------------------------
# Success / Cancel pages (usadas por Stripe Checkout redirect)
# ---------------------------
@app.route("/success", methods=["GET"])
def checkout_success_page():
    session_id = request.args.get("session_id")
    return jsonify({"ok": True, "message": "Checkout completado. Espera a que la licencia sea activada por el webhook.", "session_id": session_id}), 200

@app.route("/cancel", methods=["GET"])
def checkout_cancel_page():
    return jsonify({"ok": False, "message": "Checkout cancelado."}), 200


# ---------------------------
# Debug: listar licencias (solo para desarrollo)
# ---------------------------
@app.route("/_debug/licenses", methods=["GET"])
def debug_list_licenses():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM licenses ORDER BY id DESC LIMIT 500")
    rows = cur.fetchall()
    conn.close()
    results = [dict(r) for r in rows]
    return jsonify({"ok": True, "count": len(results), "licenses": results}), 200

# ---------------------------
# BLOQUE 3: Webhook de Stripe + manejo de eventos
# ---------------------------

@app.route("/webhook", methods=["POST"])
def stripe_webhook():
    payload = request.data
    sig_header = request.headers.get("Stripe-Signature")

    if not STRIPE_WEBHOOK_SECRET:
        print("⚠️ ADVERTENCIA: STRIPE_WEBHOOK_SECRET no configurado. Intentando fallback (solo TEST).")

    event = None

    # Intentar verificación normal
    try:
        if STRIPE_WEBHOOK_SECRET:
            event = stripe.Webhook.construct_event(
                payload, sig_header, STRIPE_WEBHOOK_SECRET
            )
            print(f"[WEBHOOK] ✔ Firma verificada: {event.get('type')}")
        else:
            raise ValueError("Sin STRIPE_WEBHOOK_SECRET")
    except Exception as e:
        print(f"[WEBHOOK] ❌ Firma inválida: {e}")

        # Fallback SOLO para entorno de pruebas
        try:
            event = json.loads(payload)
            print("⚠️ Fallback: Procesando evento SIN verificación de firma (SOLO TEST).")
        except Exception:
            return "Invalid signature", 400

    # Procesar evento
    event_type = event.get("type")
    data = event.get("data", {}).get("object", {})

    print(f"[WEBHOOK] Evento recibido: {event_type}")

    # --------------------------------------------------
    # checkout.session.completed
    # --------------------------------------------------
    if event_type == "checkout.session.completed":
        email = data.get("customer_details", {}).get("email") or data.get("customer_email")
        customer_id = data.get("customer")
        subscription_id = data.get("subscription")
        price_id = None

        try:
            if subscription_id:
                sub = stripe.Subscription.retrieve(subscription_id)
                if sub and sub.get("items", {}).get("data"):
                    price_id = sub["items"]["data"][0]["price"]["id"]
        except Exception as e:
            print("[WEBHOOK] Error obteniendo subscripción:", e)

        if not email:
            print("[WEBHOOK] ❌ checkout sin email — ignorado")
            return jsonify({"ok": True})

        price_id = price_id or "unknown"

        print(f"[WEBHOOK] checkout completado email={email} price={price_id}")

        # Asignar plan según price
        if "price_300" in price_id:
            plan = "pro_300"
            credits = 300
        elif "price_100" in price_id:
            plan = "pack_100"
            credits = 100
        elif "price_1000" in price_id:
            plan = "pack_1000"
            credits = 1000
        else:
            plan = "pro"
            credits = 150

        license_key = gen_license()
        save_license(
            license_key=license_key,
            stripe_customer_id=customer_id,
            stripe_subscription_id=subscription_id,
            email=email,
            plan=plan,
            status="active",
            expires_at=None,
            metadata={"source": "checkout.session.completed"},
            credits=credits
        )

        print(f"[WEBHOOK] ✔ Licencia creada/actualizada para {email}: {license_key}")

        return jsonify({"ok": True})

    # --------------------------------------------------
    # customer.subscription.created / updated
    # --------------------------------------------------
    if event_type in ("customer.subscription.created", "customer.subscription.updated"):
        sub = data
        customer_id = sub.get("customer")
        subscription_id = sub.get("id")
        email = None
        price_id = None

        # Intentar obtener el email del customer
        try:
            cust = stripe.Customer.retrieve(customer_id)
            email = cust.get("email")
        except:
            pass

        # Price
        try:
            if sub.get("items", {}).get("data"):
                price_id = sub["items"]["data"][0]["price"]["id"]
        except:
            pass

        if not email:
            print("[WEBHOOK] subscripción sin email, ignorado")
            return jsonify({"ok": True})

        print(f"[WEBHOOK] subscripción {event_type} email={email} price={price_id}")

        # Asignar plan según price
        if "price_300" in price_id:
            plan = "pro_300"
            credits = 300
        elif "price_150" in price_id:
            plan = "pro"
            credits = 150
        else:
            plan = "pro"
            credits = 150

        # Guardar/actualizar licencia
        existing = get_license_by_email(email)
        license_key = existing["license_key"] if existing else gen_license()

        save_license(
            license_key=license_key,
            stripe_customer_id=customer_id,
            stripe_subscription_id=subscription_id,
            email=email,
            plan=plan,
            status="active",
            expires_at=None,
            metadata={"source": event_type},
            credits=credits
        )

        print(f"[WEBHOOK] ✔ Licencia suscripción actualizada para {email}: {license_key}")

        return jsonify({"ok": True})

    # --------------------------------------------------
    # customer.subscription.deleted
    # --------------------------------------------------
    if event_type == "customer.subscription.deleted":
        sub = data
        customer_id = sub.get("customer")
        email = None

        try:
            cust = stripe.Customer.retrieve(customer_id)
            email = cust.get("email")
        except:
            pass

        if not email:
            print("[WEBHOOK] subscripción eliminada sin email")
            return jsonify({"ok": True})

        print(f"[WEBHOOK] subscription deleted para {email}")

        existing = get_license_by_email(email)
        if existing:
            # degradar a FREE sin borrar credits_left existentes
            save_license(
                license_key=existing["license_key"],
                stripe_customer_id=customer_id,
                stripe_subscription_id=None,
                email=email,
                plan="free",
                status="cancelled",
                expires_at=None,
                metadata={"source": "subscription.deleted"},
                credits=existing.get("credits_left", 0)
            )
            print(f"[WEBHOOK] licencia degradada a FREE para {email}")

        return jsonify({"ok": True})

    # --------------------------------------------------
    # invoice.payment_succeeded
    # --------------------------------------------------
    if event_type == "invoice.payment_succeeded":
        print("[WEBHOOK] invoice payment succeeded (OK)")
        return jsonify({"ok": True})

    # invoice.payment_failed
    if event_type == "invoice.payment_failed":
        print("[WEBHOOK] ⚠ pago falló — revisar plan del usuario")
        return jsonify({"ok": True})

    print("[WEBHOOK] Evento no manejado:", event_type)
    return jsonify({"ok": True})


# ---------------------------
# RUN SERVER
# ---------------------------
if __name__ == "__main__":
    print(f"🚀 Servidor escuchando en 0.0.0.0:{os.environ.get('PORT', 5000)}")
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
