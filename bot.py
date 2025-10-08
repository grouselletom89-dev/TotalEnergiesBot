import discord
from discord.ext import commands
# On importe "Select" et "SelectOption" pour le menu déroulant
from discord.ui import View, Button, Modal, TextInput, Select
from discord import SelectOption
import json
from datetime import datetime
import os

# --- DÉFINITION DU BOT ---
TOKEN = os.environ.get("DISCORD_TOKEN")
intents = discord.Intents.default()
intents.message_content = True 
bot = commands.Bot(command_prefix="!", intents=intents)

# --- Fonctions Utilitaires (inchangées) ---
def load_stocks():
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
    with open("stocks.json", "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

# --- Embed principal (inchangé) ---
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
    embed.set_footer(text=f"Mis à jour le {datetime.now().strftime('%d/%m/%Y à %H:%M')}")
    return embed

# --- MODIFIÉ : Le formulaire ne demande plus que la quantité ---
class StockModal(Modal):
    def __init__(self, action: str, carburant: str):
        self.action = action
        self.carburant = carburant
        # Le titre est maintenant dynamique
        super().__init__(title=f"{'Ajout de' if action == 'add' else 'Retrait de'} {carburant.replace('_', ' ').title()}")

    # On ne demande plus que la quantité
    quantite_stock = TextInput(label="Quantité", placeholder="Ex: 100")

    async def on_submit(self, interaction: discord.Interaction):
        try:
            quantite = int(self.quantite_stock.value)
        except ValueError:
            await interaction.response.send_message("⚠️ La quantité doit être un nombre entier.", ephemeral=True)
            return
            
        data = load_stocks()
        target_dict = None
        if self.carburant in data["total"]:
            target_dict = data["total"]
        elif self.carburant in data["entrepot"]:
            target_dict = data["entrepot"]
        else:
            await interaction.response.send_message("❌ Carburant invalide.", ephemeral=True)
            return

        if self.action == "add":
            target_dict[self.carburant] += quantite
        else:
            target_dict[self.carburant] = max(0, target_dict[self.carburant] - quantite)

        save_stocks(data)
        # On met à jour le message d'origine (qui n'est plus éphémère)
        await interaction.message.edit(embed=create_embed(), view=StockView())
        # On supprime le message contenant le menu déroulant
        await interaction.response.defer() # Accuse réception de l'interaction
        await interaction.delete_original_response()

# --- NOUVEAU : La vue avec le menu déroulant ---
class FuelSelectView(View):
    def __init__(self, action: str):
        super().__init__(timeout=180) # Le menu expire après 3 minutes
        self.action = action
        self.add_item(self.fuel_select())

    def fuel_select(self):
        # Charge les stocks pour créer les options dynamiquement
        data = load_stocks()
        # Fusionne les clés de l'entrepôt et du total pour la liste
        all_fuels = list(data['entrepot'].keys()) + list(data['total'].keys())
        
        options = [
            SelectOption(label=fuel.replace("_", " ").title(), value=fuel)
            for fuel in sorted(list(set(all_fuels))) # Utilise set pour éviter les doublons
        ]
        
        return Select(
            placeholder="Choisis le type de carburant...",
            options=options,
            custom_id="fuel_selector"
        )

    @discord.ui.select(custom_id="fuel_selector")
    async def select_callback(self, interaction: discord.Interaction, select: Select):
        # Récupère le carburant choisi par l'utilisateur
        carburant_choisi = select.values[0]
        # Ouvre le formulaire (Modal) avec l'action et le carburant
        await interaction.response.send_modal(StockModal(action=self.action, carburant=carburant_choisi))

# --- MODIFIÉ : La vue principale qui ouvre le menu déroulant ---
class StockView(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Ajouter", style=discord.ButtonStyle.success, custom_id="add_stock")
    async def add_button(self, interaction: discord.Interaction, button: Button):
        # Envoie un message éphémère avec le menu déroulant
        await interaction.response.send_message(view=FuelSelectView(action="add"), ephemeral=True)

    @discord.ui.button(label="Retirer", style=discord.ButtonStyle.danger, custom_id="remove_stock")
    async def remove_button(self, interaction: discord.Interaction, button: Button):
        # Envoie un message éphémère avec le menu déroulant
        await interaction.response.send_message(view=FuelSelectView(action="remove"), ephemeral=True)

    @discord.ui.button(label="Rafraîchir", style=discord.ButtonStyle.primary, custom_id="refresh_stock")
    async def refresh_button(self, interaction: discord.Interaction, button: Button):
        await interaction.response.edit_message(embed=create_embed(), view=self)

# --- Événements et commandes (inchangés) ---
@bot.event
async def on_ready():
    print(f'Bot connecté sous le nom : {bot.user.name}')
    bot.add_view(StockView())

@bot.command(name="stocks")
async def stocks(ctx):
    await ctx.send(embed=create_embed(), view=StockView())

# Lancement du bot
if TOKEN:
    bot.run(TOKEN)
else:
    print("ERREUR : Le token Discord n'a pas été trouvé.")
