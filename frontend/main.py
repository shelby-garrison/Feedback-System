from fastapi import FastAPI, Request, Form
from fastapi.responses import RedirectResponse, HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import httpx
import os

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

async def get_user_from_token(token: str):
    if not token:
        return None
    headers = {"Authorization": f"Bearer {token}"}
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(f"{BACKEND_URL}/api/me", headers=headers)
            resp.raise_for_status()
            return resp.json()
        except (httpx.RequestError, httpx.HTTPStatusError):
            return None

@app.get("/")
async def root():
    return RedirectResponse(url="/dashboard")

@app.get("/login", response_class=HTMLResponse)
async def login_get(request: Request):
    return templates.TemplateResponse("login.html", {"request": request, "error": None})

@app.post("/login", response_class=HTMLResponse)
async def login_post(request: Request, username: str = Form(...), password: str = Form(...)):
    async with httpx.AsyncClient() as client:
        resp = await client.post(f"{BACKEND_URL}/api/token", data={"username": username, "password": password})
        if resp.status_code == 200:
            token = resp.json()["access_token"]
            response = RedirectResponse("/dashboard", status_code=302)
            response.set_cookie("access_token", token, httponly=True)
            return response
        else:
            return templates.TemplateResponse("login.html", {"request": request, "error": "Invalid credentials"})

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    token = request.cookies.get("access_token")
    if not token:
        return RedirectResponse("/login")

    user = await get_user_from_token(token)
    if not user:
        # Clear cookie and redirect if token is invalid
        response = RedirectResponse("/login")
        response.delete_cookie("access_token")
        return response

    message = request.query_params.get("message")
    error = request.query_params.get("error")

    headers = {"Authorization": f"Bearer {token}"}
    async with httpx.AsyncClient() as client:
        try: #fetching feedbacks
            resp = await client.get(f"{BACKEND_URL}/api/feedbacks", headers=headers)
            resp.raise_for_status()
            feedbacks = resp.json()
        except (httpx.RequestError, httpx.HTTPStatusError):
            feedbacks = []
        # Fetch unread notification count
        try:
            unread_resp = await client.get(f"{BACKEND_URL}/api/notifications/unread_count", headers=headers)
            unread_resp.raise_for_status()
            unread_count = unread_resp.json().get("unread_count", 0)
        except Exception:
            unread_count = 0

    context = {
        "request": request,
        "user": user,
        "feedbacks": feedbacks,
        "message": message,
        "error": error,
        "unread_count": unread_count
    }

    if user["role"] == "manager":
        async with httpx.AsyncClient() as client:
            try:
                resp = await client.get(f"{BACKEND_URL}/api/manager/team", headers=headers)
                resp.raise_for_status()
                team = resp.json()
            except (httpx.RequestError, httpx.HTTPStatusError):
                team = []
        context["team"] = team
        return templates.TemplateResponse("dashboard_manager.html", context)
    else:  # Employee
        return templates.TemplateResponse("dashboard_employee.html", context)

@app.get("/peer-review", response_class=HTMLResponse)
async def peer_review_form(request: Request):
    token = request.cookies.get("access_token")
    if not token:
        return RedirectResponse("/login")
    
    user = await get_user_from_token(token)
    if not user:
        return RedirectResponse("/login")

    message = request.query_params.get("message")
    error = request.query_params.get("error")
    
    headers = {"Authorization": f"Bearer {token}"}
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(f"{BACKEND_URL}/api/employee/peers", headers=headers)
            resp.raise_for_status()
            peers = resp.json()
        except (httpx.RequestError, httpx.HTTPStatusError) as e:
            peers = []
            error = f"Could not load peers: {e}"

    return templates.TemplateResponse(
        "peer_review.html", 
        {"request": request, "user": user, "peers": peers, "message": message, "error": error}
    )

@app.post("/peer-review")
async def handle_peer_review_submission(request: Request):
    token = request.cookies.get("access_token")
    if not token:
        return RedirectResponse("/login")
    
    redirect_url = "/peer-review?message=Peer review submitted successfully!"
    try:
        form_data = await request.form()
        review = {
            "reviewee_id": form_data.get("reviewee_id"),
            "strengths": form_data.get("strengths"),
            "areas_to_improve": form_data.get("areas_to_improve"),
            "sentiment": form_data.get("sentiment")
        }

        if not all(review.values()):
            return RedirectResponse("/peer-review?error=All fields are required.", status_code=302)

        headers = {"Authorization": f"Bearer {token}"}
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{BACKEND_URL}/api/employee/peer_review",
                json=review,
                headers=headers
            )
            resp.raise_for_status()

    except httpx.HTTPStatusError as e:
        error_message = e.response.json().get("detail", "An unknown error occurred.")
        redirect_url = f"/peer-review?error={error_message}"
    except httpx.RequestError as e:
        redirect_url = f"/peer-review?error=Could not connect to the backend: {e}"
    
    return RedirectResponse(redirect_url, status_code=302)

