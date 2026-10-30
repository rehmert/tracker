"""Record physical vial transfers into a blend; no dosing recommendations."""
from datetime import datetime
from math import isfinite, floor

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import services, units as U
from ..audit_helpers import record
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
    destinations = int(_positive(form.get('destination_count', '1'), 'Destination vial count'))
    if destinations > 100 or str(form.get('destination_count', '1')).strip() != str(destinations):
        raise ValueError('Destination count must be a whole number between 1 and 100.')
    capacity_raw = str(form.get('capacity_ml', '')).strip()
    capacity = _positive(capacity_raw, 'Destination capacity') if capacity_raw else None
    ids = form.getlist('source_id')
    amounts = form.getlist('transfer_amount')
    units = form.getlist('transfer_unit')
    targets = form.getlist('target_amount')
    target_units = form.getlist('target_unit')
    if not (2 <= len(ids) <= 32) or not all(len(x) == len(ids) for x in (amounts, units, targets, target_units)):
        raise ValueError('Choose between 2 and 32 source vials and complete every row.')
    if len(set(ids)) != len(ids):
        raise ValueError('Each source vial may be selected only once.')
    source_vials = [db.get(Vial, int(i)) for i in ids]
    if any(v is None or v.status not in ('sealed', 'in_use') for v in source_vials):
        raise ValueError('One or more source vials are unavailable.')
    views = services.vial_views(db, source_vials)
    transfers = []
    compound_targets = {}
    volume = diluent
    for vial, amount, unit, target, target_unit in zip(source_vials, amounts, units, targets, target_units):
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
        previous = compound_targets.get(vial.compound_id)
        if previous is not None and abs(previous - target_base) > max(1e-6, previous * 1e-6):
            raise ValueError(f'{vial.compound.name}: repeat the same total per-draw target on every source row for this peptide.')
        compound_targets[vial.compound_id] = target_base
        if vial.volume_ml:
            transferred_ml = base / vd.conc_per_ml
        else:
            raise ValueError(f'Vial #{vial.id}: reconstitute the source vial before recording a blend transfer. Use the reconstitution what-if planner first.')
        volume += transferred_ml
        transfers.append((vial, base, transferred_ml, target_base, U.parse_unit(target_unit).name))
    if volume <= 0:
        raise ValueError('Final liquid volume must exceed zero; enter the diluent volume.')
    if capacity is not None and volume / destinations > capacity + 1e-8:
        raise ValueError(f'Calculated per-vial volume {volume / destinations:g} mL exceeds destination capacity {capacity:g} mL.')
    compound_totals = {}
    for vial, base, *_ in transfers:
        compound_totals[vial.compound_id] = compound_totals.get(vial.compound_id, 0.0) + base
    draw_volumes = [target * volume / compound_totals[cid] for cid, target in compound_targets.items()]
    if any(draw > volume + 1e-8 for draw in draw_volumes):
        raise ValueError('One or more target doses exceed the blend contents.')
    if max(draw_volumes) - min(draw_volumes) > max(1e-5, max(draw_volumes) * 0.001):
        raise ValueError('Per-peptide targets require different draw volumes. Adjust transfers or targets.')
    # Each source contributes a fraction of its compound's per-draw target.
    transfers = [(v, base, ml, target * base / compound_totals[v.compound_id], unit)
                 for v, base, ml, target, unit in transfers]
    return dict(label=label, diluent=diluent, capacity=capacity, volume=volume, destinations=destinations,
                transfers=transfers, views=views, draw_ml=sum(draw_volumes)/len(draw_volumes),
                notes=str(form.get('notes', '')).strip())


