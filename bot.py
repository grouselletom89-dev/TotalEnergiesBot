import discord
from discord.ext import commands
from discord.ui import View, Button, Modal, TextInput, Select
from discord import SelectOption
import json
from datetime import datetime
import os
import pytz

# --- DÉFINITION DU BOT ---
TOKEN = os.environ.get("DISCORD_TOKEN")
intents = discord.Intents.default()
intents.message_content = True 
intents.members = True 
bot = commands.Bot(command_prefix="!", intents=intents)

# --- CONFIGURATION ---
REPORT_CHANNEL_ID = 1420794939565936743
ANNUAIRE_CHANNEL_ID = 1421268834446213251
ABSENCE_CHANNEL_ID = 1420794939565936744
RADIO_FREQUENCY = "367.6 Mhz"
ANNOUNCEMENT_CHANNEL_ID = 1420794935975870574
PRIVATE_CHANNEL_CATEGORY_ID = 1420794939565936749
MANAGEMENT_CHANNEL_ID = 1426356300429918289 
BALANCES_SUMMARY_CHANNEL_ID = 1420794939565936748
STOCK_LOG_CHANNEL_ID = 1425805691754516541
FINANCE_LOG_CHANNEL_ID = 1426557263220572200 # <-- NOUVEAU

# --- CHEMINS VERS LES FICHIERS DE DONNÉES ---
STOCKS_PATH = "/data/stocks.json"
LOCATIONS_PATH = "/data/locations.json"
ANNUAIRE_PATH = "/data/annuaire.json"
FINANCES_PATH = "/data/finances.json"

def get_paris_time():
    paris_tz = pytz.timezone("Europe/Paris")
    return datetime.now(paris_tz)

def format_paris_time(dt_obj):
    return dt_obj.strftime('%d/%m/%Y %H:%M:%S')

# =================================================================================
# SECTION 1 : LOGIQUE POUR LA COMMANDE !STOCKS
# =================================================================================

async def log_stock_change(interaction: discord.Interaction, changes: list, action_type: str):
    log_channel = bot.get_channel(STOCK_LOG_CHANNEL_ID)
    if not log_channel: return

    embed = discord.Embed(
        title=f"📝 Log de Modification des Stocks",
        description=f"**Action :** {action_type}\n**Auteur :** {interaction.user.mention}",
        color=discord.Color.blue(),
        timestamp=get_paris_time()
    )
    for change in changes:
        embed.add_field(name=change.get("item", "Action").replace('_', ' ').title(), value=f"Ancienne valeur : `{change.get('old', 'N/A')}`\nNouvelle valeur : `{change.get('new', 'N/A')}`", inline=False)
    embed.set_footer(text=f"ID de l'utilisateur : {interaction.user.id}")
    try: await log_channel.send(embed=embed)
    except discord.Forbidden: print(f"ERREUR: Permissions manquantes pour envoyer des logs de stock.")

# ... (Le reste du code de la SECTION 1 reste identique)
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
    embed.add_field(name="📊 Total", value=f"Pétrole non raffiné : **{total.get('petrole_non_raffine', 0):,}**".replace(',', ' '), inline=False)
    carburants_text = (f"Gazole: **{total.get('gazole', 0):,}** | SP95: **{total.get('sp95', 0):,}** | SP98: **{total.get('sp98', 0):,}** | Kérosène: **{total.get('kerosene', 0):,}**").replace(',', ' ')
    embed.add_field(name="Carburants disponibles", value=carburants_text, inline=False)
    embed.set_footer(text=f"Dernière mise à jour le {format_paris_time(get_paris_time())}")
    embed.set_thumbnail(url="https://upload.wikimedia.org/wikipedia/fr/thumb/c/c8/TotalEnergies_logo.svg/1200px-TotalEnergies_logo.svg.png")
    return embed
class TotalStockModal(Modal, title="Mettre à jour le stock Total"):
    def __init__(self, original_message_id: int):
        super().__init__()
        self.original_message_id = original_message_id
        current_stocks = load_stocks().get("total", {})
        self.add_item(TextInput(label="Nouvelle quantité de Pétrole non raffiné", custom_id="petrole_non_raffine", default=str(current_stocks.get("petrole_non_raffine", 0))))
        self.add_item(TextInput(label="Nouvelle quantité de Gazole", custom_id="gazole", default=str(current_stocks.get("gazole", 0))))
        self.add_item(TextInput(label="Nouvelle quantité de SP95", custom_id="sp95", default=str(current_stocks.get("sp95", 0))))
        self.add_item(TextInput(label="Nouvelle quantité de SP98", custom_id="sp98", default=str(current_stocks.get("sp98", 0))))
        self.add_item(TextInput(label="Nouvelle quantité de Kérosène", custom_id="kerosene", default=str(current_stocks.get("kerosene", 0))))
    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        data = load_stocks()
        old_total_stocks = data.get("total", {}).copy()
        changes = []

        for field in self.children:
            try:
                new_value = int(field.value)
                if new_value < 0:
                    await interaction.followup.send(f"⚠️ La quantité pour {field.custom_id} ne peut pas être négative.", ephemeral=True); return
                
                old_value = old_total_stocks.get(field.custom_id, 0)
                if new_value != old_value:
                    changes.append({
                        "item": f"Total - {field.custom_id}",
                        "old": f"{old_value:,}".replace(',', ' '),
                        "new": f"{new_value:,}".replace(',', ' ')
                    })
                data['total'][field.custom_id] = new_value
            except ValueError:
                await interaction.followup.send(f"⚠️ La quantité pour {field.custom_id} doit être un nombre.", ephemeral=True); return

        if changes:
            await log_stock_change(interaction, changes, "Mise à jour groupée du stock 'Total'")
            save_stocks(data)
        
        try:
            msg = await interaction.channel.fetch_message(self.original_message_id)
            if msg: await msg.edit(embed=create_stocks_embed())
            await interaction.followup.send("✅ Stock 'Total' mis à jour !", ephemeral=True)
        except (discord.NotFound, discord.Forbidden):
            await interaction.followup.send("⚠️ Panneau mis à jour, mais l'actualisation automatique a échoué.", ephemeral=True)
