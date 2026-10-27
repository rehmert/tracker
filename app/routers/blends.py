"""Record physical vial transfers into a blend; no dosing recommendations."""
from datetime import datetime
from math import isfinite

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import services, units as U
from ..db import get_db
from ..models import Blend, BlendComponent, BlendDose, Vial
from ..templating import render

router = APIRouter()


def _positive(value, name, allow_zero=False):
    try:
        n = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{name} must be a number.")
    if not isfinite(n) or n < 0 or (not allow_zero and n == 0):
        raise ValueError(f"{name} must be {'nonnegative' if allow_zero else 'positive'} and finite.")
    return n


def blend_remaining(blend):
    return max(0.0, blend.final_volume_ml - sum(d.volume_ml for d in blend.doses))


def component_rows(blend):
    remaining = blend_remaining(blend)
    return [dict(item=c, unit=U.BASE_UNIT[U.parse_unit(c.source_vial.content_unit).dim],
                 concentration=c.transferred_base / blend.final_volume_ml,
                 target_value=U.from_base(c.target_dose_base, c.target_unit),
                 remaining=remaining * c.transferred_base / blend.final_volume_ml,
                 draw_ml=c.target_dose_base * blend.final_volume_ml / c.transferred_base)
            for c in blend.components]


@router.get('/blends')
def blends_page(request: Request, db: Session = Depends(get_db)):
    vials = list(db.scalars(select(Vial).where(Vial.status.in_(['sealed', 'in_use'])).order_by(Vial.id)))
    views = services.vial_views(db, vials)
    blends = list(db.scalars(select(Blend).order_by(Blend.id.desc())))
    return render(request, 'blends.html', vials=vials, views=views, blends=blends,
                  remaining={b.id: blend_remaining(b) for b in blends}, units=U.CONTENT_UNITS)


def calculate_blend(form, db: Session):
    """Validate and calculate a proposed blend without changing the database."""
    label = str(form.get('label', '')).strip()
    if not label:
        raise ValueError('Enter a label for the destination vial.')
    diluent = _positive(form.get('diluent_ml', '0'), 'Added diluent', allow_zero=True)
    capacity_raw = str(form.get('capacity_ml', '')).strip()
    capacity = _positive(capacity_raw, 'Destination capacity') if capacity_raw else None
    ids = form.getlist('source_id')
    amounts = form.getlist('transfer_amount')
    units = form.getlist('transfer_unit')
    targets = form.getlist('target_amount')
    target_units = form.getlist('target_unit')
    if not (2 <= len(ids) <= 8) or not all(len(x) == len(ids) for x in (amounts, units, targets, target_units)):
        raise ValueError('Choose between 2 and 8 source vials and complete every row.')
    if len(set(ids)) != len(ids):
        raise ValueError('Each source vial may be selected only once.')
    source_vials = [db.get(Vial, int(i)) for i in ids]
    if any(v is None or v.status not in ('sealed', 'in_use') for v in source_vials):
        raise ValueError('One or more source vials are unavailable.')
    views = services.vial_views(db, source_vials)
    transfers = []
    compound_ids = set()
    volume = diluent
    for vial, amount, unit, target, target_unit in zip(source_vials, amounts, units, targets, target_units):
        if vial.compound_id in compound_ids:
            raise ValueError('Choose one source vial per peptide; duplicate compounds are not supported.')
        compound_ids.add(vial.compound_id)
        vd = views[vial.id]
        base = _positive(amount, f'Transfer for vial #{vial.id}')
        base, dim = U.to_base(base, unit)
        if dim != vd.dim:
            raise ValueError(f'Vial #{vial.id}: transfer unit does not match its compound.')
        if base > vd.remaining_base + 1e-6:
            raise ValueError(f'Vial #{vial.id}: insufficient remaining content.')
        target_base, target_dim = U.to_base(_positive(target, f'Target for vial #{vial.id}'), target_unit)
        if target_dim != vd.dim:
            raise ValueError(f'Vial #{vial.id}: target dose unit does not match its compound.')
        if vial.volume_ml:
            transferred_ml = base / vd.conc_per_ml
        else:
            raise ValueError(f'Vial #{vial.id}: reconstitute the source vial before recording a blend transfer. Use the reconstitution what-if planner first.')
        volume += transferred_ml
        transfers.append((vial, base, transferred_ml, target_base, U.parse_unit(target_unit).name))
    if volume <= 0:
        raise ValueError('Final liquid volume must exceed zero; enter the diluent volume.')
    if capacity is not None and volume > capacity + 1e-8:
        raise ValueError(f'Calculated volume {volume:g} mL exceeds destination capacity {capacity:g} mL.')
    draw_volumes = [t[3] * volume / t[1] for t in transfers]
    if any(draw > volume + 1e-8 for draw in draw_volumes):
        raise ValueError('One or more target doses exceed the blend contents.')
    # A single draw delivers every compound in a fixed ratio. Reject incompatible targets.
    if max(draw_volumes) - min(draw_volumes) > max(1e-5, max(draw_volumes) * 0.001):
        details = ', '.join(f'{v.compound.name}: {draw:.4g} mL' for (v, *_), draw in zip(transfers, draw_volumes))
        raise ValueError('Per-peptide dose targets require different draw volumes. Adjust transfers or targets. ' + details)
    return dict(label=label, diluent=diluent, capacity=capacity, volume=volume,
                transfers=transfers, views=views, draw_ml=sum(draw_volumes)/len(draw_volumes),
                notes=str(form.get('notes', '')).strip())


