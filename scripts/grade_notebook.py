#!/usr/bin/env python3
"""
Script d'auto-notation pour les notebooks Jupyter.
Évalue les exercices et envoie les résultats par email.
"""

import os
import sys
import smtplib
import csv
import json
import re
import subprocess
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import nbformat
import numpy as np
import pandas as pd
from io import StringIO
from contextlib import redirect_stdout, redirect_stderr
import importlib.util

# ==================== CONFIGURATION ====================

SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USERNAME = os.getenv("SMTP_USERNAME")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
SENDER_EMAIL = os.getenv("SENDER_EMAIL", SMTP_USERNAME)
STUDENTS_FILE = os.getenv("STUDENTS_FILE", "scripts/students.csv")
NOTEBOOK_PATH = os.getenv("NOTEBOOK_PATH", "BIU/MSSM/td_exercices/TD_Exercices.ipynb")

# ==================== FONCTIONS D"UTILITAIRE ====================

def send_email(to_email, student_name, score, total, details, notebook_name):
    """Envoyer les résultats par email."""
    msg = MIMEMultipart()
    msg["From"] = SENDER_EMAIL
    msg["To"] = to_email
    msg["Subject"] = f"📊 Note Automatique - {notebook_name}"

    percentage = (score / total) * 100
    status = "✅ Validé" if percentage >= 50 else "❌ À améliorer"

    html = f"""
    <html>
    <body>
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
            <h2 style="color: #2c3e50;">🎓 Correction Automatique - Marketing Analytics</h2>
            <p>Bonjour <strong>{student_name}</strong>,</p>
            <div style="background: #f8f9fa; padding: 20px; border-radius: 8px; margin: 20px 0;">
                <h3 style="color: #3498db; margin-top: 0;">Votre Note : {score}/{total} ({percentage:.1f}%)</h3>
                <p style="font-size: 18px; font-weight: bold; color: {"#27ae60" if percentage >= 50 else "#e74c3c"};">
                    {status}
                </p>
            </div>
            <h3>📋 Détails par Exercice :</h3>
            <table style="width: 100%; border-collapse: collapse; margin: 20px 0;">
                <tr style="background: #3498db; color: white;">
                    <th style="padding: 12px; text-align: left;">Exercice</th>
                    <th style="padding: 12px; text-align: center;">Note</th>
                    <th style="padding: 12px; text-align: center;">Statut</th>
                </tr>
    """

    for exercise, result in details.items():
        exercise_score = result["score"]
        exercise_max = result["max"]
        exercise_status = "✅" if result["passed"] else "❌"
        exercise_color = "#27ae60" if result["passed"] else "#e74c3c"
        html += f"""
                <tr style="border-bottom: 1px solid #ddd;">
                    <td style="padding: 12px;">{exercise}</td>
                    <td style="padding: 12px; text-align: center;">{exercise_score}/{exercise_max}</td>
                    <td style="padding: 12px; text-align: center; color: {exercise_color};">{exercise_status}</td>
                </tr>
        """

    html += """
            </table>
            <p>Vous pouvez consulter les corrections dans le notebook.</p>
            <p>Pour toute question, contactez votre professeur.</p>
            <hr style="margin: 30px 0; border: none; border-top: 1px solid #eee;">
            <p style="color: #7f8c8d; font-size: 12px;">
                Email généré automatiquement - """ + datetime.now().strftime("%Y-%m-%d %H:%M:%S") + """
            </p>
        </div>
    </body>
    </html>
    """

    msg.attach(MIMEText(html, "html"))

    try:
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(SMTP_USERNAME, SMTP_PASSWORD)
        server.sendmail(SENDER_EMAIL, [to_email], msg.as_string())
        server.quit()
        print(f"✅ Email envoyé à {to_email}")
        return True
    except Exception as e:
        print(f"❌ Erreur envoi email à {to_email}: {e}")
        return False

