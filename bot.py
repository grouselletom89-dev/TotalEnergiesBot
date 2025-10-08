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

# --- CHEMINS VERS LES FICHIERS DE DONNÉES ---
STOCKS_PATH = "/data/stocks.json"
LOCATIONS_PATH = "/data/locations.json"
ANNUAIRE_PATH = "/data/annuaire.json"

def get_paris_time():
    paris_tz = pytz.timezone("Europe/Paris")
    return datetime.now(paris_tz).strftime('%d/%m/%Y %H:%M:%S')

# =================================================================================
# SECTION 1 : LOGIQUE POUR LA COMMANDE !STOCKS
# =================================================================================
# ... (Le code pour !stocks est inchangé et reste ici)
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
    embed.set_footer(text=f"Dernière mise à jour le {get_paris_time()}")
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
        super().__init__(timeout=180); self.original_message_id, self.category = original_message_id, category
        data = load_stocks(); fuels = list(data.get(self.category, {}).keys()); options = [SelectOption(label=f.replace("_", " ").title(), value=f) for f in sorted(fuels)]; 
        is_disabled = not bool(options)
        if not options: options = [SelectOption(label="Aucun carburant ici", value="disabled")]
        self.fuel_select = Select(placeholder="Choisis le carburant...", options=options, disabled=is_disabled)
        async def select_callback(interaction: discord.Interaction):
            carburant = interaction.data["values"][0]
            if carburant != "disabled": await interaction.response.send_modal(StockModal(category=self.category, carburant=carburant, original_message_id=self.original_message_id))
        self.fuel_select.callback = select_callback; self.add_item(self.fuel_select)
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
def load_locations():
    try:
        with open(LOCATIONS_PATH, "r", encoding="utf-8") as f: return json.load(f)
    except FileNotFoundError: return get_default_locations()
def save_locations(data):
    with open(LOCATIONS_PATH, "w", encoding="utf-8") as f: json.dump(data, f, indent=4, ensure_ascii=False)
def get_default_locations():
    default_data = {"stations": {"Station de Lampaul": {"last_updated": "N/A", "pumps": {"POMPE 1": {"gazole": 0, "sp95": 0, "sp98": 0}, "POMPE 2": {"gazole": 0, "sp95": 0, "sp98": 0}, "POMPE 3": {"gazole": 0, "sp95": 0, "sp98": 0}}}, "Station de Ligoudou": {"last_updated": "N/A", "pumps": {"POMPE 1": {"gazole": 0, "sp95": 0, "sp98": 0}, "POMPE 2": {"gazole": 0, "sp95": 0, "sp98": 0}}}},"ports": {"Port de Lampaul": {"last_updated": "N/A", "pumps": {"POMPE 1": {"gazole": 0, "sp95": 0, "sp98": 0}}}, "Port de Ligoudou": {"last_updated": "N/A", "pumps": {"POMPE 1": {"gazole": 0, "sp95": 0, "sp98": 0}}}},"aeroport": {"Aéroport": {"last_updated": "N/A", "pumps": {"POMPE 1": {"kerosene": 0}}}}}
    save_locations(default_data); return default_data
def create_locations_embed():
    data = load_locations(); embed = discord.Embed(title="Statut des pompes", color=0x0099ff)
    categories = {"stations": "🚉 Stations", "ports": "⚓ Ports", "aeroport": "✈️ Aéroport"}
    for cat_key, cat_name in categories.items():
        locations = data.get(cat_key)
        if not locations: continue
        embed.add_field(name=f"**{cat_name}**", value="\u200b", inline=False)
        for loc_name, loc_data in locations.items():
            pump_text = ""
            for pump_name, pump_fuels in loc_data.get("pumps", {}).items():
                pump_text += f"🔧 **{pump_name.upper()}**\n"
                for fuel, qty in pump_fuels.items(): pump_text += f"⛽ {fuel.capitalize()}: **{qty:,}L**\n".replace(',', ' ')
            pump_text += f"🕒 *{loc_data.get('last_updated', 'N/A')}*\n\u200b\n"
            embed.add_field(name=loc_name, value=pump_text, inline=True)
        if len(locations) % 2 != 0: embed.add_field(name="\u200b", value="\u200b", inline=True)
        if cat_key != list(categories.keys())[-1]: embed.add_field(name="\u200b", value="\u200b", inline=False)
    return embed
