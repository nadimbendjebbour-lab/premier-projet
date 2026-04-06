from flask import Flask, render_template, request, redirect, url_for, flash
from database import get_db, init_db, ANNEES
from datetime import date

app = Flask(__name__)
app.secret_key = "caisse-bendjebbour-secret-2024"

ANNEE_COURANTE = date.today().year


# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────

def statut_annee(conn, membre_id, annee):
    row = conn.execute(
        "SELECT statut, mode_paiement, date_paiement FROM paiements WHERE membre_id=? AND annee=?",
        (membre_id, annee),
    ).fetchone()
    return row  # None si pas de ligne


def paiements_par_annee(conn, membre_id):
    rows = conn.execute(
        "SELECT * FROM paiements WHERE membre_id=? ORDER BY annee", (membre_id,)
    ).fetchall()
    return {r["annee"]: r for r in rows}


def get_stats_annee(annee):
    conn = get_db()
    total = conn.execute("SELECT COUNT(DISTINCT numero_famille) FROM membres").fetchone()[0]
    # Pour les familles : payé si AU MOINS le chef a payé
    # Pour les célibataires : payé direct
    payes = conn.execute(
        """SELECT COUNT(*) FROM paiements p
           JOIN membres m ON m.id = p.membre_id
           WHERE p.annee=? AND p.statut='payé' AND m.est_chef_famille=1
        """, (annee,)
    ).fetchone()[0]
    # Célibataires payés
    payes += conn.execute(
        """SELECT COUNT(*) FROM paiements p
           JOIN membres m ON m.id=p.membre_id
           WHERE p.annee=? AND p.statut='payé' AND m.type='celibataire'
        """, (annee,)
    ).fetchone()[0]
    somme = conn.execute(
        """SELECT COALESCE(SUM(m.montant_du),0) FROM paiements p
           JOIN membres m ON m.id=p.membre_id
           WHERE p.annee=? AND p.statut='payé'
        """, (annee,)
    ).fetchone()[0]
    conn.close()
    return dict(total=total, payes=payes, somme=somme)


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
    like = f"%{q}%"

    # ── Familles : un chef par numero_famille ──
    if q:
        familles = conn.execute(
            """SELECT m.*, p.statut AS statut_annee, p.mode_paiement, p.date_paiement
               FROM membres m
               LEFT JOIN paiements p ON p.membre_id=m.id AND p.annee=?
               WHERE m.est_chef_famille=1 AND m.type='famille'
                 AND (m.nom LIKE ? OR m.prenom LIKE ? OR CAST(m.numero_famille AS TEXT) LIKE ?)
               ORDER BY m.numero_famille""",
            (annee, like, like, like),
        ).fetchall()
        celibataires = conn.execute(
            """SELECT m.*, p.statut AS statut_annee, p.mode_paiement, p.date_paiement
               FROM membres m
               LEFT JOIN paiements p ON p.membre_id=m.id AND p.annee=?
               WHERE m.type='celibataire'
                 AND (m.nom LIKE ? OR m.prenom LIKE ? OR CAST(m.numero_famille AS TEXT) LIKE ?)
               ORDER BY m.numero_famille""",
            (annee, like, like, like),
        ).fetchall()
    else:
        familles = conn.execute(
            """SELECT m.*, p.statut AS statut_annee, p.mode_paiement, p.date_paiement
               FROM membres m
               LEFT JOIN paiements p ON p.membre_id=m.id AND p.annee=?
               WHERE m.est_chef_famille=1 AND m.type='famille'
               ORDER BY m.numero_famille""",
            (annee,),
        ).fetchall()
        celibataires = conn.execute(
            """SELECT m.*, p.statut AS statut_annee, p.mode_paiement, p.date_paiement
               FROM membres m
               LEFT JOIN paiements p ON p.membre_id=m.id AND p.annee=?
               WHERE m.type='celibataire'
               ORDER BY m.numero_famille""",
            (annee,),
        ).fetchall()

    conn.close()
    stats = get_stats_annee(annee)
    return render_template(
        "index.html",
        familles=familles,
        celibataires=celibataires,
        annees=ANNEES,
        annee=annee,
        q=q,
        stats=stats,
    )


@app.route("/famille/<int:numero>")
def famille(numero):
    annee = int(request.args.get("annee", ANNEE_COURANTE))
    if annee not in ANNEES:
        annee = ANNEE_COURANTE

    conn = get_db()
    membres = conn.execute(
        """SELECT * FROM membres WHERE numero_famille=? AND type='famille'
           ORDER BY est_chef_famille DESC, id ASC""",
        (numero,),
    ).fetchall()

    if not membres:
        conn.close()
        flash("Famille introuvable.", "danger")
        return redirect(url_for("index"))

    # Paiements par membre par année
    paiements_map = {m["id"]: paiements_par_annee(conn, m["id"]) for m in membres}
    conn.close()

    chef = next((m for m in membres if m["est_chef_famille"]), membres[0])
    return render_template(
        "famille.html",
        membres=membres,
        chef=chef,
        numero=numero,
        paiements_map=paiements_map,
        annees=ANNEES,
        annee=annee,
        annee_courante=ANNEE_COURANTE,
        today=date.today().isoformat(),
    )


@app.route("/membre/<int:id>")
def membre(id):
    conn  = get_db()
    m     = conn.execute("SELECT * FROM membres WHERE id=?", (id,)).fetchone()
    if not m:
        conn.close()
        flash("Membre introuvable.", "danger")
        return redirect(url_for("index"))
    paiements = paiements_par_annee(conn, id)
    conn.close()
    return render_template(
        "membre.html",
        m=m,
        paiements=paiements,
        annees=ANNEES,
        annee_courante=ANNEE_COURANTE,
        today=date.today().isoformat(),
    )