class StockModal(Modal):
    def __init__(self, category: str, carburant: str, original_message_id: int):
        self.category, self.carburant, self.original_message_id = category, carburant, original_message_id
        super().__init__(title=f"Mettre à jour : {carburant.replace('_', ' ').title()}")
    nouvelle_quantite = TextInput(label="Nouvelle quantité totale", placeholder="Ex: 5000")
    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        try: quantite = int(self.nouvelle_quantite.value)
        except ValueError: await interaction.followup.send("⚠️ La quantité doit être un nombre.", ephemeral=True); return
        
        data = load_stocks()
        if self.category not in data or self.carburant not in data[self.category]:
            await interaction.followup.send("❌ Erreur, catégorie ou carburant introuvable.", ephemeral=True); return

        old_value = data[self.category][self.carburant]
        if quantite != old_value:
            data[self.category][self.carburant] = quantite
            changes = [{"item": f"{self.category.title()} - {self.carburant}", "old": f"{old_value:,}".replace(',', ' '), "new": f"{quantite:,}".replace(',', ' ')}]
            await log_stock_change(interaction, changes, "Mise à jour d'un stock")
            save_stocks(data)
        
        try:
            msg = await interaction.channel.fetch_message(self.original_message_id)
            if msg: await msg.edit(embed=create_stocks_embed())
            await interaction.followup.send(f"✅ Stock mis à jour !", ephemeral=True)
        except (discord.NotFound, discord.Forbidden): await interaction.followup.send("⚠️ Panneau mis à jour, mais l'actualisation automatique a échoué.", ephemeral=True)
