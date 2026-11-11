(() => {
  'use strict';

  const root = document.getElementById('recon-calculator');
  if (!root) return;

  const $ = (id) => document.getElementById(id);
  const body = $('recon-components');
  const template = $('recon-component-template');
  const status = $('recon-status');
  const results = $('recon-result');
  const initial = JSON.parse($('recon-prefill').textContent);

  let kind = 'single';
  let sequence = 0;
  let timer;
  let lastResult = null;

  const number = (v) => window.TrackerNumber563?.format(v) ?? Number(v).toLocaleString("en-US", {maximumFractionDigits:3, notation:"standard"});

  const element = (tag, className, text) => {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  };

  const rows = () => [
    ...body.querySelectorAll('.recon-component')
  ];

  const field = (row, key) =>
    row.querySelector(`[data-field="${key}"]`);

  const components = () => rows().map((row) => ({
    name: field(row, 'name').value,
    amount: field(row, 'amount').value,
    unit: field(row, 'unit').value,
  }));

  function addComponent(info = {}) {
    if (rows().length >= 8) return;

    const row = template.content.firstElementChild.cloneNode(true);

    field(row, 'name').value = info.name || '';
    field(row, 'amount').value =
      info.amount == null ? '' : info.amount;
    field(row, 'unit').value = info.unit || 'mg';

    row.querySelector('.recon-remove').addEventListener(
      'click', () => {
        if (
          rows().length <= (kind === 'single' ? 1 : 2)
        ) return;

        row.remove();
        updateLayout();
      }
    );

    body.append(row);
    updateLayout();
  }

  function syncTargetUnit() {
    const basis = $('recon-basis').value;
    const index = basis === 'total' ? 0 : Number(basis);
    const row = rows()[index];

    if (!row) return;

    const vialUnit = field(row, 'unit').value;
    const targetUnit = $('recon-target-unit');

    const mismatch =
      (vialUnit === 'IU') !== (targetUnit.value === 'IU');

    if (mismatch) {
      targetUnit.value =
        vialUnit === 'IU' ? 'IU' : vialUnit;
      $('recon-target').value = '';
    }

    $('recon-unit-hint').textContent =
      mismatch
        ? 'Unit dimension changed. Re-enter your target amount.'
        : 'Check that the target amount and selected unit refer to the same component.';
  }

  function updateBasis() {
    const select = $('recon-basis');
    const previous = select.value;
    select.replaceChildren();

    rows().forEach((row, i) => {
      const name =
        field(row, 'name').value.trim() ||
        `Component ${i + 1}`;

      select.append(
        new Option(name, String(i))
      );
    });

    if (kind === 'blend') {
      select.append(
        new Option(
          'Total blend (compatible units only)',
          'total'
        )
      );
    }

    select.value = [...select.options].some(
      (option) => option.value === previous
    ) ? previous : '0';

    const totalOption = [...select.options].find(
      (option) => option.value === 'total'
    );

    if (totalOption) {
      totalOption.disabled = new Set(rows().map(
        (row) => field(row, 'unit').value === 'IU'
          ? 'IU' : 'mass'
      )).size > 1;

      if (totalOption.disabled && select.value === 'total') {
        select.value = '0';
      }
    }

    syncTargetUnit();
  }

  function updateLayout() {
    rows().forEach((row, i) => {
      row.querySelector(
        '.recon-component-title'
      ).textContent = `Component ${i + 1}`;

      row.querySelector(
        '.recon-remove'
      ).hidden =
        kind === 'single' ||
        rows().length <= 2;
    });

    $('recon-add').hidden = kind !== 'blend';
    $('recon-add').disabled = rows().length >= 8;

    updateBasis();
    schedule();
  }

  function selectKind(next) {
    kind = next;

    if (kind === 'single') {
      rows().slice(1).forEach((row) => row.remove());
    } else if (rows().length < 2) {
      addComponent();
    }

    $('recon-method').querySelector('option[value="optimize"]').disabled =
      kind === 'blend';
    if (kind === 'blend' && $('recon-method').value === 'optimize') {
      $('recon-method').value = 'target';
      selectMethod();
    }

    root.querySelectorAll('[data-kind]').forEach(
      (button) => {
        const selected = button.dataset.kind === kind;
        button.classList.toggle('active', selected);
        button.setAttribute(
          'aria-pressed', String(selected)
        );
      }
    );

    updateLayout();
  }

  function selectMethod() {
    const method = $('recon-method').value;

    $('recon-volume-wrap').hidden =
      method === 'reverse' || method === 'optimize';

    $('recon-target-wrap').hidden =
      method === 'draw';

    $('recon-marks-wrap').hidden =
      method === 'target' || method === 'optimize';

    $('recon-optimize-wrap').hidden =
      method !== 'optimize';

    schedule();
  }

  function payload() {
    return {
      kind,
      method: $('recon-method').value,
      components: components(),
      volume_ml: $('recon-volume').value,
      vial_capacity_ml: $('recon-capacity').value,
      syringe_ml: $('recon-syringe').value,
      basis: $('recon-basis').value,
      target_amount: $('recon-target').value,
      target_unit: $('recon-target-unit').value,
      draw_units: $('recon-marks').value,
      preferred_units: $('recon-preferred').value,
      graduation_units: $('recon-graduation').value,
      volume_step_ml: $('recon-volume-step').value,
    };
  }

  function ready(data) {
    return data.components.every(
      (c) => c.amount !== '' && Number(c.amount) > 0
    ) &&
    (
      data.method === 'reverse' ||
      data.method === 'optimize' ||
      data.volume_ml !== ''
    ) &&
    (
      data.method === 'draw' ||
      data.target_amount !== ''
    ) &&
    (
      data.method === 'target' ||
      data.method === 'optimize' ||
      data.draw_units !== ''
    );
  }

  function explainCalculation(data) {
    const box = $('recon-working');
    const list = $('recon-working-list');
    list.replaceChildren();

    const add = (line) => list.append(element('li', '', line));

    if (data.method === 'optimize') {
      const c = data.recommended;

      add(`Total content: ${number(data.content)} ${data.content_unit}. Entered amount: ${number(data.target_amount)} ${data.target_unit}. Convert to compatible units before dividing.`);

      add(`Complete theoretical draws: ${data.complete_draws}; remaining compound: ${number(data.theoretical_leftover)} ${data.content_unit}. Dilution cannot remove that remainder.`);

      add(`${number(c.draw_units)} U-100 marks = ${number(c.draw_ml)} mL. Nominal final solution volume = ${number(c.nominal_final_ml)} mL.`);

      add('This is not the verified volume of diluent to add; displacement and physical handling losses are not modeled.');

    } else {
      data.components.forEach((c) => {
        add(`${c.name}: ${number(c.vial_amount)} ${c.unit} / ${number(data.final_volume_ml)} mL = ${number(c.concentration)} ${c.unit}/mL.`);

        add(`${c.name}: ${number(c.concentration)} ${c.unit}/mL x ${number(data.draw_ml)} mL = ${number(c.amount_per_draw)} ${c.unit}.`);
      });

      add(`${number(data.draw_ml)} mL x 100 = ${number(data.draw_units)} U-100 marks.`);

      add(`${number(data.final_volume_ml)} mL / ${number(data.draw_ml)} mL per draw = ${data.full_draws} complete theoretical draws (rounded down).`);
    }

    box.hidden = false;
  }

  function displayOptimization(data) {
    results.replaceChildren();

    status.textContent =
      'Nominal-volume calculation only; no inventory changed.';

    const choice = data.recommended;
    const metrics = element('div', 'recon-metrics');

    const entries = [
      [
        'Illustrative diluent volume (negligible displacement only)',
        `${number(choice.nominal_final_ml)} mL`
      ],
      [
        'Nominal final solution volume',
        `${number(choice.nominal_final_ml)} mL`
      ],
      [
        'Draw volume / U-100 markings',
        `${number(choice.draw_ml)} mL / ${number(choice.draw_units)} U`
      ],
      [
        'Complete theoretical draws',
        String(data.complete_draws)
      ],
      [
        'Theoretical compound remainder',
        `${number(data.theoretical_leftover)} ${data.content_unit}`
      ],
      [
        'Liquid remaining after full draws (theoretical)',
        `${number(choice.theoretical_leftover_ml)} mL`
      ],
    ];

    entries.forEach(([label, value]) => {
      const box = element('div', 'recon-metric');
      box.append(
        element('small', '', label),
        element('strong', '', value)
      );
      metrics.append(box);
    });

    results.append(metrics);

    results.append(element(
      'p', 'muted',
      `Vial capacity limit: ${number(data.assumed_vial_capacity_ml)} mL` +
      (data.capacity_is_default
        ? ' (default assumption; verify actual vial)'
        : '') +
      '. U-100 syringe marks are volume markings, not medication IU.'
    ));

    const scroller = element('div', 'recon-scroll');
    const table = element('table');
    const thead = element('thead');
    const headers = element('tr');

    [
      'Draw (U-100 marks)',
      'Nominal final mL',
      'Exact on selected volume grid?',
      'Nearest grid volume (mL)',
      'Amount change if rounded (%)'
    ].forEach((heading) => {
      headers.append(element('th', '', heading));
    });

    thead.append(headers);

    const tbody = element('tbody');

    data.options.forEach((option) => {
      const tr = element('tr');

      [
        number(option.draw_units),
        number(option.nominal_final_ml),
        option.matches_volume_step
          ? 'Yes'
          : 'No — approximate only',
        number(option.nearest_measurable_ml),
        option.rounding_error_pct == null
          ? 'n/a'
          : `${option.rounding_error_pct > 0 ? '+' : ''}${number(option.rounding_error_pct)}%`
      ].forEach((value) => {
        tr.append(element('td', '', value));
      });

      tbody.append(tr);
    });

    table.append(thead, tbody);
    scroller.append(table);

    results.append(
      element('h3', '', 'Alternative calculations'),
      scroller
    );

    results.append(element(
      'p', 'muted',
      'The theoretical compound remainder does not change ' +
      'when the dilution changes. Rounding an off-grid final ' +
      'volume changes the concentration.'
    ));

    data.warnings.forEach((warning) => {
      results.append(
        element('p', 'recon-message', warning)
      );
    });

    explainCalculation(data);
  }

  function display(data) {
    lastResult = data;
    $('recon-export').disabled = false;

    if (data.method === 'optimize') {
      displayOptimization(data);
      return;
    }
    results.replaceChildren();

    status.textContent =
      'Calculated from the values entered above. No records changed.';

    const metrics = element('div', 'recon-metrics');
    const entries = [
      [
        'Nominal final volume',
        `${number(data.final_volume_ml)} mL`
      ],
      [
        'Calculated draw volume',
        `${number(data.draw_ml)} mL`
      ],
      [
        'U-100 syringe marks',
        `${number(data.draw_units)} U`
      ],
      [
        'Theoretical complete draws',
        String(data.full_draws)
      ],
    ];

    entries.forEach(([label, value]) => {
      const box = element('div', 'recon-metric');

      box.append(
        element('small', '', label),
        element('strong', '', value)
      );

      metrics.append(box);
    });

    results.append(metrics);

    const bar = element('div', 'recon-meter');

    bar.setAttribute(
      'aria-invalid',
      String(!data.fits_syringe)
    );

    const fill = element('div', 'recon-meter-fill');

    fill.style.width = `${
      Math.max(
        0,
        Math.min(
          100,
          data.draw_ml / data.syringe_ml * 100
        )
      )
    }%`;

    bar.append(fill);

    results.append(
      element(
        'p',
        'muted',
        `Proportion of ${number(data.syringe_ml)} mL syringe capacity`
      ),
      bar
    );

    const scale = element('div', 'recon-scale-labels');

    [0, 0.25, 0.5, 0.75, 1].forEach((fraction) => {
      scale.append(
        element('span', '',
          number(data.syringe_ml * 100 * fraction))
      );
    });

    results.append(scale);

    const scroller = element('div', 'recon-scroll');
    const table = element('table');
    const thead = element('thead');

    const headings = [
      'Component',
      'Vial content',
      'Concentration',
      'Per 1 U-100 mark',
      'In calculated draw',
    ];

    const trh = element('tr');

    headings.forEach(
      (heading) => trh.append(
        element('th', '', heading)
      )
    );

    thead.append(trh);

    const tbody = element('tbody');

    data.components.forEach((item) => {
      const tr = element('tr');

      [
        item.name,
        `${number(item.vial_amount)} ${item.unit}`,
        `${number(item.concentration)} ${item.unit}/mL`,
        `${number(item.per_mark)} ${item.unit}`,
        `${number(item.amount_per_draw)} ${item.unit}`,
      ].forEach((value) => {
        tr.append(
          element('td', '', value)
        );
      });

      tbody.append(tr);
    });

    table.append(thead, tbody);
    scroller.append(table);
    results.append(scroller);

    data.warnings.forEach((warning) => {
      results.append(
        element(
          'p',
          'recon-message recon-error',
          warning
        )
      );
    });

    if (data.method === 'reverse') {
      results.append(
        element(
          'p',
          'recon-message',
          'Reverse calculation gives nominal final solution volume, ' +
          'not the exact volume of water to add.'
        )
      );
    }

    explainCalculation(data);
  }

  function schedule() {
    lastResult = null;
    $('recon-export').disabled = true;

    $('recon-working').hidden = true;
    $('recon-working-list').replaceChildren();
    clearTimeout(timer);
    sequence += 1;

    const current = sequence;
    const data = payload();

    if (!ready(data)) {
      results.replaceChildren();

      status.textContent =
        'Enter all required vial details and a target or draw size.';

      return;
    }

    status.textContent = 'Calculating…';

    timer = setTimeout(async () => {
      try {
        const response = await fetch(
          '/reconstitution-calculator/preview',
          {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
            },
            body: JSON.stringify(data),
            cache: 'no-store',
          }
        );

        const result = await response.json();

        if (current !== sequence) return;

        if (!response.ok) {
          results.replaceChildren();
          status.textContent =
            `Cannot calculate: ${result.error || 'Invalid input'}`;
          return;
        }

        display(result);

      } catch (error) {
        if (current === sequence) {
          results.replaceChildren();
          status.textContent =
            'Unable to calculate. Check the application connection and retry.';
        }
      }
    }, 160);
  }

  root.querySelectorAll('[data-kind]').forEach(
    (button) => button.addEventListener(
      'click',
      () => selectKind(button.dataset.kind)
    )
  );

  $('recon-add').addEventListener(
    'click', () => addComponent()
  );

  $('recon-export').addEventListener('click', () => {
    if (!lastResult) return;

    const data = lastResult;

    const lines = [
      'Tracker — Reconstitution arithmetic preview',
      'Read-only calculation; not a dose or preparation recommendation.',
      `Calculation mode: ${data.method}`,
      `Vial type: ${data.kind}`,
      ''
    ];

    if (data.method === 'optimize') {
      const option = data.recommended;

      lines.push(
        `Content: ${data.content} ${data.content_unit}`,
        `Entered amount: ${data.target_amount} ${data.target_unit}`,
        `Complete theoretical draws: ${data.complete_draws}`,
        `Theoretical compound remainder: ${data.theoretical_leftover} ${data.content_unit}`,
        `Nominal final volume: ${option.nominal_final_ml} mL`,
        `U-100 markings: ${option.draw_units}`
      );

    } else {
      lines.push(
        `Nominal final volume: ${data.final_volume_ml} mL`,
        `Calculated draw: ${data.draw_ml} mL`,
        `U-100 markings: ${data.draw_units}`,
        `Complete theoretical draws: ${data.full_draws}`
      );

      data.components.forEach((item) => lines.push(
        `${item.name}: ${item.vial_amount} ${item.unit} total; ` +
        `${item.concentration} ${item.unit}/mL; ` +
        `${item.amount_per_draw} ${item.unit} per draw`
      ));
    }

    lines.push(
      '',
      'Warnings:',
      ...(data.warnings || []),
      'Nominal final volume is not an exact diluent-addition instruction.',
      'No inventory or dose records were changed.'
    );

    const blob = new Blob(
      [lines.join('\n') + '\n'],
      {type: 'text/plain;charset=utf-8'}
    );

    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');

    link.href = url;
    link.download = 'tracker-reconstitution-preview.txt';

    document.body.append(link);
    link.click();
    link.remove();

    setTimeout(() => URL.revokeObjectURL(url), 2000);
  });

  body.addEventListener('input', (event) => {
    if (event.target.dataset.field === 'name') {
      updateBasis();
    }
    schedule();
  });

  body.addEventListener('change', (event) => {
    if (event.target.dataset.field === 'unit') {
      updateBasis();
    }
    schedule();
  });

  $('recon-basis').addEventListener('change', () => {
    syncTargetUnit();
    schedule();
  });

  [
    'recon-method',
    'recon-volume',
    'recon-target',
    'recon-target-unit',
    'recon-basis',
    'recon-syringe',
    'recon-capacity',
    'recon-marks',
    'recon-preferred',
    'recon-graduation',
    'recon-volume-step',
  ].forEach((id) => {
    $(id).addEventListener(
      'input',
      id === 'recon-method'
        ? selectMethod
        : schedule
    );

    $(id).addEventListener(
      'change',
      id === 'recon-method'
        ? selectMethod
        : schedule
    );
  });

  addComponent(initial || {});

  if (initial && initial.volume_ml != null) {
    $('recon-volume').value = initial.volume_ml;
  }

  selectMethod();
})();