class LocationUpdateModal(Modal):
    def __init__(self, category_key: str, location_name: str, pump_name: str, original_message_id: int):
        super().__init__(title=f"{pump_name} - {location_name}"); self.category_key, self.location_name, self.pump_name, self.original_message_id = category_key, location_name, pump_name, original_message_id
        fuels = load_locations()[category_key][location_name]["pumps"][pump_name]
        for fuel, qty in fuels.items(): self.add_item(TextInput(label=f"Nouv. qté pour {fuel.upper()}", custom_id=fuel, default=str(qty)))
    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True); data = load_locations(); pump_data = data[self.category_key][self.location_name]["pumps"][self.pump_name]
        for field in self.children:
            try: pump_data[field.custom_id] = int(field.value)
            except ValueError: await interaction.followup.send(f"⚠️ La qté pour {field.custom_id.upper()} doit être un nombre.", ephemeral=True); return
        data[self.category_key][self.location_name]["last_updated"] = get_paris_time(); save_locations(data)
        try:
            msg = await interaction.channel.fetch_message(self.original_message_id)
            if msg: await msg.edit(embed=create_locations_embed())
            await interaction.followup.send("✅ Pompe mise à jour !", ephemeral=True)
        except (discord.NotFound, discord.Forbidden): await interaction.followup.send("⚠️ Pompe mise à jour, mais actualisation auto. échouée.", ephemeral=True)
class PumpSelectView(View):
    def __init__(self, category_key: str, location_name: str, original_message_id: int):
        super().__init__(timeout=180); self.category_key, self.location_name, self.original_message_id = category_key, location_name, original_message_id
        pumps = list(load_locations()[category_key][location_name].get("pumps", {}).keys()); options = [SelectOption(label=p.upper()) for p in pumps]
        self.children[0].options = options if pumps else [SelectOption(label="Aucune pompe trouvée", value="disabled")]
    @discord.ui.select(placeholder="Choisis une POMPE...", custom_id="locations_pump_selector")
    async def select_callback(self, i: discord.Interaction, select: Select):
        pump_name = select.values[0]
        if pump_name != "disabled": await i.response.send_modal(LocationUpdateModal(self.category_key, self.location_name, pump_name, self.original_message_id))
class LocationSelectView(View):
    def __init__(self, category_key: str, original_message_id: int):
        super().__init__(timeout=180); self.category_key, self.original_message_id = category_key, original_message_id
        locations = list(load_locations().get(category_key, {}).keys()); options = [SelectOption(label=loc) for loc in locations]
        self.children[0].options = options if locations else [SelectOption(label="Aucun lieu trouvé", value="disabled")]
    @discord.ui.select(placeholder="Choisis un lieu...", custom_id="locations_loc_selector")
    async def select_callback(self, i: discord.Interaction, select: Select):
        loc_name = select.values[0]
        if loc_name != "disabled": await i.response.edit_message(content="Choisis une POMPE :", view=PumpSelectView(self.category_key, loc_name, self.original_message_id))
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
    @discord.ui.button(label="Rafraîchir", style=discord.ButtonStyle.secondary, custom_id="refresh_locations")
    async def refresh_button(self, i: discord.Interaction, b: Button): await i.response.edit_message(embed=create_locations_embed(), view=self)
