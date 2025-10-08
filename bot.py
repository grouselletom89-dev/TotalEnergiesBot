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

# --- CHEMINS VERS LES FICHIERS DE DONNÉES ---
STOCKS_PATH = "/data/stocks.json"
LOCATIONS_PATH = "/data/locations.json"

# =================================================================================
# SECTION 1 : LOGIQUE POUR LA COMMANDE !STOCKS
# =================================================================================

def load_stocks():
    try:
        with open(STOCKS_PATH, "r", encoding="utf-8") as f: return json.load(f)
    except FileNotFoundError: return get_default_stocks()

def save_stocks(data):
    with open(STOCKS_PATH, "w", encoding="utf-8") as f: json.dump(data, f, indent=4, ensure_ascii=False)

def get_default_stocks():
    default_data = {"entrepot": {"petrole_non_raffine": 0}, "total": {"petrole_non_raffine": 0, "gazole": 0, "sp95": 0, "sp98": 0, "kerosene": 0}}
    save_stocks(default_data); return default_data

def create_stocks_embed():
    data = load_stocks()
    embed = discord.Embed(title="⛽ Suivi des stocks - TotalEnergies", color=0xFF7900)
    embed.add_field(name="📦 Entrepôt", value=f"Pétrole non raffiné : **{data.get('entrepot', {}).get('petrole_non_raffine', 0):,}**".replace(',', ' '), inline=False)
    total = data.get('total', {})
    embed.add_field(name="📊 Total des produits finis", value=f"Pétrole non raffiné : **{total.get('petrole_non_raffine', 0):,}**".replace(',', ' '), inline=False)
    carburants_text = (f"Gazole: **{total.get('gazole', 0):,}** | SP95: **{total.get('sp95', 0):,}** | SP98: **{total.get('sp98', 0):,}** | Kérosène: **{total.get('kerosene', 0):,}**").replace(',', ' ')
    embed.add_field(name="Carburants disponibles", value=carburants_text, inline=False)
    embed.set_footer(text=f"Dernière mise à jour le {datetime.now().strftime('%d/%m/%Y à %H:%M')}")
    embed.set_thumbnail(url="https://upload.wikimedia.org/wikipedia/fr/thumb/c/c8/TotalEnergies_logo.svg/1200px-TotalEnergies_logo.svg.png")
    return embed

class StockModal(Modal):
    def __init__(self, category: str, carburant: str, original_message_id: int):
        self.category, self.carburant, self.original_message_id = category, carburant, original_message_id
        super().__init__(title=f"Mettre à jour : {carburant.replace('_', ' ').title()}")
    nouvelle_quantite = TextInput(label="Nouvelle quantité totale", placeholder="Ex: 5000")
    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        try: quantite = int(self.nouvelle_quantite.value)
        except ValueError: await interaction.followup.send("⚠️ La quantité doit être un nombre.", ephemeral=True); return
        data=load_stocks()
        if self.category in data and self.carburant in data[self.category]: data[self.category][self.carburant] = quantite; save_stocks(data)
        else: await interaction.followup.send("❌ Erreur, catégorie/carburant introuvable.", ephemeral=True); return
        try:
            msg = await interaction.channel.fetch_message(self.original_message_id)
            if msg: await msg.edit(embed=create_stocks_embed())
            await interaction.followup.send(f"✅ Stock mis à jour !", ephemeral=True)
        except (discord.NotFound, discord.Forbidden): await interaction.followup.send("⚠️ Panneau mis à jour, mais actualisation auto. échouée.", ephemeral=True)