def calculate_reconstitution_plan(form, db: Session):
    """Read-only maximum-complete-draw planner; never changes inventory.

    Transfer amounts are derived from the limiting available source and cartridge
    capacity. Source dilution is underdetermined: equal withdrawal is an
    illustrative allocation, not a physical preparation recommendation.
    """
    ids = form.getlist('source_id')
    targets = form.getlist('target_amount')
    target_units = form.getlist('target_unit')
    bac_inputs = form.getlist('source_bac_ml')
    allocation = str(form.get('planner_allocation', 'equal')).strip()
    if allocation not in ('manual', 'equal'):
        raise ValueError('Unknown source dilution allocation mode.')
    if not (2 <= len(ids) <= 32) or any(len(x) != len(ids) for x in (targets, target_units, bac_inputs)):
        raise ValueError('Select 2–32 sources and enter a target dose for each peptide.')
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
    views = services.vial_views(db, vials)
    rows = []
    max_destinations = int(_positive(form.get('planner_max_destinations', '1'), 'Maximum destination vials'))
    if max_destinations > 100 or str(form.get('planner_max_destinations', '1')).strip() != str(max_destinations):
        raise ValueError('Maximum destinations must be a whole number between 1 and 100.')
    draws_per_destination = floor((capacity + 1e-10) / draw)
    limits = [draws_per_destination * max_destinations]
    grouped = {}
    for vial, target, target_unit, bac_raw in zip(vials, targets, target_units, bac_inputs):
        vd = views[vial.id]
        target_base, dim = U.to_base(_positive(target, f'Target for {vial.compound.name}'), target_unit)
        if dim != vd.dim:
            raise ValueError(f'{vial.compound.name}: target unit is incompatible with its content.')
        group = grouped.setdefault(vial.compound_id, dict(target=target_base, vials=[]))
        if abs(group['target'] - target_base) > max(1e-6, target_base * 1e-6):
            raise ValueError(f'{vial.compound.name}: use the same per-draw target for each source vial of this peptide.')
        group['vials'].append((vial, bac_raw, target_unit))
    for group in grouped.values():
        available = sum(views[v.id].remaining_base for v, _, _ in group['vials'])
        limits.append(floor((available + 1e-8) / group['target']))
    count = min(limits)
    if count < 1:
        raise ValueError('Not enough source content or cartridge capacity for one complete draw.')
    final_volume = count * draw
    destination_count = (count + draws_per_destination - 1) // draws_per_destination
    destination_draws = [min(draws_per_destination, count - i * draws_per_destination) for i in range(destination_count)]
    rows = []
    # Allocate each compound's total requirement across its source vials in
    # selected order. Earlier vials are consumed before later ones.
    for group in grouped.values():
        needed = count * group['target']
        for vial, bac_raw, target_unit in group['vials']:
            base = min(needed, views[vial.id].remaining_base)
            needed = max(0.0, needed - base)
            if base <= 1e-8:
                continue
            rows.append(dict(vial=vial, target_base=group['target'],
                             target_unit=target_unit, base_unit=U.BASE_UNIT[views[vial.id].dim],
                             bac_input=bac_raw, base=base))
    total_fixed = 0.0
    for r in rows:
        vial = r['vial']
        base = r['base']
        if vial.volume_ml:
            if allocation == 'manual' and str(r['bac_input']).strip() and _positive(r['bac_input'], 'Source BAC', allow_zero=True) > 0:
                raise ValueError(f'{vial.compound.name}: already liquid; source BAC must be zero.')
            source_ml = base / views[vial.id].conc_per_ml
            bac = 0.0
            total_fixed += source_ml
        elif allocation == 'manual':
            bac = _positive(r['bac_input'], f'BAC for {vial.compound.name}')
            source_ml = bac * (base / views[vial.id].remaining_base)
            total_fixed += source_ml
        else:
            bac, source_ml = 0.0, 0.0
        r.update(bac=bac, source_ml=source_ml)
    if total_fixed > final_volume + 1e-8:
        raise ValueError('Source liquid exceeds final blend volume; use a different dilution allocation or fewer draws.')
    if allocation == 'equal':
        dry = [r for r in rows if not r['vial'].volume_ml]
        if dry:
            available = final_volume - total_fixed
            if available <= 1e-8:
                raise ValueError('Already-liquid source transfers leave no room for dry-source reconstitution.')
            per_dry = available / len(dry)
            for r in dry:
                r['source_ml'] = per_dry
                r['bac'] = per_dry * views[r['vial'].id].remaining_base / r['base']
                total_fixed += per_dry
    for r in rows:
        vial = r['vial']
        r['source_total_ml'] = vial.volume_ml if vial.volume_ml else r['bac']
        r['source_left_ml'] = max(0.0, r['source_total_ml'] - r['source_ml'])
        r['actual_per_draw'] = r['base'] / count
        r['concentration'] = r['base'] / final_volume
    return dict(rows=rows, capacity=capacity, draw=draw, volume=final_volume,
                destination_count=destination_count, destination_draws=destination_draws,
                destination_volumes=[n * draw for n in destination_draws],
                source_liquid=total_fixed, destination_bac=max(0.0, final_volume-total_fixed),
                free_capacity=destination_count * capacity-final_volume, allocation=allocation, draws=count)


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
                 f'{plan["capacity"]:.4g} mL per vial · Remaining nominal space across destinations: '
                 f'{plan["free_capacity"]:.4g} mL · '
                 f'<strong>{plan["draws"]} complete draws across {plan["destination_count"]} destination vials</strong> · Draw: <strong>{plan["draw"]:.4g} mL</strong> '
                 f'({plan["draw"]*100:.4g} U-100 units)</p>',
                 '<p><strong>Allocation:</strong> ' + ('Equal liquid withdrawal from each dry source (illustrative assumption)' if plan['allocation']=='equal' else 'Manually specified source BAC') + '</p>',
                 '<div class="scroll"><table><thead><tr><th>Peptide</th><th>Source BAC (mL)</th>'
                 '<th>Transfer content</th><th>Withdraw from source (mL)</th><th>Liquid left in source (mL)</th><th>Final concentration</th>'
                 '<th>Per draw (source share)</th></tr></thead><tbody>']
        for r in plan['rows']:
            cells = (f'{r["vial"].compound.name} · {r["vial"].label or "#" + str(r["vial"].id)}', f'{r["bac"]:.4g}', f'{U.from_base(r["base"], r["vial"].content_unit):.4g} {r["vial"].content_unit}',
                     f'{r["source_ml"]:.4g}', f'{r["source_left_ml"]:.4g}',
                     f'{r["concentration"]:.4g} {r["base_unit"]}/mL',
                     f'{U.from_base(r["actual_per_draw"],r["target_unit"]):.4g} {r["target_unit"]}')
            lines.append('<tr>' + ''.join(f'<td>{escape(str(v))}</td>' for v in cells) + '</tr>')
        lines.append('</tbody></table></div><p><strong>Destination fill plan:</strong> ' +
                     ', '.join(f'Vial {i}: {v:.4g} mL ({n} draws)' for i, (v, n) in enumerate(zip(plan['destination_volumes'], plan['destination_draws']), 1)) + '</p>'
                     f'<p>Additional BAC in destination vial: <strong>{plan["destination_bac"]:.4g} mL</strong>. '
                     'Transfer quantities are calculated to maximize complete draws within the nominal capacity. Each dry source is reconstituted before its calculated withdrawal. '
                     'Source BAC values are calculated using an equal-withdrawal assumption or supplied manually; neither establishes a suitable preparation volume.</p>'
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
                 f'Estimated full draws: <strong>{int((volume + 1e-9) / draw)}</strong> · '
                 f'Destination vials: <strong>{plan["destinations"]}</strong> · '
                 f'Volume per vial: <strong>{volume / plan["destinations"]:.4g} mL</strong></p>',
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
        destinations = plan['destinations']
        blends = []
        for index in range(destinations):
            blend = Blend(label=f'{label} ({index + 1}/{destinations})' if destinations > 1 else label,
                          final_volume_ml=volume / destinations, diluent_ml=diluent / destinations,
                          capacity_ml=capacity, notes=plan['notes'])
            db.add(blend)
            db.flush()
            blends.append(blend)
            for vial, base, transferred_ml, target_base, target_unit in transfers:
                db.add(BlendComponent(blend_id=blend.id, source_vial_id=vial.id,
                                      compound_id=vial.compound_id, transferred_base=base / destinations,
                                      transferred_ml=transferred_ml / destinations,
                                      target_dose_base=target_base, target_unit=target_unit))
        for blend in blends:
            record(db, "blend", blend.id, "create", after={"label": blend.label, "final_volume_ml": blend.final_volume_ml, "source_vial_ids": [v.id for v, *_ in transfers], "source_transfer_base": {str(v.id): base / destinations for v, base, *_ in transfers}})
        for vial, base, *_ in transfers:
            record(db, "vial", vial.id, "blend_transfer", before={"status": vial.status, "remaining_base": views[vial.id].remaining_base}, after={"transferred_base": base, "destination_blend_ids": [b.id for b in blends]})
            vial.status = 'in_use' if base < views[vial.id].remaining_base - 1e-6 else 'finished'
        db.commit()
        return services.flash_redirect(f'/blends/{blends[0].id}', msg=f'{destinations} destination vial(s) recorded; source inventory transferred.')
    except (ValueError, TypeError, U.UnitError) as exc:
        db.rollback()
        return services.flash_redirect('/blends', err=str(exc))


@router.get('/blends/{blend_id}')
def blend_detail(blend_id: int, request: Request, db: Session = Depends(get_db)):
    blend = db.get(Blend, blend_id)
    if blend is None:
        return services.flash_redirect('/blends', err='Blend not found.')
    dose_compounds = {}
    for row in component_rows(blend):
        c = row['item']
        entry = dose_compounds.setdefault(c.compound_id, dict(name=c.compound.name, unit=row['unit'], concentration=0.0))
        entry['concentration'] += row['concentration']
    return render(request, 'blend_detail.html', blend=blend, components=component_rows(blend),
                  dose_compounds=list(dose_compounds.values()),
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
        draw = BlendDose(blend_id=blend.id, taken_at=when, volume_ml=volume,
                         kind=kind, notes=str(form.get('notes', '')).strip())
        db.add(draw)
        db.flush()
        record(db, "blend", blend.id, "draw", after={"draw_id": draw.id, "kind": kind, "volume_ml": volume, "taken_at": when.isoformat()})
        if volume >= blend_remaining(blend) - 1e-8:
            blend.status = 'finished'
        db.commit()
        return services.flash_redirect(f'/blends/{blend.id}', msg='Blend draw recorded.')
    except (ValueError, TypeError) as exc:
        db.rollback()
        return services.flash_redirect(f'/blends/{blend.id}', err=str(exc))
