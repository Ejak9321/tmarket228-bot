import os
import asyncio
import logging
from uuid import uuid4
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputFile
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes,
)

# Charger les variables d'environnement
load_dotenv()

# === Configuration ===
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_IDS = list(map(int, os.getenv("ADMIN_IDS", "").split(",")))
CHANNEL_ID = os.getenv("CHANNEL_ID")

if not BOT_TOKEN:
    raise ValueError("Le token du bot (BOT_TOKEN) n'est pas défini dans le fichier .env.")
if not ADMIN_IDS:
    raise ValueError("Les identifiants des administrateurs (ADMIN_IDS) ne sont pas définis dans le fichier .env.")
if not CHANNEL_ID:
    raise ValueError("L'identifiant du canal (CHANNEL_ID) n'est pas défini dans le fichier .env.")

# Configure logging
logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO
)

# Stockage temporaire
user_data = {}
products = []
pending_requests = {}  # Stockage des demandes en attente pour validation
approved_sellers = set()  # Liste des vendeurs approuvés

# Assurer l'existence des dossiers nécessaires
os.makedirs("photos", exist_ok=True)
os.makedirs("static", exist_ok=True)


# Fonction pour obtenir l'image statique
def get_static_image():
    image_path = os.path.join("static", "image_a_reposter.jpg.png")
    if not os.path.exists(image_path):
        with open(image_path, "wb") as img:
            img.write(b"Placeholder for validation image")  # Image par défaut
    return image_path