@app.route("/membre/<int:id>/payer", methods=["POST"])
def payer(id):
    annee  = int(request.form.get("annee", ANNEE_COURANTE))
    mode   = request.form.get("mode_paiement")
    date_p = request.form.get("date_paiement") or date.today().isoformat()
    retour = request.form.get("retour", "membre")

    if mode not in ("espèce", "chèque", "virement"):
        flash("Mode de paiement invalide.", "danger")
        return _redirect_retour(id, retour, annee)

    conn = get_db()
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
            "INSERT INTO paiements (membre_id,annee,statut,mode_paiement,date_paiement) VALUES(?,?,'payé',?,?)",
            (id, annee, mode, date_p),
        )
    conn.commit()
    conn.close()
    flash(f"Paiement {annee} enregistré.", "success")
    return _redirect_retour(id, retour, annee)


@app.route("/membre/<int:id>/annuler", methods=["POST"])
def annuler_paiement(id):
    annee  = int(request.form.get("annee", ANNEE_COURANTE))
    retour = request.form.get("retour", "membre")
    conn   = get_db()
    conn.execute(
        "UPDATE paiements SET statut='non payé', mode_paiement=NULL, date_paiement=NULL WHERE membre_id=? AND annee=?",
        (id, annee),
    )
    conn.commit()
    conn.close()
    flash(f"Paiement {annee} annulé.", "warning")
    return _redirect_retour(id, retour, annee)


def _redirect_retour(membre_id, retour, annee):
    if retour == "famille":
        conn = get_db()
        m = conn.execute("SELECT numero_famille FROM membres WHERE id=?", (membre_id,)).fetchone()
        conn.close()
        if m:
            return redirect(url_for("famille", numero=m["numero_famille"], annee=annee))
    return redirect(url_for("membre", id=membre_id))


@app.route("/ajouter", methods=["GET", "POST"])
def ajouter():
    conn = get_db()
    # Liste des familles existantes pour pouvoir ajouter un membre à une famille existante
    familles_existantes = conn.execute(
        "SELECT numero_famille, nom FROM membres WHERE est_chef_famille=1 AND type='famille' ORDER BY numero_famille"
    ).fetchall()
    max_num = conn.execute("SELECT COALESCE(MAX(numero_famille),0) FROM membres").fetchone()[0]
    conn.close()

    if request.method == "POST":
        nom    = request.form.get("nom", "").strip()
        prenom = request.form.get("prenom", "").strip()
        type_  = request.form.get("type")
        chef   = 1 if request.form.get("est_chef_famille") else 0

        if not nom or type_ not in ("famille", "celibataire"):
            flash("Veuillez remplir tous les champs obligatoires.", "danger")
            return render_template("ajouter.html", familles=familles_existantes, prochain_num=max_num+1)

        montant = 60 if type_ == "famille" else 30

        if type_ == "famille":
            mode_num = request.form.get("mode_numero", "nouveau")
            if mode_num == "existant":
                try:
                    numero = int(request.form.get("numero_existant"))
                except (TypeError, ValueError):
                    flash("Numéro de famille invalide.", "danger")
                    return render_template("ajouter.html", familles=familles_existantes, prochain_num=max_num+1)
                chef = 0  # On ne peut pas avoir deux chefs
            else:
                numero = max_num + 1
        else:
            numero = max_num + 1
            chef   = 0

        conn = get_db()
        try:
            conn.execute(
                "INSERT INTO membres (numero_famille,nom,prenom,type,montant_du,est_chef_famille) VALUES(?,?,?,?,?,?)",
                (numero, nom, prenom, type_, montant, chef),
            )
            mid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            for a in ANNEES:
                conn.execute(
                    "INSERT OR IGNORE INTO paiements (membre_id,annee,statut) VALUES(?,?,'non payé')",
                    (mid, a),
                )
            conn.commit()
            flash(f"{prenom} {nom} ajouté(e) (Famille N° {numero}).", "success")
            if type_ == "famille":
                return redirect(url_for("famille", numero=numero))
            return redirect(url_for("index"))
        except Exception as e:
            conn.rollback()
            flash(f"Erreur : {e}", "danger")
        finally:
            conn.close()

    return render_template("ajouter.html", familles=familles_existantes, prochain_num=max_num+1)


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
        numero_famille = m["numero_famille"]
        conn.close()
        flash("Modifications enregistrées.", "success")
        if type_ == "famille":
            return redirect(url_for("famille", numero=numero_famille))
        return redirect(url_for("membre", id=id))

    conn.close()
    return render_template("modifier.html", m=m)


@app.route("/supprimer/<int:id>", methods=["POST"])
def supprimer(id):
    conn = get_db()
    m    = conn.execute("SELECT * FROM membres WHERE id=?", (id,)).fetchone()
    if m:
        numero_famille = m["numero_famille"]
        type_          = m["type"]
        conn.execute("DELETE FROM membres WHERE id=?", (id,))
        conn.commit()
        conn.close()
        flash(f"{m['prenom']} {m['nom']} supprimé(e).", "warning")
        if type_ == "famille":
            # Vérifier s'il reste des membres dans cette famille
            conn2 = get_db()
            reste = conn2.execute(
                "SELECT COUNT(*) FROM membres WHERE numero_famille=?", (numero_famille,)
            ).fetchone()[0]
            conn2.close()
            if reste > 0:
                return redirect(url_for("famille", numero=numero_famille))
    else:
        conn.close()
    return redirect(url_for("index"))


# ─────────────────────────────────────────────

if __name__ == "__main__":
    init_db()
    app.run(debug=True, host="0.0.0.0", port=5000)
