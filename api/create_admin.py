"""
create_admin.py — Crée le premier compte administrateur

Usage :
    cd api
    pip install -r requirements.txt
    python create_admin.py
    python create_admin.py --email admin@kreyol.mq --name "Admin Kreyol" --password MonMotDePasse!

Le script est idempotent : si l'email existe déjà, il affiche un message et s'arrête.
"""
import argparse
import os
import sys
from pathlib import Path

# Charge le .env situé à la racine du projet
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")

# Import après chargement des variables d'env
import psycopg2


def get_conn() -> psycopg2.extensions.connection:
    return psycopg2.connect(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=int(os.getenv("POSTGRES_PORT", "5433")),
        dbname=os.getenv("POSTGRES_DB", "langmatinitje"),
        user=os.getenv("POSTGRES_USER", "creole"),
        password=os.getenv("POSTGRES_PASSWORD", ""),
    )


def hash_password(password: str) -> str:
    import bcrypt
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def create_admin(email: str, name: str, password: str) -> None:
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            # Vérifier si l'email existe déjà
            cur.execute("SELECT id, role FROM users WHERE email = %s", (email,))
            existing = cur.fetchone()
            if existing:
                user_id, role = existing
                if role == "admin":
                    print(f"✓ Compte admin '{email}' existe déjà (id={user_id}).")
                else:
                    # Promouvoir en admin
                    cur.execute("UPDATE users SET role = 'admin' WHERE id = %s", (user_id,))
                    conn.commit()
                    print(f"✓ Compte '{email}' promu au rôle admin (id={user_id}).")
                return

            # Créer l'utilisateur admin
            cur.execute(
                """
                INSERT INTO users (email, hashed_password, name, role)
                VALUES (%s, %s, %s, 'admin')
                RETURNING id
                """,
                (email, hash_password(password), name),
            )
            user_id = cur.fetchone()[0]

            # Créer le profil contributeur associé
            cur.execute(
                "INSERT INTO contributeurs (user_id, pseudo) VALUES (%s, %s)",
                (user_id, name),
            )

        conn.commit()
        print(f"✓ Admin créé : email={email} | id={user_id}")
        print(f"  → Connectez-vous sur l'interface web ou via POST /api/v1/auth/login")

    except Exception as e:
        conn.rollback()
        print(f"✗ Erreur : {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Crée le premier compte admin Lang Matinitjé")
    parser.add_argument("--email",    default="admin@kreyol.mq",  help="Email de l'admin")
    parser.add_argument("--name",     default="Admin",             help="Nom affiché")
    parser.add_argument("--password", default=None,                help="Mot de passe (demandé si absent)")
    args = parser.parse_args()

    if not args.password:
        import getpass
        args.password = getpass.getpass(f"Mot de passe pour {args.email} : ")

    if len(args.password) < 8:
        print("✗ Le mot de passe doit faire au moins 8 caractères.", file=sys.stderr)
        sys.exit(1)

    create_admin(args.email, args.name, args.password)


if __name__ == "__main__":
    main()
