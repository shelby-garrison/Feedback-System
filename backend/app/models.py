from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

class User(BaseModel):
    id: str
    username: str
    full_name: str
    role: str  # "manager" or "employee"
    team: Optional[List[str]] = None  # For managers: list of employee ids

class UserInDB(User):
    hashed_password: str

class UserCreate(BaseModel):
    username: str
    full_name: str
    password: str
    role: str

class Feedback(BaseModel):
    id: str
    employee_id: str
    manager_id: str
    strengths: str
    areas_to_improve: str
    sentiment: str  # "positive", "neutral", "negative"
    tags: Optional[List[str]] = []
    created_at: datetime
    updated_at: datetime
    acknowledged: bool = False
    employee_comment: Optional[str] = None

class FeedbackCreate(BaseModel):
    employee_id: str
    strengths: str
    areas_to_improve: str
    sentiment: str
    tags: Optional[List[str]] = []

class FeedbackUpdate(BaseModel):
    strengths: Optional[str] = None
    areas_to_improve: Optional[str] = None
    sentiment: Optional[str] = None
    tags: Optional[List[str]] = None
    acknowledged: Optional[bool] = None
    employee_comment: Optional[str] = None

class Notification(BaseModel):
    id: str
    user_id: str
    message: str
    read: bool = False
    created_at: datetime

class PeerReviewCreate(BaseModel):
    reviewee_id: str  # The employee receiving the feedback
    strengths: str
    areas_to_improve: str
    sentiment: str 