# === Commande /start ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    welcome_message = (
        "Bienvenue sur TMarket228bot !\n"
        "1️⃣ Cliquez sur 'Devenir vendeur' pour vendre sur notre canal.\n"
        "2️⃣ Cliquez sur 'Demander une collaboration' pour soumettre une proposition."
    )
    keyboard = [
        [InlineKeyboardButton("📦 Devenir vendeur", callback_data="devenir_vendeur")],
        [InlineKeyboardButton("🤝 Demander une collaboration", callback_data="demander_collab")],
        [InlineKeyboardButton("🛠 Gérer mes produits", callback_data="gerer_produits")],
        [InlineKeyboardButton("📄 Voir mes produits", callback_data="voir_produits")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await context.bot.send_message(chat_id=chat_id, text=welcome_message, reply_markup=reply_markup)


# === Gestion des boutons ===
async def handle_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "devenir_vendeur":
        image_path = get_static_image()
        message = (
            "Pour devenir vendeur, veuillez remplir les conditions suivantes :\n"
            "1️⃣ Repostez l'image suivante sur vos réseaux sociaux : WhatsApp, TikTok et Facebook.\n"
            "2️⃣ Envoyez-nous une capture d'écran de vos publications ici.\n\n"
            "Appuyez sur le bouton ci-dessous une fois les conditions remplies."
        )
        keyboard = [[InlineKeyboardButton("✅ J'ai rempli les conditions", callback_data="conditions_remplies")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await context.bot.send_photo(chat_id=query.message.chat_id, photo=InputFile(image_path), caption=message,
                                     reply_markup=reply_markup)

    elif query.data == "conditions_remplies":
        chat_id = query.message.chat_id
        pending_requests[chat_id] = {
            "user": query.from_user,
            "status": "pending",
        }
        await query.edit_message_text(
            text="Merci ! Votre demande a été envoyée. Elle sera examinée par un administrateur.")

        # Notifier les admins
        admin_message = (
            f"Nouvelle demande de devenir vendeur :\n"
            f"Utilisateur : {query.from_user.first_name} (@{query.from_user.username})\n"
            f"ID : {chat_id}\n"
            f"Utilisez les boutons ci-dessous pour approuver ou rejeter."
        )
        keyboard = [
            [
                InlineKeyboardButton("✅ Approuver", callback_data=f"approuver_{chat_id}"),
                InlineKeyboardButton("❌ Rejeter", callback_data=f"rejeter_{chat_id}"),
            ]
        ]
        for admin_id in ADMIN_IDS:
            await context.bot.send_message(chat_id=admin_id, text=admin_message,
                                           reply_markup=InlineKeyboardMarkup(keyboard))

    elif query.data.startswith("approuver_"):
        chat_id = int(query.data.split("_")[1])
        if chat_id in pending_requests:
            approved_sellers.add(chat_id)
            del pending_requests[chat_id]
            await context.bot.send_message(chat_id=chat_id,
                                           text="Félicitations ! Vous êtes maintenant vendeur. Vous pouvez publier vos produits.")
            await query.edit_message_text(text=f"L'utilisateur {chat_id} a été approuvé.")

    elif query.data.startswith("rejeter_"):
        chat_id = int(query.data.split("_")[1])
        if chat_id in pending_requests:
            del pending_requests[chat_id]
            await context.bot.send_message(chat_id=chat_id,
                                           text="Votre demande a été rejetée. Vous pouvez réessayer plus tard.")
            await query.edit_message_text(text=f"L'utilisateur {chat_id} a été rejeté.")

    elif query.data == "gerer_produits":
        chat_id = query.message.chat_id
        if chat_id not in approved_sellers:
            await query.edit_message_text(
                text="Vous devez être approuvé en tant que vendeur pour accéder à cette fonctionnalité.")
            return

        message = (
            "Gestion de vos produits :\n"
            "- Ajouter un produit\n"
            "- Modifier un produit\n"
            "- Supprimer un produit\n\n"
            "Choisissez une option :"
        )
        keyboard = [
            [InlineKeyboardButton("➕ Ajouter un produit", callback_data="ajouter_produit")],
            [InlineKeyboardButton("✏️ Modifier un produit", callback_data="modifier_produit")],
            [InlineKeyboardButton("❌ Supprimer un produit", callback_data="supprimer_produit")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text=message, reply_markup=reply_markup)


# === Gestion des messages textes ===
async def handle_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if chat_id not in approved_sellers:
        await context.bot.send_message(chat_id=chat_id,
                                       text="Vous devez être approuvé en tant que vendeur pour utiliser cette fonctionnalité.")
        return

    user_action = context.user_data.get("action", None)

    if user_action == "ajouter_produit":
        details = update.message.text.split(",")
        if len(details) == 5:
            name, description, category, price, whatsapp = map(str.strip, details)

            # Validation du numéro WhatsApp
            if not (whatsapp.startswith("+228") and len(whatsapp[1:]) == 8 and whatsapp[1:].isdigit()):
                await context.bot.send_message(
                    chat_id=chat_id,
                    text="❌ Le numéro de WhatsApp doit commencer par +228 et être suivi de 8 chiffres.",
                )
                return

            new_product = {
                "id": str(uuid4()),
                "name": name,
                "description": description,
                "category": category,
                "price": price,
                "whatsapp": whatsapp,
                "photos": context.user_data.get("pending_photos", []),
            }
            products.append(new_product)
            context.user_data["action"] = None
            context.user_data["pending_photos"] = []
            await context.bot.send_message(
                chat_id=chat_id,
                text=f"✅ Produit ajouté :\n\nNom : {name}\nDescription : {description}\n"
                     f"Catégorie : {category}\nPrix : {price} FCFA\nWhatsApp : {whatsapp}",
            )
        else:
            await context.bot.send_message(
                chat_id=chat_id,
                text="❌ Format invalide. Veuillez réessayer en suivant le format indiqué.",
            )


# === Gestion des photos ===
async def handle_photos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if chat_id not in approved_sellers:
        await context.bot.send_message(chat_id=chat_id,
                                       text="Vous devez être approuvé en tant que vendeur pour utiliser cette fonctionnalité.")
        return

    photo = update.message.photo[-1]
    file = await photo.get_file()
    file_path = os.path.join("photos", f"{uuid4()}.jpg")
    await file.download_to_drive(file_path)

    if "pending_photos" in context.user_data:
        context.user_data["pending_photos"].append(file_path)

    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="✅ Photo ajoutée avec succès. Continuez d'envoyer des photos ou soumettez les détails du produit.",
    )


# === Lancement du bot ===
async def main():
    application = Application.builder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(handle_buttons))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_messages))
    application.add_handler(MessageHandler(filters.PHOTO, handle_photos))

    try:
        await application.run_polling()
    except Exception as ex:
        logging.error(f"Erreur lors de l'exécution du bot : {ex}")


# Point d'entrée
if __name__ == "__main__":
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(main())
    except RuntimeError as error:
        logging.error(f"Erreur : {error}. La boucle d'événements est déjà en cours d'exécution.")
    finally:
        loop.close()
