import discord
from discord.ext import commands
from discord.ui import View, Button, Modal
from discord import TextInput
import json
from datetime import datetime
import os

# --- DÉFINITION DU BOT ---

# 1. Récupération du jeton
# Assurez-vous que la variable d'environnement "DISCORD_TOKEN" est bien définie.
TOKEN = os.environ.get("DISCORD_TOKEN")

# 2. Définition des Intents et activation du contenu de message
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
        # Retourne la structure de données initiale si le fichier n'existe pas
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
    """Sauvegarde les données de stock."""
    with open("stocks.json", "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)


## Événements Discord
@bot.event
async def on_ready():
    print(f'Bot connecté sous le nom : {bot.user.name}')
    # Enregistre la vue pour la persistance des boutons après redémarrage
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

        # CORRECTION : Le label est positionnel (sans nom), le reste est nommé.
        self.add_item(TextInput(
            "Type de carburant ou pétrole",  # Le label, SANS "label="
            custom_id="type_carburant",
            placeholder="Ex: gazole, petrole_non_raffine..."
        ))
        
        self.add_item(TextInput(
            "Quantité", # Le label, SANS "label="
            custom_id="quantite_stock",
            placeholder="Ex: 100"
        ))


    async def callback(self, interaction: discord.Interaction):
        carburant = self.children[0].value.lower().strip().replace(" ", "_")
        
        try:
            quantite = int(self.children[1].value)
        except ValueError:
            await interaction.response.send_message("⚠️ La quantité doit être un nombre entier.", ephemeral=True)
            return
            
        try:
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
            
        except Exception as e:
            print(f"Erreur lors du traitement du stock: {e}") 
            await interaction.response.send_message("💥 Une erreur interne est survenue. Vérifiez la console.", ephemeral=True)


# --- Vue avec les boutons ---
class StockView(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Ajouter", style=discord.ButtonStyle.success, custom_id="add_stock")
    async def add_button(self, interaction: discord.Interaction, button: Button):
        try:
            await interaction.response.send_modal(StockModal(action="add"))
        except Exception as e:
            print(f"Erreur lors de l'envoi du Modal: {e}")
            await interaction.response.send_message("💥 Impossible d'ouvrir le formulaire.", ephemeral=True)

    @discord.ui.button(label="Retirer", style=discord.ButtonStyle.danger, custom_id="remove_stock")
    async def remove_button(self, interaction: discord.Interaction, button: Button):
        try:
            await interaction.response.send_modal(StockModal(action="remove"))
        except Exception as e:
            print(f"Erreur lors de l'envoi du Modal: {e}")
            await interaction.response.send_message("💥 Impossible d'ouvrir le formulaire.", ephemeral=True)

    @discord.ui.button(label="Rafraîchir", style=discord.ButtonStyle.primary, custom_id="refresh_stock")
    async def refresh_button(self, interaction: discord.Interaction, button: Button):
        await interaction.response.edit_message(embed=create_embed(), view=self)


# --- Commande Discord ---
@bot.command(name="stocks")
async def stocks(ctx):
    embed = create_embed()
    view = StockView()
    await ctx.send(embed=embed, view=view)

# Lancement du bot
if TOKEN:
    bot.run(TOKEN)
else:
    print("Erreur : Le token Discord n'a pas été trouvé. Assurez-vous d'avoir défini la variable d'environnement DISCORD_TOKEN.")
