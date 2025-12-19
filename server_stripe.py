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