@app.get("/my-peer-reviews", response_class=HTMLResponse)
async def my_peer_reviews_page(request: Request):
    token = request.cookies.get("access_token")
    if not token:
        return RedirectResponse("/login")

    user = await get_user_from_token(token)
    if not user:
        return RedirectResponse("/login")
    
    headers = {"Authorization": f"Bearer {token}"}
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(f"{BACKEND_URL}/api/employee/peer_reviews", headers=headers)
            resp.raise_for_status()
            reviews = resp.json()
        except (httpx.RequestError, httpx.HTTPStatusError):
            reviews = []

    return templates.TemplateResponse(
        "my_peer_reviews.html",
        {"request": request, "user": user, "reviews": reviews}
    )

@app.post("/request-feedback")
async def handle_request_feedback(request: Request):
    token = request.cookies.get("access_token")
    if not token:
        return RedirectResponse("/login")

    headers = {"Authorization": f"Bearer {token}"}
    redirect_url = "/dashboard?message=Feedback request sent successfully!"
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{BACKEND_URL}/api/employee/request_feedback",
                headers=headers
            )
            resp.raise_for_status()
    except httpx.HTTPStatusError as e:
        error_message = "An unknown error occurred."
        try:
            error_detail = e.response.json().get("detail", "Server error")
            error_message = error_detail
        except Exception:
            error_message = f"Failed to send request: Server returned status {e.response.status_code}"
        redirect_url = f"/dashboard?error={error_message}"
    except httpx.RequestError as e:
        redirect_url = f"/dashboard?error=Could not connect to the backend: {e}"

    return RedirectResponse(redirect_url, status_code=302)

@app.get("/feedback/new/{employee_id}", response_class=HTMLResponse)
async def feedback_form(request: Request, employee_id: str):
    token = request.cookies.get("access_token")
    if not token:
        return RedirectResponse("/login")
    return templates.TemplateResponse("feedback_form.html", {"request": request, "employee_id": employee_id})

@app.post("/feedback/new/{employee_id}", response_class=HTMLResponse)
async def feedback_submit(request: Request, employee_id: str, strengths: str = Form(...), areas_to_improve: str = Form(...), sentiment: str = Form(...), tags: str = Form("")):
    token = request.cookies.get("access_token")
    if not token:
        return RedirectResponse("/login")
    tags_list = [t.strip() for t in tags.split(",") if t.strip()]
    async with httpx.AsyncClient() as client:
        await client.post(
            f"{BACKEND_URL}/api/feedback",
            json={
                "employee_id": employee_id,
                "strengths": strengths,
                "areas_to_improve": areas_to_improve,
                "sentiment": sentiment,
                "tags": tags_list
            },
            headers={"Authorization": f"Bearer {token}"}
        )
    return RedirectResponse("/dashboard", status_code=302)

@app.get("/feedback/history", response_class=HTMLResponse)
async def feedback_history(request: Request):
    token = request.cookies.get("access_token")
    if not token:
        return RedirectResponse("/login")
    
    headers = {"Authorization": f"Bearer {token}"}
    async with httpx.AsyncClient() as client:
        user_resp = await client.get(f"{BACKEND_URL}/api/me", headers=headers)
        feedbacks_resp = await client.get(f"{BACKEND_URL}/api/feedbacks", headers=headers)
        
    user = user_resp.json()
    feedbacks = feedbacks_resp.json()
    
    return templates.TemplateResponse("feedback_history.html", {"request": request, "feedbacks": feedbacks, "user": user})

@app.get("/notifications", response_class=HTMLResponse)
async def notifications_page(request: Request):
    token = request.cookies.get("access_token")
    if not token:
        return RedirectResponse("/login")
    headers = {"Authorization": f"Bearer {token}"}
    async with httpx.AsyncClient() as client:
        user_resp = await client.get(f"{BACKEND_URL}/api/me", headers=headers)
        notes_resp = await client.get(f"{BACKEND_URL}/api/notifications", headers=headers)
    user = user_resp.json()
    notes = notes_resp.json()
    return templates.TemplateResponse("notifications.html", {"request": request, "notifications": notes, "user": user})

