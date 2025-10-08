import discord
from discord.ext import commands
from discord.ui import View, Button, Modal
from discord import TextInput # Correction de l'ImportError
import json
from datetime import datetime

import os

# --- DÉFINITION DU BOT (DOIT ÊTRE FAITE AVANT TOUTE COMMANDE) ---

# 1. Récupération du jeton
TOKEN = os.environ.get("DISCORD_TOKEN")

# 2. Définition des Intents
intents = discord.Intents.default()
# Décommentez la ligne ci-dessous si vous lisez le contenu des messages :
intents.message_content = True 

# 3. Définition de l'instance du bot
bot = commands.Bot(command_prefix="!", intents=intents)

# --- Fin de la partie corrigée ---

# ... (Après bot = commands.Bot(...))

# Ajoutez cette fonction pour que le bot soit prêt et enregistre les vues
## Fonctions Utilitaires (Load/Save)

def load_stocks():
    # Votre nouveau code avec gestion du FileNotFoundError ici
    try:
        with open("stocks.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {
            "entrepot": {"petrole_non_raffine": 0},
            "total": {
                "petrole_non_raffine": 0,
                "gazole": 0,
                "sp95": 0,
                "sp98": 0,
                "kerosene": 0
            }
        }


def save_stocks(data):
    with open("stocks.json", "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)


## Événements Discord
@bot.event
async def on_ready():
    print(f'Bot connecté sous le nom : {bot.user.name}')
    # L'enregistrement de la vue se fait ici
    bot.add_view(StockView())

# --- Embed principal ---
def create_embed():
    data = load_stocks()

    entrepot = data["entrepot"]
    total = data["total"]

    embed = discord.Embed(
        title="🏭 Suivi des stocks",
        color=discord.Color.orange()
    )

    embed.add_field(
        name="📦 Entrepôt",
        value=f"• Pétrole non raffiné : **{entrepot['petrole_non_raffine']}**",
        inline=False
    )

    total_text = (
        f"• Pétrole non raffiné : **{total['petrole_non_raffine']}**\n"
        f"• Gazole : **{total['gazole']}**\n"
        f"• SP 95 : **{total['sp95']}**\n"
        f"• SP 98 : **{total['sp98']}**\n"
        f"• Kérosène : **{total['kerosene']}**"
    )

    embed.add_field(name="📊 Total", value=total_text, inline=False)
    embed.set_footer(text=datetime.now().strftime("%d/%m/%Y %H:%M"))
    return embed


# --- Modals (boîte de dialogue) ---
class StockModal(Modal):
    def __init__(self, action: str):
        super().__init__(title=f"{'Ajouter' if action == 'add' else 'Retirer'} du stock")
        self.action = action

        self.add_item(TextInput(label="Type de carburant", placeholder="ex : gazole, sp95, sp98, kerosene, petrole_non_raffine"))
        self.add_item(TextInput(label="Quantité", placeholder="ex : 100"))

    async def callback(self, interaction: discord.Interaction):
        carburant = self.children[0].value.lower().strip()
        try:
            quantite = int(self.children[1].value)
        except ValueError:
            await interaction.response.send_message("⚠️ La quantité doit être un nombre entier.", ephemeral=True)
            return

        data = load_stocks()
        total = data["total"]

        if carburant not in total:
            await interaction.response.send_message("❌ Carburant invalide. Utilise : gazole, sp95, sp98, kerosene, petrole_non_raffine", ephemeral=True)
            return

        if self.action == "add":
            total[carburant] += quantite
        else:
            total[carburant] = max(0, total[carburant] - quantite)

        save_stocks(data)
        await interaction.response.edit_message(embed=create_embed(), view=StockView())


# --- Vue avec les boutons ---
class StockView(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Ajouter", style=discord.ButtonStyle.success)
    async def add_button(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_modal(StockModal(action="add"))

    @discord.ui.button(label="Retirer", style=discord.ButtonStyle.danger)
    async def remove_button(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_modal(StockModal(action="remove"))

    @discord.ui.button(label="Rafraîchir", style=discord.ButtonStyle.primary)
    async def refresh_button(self, interaction: discord.Interaction, button: Button):
        await interaction.response.edit_message(embed=create_embed(), view=self)


# --- Commande Discord ---
@bot.command(name="stocks")
async def stocks(ctx):
    embed = create_embed()
    view = StockView()
    await ctx.send(embed=embed, view=view)


bot.run(TOKEN)
