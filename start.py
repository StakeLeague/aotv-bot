# -*- coding: utf-8 -*-
import os
import sys
import time
import logging
import asyncio
from bot import bot, run_bot
from dashboard import app
from hypercorn.config import Config
from hypercorn.asyncio import serve

# Configuration du logging
logging.basicConfig(
    format='%(asctime)s | %(levelname)s | %(message)s',
    level=logging.INFO,
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)

# Filtrer les logs de discord.py
discord_logger = logging.getLogger('discord')
discord_logger.setLevel(logging.WARNING)

# Filtrer les logs de quart
quart_logger = logging.getLogger('quart')
quart_logger.setLevel(logging.WARNING)

async def run_dashboard():
    try:
        config = Config()
        # Utiliser le port fourni par Render
        port = int(os.environ.get("PORT", 5050))
        config.bind = [f"0.0.0.0:{port}"]
        config.use_reloader = False
        await serve(app, config)
    except Exception as e:
        logger.error("Erreur lors du demarrage du dashboard : " + str(e))

async def open_browser():
    import webbrowser
    await asyncio.sleep(2)  # Attendre que le serveur demarre
    webbrowser.open('http://127.0.0.1:5050')
    logger.info("Ouverture du dashboard dans votre navigateur...")

async def main():
    logger.info("""
    =================================
             AOTV BOT - DEMARRAGE    
    =================================
    """)

    if not os.path.exists('.env'):
        logger.error("Erreur : Le fichier .env est manquant !")
        logger.error("Veuillez creer un fichier .env avec vos tokens :")
        logger.error("DISCORD_TOKEN=votre_token_discord")
        sys.exit(1)

    # Démarrer le bot Discord
    bot_task = asyncio.create_task(run_bot())

    # Démarrer le dashboard
    dashboard_task = asyncio.create_task(run_dashboard())

    # Ouvrir le navigateur
    browser_task = asyncio.create_task(open_browser())

    logger.info("""
    Tous les composants sont en cours de demarrage...
    
    Pour arreter tous les composants, appuyez sur Ctrl+C
    """)

    try:
        # Attendre que toutes les tâches soient terminées
        await asyncio.gather(bot_task, dashboard_task, browser_task)
    except KeyboardInterrupt:
        logger.info("Arret de tous les composants...")
        sys.exit(0)

if __name__ == "__main__":
    asyncio.run(main()) 