class CategorySelectView(View):
    def __init__(self, original_message_id: int): 
        super().__init__(timeout=180)
        self.original_message_id = original_message_id
    @discord.ui.button(label="📦 Entrepôt", style=discord.ButtonStyle.secondary)
    async def entrepot_button(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_modal(StockModal(category="entrepot", carburant="petrole_non_raffine", original_message_id=self.original_message_id))
    @discord.ui.button(label="📊 Total", style=discord.ButtonStyle.secondary)
    async def total_button(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_modal(TotalStockModal(original_message_id=self.original_message_id))
class ResetConfirmationView(View):
    def __init__(self, original_message_id: int): super().__init__(timeout=60); self.original_message_id = original_message_id
    @discord.ui.button(label="Confirmer", style=discord.ButtonStyle.danger)
    async def confirm_button(self, i: discord.Interaction, b: Button):
        changes = [{"item": "Action Globale", "old": "Données actuelles", "new": "Tout à zéro"}]
        await log_stock_change(i, changes, "Réinitialisation complète des stocks")
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
def load_locations():
    try:
        with open(LOCATIONS_PATH, "r", encoding="utf-8") as f: return json.load(f)
    except FileNotFoundError: return get_default_locations()
def save_locations(data):
    with open(LOCATIONS_PATH, "w", encoding="utf-8") as f: json.dump(data, f, indent=4, ensure_ascii=False)
def get_default_locations():
    default_data = {"stations": {"Station de Lampaul": {"image_url": "","last_updated": "N/A", "pumps": {"Pompe 1": {"gazole": 0, "sp95": 0, "sp98": 0}, "Pompe 2": {"gazole": 0, "sp95": 0, "sp98": 0}, "Pompe 3": {"gazole": 0, "sp95": 0, "sp98": 0}}}, "Station de Ligoudou": {"image_url": "","last_updated": "N/A", "pumps": {"Pompe 1": {"gazole": 0, "sp95": 0, "sp98": 0}, "Pompe 2": {"gazole": 0, "sp95": 0, "sp98": 0}}}},"ports": {"Port de Lampaul": {"image_url": "","last_updated": "N/A", "pumps": {"Pompe 1": {"gazole": 0, "sp95": 0, "sp98": 0}}}, "Port de Ligoudou": {"image_url": "","last_updated": "N/A", "pumps": {"Pompe 1": {"gazole": 0, "sp95": 0, "sp98": 0}}}},"aeroport": {"Aéroport": {"image_url": "","last_updated": "N/A", "pumps": {"Pompe 1": {"kerosene": 0}}}}}
    save_locations(default_data); return default_data
def create_locations_embeds():
    data = load_locations()
    embeds = []
    categories = {"stations": "🚉 Stations", "ports": "⚓ Ports", "aeroport": "✈️ Aéroport"}
    MAX_CAPACITY = {"gazole": 3000, "sp95": 2000, "sp98": 2000, "kerosene": 10000}
    global_missing = {fuel: 0 for fuel in MAX_CAPACITY.keys()}
    for cat_key, cat_name in categories.items():
        locations = data.get(cat_key)
        if not locations: continue
        cat_embed = discord.Embed(title=f"**{cat_name}**", color=0x0099ff)
        image_set = False
        total_missing_in_cat = {fuel: 0 for fuel in MAX_CAPACITY.keys()}
        for loc_name, loc_data in locations.items():
            pump_text = ""
            for pump_name, pump_fuels in loc_data.get("pumps", {}).items():
                pump_text += f"🔧 **{pump_name.upper()}**\n"
                for fuel, qty in pump_fuels.items():
                    max_cap = MAX_CAPACITY.get(fuel, 0)
                    missing = max(0, max_cap - qty)
                    total_missing_in_cat[fuel] += missing
                    global_missing[fuel] += missing
                    pump_text += f"⛽ {fuel.capitalize()}: **{qty:,}L** *(manque {missing:,}L)*\n".replace(',', ' ')
                pump_text += "\n"
            pump_text += f"🕒 *{loc_data.get('last_updated', 'N/A')}*\n\u200b\n"
            cat_embed.add_field(name=loc_name, value=pump_text, inline=True)
            if loc_data.get("image_url") and not image_set:
                cat_embed.set_image(url=loc_data.get("image_url")); image_set = True
        if len(locations) % 2 != 0: cat_embed.add_field(name="\u200b", value="\u200b", inline=True)
        total_text = ""
        for fuel, missing in total_missing_in_cat.items():
            if missing > 0: total_text += f"➡️ {fuel.capitalize()}: **{missing:,}L manquants**\n".replace(',', ' ')
        if not total_text: total_text = "✅ Tous les réservoirs de cette catégorie sont pleins."
        cat_embed.add_field(name="📉 Manquant total pour la catégorie", value=total_text, inline=False)
        embeds.append(cat_embed)
    global_text = ""
    for fuel, missing in global_missing.items():
        if missing > 0: global_text += f"➡️ {fuel.capitalize()}: **{missing:,}L manquants**\n".replace(',', ' ')
    if not global_text: global_text = "✅ Tous les réservoirs sont pleins dans toutes les zones."
    global_embed = discord.Embed(title="📊 Bilan global des manquants", description=global_text, color=0xFFAA00)
    global_embed.set_footer(text=f"Dernière mise à jour le {get_paris_time()}"); embeds.append(global_embed)
    return embeds
class LocationUpdateModal(Modal):
    def __init__(self, category_key: str, location_name: str, pump_name: str, original_message_id: int):
        super().__init__(title=f"{pump_name} - {location_name}"); self.category_key, self.location_name, self.pump_name, self.original_message_id = category_key, location_name, pump_name, original_message_id
        fuels = load_locations()[category_key][location_name]["pumps"][pump_name]
        for fuel, qty in fuels.items(): self.add_item(TextInput(label=f"Nouvelle Quantité pour {fuel.upper()}", custom_id=fuel, default=str(qty)))
    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True); data = load_locations(); pump_data = data[self.category_key][self.location_name]["pumps"][self.pump_name]
        for field in self.children:
            try: pump_data[field.custom_id] = int(field.value)
            except ValueError: await interaction.followup.send(f"⚠️ La quantité pour {field.custom_id.upper()} doit être un nombre.", ephemeral=True); return
        data[self.category_key][self.location_name]["last_updated"] = get_paris_time(); save_locations(data)
        try:
            msg = await interaction.channel.fetch_message(self.original_message_id)
            if msg: await msg.edit(embeds=create_locations_embeds())
            await interaction.followup.send("✅ Pompe mise à jour !", ephemeral=True)
        except (discord.NotFound, discord.Forbidden): await interaction.followup.send("⚠️ Pompe mise à jour, mais l'actualisation automatique a échoué.", ephemeral=True)
class PumpSelectView(View):
    def __init__(self, category_key: str, location_name: str, original_message_id: int):
        super().__init__(timeout=180); self.category_key, self.location_name, self.original_message_id = category_key, location_name, original_message_id
        pumps = list(load_locations()[category_key][location_name].get("pumps", {}).keys()); options = [SelectOption(label=p) for p in pumps]
        self.children[0].options = options if pumps else [SelectOption(label="Aucune pompe trouvée", value="disabled")]
    @discord.ui.select(placeholder="Choisis une pompe...", custom_id="locations_pump_selector")
    async def select_callback(self, i: discord.Interaction, select: Select):
        pump_name = select.values[0]
        if pump_name != "disabled": await i.response.send_modal(LocationUpdateModal(self.category_key, self.location_name, pump_name, self.original_message_id))
class LocationSelectView(View):
    def __init__(self, category_key: str, original_message_id: int):
        super().__init__(timeout=180); self.category_key, self.original_message_id = category_key, original_message_id
        locations = list(load_locations().get(category_key, {}).keys()); options = [SelectOption(label=loc) for loc in locations]
        self.children[0].options = options if locations else [SelectOption(label="Aucun lieu trouvé", value="disabled")]
    @discord.ui.select(placeholder="Choisis un lieu...", custom_id="locations_loc_selector")
    async def select_callback(self, interaction: discord.Interaction, select: Select):
        loc_name = select.values[0]
        if loc_name == "disabled": await interaction.response.edit_message(content="Action annulée.", view=None); return
        location_data = load_locations().get(self.category_key, {}).get(loc_name, {}); pumps = location_data.get("pumps", {})
        if len(pumps) == 1:
            pump_name = list(pumps.keys())[0]
            await interaction.response.send_modal(LocationUpdateModal(self.category_key, loc_name, pump_name, self.original_message_id))
        else:
            pump_view = PumpSelectView(self.category_key, loc_name, self.original_message_id)
            image_url = location_data.get("image_url"); embed = None
            if image_url: embed = discord.Embed(color=0x0099ff); embed.set_image(url=image_url)
            await interaction.response.edit_message(content="Choisis une pompe :", view=pump_view, embed=embed)
class LocationCategorySelectView(View):
    def __init__(self, original_message_id: int): 
        super().__init__(timeout=180)
        self.original_message_id = original_message_id
    async def show_location_select(self, interaction: discord.Interaction, category_key: str):
        locations = load_locations().get(category_key, {})
        if len(locations) == 1:
            location_name = list(locations.keys())[0]; location_data = locations[location_name]; pumps = location_data.get("pumps", {})
            if len(pumps) == 1:
                pump_name = list(pumps.keys())[0]
                await interaction.response.send_modal(LocationUpdateModal(category_key, location_name, pump_name, self.original_message_id))
            else:
                 await interaction.response.edit_message(content=f"Choisis une pompe pour **{location_name}** :", view=PumpSelectView(category_key, location_name, self.original_message_id))
        else:
            await interaction.response.edit_message(content="Choisis un lieu :", view=LocationSelectView(category_key, self.original_message_id))
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
    @discord.ui.button(label="Rafraîchir", style=discord.ButtonStyle.secondary, custom_id="refresh_locations")
    async def refresh_button(self, i: discord.Interaction, b: Button): await i.response.edit_message(embeds=create_locations_embeds(), view=self)
@bot.command(name="stations")
async def stations(ctx): await ctx.send(embeds=create_locations_embeds(), view=LocationsView())


# =================================================================================
# SECTION 3 : LOGIQUE POUR LA COMMANDE !ANNUAIRE
# =================================================================================
def load_annuaire():
    try:
        with open(ANNUAIRE_PATH, "r", encoding="utf-8") as f: return json.load(f)
    except FileNotFoundError:
        default_data = {"Patron": [], "Co-Patron": [], "Chef d'équipe": [], "Employé": []}
        save_annuaire(default_data); return default_data
def save_annuaire(data):
    with open(ANNUAIRE_PATH, "w", encoding="utf-8") as f: json.dump(data, f, indent=4, ensure_ascii=False)
async def create_annuaire_embed(guild: discord.Guild):
    saved_data = load_annuaire(); embed = discord.Embed(title="📞 Annuaire Téléphonique", color=discord.Color.blue())
    role_priority = ["Patron", "Co-Patron", "Chef d'équipe", "Employé"]
    role_icons = {"Patron": "👑", "Co-Patron": "⭐", "Chef d'équipe": "📋", "Employé": "👨‍💼"}
    grouped_members = {role_name: [] for role_name in role_priority}
    for member in guild.members:
        if member.bot: continue
        highest_role_name = next((name for name in role_priority if discord.utils.get(member.roles, name=name)), None)
        if highest_role_name: grouped_members[highest_role_name].append(member)
    for role_name in role_priority:
        members_in_group = grouped_members[role_name]
        if not members_in_group: continue
        value_str = ""
        for member in sorted(members_in_group, key=lambda m: m.display_name):
            number = next((user.get('number') for users in saved_data.values() for user in users if user['id'] == member.id), None)
            value_str += f"• {member.display_name} → {'`' + number + '`' if number else ' Pas encore renseigné'}\n"
        if value_str: embed.add_field(name=f"{role_icons[role_name]} {role_name}", value=value_str, inline=False)
    embed.set_footer(text=f"Mis à jour le {get_paris_time()}"); return embed
class AnnuaireModal(Modal):
    def __init__(self, current_number: str = ""):
        super().__init__(title="Mon numéro de téléphone")
        self.add_item(TextInput(label="Ton numéro (laisse vide pour supprimer)", placeholder="Ex: 0612345678", required=False, default=current_number))
    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        number = self.children[0].value.strip(); data, user = load_annuaire(), interaction.user
        for role_group in data.values(): role_group[:] = [entry for entry in role_group if entry['id'] != user.id]
        role_priority = ["Patron", "Co-Patron", "Chef d'équipe", "Employé"]
        user_role_name = next((name for name in role_priority if discord.utils.get(user.roles, name=name)), None)
        if user_role_name and number: data.setdefault(user_role_name, []).append({"id": user.id, "name": user.display_name, "number": number})
        save_annuaire(data)
        try:
            async for message in interaction.channel.history(limit=100):
                if message.author == bot.user and message.embeds and message.embeds[0].title == "📞 Annuaire Téléphonique":
                    await message.edit(embed=await create_annuaire_embed(interaction.guild)); break
            await interaction.followup.send("✅ Ton numéro a été mis à jour !", ephemeral=True)
        except (discord.NotFound, discord.Forbidden): await interaction.followup.send("✅ Ton numéro est sauvegardé, mais le panneau n'a pas pu être actualisé.", ephemeral=True)
class AnnuaireView(View):
    def __init__(self): super().__init__(timeout=None)
    @discord.ui.button(label="Saisir / Modifier mon numéro", style=discord.ButtonStyle.primary, custom_id="update_annuaire_number")
    async def update_number_button(self, interaction: discord.Interaction, button: Button):
        data = load_annuaire(); current_number = next((user.get('number', '') for group in data.values() for user in group if user['id'] == interaction.user.id), "")
        await interaction.response.send_modal(AnnuaireModal(current_number=current_number))
    @discord.ui.button(label="Demander d'actualiser", style=discord.ButtonStyle.secondary, custom_id="request_annuaire_update")
    async def request_update_button(self, interaction: discord.Interaction, button: Button):
        await interaction.response.defer(ephemeral=True)
        saved_data = load_annuaire(); all_registered_ids = {user['id'] for group in saved_data.values() for user in group if user.get('number')}
        role_priority = ["Patron", "Co-Patron", "Chef d'équipe", "Employé"]; options = []
        for role_name in role_priority:
            role = discord.utils.get(interaction.guild.roles, name=role_name)
            if role:
                for member in role.members:
                    if not member.bot and member.id not in all_registered_ids:
                        options.append(SelectOption(label=member.display_name, value=str(member.id)))
        options = list({opt.value: opt for opt in options}.values()); placeholder = "Qui notifier pour renseigner son numéro ?"
        if len(options) > 25: options = options[:25]; placeholder = "Qui notifier ? (25 premiers)"
        if not options: await interaction.followup.send("🎉 Tout le monde a renseigné son numéro !", ephemeral=True); return
        select_menu = Select(placeholder=placeholder, options=options)
        async def select_callback(select_interaction: discord.Interaction):
            await select_interaction.response.defer(ephemeral=True); user_id_to_notify = select_interaction.data["values"][0]
            report_channel = bot.get_channel(REPORT_CHANNEL_ID)
            if not report_channel: await select_interaction.followup.send("❌ Erreur : Salon de signalement non trouvé.", ephemeral=True); return
            try:
                member_to_notify = await select_interaction.guild.fetch_member(int(user_id_to_notify))
                annuaire_link = f"https://discord.com/channels/{select_interaction.guild.id}/{ANNUAIRE_CHANNEL_ID}"
                await report_channel.send(f"Bonjour {member_to_notify.mention}, il semble que tu n'aies pas encore renseigné ton numéro. Merci de le faire ici : {annuaire_link}")
                await select_interaction.edit_original_response(content=f"✅ {member_to_notify.display_name} a été notifié(e).", view=None)
            except (discord.NotFound, discord.Forbidden): await select_interaction.followup.send("❌ Erreur lors de la notification.", ephemeral=True)
        select_menu.callback = select_callback; temp_view = View(timeout=180); temp_view.add_item(select_menu)
        await interaction.followup.send(view=temp_view, ephemeral=True)
    @discord.ui.button(label="Rafraîchir", style=discord.ButtonStyle.secondary, custom_id="refresh_annuaire")
    async def refresh_button(self, i: discord.Interaction, b: Button): await i.response.edit_message(embed=await create_annuaire_embed(i.guild), view=self)
    @discord.ui.button(label="Signaler numéro invalide", style=discord.ButtonStyle.danger, custom_id="report_annuaire_number")
    async def report_number_button(self, interaction: discord.Interaction, b: Button):
        await interaction.response.defer(ephemeral=True)
        saved_data = load_annuaire(); all_users = [SelectOption(label=u['name'], value=str(u['id'])) for rg in saved_data.values() for u in rg if u.get('number')]
        placeholder = "Qui veux-tu signaler ?";
        if len(all_users) > 25: all_users = all_users[:25]; placeholder = "Qui veux-tu signaler ? (25 premiers)"
        if not all_users: await interaction.followup.send("Personne n'a de numéro à signaler pour l'instant.", ephemeral=True); return
        select_menu = Select(placeholder=placeholder, options=all_users)
        async def select_callback(select_interaction: discord.Interaction):
            await select_interaction.response.defer(ephemeral=True); user_id_to_report = select_interaction.data["values"][0]
            report_channel = bot.get_channel(REPORT_CHANNEL_ID)
            if not report_channel: await select_interaction.followup.send("❌ Erreur : Salon de signalement non trouvé.", ephemeral=True); return
            try:
                member_to_report = await select_interaction.guild.fetch_member(int(user_id_to_report))
                annuaire_link = f"https://discord.com/channels/{select_interaction.guild.id}/{ANNUAIRE_CHANNEL_ID}"
                await report_channel.send(f"Bonjour {member_to_report.mention}, ton numéro dans l'annuaire semble incorrect. Merci de le mettre à jour ici : {annuaire_link}")
                await select_interaction.edit_original_response(content=f"✅ {member_to_report.display_name} a été notifié(e).", view=None)
            except (discord.NotFound, discord.Forbidden): await select_interaction.followup.send("❌ Erreur lors de la notification.", ephemeral=True)
        select_menu.callback = select_callback; temp_view = View(timeout=180); temp_view.add_item(select_menu)
        await interaction.followup.send(view=temp_view, ephemeral=True)
@bot.command(name="annuaire")
async def annuaire(ctx): await ctx.send(embed=await create_annuaire_embed(ctx.guild), view=AnnuaireView())


# =================================================================================
# SECTION 4 : LOGIQUE POUR LA COMMANDE !ABSENCE
# =================================================================================
class AbsenceModal(Modal, title="Déclarer une absence"):
    date_debut = TextInput(label="🗓️ Date de début", placeholder="Ex: 10/10/2025")
    date_fin = TextInput(label="🗓️ Date de fin", placeholder="Ex: 12/10/2025")
    motif = TextInput(label="📝 Motif", style=discord.TextStyle.paragraph, placeholder="Raison de votre absence...", max_length=1000)
    async def on_submit(self, interaction: discord.Interaction):
        absence_channel = bot.get_channel(ABSENCE_CHANNEL_ID)
        if not absence_channel:
            await interaction.response.send_message("❌ Erreur : Le salon des absences n'est pas configuré ou introuvable.", ephemeral=True); return
        embed = discord.Embed(title=f"📋 Déclaration d'absence de {interaction.user.display_name}", color=discord.Color.orange())
        embed.set_thumbnail(url=interaction.user.display_avatar.url)
        embed.add_field(name="Date de début", value=self.date_debut.value, inline=True)
        embed.add_field(name="Date de fin", value=self.date_fin.value, inline=True)
        embed.add_field(name="Motif", value=self.motif.value, inline=False)
        embed.set_footer(text=f"Déclaration faite le {get_paris_time()}")
        try:
            await absence_channel.send(embed=embed)
            await interaction.response.send_message("✅ Ton absence a bien été enregistrée.", ephemeral=True)
        except discord.Forbidden:
            await interaction.response.send_message("❌ Erreur : Je n'ai pas les permissions pour envoyer un message dans le salon des absences.", ephemeral=True)
class AbsenceView(View):
    def __init__(self): super().__init__(timeout=None)
    @discord.ui.button(label="Déclarer une absence", style=discord.ButtonStyle.primary, custom_id="declare_absence")
    async def declare_button(self, interaction: discord.Interaction, button: Button): await interaction.response.send_modal(AbsenceModal())
@bot.command(name="absence")
async def absence(ctx):
    embed = discord.Embed(title="Gestion des Absences", description="Clique sur le bouton ci-dessous pour déclarer une nouvelle absence.", color=discord.Color.dark_grey())
    await ctx.send(embed=embed, view=AbsenceView())


# =================================================================================
# SECTION 5 : LOGIQUE POUR LA COMMANDE !RADIO
# =================================================================================
@bot.command(name="radio")
async def radio(ctx):
    embed = discord.Embed(title=f"Notre fréquence est `{RADIO_FREQUENCY}`", description="⚠️ Merci de la tenir secrète !", color=discord.Color.dark_grey())
    await ctx.send(embed=embed)


# =================================================================================
# SECTION 6 : LOGIQUE POUR LA COMMANDE !ANNONCE
# =================================================================================
class AnnonceModal(Modal, title="Rédiger une annonce interne"):
    titre = TextInput(label="Titre de l'annonce", style=discord.TextStyle.short, max_length=256, required=True)
    paragraphe = TextInput(label="Contenu de l'annonce", style=discord.TextStyle.paragraph, max_length=2000, required=True)
    conclusion = TextInput(label="Conclusion (optionnel)", style=discord.TextStyle.short, required=False)
    async def on_submit(self, interaction: discord.Interaction):
        annonce_channel = bot.get_channel(ANNOUNCEMENT_CHANNEL_ID)
        if not annonce_channel:
            await interaction.response.send_message("❌ Erreur : Le salon des annonces est introuvable.", ephemeral=True); return
        user = interaction.user; role_priority = ["Patron", "Co-Patron", "Chef d'équipe", "Employé"]
        user_role_name = next((name for name in role_priority if discord.utils.get(user.roles, name=name)), "Role non défini")
        embed = discord.Embed(title=self.titre.value, description=self.paragraphe.value, color=discord.Color.blue())
        if self.conclusion.value: embed.add_field(name="\u200b", value=self.conclusion.value, inline=False)
        signature = f"Cordialement,\n**{user.display_name}**\n*{user_role_name}*"; embed.add_field(name="\u200b", value=signature, inline=False)
        embed.set_footer(text=f"Annonce faite le {get_paris_time()}")
        if interaction.guild.icon: embed.set_thumbnail(url=interaction.guild.icon.url)
        try:
            await annonce_channel.send(embed=embed)
            await interaction.response.send_message("✅ Votre annonce a été publiée avec succès !", ephemeral=True)
        except discord.Forbidden: await interaction.response.send_message("❌ Erreur : Je n'ai pas les permissions pour envoyer un message dans le salon des annonces.", ephemeral=True)
class AnnonceView(View):
    def __init__(self): super().__init__(timeout=None)
    @discord.ui.button(label="Rédiger une annonce", style=discord.ButtonStyle.primary, custom_id="make_announcement")
    async def announce_button(self, interaction: discord.Interaction, button: Button): await interaction.response.send_modal(AnnonceModal())

@bot.command(name="annonce")
@commands.has_any_role("Patron", "Co-Patron", "Chef d'équipe")
async def annonce(ctx):
    embed = discord.Embed(title="Panneau des Annonces Internes", description="Cliquez sur le bouton ci-dessous pour rédiger et publier une nouvelle annonce.", color=discord.Color.dark_blue())
    await ctx.send(embed=embed, view=AnnonceView())
@annonce.error
async def annonce_error(ctx, error):
    if isinstance(error, commands.MissingAnyRole):
        await ctx.send("❌ Vous n'avez pas la permission d'utiliser cette commande.", ephemeral=True)
    else:
        await ctx.send("❌ Une erreur est survenue lors de l'exécution de la commande."); print(f"Erreur commande !annonce: {error}")


# =================================================================================
# SECTION 7 : LOGIQUE POUR LE PANEL FINANCIER
# =================================================================================

async def log_finance_change(interaction: discord.Interaction, member: discord.Member, action_type: str, amount: str, details: str):
    log_channel = bot.get_channel(FINANCE_LOG_CHANNEL_ID)
    if not log_channel:
        print(f"ERREUR: Le salon de log des finances (ID: {FINANCE_LOG_CHANNEL_ID}) est introuvable.")
        return

    embed = discord.Embed(
        title="💸 Log de Transaction Financière",
        description=f"**Auteur de l'action :** {interaction.user.mention}",
        color=discord.Color.green() if action_type == "Paiement" else discord.Color.orange(),
        timestamp=get_paris_time()
    )
    embed.add_field(name="Employé Concerné", value=member.mention, inline=False)
    embed.add_field(name="Type d'Action", value=action_type, inline=True)
    embed.add_field(name="Montant", value=f"`{amount}`", inline=True)
    if details:
        embed.add_field(name="Détails", value=details, inline=True)
    embed.set_footer(text=f"ID Auteur: {interaction.user.id} | ID Employé: {member.id}")
    
    try:
        await log_channel.send(embed=embed)
    except discord.Forbidden:
        print(f"ERREUR: Permissions manquantes pour envoyer des messages dans le salon de log des finances.")

def load_finances():
    try:
        with open(FINANCES_PATH, "r", encoding="utf-8") as f: return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError): return {}

