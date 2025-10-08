import discord
from discord.ext import commands
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

# --- Fonctions Utilitaires ---
def load_stocks():
    """Charge les données de stock depuis stocks.json, ou initialise le fichier s'il n'existe pas."""
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
    """Sauvegarde les données de stock dans stocks.json."""
    with open("stocks.json", "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

# --- Embed principal ---
def create_embed():
    """Crée et retourne l'embed Discord affichant l'état des stocks."""
    data = load_stocks()
    embed = discord.Embed(title="🏭 Suivi des stocks", color=discord.Color.orange())
    embed.add_field(
        name="📦 Entrepôt",
        value=f"• Pétrole non raffiné : **{data.get('entrepot', {}).get('petrole_non_raffine', 0)}**",
        inline=False
    )
    total = data.get('total', {})
    total_text = (
        f"• Pétrole non raffiné : **{total.get('petrole_non_raffine', 0)}**\n"
        f"• Gazole : **{total.get('gazole', 0)}**\n"
        f"• SP 95 : **{total.get('sp95', 0)}**\n"
        f"• SP 98 : **{total.get('sp98', 0)}**\n"
        f"• Kérosène : **{total.get('kerosene', 0)}**"
    )
    embed.add_field(name="📊 Total", value=total_text, inline=False)
    embed.set_footer(text=f"Mis à jour le {datetime.now().strftime('%d/%m/%Y à %H:%M')}")
    return embed

# --- Formulaire (Modal) ---
class StockModal(Modal):
    def __init__(self, action: str, carburant: str):
        self.action = action
        self.carburant = carburant
        super().__init__(title=f"{'Ajout de' if action == 'add' else 'Retrait de'} {carburant.replace('_', ' ').title()}")

    quantite_stock = TextInput(label="Quantité", placeholder="Ex: 100")

    async def on_submit(self, interaction: discord.Interaction):
        try:
            quantite = int(self.quantite_stock.value)
        except ValueError:
            await interaction.response.send_message("⚠️ La quantité doit être un nombre entier.", ephemeral=True)
            return
        
        data = load_stocks()
        target_dict = None
        if self.carburant in data.get("total", {}):
            target_dict = data["total"]
        elif self.carburant in data.get("entrepot", {}):
            target_dict = data["entrepot"]
        
        if target_dict is None:
            await interaction.response.send_message("❌ Une erreur est survenue avec ce type de carburant.", ephemeral=True)
            return

        if self.action == "add":
            target_dict[self.carburant] += quantite
        else:
            target_dict[self.carburant] = max(0, target_dict[self.carburant] - quantite)

        save_stocks(data)
        await interaction.response.send_message(f"✅ Stock de **{self.carburant.replace('_', ' ')}** mis à jour !", ephemeral=True)

# --- Vue avec le menu déroulant (CORRIGÉE) ---
class FuelSelectView(View):
    def __init__(self, action: str):
        super().__init__(timeout=180)
        self.action = action
        self.populate_options()

    def populate_options(self):
        """Peuple le menu déroulant avec les options du fichier JSON."""
        data = load_stocks()
        all_fuels = list(data.get('entrepot', {}).keys()) + list(data.get('total', {}).keys())
        
        options = [
            SelectOption(label=fuel.replace("_", " ").title(), value=fuel)
            for fuel in sorted(list(set(all_fuels)))
        ]
        
        # S'assure qu'il y a au moins une option pour éviter l'erreur
        if not options:
            options.append(SelectOption(label="Aucun carburant trouvé", value="disabled", default=True))
        
        # Récupère le composant Select et met à jour ses options
        select_menu = discord.utils.get(self.children, custom_id="fuel_selector")
        select_menu.options = options
        select_menu.disabled = not all_fuels # Désactive le menu si la liste est vide

    @discord.ui.select(placeholder="Choisis le type de carburant...", custom_id="fuel_selector", min_values=1, max_values=1)
    async def select_callback(self, interaction: discord.Interaction, select: Select):
        carburant_choisi = select.values[0]
        if carburant_choisi == "disabled":
            await interaction.response.defer()
            return
        await interaction.response.send_modal(StockModal(action=self.action, carburant=carburant_choisi))

# --- Vue principale avec les boutons ---
class StockView(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Ajouter", style=discord.ButtonStyle.success, custom_id="add_stock")
    async def add_button(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_message(view=FuelSelectView(action="add"), ephemeral=True)

    @discord.ui.button(label="Retirer", style=discord.ButtonStyle.danger, custom_id="remove_stock")
    async def remove_button(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_message(view=FuelSelectView(action="remove"), ephemeral=True)

    @discord.ui.button(label="Rafraîchir", style=discord.ButtonStyle.primary, custom_id="refresh_stock")
    async def refresh_button(self, interaction: discord.Interaction, button: Button):
        await interaction.response.edit_message(embed=create_embed(), view=self)

# --- Événements et commandes ---
@bot.event
async def on_ready():
    print(f'Bot connecté sous le nom : {bot.user.name}')
    bot.add_view(StockView())

@bot.command(name="stocks")
async def stocks(ctx):
    await ctx.send(embed=create_embed(), view=StockView())

# --- Lancement du bot ---
if TOKEN:
    bot.run(TOKEN)
else:
    print("ERREUR : Le token Discord n'a pas été trouvé. Assurez-vous d'avoir défini la variable d'environnement DISCORD_TOKEN.")
