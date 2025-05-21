import os
from quart import Quart, request, jsonify, render_template
import asyncio
import json
from dotenv import load_dotenv
import logging
import discord
from datetime import datetime
from bot import bot

# Configuration du logging
logging.basicConfig(
    format='%(asctime)s | %(levelname)s | %(message)s',
    level=logging.INFO,
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)

# Configuration de Quart
app = Quart(__name__)
app.config.update(
    PROVIDE_AUTOMATIC_OPTIONS=True,
    SECRET_KEY=os.urandom(24),
    TEMPLATES_AUTO_RELOAD=True
)

load_dotenv()

# Configuration du port pour Render
port = int(os.environ.get("PORT", 5050))

# Fichiers de stockage
MESSAGES_FILE = 'saved_messages.json'
ROLES_FILE = 'saved_roles.json'
MATCHS_FILE = 'matchs.json'

def load_messages():
    if os.path.exists(MESSAGES_FILE):
        with open(MESSAGES_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []

def save_messages(messages):
    with open(MESSAGES_FILE, 'w', encoding='utf-8') as f:
        json.dump(messages, f, ensure_ascii=False, indent=4)

def load_roles():
    if os.path.exists(ROLES_FILE):
        with open(ROLES_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []

def save_roles(roles):
    with open(ROLES_FILE, 'w', encoding='utf-8') as f:
        json.dump(roles, f, ensure_ascii=False, indent=4)

def load_matchs():
    if os.path.exists(MATCHS_FILE):
        with open(MATCHS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []

def save_matchs(matchs):
    with open(MATCHS_FILE, 'w', encoding='utf-8') as f:
        json.dump(matchs, f, ensure_ascii=False, indent=4)

@app.route("/")
async def home():
    return await render_template("admin.html")

@app.route("/roles")
async def get_roles():
    roles = load_roles()
    return jsonify(roles)

@app.route("/roles", methods=["POST"])
async def save_role():
    data = await request.get_json()
    roles = load_roles()
    roles.append(data)
    save_roles(roles)
    return jsonify({"success": True})

@app.route("/roles/<int:index>", methods=["DELETE"])
async def delete_role(index):
    roles = load_roles()
    if 0 <= index < len(roles):
        roles.pop(index)
        save_roles(roles)
        return jsonify({"success": True})
    return jsonify({"error": "Rôle non trouvé"}), 404

@app.route("/messages-history")
async def get_messages():
    messages = load_messages()
    return jsonify(messages)

@app.route("/messages-history/<int:index>", methods=["DELETE"])
async def delete_message(index):
    messages = load_messages()
    if 0 <= index < len(messages):
        messages.pop(index)
        save_messages(messages)
        return jsonify({"success": True})
    return jsonify({"error": "Message non trouvé"}), 404

@app.route("/send", methods=["POST"])
async def send_message():
    try:
        data = await request.get_json()
        message = data.get("message", "")
        platforms = data.get("platforms", [])
        roleIds = data.get("roleIds", [])
        reactions = data.get("reactions", [])

        if not message:
            return jsonify({"error": "Le message est requis"}), 400

        if not platforms:
            return jsonify({"error": "Au moins une plateforme doit être sélectionnée"}), 400

        sent_count = 0
        failed_users = []

        # Envoyer sur Discord si sélectionné
        if "discord" in platforms:
            from bot import send_message_to_channel
            discord_count, failed = await send_message_to_channel(message, roleIds, reactions)
            sent_count += discord_count
            failed_users.extend(failed)

        # Sauvegarder le message
        messages = load_messages()
        messages.append({
            "message": message,
            "timestamp": datetime.now().isoformat(),
            "platforms": platforms,
            "roleIds": roleIds,
            "reactions": reactions,
            "sent_count": sent_count,
            "stats": {
                "total_reactions": 0,
                "reactions_by_type": {}
            }
        })
        save_messages(messages)

        response = {
            "success": True,
            "sent_count": sent_count
        }
        
        if failed_users:
            response["warning"] = f"Impossible d'envoyer le message à {len(failed_users)} utilisateurs car ils ont désactivé les messages privés. Ils doivent activer les messages privés dans leurs paramètres Discord (Confidentialité et sécurité)."
            response["failed_users"] = failed_users

        return jsonify(response)

    except Exception as e:
        logger.error(f"Erreur lors de l'envoi du message : {str(e)}", exc_info=True)
        return jsonify({"error": str(e)}), 500

@app.route("/discord-roles")
async def get_discord_roles():
    try:
        # Attendre que le bot soit connecté et ait accès aux serveurs
        if not bot.is_ready():
            return jsonify({"error": "Le bot n'est pas encore prêt"}), 503

        # Récupérer le premier serveur (guild) où le bot est présent
        if not bot.guilds:
            return jsonify({"error": "Le bot n'est pas présent dans aucun serveur"}), 404

        guild = bot.guilds[0]
        roles = []
        
        # Récupérer tous les rôles du serveur
        for role in guild.roles:
            if role.name != "@everyone":  # Exclure le rôle @everyone
                roles.append({
                    "id": str(role.id),
                    "name": role.name,
                    "color": str(role.color)
                })
        
        return jsonify(roles)
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des rôles Discord : {str(e)}", exc_info=True)
        return jsonify({"error": str(e)}), 500

@app.route('/matchs')
async def get_matchs():
    return jsonify(load_matchs())

@app.route('/matchs', methods=['POST'])
async def add_match():
    data = await request.get_json()
    titre = data.get('titre', '').strip()
    lien = data.get('lien', '').strip()
    if not titre or not lien:
        return jsonify({'error': 'Titre et lien requis'}), 400
    matchs = load_matchs()
    matchs.append({'titre': titre, 'lien': lien})
    save_matchs(matchs)
    return jsonify({'success': True})

@app.route('/matchs/<int:index>', methods=['DELETE'])
async def delete_match(index):
    matchs = load_matchs()
    if 0 <= index < len(matchs):
        matchs.pop(index)
        save_matchs(matchs)
        return jsonify({'success': True})
    return jsonify({'error': 'Match non trouvé'}), 404

@app.route('/discord-channels')
async def get_discord_channels():
    try:
        if not bot.is_ready():
            return jsonify({'error': 'Le bot n\'est pas encore prêt'}), 503
        if not bot.guilds:
            return jsonify({'error': 'Le bot n\'est dans aucun serveur'}), 404
        guild = bot.guilds[0]
        channels = [
            {'id': str(c.id), 'name': c.name}
            for c in guild.text_channels
        ]
        return jsonify(channels)
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des salons Discord : {str(e)}", exc_info=True)
        return jsonify({'error': str(e)}), 500

@app.route('/send-channel-message', methods=['POST'])
async def send_channel_message():
    try:
        data = await request.get_json()
        channel_id = data.get('channel_id')
        message = data.get('message', '')
        if not channel_id or not message:
            return jsonify({'error': 'Salon et message requis'}), 400
        from bot import send_message_to_channel_id
        result = await send_message_to_channel_id(channel_id, message)
        if result:
            return jsonify({'success': True})
        else:
            return jsonify({'error': 'Impossible d\'envoyer le message'}), 500
    except Exception as e:
        logger.error(f"Erreur lors de l'envoi du message dans le salon : {str(e)}", exc_info=True)
        return jsonify({'error': str(e)}), 500

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=port, debug=True)
