from flask import Flask, render_template, request, redirect, url_for, flash
from database import get_db, init_db, ANNEES
from datetime import date

app = Flask(__name__)
app.secret_key = "caisse-bendjebbour-secret-2024"

ANNEE_COURANTE = date.today().year


# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────

def get_stats(annee):
    conn = get_db()
    total   = conn.execute("SELECT COUNT(*) FROM membres").fetchone()[0]
    payes   = conn.execute(
        "SELECT COUNT(*) FROM paiements WHERE annee=? AND statut='payé'", (annee,)
    ).fetchone()[0]
    somme   = conn.execute(
        """SELECT COALESCE(SUM(m.montant_du),0)
           FROM paiements p JOIN membres m ON m.id=p.membre_id
           WHERE p.annee=? AND p.statut='payé'""", (annee,)
    ).fetchone()[0]
    conn.close()
    return dict(total=total, payes=payes, non_payes=total - payes, somme=somme)


def paiements_pour_membre(conn, membre_id):
    rows = conn.execute(
        "SELECT * FROM paiements WHERE membre_id=? ORDER BY annee", (membre_id,)
    ).fetchall()
    return {r["annee"]: r for r in rows}


# ─────────────────────────────────────────────
# Routes
# ─────────────────────────────────────────────

@app.route("/")
def index():
    q     = request.args.get("q", "").strip()
    annee = int(request.args.get("annee", ANNEE_COURANTE))
    if annee not in ANNEES:
        annee = ANNEE_COURANTE

    conn = get_db()

    if q:
        like = f"%{q}%"
        membres = conn.execute(
            """SELECT * FROM membres
               WHERE nom LIKE ? OR prenom LIKE ? OR CAST(numero AS TEXT) LIKE ?
               ORDER BY numero ASC""",
            (like, like, like),
        ).fetchall()
    else:
        membres = conn.execute(
            "SELECT * FROM membres ORDER BY numero ASC"
        ).fetchall()

    # Pour chaque membre, récupérer tous ses paiements indexés par année
    paiements_map = {}
    for m in membres:
        paiements_map[m["id"]] = paiements_pour_membre(conn, m["id"])

    conn.close()
    stats = get_stats(annee)
    return render_template(
        "index.html",
        membres=membres,
        paiements_map=paiements_map,
        annees=ANNEES,
        annee=annee,
        q=q,
        stats=stats,
    )


@app.route("/membre/<int:id>")
def membre(id):
    conn = get_db()
    m = conn.execute("SELECT * FROM membres WHERE id=?", (id,)).fetchone()
    if not m:
        conn.close()
        flash("Membre introuvable.", "danger")
        return redirect(url_for("index"))
    paiements = paiements_pour_membre(conn, id)
    conn.close()
    today = date.today().isoformat()
    return render_template(
        "membre.html",
        m=m,
        paiements=paiements,
        annees=ANNEES,
        annee_courante=ANNEE_COURANTE,
        today=today,
    )


@app.route("/membre/<int:id>/payer", methods=["POST"])
def payer(id):
    annee  = int(request.form.get("annee", ANNEE_COURANTE))
    mode   = request.form.get("mode_paiement")
    date_p = request.form.get("date_paiement") or date.today().isoformat()

    if mode not in ("espèce", "chèque", "virement"):
        flash("Mode de paiement invalide.", "danger")
        return redirect(url_for("membre", id=id))

    conn = get_db()
    # Upsert : si la ligne n'existe pas encore pour cette année, l'insérer
    existing = conn.execute(
        "SELECT id FROM paiements WHERE membre_id=? AND annee=?", (id, annee)
    ).fetchone()
    if existing:
        conn.execute(
            "UPDATE paiements SET statut='payé', mode_paiement=?, date_paiement=? WHERE membre_id=? AND annee=?",
            (mode, date_p, id, annee),
        )
    else:
        conn.execute(
            "INSERT INTO paiements (membre_id,annee,statut,mode_paiement,date_paiement) VALUES(?,?,?,?,?)",
            (id, annee, "payé", mode, date_p),
        )
    conn.commit()
    conn.close()
    flash(f"Paiement {annee} enregistré.", "success")
    return redirect(url_for("membre", id=id))