@bot.command(name="stations")
async def stations(ctx): await ctx.send(embed=create_locations_embed(), view=LocationsView())


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
    saved_data = load_annuaire()
    embed = discord.Embed(title="📞 Annuaire Téléphonique", color=discord.Color.blue())
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
    embed.set_footer(text=f"Mis à jour le {get_paris_time()}")
    return embed

class AnnuaireModal(Modal, title="Mon numéro de téléphone"):
    phone_number = TextInput(label="Saisis ton numéro ici (laisse vide pour le supprimer)", placeholder="Ex: 0612345678", required=False)
    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        data, user, number = load_annuaire(), interaction.user, self.phone_number.value.strip()
        for role_group in data.values():
            role_group[:] = [entry for entry in role_group if entry['id'] != user.id]
        role_priority = ["Patron", "Co-Patron", "Chef d'équipe", "Employé"]
        user_role_name = next((name for name in role_priority if discord.utils.get(user.roles, name=name)), None)
        if user_role_name and number:
            data.setdefault(user_role_name, []).append({"id": user.id, "name": user.display_name, "number": number})
        save_annuaire(data)
        try:
            async for message in interaction.channel.history(limit=100):
                if message.author == bot.user and message.embeds and message.embeds[0].title == "📞 Annuaire Téléphonique":
                    await message.edit(embed=await create_annuaire_embed(interaction.guild)); break
            await interaction.followup.send("✅ Ton numéro a été mis à jour !", ephemeral=True)
        except (discord.NotFound, discord.Forbidden): await interaction.followup.send("✅ Ton numéro est sauvegardé, mais le panneau n'a pas pu être actualisé.", ephemeral=True)

class ReportSelectView(View):
    def __init__(self):
        super().__init__(timeout=180)
        all_users = [SelectOption(label=u['name'], value=str(u['id'])) for rg in load_annuaire().values() for u in rg]
        placeholder = "Qui veux-tu signaler ?";
        if len(all_users) > 25: all_users = all_users[:25]; placeholder = "Qui veux-tu signaler ? (25 premiers)"
        if not all_users: all_users.append(SelectOption(label="Personne dans l'annuaire", value="disabled"))
        self.user_select = Select(placeholder=placeholder, options=all_users)
        async def select_callback(interaction: discord.Interaction):
            await interaction.response.defer(ephemeral=True)
            user_id_to_report = interaction.data["values"][0]
            if user_id_to_report == "disabled": await interaction.followup.send("Action annulée.", ephemeral=True); return
            report_channel = bot.get_channel(REPORT_CHANNEL_ID)
            if not report_channel: await interaction.followup.send("❌ Erreur : Salon de signalement non trouvé.", ephemeral=True); return
            try:
                member_to_report = await interaction.guild.fetch_member(int(user_id_to_report))
                annuaire_link = f"https://discord.com/channels/{interaction.guild.id}/{ANNUAIRE_CHANNEL_ID}"
                await report_channel.send(f"Bonjour {member_to_report.mention}, ton numéro dans l'annuaire semble incorrect. Merci de le mettre à jour ici : {annuaire_link}")
                await interaction.followup.send(f"✅ {member_to_report.display_name} a été notifié(e).", ephemeral=True)
            except (discord.NotFound, discord.Forbidden): await interaction.followup.send("❌ Erreur lors de la notification.", ephemeral=True)
        self.user_select.callback = select_callback
        self.add_item(self.user_select)

