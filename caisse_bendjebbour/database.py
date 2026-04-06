import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "caisse.db")


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS membres (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            numero_famille INTEGER UNIQUE NOT NULL,
            nom TEXT NOT NULL,
            prenom TEXT NOT NULL,
            type TEXT NOT NULL CHECK(type IN ('famille', 'celibataire')),
            montant_du INTEGER NOT NULL,
            statut TEXT NOT NULL DEFAULT 'non payé' CHECK(statut IN ('payé', 'non payé')),
            mode_paiement TEXT CHECK(mode_paiement IN ('espèce', 'chèque', 'virement')),
            date_paiement TEXT,
            est_doyen INTEGER NOT NULL DEFAULT 0
        )
    """)
    conn.commit()

    row = conn.execute("SELECT COUNT(*) FROM membres").fetchone()
    if row[0] == 0:
        _seed(conn)

    conn.close()


def _seed(conn):
    membres = [
        # (numero_famille, nom, prenom, type, statut, mode_paiement, date_paiement, est_doyen)
        (1,  "Améziane",    "Hadj Mohand",   "famille",    "payé",     "espèce",   "2024-01-15", 1),
        (2,  "Bencherif",   "Karim",          "famille",    "payé",     "virement", "2024-02-03", 0),
        (3,  "Ouali",       "Fatima",         "famille",    "payé",     "chèque",   "2024-01-28", 0),
        (4,  "Hadj",        "Youcef",         "famille",    "non payé", None,       None,          0),
        (5,  "Meziane",     "Samir",          "famille",    "payé",     "espèce",   "2024-03-10", 0),
        (6,  "Aït Yahia",   "Nadia",          "famille",    "non payé", None,       None,          0),
        (7,  "Belkacem",    "Omar",           "famille",    "payé",     "virement", "2024-02-20", 0),
        (8,  "Hamidou",     "Lyes",           "famille",    "non payé", None,       None,          0),
        (9,  "Ziani",       "Kheira",         "famille",    "payé",     "chèque",   "2024-01-05", 0),
        (10, "Tizi",        "Rachid",         "famille",    "non payé", None,       None,          0),
        (11, "Idir",        "Massinissa",     "famille",    "payé",     "espèce",   "2024-03-22", 0),
        (12, "Boudiaf",     "Amina",          "celibataire","payé",     "espèce",   "2024-02-14", 0),
        (13, "Ferhat",      "Djamel",         "celibataire","non payé", None,       None,          0),
        (14, "Cherif",      "Lynda",          "celibataire","payé",     "virement", "2024-01-30", 0),
        (15, "Agouni",      "Reda",           "celibataire","non payé", None,       None,          0),
    ]

    for m in membres:
        numero, nom, prenom, type_, statut, mode, date_p, doyen = m
        montant = 60 if type_ == "famille" else 30
        conn.execute(
            """INSERT INTO membres
               (numero_famille, nom, prenom, type, montant_du, statut,
                mode_paiement, date_paiement, est_doyen)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (numero, nom, prenom, type_, montant, statut, mode, date_p, doyen),
        )
    conn.commit()