def save_finances(data):
    with open(FINANCES_PATH, "w", encoding="utf-8") as f: json.dump(data, f, indent=4, ensure_ascii=False)

def add_to_history(member_id: int, action: str, amount_str: str, details: str = ""):
    finances = load_finances()
    member_id_str = str(member_id)
    if member_id_str not in finances or "history" not in finances[member_id_str]:
        finances[member_id_str] = {"solde": finances.get(member_id_str, {}).get("solde", 0), "history": []}
    
    log_entry = {"action": action, "details": details, "amount": amount_str, "timestamp": format_paris_time(get_paris_time())}
    finances[member_id_str]["history"].insert(0, log_entry)
    finances[member_id_str]["history"] = finances[member_id_str]["history"][:15]
    save_finances(finances)

async def update_balances_summary_panel():
    channel = bot.get_channel(BALANCES_SUMMARY_CHANNEL_ID)
    if not channel: return
    try:
        new_embed = await create_balances_summary_embed(channel.guild)
        async for message in channel.history(limit=50):
            if message.author == bot.user and message.embeds and message.embeds[0].title == "📊 Récapitulatif des Soldes":
                await message.edit(embed=new_embed); return
    except Exception as e: print(f"Erreur màj auto panneau soldes: {e}")

def create_financial_embed(member: discord.Member):
    finances = load_finances()
    member_id_str = str(member.id)
    if member_id_str not in finances:
        finances[member_id_str] = {"solde": 0, "history": []}; save_finances(finances)
    solde = finances[member_id_str].get('solde', 0)
    solde_formatted = f"{solde:,.2f} €".replace(',', ' ')
    embed_color = discord.Color.red() if solde > 0 else discord.Color.green()
    solde_message = f"🔴 Votre solde est de **{solde_formatted}**." if solde > 0 else f"🟢 Votre solde est de **{solde_formatted}**."
    financial_embed = discord.Embed(title="💰 Panel de Gestion Financière", description=f"Panneau de suivi des transactions.\n*Employé lié : {member.mention}*", color=embed_color)
    financial_embed.add_field(name="🧾 Solde Actuel", value=solde_message, inline=False)
    actions_text = "🚢 **Déclarer un trajet** : T1 / T2 / T3\n💸 **Payer** : réservé patron/co-patron\n📜 **Historique** : voir les 10 dernières opérations"
    financial_embed.add_field(name="🛠️ Actions Disponibles", value=actions_text, inline=False)
    financial_embed.set_footer(text=f"Panel financier de {member.display_name}")
    return financial_embed

