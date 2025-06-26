from .database import db
from .models import UserCreate, FeedbackCreate, FeedbackUpdate, PeerReviewCreate
from datetime import datetime
from bson import ObjectId

async def create_user(user: UserCreate, hashed_password: str):
    doc = user.dict()
    doc["hashed_password"] = hashed_password
    doc["role"] = user.role
    if user.role == "manager":
        doc["team"] = []
    result = await db.users.insert_one(doc)
    return str(result.inserted_id)

async def get_user_by_id(user_id: str):
    user = await db.users.find_one({"_id": ObjectId(user_id)})
    if user:
        user["id"] = str(user["_id"])
        return user
    return None

async def add_employee_to_manager(manager_id: str, employee_id: str):
    await db.users.update_one(
        {"_id": ObjectId(manager_id)},
        {"$addToSet": {"team": employee_id}}
    )

async def get_manager_for_employee(employee_id: str):
    manager = await db.users.find_one({"role": "manager", "team": employee_id})
    if manager:
        manager["id"] = str(manager["_id"])
        return manager
    return None

async def get_peers_for_employee(employee_id: str):
    manager = await get_manager_for_employee(employee_id)
    if not manager or not manager.get("team"):
        return []

    peers = []
    # Exclude the current employee from their own peer list
    peer_ids = [pid for pid in manager["team"] if pid != employee_id]
    
    for peer_id in peer_ids:
        peer = await get_user_by_id(peer_id)
        if peer:
            peers.append(peer)
            
    return peers

async def create_feedback(manager_id: str, feedback: FeedbackCreate):
    now = datetime.utcnow()
    doc = feedback.dict()
    doc["manager_id"] = manager_id
    doc["created_at"] = now
    doc["updated_at"] = now
    doc["acknowledged"] = False
    doc["employee_comment"] = None
    result = await db.feedbacks.insert_one(doc)
    return str(result.inserted_id)

async def get_feedbacks_for_employee(employee_id: str):
    feedbacks = []
    employee = await get_user_by_id(employee_id)
    async for fb in db.feedbacks.find({"employee_id": employee_id}).sort("created_at", -1):
        fb["id"] = str(fb["_id"])
        if employee:
            fb["employee_name"] = employee["full_name"]
        manager = await get_user_by_id(fb["manager_id"])
        if manager:
            fb["manager_name"] = manager["full_name"]
        else:
            fb["manager_name"] = "Unknown"
        feedbacks.append(fb)
    return feedbacks

async def get_feedbacks_for_manager(manager_id: str):
    feedbacks = []
    manager = await get_user_by_id(manager_id)
    async for fb in db.feedbacks.find({"manager_id": manager_id}).sort("created_at", -1):
        fb["id"] = str(fb["_id"])
        if manager:
            fb["manager_name"] = manager["full_name"]
        employee = await get_user_by_id(fb["employee_id"])
        if employee:
            fb["employee_name"] = employee["full_name"]
        else:
            fb["employee_name"] = "Unknown"
        feedbacks.append(fb)
    return feedbacks

async def update_feedback(feedback_id: str, update: FeedbackUpdate):
    update_dict = {}
    for k, v in update.dict(exclude_unset=True).items():
        if k in ["employee_comment", "acknowledged"]:
            update_dict[k] = v  # allow explicit None
        elif v is not None:
            update_dict[k] = v
    if update_dict:
        update_dict["updated_at"] = datetime.utcnow()
        await db.feedbacks.update_one(
            {"_id": ObjectId(feedback_id)},
            {"$set": update_dict}
        )

async def get_feedback_by_id(feedback_id: str):
    fb = await db.feedbacks.find_one({"_id": ObjectId(feedback_id)})
    if fb:
        fb["id"] = str(fb["_id"])
        employee = await get_user_by_id(fb["employee_id"])
        if employee:
            fb["employee_name"] = employee["full_name"]
        manager = await get_user_by_id(fb["manager_id"])
        if manager:
            fb["manager_name"] = manager["full_name"]
        return fb
    return None

async def create_notification(user_id: str, message: str):
    now = datetime.utcnow()
    doc = {
        "user_id": user_id,
        "message": message,
        "read": False,
        "created_at": now
    }
    await db.notifications.insert_one(doc)

async def get_notifications(user_id: str):
    notes = []
    async for n in db.notifications.find({"user_id": user_id}).sort("created_at", -1):
        n["id"] = str(n["_id"])
        notes.append(n)
    return notes

async def mark_notification_read(notification_id: str):
    await db.notifications.update_one(
        {"_id": ObjectId(notification_id)},
        {"$set": {"read": True}}
    )

async def create_peer_review(reviewer_id: str, review: PeerReviewCreate):
    now = datetime.utcnow()
    doc = review.dict()
    doc["reviewer_id"] = reviewer_id # Stored for integrity, but not exposed in the API
    doc["created_at"] = now
    result = await db.peer_reviews.insert_one(doc)
    return str(result.inserted_id)

async def get_peer_reviews_for_employee(employee_id: str):
    reviews = []
    # Sort by most recent first
    async for r in db.peer_reviews.find({"reviewee_id": employee_id}).sort("created_at", -1):
        r["id"] = str(r["_id"])
        reviews.append(r)
    return reviews

async def clear_all_notifications(user_id: str):
    await db.notifications.delete_many({"user_id": user_id})

async def count_unread_notifications(user_id: str):
    return await db.notifications.count_documents({"user_id": user_id, "read": False}) 