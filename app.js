(() => {
  'use strict';

  const state = { data: null, geo: null, aggregateGeo: null, employment: null, transit: null, property: null, currentId: 'westchester-county', theme: 'population' };
  const $ = (selector) => document.querySelector(selector);
  const $$ = (selector) => [...document.querySelectorAll(selector)];

  const escapeHtml = (value) => String(value ?? '').replace(/[&<>"]/g, (char) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[char]));
  const number = new Intl.NumberFormat('en-US', { maximumFractionDigits: 0 });
  const oneDecimal = new Intl.NumberFormat('en-US', { minimumFractionDigits: 1, maximumFractionDigits: 1 });
  const currency = new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 });

  function metricValue(metric, kind = 'number') {
    if (!metric || metric.estimate == null) return 'Not available';
    if (kind === 'percent') return `${oneDecimal.format(metric.estimate)}%`;
    if (kind === 'currency') return currency.format(metric.estimate);
    return number.format(metric.estimate);
  }

  function moeText(metric, kind = 'number') {
    if (!metric || metric.moe == null) return 'MOE not available';
    const value = kind === 'percent' ? `${oneDecimal.format(metric.moe)} pts` : kind === 'currency' ? currency.format(metric.moe) : number.format(metric.moe);
    return `±${value} at 90% confidence`;
  }

  function fact(label, metric, kind) {
    return `<article class="fact"><span class="fact-label">${escapeHtml(label)}</span><strong class="fact-value">${metricValue(metric, kind)}</strong><span class="moe">${moeText(metric, kind)}</span></article>`;
  }

  function barRows(items, max = 100, suffix = '%') {
    return `<div class="bar-list" role="list">${items.map(({ label, metric, value }) => {
      const estimate = value ?? metric?.estimate;
      const width = estimate == null ? 0 : Math.max(0, Math.min(100, estimate / max * 100));
      const display = estimate == null ? 'N/A' : suffix === '%' ? `${oneDecimal.format(estimate)}%` : suffix === 'acres' ? `${number.format(estimate)} ac` : number.format(estimate);
      const uncertainty = metric ? moeText(metric, suffix === '%' ? 'percent' : 'number') : 'County GIS observation; no sampling MOE';
      return `<div class="bar-row" role="listitem" aria-label="${escapeHtml(`${label}: ${display}; ${uncertainty}`)}"><span>${escapeHtml(label)}</span><span class="bar-track" aria-hidden="true"><span class="bar-fill" style="width:${width}%"></span></span><strong class="bar-value">${display}</strong><span class="bar-moe">${escapeHtml(uncertainty)}</span></div>`;
    }).join('')}</div>`;
  }

  function compareNote(profile, path, kind = 'percent') {
    if (profile.id === 'westchester-county') return 'County estimate shown. Select a municipality to compare it with the County.';
    const current = path(profile);
    const county = path(getProfile('westchester-county'));
    if (!current || !county || current.estimate == null || county.estimate == null) return 'County comparison unavailable.';
    const delta = current.estimate - county.estimate;
    const direction = delta === 0 ? 'the same as' : delta > 0 ? 'above' : 'below';
    const amount = kind === 'currency' ? currency.format(Math.abs(delta)) : `${oneDecimal.format(Math.abs(delta))} percentage points`;
    return `${amount} ${direction} the Westchester County estimate.`;
  }

  function getProfile(id) {
    return state.data.profiles.find((profile) => profile.id === id) || state.data.profiles[0];
  }

  function themeRoute(profileId = state.currentId, theme = state.theme) {
    return `#/profile/${profileId}/theme/${theme}`;
  }

  function renderKeyFacts(profile) {
    const m = profile.metrics;
    $('#keyFacts').innerHTML = [
      fact('Population', m.population.total),
      fact('Median household income', m.income.median_household, 'currency'),
      fact('Housing units', m.housing.units),
      fact('Public transit share', m.commute.public_transit_pct, 'percent'),
    ].join('');
  }

  function renderPopulation(profile) {
    const p = profile.metrics.population;
    const i = profile.metrics.income;
    return `<div class="section-grid">
      <article class="data-card card">
        <h3>Age profile</h3><p>Shares of the total population. MOEs are available on hover.</p>
        ${barRows([{ label: 'Under age 18', metric: p.under_18_pct }, { label: 'Age 65 and older', metric: p.age_65_plus_pct }])}
      </article>
      <article class="data-card card">
        <h3>Race and ethnicity</h3><p>Race-alone categories and Hispanic/Latino ethnicity overlap; bars are not components of one total.</p>
        ${barRows([
          { label: 'White alone', metric: p.white_alone_pct }, { label: 'Black alone', metric: p.black_alone_pct },
          { label: 'Asian alone', metric: p.asian_alone_pct }, { label: 'Hispanic or Latino', metric: p.hispanic_latino_pct },
        ])}
      </article>
      <article class="data-card card full">
        <h3>Household resources</h3><p>Income values are nominal 2024 ACS inflation-adjusted dollars. Household, family, and person universes differ.</p>
        <div class="inline-stats">
          <div class="inline-stat"><strong>${metricValue(i.median_household, 'currency')}</strong><span>Median household income · ${moeText(i.median_household, 'currency')}</span></div>
          <div class="inline-stat"><strong>${metricValue(i.median_family, 'currency')}</strong><span>Median family income · ${moeText(i.median_family, 'currency')}</span></div>
          <div class="inline-stat"><strong>${metricValue(i.per_capita, 'currency')}</strong><span>Per-capita income · ${moeText(i.per_capita, 'currency')}</span></div>
        </div>
        <p class="compare">${escapeHtml(compareNote(profile, (x) => x.metrics.income.median_household, 'currency'))}</p>
      </article>
    </div>`;
  }

  function renderHousing(profile) {
    const h = profile.metrics.housing;
    const structure = Object.entries(h.structure_share_pct).map(([label, metric]) => ({ label, metric }));
    return `<div class="section-grid">
      <article class="data-card card">
        <h3>Occupancy and tenure</h3><p>Vacancy uses all housing units; tenure uses occupied units.</p>
        ${barRows([{ label: 'Owner occupied', metric: h.owner_occupied_pct }, { label: 'Renter occupied', metric: h.renter_occupied_pct }, { label: 'Vacant', metric: h.vacancy_rate_pct }])}
      </article>
      <article class="data-card card">
        <h3>Housing costs</h3><p>Gross rent includes contract rent plus tenant-paid utilities. Cost burden covers cash-rent households with computed income.</p>
        <div class="inline-stats">
          <div class="inline-stat"><strong>${metricValue(h.median_home_value, 'currency')}</strong><span>Median owner-occupied home value</span></div>
          <div class="inline-stat"><strong>${metricValue(h.median_gross_rent, 'currency')}</strong><span>Median monthly gross rent</span></div>
          <div class="inline-stat"><strong>${metricValue(h.rent_burden_30_plus_pct, 'percent')}</strong><span>Renters paying 30%+ of income</span></div>
        </div>
      </article>
      <article class="data-card card full">
        <h3>Units in structure</h3><p>ACS housing-unit estimates describe physical structure, not parcel land use.</p>
        ${barRows(structure)}
      </article>
    </div>`;
  }

  function renderCommute(profile) {
    const c = profile.metrics.commute;
    return `<div class="section-grid">
      <article class="data-card card full">
        <h3>How residents get to work</h3><p>Universe: workers age 16 and over (ACS B08301). Work from home is included; these are resident worker modes, not trips observed on the transportation network.</p>
        ${barRows([
          { label: 'Drove alone', metric: c.drove_alone_pct }, { label: 'Carpooled', metric: c.carpooled_pct },
          { label: 'Public transportation', metric: c.public_transit_pct }, { label: 'Walked', metric: c.walked_pct },
          { label: 'Bicycle', metric: c.bicycle_pct }, { label: 'Other means', metric: c.other_means_pct },
          { label: 'Worked from home', metric: c.worked_from_home_pct },
        ])}
        <p class="compare">${escapeHtml(compareNote(profile, (x) => x.metrics.commute.public_transit_pct))}</p>
      </article>
      <aside class="note full"><strong>Interpret carefully.</strong> ACS commute mode is based on a worker's usual mode during the survey reference period. It does not measure daily ridership, peak-hour station use, transit frequency, or where jobs are located.</aside>
    </div>`;
  }

  function renderLandUse(profile) {
    const land = profile.metrics.land_use;
    const max = Math.max(...land.categories.map((item) => item.acres), 1);
    return `<div class="section-grid">
      <article class="data-card card full">
        <h3>Assessment parcel acres by primary property class</h3><p>Westchester County GIS 2025 tax parcels. Duplicate geometry records are excluded. This is assessed use—not zoning or land cover.</p>
        ${barRows(land.categories.map((item) => ({ label: item.category, value: item.acres })), max, 'acres')}
        <div class="inline-stats" style="margin-top:1rem">
          <div class="inline-stat"><strong>${number.format(land.assessor_parcel_acres)}</strong><span>Mapped assessment-parcel acres</span></div>
          <div class="inline-stat"><strong>${number.format(land.parcel_records)}</strong><span>Non-duplicate parcel records</span></div>
          <div class="inline-stat"><strong>${land.categories.length}</strong><span>Observed broad use classes</span></div>
        </div>
      </article>
      <aside class="note full"><strong>Not a municipal-area denominator.</strong> Parcel acreage omits water and rights-of-way, and mixed-use parcels have one primary assessment class. Percent shares use mapped, non-duplicate parcel acres—not total municipal land acres.</aside>
    </div>`;
  }

  function renderEconomy(profile) {
    const economy = state.data.metadata.economic_context;
    const cbp = economy.business_patterns;
    const cpi = economy.cpi;
    const latest = cpi.latest;
    const observations = cpi.observations.slice(0, 12);
    const contextNote = profile.id === 'westchester-county'
      ? 'These observations describe Westchester County and the New York metropolitan price area.'
      : `${profile.name} does not have a directly published County Business Patterns observation. County and regional context is shown without allocating values to the municipality.`;
    return `<div class="section-grid">
      <aside class="note full"><strong>Geography matters.</strong> ${escapeHtml(contextNote)}</aside>
      <article class="data-card card">
        <h3>County business activity</h3>
        <p>U.S. Census Bureau County Business Patterns, ${cbp.vintage}. Payroll is published in thousands of dollars.</p>
        <div class="inline-stats">
          <div class="inline-stat"><strong>${number.format(cbp.establishments)}</strong><span>Employer establishments</span></div>
          <div class="inline-stat"><strong>${number.format(cbp.employees)}</strong><span>Employees</span></div>
          <div class="inline-stat"><strong>${currency.format(cbp.annual_payroll_thousands * 1000)}</strong><span>Annual payroll</span></div>
        </div>
        <p class="compare">${escapeHtml(cbp.limitation)} <a href="${escapeHtml(cbp.source)}" target="_blank" rel="noreferrer">Census CBP source</a></p>
      </article>
      <article class="data-card card">
        <h3>Regional inflation context</h3>
        <p>${escapeHtml(cpi.series_name)}. This index supports constant-dollar comparisons; it is not a local cost-of-living score.</p>
        <div class="inline-stats">
          <div class="inline-stat"><strong>${oneDecimal.format(latest.value)}</strong><span>${escapeHtml(latest.period_name)} ${latest.year} index</span></div>
          <div class="inline-stat"><strong>${latest.year_over_year_pct == null ? 'N/A' : `${oneDecimal.format(latest.year_over_year_pct)}%`}</strong><span>Year-over-year change</span></div>
          <div class="inline-stat"><strong>1982–84</strong><span>Index base = 100</span></div>
        </div>
        <p class="compare">${escapeHtml(cpi.limitation)} <a href="${escapeHtml(cpi.source)}" target="_blank" rel="noreferrer">BLS source and history</a></p>
      </article>
      <article class="data-card card full">
        <h3>Recent CPI observations</h3>
        <p>Newest available numeric observations. A missing month is not interpolated.</p>
        <table class="data-table"><caption class="sr-only">Recent New York metropolitan CPI-U observations</caption><thead><tr><th scope="col">Period</th><th scope="col">Series</th><th scope="col">Index</th></tr></thead><tbody>${observations.map((item) => `<tr><td>${escapeHtml(item.period_name)} ${item.year}</td><td>${escapeHtml(cpi.series_id)}</td><td>${oneDecimal.format(item.value)}</td></tr>`).join('')}</tbody></table>
      </article>
    </div>`;
  }

  function statusClass(status) {
    return `status-${status.replace(/—/g, '-').replace(/[^a-z]+/gi, '-').replace(/^-|-$/g, '').toLowerCase()}`;
  }

  function requirementRows() {
    return state.data.metadata.requirements.map((item) => `<div class="requirement">
      <span class="requirement-id">${escapeHtml(item.id)}</span>
      <span><strong>${escapeHtml(item.title)}</strong><span class="requirement-note">${escapeHtml(item.note)}</span></span>
      <span class="status-badge ${statusClass(item.status)}">${escapeHtml(item.status)}</span>
    </div>`).join('');
  }

  function renderMethods(profile) {
    const md = state.data.metadata;
    const boundaryMetadata = profile.map_role === 'aggregate overlay' ? md.aggregate_boundaries : md.boundaries;
    return `<div class="section-grid">
      <article class="data-card card">
        <h3>ACS estimates</h3>
        <p>${escapeHtml(md.acs.dataset)} · ${md.acs.vintage} vintage · ${escapeHtml(md.acs.confidence_level)}.</p>
        <ul class="source-list">
          <li>Profile geography: ${escapeHtml(profile.census_geography)}</li>
          <li>Census name: ${escapeHtml(profile.census_name)}</li>
          <li>GEOID: <code>${escapeHtml(profile.census_geoid)}</code></li>
          <li>Dollar basis: ${escapeHtml(md.acs.dollar_basis)}</li>
          <li><a href="${escapeHtml(md.acs.source)}" target="_blank" rel="noreferrer">Census API dataset</a></li>
        </ul>
      </article>
      <article class="data-card card">
        <h3>Boundary and parcel GIS</h3><p>${escapeHtml(md.land_use.definition)}</p>
        <ul class="source-list">
          <li>Boundary CRS: ${escapeHtml(boundaryMetadata.crs)}</li>
          <li>${profile.map_role === 'aggregate overlay' ? '2024 Census TIGER/Line legal town overlay' : `${md.boundaries.source_feature_rows} County source parts → ${md.boundaries.unique_profile_communities} unique map communities`}</li>
          <li>2025 parcel roll and spatial vintage</li>
          <li><a href="${escapeHtml(boundaryMetadata.source)}" target="_blank" rel="noreferrer">${profile.map_role === 'aggregate overlay' ? 'TIGER/Line county subdivision source' : 'Municipal Boundaries service'}</a></li>
          <li><a href="${escapeHtml(md.land_use.source)}" target="_blank" rel="noreferrer">Tax Parcels service</a></li>
        </ul>
      </article>
      <article class="data-card card full">
        <h3>Requirements coverage · GR-01 through GR-16</h3>
        <p>Recovered from the pre-workshop requirements traceability matrix. Status reflects this prototype—not a production acceptance decision. Workshop priority and phase remain unconfirmed.</p>
        <div class="requirement-list">${requirementRows()}</div>
      </article>
      <article class="data-card card full">
        <h3>External data gaps</h3><p>Unavailable data are not represented with proxy metrics. Located-but-not-integrated sources are distinguished in the checklist above.</p>
        <ul class="gap-list">${md.known_gaps.map((gap) => `<li>${escapeHtml(gap)}</li>`).join('')}</ul>
      </article>
      <article class="data-card card full">
        <h3>43 non-overlapping map geographies + 2 town aggregates</h3>
        <p>The selector has all 45 municipal-government profiles: the County GIS layer's 43 non-overlapping geographies plus separate overlapping Town of Pelham and Town of Rye aggregate profiles. Their official Census TIGER/Line county-subdivision boundaries appear as overlays and do not replace or inflate the 43-feature base map.</p>
        <p>Town of Pelham overlaps the Pelham and Pelham Manor village profiles. Town of Rye is a noncontiguous geography overlapping Port Chester, Rye Brook, and the Rye Neck section of Mamaroneck Village; Rye City is a separate city and is not in Rye town. Never sum a town aggregate with its overlapping villages.</p>
        <p>New York State reports 48 city, town, and village corporations. The dashboard has 45 municipal-government profiles because Harrison, Mount Kisco, and Scarsdale are coterminous town-villages with one combined government and are accurately represented once.</p>
        <ul class="source-list">
          <li><a href="https://www.ny.gov/counties/westchester" target="_blank" rel="noreferrer">New York State Westchester overview</a></li>
          <li><a href="https://www.westchestercountyny.gov/online-data" target="_blank" rel="noreferrer">Westchester County city, town, and village list</a></li>
          <li><a href="https://www.ryetownny.gov/departments/facts_history.php" target="_blank" rel="noreferrer">Town of Rye geography description</a></li>
        </ul>
      </article>
      <aside class="note full"><strong>Do not aggregate profile rows.</strong> Village Census-place estimates overlap town county-subdivision estimates. Use the separately queried County profile for the County total.</aside>
    </div>`;
  }

  // ---------------------------------------------------------------------
  // External datasets integrated from verified public sources.
  // Each is loaded independently and tolerantly: a missing collector output
  // degrades one tab with a clear message; it never breaks the dashboard.
  // ---------------------------------------------------------------------

  function unavailable(title, detail) {
    return `<div class="section-grid"><aside class="note full"><strong>${escapeHtml(title)} is not loaded.</strong> ${escapeHtml(detail)}</aside></div>`;
  }

  function sourceNote(label, url, detail) {
    if (!url) return `<p class="compare">${escapeHtml(detail)}</p>`;
    return `<p class="compare">${escapeHtml(detail)} <a href="${escapeHtml(url)}" target="_blank" rel="noreferrer">${escapeHtml(label)}</a></p>`;
  }

  // Bars for administrative counts rather than survey estimates. The existing
  // barRows() helper hardcodes a GIS uncertainty caption, which would be wrong
  // for BLS / transit / assessment-roll figures, so provenance is passed in.
  function countRows(items, max, note, format = number) {
    return `<div class="bar-list" role="list">${items.map((item) => {
      const value = item.value;
      const width = value == null ? 0 : Math.max(0, Math.min(100, value / max * 100));
      const display = value == null ? 'N/A' : format.format(value);
      return `<div class="bar-row" role="listitem" aria-label="${escapeHtml(`${item.label}: ${display}. ${note}`)}"><span>${escapeHtml(item.label)}</span><span class="bar-track" aria-hidden="true"><span class="bar-fill" style="width:${width}%"></span></span><strong class="bar-value">${display}</strong><span class="bar-moe">${escapeHtml(note)}</span></div>`;
    }).join('')}</div>`;
  }

  function renderEmployment(profile) {
    const qcew = state.employment;
    if (!qcew) return unavailable('BLS QCEW employment', 'Run scripts/run_collectors.sh to build data/employment/qcew_westchester.json.');
    const total = qcew.latest_total_covered;
    const ownership = Object.entries(qcew.latest_ownership);
    const industries = qcew.latest_industries.slice(0, 14);
    const maxIndustry = Math.max(...industries.map((item) => item.employment), 1);
    const contextNote = profile.id === 'westchester-county'
      ? 'These figures describe Westchester County as a whole.'
      : `QCEW is published at county granularity, so no Westchester municipality has its own QCEW record. County figures are shown as context and are not allocated to ${profile.name}.`;
    return `<div class="section-grid">
      <aside class="note full"><strong>County geography.</strong> ${escapeHtml(contextNote)}</aside>
      <article class="data-card card full">
        <h3>Covered employment and wages</h3>
        <p>U.S. Bureau of Labor Statistics Quarterly Census of Employment and Wages, ${escapeHtml(qcew.latest_period)}. These are administrative counts drawn from unemployment-insurance filings, not survey estimates, so no margin of error applies.</p>
        <div class="inline-stats">
          <div class="inline-stat"><strong>${number.format(total.employment)}</strong><span>Total covered jobs</span></div>
          <div class="inline-stat"><strong>${number.format(total.establishments)}</strong><span>Reporting establishments</span></div>
          <div class="inline-stat"><strong>${currency.format(total.avg_weekly_wage_usd)}</strong><span>Average weekly wage</span></div>
        </div>
        ${sourceNote('BLS QCEW source', qcew.source_url, qcew.granularity_note)}
      </article>
      <article class="data-card card">
        <h3>Ownership split</h3><p>Jobs and wages by ownership sector in the latest period.</p>
        <table class="data-table"><caption class="sr-only">Westchester County employment by ownership</caption><thead><tr><th scope="col">Ownership</th><th scope="col">Estab.</th><th scope="col">Jobs</th><th scope="col">Avg weekly wage</th></tr></thead><tbody>${ownership.map(([name, values]) => `<tr><td>${escapeHtml(name)}</td><td>${number.format(values.establishments)}</td><td>${number.format(values.employment)}</td><td>${currency.format(values.avg_weekly_wage_usd)}</td></tr>`).join('')}</tbody></table>
      </article>
      <article class="data-card card">
        <h3>Largest private sectors</h3><p>NAICS 2-digit sectors, private ownership only. Labels are BLS standard sector names.</p>
        ${countRows(industries.map((item) => ({ label: item.label, value: item.employment })), maxIndustry, 'Administrative count · no sampling MOE')}
      </article>
      <aside class="note full"><strong>Not an employer list.</strong> QCEW publishes industry totals, never named employers. Establishment-level figures are confidential under BLS disclosure rules, so this tab cannot identify individual employers or their addresses.</aside>
    </div>`;
  }

  function renderTransit(profile) {
    const gtfs = state.transit;
    if (!gtfs) return unavailable('Metro-North GTFS service frequency', 'Run scripts/run_collectors.sh to build data/gtfs/mnr_station_frequency.json.');
    const munis = gtfs.municipalities;
    const method = `<article class="data-card card full"><h3>Method and limits</h3><p>${escapeHtml(gtfs.method_note)}</p><ul class="source-list"><li>Feed: <a href="${escapeHtml(gtfs.source)}" target="_blank" rel="noreferrer">MTA Metro-North GTFS</a></li><li>Service date analysed: ${escapeHtml(gtfs.service_date_used)}</li><li>Active weekday service IDs: ${number.format(gtfs.active_service_ids)} · active trips: ${number.format(gtfs.active_trips)}</li><li>Stations matched to a Westchester municipality: ${number.format(gtfs.stations_matched_to_municipality)} of ${number.format(gtfs.total_stations_in_feed)} · outside the county (e.g. NYC, Connecticut): ${number.format(gtfs.stations_outside_westchester)}</li></ul></article>`;

    if (profile.id !== 'westchester-county' && !munis[profile.name]) {
      return `<div class="section-grid">
        <aside class="note full"><strong>No Metro-North station inside ${escapeHtml(profile.name)}.</strong> The ${escapeHtml(gtfs.service_date_used)} feed contains no stop within this municipality's boundary. This is not a statement about rail access — residents may still reach neighbouring stations, and a stop assigned to one municipality can serve others.</aside>
        ${method}
      </div>`;
    }

    const rows = profile.id === 'westchester-county'
      ? Object.entries(munis).sort((a, b) => b[1].weekday_scheduled_calls - a[1].weekday_scheduled_calls)
      : [[profile.name, munis[profile.name]]];
    const maxCalls = Math.max(...rows.map(([, values]) => values.weekday_scheduled_calls), 1);
    const totalCalls = Object.values(munis).reduce((sum, values) => sum + values.weekday_scheduled_calls, 0);
    const totalStations = Object.values(munis).reduce((sum, values) => sum + values.stations, 0);
    const isCounty = profile.id === 'westchester-county';
    const stations = rows.flatMap(([name, values]) => values.station_names.map((station) => ({ name, station })));

    return `<div class="section-grid">
      <aside class="note full"><strong>Scheduled service, not observed ridership.</strong> ${isCounty ? 'Counts cover all Westchester municipalities with Metro-North service.' : `Counts cover stations inside ${escapeHtml(profile.name)} only.`} This measures timetabled station calls on one representative weekday. It is not passenger boardings, and it excludes bus, subway, and Amtrak service.</aside>
      <article class="data-card card full">
        <h3>Scheduled weekday station calls</h3><p>Metro-North railroad only. A station call is one scheduled train arrival at that station.</p>
        <div class="inline-stats">
          <div class="inline-stat"><strong>${number.format(isCounty ? totalStations : rows[0][1].stations)}</strong><span>Stations in ${isCounty ? 'Westchester' : escapeHtml(profile.name)}</span></div>
          <div class="inline-stat"><strong>${number.format(isCounty ? rows.length : rows[0][1].weekday_scheduled_calls)}</strong><span>${isCounty ? 'Municipalities with service' : 'Scheduled weekday calls'}</span></div>
          <div class="inline-stat"><strong>${number.format(isCounty ? totalCalls : rows[0][1].stations)}</strong><span>${isCounty ? 'Total scheduled calls' : 'Stations'}</span></div>
        </div>
      </article>
      <article class="data-card card full">
        <h3>${isCounty ? 'Service by municipality' : `Stations in ${escapeHtml(profile.name)}`}</h3>
        <p>${isCounty ? 'All 31 Westchester municipalities with at least one Metro-North station.' : 'Station names as published in the feed.'}</p>
        ${countRows(rows.map(([name, values]) => ({ label: name, value: values.weekday_scheduled_calls })), maxCalls, 'Scheduled weekday calls · administrative count')}
      </article>
      <article class="data-card card full">
        <h3>Station detail</h3>
        <table class="data-table"><caption class="sr-only">Metro-North stations and scheduled weekday calls</caption><thead><tr><th scope="col">Municipality</th><th scope="col">Station</th></tr></thead><tbody>${stations.map((row) => `<tr><td>${escapeHtml(row.name)}</td><td>${escapeHtml(row.station)}</td></tr>`).join('')}</tbody></table>
      </article>
      ${method}
    </div>`;
  }

  // The ORPTS roll reports taxing municipalities (towns and cities), not every
  // village, so there is no single "Westchester County" row. The County view is
  // the sum of the municipal records actually present, assembled here.
  function countyPropertyEntry(munis) {
    const counts = {};
    const classes = new Map();
    let multifamily = 0;
    for (const entry of Object.values(munis)) {
      for (const [field, value] of Object.entries(entry.parcel_counts)) {
        if (typeof value !== 'number') continue;
        counts[field] = (counts[field] || 0) + value;
      }
      for (const item of entry.property_classes) {
        const prev = classes.get(item.class) || {
          class: item.class, description: item.description, parcels: 0,
          total_market_value_usd: 0, is_multifamily: item.is_multifamily,
        };
        prev.parcels += item.parcels;
        prev.total_market_value_usd += item.total_market_value_usd || 0;
        classes.set(item.class, prev);
      }
      multifamily += entry.multifamily_parcels || 0;
    }
    const total = counts.total_parcel_count || 0;
    return {
      parcel_counts: counts,
      property_classes: [...classes.values()].sort((a, b) => b.parcels - a.parcels),
      multifamily_parcels: multifamily,
      multifamily_share_pct: total ? Number((100 * multifamily / total).toFixed(2)) : null,
      municipal_records_summed: Object.keys(munis).length,
    };
  }

  function renderProperty(profile) {
    const prop = state.property;
    if (!prop) return unavailable('NYS ORPTS property inventory', 'Run scripts/run_collectors.sh to build data/parcels/nyopendata_property_inventory.json.');
    const munis = prop.municipalities;
    const isCounty = profile.id === 'westchester-county';
    const entry = isCounty ? countyPropertyEntry(munis) : munis[profile.name];

    if (!entry) {
      return `<div class="section-grid">
        <aside class="note full"><strong>No ORPTS assessment-roll record matched ${escapeHtml(profile.name)}.</strong> The ${escapeHtml(prop.roll_year)} roll carries ${number.format(prop.municipalities_in_source)} Westchester municipal records, which cover the county's towns and cities. Villages are assessed within their town and do not appear as separate roll entries; a coterminous town-village is reported under a single name.</aside>
        ${propertyMethod(prop)}
      </div>`;
    }

    const counts = entry.parcel_counts;
    const classes = entry.property_classes.slice(0, 12);
    const maxClass = Math.max(...classes.map((item) => item.parcels), 1);
    const broadUse = [
      ['Agricultural', counts.broad_use_100_agricultural_property_count],
      ['Residential', counts.broad_use_200_residential_property_count],
      ['Vacant land', counts.broad_use_300_vacant_land_property_count],
      ['Commercial', counts.broad_use_400_commercial_property_count],
      ['Recreation', counts.broad_use_500_recreation_property_count],
      ['Community service', counts.broad_use_600_community_service_property_count],
      ['Industrial', counts.broad_use_700_industrial_property_count],
      ['Public service', counts.broad_use_800_public_service_property_count],
      ['Forest & conservation', counts.broad_use_900_forest_and_conservation_property_count],
    ].filter(([, value]) => value != null);
    const maxUse = Math.max(...broadUse.map(([, value]) => value), 1);
    return `<div class="section-grid">
      <aside class="note full"><strong>Assessment roll, not a housing survey.</strong> Figures are parcel counts from the ${escapeHtml(prop.roll_year)} NYS ORPTS roll for ${isCounty ? 'Westchester municipalities' : escapeHtml(profile.name)}. A parcel is a taxing unit, not a dwelling: one parcel may contain many units, and condominium units are frequently assessed as a single parcel. This does not count housing units.</aside>
      <article class="data-card card full">
        <h3>Parcels by broad use class</h3><p>First digit of the NYS property-class code. Every parcel has exactly one primary class, so these categories sum to the municipal total.</p>
        ${countRows(broadUse.map(([label, value]) => ({ label, value })), maxUse, 'Parcel count · administrative record')}
        <div class="inline-stats" style="margin-top:1rem">
          <div class="inline-stat"><strong>${number.format(counts.total_parcel_count)}</strong><span>Total parcels</span></div>
          <div class="inline-stat"><strong>${number.format(entry.multifamily_parcels)}</strong><span>Apartment-class parcels</span></div>
          <div class="inline-stat"><strong>${entry.multifamily_share_pct == null ? 'N/A' : `${oneDecimal.format(entry.multifamily_share_pct)}%`}</strong><span>Apartment share of parcels</span></div>
        </div>
      </article>
      <article class="data-card card full">
        <h3>Most common property classes</h3><p>Top ${classes.length} classes by parcel count. Class 411 (Apartments) is the class under which condominium and cooperative units are reported.</p>
        ${countRows(classes.map((item) => ({ label: `${item.class} · ${item.description}`, value: item.parcels })), maxClass, 'Parcel count · administrative record')}
      </article>
      <article class="data-card card full">
        <h3>Class detail with assessed market value</h3>
        <table class="data-table"><caption class="sr-only">Property classes, parcel counts, and total assessed market value</caption><thead><tr><th scope="col">Class</th><th scope="col">Description</th><th scope="col">Parcels</th><th scope="col">Assessed market value</th></tr></thead><tbody>${classes.map((item) => `<tr><td>${escapeHtml(item.class)}</td><td>${escapeHtml(item.description)}</td><td>${number.format(item.parcels)}</td><td>${item.total_market_value_usd == null ? 'Not available' : currency.format(item.total_market_value_usd)}</td></tr>`).join('')}</tbody></table>
      </article>
      ${propertyMethod(prop)}
    </div>`;
  }

  function propertyMethod(prop) {
    return `<article class="data-card card full">
      <h3>Method and limits</h3>
      <p>${escapeHtml(prop.multifamily_class_note)}</p>
      <ul class="source-list">${prop.sources.map((source) => `<li><a href="${escapeHtml(source.url)}" target="_blank" rel="noreferrer">${escapeHtml(source.name)}</a> — ${escapeHtml(source.publisher)}, dataset <code>${escapeHtml(source.dataset_id)}</code></li>`).join('')}</ul>
      <p class="compare">Counts cover ${number.format(prop.municipalities_in_source)} municipalities in the ${escapeHtml(prop.county)} roll. Values are as-reported; this prototype does not re-assess, equalize, or rank municipalities by them.</p>
    </article>`;
  }

  function renderTheme(profile) {
    const renderers = { population: renderPopulation, housing: renderHousing, commute: renderCommute, 'land-use': renderLandUse, economy: renderEconomy, employment: renderEmployment, transit: renderTransit, property: renderProperty, methods: renderMethods };
    $('#themeContent').innerHTML = renderers[state.theme](profile);
    $$('#themeTabs button').forEach((button) => {
      const selected = button.dataset.theme === state.theme;
      button.setAttribute('aria-selected', String(selected));
      button.setAttribute('tabindex', selected ? '0' : '-1');
    });
  }

  function allCoordinates(geometry) {
    const points = [];
    (function walk(value) {
      if (Array.isArray(value) && typeof value[0] === 'number') points.push(value);
      else if (Array.isArray(value)) value.forEach(walk);
    })(geometry.coordinates);
    return points;
  }

  function renderMap() {
    const features = state.geo.features;
    const aggregateFeature = state.aggregateGeo.features.find((feature) => feature.properties.profile_id === state.currentId);
    const points = [...features, ...(aggregateFeature ? [aggregateFeature] : [])].flatMap((feature) => allCoordinates(feature.geometry));
    let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity;
    for (const [x, y] of points) {
      if (x < minX) minX = x;
      if (x > maxX) maxX = x;
      if (y < minY) minY = y;
      if (y > maxY) maxY = y;
    }
    const width = 680, height = 390, pad = 10;
    const scale = Math.min((width - pad * 2) / (maxX - minX), (height - pad * 2) / (maxY - minY));
    const offsetX = (width - (maxX - minX) * scale) / 2;
    const offsetY = (height - (maxY - minY) * scale) / 2;
    const project = ([x, y]) => [offsetX + (x - minX) * scale, height - offsetY - (y - minY) * scale];
    const ringPath = (ring) => ring.map((point, index) => `${index ? 'L' : 'M'}${project(point).map((v) => v.toFixed(2)).join(',')}`).join(' ') + ' Z';
    const geometryPath = (geometry) => {
      if (geometry.type === 'Polygon') return geometry.coordinates.map(ringPath).join(' ');
      return geometry.coordinates.flatMap((polygon) => polygon.map(ringPath)).join(' ');
    };
    const selectedProfile = getProfile(state.currentId);
    const selected = selectedProfile.map_role === 'base' ? state.currentId : null;
    const hasSelection = state.currentId !== 'westchester-county';
    const paths = features.map((feature) => {
      const id = feature.properties.profile_id;
      const classes = [id === selected ? 'selected' : '', hasSelection && id !== selected ? 'dimmed' : ''].filter(Boolean).join(' ');
      return `<path d="${geometryPath(feature.geometry)}" data-id="${escapeHtml(id)}" class="${classes}" tabindex="0" role="button" aria-label="Open ${escapeHtml(feature.properties.name)} profile"><title>${escapeHtml(feature.properties.name)}</title></path>`;
    }).join('');
    const overlay = aggregateFeature
      ? `<path d="${geometryPath(aggregateFeature.geometry)}" data-id="${escapeHtml(state.currentId)}" class="aggregate-overlay" tabindex="0" role="button" aria-label="Selected ${escapeHtml(aggregateFeature.properties.name)} overlapping town boundary"><title>${escapeHtml(aggregateFeature.properties.name)} · overlapping legal town boundary</title></path>`
      : '';
    const mapTitle = aggregateFeature ? `${aggregateFeature.properties.name} overlapping town boundary in Westchester County` : 'Westchester County community boundaries';
    $('#map').innerHTML = `<svg viewBox="0 0 ${width} ${height}" aria-labelledby="mapTitle"><title id="mapTitle">${escapeHtml(mapTitle)}</title><g fill-rule="evenodd">${paths}${overlay}</g></svg>`;
    $$('#map path').forEach((path) => {
      const go = () => { window.location.hash = themeRoute(path.dataset.id); };
      path.addEventListener('click', go);
      path.addEventListener('keydown', (event) => { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); go(); } });
    });
  }

  function renderDirectory() {
    const municipalities = state.data.profiles.filter((profile) => profile.id !== 'westchester-county').sort((a, b) => a.name.localeCompare(b.name));
    $('#communityList').innerHTML = `<a class="community-link" data-id="westchester-county" href="${themeRoute('westchester-county')}"><span>County overview</span><small>county</small></a>` + municipalities.map((profile) => `<a class="community-link" data-id="${escapeHtml(profile.id)}" data-search="${escapeHtml(profile.name.toLowerCase())}" href="${themeRoute(profile.id)}"><span>${escapeHtml(profile.name)}</span><small>${escapeHtml(profile.profile_type)}</small></a>`).join('');
    $('#communitySelect').innerHTML = `<option value="westchester-county">Westchester County overview</option>` + municipalities.map((profile) => `<option value="${escapeHtml(profile.id)}">${escapeHtml(profile.name)} · ${escapeHtml(profile.profile_type)}</option>`).join('');
  }

  function renderProfile() {
    const profile = getProfile(state.currentId);
    state.currentId = profile.id;
    $('#profileName').textContent = profile.name;
    $('#profileType').textContent = `${profile.profile_type} profile`;
    $('#profileDescription').textContent = profile.id === 'westchester-county'
      ? 'Countywide overview with direct access to all 45 municipal-government profiles.'
      : profile.geography_note || `A 2024 ACS and 2025 County parcel profile using ${profile.census_geography} geography.`;
    $('#communitySelect').value = profile.id;
    $$('.community-link').forEach((link) => {
      const active = link.dataset.id === profile.id;
      link.classList.toggle('active', active);
      link.href = themeRoute(link.dataset.id);
      if (active) link.setAttribute('aria-current', 'page'); else link.removeAttribute('aria-current');
    });
    $('#mapHeading').textContent = profile.id === 'westchester-county'
      ? 'Select a community'
      : profile.map_role === 'aggregate overlay' ? `${profile.name} aggregate overlay` : `${profile.name} in county context`;
    $('#mapHelp').textContent = profile.map_role === 'aggregate overlay'
      ? 'Dashed orange outline: official Census TIGER/Line town boundary. Muted polygons: the unchanged 43-geography County GIS base map. The town total overlaps village profiles.'
      : 'Select a community on the map or in the directory. Base polygons are County GIS data; split village parts are unioned by name.';
    renderKeyFacts(profile);
    renderMap();
    renderTheme(profile);
    document.title = `${profile.name} | Westchester Community Profiles`;
  }

  function route() {
    const match = window.location.hash.match(/^#\/profile\/([a-z0-9-]+)(?:\/theme\/([a-z-]+))?$/);
    const validThemes = new Set(['population', 'housing', 'commute', 'land-use', 'economy', 'employment', 'transit', 'property', 'methods']);
    state.currentId = match ? match[1] : 'westchester-county';
    state.theme = match && validThemes.has(match[2]) ? match[2] : 'population';
    if (state.data) renderProfile();
  }

  // Externally collected datasets are OPTIONAL: they are produced by
  // scripts/run_collectors.sh, not by the main Census/GIS build. A missing or
  // malformed file must leave the core dashboard fully working; the affected
  // tab renders an explanatory message instead of failing the whole app.
  async function loadOptional(key, path) {
    try {
      const response = await fetch(path);
      if (!response.ok) return;
      state[key] = await response.json();
    } catch (_) {
      /* leave state[key] null; renderer explains the situation */
    }
  }

  async function init() {
    try {
      const [profileResponse, geoResponse, aggregateGeoResponse] = await Promise.all([
        fetch('data/profiles.json'),
        fetch('data/municipal_boundaries.geojson'),
        fetch('data/town_aggregate_boundaries.geojson'),
      ]);
      if (!profileResponse.ok || !geoResponse.ok || !aggregateGeoResponse.ok) throw new Error(`Data request failed (${profileResponse.status}/${geoResponse.status}/${aggregateGeoResponse.status})`);
      state.data = await profileResponse.json();
      state.geo = await geoResponse.json();
      state.aggregateGeo = await aggregateGeoResponse.json();
      if (state.data.profiles.length !== 46 || state.geo.features.length !== 43 || state.aggregateGeo.features.length !== 2) throw new Error('Profile completeness check failed');
      await Promise.all([
        loadOptional('employment', 'data/employment/qcew_westchester.json'),
        loadOptional('transit', 'data/gtfs/mnr_station_frequency.json'),
        loadOptional('property', 'data/parcels/nyopendata_property_inventory.json'),
      ]);
      $('#vintageLabel').textContent = `· ACS ${state.data.metadata.acs.vintage} 5-year`;
      renderDirectory();
      if (!window.location.hash) history.replaceState(null, '', themeRoute());
      route();
      $('#status').hidden = true;
      $('#dashboard').hidden = false;
    } catch (error) {
      $('#status').innerHTML = `<strong>Dashboard data could not load.</strong><br>${escapeHtml(error.message)}. Serve this directory over HTTP rather than opening the file directly.`;
      console.error(error);
    }
  }

  function filterCommunities(query) {
    const normalized = query.trim().toLowerCase();
    $$('.community-link[data-search]').forEach((link) => link.classList.toggle('hidden', !link.dataset.search.includes(normalized)));
  }
  $('#communitySearch').addEventListener('input', (event) => {
    $('#headerCommunitySearch').value = event.target.value;
    filterCommunities(event.target.value);
  });
  $('#headerCommunitySearch').addEventListener('input', (event) => {
    $('#communitySearch').value = event.target.value;
    filterCommunities(event.target.value);
  });
  $('#communitySelect').addEventListener('change', (event) => { window.location.hash = themeRoute(event.target.value); });
  $('#resetMap').addEventListener('click', () => { window.location.hash = themeRoute('westchester-county'); });
  $('#themeTabs').addEventListener('click', (event) => {
    const button = event.target.closest('button[data-theme]');
    if (!button) return;
    window.location.hash = themeRoute(state.currentId, button.dataset.theme);
  });
  $('#themeTabs').addEventListener('keydown', (event) => {
    if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return;
    const tabs = $$('#themeTabs button');
    const current = tabs.findIndex((tab) => tab.dataset.theme === state.theme);
    const next = event.key === 'Home' ? 0 : event.key === 'End' ? tabs.length - 1 : (current + (event.key === 'ArrowRight' ? 1 : -1) + tabs.length) % tabs.length;
    event.preventDefault();
    window.location.hash = themeRoute(state.currentId, tabs[next].dataset.theme);
    tabs[next].focus();
  });
  $('#copyLink').addEventListener('click', async (event) => {
    try {
      await navigator.clipboard.writeText(window.location.href);
      event.target.textContent = 'Link copied';
      setTimeout(() => { event.target.textContent = 'Copy profile link'; }, 1600);
    } catch (_) {
      window.prompt('Copy this profile link:', window.location.href);
    }
  });
  window.addEventListener('hashchange', route);
  init();
})();
