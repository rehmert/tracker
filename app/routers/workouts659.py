"""Release 659: one-machine-at-a-time gym logging, reusing validated Workout writes.

No new tables, alternate authentication, data migrations or scoring estimates.
All database reads use the authenticated user's existing scoped SQLite database.
"""
from __future__ import annotations

from urllib.parse import parse_qs, urlsplit

from fastapi import APIRouter, Depends, Form, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import services
from ..scoped_db390 import get_scoped_db390
from ..templating import render
from ..workout_models654 import WorkoutEquipment654, WorkoutSet654
from ..workout_models655 import WorkoutRoutine655, WorkoutRoutineItem655, WorkoutSessionRoutine655
from ..workout_models667 import WorkoutRoutineConfig667, WorkoutRoutineTarget667, WorkoutSessionTarget667, WorkoutSetType667
from ..workout_program667 import progress667
from ..workout_progression674 import progression_for674
from ..workout_models668 import WorkoutRoutineGroup668, WorkoutRoutineGroupMember668, WorkoutEquipmentLoad668
from .workouts654 import active654, add_set654, start654, finish654
from .workouts655 import repeat_last_set655, start_routine655

router = APIRouter()


def redirect_quick659(response, machine_id: int | None = None, *, logged: bool = False):
    """Translate only the trusted existing Workout flash into the quick UI."""
    params = parse_qs(urlsplit(response.headers.get("location", "")).query)
    msg = params.get("msg", [""])[0]
    err = params.get("err", [""])[0]
    target = "/workouts/quick"
    if machine_id is not None:
        target += f"?machine={machine_id}"
    if logged and not err:
        target += ("&" if "?" in target else "?") + "logged=1"
    return services.flash_redirect(target, err=err) if err else services.flash_redirect(
        target, msg=msg
    )


