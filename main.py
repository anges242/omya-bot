import os
import json
import asyncio
from datetime import datetime
import anthropic
from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes
from notion_client import Client as NotionClient

# Configuration
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
NOTION_TOKEN = os.environ.get("NOTION_TOKEN")

# IDs des bases Notion
NOTION_TRANSACTIONS_DB = os.environ.get("NOTION_TRANSACTIONS_DB")
NOTION_CLIENTS_DB = os.environ.get("NOTION_CLIENTS_DB")
NOTION_SESSIONS_DB = os.environ.get("NOTION_SESSIONS_DB")
NOTION_INFRA_DB = os.environ.get("NOTION_INFRA_DB")

# Clients
notion = NotionClient(auth=NOTION_TOKEN)
anthropic_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

SYSTEM_PROMPT = """Tu es l'assistant de gestion OMYA. Tu aides à gérer une entreprise de formation et services digitaux à Pointe-Noire, Congo.

Tu reçois des messages en français naturel et tu dois:
1. Comprendre l'intention (enregistrer une transaction, ajouter un client, créer une session, etc.)
2. Extraire les données importantes
3. Retourner un JSON structuré avec l'action à effectuer

ACTIONS DISPONIBLES:
- "add_transaction": ajouter revenus ou dépenses
- "add_client": ajouter apprenant ou client digital
- "add_session": créer une session de formation
- "add_infra": ajouter matériel ou fournisseur
- "query_transactions": consulter finances
- "query_clients": consulter clients
- "query_sessions": consulter sessions
- "query_infra": consulter infrastructure
- "daily_report": rapport du jour
- "unknown": message incompréhensible

TYPES DE TRANSACTIONS:
- Revenu Formation, Revenu Digital, Dépense, Transfert

CANAUX:
- Cash, Orange Money, MTN MoMo

CATÉGORIES DÉPENSES:
- Fournitures, Internet, Transport, Loyer, Matériel, Marketing, Salaire, Imprévu

MODULES FORMATION:
- Word, Excel, PowerPoint, Windows, IA

SERVICES DIGITAUX:
- Site Vitrine, Agent WhatsApp, Pack Notion

Réponds UNIQUEMENT en JSON valide, sans texte avant ou après.

EXEMPLES:

Message: "Reçu 25000F de Jean Moukala pour formation Word en cash"
Réponse: {
  "action": "add_transaction",
  "data": {
    "libelle": "Paiement formation Word - Jean Moukala",
    "type": "Revenu Formation",
    "montant": 25000,
    "canal": "Cash",
    "categorie": "Formation",
    "notes": "Jean Moukala"
  },
  "message": "✅ PAIEMENT ENREGISTRÉ\n👤 Client : Jean Moukala\n📚 Formation : Word\n💵 Montant : 25 000 F\n💳 Canal : Cash"
}

Message: "Nouvelle inscription Paul Banzouzi PowerPoint 35000F paiement en 2 fois acompte 20000F"
Réponse: {
  "action": "add_client",
  "data": {
    "nom": "Paul Banzouzi",
    "type": "Apprenant",
    "service": "PowerPoint",
    "montant_total": 35000,
    "montant_paye": 20000,
    "reste_du": 15000,
    "statut_paiement": "Partiel",
    "statut": "Actif"
  },
  "message": "✅ INSCRIPTION ENREGISTRÉE\n👤 Paul Banzouzi\n📚 PowerPoint\n💰 Total : 35 000 F\n💵 Payé : 20 000 F\n🔴 Reste : 15 000 F"
}

Message: "Dépense internet Airtel 20000F"
Réponse: {
  "action": "add_transaction",
  "data": {
    "libelle": "Internet Airtel mensuel",
    "type": "Dépense",
    "montant": 20000,
    "canal": "Cash",
    "categorie": "Internet",
    "notes": "Abonnement mensuel"
  },
  "message": "✅ DÉPENSE ENREGISTRÉE\n📂 Internet\n💸 20 000 F\n📉 Charge mensuelle enregistrée"
}

Message: "rapport du jour"
Réponse: {
  "action": "daily_report",
  "data": {},
  "message": ""
}

Message: "liste clients"
Réponse: {
  "action": "query_clients",
  "data": {},
  "message": ""
}"""