def calculate_reconstitution_plan(form, db: Session):
    """What-if BAC allocations; does not update source vials or blend inventory.

    Assumes nominal volume additivity and ignores powder displacement. No physical
    compatibility, solubility, sterility or cartridge headspace is inferred.
    """
    ids = form.getlist('source_id')
    amounts = form.getlist('transfer_amount')
    units = form.getlist('transfer_unit')
    targets = form.getlist('target_amount')
    target_units = form.getlist('target_unit')
    bac_inputs = form.getlist('source_bac_ml')
    if not (2 <= len(ids) <= 8) or any(len(x) != len(ids) for x in (amounts, units, targets, target_units, bac_inputs)):
        raise ValueError('Complete 2–8 source rows, including BAC water fields.')
    if len(set(ids)) != len(ids):
        raise ValueError('Select each source vial only once.')
    capacity = _positive(form.get('planner_capacity_ml', '3'), 'Cartridge capacity')
    draw = _positive(form.get('planner_draw_ml'), 'Desired draw volume')
    if draw > capacity:
        raise ValueError('Desired draw exceeds cartridge capacity.')
    vials = []
    for raw in ids:
        try:
            vial = db.get(Vial, int(raw))
        except (ValueError, TypeError):
            vial = None
        if vial is None or vial.status not in ('sealed', 'in_use'):
            raise ValueError('A source vial is unavailable.')
        vials.append(vial)
    if len({v.compound_id for v in vials}) != len(vials):
        raise ValueError('Select one vial per compound.')
    views = services.vial_views(db, vials)
    rows = []
    total_fixed = 0.0
    for vial, amount, unit, target, target_unit, bac_raw in zip(vials, amounts, units, targets, target_units, bac_inputs):
        vd = views[vial.id]
        base, dim = U.to_base(_positive(amount, 'Transfer amount'), unit)
        target_base, tdim = U.to_base(_positive(target, 'Target per draw'), target_unit)
        if dim != vd.dim or tdim != vd.dim:
            raise ValueError(f'{vial.compound.name}: incompatible units.')
        if base > vd.remaining_base + 1e-6:
            raise ValueError(f'{vial.compound.name}: transfer exceeds remaining inventory.')
        if vial.volume_ml:
            if str(bac_raw).strip() and _positive(bac_raw, 'Source BAC', allow_zero=True) > 0:
                raise ValueError(f'{vial.compound.name}: already liquid; source BAC must be zero.')
            source_ml = base / vd.conc_per_ml
            bac = 0.0
        else:
            bac = _positive(bac_raw, f'BAC for {vial.compound.name}')
            # First reconstitute the *entire* dry source. Only the fraction
            # containing the requested peptide amount is transferred.
            source_ml = bac * (base / vd.remaining_base)
        total_fixed += source_ml
        rows.append(dict(vial=vial, base=base, target_base=target_base,
                         target_unit=target_unit, bac=bac, source_ml=source_ml,
                         source_total_ml=(vial.volume_ml if vial.volume_ml else bac),
                         source_left_ml=((vial.volume_ml if vial.volume_ml else bac) - source_ml),
                         base_unit=U.BASE_UNIT[vd.dim]))
    # Fixed composition: every peptide must require the same final volume for a
    # chosen draw. BAC changes dilution but cannot correct unequal ratios.
    volumes = [r['base'] * draw / r['target_base'] for r in rows]
    final_volume = sum(volumes) / len(volumes)
    if max(volumes) - min(volumes) > max(1e-5, max(volumes) * 0.001):
        details = ', '.join(f"{r['vial'].compound.name}: {v:.4g} mL" for r, v in zip(rows, volumes))
        raise ValueError('Targets have incompatible peptide ratios; BAC water alone cannot fix this. Required final volumes: ' + details)
    if final_volume > capacity + 1e-8:
        raise ValueError(f'Required {final_volume:.4g} mL exceeds {capacity:.4g} mL capacity. Reduce transfer quantities or adjust the desired draw/targets.')
    if total_fixed > final_volume + 1e-8:
        raise ValueError(f'Source liquid totals {total_fixed:.4g} mL, exceeding required {final_volume:.4g} mL. Reduce source BAC allocations or transfer amounts.')
    destination_bac = max(0.0, final_volume - total_fixed)
    for r in rows:
        r['actual_per_draw'] = r['base'] * draw / final_volume
        r['concentration'] = r['base'] / final_volume
    return dict(rows=rows, capacity=capacity, draw=draw, volume=final_volume,
                source_liquid=total_fixed, destination_bac=destination_bac,
                free_capacity=capacity-final_volume)


