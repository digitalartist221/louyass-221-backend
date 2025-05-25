# app/services/payment_service.py
import requests
import json
from app.config import settings # Importer les paramètres de votre application

# Fonction utilitaire pour obtenir l'URL de base de l'API de paiement
# Bascule entre l'environnement de test et de production en fonction de settings.DEBUG
def get_payment_api_base_url():
    """
    Retourne l'URL de base de l'API de paiement (test ou production)
    en fonction du mode DEBUG de l'application.
    """
    if settings.DEBUG:
        return settings.PAYTECH_API_BASE_URL_TEST
    return settings.PAYTECH_API_BASE_URL_PROD

def initiate_payment(amount: float, order_id: str, description: str, customer_email: str):
    """
    Initialise une transaction de paiement avec la passerelle de paiement (ex: PayTech/CinetPay).

    Args:
        amount (float): Le montant de la transaction.
        order_id (str): Une référence unique pour votre commande/transaction.
        description (str): Description de l'article ou du service.
        customer_email (str): L'adresse e-mail du client.

    Returns:
        dict: Un dictionnaire contenant le succès de l'opération,
              l'URL de redirection si succès, et un message en cas d'échec.
    """
    api_url = f"{get_payment_api_base_url()}/v1/payment/request" # Adaptez cet endpoint selon la doc de votre passerelle

    # Le corps de la requête (payload) doit correspondre aux exigences de votre passerelle de paiement.
    # Les noms des champs (item_name, item_price, currency, etc.) peuvent varier.
    payload = {
        "item_name": description,
        "item_price": amount,
        "currency": "XOF", # Devise (ex: XOF pour le Franc CFA, USD, EUR)
        "command_name": f"Commande #{order_id}",
        "ref_command": order_id, # Votre référence unique de commande
        "ipn_url": f"{settings.APP_BASE_URL}/api/payment/notification", # URL de notification (webhook)
        "success_url": f"{settings.APP_BASE_URL}/payment/success", # URL de redirection en cas de succès
        "cancel_url": f"{settings.APP_BASE_URL}/payment/cancel", # URL de redirection en cas d'annulation
        "custom_field": json.dumps({"customer_email": customer_email, "order_id": order_id}), # Champs personnalisés (doivent être une chaîne JSON)
        "env": "test" if settings.DEBUG else "prod" # Indiquer l'environnement (si supporté par la passerelle)
    }

    # Les en-têtes (headers) pour l'authentification et le type de contenu.
    # PayTech/CinetPay peuvent exiger des en-têtes spécifiques (ex: X-API-KEY, X-SECRET-KEY, X-SERVICE-ID).
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "X-API-KEY": settings.PAYTECH_API_KEY,
        "X-SECRET-KEY": settings.PAYTECH_SECRET_KEY,
        "X-SERVICE-ID": settings.PAYTECH_SERVICE_ID # Ou tout autre en-tête d'ID marchand
    }

    try:
        response = requests.post(api_url, headers=headers, json=payload, timeout=10) # Ajout d'un timeout
        response.raise_for_status() # Lève une exception pour les codes d'erreur HTTP (4xx ou 5xx)

        data = response.json()

        # Vérifier la structure de la réponse et les champs attendus par votre passerelle
        if data.get("status") == "success" and data.get("redirect_url"):
            return {
                "success": True,
                "redirect_url": data["redirect_url"],
                "transaction_id": data.get("token") # L'ID de transaction généré par la passerelle
            }
        else:
            # Gérer les cas où la passerelle renvoie une erreur dans sa réponse JSON
            error_message = data.get("message", "Erreur inconnue de la passerelle de paiement.")
            print(f"Erreur d'initialisation du paiement: {error_message} - Détails: {data}")
            return {"success": False, "message": error_message}

    except requests.exceptions.Timeout:
        print("Timeout lors de la connexion à la passerelle de paiement.")
        return {"success": False, "message": "Le service de paiement a pris trop de temps à répondre."}
    except requests.exceptions.RequestException as e:
        # Gérer les erreurs de connexion ou de requête HTTP
        print(f"Erreur de connexion/requête à la passerelle de paiement: {e}")
        return {"success": False, "message": "Problème de connexion avec le service de paiement."}
    except json.JSONDecodeError:
        # Gérer les cas où la réponse n'est pas un JSON valide
        print(f"Réponse API passerelle de paiement non JSON valide: {response.text}")
        return {"success": False, "message": "Réponse invalide de l'API de paiement."}
    except Exception as e:
        # Gérer toute autre exception inattendue
        print(f"Une erreur inattendue est survenue: {e}")
        return {"success": False, "message": "Une erreur interne est survenue lors de l'initialisation du paiement."}

def verify_payment_status(transaction_id: str):
    """
    Interroge la passerelle de paiement pour obtenir le statut final d'une transaction.
    Cette fonction est cruciale pour la sécurité, surtout après un IPN.

    Args:
        transaction_id (str): L'ID de transaction fourni par la passerelle de paiement.

    Returns:
        dict: Un dictionnaire contenant le succès de l'opération, le statut de la transaction,
              et un message.
    """
    api_url = f"{get_payment_api_base_url()}/v1/payment/check_status" # Adaptez cet endpoint
    headers = {
        "Content-Type": "application/json",
        "X-API-KEY": settings.PAYTECH_API_KEY,
        "X-SECRET_KEY": settings.PAYTECH_SECRET_KEY,
        "X-SERVICE-ID": settings.PAYTECH_SERVICE_ID
    }
    payload = {"token": transaction_id} # Le token/ID de transaction à vérifier

    try:
        response = requests.post(api_url, headers=headers, json=payload, timeout=10)
        response.raise_for_status()
        data = response.json()

        # Adaptez l'analyse de la réponse en fonction de la documentation de votre passerelle
        # Les champs comme 'status', 'message', 'transaction_details' peuvent varier
        if data.get("status") == "success":
            # Le statut réel de la transaction (ex: 'COMPLETED', 'PENDING', 'FAILED')
            payment_status = data.get("transaction_status")
            return {"success": True, "status": payment_status, "message": data.get("message")}
        else:
            return {"success": False, "message": data.get("message", "Échec de la vérification du statut.")}

    except requests.exceptions.RequestException as e:
        print(f"Erreur lors de la vérification du statut de paiement: {e}")
        return {"success": False, "message": "Problème de connexion lors de la vérification du statut."}
    except json.JSONDecodeError:
        print(f"Réponse JSON invalide lors de la vérification du statut: {response.text}")
        return {"success": False, "message": "Réponse invalide de l'API de paiement."}
    except Exception as e:
        print(f"Une erreur inattendue est survenue lors de la vérification du statut: {e}")
        return {"success": False, "message": "Une erreur interne est survenue."}
