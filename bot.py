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
PERSISTENT_STORAGE_PATH = "/data/stocks.json"

# --- Fonctions Utilitaires ---
def load_stocks():
    """Charge les données depuis le volume persistant."""
    try:
        with open(PERSISTENT_STORAGE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
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
    with open(PERSISTENT_STORAGE_PATH, "w", encoding="utf-8") as f:
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

# --- MODIFIÉ : Le formulaire pour définir la nouvelle quantité ---
class StockModal(Modal):
    def __init__(self, carburant: str, original_message_id: int):
        self.carburant = carburant
        self.original_message_id = original_message_id
        super().__init__(title=f"Mettre à jour : {carburant.replace('_', ' ').title()}")

    nouvelle_quantite = TextInput(label="Nouvelle quantité totale", placeholder="Ex: 5000")

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        try:
            quantite = int(self.nouvelle_quantite.value)
            if quantite < 0: # S'assure que la quantité n'est pas négative
                await interaction.followup.send("⚠️ La quantité ne peut pas être négative.", ephemeral=True)
                return
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

        # Définit directement la nouvelle quantité
        target_dict[self.carburant] = quantite
        save_stocks(data)

        try:
            original_message = await interaction.channel.fetch_message(self.original_message_id)
            if original_message:
                await original_message.edit(embed=create_embed())
                await interaction.followup.send(f"✅ Stock de **{self.carburant.replace('_', ' ')}** mis à jour à **{quantite}** !", ephemeral=True)
        except (discord.NotFound, discord.Forbidden):
            await interaction.followup.send("⚠️ Le panneau principal a été mis à jour, mais n'a pas pu être actualisé automatiquement.", ephemeral=True)

# --- Vue du menu déroulant (légèrement modifiée) ---
class FuelSelectView(View):
    def __init__(self, original_message_id: int, category: str):
        super().__init__(timeout=180)
        self.original_message_id = original_message_id
        self.category = category
        self.populate_options()

    def populate_options(self):
        data = load_stocks()
        fuels_in_category = list(data.get(self.category, {}).keys())
        options = [SelectOption(label=fuel.replace("_", " ").title(), value=fuel) for fuel in sorted(fuels_in_category)]
        
        select_menu = self.children[0]
        if not options:
            select_menu.options = [SelectOption(label="Aucun carburant dans cette catégorie", value="disabled")]
            select_menu.disabled = True
        else:
            select_menu.options = options
            select_menu.disabled = False

    @discord.ui.select(placeholder="Choisis le carburant à mettre à jour...", custom_id="fuel_selector")
    async def select_callback(self, interaction: discord.Interaction, select: Select):
        carburant_choisi = select.values[0]
        if carburant_choisi != "disabled":
            await interaction.response.send_modal(StockModal(carburant=carburant_choisi, original_message_id=self.original_message_id))

# --- Vue pour choisir la catégorie (légèrement modifiée) ---
class CategorySelectView(View):
    def __init__(self, original_message_id: int):
        super().__init__(timeout=180)
        self.original_message_id = original_message_id

    async def show_fuel_select(self, interaction: discord.Interaction, category: str):
        view = FuelSelectView(original_message_id=self.original_message_id, category=category)
        await interaction.response.edit_message(content="Maintenant, choisis le carburant :", view=view)

    @discord.ui.button(label="📦 Entrepôt", style=discord.ButtonStyle.secondary)
    async def entrepot_button(self, interaction: discord.Interaction, button: Button):
        await self.show_fuel_select(interaction, "entrepot")

    @discord.ui.button(label="📊 Total", style=discord.ButtonStyle.secondary)
    async def total_button(self, interaction: discord.Interaction, button: Button):
        await self.show_fuel_select(interaction, "total")

# --- MODIFIÉ : La vue principale avec un seul bouton "Mettre à jour" ---
class StockView(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Mettre à jour", style=discord.ButtonStyle.success, custom_id="update_stock")
    async def update_button(self, interaction: discord.Interaction, button: Button):
        # Ouvre directement la vue pour choisir la catégorie
        await interaction.response.send_message(
            content="Dans quelle catégorie souhaites-tu mettre à jour un stock ?",
            view=CategorySelectView(original_message_id=interaction.message.id), 
            ephemeral=True
        )

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