def load_students():
    """Charger la liste des étudiants."""
    students = {}
    try:
        with open(STUDENTS_FILE, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                username = row.get("github_username", "").strip().lower()
                if username:
                    students[username] = {
                        "email": row.get("email", "").strip(),
                        "name": row.get("full_name", "").strip()
                    }
        print(f"✅ Chargé {len(students)} étudiants")
    except FileNotFoundError:
        print(f"❌ Fichier {STUDENTS_FILE} introuvable")
    except Exception as e:
        print(f"❌ Erreur lecture {STUDENTS_FILE}: {e}")
    return students

def get_current_student():
    """Identifier l"étudiant à partir du commit."""
    try:
        email = subprocess.check_output(
            ["git", "log", "-1", "--pretty=format:%ae"],
            stderr=subprocess.DEVNULL
        ).decode("utf-8").strip().lower()

        name = subprocess.check_output(
            ["git", "log", "-1", "--pretty=format:%an"],
            stderr=subprocess.DEVNULL
        ).decode("utf-8").strip()

        branch = subprocess.check_output(
            ["git", "branch", "--show-current"],
            stderr=subprocess.DEVNULL
        ).decode("utf-8").strip()

        print(f"Commit par: {name} ({email}), branche: {branch}")
        return email, name, branch
    except Exception as e:
        print(f"⚠️ Impossible d"identifier l"étudiant: {e}")
        return None, None, None

def find_student_by_branch(branch, students):
    """Trouver l"étudiant par nom de branche."""
    if branch.startswith("student-"):
        username = branch[8:].lower()
    else:
        username = branch.lower()
    return students.get(username)

def execute_cell_code(code, variables=None):
    """Exécuter du code Python dans un environnement isolé."""
    if variables is None:
        variables = {}

    spec = importlib.util.spec_from_loader("temp_module", loader=None)
    temp_module = importlib.util.module_from_spec(spec)
    sys.modules["temp_module"] = temp_module

    stdout_capture = StringIO()
    stderr_capture = StringIO()

    try:
        with redirect_stdout(stdout_capture), redirect_stderr(stderr_capture):
            for key, value in variables.items():
                setattr(temp_module, key, value)
            exec(code, temp_module.__dict__)
            result_vars = {k: v for k, v in temp_module.__dict__.items()
                          if not k.startswith("__") and k not in variables}
            return {
                "success": True,
                "stdout": stdout_capture.getvalue(),
                "stderr": stderr_capture.getvalue(),
                "variables": result_vars
            }
    except Exception as e:
        return {
            "success": False,
            "stdout": stdout_capture.getvalue(),
            "stderr": stderr_capture.getvalue(),
            "error": str(e)
        }
# ==================== FONCTIONS DE NOTATION ====================

def grade_exercise_1(cell_code, clients_df):
    """Évaluer l"Exercice 1 : Audit de base."""
    result = execute_cell_code(cell_code, {"clients": clients_df})
    if not result["success"]:
        return {"score": 0, "max": 5, "passed": False, "feedback": result["error"]}
    vars_created = result["variables"]
    score = 0
    feedback = []
    if "nb_lignes" in vars_created:
        if vars_created["nb_lignes"] == len(clients_df):
            score += 1
        else:
            feedback.append(f"nb_lignes incorrect")
    else:
        feedback.append("Variable nb_lignes manquante")
    if "nb_colonnes" in vars_created:
        if vars_created["nb_colonnes"] == len(clients_df.columns):
            score += 1
        else:
            feedback.append("nb_colonnes incorrect")
    else:
        feedback.append("Variable nb_colonnes manquante")
    if "valeurs_manquantes" in vars_created:
        score += 2
    else:
        feedback.append("Variable valeurs_manquantes manquante")
    if "nb_doublons" in vars_created:
        score += 1
    else:
        feedback.append("Variable nb_doublons manquante")
    return {"score": score, "max": 5, "passed": score >= 4, "feedback": "; ".join(feedback) if feedback else "Parfait !"}

def grade_exercise_2(cell_code, clients_df, transactions_df):
    """Évaluer l"Exercice 2 : Jointure et cohérence."""
    result = execute_cell_code(cell_code, {"clients": clients_df, "transactions": transactions_df})
    if not result["success"]:
        return {"score": 0, "max": 5, "passed": False, "feedback": result["error"]}
    vars_created = result["variables"]
    score = 0
    feedback = []
    if "merged" in vars_created:
        merged_df = vars_created["merged"]
        if "client_id" in merged_df.columns:
            if merged_df["client_id"].notna().all():
                score += 3
            else:
                feedback.append("Certaines transactions ont perdu leur client")
        else:
            feedback.append("Colonne client_id manquante")
        if "clients_sans_transaction" in vars_created:
            score += 2
        else:
            feedback.append("Variable clients_sans_transaction manquante")
    else:
        feedback.append("Variable merged manquante")
    return {"score": score, "max": 5, "passed": score >= 4, "feedback": "; ".join(feedback) if feedback else "Parfait !"}

def grade_exercise_3(cell_code, transactions_df):
    """Évaluer l"Exercice 3 : Création de variables dérivées."""
    result = execute_cell_code(cell_code, {"transactions": transactions_df.copy()})
    if not result["success"]:
        return {"score": 0, "max": 5, "passed": False, "feedback": result["error"]}
    vars_created = result["variables"]
    score = 0
    feedback = []
    if "transactions" in vars_created:
        modified_transactions = vars_created["transactions"]
        if "annee" in modified_transactions.columns:
            score += 2
        else:
            feedback.append("Colonne annee manquante")
        if "mois_lib" in modified_transactions.columns:
            score += 1
        else:
            feedback.append("Colonne mois_lib manquante")
        if "panier_moyen_par_annee" in vars_created:
            score += 2
        else:
            feedback.append("Variable panier_moyen_par_annee manquante")
    else:
        feedback.append("Variable transactions non modifiée")
    return {"score": score, "max": 5, "passed": score >= 4, "feedback": "; ".join(feedback) if feedback else "Parfait !"}

def grade_exercise_4(cell_code, transactions_df):
    """Évaluer l"Exercice 4 : Détection d"outliers."""
    result = execute_cell_code(cell_code, {"transactions": transactions_df})
    if not result["success"]:
        return {"score": 0, "max": 5, "passed": False, "feedback": result["error"]}
    vars_created = result["variables"]
    score = 0
    feedback = []
    if "outliers" in vars_created:
        outliers = vars_created["outliers"]
        percentile_99 = transactions_df["montant"].quantile(0.99)
        expected_outliers = transactions_df[transactions_df["montant"] > percentile_99]
        if len(outliers) == len(expected_outliers):
            score += 3
        else:
            feedback.append("Nombre d"outliers incorrect")
        if "commentaire" in vars_created:
            score += 2
        else:
            feedback.append("Variable commentaire manquante")
    else:
        feedback.append("Variable outliers manquante")
    return {"score": score, "max": 5, "passed": score >= 4, "feedback": "; ".join(feedback) if feedback else "Parfait !"}

def grade_exercise_5(cell_code, transactions_df):
    """Évaluer l"Exercice 5 : Calcul RFM."""
    result = execute_cell_code(cell_code, {"transactions": transactions_df})
    if not result["success"]:
        return {"score": 0, "max": 8, "passed": False, "feedback": result["error"]}
    vars_created = result["variables"]
    score = 0
    feedback = []
    if "rfm" in vars_created:
        rfm = vars_created["rfm"]
        required_columns = ["client_id", "recence", "frequence", "montant"]
        for col in required_columns:
            if col in rfm.columns:
                score += 2
            else:
                feedback.append(f"Colonne {col} manquante")
    else:
        feedback.append("Variable rfm manquante")
    return {"score": score, "max": 8, "passed": score >= 6, "feedback": "; ".join(feedback) if feedback else "Parfait !"}

def grade_exercise_6(cell_code, transactions_df):
    """Évaluer l"Exercice 6 : Scoring et actions."""
    from datetime import datetime as dt
    ref_date = transactions_df["date_transaction"].max()
    rfm = transactions_df.groupby("client_id").agg({
        "date_transaction": lambda x: (ref_date - x.max()).days,
        "client_id": "count",
        "montant": "sum"
    }).rename(columns={
        "date_transaction": "recence",
        "client_id": "frequence",
        "montant": "montant"
    }).reset_index()
    result = execute_cell_code(cell_code, {"rfm": rfm})
    if not result["success"]:
        return {"score": 0, "max": 12, "passed": False, "feedback": result["error"]}
    vars_created = result["variables"]
    score = 0
    feedback = []
    for score_type in ["score_r", "score_f", "score_m"]:
        if score_type in vars_created:
            score += 1
        else:
            feedback.append(f"Variable {score_type} manquante")
    if "segment" in vars_created:
        segments = set(vars_created["segment"])
        expected_segments = {"Champions", "Fidèles", "À risque", "Perdus"}
        if segments == expected_segments:
            score += 4
        else:
            feedback.append(f"Segments incorrects")
    else:
        feedback.append("Variable segment manquante")
    if "actions" in vars_created:
        score += 4
    else:
        feedback.append("Variable actions manquante")
    return {"score": score, "max": 12, "passed": score >= 9, "feedback": "; ".join(feedback) if feedback else "Parfait !"}
def grade_exercise_7(cell_code, churn_df):
    """Évaluer l"Exercice 7 : Pipeline et évaluation."""
    result = execute_cell_code(cell_code, {"churn": churn_df})
    if not result["success"]:
        return {"score": 0, "max": 10, "passed": False, "feedback": result["error"]}
    vars_created = result["variables"]
    score = 0
    feedback = []
    if "pipeline" in vars_created:
        score += 4
    else:
        feedback.append("Variable pipeline manquante")
    if "auc" in vars_created:
        if vars_created["auc"] > 0.5:
            score += 3
        else:
            feedback.append("AUC trop bas")
    else:
        feedback.append("Variable auc manquante")
    if "confusion_matrix" in vars_created:
        score += 3
    else:
        feedback.append("Variable confusion_matrix manquante")
    return {"score": score, "max": 10, "passed": score >= 7, "feedback": "; ".join(feedback) if feedback else "Parfait !"}

def grade_exercise_8(cell_code, churn_df):
    """Évaluer l"Exercice 8 : Lift et ROI."""
    result = execute_cell_code(cell_code, {"churn": churn_df})
    if not result["success"]:
        return {"score": 0, "max": 10, "passed": False, "feedback": result["error"]}
    vars_created = result["variables"]
    score = 0
    feedback = []
    if "lift_decile_1" in vars_created:
        score += 5
    else:
        feedback.append("Variable lift_decile_1 manquante")
    if "decile_rentable" in vars_created:
        score += 5
    else:
        feedback.append("Variable decile_rentable manquante")
    return {"score": score, "max": 10, "passed": score >= 7, "feedback": "; ".join(feedback) if feedback else "Parfait !"}

def grade_exercise_9(cell_code, campagnes_df):
    """Évaluer l"Exercice 9 : Test statistique."""
    result = execute_cell_code(cell_code, {"campagnes": campagnes_df})
    if not result["success"]:
        return {"score": 0, "max": 10, "passed": False, "feedback": result["error"]}
    vars_created = result["variables"]
    score = 0
    feedback = []
    if "taux_conversion" in vars_created:
        score += 4
    else:
        feedback.append("Variable taux_conversion manquante")
    if "test_result" in vars_created:
        score += 6
    else:
        feedback.append("Variable test_result manquante")
    return {"score": score, "max": 10, "passed": score >= 7, "feedback": "; ".join(feedback) if feedback else "Parfait !"}

def grade_exercise_10(cell_code):
    """Évaluer l"Exercice 10 : Taille d"échantillon."""
    result = execute_cell_code(cell_code, {})
    if not result["success"]:
        return {"score": 0, "max": 10, "passed": False, "feedback": result["error"]}
    vars_created = result["variables"]
    score = 0
    feedback = []
    if "taille_echantillon" in vars_created:
        score += 10
    else:
        feedback.append("Variable taille_echantillon manquante")
    return {"score": score, "max": 10, "passed": score >= 7, "feedback": "; ".join(feedback) if feedback else "Parfait !"}

def grade_exercise_11(cell_code, transactions_df):
    """Évaluer l"Exercice 11 : Régression avec saisonnalité."""
    result = execute_cell_code(cell_code, {"transactions": transactions_df})
    if not result["success"]:
        return {"score": 0, "max": 10, "passed": False, "feedback": result["error"]}
    vars_created = result["variables"]
    score = 0
    feedback = []
    if "model" in vars_created:
        score += 5
    else:
        feedback.append("Variable model manquante")
    if "mape" in vars_created:
        score += 5
    else:
        feedback.append("Variable mape manquante")
    return {"score": score, "max": 10, "passed": score >= 7, "feedback": "; ".join(feedback) if feedback else "Parfait !"}

def grade_exercise_12(cell_code, model, transactions_df):
    """Évaluer l"Exercice 12 : Prévision à 3 mois."""
    result = execute_cell_code(cell_code, {"model": model, "transactions": transactions_df})
    if not result["success"]:
        return {"score": 0, "max": 10, "passed": False, "feedback": result["error"]}
    vars_created = result["variables"]
    score = 0
    feedback = []
    if "previsions" in vars_created:
        score += 5
    else:
        feedback.append("Variable previsions manquante")
    if "visualisation" in vars_created:
        score += 5
    else:
        feedback.append("Variable visualisation manquante")
    return {"score": score, "max": 10, "passed": score >= 7, "feedback": "; ".join(feedback) if feedback else "Parfait !"}

def grade_notebook(notebook_path, students_data):
    """Évaluer complètement le notebook."""
    print(f"\n📖 Chargement du notebook: {notebook_path}")
    try:
        with open(notebook_path, "r", encoding="utf-8") as f:
            notebook = nbformat.read(f, as_version=4)
        print("✅ Notebook chargé")
    except Exception as e:
        print(f"❌ Erreur chargement notebook: {e}")
        return None

    data_dir = os.path.join(os.path.dirname(notebook_path), "../data")
    try:
        clients = pd.read_csv(f"{data_dir}/clients.csv", parse_dates=["date_inscription"])
        transactions = pd.read_csv(f"{data_dir}/transactions.csv", parse_dates=["date_transaction"])
        campagnes = pd.read_csv(f"{data_dir}/campagnes.csv", parse_dates=["date_debut", "date_fin"])
        churn = pd.read_csv(f"{data_dir}/churn_dataset.csv", parse_dates=["derniere_achat"])
        print("✅ Données chargées")
    except Exception as e:
        print(f"❌ Erreur chargement données: {e}")
        return None

    exercises = {}
    current_exercise = None
    for cell in notebook.cells:
        if cell.cell_type == "markdown":
            source = "".join(cell.source)
            if "Exercice" in source and "pts" in source:
                match = re.search(r"Exercice\\s+(\\d+)", source)
                if match:
                    current_exercise = f"Exercice {match.group(1)}"
                    exercises[current_exercise] = {"code": "", "cell": None}
        elif cell.cell_type == "code" and current_exercise:
            source = "".join(cell.source)
            if "# À COMPLÉTER" in source:
                exercises[current_exercise]["code"] = source
                exercises[current_exercise]["cell"] = cell

    print(f"🎯 {len(exercises)} exercices trouvés à évaluer")
    results = {}
    total_score = 0
    total_max = 0

    for exercise_name, exercise_data in exercises.items():
        code = exercise_data["code"]
        print(f"\n🔍 Évaluation de {exercise_name}...")
        num = int(exercise_name.split()[1])
        if num == 1:
            result = grade_exercise_1(code, clients)
        elif num == 2:
            result = grade_exercise_2(code, clients, transactions)
        elif num == 3:
            result = grade_exercise_3(code, transactions)
        elif num == 4:
            result = grade_exercise_4(code, transactions)
        elif num == 5:
            result = grade_exercise_5(code, transactions)
        elif num == 6:
            result = grade_exercise_6(code, transactions)
        elif num == 7:
            result = grade_exercise_7(code, churn)
        elif num == 8:
            result = grade_exercise_8(code, churn)
        elif num == 9:
            result = grade_exercise_9(code, campagnes)
        elif num == 10:
            result = grade_exercise_10(code)
        elif num == 11:
            result = grade_exercise_11(code, transactions)
        elif num == 12:
            result = grade_exercise_12(code, None, transactions)
        else:
            result = {"score": 0, "max": 0, "passed": True, "feedback": "Non implémenté"}
        results[exercise_name] = result
        total_score += result["score"]
        total_max += result["max"]
        print(f"  → {result[\"score\"]}/{result[\"max\"]} pts")

    print(f"\n📊 Note totale: {total_score}/{total_max}")
    return {"score": total_score, "max": total_max, "details": results}
# ==================== FONCTION PRINCIPALE ====================

def main():
    """Fonction principale."""
    print("=" * 60)
    print("🎓 SYSTÈME D"AUTO-NOTATION")
    print("=" * 60)

    students = load_students()
    if not students:
        print("❌ Aucun étudiant chargé. Arrêt.")
        sys.exit(1)

    commit_email, commit_name, branch = get_current_student()

    student = None
    if commit_email:
        for username, info in students.items():
            if info["email"].lower() == commit_email.lower():
                student = {"username": username, **info}
                break

    if not student and branch:
        student = find_student_by_branch(branch, students)

    if not student:
        print("⚠️ Étudiant non identifié. Utilisation du premier étudiant par défaut.")
        first_username = next(iter(students.keys()))
        student = {"username": first_username, **students[first_username]}

    print(f"\n👤 Étudiant identifié: {student[\"name\"]} ({student[\"username\"]})")
    print(f"📧 Email: {student[\"email\"]}")

    if not os.path.exists(NOTEBOOK_PATH):
        print(f"❌ Notebook introuvable: {NOTEBOOK_PATH}")
        sys.exit(1)

    result = grade_notebook(NOTEBOOK_PATH, students)

    if result is None:
        print("❌ Échec de la notation")
        sys.exit(1)

    notebook_name = os.path.basename(NOTEBOOK_PATH)
    success = send_email(
        to_email=student["email"],
        student_name=student["name"],
        score=result["score"],
        total=result["max"],
        details=result["details"],
        notebook_name=notebook_name
    )

    if success:
        print(f"\n✅ Tâche terminée avec succès !")
        print(f"   Note: {result[\"score\"]}/{result[\"max\"]}")
        print(f"   Email envoyé à: {student[\"email\"]}")
    else:
        print(f"\n⚠️ Notation terminée mais email non envoyé")
        print(f"   Note: {result[\"score\"]}/{result[\"max\"]}")

    results_file = "results.json"
    try:
        with open(results_file, "w") as f:
            json.dump({
                "student": student,
                "timestamp": datetime.now().isoformat(),
                "result": result
            }, f, indent=2, ensure_ascii=False)
        print(f"📝 Résultats sauvegardés dans {results_file}")
    except Exception as e:
        print(f"⚠️ Impossible de sauvegarder: {e}")

if __name__ == "__main__":
    main()
