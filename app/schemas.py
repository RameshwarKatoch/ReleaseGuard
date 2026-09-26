from pydantic import BaseModel

class OrderCreate(BaseModel):
    customer_name : str
    item : str
    quantity: float

class OrderUpdate(BaseModel):
    customer_name : str
    item : str
    quantity: float

class ReleaseCreate(BaseModel):
    version: str
    environment: str
    deployment_status: str
    health_status: str
    commit_sha: str