async def create_balances_summary_embed(guild: discord.Guild):
    embed = discord.Embed(title="📊 Récapitulatif des Soldes", description="Aperçu de tous les soldes des employés.", color=discord.Color.gold())
    finances = load_finances()
    if not finances:
        embed.description = "Aucune donnée financière trouvée."; return embed
    total_due = 0
    balance_lines = []
    for member_id, data in finances.items():
        solde = data.get("solde", 0)
        if solde > 0: total_due += solde
        try: member_name = (await guild.fetch_member(int(member_id))).display_name
        except (discord.NotFound, ValueError): member_name = f"Utilisateur Inconnu (ID: {member_id})"
        balance_lines.append(f"• {member_name} → **`{solde:,.2f} €`.replace(',', ' ')`**")
    embed.description = "\n".join(balance_lines) if balance_lines else "Aucun employé n'a de solde enregistré."
    embed.add_field(name="Total à Payer", value=f"💸 **`{total_due:,.2f} €`.replace(',', ' ')`**", inline=False)
    embed.set_footer(text=f"Dernière mise à jour le {format_paris_time(get_paris_time())}")
    return embed

class DeclareTripModal(Modal, title="Déclarer un nouveau trajet"):
    def __init__(self, member: discord.Member, original_message: discord.Message):
        super().__init__()
        self.member, self.original_message = member, original_message
    trip_type = TextInput(label="Type de trajet (T1, T2, ou T3)", placeholder="Ex: T2", max_length=2, required=True)
    location = TextInput(label="Lieu (requis pour T3 : station ou export)", placeholder="Laissez vide si ce n'est pas un T3", required=False)
    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        ttype, loc, amount_to_add = self.trip_type.value.strip().upper(), self.location.value.strip().lower(), 0
        if ttype == "T1": amount_to_add = 3200
        elif ttype == "T2": amount_to_add = 1600
        elif ttype == "T3":
            if loc not in ["station", "export"]: await interaction.followup.send("❌ Pour un T3, le lieu doit être `station` ou `export`.", ephemeral=True); return
            amount_to_add = 3200
        else: await interaction.followup.send("❌ Type de trajet invalide. Utilisez T1, T2, ou T3.", ephemeral=True); return

        finances = load_finances()
        finances[str(self.member.id)]["solde"] += amount_to_add
        save_finances(finances)
        details = f"{ttype} ({loc})" if ttype == "T3" else ttype
        add_to_history(self.member.id, "Ajout Trajet", f"+{amount_to_add}€", details)
        await log_finance_change(interaction, self.member, "Déclaration de Trajet", f"+{amount_to_add}€", details)
        await self.original_message.edit(embed=create_financial_embed(self.member))
        await update_balances_summary_panel()
        await interaction.followup.send(f"✅ Trajet **{ttype}** de **{amount_to_add}€** ajouté à {self.member.display_name}.", ephemeral=True)

