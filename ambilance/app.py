from flask import Flask, render_template, request, redirect, url_for
import pandas as pd
import joblib
import json
import os
import uuid
app = Flask(__name__)
# Charger les modèles
model_1 = joblib.load('modele_random_forest.pkl')
model_2 = joblib.load('random_forest_model1.pkl')
# Fonction de sauvegarde JSON
def sauvegarder_donnees(user_data, fichier='C:\\Users\\HP\\Documents\\ethique project\\ambilance\\static\\donnees.json'):
    if os.path.exists(fichier):
        with open(fichier, 'r') as f:
            try:
                data = json.load(f)
            except json.JSONDecodeError:
                data = []
    else:
        data = []

    data.append(user_data)

    with open(fichier, 'w') as f:
        json.dump(data, f, indent=4)

# Fonction pour calculer le score de priorité
def calculer_score_priorite(urgence, score_survie, distance, temps_alerte):
    urgence_val = {'Critique': 3, 'Élevé': 2, 'Moyen': 1}.get(urgence, 1)
    score = (
        3 * urgence_val +
        0.5 * score_survie -
        1.2 * distance -
        1.0 * temps_alerte
    )
    return round(score, 2)

def sauvegarder_comparaison(user_id, urgence, score_survie, distance, temps_depuis_alerte,
                             fichier='static/comparison.json'):
    try:
        if os.path.exists(fichier):
            with open(fichier, 'r', encoding='utf-8') as f:
                try:
                    data = json.load(f)
                except json.JSONDecodeError:
                    print("[WARN] Fichier JSON corrompu, initialisation vide.")
                    data = []
        else:
            print(f"[INFO] Fichier inexistant, création : {fichier}")
            data = []

        # ➕ Calcul du score final
        score_final = calculer_score_priorite(
            urgence, score_survie, distance, temps_depuis_alerte
        )

        nouvelle_entree = {
            "user_id": user_id,
            "urgence": urgence,
            "score": score_survie,
            "distance": distance,
            "temps_depuis_alerte": temps_depuis_alerte,
            "score_final": score_final
        }

        data.append(nouvelle_entree)

        with open(fichier, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)

        print(f"[OK] Comparaison sauvegardée avec score final : {nouvelle_entree}")

    except Exception as e:
        print(f"[ERREUR] Échec de sauvegarde comparaison : {e}")

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/reset")
def reset():
    global patients
    patients = []
    return redirect(url_for("index"))
@app.route('/services', methods=['GET', 'POST'])
def services():
    if request.method == 'POST':
        user_id = str(uuid.uuid4())
        age = int(request.form['age_patient'])
        temps_alerte = float(request.form['temps_depuis_alerte_min'])
        distance = float(request.form['distance_patient_km'])
        temps_deplacement = float(request.form['temps_estime_deplacement_min'])
        symptomes = request.form.get('symptomes', 'Inconnu')
        antecedents_med = request.form.get('antecedents_med', 'Inconnu')
        traitements_admin = request.form.get('traitements_admin', 'Inconnu')

        # 🔷 Prédiction avec modèle 1
        input_data_1 = pd.DataFrame([{
            'âge_patient': age,
            'temps_depuis_alerte_min': temps_alerte,
            'distance_patient_km': distance,
            'temps_estime_deplacement_min': temps_deplacement,
            'besoin_médical': 0,
            'type_incident': 0
        }])
        prediction = model_1.predict(input_data_1)[0]

        # 🔷 Sauvegarde données utilisateur
        user_data = {
            "user_id": user_id,
            "age": age,
            "symptomes": symptomes,
            "antecedents_med": antecedents_med,
            "traitements_admin": traitements_admin,
            "temps_depuis_alerte": temps_alerte,
            "distance": distance,
            "temps_deplacement": temps_deplacement,
            "urgence": int(prediction)
        }
        sauvegarder_donnees(user_data)

        # 🔷 Préparation pour modèle 2 (gravité)
        urgence_code = int(prediction)
        gravite_text = {0: 'Critique', 1: 'Moyen', 2: 'Élevé'}.get(urgence_code, 'Moyen')

        gravite_encodage = {'Critique': 0, 'Moyen': 1, 'Élevé': 2}
        gravite_num = gravite_encodage.get(gravite_text, 1)

        symptome_num = 2 if 'douleur' in symptomes.lower() else 1
        antecedents_num = 0 if antecedents_med == "Aucun" else 1
        traitements_num = 0 if traitements_admin == "Aucun" else 1

        input_data_2 = pd.DataFrame([[
            age,
            gravite_num,
            symptome_num,
            antecedents_num,
            traitements_num,
            temps_alerte,
            distance
        ]], columns=[
            'age', 'gravite', 'symptomes', 'antecedents_med',
            'traitements_admin', 'temps_depuis_alerte', 'distance'
        ])

        try:
            score_survie = model_2.predict(input_data_2)[0]

            # 🔷 Sauvegarde dans comparison.json
            sauvegarder_comparaison(
                user_id=user_id,
                urgence=gravite_text,
                score_survie=score_survie,
                distance=distance,
                temps_depuis_alerte=temps_alerte
            )

        except Exception as e:
            return f"Erreur prédiction model_2 : {str(e)}"

        # 🔷 Affichage de la page analyse
        return render_template('analyse.html',
                               gravite=gravite_text,
                               score=score_survie)

    return render_template('services.html')



@app.route('/classement')
def classement_utilisateurs():
    fichier = 'static/comparison.json'
    
    if not os.path.exists(fichier):
        return "Aucune donnée disponible."

    with open(fichier, 'r', encoding='utf-8') as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError:
            return "Erreur de lecture du fichier JSON."

    if not data:
        return "Aucun utilisateur enregistré."

    # Trier par score_final décroissant
    classement = sorted(data, key=lambda x: x.get('score_final', 0), reverse=True)

    return render_template('classement.html', classement=classement)
@app.route('/about')
def about():
    return render_template('about.html')



if __name__ == "__main__":
    app.run(debug=True)