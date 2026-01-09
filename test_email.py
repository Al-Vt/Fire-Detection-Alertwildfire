#!/usr/bin/env python3
"""
Script de test pour vérifier que l'envoi d'email fonctionne depuis Airflow
"""
from airflow.utils.email import send_email

subject = "🔥 TEST - Système de détection d'incendie"
html_content = """
<h2>✅ Test de l'alerte email</h2>
<p>Ce message confirme que le système d'alerte automatique fonctionne correctement.</p>

<h3>Configuration actuelle :</h3>
<ul>
    <li><b>Scraping :</b> Toutes les 10 minutes</li>
    <li><b>Analyse :</b> Modèle YOLOv8</li>
    <li><b>Seuil de confiance :</b> 40%</li>
    <li><b>Email de destination :</b> axel.vilamot@gmail.com</li>
</ul>

<hr>
<p><i>Vous recevrez un email similaire automatiquement quand un incendie sera détecté.</i></p>

<p>🚀 <b>Système opérationnel !</b></p>
"""

print("📧 Envoi de l'email de test...")
try:
    send_email(to=['axel.vilamot@gmail.com'], subject=subject, html_content=html_content)
    print("✅ Email envoyé avec succès !")
    print("   Vérifiez votre boîte de réception (et les spams si besoin)")
except Exception as e:
    print(f"❌ Erreur lors de l'envoi : {e}")
    print("\n⚠️  Vérifiez que :")
    print("   1. Le mot de passe d'application Gmail est correct dans .env")
    print("   2. L'authentification à 2 facteurs est activée sur Gmail")
    print("   3. Vous avez généré un 'App Password' sur https://myaccount.google.com/apppasswords")