@app.route("/membre/<int:id>/annuler", methods=["POST"])
def annuler_paiement(id):
    annee = int(request.form.get("annee", ANNEE_COURANTE))
    conn  = get_db()
    conn.execute(
        "UPDATE paiements SET statut='non payé', mode_paiement=NULL, date_paiement=NULL WHERE membre_id=? AND annee=?",
        (id, annee),
    )
    conn.commit()
    conn.close()
    flash(f"Paiement {annee} annulé.", "warning")
    return redirect(url_for("membre", id=id))


@app.route("/ajouter", methods=["GET", "POST"])
def ajouter():
    if request.method == "POST":
        nom    = request.form.get("nom", "").strip()
        prenom = request.form.get("prenom", "").strip()
        type_  = request.form.get("type")
        chef   = 1 if request.form.get("est_chef_famille") else 0

        if not nom or type_ not in ("famille", "celibataire"):
            flash("Veuillez remplir tous les champs obligatoires.", "danger")
            return render_template("ajouter.html", annees=ANNEES)

        montant = 60 if type_ == "famille" else 30
        conn    = get_db()
        max_num = conn.execute("SELECT COALESCE(MAX(numero),0) FROM membres").fetchone()[0]
        numero  = max_num + 1

        try:
            conn.execute(
                "INSERT INTO membres (numero,nom,prenom,type,montant_du,est_chef_famille) VALUES(?,?,?,?,?,?)",
                (numero, nom, prenom, type_, montant, chef),
            )
            membre_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

            # Créer les lignes de paiement vides pour toutes les années
            for a in ANNEES:
                conn.execute(
                    "INSERT OR IGNORE INTO paiements (membre_id,annee,statut) VALUES(?,?,'non payé')",
                    (membre_id, a),
                )
            conn.commit()
            flash(f"{prenom} {nom} ajouté(e) (N° {numero}).", "success")
            return redirect(url_for("index"))
        except Exception as e:
            conn.rollback()
            flash(f"Erreur : {e}", "danger")
        finally:
            conn.close()

    return render_template("ajouter.html", annees=ANNEES)


@app.route("/modifier/<int:id>", methods=["GET", "POST"])
def modifier(id):
    conn = get_db()
    m    = conn.execute("SELECT * FROM membres WHERE id=?", (id,)).fetchone()
    if not m:
        conn.close()
        flash("Membre introuvable.", "danger")
        return redirect(url_for("index"))

    if request.method == "POST":
        nom    = request.form.get("nom", "").strip()
        prenom = request.form.get("prenom", "").strip()
        type_  = request.form.get("type")
        chef   = 1 if request.form.get("est_chef_famille") else 0

        if not nom or type_ not in ("famille", "celibataire"):
            flash("Veuillez remplir tous les champs obligatoires.", "danger")
            conn.close()
            return render_template("modifier.html", m=m)

        montant = 60 if type_ == "famille" else 30
        conn.execute(
            "UPDATE membres SET nom=?,prenom=?,type=?,montant_du=?,est_chef_famille=? WHERE id=?",
            (nom, prenom, type_, montant, chef, id),
        )
        conn.commit()
        conn.close()
        flash("Modifications enregistrées.", "success")
        return redirect(url_for("membre", id=id))

    conn.close()
    return render_template("modifier.html", m=m)


@app.route("/supprimer/<int:id>", methods=["POST"])
def supprimer(id):
    conn = get_db()
    m    = conn.execute("SELECT nom, prenom FROM membres WHERE id=?", (id,)).fetchone()
    if m:
        conn.execute("DELETE FROM membres WHERE id=?", (id,))
        conn.commit()
        flash(f"{m['prenom']} {m['nom']} supprimé(e).", "warning")
    conn.close()
    return redirect(url_for("index"))


# ─────────────────────────────────────────────

if __name__ == "__main__":
    init_db()
    app.run(debug=True, host="0.0.0.0", port=5000)
