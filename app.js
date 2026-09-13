(() => {
  'use strict';

  const state = { data: null, geo: null, aggregateGeo: null, currentId: 'westchester-county', theme: 'population' };
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
    return `<div class="bar-list">${items.map(({ label, metric, value }) => {
      const estimate = value ?? metric?.estimate;
      const width = estimate == null ? 0 : Math.max(0, Math.min(100, estimate / max * 100));
      const display = estimate == null ? 'N/A' : suffix === '%' ? `${oneDecimal.format(estimate)}%` : suffix === 'acres' ? `${number.format(estimate)} ac` : number.format(estimate);
      const title = metric ? moeText(metric, suffix === '%' ? 'percent' : 'number') : 'County GIS parcel observation; no sampling MOE';
      return `<div class="bar-row" title="${escapeHtml(title)}"><span>${escapeHtml(label)}</span><span class="bar-track"><span class="bar-fill" style="width:${width}%"></span></span><strong class="bar-value">${display}</strong></div>`;
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
        <h3>Known gaps and next integrations</h3><p>Unavailable data are not represented with proxy metrics.</p>
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

  function renderTheme(profile) {
    const renderers = { population: renderPopulation, housing: renderHousing, commute: renderCommute, 'land-use': renderLandUse, methods: renderMethods };
    $('#themeContent').innerHTML = renderers[state.theme](profile);
    $$('#themeTabs button').forEach((button) => button.setAttribute('aria-selected', String(button.dataset.theme === state.theme)));
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
      const go = () => { window.location.hash = `#/profile/${path.dataset.id}`; };
      path.addEventListener('click', go);
      path.addEventListener('keydown', (event) => { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); go(); } });
    });
  }

  function renderDirectory() {
    const municipalities = state.data.profiles.filter((profile) => profile.id !== 'westchester-county').sort((a, b) => a.name.localeCompare(b.name));
    $('#communityList').innerHTML = `<a class="community-link" data-id="westchester-county" href="#/profile/westchester-county"><span>County overview</span><small>county</small></a>` + municipalities.map((profile) => `<a class="community-link" data-id="${escapeHtml(profile.id)}" data-search="${escapeHtml(profile.name.toLowerCase())}" href="#/profile/${escapeHtml(profile.id)}"><span>${escapeHtml(profile.name)}</span><small>${escapeHtml(profile.profile_type)}</small></a>`).join('');
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
    $$('.community-link').forEach((link) => link.classList.toggle('active', link.dataset.id === profile.id));
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
    const match = window.location.hash.match(/^#\/profile\/([a-z0-9-]+)$/);
    state.currentId = match ? match[1] : 'westchester-county';
    if (state.data) renderProfile();
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
      $('#vintageLabel').textContent = `· ACS ${state.data.metadata.acs.vintage} 5-year`;
      renderDirectory();
      route();
      $('#status').hidden = true;
      $('#dashboard').hidden = false;
    } catch (error) {
      $('#status').innerHTML = `<strong>Dashboard data could not load.</strong><br>${escapeHtml(error.message)}. Serve this directory over HTTP rather than opening the file directly.`;
      console.error(error);
    }
  }

  $('#communitySearch').addEventListener('input', (event) => {
    const query = event.target.value.trim().toLowerCase();
    $$('.community-link[data-search]').forEach((link) => link.classList.toggle('hidden', !link.dataset.search.includes(query)));
  });
  $('#communitySelect').addEventListener('change', (event) => { window.location.hash = `#/profile/${event.target.value}`; });
  $('#resetMap').addEventListener('click', () => { window.location.hash = '#/profile/westchester-county'; });
  $('#themeTabs').addEventListener('click', (event) => {
    const button = event.target.closest('button[data-theme]');
    if (!button) return;
    state.theme = button.dataset.theme;
    renderTheme(getProfile(state.currentId));
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