# --- CORRIGÉ : Vue pour demander une mise à jour (personnes sans numéro) ---
class RequestUpdateView(View):
    def __init__(self, interaction: discord.Interaction):
        super().__init__(timeout=180)
        self.interaction = interaction # Garde l'interaction originale pour la réponse

        # Prépare les options pour le menu déroulant
        saved_data = load_annuaire()
        all_registered_ids = {user['id'] for group in saved_data.values() for user in group}
        role_priority = ["Patron", "Co-Patron", "Chef d'équipe", "Employé"]
        
        options = []
        for role_name in role_priority:
            role = discord.utils.get(interaction.guild.roles, name=role_name)
            if role:
                for member in role.members:
                    if member.id not in all_registered_ids:
                        options.append(SelectOption(label=member.display_name, value=str(member.id)))

        placeholder = "Qui notifier pour renseigner son numéro ?"
        if len(options) > 25:
            options = options[:25]
            placeholder = "Qui notifier ? (25 premiers)"
        if not options:
            options = [SelectOption(label="Tout le monde est à jour !", value="disabled")]
        
        # Crée le menu déroulant dynamiquement
        self.user_select = Select(placeholder=placeholder, options=options, disabled=(not options or options[0].value == "disabled"))

        # Définit le callback
        async def select_callback(interaction: discord.Interaction):
            await interaction.response.defer(ephemeral=True)
            user_id_to_notify = interaction.data["values"][0]
            if user_id_to_notify == "disabled":
                await interaction.followup.send("Action annulée.", ephemeral=True)
                return

            report_channel = bot.get_channel(REPORT_CHANNEL_ID)
            if not report_channel:
                await interaction.followup.send("❌ Erreur : Salon de signalement non trouvé.", ephemeral=True)
                return

            try:
                member_to_notify = await interaction.guild.fetch_member(int(user_id_to_notify))
                annuaire_link = f"https://discord.com/channels/{interaction.guild.id}/{ANNUAIRE_CHANNEL_ID}"
                await report_channel.send(f"Bonjour {member_to_notify.mention}, il semble que tu n'aies pas encore renseigné ton numéro dans l'annuaire. Merci de le faire ici : {annuaire_link}")
                await interaction.followup.send(f"✅ {member_to_notify.display_name} a été notifié(e).", ephemeral=True)
            except (discord.NotFound, discord.Forbidden):
                await interaction.followup.send("❌ Erreur lors de la notification.", ephemeral=True)
        
        # Lie le callback et ajoute l'item
        self.user_select.callback = select_callback
        self.add_item(self.user_select)

class AnnuaireView(View):
    def __init__(self): super().__init__(timeout=None)
    @discord.ui.button(label="Saisir / Modifier mon numéro", style=discord.ButtonStyle.primary, custom_id="update_annuaire_number")
    async def update_number_button(self, i: discord.Interaction, b: Button): await i.response.send_modal(AnnuaireModal())
    
    @discord.ui.button(label="Demander d'actualiser", style=discord.ButtonStyle.secondary, custom_id="request_annuaire_update")
    async def request_update_button(self, interaction: discord.Interaction, button: Button):
        # La vue a besoin de 'interaction' pour peupler la liste des membres
        await interaction.response.send_message(view=RequestUpdateView(interaction), ephemeral=True)

    @discord.ui.button(label="Rafraîchir", style=discord.ButtonStyle.secondary, custom_id="refresh_annuaire")
    async def refresh_button(self, i: discord.Interaction, b: Button): await i.response.edit_message(embed=await create_annuaire_embed(i.guild), view=self)

    @discord.ui.button(label="Signaler numéro invalide", style=discord.ButtonStyle.danger, custom_id="report_annuaire_number")
    async def report_number_button(self, i: discord.Interaction, b: Button): await i.response.send_message(view=ReportSelectView(), ephemeral=True)

@bot.command(name="annuaire")
async def annuaire(ctx): await ctx.send(embed=await create_annuaire_embed(ctx.guild), view=AnnuaireView())


# =================================================================================
# SECTION 4 : GESTION GÉNÉRALE DU BOT
# =================================================================================
@bot.event
async def on_ready():
    print(f'Bot connecté sous le nom : {bot.user.name}')
    bot.add_view(StockView())
    bot.add_view(LocationsView())
    bot.add_view(AnnuaireView())

# --- Lancement du bot ---
if TOKEN:
    bot.run(TOKEN)
else:
    print("ERREUR : Le token Discord n'a pas été trouvé.")