class FinancialPanelView(View):
    def __init__(self): super().__init__(timeout=None)
    @discord.ui.button(label="Déclarer un trajet", style=discord.ButtonStyle.success, custom_id="declare_trip")
    async def declare_trip_button(self, interaction: discord.Interaction, button: Button):
        embed = interaction.message.embeds[0]
        try: member = await interaction.guild.fetch_member(int(embed.description.split('<@')[1].split('>')[0]))
        except (IndexError, ValueError, discord.NotFound): await interaction.response.send_message("❌ Erreur : Employé lié introuvable.", ephemeral=True); return
        await interaction.response.send_modal(DeclareTripModal(member, interaction.message))

    @discord.ui.button(label="Payer", style=discord.ButtonStyle.primary, custom_id="pay_balance")
    async def pay_button(self, interaction: discord.Interaction, button: Button):
        if not any(r.name in ["Patron", "Co-Patron"] for r in interaction.user.roles):
            await interaction.response.send_message("❌ Vous n'avez pas la permission.", ephemeral=True); return
        await interaction.response.defer(ephemeral=True)
        embed = interaction.message.embeds[0]
        try: member = await interaction.guild.fetch_member(int(embed.description.split('<@')[1].split('>')[0]))
        except (IndexError, ValueError, discord.NotFound): await interaction.followup.send("❌ Erreur : Employé lié introuvable.", ephemeral=True); return

        finances = load_finances()
        member_id_str = str(member.id)
        balance = finances.get(member_id_str, {}).get("solde", 0)
        if balance <= 0: await interaction.followup.send(f"ℹ️ Le solde de **{member.display_name}** est déjà à jour.", ephemeral=True); return

        finances[member_id_str]["solde"] = 0
        save_finances(finances)
        add_to_history(member.id, "Paiement", f"-{balance}€", "Solde remis à zéro")
        await log_finance_change(interaction, member, "Paiement", f"-{balance}€", f"Le solde de {balance}€ a été réglé.")
        await interaction.message.edit(embed=create_financial_embed(member))
        await update_balances_summary_panel()
        await interaction.followup.send(f"✅ Le solde de **{member.display_name}** a été payé.", ephemeral=True)

    @discord.ui.button(label="Historique", style=discord.ButtonStyle.secondary, custom_id="financial_history")
    async def history_button(self, interaction: discord.Interaction, button: Button):
        await interaction.response.defer(ephemeral=True)
        embed = interaction.message.embeds[0]
        try: member = await interaction.guild.fetch_member(int(embed.description.split('<@')[1].split('>')[0]))
        except (IndexError, ValueError, discord.NotFound): await interaction.followup.send("❌ Erreur : Employé lié introuvable.", ephemeral=True); return
        history = load_finances().get(str(member.id), {}).get("history", [])
        if not history: await interaction.followup.send("ℹ️ Aucun historique de transaction.", ephemeral=True); return
        history_embed = discord.Embed(title=f"📜 Historique de {member.display_name}", color=discord.Color.blue())
        description = "\n\n".join([f"`{e['timestamp']}`\n**{e['action']}**{(f' ({e['details']})' if e['details'] else '')} : `{e['amount']}`" for e in history[:10]])
        history_embed.description = description
        history_embed.set_footer(text="Affiche les 10 dernières opérations.")
        await interaction.followup.send(embed=history_embed, ephemeral=True)
    
    @discord.ui.button(label="Rafraîchir", style=discord.ButtonStyle.secondary, custom_id="refresh_financial_panel", emoji="🔄")
    async def refresh_button(self, interaction: discord.Interaction, button: Button):
        await interaction.response.defer()
        embed = interaction.message.embeds[0]
        try: member = await interaction.guild.fetch_member(int(embed.description.split('<@')[1].split('>')[0]))
        except (IndexError, ValueError, discord.NotFound): await interaction.followup.send("❌ Erreur : Employé lié introuvable.", ephemeral=True); return
        await interaction.edit_original_response(embed=create_financial_embed(member))

