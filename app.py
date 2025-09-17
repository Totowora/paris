import streamlit as st
import pandas as pd
import json
from datetime import datetime
import os

SAVE_FILE = "paris_data.json"

# -----------------------------
# Fonctions de sauvegarde / chargement
# -----------------------------

def save_state():
    payload = {
        "competitors": st.session_state.competitors,
        "matches": st.session_state.matches,
        "bets": st.session_state.bets,
        "commission": st.session_state.commission,
    }
    with open(SAVE_FILE, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

def load_state():
    if os.path.exists(SAVE_FILE):
        try:
            with open(SAVE_FILE, "r", encoding="utf-8") as f:
                parsed = json.load(f)
            st.session_state.competitors = parsed.get("competitors", [])
            st.session_state.matches = parsed.get("matches", [])
            st.session_state.bets = parsed.get("bets", [])
            st.session_state.commission = parsed.get("commission", 10.0)
        except Exception as e:
            st.error(f"Erreur lors du chargement du fichier de sauvegarde : {e}")

# -----------------------------
# Initialisation de l'état
# -----------------------------
if "initialized" not in st.session_state:
    st.session_state.initialized = True
    st.session_state.competitors = []
    st.session_state.matches = []
    st.session_state.bets = []
    st.session_state.commission = 10.0
    load_state()

# -----------------------------
# Fonctions utilitaires
# -----------------------------

def total_pool(match_id):
    return sum(b["amount"] for b in st.session_state.bets if b["match_id"] == match_id)

def total_on_comp(match_id, comp):
    return sum(b["amount"] for b in st.session_state.bets if b["match_id"] == match_id and b["selection"] == comp and b["type"] == "competitor")

def total_on_team(match_id, team_name, match):
    team_comps = match["teams"][team_name]
    return sum(total_on_comp(match_id, c) for c in team_comps) + sum(b["amount"] for b in st.session_state.bets if b["match_id"] == match_id and b["selection"] == team_name and b["type"] == "team")

def odds(match_id, comp):
    pool = total_pool(match_id)
    on_comp = total_on_comp(match_id, comp)
    if on_comp == 0:
        return None
    effective_pool = pool * (1 - st.session_state.commission / 100)
    return round(effective_pool / on_comp, 2)

def odds_team(match_id, team_name, match):
    pool = total_pool(match_id)
    on_team = total_on_team(match_id, team_name, match)
    if on_team == 0:
        return None
    effective_pool = pool * (1 - st.session_state.commission / 100)
    return round(effective_pool / on_team, 2)

def potential_payout(match_id, selection, bet_type, amount, match):
    if bet_type == "competitor":
        o = odds(match_id, selection)
    else:
        o = odds_team(match_id, selection, match)
    if not o:
        return 0
    return round(amount * o, 2)

def implied_probability(match_id, comp_or_team, bet_type, match):
    pool = total_pool(match_id)
    if bet_type == "competitor":
        on_amount = total_on_comp(match_id, comp_or_team)
    else:
        on_amount = total_on_team(match_id, comp_or_team, match)
    if pool == 0:
        return 0
    return round((on_amount / pool) * 100, 1)

# -----------------------------
# Interface utilisateur
# -----------------------------

st.title("🎲 Gomorra Bookmaker")

col1, col2 = st.columns([1, 2])

# -----------------------------
# Colonne gauche : Gestion
# -----------------------------
with col1:
    st.header("Gestion")

    # Ajout concurrent
    new_comp = st.text_input("Ajouter un concurrent")
    if st.button("Ajouter concurrent"):
        if new_comp.strip() and len(st.session_state.competitors) < 30:
            st.session_state.competitors.append(new_comp.strip())
            save_state()
        elif len(st.session_state.competitors) >= 30:
            st.warning("Nombre maximum de concurrents atteint (30).")

    # Suppression concurrent
    if st.session_state.competitors:
        st.subheader("Supprimer un concurrent")
        comp_to_remove = st.selectbox("Choisir le concurrent à supprimer", st.session_state.competitors)
        confirm = st.checkbox("Confirmer la suppression")
        if st.button("Supprimer concurrent"):
            if confirm:
                st.session_state.competitors = [c for c in st.session_state.competitors if c != comp_to_remove]
                st.session_state.matches = [m for m in st.session_state.matches if comp_to_remove not in sum(m["teams"].values(), [])]
                st.session_state.bets = [b for b in st.session_state.bets if b["selection"] != comp_to_remove]
                save_state()
                st.success(f"Concurrent {comp_to_remove} supprimé avec ses matchs et paris associés.")
            else:
                st.warning("Veuillez cocher la case avant de supprimer.")

    # Création de match multi-concurrents et équipes
    if len(st.session_state.competitors) > 1:
        max_comp = min(30, len(st.session_state.competitors))
        if max_comp > 2:
            num_comp = st.slider("Nombre de concurrents dans le match", 2, max_comp)
        else:
            num_comp = 2
            st.info("Nombre de concurrents fixé à 2.")

        selected_comps = st.multiselect("Choisir les concurrents", st.session_state.competitors, default=st.session_state.competitors[:num_comp])

        if len(selected_comps) > 0:
            max_teams = min(6, len(selected_comps))
            if max_teams > 1:
                num_teams = st.slider("Nombre de groupes / équipes", 1, max_teams)
            else:
                num_teams = 1
                st.info("Nombre de groupes fixé à 1.")

            teams = {}
            remaining_comps = selected_comps.copy()
            for i in range(num_teams):
                team_name = f"Equipe {i+1}"
                teams[team_name] = st.multiselect(f"Attribuer les concurrents à {team_name}", remaining_comps)
                remaining_comps = [c for c in remaining_comps if c not in teams[team_name]]

            if st.button("Créer match"):
                if remaining_comps:
                    st.error("Tous les concurrents doivent être assignés à une équipe.")
                else:
                    match_id = len(st.session_state.matches) + 1
                    st.session_state.matches.append({"id": match_id, "teams": teams, "closed": False, "winner": None})
                    save_state()
                    st.success("Match créé avec succès.")
    else:
        st.info("Ajoutez au moins 2 concurrents pour créer un match.")

    # Paramètres commission
    st.subheader("Commission")
    new_commission = st.slider("Commission (%)", 0.0, 20.0, st.session_state.commission, 0.5)
    if new_commission != st.session_state.commission:
        st.session_state.commission = new_commission
        save_state()

    # Réinitialisation
    if st.button("Réinitialiser"):
        st.session_state.competitors = []
        st.session_state.matches = []
        st.session_state.bets = []
        st.session_state.commission = 10.0
        save_state()
        st.success("Session réinitialisée")

# -----------------------------
# Colonne droite : Paris, Stats et Clôture
# -----------------------------
with col2:
    st.header("Paris et Cotes")

    if st.session_state.matches:
        match = st.selectbox(
            "Choisir un match",
            st.session_state.matches,
            format_func=lambda m: f"{' vs '.join(sum(m['teams'].values(), []))}" + (" ✅" if m.get("closed") else ""),
        )

        if not match["closed"]:
            st.subheader("Placer un pari")
            selections = list(match["teams"].keys()) + sum(match["teams"].values(), [])
            selection_choice = st.radio("Choisir un concurrent ou une équipe", selections)
            bet_type = "team" if selection_choice in match["teams"] else "competitor"

            first = st.text_input("Prénom du parieur")
            last = st.text_input("Nom du parieur")
            amount = st.number_input("Mise ($)", min_value=1.0, step=1.0)

            if st.button("Parier"):
                bet = {
                    "match_id": match["id"],
                    "selection": selection_choice,
                    "type": bet_type,
                    "amount": amount,
                    "first_name": first.strip(),
                    "last_name": last.strip(),
                    "ts": datetime.now().isoformat(),
                }
                st.session_state.bets.append(bet)
                save_state()
                st.success("Pari enregistré")

            st.subheader("Statistiques du match")
            pool = total_pool(match["id"])
            st.write(f"**Total des mises (avant commission)** : {pool:.2f} $")
            st.write(f"**Commission actuelle** : {st.session_state.commission:.1f}%")

            for sel in selections:
                sel_type = "team" if sel in match["teams"] else "competitor"
                total_mise = total_on_team(match["id"], sel, match) if sel_type == "team" else total_on_comp(match["id"], sel)
                cote = odds_team(match["id"], sel, match) if sel_type == "team" else odds(match["id"], sel)
                st.write(f"### {sel}")
                st.write(f"Total misé : {total_mise:.2f} $")
                st.write(f"Cote (après commission) : {cote if cote else 'N/A'}")
                st.write(f"Probabilité implicite : {implied_probability(match['id'], sel, sel_type, match)}%")

            bets_df = pd.DataFrame([b for b in st.session_state.bets if b["match_id"] == match["id"]])
            if not bets_df.empty:
                st.subheader("Liste des paris")
                st.dataframe(bets_df)
            else:
                st.info("Aucun pari pour ce match.")

            st.subheader("Clôturer le match")
            winner_selection = st.selectbox("Vainqueur", selections)
            if st.button("Clôturer"):
                for m in st.session_state.matches:
                    if m["id"] == match["id"]:
                        m["closed"] = True
                        m["winner"] = winner_selection
                save_state()
                st.success(f"Match clôturé. Vainqueur : {winner_selection}")

        else:
            st.subheader("Résultats du match")
            st.write(f"✅ Match clôturé. Vainqueur : {match['winner']}")

            pool = total_pool(match["id"])
            commission_amount = pool * (st.session_state.commission / 100)

            winners = [b for b in st.session_state.bets if b["match_id"] == match["id"] and (
                b["selection"] == match["winner"] or (b["type"] == "team" and match["winner"] in match["teams"] and b["selection"] == match["winner"])
            )]

            if winners:
                results = []
                total_payouts = 0
                for b in winners:
                    payout = potential_payout(match["id"], b["selection"], b["type"], b["amount"], match)
                    total_payouts += payout
                    results.append({
                        "Prénom": b["first_name"],
                        "Nom": b["last_name"],
                        "Mise (€)": b["amount"],
                        "Gain (€)": payout,
                    })
                st.subheader("Parieurs gagnants")
                st.dataframe(pd.DataFrame(results))

                bookmaker_profit = commission_amount + (pool - commission_amount - total_payouts)
                st.write(f"💰 Bénéfice du bookmaker : {bookmaker_profit:.2f} €")
            else:
                st.info("Aucun gagnant sur ce match.")
                st.write(f"💰 Bénéfice du bookmaker : {commission_amount:.2f} € (commission totale)")
    else:
        st.info("Ajoutez au moins un match pour commencer à parier.")           
