import sqlite3
import os
import random

DB_PATH = os.path.join(os.path.dirname(__file__), "caisse.db")
ANNEES  = list(range(2020, 2027))   # 2020 → 2026


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = get_db()

    # numero_famille n'est PAS unique : plusieurs membres d'une même famille partagent ce numéro.
    conn.execute("""
        CREATE TABLE IF NOT EXISTS membres (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            numero_famille   INTEGER NOT NULL,
            nom              TEXT NOT NULL,
            prenom           TEXT NOT NULL,
            type             TEXT NOT NULL CHECK(type IN ('famille','celibataire')),
            montant_du       INTEGER NOT NULL,
            est_chef_famille INTEGER NOT NULL DEFAULT 0
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS paiements (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            membre_id      INTEGER NOT NULL REFERENCES membres(id) ON DELETE CASCADE,
            annee          INTEGER NOT NULL,
            statut         TEXT NOT NULL DEFAULT 'non payé'
                               CHECK(statut IN ('payé','non payé')),
            mode_paiement  TEXT CHECK(mode_paiement IN ('espèce','chèque','virement')),
            date_paiement  TEXT,
            UNIQUE(membre_id, annee)
        )
    """)
    conn.commit()

    if conn.execute("SELECT COUNT(*) FROM membres").fetchone()[0] == 0:
        _seed(conn)

    conn.close()


def _seed(conn):
    random.seed(42)

    # Format : (numero_famille, nom, prenom, type, est_chef)
    # Plusieurs membres peuvent partager le même numero_famille (même famille)
    membres_seed = [
        # Famille 1 — Améziane (2 membres)
        (1, "Améziane",          "Hadj Mohand",   "famille",    1),
        (1, "Améziane",          "Fatima",         "famille",    0),
        # Célibataires (numéros uniques)
        (2, "Djamel",            "",               "celibataire",0),
        (3, "Lotfi",             "",               "celibataire",0),
        (4, "Mohamkied",         "",               "celibataire",0),
        # Famille 5 — Zahra (2 membres)
        (5, "Zahra",             "Fatima",         "famille",    1),
        (5, "Zahra",             "Karim",          "famille",    0),
        # Famille 6 — Villepinte (2 membres)
        (6, "Villepinte",        "Abdel Kader",    "famille",    1),
        (6, "Villepinte",        "Ahmed",          "famille",    0),
        # Familles seules
        (7, "Bencherif",         "Omar",           "famille",    1),
        (8, "Meziane",           "Samir",          "famille",    1),
        (9, "Belkacem",          "Nadia",          "famille",    1),
        (10,"Ziani",             "Rachid",         "famille",    1),
        # Célibataires
        (11,"Boudiaf",           "Amina",          "celibataire",0),
        (12,"Ferhat",            "Djamel",         "celibataire",0),
    ]

    # Paiements fixes pour les membres du cahier (photo)
    grille_fixe = {
        # (numero_famille, prenom): {annee: (statut, mode)}
        (1, "Hadj Mohand"): {2020:("payé","espèce"),2021:("payé","espèce"),2022:("payé","espèce"),
                              2023:("payé","espèce"),2024:("payé","espèce"),2025:("payé","espèce"),2026:("non payé",None)},
        (1, "Fatima"):      {2020:("payé","espèce"),2021:("payé","espèce"),2022:("payé","espèce"),
                              2023:("non payé",None),2024:("payé","espèce"),2025:("payé","espèce"),2026:("non payé",None)},
        (5, "Fatima"):      {2020:("payé","chèque"),2021:("payé","espèce"),2022:("payé","espèce"),
                              2023:("payé","virement"),2024:("payé","espèce"),2025:("payé","chèque"),2026:("non payé",None)},
        (5, "Karim"):       {2020:("payé","espèce"),2021:("non payé",None),2022:("payé","espèce"),
                              2023:("payé","espèce"),2024:("non payé",None),2025:("payé","espèce"),2026:("non payé",None)},
        (6, "Abdel Kader"): {2020:("payé","espèce"),2021:("payé","espèce"),2022:("payé","espèce"),
                              2023:("payé","espèce"),2024:("payé","chèque"),2025:("payé","espèce"),2026:("non payé",None)},
        (6, "Ahmed"):       {2020:("payé","espèce"),2021:("payé","espèce"),2022:("payé","espèce"),
                              2023:("payé","espèce"),2024:("payé","espèce"),2025:("payé","espèce"),2026:("non payé",None)},
    }

    def pmt_aleatoire(annee):
        if annee == 2026:
            return ("non payé", None)
        if random.random() > 0.35:
            return ("payé", random.choice(["espèce","chèque","virement"]))
        return ("non payé", None)

    for num_f, nom, prenom, type_, chef in membres_seed:
        montant = 60 if type_ == "famille" else 30
        conn.execute(
            "INSERT INTO membres (numero_famille,nom,prenom,type,montant_du,est_chef_famille) VALUES(?,?,?,?,?,?)",
            (num_f, nom, prenom, type_, montant, chef),
        )
        mid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

        cle = (num_f, prenom)
        for annee in ANNEES:
            if cle in grille_fixe:
                statut, mode = grille_fixe[cle].get(annee, ("non payé", None))
            else:
                statut, mode = pmt_aleatoire(annee)
            date_p = f"{annee}-01-15" if statut == "payé" else None
            conn.execute(
                "INSERT OR IGNORE INTO paiements (membre_id,annee,statut,mode_paiement,date_paiement) VALUES(?,?,?,?,?)",
                (mid, annee, statut, mode, date_p),
            )

    conn.commit()