class BalancesSummaryView(View):
    def __init__(self): super().__init__(timeout=None)
    # Plus de bouton ici, la vue est vide mais nécessaire pour on_ready
    pass

# =================================================================================
# SECTION 8 : LOGIQUE POUR LA CRÉATION DE SALON PRIVÉ
# =================================================================================
class OpenChannelModal(Modal, title="Ouvrir un salon privé"):
    member_id = TextInput(label="ID du membre", placeholder="Collez l'ID de l'utilisateur ici")
    first_name = TextInput(label="Prénom", placeholder="Prénom de l'utilisateur")
    last_name = TextInput(label="Nom", placeholder="Nom de l'utilisateur")
    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        category = discord.utils.get(interaction.guild.categories, id=PRIVATE_CHANNEL_CATEGORY_ID)
        if not category: await interaction.followup.send("❌ Erreur : Catégorie des salons privés introuvable.", ephemeral=True); return
        try: member = await interaction.guild.fetch_member(int(self.member_id.value))
        except (ValueError, discord.NotFound): await interaction.followup.send("❌ Erreur : ID de membre invalide ou membre introuvable.", ephemeral=True); return
        channel_name = f"📁・{self.first_name.value.strip().lower()}-{self.last_name.value.strip().lower()}"
        nickname = f"{self.first_name.value.strip().title()} {self.last_name.value.strip().title()}"
        if discord.utils.get(interaction.guild.text_channels, name=channel_name):
            await interaction.followup.send(f"⚠️ Un salon nommé `{channel_name}` existe déjà.", ephemeral=True); return
        try: await member.edit(nick=nickname)
        except discord.Forbidden: await interaction.followup.send(f"⚠️ Je n'ai pas la permission de renommer {member.display_name}.", ephemeral=True)
        patron_role, co_patron_role = discord.utils.get(interaction.guild.roles, name="Patron"), discord.utils.get(interaction.guild.roles, name="Co-Patron")
        overwrites = {
            interaction.guild.default_role: discord.PermissionOverwrite(read_messages=False),
            member: discord.PermissionOverwrite(read_messages=True, send_messages=True, read_message_history=True),
            interaction.guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
        }
        if patron_role: overwrites[patron_role] = discord.PermissionOverwrite(read_messages=True)
        if co_patron_role: overwrites[co_patron_role] = discord.PermissionOverwrite(read_messages=True)
        try:
            new_channel = await interaction.guild.create_text_channel(name=channel_name, category=category, overwrites=overwrites)
            welcome_embed = discord.Embed(title=f"Bienvenue {nickname} !", description=f"Bonjour {member.mention}, bienvenue dans votre salon privé avec la direction.", color=discord.Color.blue())
            if member.joined_at: welcome_embed.add_field(name="Date de recrutement", value=discord.utils.format_dt(member.joined_at, style='F'))
            welcome_embed.set_thumbnail(url=member.display_avatar.url)
            await new_channel.send(embed=welcome_embed)
            await new_channel.send(embed=create_financial_embed(member), view=FinancialPanelView())
            await update_balances_summary_panel()
            await interaction.followup.send(f"✅ Salon {new_channel.mention} créé et {member.display_name} renommé.", ephemeral=True)
        except discord.Forbidden: await interaction.followup.send("❌ Erreur : Je n'ai pas la permission de créer un salon.", ephemeral=True)

