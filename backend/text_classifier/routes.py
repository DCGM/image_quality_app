from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from text_classifier import base_objects, crud
from text_classifier.database import User, get_async_session
from text_classifier.db_model import Task
from text_classifier.users import current_active_user
from text_classifier.prompt_parser import load_prompts

api_route = APIRouter()
admin_route = APIRouter()


@api_route.get('/tasks', response_model=list[base_objects.TaskDefinition])
async def tasks(db: AsyncSession = Depends(get_async_session)):
    return await crud.list_enabled_tasks(db)


@admin_route.get('/tasks', response_model=list[base_objects.TaskDefinition])
async def admin_tasks(user: User = Depends(current_active_user), db: AsyncSession = Depends(get_async_session)):
    if not user.is_superuser:
        raise HTTPException(status_code=403)
    return await crud.list_tasks(db)


@api_route.get('/tasks/{task_id}', response_model=base_objects.TaskDefinition)
async def task(task_id: str, db: AsyncSession = Depends(get_async_session)):
    t = await db.get(Task, task_id)
    if not t or not t.enabled:
        raise HTTPException(status_code=404, detail='Task not found')
    return t


@api_route.post('/texts/next', response_model=base_objects.NextTextResponse)
async def next_text(payload: base_objects.NextTextRequest, user: User = Depends(current_active_user), db: AsyncSession = Depends(get_async_session)):
    t = await crud.get_next_text(db, user.id, payload.task_ids)
    if t is None:
        return Response(status_code=204)
    return {'id': t.id, 'text': t.text, 'language': t.language}


@api_route.post('/annotations')
async def annotations(payload: base_objects.AnnotationSubmit, user: User = Depends(current_active_user), db: AsyncSession = Depends(get_async_session)):
    task_ids = {a.task_id for a in payload.annotations}
    tasks = (await db.execute(select(Task).where(Task.id.in_(task_ids), Task.enabled.is_(True)))).scalars().all()
    tasks_map = {t.id: t for t in tasks}
    if len(tasks_map) != len(task_ids):
        raise HTTPException(status_code=400, detail='Unknown or disabled task in payload')
    try:
        await crud.save_annotations(db, user.id, payload, tasks_map)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    await db.commit()
    return Response(status_code=201)


@api_route.get('/stats/me')
async def stats_me(user: User = Depends(current_active_user), db: AsyncSession = Depends(get_async_session)):
    return await crud.my_stats(db, user.id)


@api_route.get('/stats/global', response_model=base_objects.GlobalStats)
async def stats_global(db: AsyncSession = Depends(get_async_session)):
    return await crud.global_stats(db)


@api_route.get('/stats/leaderboard', response_model=list[base_objects.LeaderboardEntry])
async def stats_lb_overall(
    since_days: Optional[int] = Query(None, description='Limit to annotations in the last N days'),
    db: AsyncSession = Depends(get_async_session),
):
    since = datetime.now(timezone.utc) - timedelta(days=since_days) if since_days else None
    return await crud.leaderboard_overall(db, since=since)


@api_route.get('/stats/leaderboard/{task_id}', response_model=list[base_objects.LeaderboardEntry])
async def stats_lb(
    task_id: str,
    since_days: Optional[int] = Query(None, description='Limit to annotations in the last N days'),
    db: AsyncSession = Depends(get_async_session),
):
    since = datetime.now(timezone.utc) - timedelta(days=since_days) if since_days else None
    return await crud.leaderboard(db, task_id, since=since)


@admin_route.post('/tasks')
async def admin_task(task: base_objects.TaskDefinition, user: User = Depends(current_active_user), db: AsyncSession = Depends(get_async_session)):
    if not user.is_superuser:
        raise HTTPException(status_code=403)
    await crud.upsert_task(db, task)
    await db.commit()
    return Response(status_code=201)


@admin_route.put('/tasks/{task_id}')
async def admin_task_put(task_id: str, task: base_objects.TaskDefinition, user: User = Depends(current_active_user), db: AsyncSession = Depends(get_async_session)):
    if not user.is_superuser:
        raise HTTPException(status_code=403)
    if task.id != task_id:
        raise HTTPException(status_code=400, detail='Task id in path and body must match')
    await crud.upsert_task(db, task)
    await db.commit()
    return Response(status_code=204)


@admin_route.patch('/tasks/{task_id}')
async def admin_task_patch(task_id: str, patch: base_objects.TaskStatePatch, user: User = Depends(current_active_user), db: AsyncSession = Depends(get_async_session)):
    if not user.is_superuser:
        raise HTTPException(status_code=403)
    changed = await crud.set_task_state(db, task_id, patch)
    if not changed:
        raise HTTPException(status_code=404)
    await db.commit()
    return Response(status_code=204)


@admin_route.post('/tasks/import-prompts')
async def admin_import_prompts(user: User = Depends(current_active_user), db: AsyncSession = Depends(get_async_session)):
    if not user.is_superuser:
        raise HTTPException(status_code=403)
    prompts = load_prompts(Path(__file__).resolve().parents[2] / 'prompts')
    for item in prompts:
        await crud.upsert_task(db, base_objects.TaskDefinition(**item))
    await db.commit()
    return {'imported': len(prompts)}


@admin_route.get('/texts', response_model=base_objects.TextListResponse)
async def admin_list_texts(
    page: int = Query(0, ge=0),
    q: str = Query(''),
    page_size: int = Query(50, ge=1, le=200),
    user: User = Depends(current_active_user),
    db: AsyncSession = Depends(get_async_session),
):
    if not user.is_superuser:
        raise HTTPException(status_code=403)
    return await crud.list_texts(db, page=page, q=q, page_size=page_size)