@router.post('/blends/reconstitution-preview')
async def preview_reconstitution(request: Request, db: Session = Depends(get_db)):
    """Read-only planner; intentionally does not call the blend creation route."""
    from fastapi.responses import HTMLResponse
    from html import escape
    try:
        plan = calculate_reconstitution_plan(await request.form(), db)
        lines = ['<h3>Reconstitution what-if (not saved)</h3>',
                 '<p><strong>No inventory has been changed.</strong> '
                 'Calculated liquid volumes assume additive volumes and ignore powder displacement, '
                 'solubility, compatibility, sterility and cartridge headspace.</p>',
                 f'<p>Target final volume: <strong>{plan["volume"]:.4g} mL</strong> / '
                 f'{plan["capacity"]:.4g} mL capacity · Remaining nominal space: '
                 f'{plan["free_capacity"]:.4g} mL · '
                 f'Draw: <strong>{plan["draw"]:.4g} mL</strong> '
                 f'({plan["draw"]*100:.4g} U-100 units)</p>',
                 '<div class="scroll"><table><thead><tr><th>Peptide</th><th>Source BAC (mL)</th>'
                 '<th>Withdraw from source (mL)</th><th>Liquid left in source (mL)</th><th>Final concentration</th>'
                 '<th>Per draw</th></tr></thead><tbody>']
        for r in plan['rows']:
            cells = (r['vial'].compound.name, f'{r["bac"]:.4g}',
                     f'{r["source_ml"]:.4g}', f'{r["source_left_ml"]:.4g}',
                     f'{r["concentration"]:.4g} {r["base_unit"]}/mL',
                     f'{U.from_base(r["actual_per_draw"],r["target_unit"]):.4g} {r["target_unit"]}')
            lines.append('<tr>' + ''.join(f'<td>{escape(str(v))}</td>' for v in cells) + '</tr>')
        lines.append('</tbody></table></div>'
                     f'<p>Additional BAC in destination vial: <strong>{plan["destination_bac"]:.4g} mL</strong>. '
                     'Each dry source is reconstituted first; only the calculated withdrawal is transferred. '
                     'Source BAC values are user-entered assumptions, not recommended reconstitution volumes.</p>'
                     '<p><strong>Preview only:</strong> To record a blend, first record source reconstitutions '
                     'in the normal vial workflow, then use the existing blend form with the measured volumes.</p>')
        return HTMLResponse(''.join(lines))
    except (ValueError, TypeError, U.UnitError, OverflowError, ZeroDivisionError) as exc:
        return HTMLResponse('<p role="alert"><strong>Cannot calculate:</strong> '+escape(str(exc))+'</p>', status_code=422)


