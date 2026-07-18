"""Task management API."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dashscope_client import get_embedding
from app.core.database import get_db
from app.memory.models import Memory
from app.models.task import Task
from app.models.user import User

router = APIRouter(prefix="/api", tags=["tasks"])


class TaskCreateRequest(BaseModel):
    user_id: str = Field(..., min_length=1)
    title: str = Field(..., min_length=1)
    description: str | None = None


class TaskUpdateRequest(BaseModel):
    status: str | None = None
    title: str | None = None
    description: str | None = None


class TaskOut(BaseModel):
    id: str
    user_id: str
    title: str
    description: str | None
    status: str
    created_at: str


async def _get_user_or_404(user_id: str, db: AsyncSession) -> User:
    try:
        user_uuid = uuid.UUID(user_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid user id")

    user = await db.get(User, user_uuid)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.post("/tasks", response_model=TaskOut)
async def create_task(
    body: TaskCreateRequest,
    db: AsyncSession = Depends(get_db),
) -> TaskOut:
    """Create a task and store a matching task memory."""

    await _get_user_or_404(body.user_id, db)
    title = body.title.strip()
    description = body.description.strip() if body.description else None

    task = Task(
        user_id=uuid.UUID(body.user_id),
        title=title,
        description=description,
    )
    db.add(task)

    memory_content = f"Task: {title}"
    embedding = await get_embedding(memory_content)
    db.add(
        Memory(
            user_id=body.user_id,
            type="task",
            content=memory_content,
            embedding=embedding,
            importance=0.8,
        )
    )
    await db.commit()
    await db.refresh(task)

    return TaskOut(
        id=str(task.id),
        user_id=str(task.user_id),
        title=task.title,
        description=task.description,
        status=task.status,
        created_at=task.created_at.isoformat(),
    )


@router.get("/tasks", response_model=list[TaskOut])
async def list_tasks(
    user_id: str = Query(..., min_length=1),
    db: AsyncSession = Depends(get_db),
) -> list[TaskOut]:
    """Return all tasks for a user, newest first."""

    await _get_user_or_404(user_id, db)
    result = await db.execute(
        select(Task)
        .where(Task.user_id == uuid.UUID(user_id))
        .order_by(Task.created_at.desc())
    )
    tasks = result.scalars().all()
    return [
        TaskOut(
            id=str(task.id),
            user_id=str(task.user_id),
            title=task.title,
            description=task.description,
            status=task.status,
            created_at=task.created_at.isoformat(),
        )
        for task in tasks
    ]


@router.patch("/tasks/{task_id}", response_model=TaskOut)
async def update_task(
    task_id: str,
    body: TaskUpdateRequest,
    db: AsyncSession = Depends(get_db),
) -> TaskOut:
    """Update task fields such as status."""

    try:
        task_uuid = uuid.UUID(task_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid task id")

    task = await db.get(Task, task_uuid)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")

    if body.status is not None:
        task.status = body.status
    if body.title is not None:
        task.title = body.title.strip()
    if body.description is not None:
        task.description = body.description.strip() or None

    await db.commit()
    await db.refresh(task)

    return TaskOut(
        id=str(task.id),
        user_id=str(task.user_id),
        title=task.title,
        description=task.description,
        status=task.status,
        created_at=task.created_at.isoformat(),
    )


@router.delete("/tasks/{task_id}")
async def delete_task(
    task_id: str,
    db: AsyncSession = Depends(get_db),
) -> dict[str, bool]:
    """Delete a task."""

    try:
        task_uuid = uuid.UUID(task_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid task id")

    result = await db.execute(delete(Task).where(Task.id == task_uuid))
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Task not found")
    await db.commit()
    return {"success": True}
