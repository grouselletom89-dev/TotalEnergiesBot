import discord
from discord.ext import commands
from discord.ui import View, Button, Modal, TextInput
import json
from datetime import datetime
import os

# --- DÉFINITION DU BOT ---

# 1. Récupération du jeton
TOKEN = os.environ.get("DISCORD_TOKEN")

# 2. Définition des Intents
intents = discord.Intents.default()
intents.message_content = True 

# 3. Définition de l'instance du bot
bot = commands.Bot(command_prefix="!", intents=intents)

# --- FIN DE L'INITIALISATION ---


## Fonctions Utilitaires (Load/Save)

def load_stocks():
    """Charge les données de stock, ou initialise si le fichier n'existe pas."""
    try:
        with open("stocks.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {
            "entrepot": {"petrole_non_raffine": 0},
            "total": {
                "petrole_non_raffine": 0, "gazole": 0,
                "sp95": 0, "sp98": 0, "kerosene": 0
            }
        }

def save_stocks(data):
    """Sauvegarde les données de stock."""
    with open("stocks.json", "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)


## Événements Discord
@bot.event
async def on_ready():
    print(f'Bot connecté sous le nom : {bot.user.name}')
    bot.add_view(StockView())


# --- Embed principal ---
def create_embed():
    data = load_stocks()
    embed = discord.Embed(title="🏭 Suivi des stocks", color=discord.Color.orange())
    
    embed.add_field(
        name="📦 Entrepôt",
        value=f"• Pétrole non raffiné : **{data['entrepot']['petrole_non_raffine']}**",
        inline=False
    )
    
    total = data['total']
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
class StockModal(Modal, title="Gestion des stocks"):
    def __init__(self, action: str):
        super().__init__()
        self.action = action

    type_carburant = TextInput(
        label="Type de carburant ou pétrole",
        placeholder="Ex: gazole, petrole_non_raffine..."
    )
    
    quantite_stock = TextInput(
        label="Quantité",
        placeholder="Ex: 100"
    )

    async def on_submit(self, interaction: discord.Interaction):
        carburant = self.type_carburant.value.lower().strip().replace(" ", "_")
        try:
            quantite = int(self.quantite_stock.value)
        except ValueError:
            await interaction.response.send_message("⚠️ La quantité doit être un nombre entier.", ephemeral=True)
            return
            
        data = load_stocks()
        target_dict = None
        if carburant in data["total"]:
            target_dict = data["total"]
        elif carburant in data["entrepot"]:
            target_dict = data["entrepot"]
        else:
            valid_fuels = list(data['total'].keys()) + list(data['entrepot'].keys())
            await interaction.response.send_message(f"❌ Carburant invalide. Essayez : {', '.join(valid_fuels)}", ephemeral=True)
            return

        if self.action == "add":
            target_dict[carburant] += quantite
        else:
            target_dict[carburant] = max(0, target_dict[carburant] - quantite)

        save_stocks(data)
        await interaction.response.edit_message(embed=create_embed(), view=StockView())


# --- Vue avec les boutons ---
class StockView(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Ajouter", style=discord.ButtonStyle.success, custom_id="add_stock")
    async def add_button(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_modal(StockModal(action="add"))

    @discord.ui.button(label="Retirer", style=discord.ButtonStyle.danger, custom_id="remove_stock")
    async def remove_button(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_modal(StockModal(action="remove"))

    @discord.ui.button(label="Rafraîchir", style=discord.ButtonStyle.primary, custom_id="refresh_stock")
    async def refresh_button(self, interaction: discord.Interaction, button: Button):
        await interaction.response.edit_message(embed=create_embed(), view=self)


# --- Commande Discord ---
@bot.command(name="stocks")
async def stocks(ctx):
    await ctx.send(embed=create_embed(), view=StockView())

# Lancement du bot
if TOKEN:
    bot.run(TOKEN)
else:
    print("Erreur : Le token Discord n'a pas été trouvé.")