@router.post('/blends/preview')
async def preview_blend(request: Request, db: Session = Depends(get_db)):
    """What-if calculations only: no INSERT, UPDATE, or inventory transfer."""
    from fastapi.responses import HTMLResponse
    from html import escape
    form = await request.form()
    try:
        plan = calculate_blend(form, db)
        volume = plan['volume']
        draw = plan['draw_ml']
        lines = [f'<h3>What-if preview: {escape(plan["label"])}</h3>',
                 '<p><strong>Preview only.</strong> No blend has been saved and no inventory has been deducted.</p>',
                 f'<p>Final volume: <strong>{volume:.4g} mL</strong> · '
                 f'Common draw: <strong>{draw:.4g} mL</strong> '
                 f'({draw * 100:.4g} U-100 units) · '
                 f'Estimated full draws: <strong>{int((volume + 1e-9) / draw)}</strong></p>',
                 '<div class="scroll"><table><thead><tr><th>Compound</th><th>Source</th><th>Transfer</th>'
                 '<th>Source liquid</th><th>Concentration</th><th>Per draw</th><th>Remaining in source after save</th>'
                 '</tr></thead><tbody>']
        for vial, base, transferred_ml, target_base, target_unit in plan['transfers']:
            dim = plan['views'][vial.id].dim
            base_unit = U.BASE_UNIT[dim]
            after = max(0, plan['views'][vial.id].remaining_base - base)
            lines.append('<tr>' + ''.join(f'<td>{escape(str(value))}</td>' for value in (
                vial.compound.name, vial.label or f'#{vial.id}',
                f'{base:.4g} {base_unit}', f'{transferred_ml:.4g} mL',
                f'{base / volume:.4g} {base_unit}/mL',
                f'{U.from_base(target_base, target_unit):.4g} {target_unit}',
                f'{after:.4g} {base_unit}')) + '</tr>')
        lines.append('</tbody></table></div><p>Review the calculations before recording the blend.</p>')
        return HTMLResponse(''.join(lines))
    except (ValueError, TypeError, U.UnitError, OverflowError) as exc:
        return HTMLResponse('<p role="alert"><strong>Cannot preview:</strong> '+escape(str(exc))+'</p>',status_code=422)


@router.post('/blends')
async def create_blend(request: Request, db: Session = Depends(get_db)):
    form = await request.form()
    try:
        plan = calculate_blend(form, db)
        label, diluent, capacity, volume = (plan[k] for k in ('label', 'diluent', 'capacity', 'volume'))
        transfers, views = plan['transfers'], plan['views']
        blend = Blend(label=label, final_volume_ml=volume, diluent_ml=diluent,
                      capacity_ml=capacity, notes=str(form.get('notes', '')).strip())
        db.add(blend)
        db.flush()
        for vial, base, transferred_ml, target_base, target_unit in transfers:
            db.add(BlendComponent(blend_id=blend.id, source_vial_id=vial.id,
                                  compound_id=vial.compound_id, transferred_base=base,
                                  transferred_ml=transferred_ml, target_dose_base=target_base,
                                  target_unit=target_unit))
            vial.status = 'in_use' if base < views[vial.id].remaining_base - 1e-6 else 'finished'
        db.commit()
        return services.flash_redirect(f'/blends/{blend.id}', msg='Blend recorded; source inventory transferred.')
    except (ValueError, TypeError, U.UnitError) as exc:
        db.rollback()
        return services.flash_redirect('/blends', err=str(exc))


@router.get('/blends/{blend_id}')
def blend_detail(blend_id: int, request: Request, db: Session = Depends(get_db)):
    blend = db.get(Blend, blend_id)
    if blend is None:
        return services.flash_redirect('/blends', err='Blend not found.')
    return render(request, 'blend_detail.html', blend=blend, components=component_rows(blend),
                  remaining=blend_remaining(blend),
                  common_draw=component_rows(blend)[0]['draw_ml'] if blend.components else None,
                  now=datetime.now().strftime('%Y-%m-%dT%H:%M'))


@router.post('/blends/{blend_id}/doses')
async def record_blend_dose(blend_id: int, request: Request, db: Session = Depends(get_db)):
    blend = db.get(Blend, blend_id)
    if blend is None:
        return services.flash_redirect('/blends', err='Blend not found.')
    form = await request.form()
    try:
        if blend.status != 'in_use':
            raise ValueError('This blend is not active.')
        volume = _positive(form.get('volume_ml'), 'Draw volume')
        if volume > blend_remaining(blend) + 1e-8:
            raise ValueError('Draw volume exceeds remaining blend volume.')
        when = datetime.fromisoformat(str(form.get('taken_at', '')))
        if when.tzinfo is not None:
            raise ValueError('Enter a local Eastern date and time.')
        kind = str(form.get('kind', 'dose'))
        if kind not in ('dose', 'waste'):
            raise ValueError('Invalid record type.')
        db.add(BlendDose(blend_id=blend.id, taken_at=when, volume_ml=volume,
                         kind=kind, notes=str(form.get('notes', '')).strip()))
        if volume >= blend_remaining(blend) - 1e-8:
            blend.status = 'finished'
        db.commit()
        return services.flash_redirect(f'/blends/{blend.id}', msg='Blend draw recorded.')
    except (ValueError, TypeError) as exc:
        db.rollback()
        return services.flash_redirect(f'/blends/{blend.id}', err=str(exc))
