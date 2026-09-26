from sqlalchemy import delete
from datetime import datetime
from app.database import get_db
from app.schemas import OrderCreate ,OrderUpdate,ReleaseCreate
from fastapi import FastAPI, Depends,HTTPException
from app.database import engine
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Order
from app.release import Release


app = FastAPI()

@app.get("/")
def root():
    return {
        "message":"This is the Release Guard"
    }

@app.get("/health")
def health():
    return{
        "status":"Active"
    }

@app.get("/version")
def version():
    return{
        "version":"0.0.1"
    }

@app.post("/order")
def create_order(order: OrderCreate,db:Session=Depends(get_db)):
    new_order = Order(
        customer_name = order.customer_name,
        quantity = order.quantity,
        item = order.item,
        date = datetime.now(),
        status = "PENDING"
    )
    db.add(new_order)
    db.commit()
    db.refresh(new_order)

    return new_order

@app.get("/orders")
def get_order(db:Session = Depends(get_db)):
    orders = db.query(Order).all()
    return orders

@app.get("/orders/{order_id}")
def get_order(order_id: int, db: Session = Depends(get_db)):
    order = db.query(Order).filter(Order.id == order_id).first()

    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    return order

@app.put("/order/{order_id}")
def update(order_id: int ,order_data: OrderUpdate, db:Session=Depends(get_db)):
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail = "Order not found")

    order.customer_name = order_data.customer_name
    order.item = order_data.item
    order.quantity = order_data.quantity
    db.commit()
    db.refresh(order)
    return order

@app.delete("/order/{order_id}")
def order_delete(order_id:int,db:Session=Depends(get_db)):
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    db.delete(order)
    db.commit()
    
    return {"message": "Order deleted successfully"}

@app.post("/release")
def create_release(release:ReleaseCreate,db:Session=Depends(get_db)):
    new_release = Release(
        version = release.version,
        environment = release.environment,
        deployment_status = release.deployment_status,
        health_status = release.health_status,
        commit_sha = release.commit_sha
    )
    db.add(new_release)
    db.commit()
    db.refresh(new_release)
    return new_release

@app.get("/releases")
def get_releases(db: Session = Depends(get_db)):
    releases = db.query(Release).all()
    return releases

@app.get("/releases/{release_id}")
def get_release(release_id: int, db: Session = Depends(get_db)):
    release = db.query(Release).filter(Release.id == release_id).first()

    if not release:
        raise HTTPException(status_code=404, detail="Release not found")

    return release