async def parse_message(text: str) -> dict:
    """Utilise Claude pour comprendre le message"""
    response = anthropic_client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1000,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": text}]
    )
    
    content = response.content[0].text.strip()
    # Nettoyer le JSON
    if content.startswith("```"):
        content = content.split("```")[1]
        if content.startswith("json"):
            content = content[4:]
    
    return json.loads(content)


def add_transaction(data: dict) -> str:
    """Ajoute une transaction dans Notion"""
    today = datetime.now().strftime("%Y-%m-%d")
    
    notion.pages.create(
        parent={"database_id": NOTION_TRANSACTIONS_DB},
        properties={
            "Libellé": {"title": [{"text": {"content": data.get("libelle", "Transaction")}}]},
            "Type": {"select": {"name": data.get("type", "Dépense")}},
            "Montant": {"number": data.get("montant", 0)},
            "Canal": {"select": {"name": data.get("canal", "Cash")}},
            "Catégorie": {"select": {"name": data.get("categorie", "Imprévu")}},
            "Date": {"date": {"start": today}},
            "Notes": {"rich_text": [{"text": {"content": data.get("notes", "")}}]},
        }
    )
    return "ok"


def add_client(data: dict) -> str:
    """Ajoute un client/apprenant dans Notion"""
    today = datetime.now().strftime("%Y-%m-%d")
    
    notion.pages.create(
        parent={"database_id": NOTION_CLIENTS_DB},
        properties={
            "Nom": {"title": [{"text": {"content": data.get("nom", "Client")}}]},
            "Type": {"select": {"name": data.get("type", "Apprenant")}},
            "Service": {"select": {"name": data.get("service", "Word")}},
            "Montant Total": {"number": data.get("montant_total", 0)},
            "Montant Payé": {"number": data.get("montant_paye", 0)},
            "Reste Dû": {"number": data.get("reste_du", 0)},
            "Statut Paiement": {"select": {"name": data.get("statut_paiement", "Non Payé")}},
            "Statut": {"select": {"name": data.get("statut", "Actif")}},
            "Date Inscription": {"date": {"start": today}},
            "Téléphone": {"rich_text": [{"text": {"content": data.get("telephone", "")}}]},
            "Notes": {"rich_text": [{"text": {"content": data.get("notes", "")}}]},
        }
    )
    return "ok"


def add_session(data: dict) -> str:
    """Ajoute une session de formation dans Notion"""
    notion.pages.create(
        parent={"database_id": NOTION_SESSIONS_DB},
        properties={
            "Session": {"title": [{"text": {"content": data.get("session", "Session")}}]},
            "Module": {"select": {"name": data.get("module", "Word")}},
            "Horaire": {"rich_text": [{"text": {"content": data.get("horaire", "")}}]},
            "Statut": {"select": {"name": data.get("statut", "Programmée")}},
            "Nombre Apprenants": {"number": data.get("nombre_apprenants", 0)},
            "Notes": {"rich_text": [{"text": {"content": data.get("notes", "")}}]},
        }
    )
    return "ok"


def get_daily_report() -> str:
    """Génère le rapport du jour"""
    today = datetime.now().strftime("%Y-%m-%d")
    date_affichage = datetime.now().strftime("%d/%m/%Y")
    
    # Récupérer transactions du jour
    results = notion.databases.query(
        database_id=NOTION_TRANSACTIONS_DB,
        filter={
            "property": "Date",
            "date": {"equals": today}
        }
    )
    
    revenus_formation = 0
    revenus_digital = 0
    depenses = 0
    
    for page in results["results"]:
        props = page["properties"]
        montant = props.get("Montant", {}).get("number", 0) or 0
        type_tx = props.get("Type", {}).get("select", {})
        type_name = type_tx.get("name", "") if type_tx else ""
        
        if type_name == "Revenu Formation":
            revenus_formation += montant
        elif type_name == "Revenu Digital":
            revenus_digital += montant
        elif type_name == "Dépense":
            depenses += montant
    
    total_revenus = revenus_formation + revenus_digital
    net = total_revenus - depenses
    
    # Clients avec reste dû
    clients_results = notion.databases.query(
        database_id=NOTION_CLIENTS_DB,
        filter={
            "property": "Statut Paiement",
            "select": {"does_not_equal": "Soldé"}
        }
    )
    
    nb_debiteurs = len(clients_results["results"])
    total_dus = sum(
        (p["properties"].get("Reste Dû", {}).get("number", 0) or 0)
        for p in clients_results["results"]
    )
    
    rapport = f"""📊 RAPPORT OMYA — {date_affichage}

💰 REVENUS DU JOUR
   📚 Formations    : {revenus_formation:,.0f} F
   🌐 Digital       : {revenus_digital:,.0f} F
   ─────────────────────
   Total revenus    : {total_revenus:,.0f} F

💸 Dépenses du jour : {depenses:,.0f} F

✅ Net du jour      : {'+' if net >= 0 else ''}{net:,.0f} F

👥 Clients débiteurs : {nb_debiteurs} personnes
💳 Total dû         : {total_dus:,.0f} F"""
    
    return rapport


