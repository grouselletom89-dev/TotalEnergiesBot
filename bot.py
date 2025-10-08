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

# CHEMIN VERS LE VOLUME PERSISTANT 💾
# On s'assure que le chemin est correct pour l'environnement de Railway.
PERSISTENT_STORAGE_PATH = "/data/stocks.json"

# --- Fonctions Utilitaires (MODIFIÉES) ---
def load_stocks():
    """Charge les données depuis le volume persistant."""
    try:
        # Utilise le nouveau chemin
        with open(PERSISTENT_STORAGE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        # Si le fichier n'existe pas dans le volume, on le crée avec les valeurs par défaut
        default_data = {
            "entrepot": {"petrole_non_raffine": 0},
            "total": {
                "petrole_non_raffine": 0, "gazole": 0,
                "sp95": 0, "sp98": 0, "kerosene": 0
            }
        }
        save_stocks(default_data)
        return default_data

def save_stocks(data):
    """Sauvegarde les données dans le volume persistant."""
    # Utilise le nouveau chemin
    with open(PERSISTENT_STORAGE_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

# --- Embed principal ---
def create_embed():
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
    def __init__(self, action: str, carburant: str, original_message_id: int):
        self.action = action
        self.carburant = carburant
        self.original_message_id = original_message_id
        super().__init__(title=f"{'Ajout de' if action == 'add' else 'Retrait de'} {carburant.replace('_', ' ').title()}")

    quantite_stock = TextInput(label="Quantité", placeholder="Ex: 100")

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        
        try:
            quantite = int(self.quantite_stock.value)
        except ValueError:
            await interaction.followup.send("⚠️ La quantité doit être un nombre entier.", ephemeral=True)
            return
        
        data = load_stocks()
        target_dict = None
        if self.carburant in data.get("total", {}):
            target_dict = data["total"]
        elif self.carburant in data.get("entrepot", {}):
            target_dict = data["entrepot"]
        
        if target_dict is None:
            await interaction.followup.send("❌ Une erreur est survenue avec ce type de carburant.", ephemeral=True)
            return

        if self.action == "add":
            target_dict[self.carburant] += quantite
        else:
            target_dict[self.carburant] = max(0, target_dict[self.carburant] - quantite)

        save_stocks(data)

        try:
            original_message = await interaction.channel.fetch_message(self.original_message_id)
            if original_message:
                await original_message.edit(embed=create_embed())
                await interaction.followup.send(f"✅ Stock de **{self.carburant.replace('_', ' ')}** mis à jour !", ephemeral=True)
        except discord.NotFound:
            await interaction.followup.send("⚠️ Le message original n'a pas pu être trouvé pour la mise à jour.", ephemeral=True)
        except discord.Forbidden:
            await interaction.followup.send("⚠️ Je n'ai pas les permissions pour modifier le message original.", ephemeral=True)

# --- Vue avec le menu déroulant ---
class FuelSelectView(View):
    def __init__(self, action: str, original_message_id: int):
        super().__init__(timeout=180)
        self.action = action
        self.original_message_id = original_message_id
        self.populate_options()

    def populate_options(self):
        data = load_stocks()
        all_fuels = list(data.get('entrepot', {}).keys()) + list(data.get('total', {}).keys())
        options = [SelectOption(label=fuel.replace("_", " ").title(), value=fuel) for fuel in sorted(list(set(all_fuels)))]
        
        select_menu = self.children[0]
        if not options:
            select_menu.options = [SelectOption(label="Aucun carburant trouvé", value="disabled")]
            select_menu.disabled = True
        else:
            select_menu.options = options
            select_menu.disabled = False

    @discord.ui.select(placeholder="Choisis le type de carburant...", custom_id="fuel_selector", min_values=1, max_values=1)
    async def select_callback(self, interaction: discord.Interaction, select: Select):
        carburant_choisi = select.values[0]
        if carburant_choisi != "disabled":
            await interaction.response.send_modal(StockModal(action=self.action, carburant=carburant_choisi, original_message_id=self.original_message_id))

# --- Vue principale avec les boutons ---
class StockView(View):
    def __init__(self):
        super().__init__(timeout=None)

    async def send_fuel_select(self, interaction: discord.Interaction, action: str):
        await interaction.response.send_message(
            view=FuelSelectView(action=action, original_message_id=interaction.message.id), 
            ephemeral=True
        )

    @discord.ui.button(label="Ajouter", style=discord.ButtonStyle.success, custom_id="add_stock")
    async def add_button(self, interaction: discord.Interaction, button: Button):
        await self.send_fuel_select(interaction, "add")

    @discord.ui.button(label="Retirer", style=discord.ButtonStyle.danger, custom_id="remove_stock")
    async def remove_button(self, interaction: discord.Interaction, button: Button):
        await self.send_fuel_select(interaction, "remove")

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
    print("ERREUR : Le token Discord n'a pas été trouvé.")
