from fastapi import Depends, HTTPException, status
from .auth import get_current_active_user
from .models import UserInDB

async def get_manager_user(current_user: UserInDB = Depends(get_current_active_user)):
    if current_user.role != "manager":
        raise HTTPException(status_code=403, detail="Managers only")
    return current_user

async def get_employee_user(current_user: UserInDB = Depends(get_current_active_user)):
    if current_user.role != "employee":
        raise HTTPException(status_code=403, detail="Employees only")
    return current_user 