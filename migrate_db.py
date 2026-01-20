
from sqlalchemy import create_engine, text
from katrain.web.core.config import settings

def migrate():
    # Connection string from settings
    db_url = settings.DATABASE_URL
    if not db_url:
        print("DATABASE_URL not set in settings")
        return

    print(f"Connecting to {db_url}...")
    engine = create_engine(db_url)
    
    with engine.connect() as conn:
        print("Checking for missing columns in 'users' table...")
        
        # Add net_wins to users
        try:
            conn.execute(text("ALTER TABLE users ADD COLUMN net_wins INTEGER DEFAULT 0"))
            print("Added 'net_wins' to 'users'")
        except Exception as e:
            if "already exists" in str(e):
                print("'net_wins' already exists")
            else:
                print(f"Error adding 'net_wins': {e}")

        # Add elo_points to users
        try:
            conn.execute(text("ALTER TABLE users ADD COLUMN elo_points INTEGER DEFAULT 0"))
            print("Added 'elo_points' to 'users'")
        except Exception as e:
            if "already exists" in str(e):
                print("'elo_points' already exists")
            else:
                print(f"Error adding 'elo_points': {e}")

        # Add elo_change to rating_history
        print("Checking for missing columns in 'rating_history' table...")
        try:
            conn.execute(text("ALTER TABLE rating_history ADD COLUMN elo_change INTEGER DEFAULT 0"))
            print("Added 'elo_change' to 'rating_history'")
        except Exception as e:
            if "already exists" in str(e):
                print("'elo_change' already exists")
            elif "does not exist" in str(e):
                print("'rating_history' table doesn't exist yet, SQLAlchemy will create it normally.")
            else:
                print(f"Error adding 'elo_change': {e}")

        conn.commit()
    print("Migration complete.")

if __name__ == "__main__":
    migrate()