@admin_route.patch('/texts/{text_id}')
async def admin_patch_text(text_id: str, patch: base_objects.TextPatch, user: User = Depends(current_active_user), db: AsyncSession = Depends(get_async_session)):
    if not user.is_superuser:
        raise HTTPException(status_code=403)
    found = await crud.set_text_suspended(db, text_id, patch.suspended)
    if not found:
        raise HTTPException(status_code=404)
    await db.commit()
    return Response(status_code=204)


@admin_route.post('/texts')
async def admin_texts(lines: str = Body(..., media_type='text/plain'), user: User = Depends(current_active_user), db: AsyncSession = Depends(get_async_session)):
    if not user.is_superuser:
        raise HTTPException(status_code=403)
    count = 0
    for line in lines.splitlines():
        if not line.strip():
            continue
        rec = json.loads(line)
        if 'id' not in rec or 'text' not in rec or 'language' not in rec:
            raise HTTPException(status_code=400, detail='Each JSONL row must include id, text, language')
        await crud.upsert_text(db, rec['id'], rec['text'], rec['language'], rec)
        count += 1
    await db.commit()
    return {'imported': count}



@api_route.get('/tasks', response_model=list[base_objects.TaskDefinition])
async def tasks(db: AsyncSession = Depends(get_async_session)):
    return await crud.list_enabled_tasks(db)


@admin_route.get('/tasks', response_model=list[base_objects.TaskDefinition])
async def admin_tasks(user: User = Depends(current_active_user), db: AsyncSession = Depends(get_async_session)):
    if not user.is_superuser:
        raise HTTPException(status_code=403)
    return await crud.list_tasks(db)


@api_route.get('/tasks/{task_id}', response_model=base_objects.TaskDefinition)
async def task(task_id: str, db: AsyncSession = Depends(get_async_session)):
    t = await db.get(Task, task_id)
    if not t or not t.enabled:
        raise HTTPException(status_code=404, detail='Task not found')
    return t


@api_route.post('/texts/next', response_model=base_objects.NextTextResponse)
async def next_text(payload: base_objects.NextTextRequest, user: User = Depends(current_active_user), db: AsyncSession = Depends(get_async_session)):
    t = await crud.get_next_text(db, user.id, payload.task_ids)
    if t is None:
        return Response(status_code=204)
    return {'id': t.id, 'text': t.text, 'language': t.language}


@api_route.post('/annotations')
async def annotations(payload: base_objects.AnnotationSubmit, user: User = Depends(current_active_user), db: AsyncSession = Depends(get_async_session)):
    task_ids = {a.task_id for a in payload.annotations}
    tasks = (await db.execute(select(Task).where(Task.id.in_(task_ids), Task.enabled.is_(True)))).scalars().all()
    tasks_map = {t.id: t for t in tasks}
    if len(tasks_map) != len(task_ids):
        raise HTTPException(status_code=400, detail='Unknown or disabled task in payload')
    try:
        await crud.save_annotations(db, user.id, payload, tasks_map)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    await db.commit()
    return Response(status_code=201)


@api_route.get('/stats/me')
async def stats_me(user: User = Depends(current_active_user), db: AsyncSession = Depends(get_async_session)):
    return await crud.my_stats(db, user.id)


@api_route.get('/stats/leaderboard/{task_id}')
async def stats_lb(task_id: str, db: AsyncSession = Depends(get_async_session)):
    return await crud.leaderboard(db, task_id)


@admin_route.post('/tasks')
async def admin_task(task: base_objects.TaskDefinition, user: User = Depends(current_active_user), db: AsyncSession = Depends(get_async_session)):
    if not user.is_superuser:
        raise HTTPException(status_code=403)
    await crud.upsert_task(db, task)
    await db.commit()
    return Response(status_code=201)


@admin_route.put('/tasks/{task_id}')
async def admin_task_put(task_id: str, task: base_objects.TaskDefinition, user: User = Depends(current_active_user), db: AsyncSession = Depends(get_async_session)):
    if not user.is_superuser:
        raise HTTPException(status_code=403)
    if task.id != task_id:
        raise HTTPException(status_code=400, detail='Task id in path and body must match')
    await crud.upsert_task(db, task)
    await db.commit()
    return Response(status_code=204)


@admin_route.patch('/tasks/{task_id}')
async def admin_task_patch(task_id: str, patch: base_objects.TaskStatePatch, user: User = Depends(current_active_user), db: AsyncSession = Depends(get_async_session)):
    if not user.is_superuser:
        raise HTTPException(status_code=403)
    changed = await crud.set_task_state(db, task_id, patch)
    if not changed:
        raise HTTPException(status_code=404)
    await db.commit()
    return Response(status_code=204)


@admin_route.post('/tasks/import-prompts')
async def admin_import_prompts(user: User = Depends(current_active_user), db: AsyncSession = Depends(get_async_session)):
    if not user.is_superuser:
        raise HTTPException(status_code=403)
    prompts = load_prompts(Path(__file__).resolve().parents[2] / 'prompts')
    for item in prompts:
        await crud.upsert_task(db, base_objects.TaskDefinition(**item))
    await db.commit()
    return {'imported': len(prompts)}


@admin_route.post('/texts')
async def admin_texts(lines: str = Body(..., media_type='text/plain'), user: User = Depends(current_active_user), db: AsyncSession = Depends(get_async_session)):
    if not user.is_superuser:
        raise HTTPException(status_code=403)
    for line in lines.splitlines():
        if not line.strip():
            continue
        rec = json.loads(line)
        if 'id' not in rec or 'text' not in rec or 'language' not in rec:
            raise HTTPException(status_code=400, detail='Each JSONL row must include id, text, language')
        await crud.upsert_text(db, rec['id'], rec['text'], rec['language'], rec)
    await db.commit()
