# app/main.py
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import json # Pour gérer les champs personnalisés JSON si nécessaire
import hmac # Pour la vérification de signature (exemple)
import hashlib # Pour la vérification de signature (exemple)

# Importez les services de paiement
from app.services.payment_service import initiate_payment, verify_payment_status
# Importez les paramètres de configuration
from app.config import settings

# IMPORTER LES ROUTEURS DIRECTEMENT DEPUIS LEURS FICHIERS RESPECTIFS
from app.auth.routes import router as auth_router
from app.routers.users import router as users_router
from app.routers.maisons import router as maisons_router
from app.routers.chambres import router as chambres_router
from app.routers.contrats import router as contrats_router
from app.routers.paiements import router as paiements_router
from app.routers.rendez_vous import router as rendez_vous_router
from app.routers.medias import router as medias_router
from app.routers.problemes import router as problemes_router
from app.routers.recherche import router as recherche_router

from app.database import Base, engine

# Crée les tables de la base de données si elles n'existent pas
Base.metadata.create_all(bind=engine)

# Initialisation de l'application FastAPI
app = FastAPI(
    title=settings.APP_NAME, # Utilise le nom de l'application depuis les paramètres
    version=settings.APP_VERSION, # Utilise la version de l'application depuis les paramètres
    debug=settings.DEBUG # Utilise le mode debug depuis les paramètres
)

# Configurer CORS (Cross-Origin Resource Sharing)
# Permet à votre frontend (ex: React sur localhost:3000 ou 5173) de faire des requêtes à votre backend.
origins = [
    "http://localhost", # Pour une compatibilité plus large
    "http://localhost:3000", # L'URL de votre application frontend (React, Vue, Angular)
    "http://localhost:5173", # L'URL de votre application frontend (Vite/React par exemple)
    # Ajoutez d'autres domaines si votre frontend est hébergé ailleurs en production
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"], # Permet toutes les méthodes HTTP (GET, POST, PUT, DELETE, etc.)
    allow_headers=["*"], # Permet tous les en-têtes dans les requêtes
)

# --- Schéma Pydantic pour la requête d'initialisation de paiement ---
class PaymentInitiateRequest(BaseModel):
    """
    Schéma pour les données requises pour initier un paiement.
    """
    amount: float = Field(..., description="Montant de la transaction.")
    order_id: str = Field(..., description="ID unique de la commande ou de la transaction.")
    description: str = Field(..., description="Description de l'article ou du service.")
    customer_email: str = Field(..., description="Adresse e-mail du client.")
    # Vous pouvez ajouter d'autres champs nécessaires ici, ex: customer_phone, currency, etc.

# --- Route pour initier un paiement ---

# --- Routes de l'application ---
app.include_router(auth_router)
app.include_router(users_router)
app.include_router(maisons_router)
app.include_router(chambres_router)
app.include_router(contrats_router)
app.include_router(paiements_router)
app.include_router(rendez_vous_router)
app.include_router(medias_router)
app.include_router(problemes_router)
app.include_router(recherche_router)
@app.post("/api/payments/initiate", summary="Initier une transaction de paiement")
async def create_payment(payment_request: PaymentInitiateRequest):
    """
    Endpoint pour initier une transaction de paiement via la passerelle.
    """
    print(f"Requête d'initialisation de paiement reçue: {payment_request.dict()}")

    # Appelle la fonction du service de paiement
    result = initiate_payment(
        amount=payment_request.amount,
        order_id=payment_request.order_id,
        description=payment_request.description,
        customer_email=payment_request.customer_email
    )

    if result["success"]:
        print(f"Paiement initié avec succès. Redirection URL: {result['redirect_url']}")
        return {
            "message": "Paiement initié avec succès",
            "redirect_url": result["redirect_url"],
            "transaction_id": result["transaction_id"]
        }
    else:
        print(f"Échec de l'initialisation du paiement: {result['message']}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result["message"]
        )

