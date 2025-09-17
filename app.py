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
    return sum(b["amount"] for b in st.session_state.bets if b["match_id"] == match_id and b["competitor"] == comp)

def odds(match_id, comp):
    pool = total_pool(match_id)
    on_comp = total_on_comp(match_id, comp)
    if on_comp == 0:
        return None
    effective_pool = pool * (1 - st.session_state.commission / 100)
    return round(effective_pool / on_comp, 2)

def implied_probability(match_id, comp):
    pool = total_pool(match_id)
    on_comp = total_on_comp(match_id, comp)
    if pool == 0:
        return 0
    return round((on_comp / pool) * 100, 1)

def potential_payout(match_id, comp, bet_amount):
    o = odds(match_id, comp)
    if not o:
        return 0
    return round(bet_amount * o, 2)

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
        if new_comp.strip():
            st.session_state.competitors.append(new_comp.strip())
            save_state()

    # Suppression concurrent
    if st.session_state.competitors:
        st.subheader("Supprimer un concurrent")
        comp_to_remove = st.selectbox("Choisir le concurrent à supprimer", st.session_state.competitors)
        confirm = st.checkbox("Confirmer la suppression")
        if st.button("Supprimer concurrent"):
            if confirm:
                st.session_state.competitors = [c for c in st.session_state.competitors if c != comp_to_remove]
                # Supprimer les matchs et paris liés
                st.session_state.matches = [m for m in st.session_state.matches if m["comp_a"] != comp_to_remove and m["comp_b"] != comp_to_remove]
                st.session_state.bets = [b for b in st.session_state.bets if b["competitor"] != comp_to_remove]
                save_state()
                st.success(f"Concurrent {comp_to_remove} supprimé avec ses matchs et paris associés.")
            else:
                st.warning("Veuillez cocher la case avant de supprimer.")

    # Création de match
    if len(st.session_state.competitors) >= 2:
        st.subheader("Créer un match")
        comp_a = st.selectbox("Concurrent A", st.session_state.competitors, key="comp_a")
        comp_b = st.selectbox("Concurrent B", [c for c in st.session_state.competitors if c != comp_a], key="comp_b")
        if st.button("Créer match"):
            match_id = len(st.session_state.matches) + 1
            st.session_state.matches.append({"id": match_id, "comp_a": comp_a, "comp_b": comp_b, "closed": False, "winner": None})
            save_state()

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

with col2:
    st.header("Paris et Cotes")

    if st.session_state.matches:
        match = st.selectbox(
            "Choisir un match",
            st.session_state.matches,
            format_func=lambda m: f"{m['comp_a']} vs {m['comp_b']}" + (" ✅" if m.get("closed") else ""),
        )

        if not match["closed"]:
            st.subheader("Placer un pari")
            comp_choice = st.radio("Choisir un concurrent", [match["comp_a"], match["comp_b"]])
            first = st.text_input("Prénom du parieur")
            last = st.text_input("Nom du parieur")
            amount = st.number_input("Mise ($)", min_value=1.0, step=1.0)

            if st.button("Parier"):
                bet = {
                    "match_id": match["id"],
                    "competitor": comp_choice,
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

            for comp in [match["comp_a"], match["comp_b"]]:
                st.write(f"### {comp}")
                st.write(f"Total misé : {total_on_comp(match['id'], comp):.2f} $")
                st.write(f"Cote (après commission) : {odds(match['id'], comp) if odds(match['id'], comp) else 'N/A'}")
                st.write(f"Probabilité implicite : {implied_probability(match['id'], comp)}%")

            bets_df = pd.DataFrame([b for b in st.session_state.bets if b["match_id"] == match["id"]])
            if not bets_df.empty:
                st.subheader("Liste des paris")
                st.dataframe(bets_df)
            else:
                st.info("Aucun pari pour ce match.")

            st.subheader("Clôturer le match")
            winner = st.selectbox("Vainqueur", [match["comp_a"], match["comp_b"]], key=f"winner_{match['id']}")
            if st.button("Clôturer", key=f"close_{match['id']}"):
                for m in st.session_state.matches:
                    if m["id"] == match["id"]:
                        m["closed"] = True
                        m["winner"] = winner
                save_state()
                st.success(f"Match clôturé. Vainqueur : {winner}")

        else:
            st.subheader("Résultats du match")
            st.write(f"✅ Match clôturé. Vainqueur : {match['winner']}")

            pool = total_pool(match["id"])
            commission_amount = pool * (st.session_state.commission / 100)

            winners = [b for b in st.session_state.bets if b["match_id"] == match["id"] and b["competitor"] == match["winner"]]
            if winners:
                results = []
                total_payouts = 0
                for b in winners:
                    payout = potential_payout(match["id"], b["competitor"], b["amount"])
                    total_payouts += payout
                    results.append({
                        "Prénom": b["first_name"],
                        "Nom": b["last_name"],
                        "Mise (€)": b["amount"],
                        "Gain (€)": payout,
                    })
                st.dataframe(pd.DataFrame(results))

                bookmaker_profit = commission_amount + (pool - commission_amount - total_payouts)
                st.write(f"💰 Bénéfice du bookmaker : {bookmaker_profit:.2f} €")
            else:
                st.info("Aucun gagnant sur ce match.")
                st.write(f"💰 Bénéfice du bookmaker : {commission_amount:.2f} € (commission totale)")
    else:
        st.info("Ajoutez au moins un match pour commencer à parier.")
