"""Release 659: one-machine-at-a-time gym logging, reusing validated Workout writes.

No new tables, alternate authentication, data migrations or scoring estimates.
All database reads use the authenticated user's existing scoped SQLite database.
"""
from __future__ import annotations

from urllib.parse import parse_qs, urlsplit

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .. import services
from ..scoped_db390 import get_scoped_db390
from ..templating import render
from ..workout_models654 import KINDS654, WorkoutEquipment654, WorkoutSet654
from ..workout_models655 import WorkoutRoutine655, WorkoutRoutineItem655, WorkoutSessionRoutine655
from ..workout_models667 import WorkoutRoutineConfig667, WorkoutRoutineTarget667, WorkoutSessionTarget667, WorkoutSetType667
from ..workout_program667 import progress667
from ..workout_progression674 import progression_for674
from ..workout_models668 import WorkoutRoutineGroup668, WorkoutRoutineGroupMember668, WorkoutEquipmentLoad668
from .workouts654 import active654, add_set654, start654, finish654
from .workouts655 import MAX_ROUTINE_ITEMS655, repeat_last_set655, start_routine655

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
        available_to_add716=[item for item in equipment if not routine or item.id not in ranks],
        equipment_kinds716=KINDS654,
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

def _active_for_machine716(db: Session, session_id: int):
    """A stale phone form must never modify the next workout's routine."""
    active = active654(db)
    if active is None or active.id != session_id:
        return None
    return active


def _add_to_active_routine716(db: Session, session_id: int, equipment_id: int) -> bool:
    """Append to the active saved routine; a free workout has no planned list.

    The routine is deliberately modified for later sessions too. Existing
    frozen session goals and recorded sets are never overwritten.
    """
    link = db.get(WorkoutSessionRoutine655, session_id)
    if link is None:
        return False
    items = list(db.scalars(
        select(WorkoutRoutineItem655)
        .where(WorkoutRoutineItem655.routine_id == link.routine_id)
        .order_by(WorkoutRoutineItem655.position, WorkoutRoutineItem655.id)
    ))
    if any(item.equipment_id == equipment_id for item in items):
        raise ValueError("This machine is already in your saved routine.")
    if len(items) >= MAX_ROUTINE_ITEMS655:
        raise ValueError("The saved routine already has 30 exercises.")
    db.add(WorkoutRoutineItem655(
        routine_id=link.routine_id, equipment_id=equipment_id,
        position=max((item.position for item in items), default=-1) + 1,
    ))
    return True


@router.post("/workouts/quick/machines")
def quick_add_existing_machine716(
    session_id: int = Form(...), equipment_id: int = Form(...),
    db: Session = Depends(get_scoped_db390),
):
    if _active_for_machine716(db, session_id) is None:
        return services.flash_redirect(
            "/workouts/quick", err="Workout changed. Reopen Add Machine."
        )
    if db.get(WorkoutEquipment654, equipment_id) is None:
        raise HTTPException(404, "Equipment not found")
    try:
        saved = _add_to_active_routine716(db, session_id, equipment_id)
        if saved:
            db.commit()
    except ValueError as exc:
        db.rollback()
        return services.flash_redirect("/workouts/quick", err=str(exc))
    except IntegrityError:
        db.rollback()
        return services.flash_redirect(
            "/workouts/quick", err="Unable to add this machine to the routine."
        )
    return services.flash_redirect(
        f"/workouts/quick?machine={equipment_id}",
        msg=("Machine added to this workout and saved routine." if saved else
             "Machine selected. Log a set to include it in this free workout."),
    )


@router.post("/workouts/quick/machines/new")
def quick_create_machine716(
    session_id: int = Form(...), name: str = Form(""),
    kind: str = Form("selectorized"),
    gym: str = Form("Merritt Athletic Club - Eldersburg"),
    manufacturer: str = Form(""), seat_setting: str = Form(""),
    db: Session = Depends(get_scoped_db390),
):
    if _active_for_machine716(db, session_id) is None:
        return services.flash_redirect(
            "/workouts/quick", err="Workout changed. Reopen Add Machine."
        )
    name, gym = name.strip(), gym.strip()
    manufacturer, seat_setting = manufacturer.strip(), seat_setting.strip()
    if not name or len(name) > 140 or not gym or len(gym) > 140:
        return services.flash_redirect(
            "/workouts/quick", err="Enter a machine name and gym (up to 140 characters)."
        )
    if kind not in KINDS654 or len(manufacturer) > 100 or len(seat_setting) > 80:
        return services.flash_redirect(
            "/workouts/quick", err="Invalid equipment type or machine details."
        )
    # Prevent accidental doubles from a phone submission. A machine is
    # cataloged once, then reused in every workout.
    existing = list(db.scalars(select(WorkoutEquipment654)))
    if any(m.name.casefold() == name.casefold() and
           m.gym.casefold() == gym.casefold() for m in existing):
        return services.flash_redirect(
            "/workouts/quick", err="Machine already exists. Select it above."
        )
    link = db.get(WorkoutSessionRoutine655, session_id)
    if link is not None:
        count = db.scalar(select(func.count(WorkoutRoutineItem655.id)).where(
            WorkoutRoutineItem655.routine_id == link.routine_id
        ))
        if count >= MAX_ROUTINE_ITEMS655:
            return services.flash_redirect(
                "/workouts/quick", err="The saved routine already has 30 exercises."
            )
    machine = WorkoutEquipment654(
        name=name, kind=kind, gym=gym, manufacturer=manufacturer,
        seat_setting=seat_setting,
    )
    db.add(machine)
    try:
        db.flush()
        saved = _add_to_active_routine716(db, session_id, machine.id)
        db.commit()
    except (ValueError, IntegrityError):
        db.rollback()
        return services.flash_redirect(
            "/workouts/quick", err="Could not add that machine. Try again."
        )
    return services.flash_redirect(
        f"/workouts/quick?machine={machine.id}",
        msg=("New machine created and added to your saved routine." if saved else
             "New machine created. Log a set to include it in this workout."),
    )