def get_clients_list() -> str:
    """Retourne la liste des clients actifs"""
    results = notion.databases.query(
        database_id=NOTION_CLIENTS_DB,
        filter={
            "property": "Statut",
            "select": {"equals": "Actif"}
        }
    )
    
    if not results["results"]:
        return "📋 Aucun client actif pour le moment."
    
    liste = "📋 CLIENTS & APPRENANTS ACTIFS\n\n"
    for page in results["results"]:
        props = page["properties"]
        nom = props.get("Nom", {}).get("title", [{}])
        nom = nom[0].get("text", {}).get("content", "?") if nom else "?"
        service_obj = props.get("Service", {}).get("select", {})
        service = service_obj.get("name", "?") if service_obj else "?"
        statut_obj = props.get("Statut Paiement", {}).get("select", {})
        statut = statut_obj.get("name", "?") if statut_obj else "?"
        reste = props.get("Reste Dû", {}).get("number", 0) or 0
        
        emoji = "✅" if statut == "Soldé" else "🔴" if statut == "Non Payé" else "🟡"
        liste += f"{emoji} {nom} | {service} | {reste:,.0f} F dû\n"
    
    return liste


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Traite chaque message reçu"""
    text = update.message.text
    
    # Indicateur de traitement
    await update.message.reply_text("⏳ Traitement en cours...")
    
    try:
        # Claude analyse le message
        parsed = await parse_message(text)
        action = parsed.get("action", "unknown")
        data = parsed.get("data", {})
        message = parsed.get("message", "")
        
        if action == "add_transaction":
            add_transaction(data)
            await update.message.reply_text(message)
            
        elif action == "add_client":
            add_client(data)
            # Enregistrer aussi le paiement comme transaction
            if data.get("montant_paye", 0) > 0:
                add_transaction({
                    "libelle": f"Paiement {data.get('service')} - {data.get('nom')}",
                    "type": "Revenu Formation" if data.get("type") == "Apprenant" else "Revenu Digital",
                    "montant": data.get("montant_paye", 0),
                    "canal": "Cash",
                    "categorie": "Formation" if data.get("type") == "Apprenant" else "Digital",
                    "notes": data.get("nom", "")
                })
            await update.message.reply_text(message)
            
        elif action == "add_session":
            add_session(data)
            await update.message.reply_text(message)
            
        elif action == "daily_report":
            rapport = get_daily_report()
            await update.message.reply_text(rapport)
            
        elif action == "query_clients":
            liste = get_clients_list()
            await update.message.reply_text(liste)
            
        elif action == "unknown":
            await update.message.reply_text(
                "❓ Je n'ai pas compris. Essaie par exemple :\n"
                "• 'Reçu 25000F de Jean pour Word'\n"
                "• 'Dépense internet 20000F'\n"
                "• 'rapport du jour'\n"
                "• 'liste clients'"
            )
        else:
            await update.message.reply_text(
                f"✅ Action '{action}' reçue.\n{message}"
            )
            
    except Exception as e:
        await update.message.reply_text(
            f"❌ Erreur : {str(e)}\nRéessaie avec un message plus simple."
        )


def main():
    """Lance le bot"""
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    print("🚀 Bot OMYA démarré...")
    app.run_polling()


if __name__ == "__main__":
    main()
