from app import database
from app import database
from app import database
from app import database
from app import database
from app import release
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
from app.health_check import check_health
from app.deployment import (
    trigger_deployment,
    wait_for_rollback_run,
    wait_for_rollback_completion,
)
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

@app.get("/releases/{release_id}/previous-healthy")
def get_previous_healthy_release(release_id: int,db: Session = Depends(get_db)):
    current_release = db.query(Release).filter(Release.id == release_id).first()

    if not current_release:
        raise HTTPException(
            status_code=404,
            detail="Release not found"
        )

    previous_release = db.query(Release).filter(
        Release.environment == current_release.environment,
        Release.health_status == "HEALTHY",
        Release.id < current_release.id
    ).order_by(Release.id.desc()).first()

    if not previous_release:
        raise HTTPException(
            status_code=404,
            detail="No previous healthy release found"
        )

    return previous_release

@app.get("/releases/{release_id}/rollback-target")
def get_rollback_target(release_id: int,db: Session = Depends(get_db)):
    current_release = db.query(Release).filter(Release.id == release_id).first()

    if not current_release:
        raise HTTPException(
            status_code=404,
            detail="Release not found"
        )

    if current_release.health_status == "HEALTHY":
        return {
            "message": "Rollback not required",
            "release_id": current_release.id
        }

    previous_release = db.query(Release).filter(
        Release.environment == current_release.environment,
        Release.health_status == "HEALTHY",
        Release.id < current_release.id
    ).order_by(Release.id.desc()).first()

    if not previous_release:
        raise HTTPException(
            status_code=404,
            detail="No rollback target found"
        )

    return {
        "message": "Rollback required",
        "rollback_to_release_id": previous_release.id,
        "version": previous_release.version,
        "commit_sha": previous_release.commit_sha
    }

@app.post("/releases/{release_id}/rollback")
def rollback_release(release_id: int,db: Session = Depends(get_db)):
    current_release = db.query(Release).filter(Release.id == release_id).first()

    if not current_release:
        raise HTTPException(
            status_code=404,
            detail="Release not found"
        )

    if current_release.health_status == "HEALTHY":
        return {
            "message": "Rollback not required",
            "release_id": current_release.id
        }

    previous_release = db.query(Release).filter(
        Release.environment == current_release.environment,
        Release.health_status == "HEALTHY",
        Release.id < current_release.id
    ).order_by(Release.id.desc()).first()

    if not previous_release:
        raise HTTPException(
            status_code=404,
            detail="No rollback target found"
        )

    current_release.deployment_status = "ROLLED_BACK"

    db.commit()
    db.refresh(current_release)

    return {
        "message": "Rollback completed",
        "rolled_back_release_id": current_release.id,
        "rollback_target_id": previous_release.id,
        "rollback_version": previous_release.version,
        "rollback_commit_sha": previous_release.commit_sha
    }

@app.get("/check-health")
def check_application_health(url: str):
    is_healthy = check_health(url)

    if is_healthy:
        return {
            "status": "HEALTHY"
        }

    return {
        "status": "UNHEALTHY"
    }

@app.post("/releases/{release_id}/check-health")
def check_release_health(
    release_id: int,
    url: str,
    db: Session = Depends(get_db)
):
    release = db.query(Release).filter(
        Release.id == release_id
    ).first()

    if not release:
        raise HTTPException(
            status_code=404,
            detail="Release not found"
        )

    is_healthy = check_health(url)

    if is_healthy:
        release.health_status = "HEALTHY"
    else:
        release.health_status = "UNHEALTHY"

    db.commit()
    db.refresh(release)

    return {
        "release_id": release.id,
        "health_status": release.health_status
    }

@app.post("/releases/{release_id}/auto-rollback")
def auto_rollback(
    release_id: int,
    url: str,
    db: Session = Depends(get_db)
):
    release = db.query(Release).filter(
        Release.id == release_id
    ).first()

    if not release:
        raise HTTPException(
            status_code=404,
            detail="Release not found"
        )

    is_healthy = check_health(url)

    if is_healthy:
        release.health_status = "HEALTHY"

        db.commit()
        db.refresh(release)

        return {
            "message": "Release is healthy",
            "health_status": "HEALTHY",
            "rollback_required": False
        }

    release.health_status = "UNHEALTHY"

    previous_release = db.query(Release).filter(
        Release.environment == release.environment,
        Release.health_status == "HEALTHY",
        Release.id < release.id
    ).order_by(Release.id.desc()).first()

    if not previous_release:
        db.commit()
        raise HTTPException(
            status_code=404,
            detail="No rollback target found"
        )

    # Rollback has been requested
    release.rollback_status = "ROLLBACK_REQUESTED"
    db.commit()

    deployment_started = trigger_deployment(
        previous_release.commit_sha
    )

    if not deployment_started:
        release.rollback_status = "ROLLBACK_FAILED"
        db.commit()

        raise HTTPException(
            status_code=500,
            detail="Rollback deployment failed to start"
        )

    # GitHub accepted the rollback request
    release.rollback_status = "ROLLBACK_IN_PROGRESS"
    db.commit()

    run_id = wait_for_rollback_run()

    if run_id is None:
        release.rollback_status = "ROLLBACK_FAILED"
        db.commit()

        raise HTTPException(
            status_code=500,
            detail="Rollback workflow run not found"
        )

    rollback_success = wait_for_rollback_completion(run_id)

    if not rollback_success:
        release.rollback_status = "ROLLBACK_FAILED"
        db.commit()

        raise HTTPException(
            status_code=500,
            detail="Rollback workflow failed"
        )

    # Verify application health after rollback
    is_healthy_after_rollback = check_health(url)

    if not is_healthy_after_rollback:
        release.rollback_status = "ROLLBACK_FAILED"
        db.commit()

        raise HTTPException(
            status_code=500,
            detail="Rollback completed but application is still unhealthy"
        )

    release.rollback_status = "ROLLED_BACK"
    release.health_status = "HEALTHY"

    db.commit()
    db.refresh(release)

    return {
        "message": "Automatic rollback completed",
        "health_status": "HEALTHY",
        "rollback_required": True,
        "rollback_target_id": previous_release.id,
        "rollback_version": previous_release.version,
        "rollback_commit_sha": previous_release.commit_sha
    }