class FuelSelectView(View):
    def __init__(self, original_message_id: int, category: str):
        super().__init__(timeout=180); self.original_message_id, self.category = original_message_id, category; self.populate_options()
    def populate_options(self):
        data, fuels = load_stocks(), list(data.get(self.category, {}).keys()); options = [SelectOption(label=f.replace("_", " ").title(), value=f) for f in sorted(fuels)]; select_menu = self.children[0]
        if not options: select_menu.options, select_menu.disabled = [SelectOption(label="Aucun carburant ici", value="disabled")], True
        else: select_menu.options, select_menu.disabled = options, False
    @discord.ui.select(placeholder="Choisis le carburant...", custom_id="stocks_fuel_selector")
    async def select_callback(self, i: discord.Interaction, select: Select):
        carburant = select.values[0]
        if carburant != "disabled": await i.response.send_modal(StockModal(category=self.category, carburant=carburant, original_message_id=self.original_message_id))
class CategorySelectView(View):
    def __init__(self, original_message_id: int): super().__init__(timeout=180); self.original_message_id = original_message_id
    async def show_fuel_select(self, i: discord.Interaction, cat: str): await i.response.edit_message(content="Choisis le carburant :", view=FuelSelectView(self.original_message_id, cat))
    @discord.ui.button(label="📦 Entrepôt", style=discord.ButtonStyle.secondary)
    async def entrepot_button(self, i: discord.Interaction, b: Button): await self.show_fuel_select(i, "entrepot")
    @discord.ui.button(label="📊 Total", style=discord.ButtonStyle.secondary)
    async def total_button(self, i: discord.Interaction, b: Button): await self.show_fuel_select(i, "total")
class ResetConfirmationView(View):
    def __init__(self, original_message_id: int): super().__init__(timeout=60); self.original_message_id = original_message_id
    @discord.ui.button(label="Confirmer", style=discord.ButtonStyle.danger)
    async def confirm_button(self, i: discord.Interaction, b: Button):
        save_stocks(get_default_stocks())
        try: 
            msg = await i.channel.fetch_message(self.original_message_id)
            if msg: await msg.edit(embed=create_stocks_embed())
        except (discord.NotFound, discord.Forbidden): pass
        await i.response.edit_message(content="✅ Stocks remis à zéro.", view=None)
    @discord.ui.button(label="Annuler", style=discord.ButtonStyle.secondary)
    async def cancel_button(self, i: discord.Interaction, b: Button): await i.response.edit_message(content="Opération annulée.", view=None)
class StockView(View):
    def __init__(self): super().__init__(timeout=None)
    @discord.ui.button(label="Mettre à jour", style=discord.ButtonStyle.success, custom_id="update_stock")
    async def update_button(self, i: discord.Interaction, b: Button): await i.response.send_message(content="Catégorie à modifier ?", view=CategorySelectView(original_message_id=i.message.id), ephemeral=True)
    @discord.ui.button(label="Rafraîchir", style=discord.ButtonStyle.primary, custom_id="refresh_stock")
    async def refresh_button(self, i: discord.Interaction, b: Button): await i.response.edit_message(embed=create_stocks_embed(), view=self)
    @discord.ui.button(label="Tout remettre à 0", style=discord.ButtonStyle.danger, custom_id="reset_all_stock")
    async def reset_button(self, i: discord.Interaction, b: Button): await i.response.send_message(content="**⚠️ Action irréversible. Confirmer ?**", view=ResetConfirmationView(original_message_id=i.message.id), ephemeral=True)
@bot.command(name="stocks")
async def stocks(ctx): await ctx.send(embed=create_stocks_embed(), view=StockView())


# =================================================================================
# SECTION 2 : LOGIQUE POUR LA COMMANDE !STATIONS
# =================================================================================

# --- MODIFIÉ : Fonctions Utilitaires pour !stations ---
def load_locations():
    """Charge les données des stations depuis le volume persistant."""
    try:
        with open(LOCATIONS_PATH, "r", encoding="utf-8") as f: 
            return json.load(f)
    except FileNotFoundError:
        # Si le fichier n'existe pas, on le crée avec les valeurs par défaut
        return get_default_locations()

def save_locations(data):
    """Sauvegarde les données des stations dans le volume persistant."""
    with open(LOCATIONS_PATH, "w", encoding="utf-8") as f: 
        json.dump(data, f, indent=4, ensure_ascii=False)

