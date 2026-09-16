from sqlalchemy import engine,create_engine
from sqlalchemy.orm import sessionmaker

DATABASE_URL = "postgresql://rameshwarkatoch@localhost:5432/orderflow"

engine = create_engine(DATABASE_URL)

SessionLocal = sessionmaker(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


