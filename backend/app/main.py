from fastapi import FastAPI, Depends, HTTPException, status, Request, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.responses import FileResponse
from . import database, models, schemas, auth, crud, dependencies, notifications
from datetime import timedelta, datetime
from bson import ObjectId
import os
import tempfile
from fpdf import FPDF
from typing import List
import markdown2

app = FastAPI()

# CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # For dev only
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def startup():
    await database.ensure_indexes()

# --- Auth ---
@app.post("/api/token", response_model=schemas.Token)
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    user = await auth.authenticate_user(form_data.username, form_data.password)
    if not user:
        raise HTTPException(status_code=400, detail="Incorrect username or password")
    access_token = auth.create_access_token(
        data={"sub": user.username}
    )
    return {"access_token": access_token, "token_type": "bearer"}

# --- User Registration (for setup only) ---
@app.post("/api/register", response_model=schemas.UserOut)
async def register(user: models.UserCreate):
    existing = await auth.get_user(user.username)
    if existing:
        raise HTTPException(status_code=400, detail="Username already registered")
    hashed_pw = auth.get_password_hash(user.password)
    user_id = await crud.create_user(user, hashed_pw)
    return schemas.UserOut(id=user_id, username=user.username, full_name=user.full_name, role=user.role)

# --- Get Current User ---
@app.get("/api/me", response_model=schemas.UserOut)
async def get_me(current_user=Depends(auth.get_current_active_user)):
    return schemas.UserOut(
        id=current_user.id,
        username=current_user.username,
        full_name=current_user.full_name,
        role=current_user.role
    )

def convert_objectid(obj):
    if isinstance(obj, list):
        return [convert_objectid(item) for item in obj]
    elif isinstance(obj, dict):
        return {k: convert_objectid(v) for k, v in obj.items()}
    elif isinstance(obj, ObjectId):
        return str(obj)
    else:
        return obj

# --- Manager: Get Team Members ---
@app.get("/api/manager/team")
async def get_team(current_user=Depends(dependencies.get_manager_user)):
    team_ids = current_user.team or []
    team = []
    for eid in team_ids:
        emp = await crud.get_user_by_id(eid)
        if emp:
            team.append({
                "id": str(emp["id"]),
                "username": emp["username"],
                "full_name": emp["full_name"]
            })
    return convert_objectid(team)

# --- Manager: Add Employee to Team ---
@app.post("/api/manager/add_employee")
async def add_employee_to_team(employee_id: str, current_user=Depends(dependencies.get_manager_user)):
    await crud.add_employee_to_manager(current_user.id, employee_id)
    return {"status": "ok"}

# --- Manager: Submit Feedback ---
@app.post("/api/feedback", response_model=str)
async def submit_feedback(feedback: models.FeedbackCreate, current_user=Depends(dependencies.get_manager_user)):
    fb_id = await crud.create_feedback(current_user.id, feedback)
    await notifications.notify_feedback(feedback.employee_id, "You have new feedback.")
    return fb_id

# --- Manager: Edit Feedback ---
@app.put("/api/feedback/{feedback_id}")
async def edit_feedback(feedback_id: str, update: models.FeedbackUpdate, current_user=Depends(dependencies.get_manager_user)):
    fb = await crud.get_feedback_by_id(feedback_id)
    if not fb or fb["manager_id"] != current_user.id:
        raise HTTPException(status_code=404, detail="Feedback not found")
    # Always clear employee_comment and reset acknowledged
    update.employee_comment = None
    update.acknowledged = False
    await crud.update_feedback(feedback_id, update)
    # Notify the employee
    await notifications.notify_feedback(fb["employee_id"], "A feedback from your manager was updated. Please review and acknowledge.")
    return {"status": "updated"}

# --- Employee: Acknowledge Feedback ---
# @app.post("/api/feedback/{feedback_id}/ack")
# async def acknowledge_feedback(feedback_id: str, current_user=Depends(dependencies.get_employee_user)):
#     fb = await crud.get_feedback_by_id(feedback_id)
#     if not fb or fb["employee_id"] != current_user.id:
#         raise HTTPException(status_code=404, detail="Feedback not found")
#     await crud.update_feedback(feedback_id, models.FeedbackUpdate(acknowledged=True))
#     return {"status": "acknowledged"}

# --- Employee: Comment on Feedback ---
@app.post("/api/feedback/{feedback_id}/comment")
async def comment_feedback(
    feedback_id: str,
    comment: str = Form(...),
    current_user=Depends(dependencies.get_employee_user)
):
    fb = await crud.get_feedback_by_id(feedback_id)
    if not fb or fb["employee_id"] != current_user.id:
        raise HTTPException(status_code=404, detail="Feedback not found")
    await crud.update_feedback(feedback_id, models.FeedbackUpdate(employee_comment=comment, acknowledged=True))
    return {"status": "commented"}

# --- Employee: Request Feedback ---
@app.post("/api/employee/request_feedback")
async def request_feedback(current_user: models.User = Depends(dependencies.get_employee_user)):
    manager = await crud.get_manager_for_employee(current_user.id)
    if not manager:
        raise HTTPException(status_code=400, detail="Could not find an assigned manager for your account. Please contact an admin.")
    
    await notifications.notify_feedback(
        manager["id"], 
        f"Feedback request from {current_user.full_name}."
    )
    return {"status": "requested"}

# --- Employee: Get Peers ---
@app.get("/api/employee/peers", response_model=List[schemas.UserOut])
async def get_peers(current_user: models.User = Depends(dependencies.get_employee_user)):
    peers_data = await crud.get_peers_for_employee(current_user.id)
    return [schemas.UserOut(**p) for p in peers_data]

