from sqlalchemy.orm import declarative_base
from sqlalchemy import Column , String ,Integer,Float,DateTime

Base = declarative_base()

class Order(Base):
    __tablename__ = "orders"

    id = Column(Integer,primary_key = True,index=True)
    customer_name = Column(String)
    item = Column(String)
    quantity = Column(Float)
    date = Column(DateTime)
    status = Column(String)