@router.get("/workouts/quick")
def quick_workout659(
    request: Request, machine: int | None = None,
    db: Session = Depends(get_scoped_db390),
):
    equipment = list(db.scalars(
        select(WorkoutEquipment654).order_by(
            WorkoutEquipment654.gym, WorkoutEquipment654.name, WorkoutEquipment654.id
        )
    ))
    active = active654(db)
    link = db.get(WorkoutSessionRoutine655, active.id) if active else None
    routine = db.get(WorkoutRoutine655, link.routine_id) if link else None
    items = list(db.scalars(
        select(WorkoutRoutineItem655)
        .where(WorkoutRoutineItem655.routine_id == routine.id)
        .order_by(WorkoutRoutineItem655.position, WorkoutRoutineItem655.id)
    )) if routine else []
    routine_ids = [item.equipment_id for item in items]
    ranks = {item_id: index for index, item_id in enumerate(routine_ids)}
    equipment.sort(key=lambda item: (
        (0, ranks[item.id]) if item.id in ranks
        else (1, item.gym, item.name, item.id)
    ))
    lookup = {item.id: item for item in equipment}
    latest_active = db.scalar(
        select(WorkoutSet654)
        .where(WorkoutSet654.session_id == active.id)
        .order_by(WorkoutSet654.performed_at.desc(), WorkoutSet654.id.desc())
        .limit(1)
    ) if active else None

    chosen_id = machine if machine in lookup else None
    if chosen_id is None:
        if latest_active and latest_active.equipment_id in lookup:
            chosen_id = latest_active.equipment_id
        elif routine_ids and routine_ids[0] in lookup:
            chosen_id = routine_ids[0]
        elif equipment:
            chosen_id = equipment[0].id
    chosen = lookup.get(chosen_id)
    # Match only the current machine to an item of the active saved routine.
    plan_item_id = next((item.id for item in items
                         if chosen and item.equipment_id == chosen.id), None)
    frozen_goal = db.get(
        WorkoutSessionTarget667, (active.id, chosen.id),
    ) if active and chosen and plan_item_id else None
    current_goal = db.get(WorkoutRoutineTarget667, plan_item_id) if plan_item_id else None
    settings = db.get(WorkoutRoutineConfig667, routine.id) if routine else None
    rest_seconds667 = (
        frozen_goal.rest_seconds if frozen_goal else
        (current_goal.rest_seconds if current_goal and current_goal.rest_seconds else
         (settings.rest_seconds if settings else 90))
    )
    goal_progress667 = progress667(db, active.id, chosen.id) if active and chosen else None
    last = db.scalar(
        select(WorkoutSet654)
        .where(WorkoutSet654.equipment_id == chosen.id)
        .order_by(WorkoutSet654.performed_at.desc(), WorkoutSet654.id.desc())
        .limit(1)
    ) if chosen else None
    machine_sets = list(db.scalars(
        select(WorkoutSet654)
        .where(
            WorkoutSet654.session_id == active.id,
            WorkoutSet654.equipment_id == chosen.id,
        )
        .order_by(WorkoutSet654.performed_at.desc(), WorkoutSet654.id.desc())
        .limit(12)
    )) if active and chosen else []
    all_logged_ids = set(db.scalars(
        select(WorkoutSet654.equipment_id).where(WorkoutSet654.session_id == active.id)
    )) if active else set()
    next_id = None
    previous_id = None
    if chosen and chosen.id in ranks:
        index = ranks[chosen.id]
        if index + 1 < len(routine_ids):
            next_id = routine_ids[index + 1]
        if index > 0:
            previous_id = routine_ids[index - 1]
    # Advisory group membership only; the gym form remains the sole set writer.
    grouped668 = []
    if routine:
        for group in db.scalars(
            select(WorkoutRoutineGroup668)
            .where(WorkoutRoutineGroup668.routine_id == routine.id)
            .order_by(WorkoutRoutineGroup668.id)
        ):
            member_rows = list(db.scalars(
                select(WorkoutRoutineGroupMember668)
                .where(WorkoutRoutineGroupMember668.group_id == group.id)
                .order_by(WorkoutRoutineGroupMember668.position,
                          WorkoutRoutineGroupMember668.id)
            ))
            by_id = {item.id: item.equipment_id for item in items}
            machines = [lookup[by_id[member.routine_item_id]]
                        for member in member_rows
                        if member.routine_item_id in by_id
                        and by_id[member.routine_item_id] in lookup]
            if machines:
                # Count only actual working sets. The visual round guide
                # never creates sets or implies that exercise was performed.
                count_rows = dict(db.execute(
                    select(WorkoutSet654.equipment_id, func.count(WorkoutSet654.id))
                    .outerjoin(
                        WorkoutSetType667,
                        WorkoutSetType667.set_id == WorkoutSet654.id,
                    )
                    .where(
                        WorkoutSet654.session_id == active.id,
                        WorkoutSet654.equipment_id.in_([m.id for m in machines]),
                        (WorkoutSetType667.set_type.is_(None) |
                         (WorkoutSetType667.set_type == "working")),
                    )
                    .group_by(WorkoutSet654.equipment_id)
                ).all()) if active else {}
                minimum = min((count_rows.get(m.id, 0) for m in machines), default=0)
                follow = next((m for m in machines
                               if count_rows.get(m.id, 0) == minimum
                               and minimum < group.rounds), None)
                grouped668.append(dict(
                    group=group, machines=machines,
                    progress={m.id: min(count_rows.get(m.id, 0), group.rounds)
                              for m in machines},
                    next_machine=follow,
                    complete=follow is None,
                ))
    progression674 = progression_for674(
        db, chosen.id,
        (frozen_goal.target_reps if frozen_goal else (
            current_goal.target_reps if current_goal else None
        )),
    ) if chosen else None
    routines = list(db.scalars(
        select(WorkoutRoutine655).order_by(
            WorkoutRoutine655.created_at.desc(), WorkoutRoutine655.id.desc()
        ).limit(20)
    )) if not active else []
    return render(
        request, "workout_quick659.html",
        active=active, machine=chosen, equipment=equipment, routines=routines,
        routine=routine, routine_total=len(routine_ids),
        grouped668=grouped668,
        load_config668=db.get(WorkoutEquipmentLoad668, chosen.id) if chosen else None,
        plan_item_id=plan_item_id,
        frozen_goal=frozen_goal, current_goal=current_goal,
        goal_progress667=goal_progress667,
        rest_seconds667=rest_seconds667,
        routine_logged=len(all_logged_ids.intersection(routine_ids)),
        machine_sets=machine_sets, last=last, progression674=progression674,
        previous_machine=lookup.get(previous_id),
        next_machine=lookup.get(next_id),
    )


@router.post("/workouts/quick/start")
def quick_start659(db: Session = Depends(get_scoped_db390)):
    response = start654(db=db)
    return redirect_quick659(response)


@router.post("/workouts/quick/routines/{routine_id}/start")
def quick_start_routine659(
    routine_id: int, db: Session = Depends(get_scoped_db390),
):
    response = start_routine655(routine_id=routine_id, db=db)
    params = parse_qs(urlsplit(response.headers.get("location", "")).query)
    selected = params.get("machine", [None])[0]
    return redirect_quick659(response, machine_id=int(selected) if selected else None)


@router.post("/workouts/quick/sets")
def quick_set659(
    equipment_id: int = Form(...), weight_lb: float = Form(...),
    reps: int = Form(...), effort: str = Form(""),
    set_type: str = Form("working"),
    db: Session = Depends(get_scoped_db390),
):
    response = add_set654(
        equipment_id=equipment_id, weight_lb=weight_lb,
        reps=reps, effort=effort, db=db, set_type=set_type,
    )
    return redirect_quick659(response, equipment_id, logged=True)


@router.post("/workouts/quick/repeat")
def quick_repeat659(
    equipment_id: int = Form(...), source_set_id: int = Form(...),
    db: Session = Depends(get_scoped_db390),
):
    response = repeat_last_set655(
        equipment_id=equipment_id, source_set_id=source_set_id, db=db,
    )
    return redirect_quick659(response, equipment_id, logged=True)


@router.post("/workouts/quick/finish")
def quick_finish659(db: Session = Depends(get_scoped_db390)):
    response = finish654(db=db)
    return redirect_quick659(response)