# --- Employee: Submit Peer Review ---
@app.post("/api/employee/peer_review")
async def submit_peer_review(review: models.PeerReviewCreate, current_user: models.User = Depends(dependencies.get_employee_user)):
    # Ensure the person being reviewed is a valid peer
    peers = await crud.get_peers_for_employee(current_user.id)
    if review.reviewee_id not in [p["id"] for p in peers]:
        raise HTTPException(status_code=403, detail="You can only review members of your own team.")
    
    review_id = await crud.create_peer_review(current_user.id, review)
    
    # Notify the recipient
    await notifications.notify_feedback(review.reviewee_id, "You have received a new anonymous peer review.")
    
    return {"status": "created", "review_id": review_id}

# --- Employee: Get Received Peer Reviews ---
@app.get("/api/employee/peer_reviews", response_model=List[schemas.PeerReviewOut])
async def get_my_peer_reviews(current_user: models.User = Depends(dependencies.get_employee_user)):
    reviews = await crud.get_peer_reviews_for_employee(current_user.id)
    for r in reviews:
        r["created_at"] = r["created_at"].isoformat()
    return reviews

# --- Get Feedbacks (Employee or Manager) ---
@app.get("/api/feedbacks")
async def get_feedbacks(current_user=Depends(auth.get_current_active_user)):
    if current_user.role == "manager":
        feedbacks = await crud.get_feedbacks_for_manager(current_user.id)
    else:
        feedbacks = await crud.get_feedbacks_for_employee(current_user.id)
    for fb in feedbacks:
        fb["id"] = str(fb["_id"])
        if "employee_id" in fb:
            fb["employee_id"] = str(fb["employee_id"])
        if "manager_id" in fb:
            fb["manager_id"] = str(fb["manager_id"])
        if "created_at" in fb:
            fb["created_at"] = fb["created_at"].isoformat()
        if "updated_at" in fb:
            fb["updated_at"] = fb["updated_at"].isoformat()
        if fb.get("employee_comment"):
            fb["employee_comment"] = markdown2.markdown(fb["employee_comment"])
    return convert_objectid(feedbacks)

# --- Get Notifications ---
@app.get("/api/notifications")
async def get_notifications(current_user=Depends(auth.get_current_active_user)):
    notes = await crud.get_notifications(current_user.id)
    # Mark all unread notifications as read
    unread_ids = [n["id"] for n in notes if not n.get("read")]
    for nid in unread_ids:
        await crud.mark_notification_read(nid)
    for n in notes:
        n["id"] = str(n["_id"])
        if "created_at" in n:
            n["created_at"] = n["created_at"].isoformat()
    return convert_objectid(notes)

# --- Mark Notification as Read ---
@app.post("/api/notifications/{notification_id}/read")
async def mark_notification(notification_id: str, current_user=Depends(auth.get_current_active_user)):
    await crud.mark_notification_read(notification_id)
    return {"status": "read"}

@app.post("/api/notifications/clear_all")
async def clear_all_notifications(current_user=Depends(auth.get_current_active_user)):
    await crud.clear_all_notifications(current_user.id)
    return {"status": "cleared"}

@app.get("/api/notifications/unread_count")
async def unread_notification_count(current_user=Depends(auth.get_current_active_user)):
    count = await crud.count_unread_notifications(current_user.id)
    return {"unread_count": count}

def create_feedback_pdf(feedbacks, filename="feedbacks.pdf"):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", "B", 16)
    pdf.cell(200, 10, txt="Feedback Report", ln=True, align="C")
    pdf.set_font("Arial", size=12)

    for fb in feedbacks:
        pdf.set_font("Arial", "B", 12)
        pdf.cell(200, 10, txt=f"Feedback from {fb.get('manager_name', 'N/A')} to {fb.get('employee_name', 'N/A')}", ln=True)
        pdf.set_font("Arial", size=11)
        pdf.cell(200, 8, txt=f"Date: {fb['created_at'].isoformat() if isinstance(fb['created_at'], datetime) else fb['created_at']}", ln=True)
        pdf.cell(200, 8, txt=f"Strengths: {fb.get('strengths', '')}", ln=True)
        pdf.cell(200, 8, txt=f"Areas to Improve: {fb.get('areas_to_improve', '')}", ln=True)
        pdf.cell(200, 8, txt=f"Sentiment: {fb.get('sentiment', '')}", ln=True)
        if fb.get('employee_comment'):
            pdf.cell(200, 8, txt=f"Employee Comment: {fb.get('employee_comment')}", ln=True)
        pdf.ln(5) # Add a small space

    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        pdf.output(tmp.name)
        return FileResponse(tmp.name, filename=filename, media_type="application/pdf")

@app.get("/api/feedbacks/export")
async def export_feedbacks_history(current_user: models.User = Depends(auth.get_current_active_user)):
    if current_user.role == "manager":
        feedbacks = await crud.get_feedbacks_for_manager(current_user.id)
    else:
        feedbacks = await crud.get_feedbacks_for_employee(current_user.id)
    return create_feedback_pdf(feedbacks, filename="feedback_history.pdf")

@app.get("/api/feedback/{feedback_id}/export")
async def export_single_feedback(feedback_id: str, current_user: models.User = Depends(auth.get_current_active_user)):
    fb = await crud.get_feedback_by_id(feedback_id)

    # Security check
    if not fb or (current_user.role == 'employee' and fb['employee_id'] != current_user.id) or \
       (current_user.role == 'manager' and fb['manager_id'] != current_user.id):
        raise HTTPException(status_code=404, detail="Feedback not found or access denied")

    return create_feedback_pdf([fb], filename=f"feedback_{feedback_id}.pdf") 