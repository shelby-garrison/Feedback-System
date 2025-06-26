# Feedback System

A modern web application for structured, role-based employee feedback, supporting managers and employees with dashboards, notifications, and peer review.

---

## ✨ Features

- **Role-Based Authentication**: Secure login for Managers and Employees, with access control.
- **Team Management**: Managers can view and manage only their assigned team members.
- **Structured Feedback**: Managers submit detailed feedback (strengths, areas to improve, sentiment, tags) for employees.
- **Feedback History**: Both managers and employees can view a timeline of all feedback entries.
- **Feedback Editing & Acknowledgement**: Managers can update feedback; employees can acknowledge and comment on feedback.
- **Dashboards**: 
  - Managers: Team overview, feedback statistics, sentiment trends.
  - Employees: Personal feedback timeline.
- **Peer Review**: Employees can submit anonymous peer feedback (optional anonymity).
- **Feedback Requests**: Employees can proactively request feedback from their manager.
- **Notifications**: Real-time in-app notifications.
- **Tags & Categorization**: Feedback can be tagged (e.g., "communication", "leadership").
- **PDF Export**: Export feedback records as PDF documents.
- **Markdown Support**: Employee comments on feedback support Markdown formatting.
- **Responsive UI**: Clean, role-based interface for all users.

---

## 🛠️ Tech Stack

### Backend
- **Framework:** FastAPI (Python)
- **Database:** MongoDB (async, via Motor)
- **Authentication:** JWT-based
- **Containerization:** Docker
- **Other:** CORS enabled, PDF export, Markdown support

### Frontend
- **Framework:** FastAPI (Python)
- **Templating:** Jinja2
- **HTTP Client:** httpx (for backend API communication)
- **Server:** Uvicorn
- **Styling:** Custom CSS (`frontend/static/style.css`)

---

## ⚡ Setup Instructions

### Prerequisites
- Python 3.10+
- MongoDB (local or remote)
- Docker (optional, for containerized setup)



### Backend Setup

#### Local Development
1. **Install dependencies:**
   ```bash
   pip install -r backend/requirements.txt
   ```
2. **Start MongoDB:**
   - Ensure MongoDB is running locally, or update `MONGO_URL` to point to your MongoDB instance.
3. **Run the backend server:**
    Navigate to backend directory:
   ```bash
    cd backend
   ```
    from the `backend` directory:
   ```bash
   uvicorn app.main:app --reload
   ```
4. **Register a user:**
   - Use the `/api/register` endpoint to create your first user (manager or employee).

#### Run backend via Docker
1. **Build the Docker image:**
   ```bash
   cd backend
   docker build -t feedback-backend .
   ```
2. **Run the container:**
   ```bash
   docker run -p 8000:8000 -e MONGO_URL="mongodb://host.docker.internal:27017/feedback_system" feedback-backend
   ```
   - On Windows/Mac, `host.docker.internal` lets Docker access your host's MongoDB.
   - Or link to a MongoDB container/network as needed.

### Frontend Setup

#### Local Development
1. **Install dependencies:**
   ```bash
   pip install -r frontend/requirements.txt
   ```
2. **Run the frontend server:**
    Navigate to frontend directory
   ```bash
   > cd frontend
   ```
    from the `frontend` directory:
   ```bash
   > uvicorn main:app --reload --port 8001
   ```
3. **Access the app:**
   - Open your browser and go to `http://localhost:8001`

---

## 📦 Main Models
- **User**: Manager or Employee, with roles and teams
- **Feedback**: Feedback from manager to employee, with strengths, areas to improve, sentiment, tags, comments
- **Notification**: System/user notifications
- **PeerReview**: Anonymous peer feedback

---

## 📝 Design Notes
- **FastAPI** enables async, modern Python APIs for both backend and frontend.
- **Motor** provides async MongoDB access for scalable data operations.
- **JWT** ensures stateless, secure authentication.
- **CORS** is enabled for frontend-backend separation.
- **PDF/Markdown**: Feedback can be exported as PDF; comments support Markdown.
- **Docker**: For easy deployment and consistent environments.

---