class OpenChannelInitView(View):
    def __init__(self): super().__init__(timeout=None)
    @discord.ui.button(label="Créer un salon privé", style=discord.ButtonStyle.primary, custom_id="create_private_channel_btn")
    async def open_modal_button(self, interaction: discord.Interaction, button: Button): await interaction.response.send_modal(OpenChannelModal())

# =================================================================================
# SECTION 9 : COMMANDE SETUP POUR RAFRAÎCHIR LES PANNEAUX
# =================================================================================
@bot.command(name="setup")
@commands.has_any_role("Patron", "Co-Patron")
async def setup_panels(ctx):
    """Met à jour ou crée les panneaux d'information principaux."""
    try: await ctx.message.delete()
    except: pass 
    msg = await ctx.send(" Mise à jour des panneaux en cours...", delete_after=10)
    panels = {
        "annuaire": {"channel_id": ANNUAIRE_CHANNEL_ID, "title": "📞 Annuaire Téléphonique", "embed_coro": create_annuaire_embed, "view": AnnuaireView()},
        "absence": {"channel_id": ABSENCE_CHANNEL_ID, "title": "Gestion des Absences", "embed": discord.Embed(title="Gestion des Absences", description="Cliquez ci-dessous pour déclarer une absence.", color=discord.Color.dark_grey()), "view": AbsenceView()},
        "annonce": {"channel_id": ANNOUNCEMENT_CHANNEL_ID, "title": "Panneau des Annonces Internes", "embed": discord.Embed(title="Panneau des Annonces Internes", description="Cliquez ci-dessous pour rédiger une annonce.", color=discord.Color.dark_blue()), "view": AnnonceView()},
        "management": {"channel_id": MANAGEMENT_CHANNEL_ID, "title": "Panneau de Gestion des Employés", "embed": discord.Embed(title="Panneau de Gestion des Employés", description="Utilisez le bouton pour créer un dossier employé.", color=discord.Color.dark_red()), "view": OpenChannelInitView()},
        "balances_summary": {"channel_id": BALANCES_SUMMARY_CHANNEL_ID, "title": "📊 Récapitulatif des Soldes", "embed_coro": create_balances_summary_embed, "view": BalancesSummaryView()}
    }
    for name, config in panels.items():
        channel = bot.get_channel(config["channel_id"])
        if not channel:
            print(f"WARN: Salon pour '{name}' introuvable (ID: {config['channel_id']})"); continue
        embed_content = await config["embed_coro"](ctx.guild) if config.get("embed_coro") else config["embed"]
        try:
            found = False
            async for message in channel.history(limit=50):
                if message.author == bot.user and message.embeds and message.embeds[0].title == config["title"]:
                    await message.edit(embed=embed_content, view=config.get("view")); found = True; break
            if not found: await channel.send(embed=embed_content, view=config.get("view"))
        except discord.Forbidden: print(f"ERREUR: Permissions manquantes dans '{channel.name}' pour '{name}'.")
        except Exception as e: print(f"ERREUR lors de la mise à jour de '{name}': {e}")
    await msg.edit(content="✅ Panneaux principaux mis à jour !", delete_after=5)
@setup_panels.error
async def setup_panels_error(ctx, error):
    try: await ctx.message.delete()
    except: pass
    if isinstance(error, commands.MissingAnyRole):
        await ctx.send("❌ Vous n'avez pas la permission.", delete_after=10)
    else:
        print(f"Erreur commande !setup: {error}")
        await ctx.send(f"❌ Erreur lors du setup : {error}", delete_after=10)

# =================================================================================
# SECTION 10 : GESTION GÉNÉRALE DU BOT
# =================================================================================
@bot.event
async def on_ready():
    print(f'Bot connecté sous le nom : {bot.user.name}')
    bot.add_view(StockView())
    bot.add_view(LocationsView())
    bot.add_view(AnnuaireView())
    bot.add_view(AbsenceView())
    bot.add_view(AnnonceView())
    bot.add_view(OpenChannelInitView())
    bot.add_view(FinancialPanelView())
    bot.add_view(BalancesSummaryView())

# --- Lancement du bot ---
if TOKEN:
    bot.run(TOKEN)
else:
    print("ERREUR : Le token Discord n'a pas été trouvé.")
