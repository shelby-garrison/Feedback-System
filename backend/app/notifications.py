from .crud import create_notification

async def notify_feedback(employee_id: str, message: str):
    await create_notification(employee_id, message) 