# --- Route pour gérer les notifications de paiement (IPN/Webhook) ---
@app.post("/api/payment/notification", summary="Recevoir les notifications de paiement (Webhook/IPN)")
async def paytech_ipn_handler(request: Request):
    """
    Endpoint pour recevoir les notifications de paiement instantanées (IPN/Webhooks)
    envoyées par la passerelle de paiement (PayTech, CinetPay, etc.).
    """
    try:
        # La passerelle peut envoyer les données en JSON ou en form-data.
        # Adaptez ceci en fonction de la documentation de votre passerelle.
        # Pour PayTech/CinetPay, c'est souvent du JSON ou du form-data.
        # Si c'est du JSON:
        data = await request.json()
        # Si c'est du form-data (décommenter et commenter la ligne ci-dessus):
        # data = await request.form() # Nécessite `python-multipart`

    except json.JSONDecodeError:
        print("Erreur: Corps de la requête IPN n'est pas un JSON valide.")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Corps de la requête invalide (JSON attendu).")
    except Exception as e:
        print(f"Erreur inattendue lors de la lecture des données IPN: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Erreur lors de la lecture des données de notification.")

    print(f"Notification de paiement reçue: {data}")

    # --- Étape CRITIQUE: Validation de l'authenticité de la notification ---
    # C'est essentiel pour la sécurité afin de s'assurer que la notification provient
    # bien de la passerelle de paiement et n'a pas été falsifiée.
    # La méthode de validation dépend de la passerelle (ex: signature HMAC, IP source).
    # Consultez la documentation de PayTech/CinetPay pour les détails.

    # Exemple conceptuel de vérification de signature (à adapter)
    # signature = request.headers.get("X-Paytech-Signature") # Nom de l'en-tête de signature
    # if not signature:
    #     print("Erreur: En-tête de signature manquant.")
    #     raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Signature manquante.")

    # # Reconstruire le message signé et vérifier la signature
    # # Ceci est un exemple, la logique exacte dépend de la passerelle
    # expected_signature = hmac.new(
    #     settings.PAYTECH_SECRET_KEY.encode('utf-8'),
    #     json.dumps(data, separators=(',', ':')).encode('utf-8'), # Assurez-vous que le JSON est exactement comme signé
    #     hashlib.sha256
    # ).hexdigest()

    # if not hmac.compare_digest(expected_signature, signature):
    #     print("Erreur: Signature de notification invalide.")
    #     raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Signature invalide.")

    # --- Traitement de la notification ---
    transaction_status = data.get("status") # Ex: "SUCCESS", "FAILED", "PENDING"
    transaction_id = data.get("transaction_id") # L'ID de transaction de la passerelle
    order_id = data.get("ref_command") # Votre référence de commande que vous avez envoyée

    if not transaction_id or not order_id or not transaction_status:
        print("Erreur: Données de notification essentielles manquantes.")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Données de notification essentielles manquantes.")

    # --- (Optionnel mais fortement recommandé) Vérification du statut auprès de la passerelle ---
    # Pour une sécurité maximale, après avoir reçu l'IPN, interrogez la passerelle
    # pour confirmer le statut de la transaction avec l'ID de transaction.
    # Cela permet de se prémunir contre les notifications falsifiées ou erronées.
    # verification_result = verify_payment_status(transaction_id)
    # if not verification_result["success"] or verification_result["status"] != transaction_status:
    #     print(f"Alerte: Incohérence de statut pour transaction {transaction_id}. IPN: {transaction_status}, Vérifié: {verification_result.get('status')}")
    #     # Ici, vous pourriez déclencher une alerte ou un processus de réconciliation manuel
    #     raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Statut de transaction incohérent après vérification.")


    # --- Mise à jour de votre base de données ---
    # C'est ici que vous mettez à jour le statut de votre commande/facture dans votre propre base de données.
    # Assurez-vous que cette opération est idempotente (peut être appelée plusieurs fois sans effet secondaire).
    if transaction_status == "SUCCESS":
        print(f"Transaction {transaction_id} pour commande {order_id} réussie. Mise à jour de la base de données...")
        # Exemple: update_order_status(order_id, "paid", transaction_id)
        pass # Remplacez par votre logique de mise à jour DB
    elif transaction_status == "FAILED":
        print(f"Transaction {transaction_id} pour commande {order_id} échouée. Mise à jour de la base de données...")
        # Exemple: update_order_status(order_id, "failed")
        pass # Remplacez par votre logique de mise à jour DB
    else:
        print(f"Statut de transaction {transaction_status} non géré pour {transaction_id}.")
        # Gérer d'autres statuts comme "PENDING", "CANCELLED", etc.

    # --- Retourner une réponse HTTP 200 OK à la passerelle ---
    # Il est crucial de renvoyer un statut 200 OK pour indiquer à la passerelle que
    # vous avez bien reçu et traité la notification. Sinon, elle pourrait la renvoyer.
    return {"message": "Notification de paiement reçue et traitée avec succès."}




@app.get("/")
def read_root():
    """
    Route racine de l'API.
    """
    return {"message": "Bienvenue sur l'API Backend de Hebergement"}
