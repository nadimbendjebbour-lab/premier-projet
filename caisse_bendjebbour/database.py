import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "caisse.db")
ANNEES  = list(range(2020, 2027))   # 2020 → 2026


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = get_db()

    conn.execute("""
        CREATE TABLE IF NOT EXISTS membres (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            numero           INTEGER UNIQUE NOT NULL,
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
    # (numero, nom, prenom, type, est_chef)
    membres = [
        (1,  "Fils de Abdel Kader", "Ahmed",        "famille",    1),
        (2,  "Djamel",              "",              "celibataire",0),
        (3,  "Lotfi",               "",              "celibataire",0),
        (4,  "Mohamkied",           "",              "celibataire",0),
        (5,  "Zahra",               "Fatima",        "famille",    1),
        (6,  "Taxi Villepinte",     "Abdel Kader",   "famille",    1),
        (7,  "Bencherif",           "Karim",         "famille",    1),
        (8,  "Ouali",               "Fatima",        "famille",    0),
        (9,  "Meziane",             "Samir",         "famille",    1),
        (10, "Belkacem",            "Omar",          "famille",    1),
        (11, "Ziani",               "Kheira",        "famille",    0),
        (12, "Idir",                "Massinissa",    "famille",    1),
        (13, "Boudiaf",             "Amina",         "celibataire",0),
        (14, "Ferhat",              "Djamel",        "celibataire",0),
        (15, "Cherif",              "Lynda",         "celibataire",0),
    ]

    # Grille de paiements tirée du cahier (photo) pour les 6 premiers,
    # données fictives pour les suivants.
    # Format : {numero: {annee: (statut, mode)}}
    grille = {
        1: {2020:("payé","espèce"),  2021:("payé","espèce"),  2022:("payé","espèce"),
            2023:("payé","espèce"),  2024:("payé","espèce"),  2025:("payé","espèce"),  2026:("non payé",None)},
        2: {2020:("payé","espèce"),  2021:("payé","espèce"),  2022:("payé","chèque"),
            2023:("payé","espèce"),  2024:("payé","espèce"),  2025:("payé","espèce"),  2026:("non payé",None)},
        3: {2020:("payé","espèce"),  2021:("payé","espèce"),  2022:("payé","espèce"),
            2023:("payé","espèce"),  2024:("non payé",None),  2025:("payé","virement"),2026:("non payé",None)},
        4: {2020:("payé","espèce"),  2021:("payé","espèce"),  2022:("payé","espèce"),
            2023:("non payé",None),  2024:("payé","espèce"),  2025:("payé","espèce"),  2026:("non payé",None)},
        5: {2020:("payé","espèce"),  2021:("payé","chèque"),  2022:("payé","espèce"),
            2023:("payé","espèce"),  2024:("payé","virement"),2025:("payé","espèce"),  2026:("non payé",None)},
        6: {2020:("payé","espèce"),  2021:("payé","espèce"),  2022:("payé","espèce"),
            2023:("payé","espèce"),  2024:("payé","chèque"),  2025:("payé","espèce"),  2026:("non payé",None)},
    }
    # Défaut pour les membres 7-15
    import random
    random.seed(42)
    for num in range(7, 16):
        grille[num] = {}
        for a in ANNEES:
            if a == 2026:
                grille[num][a] = ("non payé", None)
            elif random.random() > 0.3:
                grille[num][a] = ("payé", random.choice(["espèce","chèque","virement"]))
            else:
                grille[num][a] = ("non payé", None)

    for num, nom, prenom, type_, chef in membres:
        montant = 60 if type_ == "famille" else 30
        conn.execute(
            "INSERT INTO membres (numero,nom,prenom,type,montant_du,est_chef_famille) VALUES(?,?,?,?,?,?)",
            (num, nom, prenom, type_, montant, chef),
        )
        membre_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

        for annee in ANNEES:
            statut, mode = grille[num].get(annee, ("non payé", None))
            date_p = f"{annee}-01-15" if statut == "payé" else None
            conn.execute(
                "INSERT INTO paiements (membre_id,annee,statut,mode_paiement,date_paiement) VALUES(?,?,?,?,?)",
                (membre_id, annee, statut, mode, date_p),
            )

    conn.commit()