# --- NOUVEAU : Fonction pour créer le fichier de stations par défaut ---
def get_default_locations():
    """Retourne la structure par défaut pour les stations et la sauvegarde."""
    default_data = {
        "stations": {
            "Station de Lampaul": {"last_updated": "N/A", "pumps": {"Pompe 1": {"gazole": 0, "sp95": 0, "sp98": 0}, "Pompe 2": {"gazole": 0, "sp95": 0, "sp98": 0}, "Pompe 3": {"gazole": 0, "sp95": 0, "sp98": 0}}},
            "Station de Ligoudou": {"last_updated": "N/A", "pumps": {"Pompe 1": {"gazole": 0, "sp95": 0, "sp98": 0}, "Pompe 2": {"gazole": 0, "sp95": 0, "sp98": 0}}}
        },
        "ports": {
            "Port de Lampaul": {"last_updated": "N/A", "pumps": {"Pompe 1": {"gazole": 0, "sp95": 0, "sp98": 0}}},
            "Port de Ligoudou": {"last_updated": "N/A", "pumps": {"Pompe 1": {"gazole": 0, "sp95": 0, "sp98": 0}}}
        },
        "aeroport": {
            "Aéroport": {"last_updated": "N/A", "pumps": {"Pompe 1": {"kerosene": 0}}}
        }
    }
    save_locations(default_data)
    return default_data

# --- Embed pour !stations ---
def create_locations_embed():
    data = load_locations()
    embed = discord.Embed(title="⛽ Statut des pompes", color=0x3498db)
    categories = {"stations": " Stations", "ports": " Ports", "aeroport": " Aéroport"}
    embed.add_field(name="\u200b", value="\u200b", inline=False)
    for cat_key, cat_name in categories.items():
        locations = data.get(cat_key)
        if not locations: continue
        embed.add_field(name=f"**{cat_name.upper()}**", value="\u200b", inline=False)
        for i, (loc_name, loc_data) in enumerate(locations.items()):
            pump_text = ""
            for pump_name, pump_fuels in loc_data.get("pumps", {}).items():
                pump_text += f"🔧 **{pump_name}**\n"
                for fuel, qty in pump_fuels.items(): pump_text += f"› {fuel.capitalize()}: {qty:,}L\n".replace(',', ' ')
            pump_text += f"🕒 *{loc_data.get('last_updated', 'N/A')}*"
            embed.add_field(name=loc_name, value=pump_text, inline=True)
        if len(locations) % 2 != 0: embed.add_field(name="\u200b", value="\u200b", inline=True)
        embed.add_field(name="\u200b", value="\u200b", inline=False)
    return embed

# --- Vues et Modals pour la mise à jour des stations ---
class LocationUpdateModal(Modal):
    def __init__(self, category_key: str, location_name: str, pump_name: str, original_message_id: int):
        super().__init__(title=f"{pump_name} - {location_name}")
        self.category_key, self.location_name, self.pump_name, self.original_message_id = category_key, location_name, pump_name, original_message_id
        fuels = load_locations()[category_key][location_name]["pumps"][pump_name]
        for fuel, qty in fuels.items(): self.add_item(TextInput(label=f"Nouv. qté pour {fuel.upper()}", custom_id=fuel, default=str(qty)))
    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        data = load_locations()
        pump_data = data[self.category_key][self.location_name]["pumps"][self.pump_name]
        for field in self.children:
            try: pump_data[field.custom_id] = int(field.value)
            except ValueError: await interaction.followup.send(f"⚠️ La qté pour {field.custom_id.upper()} doit être un nombre.", ephemeral=True); return
        data[self.category_key][self.location_name]["last_updated"] = datetime.now().strftime('%d/%m/%Y %H:%M:%S')
        save_locations(data)
        try:
            msg = await interaction.channel.fetch_message(self.original_message_id)
            if msg: await msg.edit(embed=create_locations_embed())
            await interaction.followup.send("✅ Pompe mise à jour !", ephemeral=True)
        except (discord.NotFound, discord.Forbidden): await interaction.followup.send("⚠️ Pompe mise à jour, mais actualisation auto. échouée.", ephemeral=True)

