from flask import Flask, render_template, request, redirect, url_for, flash
from database import get_db, init_db
from datetime import date

app = Flask(__name__)
app.secret_key = "caisse-bendjebbour-secret-2024"


# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────

def get_stats():
    conn = get_db()
    total     = conn.execute("SELECT COUNT(*) FROM membres").fetchone()[0]
    payes     = conn.execute("SELECT COUNT(*) FROM membres WHERE statut='payé'").fetchone()[0]
    non_payes = total - payes
    somme     = conn.execute("SELECT COALESCE(SUM(montant_du),0) FROM membres WHERE statut='payé'").fetchone()[0]
    conn.close()
    return dict(total=total, payes=payes, non_payes=non_payes, somme=somme)


# ─────────────────────────────────────────────
# Routes
# ─────────────────────────────────────────────

@app.route("/")
def index():
    q = request.args.get("q", "").strip()
    conn = get_db()

    if q:
        like = f"%{q}%"
        membres = conn.execute(
            """SELECT * FROM membres
               WHERE nom LIKE ? OR prenom LIKE ? OR CAST(numero_famille AS TEXT) LIKE ?
               ORDER BY est_doyen DESC, numero_famille ASC""",
            (like, like, like),
        ).fetchall()
    else:
        membres = conn.execute(
            "SELECT * FROM membres ORDER BY est_doyen DESC, numero_famille ASC"
        ).fetchall()

    conn.close()
    stats = get_stats()
    return render_template("index.html", membres=membres, q=q, stats=stats)


@app.route("/membre/<int:id>")
def membre(id):
    conn = get_db()
    m = conn.execute("SELECT * FROM membres WHERE id=?", (id,)).fetchone()
    conn.close()
    if not m:
        flash("Membre introuvable.", "danger")
        return redirect(url_for("index"))
    today = date.today().isoformat()
    return render_template("membre.html", m=m, today=today)


@app.route("/membre/<int:id>/payer", methods=["POST"])
def payer(id):
    mode  = request.form.get("mode_paiement")
    date_p = request.form.get("date_paiement") or date.today().isoformat()

    if mode not in ("espèce", "chèque", "virement"):
        flash("Mode de paiement invalide.", "danger")
        return redirect(url_for("membre", id=id))

    conn = get_db()
    conn.execute(
        """UPDATE membres SET statut='payé', mode_paiement=?, date_paiement=?
           WHERE id=?""",
        (mode, date_p, id),
    )
    conn.commit()
    conn.close()
    flash("Paiement enregistré avec succès.", "success")
    return redirect(url_for("membre", id=id))


@app.route("/membre/<int:id>/annuler", methods=["POST"])
def annuler_paiement(id):
    conn = get_db()
    conn.execute(
        """UPDATE membres SET statut='non payé', mode_paiement=NULL, date_paiement=NULL
           WHERE id=?""",
        (id,),
    )
    conn.commit()
    conn.close()
    flash("Paiement annulé.", "warning")
    return redirect(url_for("membre", id=id))


@app.route("/ajouter", methods=["GET", "POST"])
def ajouter():
    if request.method == "POST":
        nom    = request.form.get("nom", "").strip()
        prenom = request.form.get("prenom", "").strip()
        type_  = request.form.get("type")
        doyen  = 1 if request.form.get("est_doyen") else 0

        if not nom or not prenom or type_ not in ("famille", "celibataire"):
            flash("Veuillez remplir tous les champs obligatoires.", "danger")
            return render_template("ajouter.html")

        montant = 60 if type_ == "famille" else 30

        conn = get_db()

        # Si nouveau doyen, retirer l'ancien
        if doyen:
            conn.execute("UPDATE membres SET est_doyen=0")

        # Prochain numéro de famille
        max_num = conn.execute("SELECT COALESCE(MAX(numero_famille),0) FROM membres").fetchone()[0]
        numero  = max_num + 1

        try:
            conn.execute(
                """INSERT INTO membres
                   (numero_famille, nom, prenom, type, montant_du, statut, est_doyen)
                   VALUES (?, ?, ?, ?, ?, 'non payé', ?)""",
                (numero, nom, prenom, type_, montant, doyen),
            )
            conn.commit()
            flash(f"{prenom} {nom} ajouté(e) avec succès (N° {numero}).", "success")
            return redirect(url_for("index"))
        except Exception as e:
            conn.rollback()
            flash(f"Erreur lors de l'ajout : {e}", "danger")
        finally:
            conn.close()

    return render_template("ajouter.html")


@app.route("/modifier/<int:id>", methods=["GET", "POST"])
def modifier(id):
    conn = get_db()
    m = conn.execute("SELECT * FROM membres WHERE id=?", (id,)).fetchone()
    if not m:
        conn.close()
        flash("Membre introuvable.", "danger")
        return redirect(url_for("index"))

    if request.method == "POST":
        nom    = request.form.get("nom", "").strip()
        prenom = request.form.get("prenom", "").strip()
        type_  = request.form.get("type")
        doyen  = 1 if request.form.get("est_doyen") else 0

        if not nom or not prenom or type_ not in ("famille", "celibataire"):
            flash("Veuillez remplir tous les champs obligatoires.", "danger")
            return render_template("modifier.html", m=m)

        montant = 60 if type_ == "famille" else 30

        if doyen:
            conn.execute("UPDATE membres SET est_doyen=0 WHERE id != ?", (id,))

        conn.execute(
            """UPDATE membres SET nom=?, prenom=?, type=?, montant_du=?, est_doyen=?
               WHERE id=?""",
            (nom, prenom, type_, montant, doyen, id),
        )
        conn.commit()
        conn.close()
        flash("Membre modifié avec succès.", "success")
        return redirect(url_for("membre", id=id))

    conn.close()
    return render_template("modifier.html", m=m)


@app.route("/supprimer/<int:id>", methods=["POST"])
def supprimer(id):
    conn = get_db()
    m = conn.execute("SELECT nom, prenom FROM membres WHERE id=?", (id,)).fetchone()
    if m:
        conn.execute("DELETE FROM membres WHERE id=?", (id,))
        conn.commit()
        flash(f"{m['prenom']} {m['nom']} supprimé(e).", "warning")
    conn.close()
    return redirect(url_for("index"))


# ─────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────

if __name__ == "__main__":
    init_db()
    app.run(debug=True, host="0.0.0.0", port=5000)