@app.get("/feedback/export")
async def export_all_feedback(request: Request):
    token = request.cookies.get("access_token")
    if not token:
        return RedirectResponse(url="/login")
    headers = {"Authorization": f"Bearer {token}"}
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{BACKEND_URL}/api/feedbacks/export", headers=headers)
        if response.status_code == 200:
            return Response(content=response.content, media_type="application/pdf")
        return HTMLResponse("Could not export.", status_code=response.status_code)

@app.get("/feedback/{feedback_id}/export")
async def export_one_feedback(request: Request, feedback_id: str):
    token = request.cookies.get("access_token")
    if not token:
        return RedirectResponse(url="/login")
    headers = {"Authorization": f"Bearer {token}"}
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{BACKEND_URL}/api/feedback/{feedback_id}/export", headers=headers)
        if response.status_code == 200:
            return Response(content=response.content, media_type="application/pdf")
        return HTMLResponse("Could not export.", status_code=response.status_code)

@app.post("/feedback/{feedback_id}/comment")
async def post_comment(request: Request, feedback_id: str, comment: str = Form(...)):
    token = request.cookies.get("access_token")
    if not token:
        return RedirectResponse("/login")
    async with httpx.AsyncClient() as client:
        await client.post(
            f"{BACKEND_URL}/api/feedback/{feedback_id}/comment",
            data={"comment": comment},
            headers={"Authorization": f"Bearer {token}"}
        )
    return RedirectResponse("/dashboard", status_code=302)

@app.get("/feedback/edit/{feedback_id}", response_class=HTMLResponse)
async def edit_feedback_form(request: Request, feedback_id: str):
    token = request.cookies.get("access_token")
    if not token:
        return RedirectResponse("/login")
    headers = {"Authorization": f"Bearer {token}"}
    async with httpx.AsyncClient() as client:
        resp = await client.get(f"{BACKEND_URL}/api/feedbacks", headers=headers)
        resp.raise_for_status()
        feedbacks = resp.json()
    feedback = next((fb for fb in feedbacks if fb["id"] == feedback_id), None)
    if not feedback:
        return RedirectResponse("/dashboard?error=Feedback not found")
    return templates.TemplateResponse("edit_feedback.html", {"request": request, "feedback": feedback, "message": None, "error": None})

@app.post("/feedback/edit/{feedback_id}")
async def edit_feedback_submit(request: Request, feedback_id: str):
    token = request.cookies.get("access_token")
    if not token:
        return RedirectResponse("/login")
    form = await request.form()
    strengths = form.get("strengths")
    areas_to_improve = form.get("areas_to_improve")
    sentiment = form.get("sentiment")
    tags = [t.strip() for t in (form.get("tags") or "").split(",") if t.strip()]
    update = {
        "strengths": strengths,
        "areas_to_improve": areas_to_improve,
        "sentiment": sentiment,
        "tags": tags
    }
    headers = {"Authorization": f"Bearer {token}"}
    async with httpx.AsyncClient() as client:
        resp = await client.put(f"{BACKEND_URL}/api/feedback/{feedback_id}", json=update, headers=headers)
        if resp.status_code == 200:
            return RedirectResponse("/dashboard?message=Feedback updated successfully!", status_code=302)
        else:
            error = resp.json().get("detail", "Failed to update feedback.")
            # Re-render form with error
            resp2 = await client.get(f"{BACKEND_URL}/api/feedbacks", headers=headers)
            resp2.raise_for_status()
            feedbacks = resp2.json()
            feedback = next((fb for fb in feedbacks if fb["id"] == feedback_id), None)
            return templates.TemplateResponse("edit_feedback.html", {"request": request, "feedback": feedback, "message": None, "error": error})

@app.post("/notifications/clear_all")
async def clear_all_notifications(request: Request):
    token = request.cookies.get("access_token")
    if not token:
        return RedirectResponse("/login")
    headers = {"Authorization": f"Bearer {token}"}
    async with httpx.AsyncClient() as client:
        await client.post(f"{BACKEND_URL}/api/notifications/clear_all", headers=headers)
    return RedirectResponse("/notifications", status_code=302) 