class PumpSelectView(View):
    def __init__(self, category_key: str, location_name: str, original_message_id: int):
        super().__init__(timeout=180); self.category_key, self.location_name, self.original_message_id = category_key, location_name, original_message_id
        pumps = list(load_locations()[category_key][location_name].get("pumps", {}).keys())
        options = [SelectOption(label=p) for p in pumps]
        self.children[0].options = options if pumps else [SelectOption(label="Aucune pompe trouvée", value="disabled")]
    @discord.ui.select(placeholder="Choisis une pompe...", custom_id="locations_pump_selector")
    async def select_callback(self, i: discord.Interaction, select: Select):
        pump_name = select.values[0]
        if pump_name != "disabled": await i.response.send_modal(LocationUpdateModal(self.category_key, self.location_name, pump_name, self.original_message_id))

class LocationSelectView(View):
    def __init__(self, category_key: str, original_message_id: int):
        super().__init__(timeout=180); self.category_key, self.original_message_id = category_key, original_message_id
        locations = list(load_locations().get(category_key, {}).keys())
        options = [SelectOption(label=loc) for loc in locations]
        self.children[0].options = options if locations else [SelectOption(label="Aucun lieu trouvé", value="disabled")]
    @discord.ui.select(placeholder="Choisis un lieu...", custom_id="locations_loc_selector")
    async def select_callback(self, i: discord.Interaction, select: Select):
        loc_name = select.values[0]
        if loc_name != "disabled": await i.response.edit_message(content="Choisis une pompe :", view=PumpSelectView(self.category_key, loc_name, self.original_message_id))

class LocationCategorySelectView(View):
    def __init__(self, original_message_id: int): super().__init__(timeout=180); self.original_message_id = original_message_id
    async def show_location_select(self, i: discord.Interaction, cat_key: str): await i.response.edit_message(content="Choisis un lieu :", view=LocationSelectView(cat_key, self.original_message_id))
    @discord.ui.button(label="Stations", style=discord.ButtonStyle.secondary)
    async def stations_button(self, i: discord.Interaction, b: Button): await self.show_location_select(i, "stations")
    @discord.ui.button(label="Ports", style=discord.ButtonStyle.secondary)
    async def ports_button(self, i: discord.Interaction, b: Button): await self.show_location_select(i, "ports")
    @discord.ui.button(label="Aéroport", style=discord.ButtonStyle.secondary)
    async def aeroport_button(self, i: discord.Interaction, b: Button): await self.show_location_select(i, "aeroport")

class LocationsView(View):
    def __init__(self): super().__init__(timeout=None)
    @discord.ui.button(label="Mettre à jour", style=discord.ButtonStyle.primary, custom_id="update_location")
    async def update_button(self, i: discord.Interaction, b: Button): await i.response.send_message("Choisis une catégorie :", view=LocationCategorySelectView(i.message.id), ephemeral=True)
    @discord.ui.button(label="Historique complet", style=discord.ButtonStyle.secondary, custom_id="location_history")
    async def history_button(self, i: discord.Interaction, b: Button): await i.response.send_message("Fonctionnalité en cours de développement.", ephemeral=True)

@bot.command(name="stations")
async def stations(ctx): await ctx.send(embed=create_locations_embed(), view=LocationsView())

# =================================================================================
# SECTION 3 : GESTION GÉNÉRALE DU BOT
# =================================================================================
@bot.event
async def on_ready():
    print(f'Bot connecté sous le nom : {bot.user.name}')
    bot.add_view(StockView())
    bot.add_view(LocationsView())

# --- Lancement du bot ---
if TOKEN:
    bot.run(TOKEN)
else:
    print("ERREUR : Le token Discord n'a pas été trouvé.")
