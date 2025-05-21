import os
from dotenv import load_dotenv
import discord
from discord.ext import commands
import json
import threading
import requests
from datetime import datetime
import asyncio

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

if not TOKEN:
    print("Erreur : Le token Discord est introuvable ou vide.")
    exit(1)

print(f"TOKEN chargé : {TOKEN}")
print(f"Longueur du token : {len(TOKEN)}")

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.reactions = True

bot = commands.Bot(command_prefix="!", intents=intents)

def load_messages_history():
    try:
        with open("messages_history.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []

def save_messages_history(history):
    with open("messages_history.json", "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)

def update_message_stats(message_id, stats):
    history = load_messages_history()
    for message in history:
        if any(msg_id == message_id for msg_id in message["message_ids"]):
            message["stats"] = stats
            save_messages_history(history)
            # Mettre à jour les stats via l'API
            try:
                requests.post("http://localhost:5050/update-message-stats", json={
                    "messageId": message["id"],
                    "stats": stats
                })
            except:
                pass
            break

@bot.event
async def on_ready():
    print(f"Connecté en tant que {bot.user}")

@bot.event
async def on_member_update(before, after):
    foot_role = discord.utils.get(after.guild.roles, name="Foot")
    if foot_role and foot_role in after.roles and foot_role not in before.roles:
        try:
            await after.send(
                "Bienvenue ! Sur ce serveur, le mot 'match' est remplacé par 'fête' pour éviter les bannissements.\n"
                "Pour recevoir les liens de diffusion, il te suffit de m'envoyer la commande `!match` en message privé."
            )
        except discord.Forbidden:
            print(f"Impossible d'envoyer un DM à {after.name}")

@bot.event
async def on_reaction_add(reaction, user):
    if user.bot:
        return
    
    if isinstance(reaction.message.channel, discord.DMChannel):
        history = load_messages_history()
        for message in history:
            if str(reaction.message.id) in message["message_ids"]:
                stats = message["stats"]
                stats["total_reactions"] += 1
                reaction_type = str(reaction.emoji)
                stats["reactions_by_type"][reaction_type] = stats["reactions_by_type"].get(reaction_type, 0) + 1
                update_message_stats(str(reaction.message.id), stats)
                break

@bot.event
async def on_reaction_remove(reaction, user):
    if user.bot:
        return
    
    if isinstance(reaction.message.channel, discord.DMChannel):
        history = load_messages_history()
        for message in history:
            if str(reaction.message.id) in message["message_ids"]:
                stats = message["stats"]
                stats["total_reactions"] -= 1
                reaction_type = str(reaction.emoji)
                stats["reactions_by_type"][reaction_type] = max(0, stats["reactions_by_type"].get(reaction_type, 0) - 1)
                update_message_stats(str(reaction.message.id), stats)
                break

@bot.event
async def on_message(message):
    await bot.process_commands(message)

@bot.command()
async def match(ctx):
    if isinstance(ctx.channel, discord.DMChannel):
        try:
            with open("matchs.json", "r", encoding="utf-8") as f:
                matchs = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            matchs = []
        if matchs:
            for m in matchs:
                await ctx.send(f"{m['titre']} : {m['lien']}")
        else:
            await ctx.send("Il n'y a pas encore de liens pour les matchs. Merci d'attendre l'annonce dans le salon <#1369658120976076892> du serveur.")
    else:
        await ctx.send("Cette commande ne fonctionne qu'en message privé avec moi !")

@bot.command()
async def casino(ctx):
    # Vérifier si la commande est exécutée par un administrateur
    if not ctx.author.guild_permissions.administrator:
        await ctx.send("❌ Vous n'avez pas la permission d'utiliser cette commande.")
        return

    # Vérifier les permissions du bot
    bot_member = ctx.guild.get_member(bot.user.id)
    if not bot_member.guild_permissions.manage_roles:
        await ctx.send("❌ Je n'ai pas la permission de gérer les rôles. Veuillez m'attribuer le rôle 'Gestionnaire de rôles'.")
        return

    # Récupérer les rôles
    novice_role = discord.utils.get(ctx.guild.roles, name="Novice AOTV")
    casino_role = discord.utils.get(ctx.guild.roles, name="Casino")

    if not novice_role or not casino_role:
        await ctx.send("❌ Les rôles 'Novice AOTV' ou 'Casino' n'ont pas été trouvés.")
        return

    # Vérifier la hiérarchie des rôles
    bot_top_role = bot_member.top_role
    if bot_top_role.position <= novice_role.position or bot_top_role.position <= casino_role.position:
        await ctx.send("❌ Mon rôle doit être placé plus haut dans la hiérarchie que les rôles 'Novice AOTV' et 'Casino'.")
        return

    # Compteur pour suivre les modifications
    count = 0
    failed_members = []

    # Parcourir tous les membres du serveur
    for member in ctx.guild.members:
        # Vérifier si le membre a uniquement le rôle Novice AOTV
        if len(member.roles) == 2 and novice_role in member.roles:  # 2 car @everyone est toujours présent
            try:
                await member.add_roles(casino_role)
                count += 1
            except discord.Forbidden:
                failed_members.append(member.name)
            except Exception as e:
                await ctx.send(f"❌ Une erreur s'est produite lors de la modification des rôles de {member.name}: {str(e)}")
                return

    if failed_members:
        await ctx.send(f"⚠️ Le rôle Casino a été attribué à {count} membres, mais je n'ai pas pu modifier les rôles pour : {', '.join(failed_members)}")
    else:
        await ctx.send(f"✅ Le rôle Casino a été attribué à {count} membres ayant uniquement le rôle Novice AOTV.")

async def send_message_to_channel(message, role_ids, reactions=None):
    if reactions is None:
        reactions = []
    try:
        # Récupérer le premier serveur (guild) où le bot est présent
        guild = bot.guilds[0]
        print(f"Tentative d'envoi de messages dans le serveur : {guild.name}")
        
        # Vérifier les permissions du bot
        bot_member = guild.get_member(bot.user.id)
        if not bot_member:
            print("Erreur : Impossible de trouver le bot dans le serveur")
            return 0, []
            
        print(f"Permissions du bot : {bot_member.guild_permissions.value}")
        print(f"Rôles du bot : {[role.name for role in bot_member.roles]}")
            
        sent_count = 0
        failed_users = []
        total_members = 0

        # Compter le nombre total de membres à contacter
        for role_id in role_ids:
            role = guild.get_role(int(role_id))
            if role:
                total_members += len(role.members)

        # Vérifier si le nombre de membres est raisonnable
        if total_members > 50:
            print(f"Attention : Tentative d'envoi à {total_members} membres. Limite recommandée : 50 membres maximum.")
            return 0, ["Trop de destinataires. Limite recommandée : 50 membres maximum."]

        # Pour chaque rôle sélectionné
        for role_id in role_ids:
            role = guild.get_role(int(role_id))
            if role:
                print(f"Traitement du rôle : {role.name}")
                print(f"Nombre de membres avec ce rôle : {len(role.members)}")
                # Pour chaque membre ayant ce rôle
                for member in role.members:
                    try:
                        print(f"Tentative d'envoi à {member.name} (ID: {member.id})")
                        print(f"Rôles de l'utilisateur : {[r.name for r in member.roles]}")
                        
                        # Ajouter un délai entre chaque message
                        await asyncio.sleep(2)  # Attendre 2 secondes entre chaque message
                        
                        # Envoyer le message en DM avec un timeout
                        async with asyncio.timeout(5):  # 5 secondes de timeout
                            msg_obj = await member.send(message)
                            print(f"Message envoyé avec succès à {member.name}")
                            sent_count += 1
                            # Ajouter les réactions sélectionnées
                            for emoji in reactions:
                                try:
                                    await msg_obj.add_reaction(emoji)
                                except Exception as e:
                                    print(f"Impossible d'ajouter la réaction {emoji} à {member.name}: {str(e)}")
                    except discord.Forbidden as e:
                        print(f"Erreur 403 (Forbidden) pour {member.name}: {str(e)}")
                        failed_users.append(member.name)
                    except asyncio.TimeoutError:
                        print(f"Timeout lors de l'envoi du message à {member.name}")
                        failed_users.append(member.name)
                    except Exception as e:
                        print(f"Erreur inattendue pour {member.name}: {str(e)}")
                        failed_users.append(member.name)
            else:
                print(f"Rôle non trouvé avec l'ID : {role_id}")

        print(f"Résumé : {sent_count} messages envoyés avec succès, {len(failed_users)} échecs")
        return sent_count, failed_users
    except Exception as e:
        print(f"Erreur générale lors de l'envoi des messages: {str(e)}")
        return 0, []

async def send_message_to_channel_id(channel_id, message):
    try:
        channel = bot.get_channel(int(channel_id))
        if channel and hasattr(channel, 'send'):
            # Remplacer les mentions @username par les mentions Discord
            guild = channel.guild
            for member in guild.members:
                if f"@{member.name}" in message:
                    message = message.replace(f"@{member.name}", member.mention)
            
            await channel.send(message)
            return True
        else:
            print(f"Salon introuvable ou non textuel : {channel_id}")
            return False
    except Exception as e:
        print(f"Erreur lors de l'envoi du message dans le salon {channel_id} : {str(e)}")
        return False

async def run_bot():
    try:
        await bot.start(TOKEN)
    except discord.errors.LoginFailure:
        print("Erreur : Le token Discord est invalide.")
    except Exception as e:
        print(f"Erreur inattendue : {e}")

# Ne pas démarrer le bot automatiquement ici
# Le démarrage sera géré par start.py
