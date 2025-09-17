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
        num_comp = st.slider("Nombre de concurrents dans le match", 2, max_comp)
        selected_comps = st.multiselect("Choisir les concurrents", st.session_state.competitors, default=st.session_state.competitors[:num_comp])
        if len(selected_comps) > 0:
            max_teams = min(6, len(selected_comps))
            num_teams = st.slider("Nombre de groupes / équipes", 1, max_teams)

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
