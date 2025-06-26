from pydantic import BaseModel
from typing import List, Optional

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: Optional[str] = None

class UserOut(BaseModel):
    id: str
    username: str
    full_name: str
    role: str

class FeedbackOut(BaseModel):
    id: str
    employee_id: str
    manager_id: str
    strengths: str
    areas_to_improve: str
    sentiment: str
    tags: List[str]
    created_at: str
    updated_at: str
    acknowledged: bool
    employee_comment: Optional[str]

class PeerReviewOut(BaseModel):
    id: str
    reviewee_id: str
    strengths: str
    areas_to_improve: str
    sentiment: str
    created_at: str 