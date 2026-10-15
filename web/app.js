import * as THREE from './vendor/three.module.js';
import { MapControls } from './vendor/MapControls.js';

// Colours are authored in sRGB and drawn as they are.
THREE.ColorManagement.enabled = false;

const SKY = '#e4e8ea';
const LAND = '#f4f3ef';
const WATER = '#b5c7c6';
const MAQUETTE = '#efeee9';
const GROUP_COLORS = ['#ec0000', '#1f4e8c', '#d99a12', '#2e8b57', '#7b3fa0', '#00909a', '#8c5a2b', '#d6336c'];
const MAX_GROUPS = GROUP_COLORS.length;
const ATTR_W = 256;
const WORKERS = Math.min(4, navigator.hardwareConcurrency || 2);
// Solar and heating share the Energy button and the demolished buildings the Period one: the panel switches between them.
const MODE = { period: 0, floors: 1, energy: 2, layers: 3, solar: 4, gone: 5, heat: 6 };
// Energy labels G … A (index 1–7; 0 = no label), from red through yellow to green.
const ENERGY_COLORS = ['#efeee9', '#c1272d', '#e4572e', '#f08a24', '#f6c445', '#c9d64a', '#8cc152', '#2e9a49'];
// Solar potential: none, no suitable roof, then the steps of config.solar.steps from pale yellow to deep orange.
// Floors in seven steps, each from its lower bound: 1, 2, 3–4, 5–6, 7–8, 9–12, 13+. The city is mostly low (63 % have
// one floor), so the steps sit where its height varies. Light to dark, each step clearly darker than the last (OKLCH L
// 0.86 → 0.29, checked with the dataviz validator), and the hue turns all the way, yellow, orange, red, magenta,
// purple, indigo, navy, at full chroma: the walls' shading moves lightness as much as a step does, so the hue tells
// the steps apart (about 14 ΔE between neighbours). The yellow is near the land in lightness, but not in hue.
const FLOOR_STEPS = [1, 2, 3, 5, 7, 9, 13];
const FLOOR_COLORS = ['#f5ce05', '#fd9305', '#f6563b', '#d3266f', '#952490', '#52268d', '#191e6a'];
const SOLAR_COLORS = ['#efeee9', '#c4c9cc', '#fbeeb0', '#f9dc7a', '#f6c445', '#f0a830', '#e88a24', '#d9661f', '#bf4a1c', '#8f2f14'];
// Heat source, by the groups of pipeline/codes.py HEAT after none recorded: district heating, electricity, ground-source
// heat, oil, the rest. Every pair stays apart for colour-blind eyes too (dataviz validator, all pairs, on the land);
// the closest, oil and ground heat, sits in the 6–8 ΔE band that asks for a second cue: the legend names each and
// isolates it on a click.
const HEAT_COLORS = ['#efeee9', '#2a78d6', '#eda100', '#1baf7a', '#e34948', '#8f2f14'];

const [config, layers, attrBuf, info, war, other] = await Promise.all([
  fetch('data/helsinki.json').then(r => r.json()),
  fetch('data/layers.json').then(r => r.json()),
  fetch('data/attrs.bin').then(r => r.arrayBuffer()),
  fetch('data/info.json').then(r => r.json()),   // per building: id (VTJ-PRT or the city's feature id), address
  fetch('data/war.json').then(r => r.json()),    // views laid on the ground rather than on the buildings: s11_war,
  fetch('data/other.json').then(r => r.json()),  // and s12_other
]);
const attrs = new DataView(attrBuf);

// ---------- Language ----------
// Finnish and English. Data carries `<field>_fi` next to each English text; the interface strings are below.
const FI_UI = {
  'Helsinki, building by building': 'Helsinki, rakennus rakennukselta',
  'Quests': 'Visailut',
  'Easy': 'Helppo',
  'Medium': 'Keskitaso',
  'Hard': 'Vaikea',
  'Start': 'Aloita',
  'Continue': 'Jatka',
  'Play again': 'Pelaa uudelleen',
  'Find buildings from riddles and old photos, guess their age with the colours switched off. Every answer is worth three crosses; hints and wrong answers cost one.': 'Etsi rakennuksia arvoitusten ja vanhojen kuvien avulla ja arvaa niiden ikä värit piilotettuina. Jokaisesta vastauksesta saa kolme ristiä; vihjeet ja väärät vastaukset maksavat yhden.',
  'Your crosses': 'Ristisi',
  'Look inside the red circle.': 'Katso punaisen ympyrän sisältä.',
  'Find it on the map and click it.': 'Etsi se kartalta ja napsauta sitä.',
  'Hint': 'Vihje',
  'Colour by floors': 'Väritä kerrosluvun mukaan',
  'Colour by period': 'Väritä aikakauden mukaan',
  'Show me': 'Näytä',
  'Your guess': 'Arvauksesi',
  'Guess': 'Arvaa',
  'A photo of the building to find': 'Kuva etsittävästä rakennuksesta',
  'Built': 'Valmistui',
  'Exactly right.': 'Täsmälleen oikein.',
  'year off': 'vuosi pielessä',
  'years off': 'vuotta pielessä',
  'Shown, not found: no crosses.': 'Näytetty, ei löydetty: ei ristejä.',
  'Full marks.': 'Täydet pisteet.',
  'See the result': 'Katso tulos',
  'Next': 'Seuraava',
  'Open its card': 'Avaa rakennuksen kortti',
  'Not that one.': 'Ei se.',
  'A true Helsinki local.': 'Todellinen stadilainen.',
  'You know your way around.': 'Tunnet kaupunkisi.',
  'A good walk.': 'Hyvä kävely.',
  'Time for a walk through town.': 'Aika lähteä kaupunkikävelylle.',
  'Copy result': 'Kopioi tulos',
  'Copied': 'Kopioitu',
  'More quests': 'Lisää visailuja',
  'Not this one, but right next to it.': 'Ei tämä, mutta aivan vieressä.',
  'Not this one. Very warm.': 'Ei tämä. Tosi lähellä.',
  'Not this one. A few streets away.': 'Ei tämä. Muutaman korttelin päässä.',
  'Not this one. Far off.': 'Ei tämä. Kaukana.',
  'Warmer than before.': 'Lähempänä kuin äsken.',
  'Colder than before.': 'Kauempana kuin äsken.',
  'Every building standing today, by the year it was completed.': 'Kaupungin jokainen rakennus valmistumisvuoden mukaan.',
  'About': 'Tietoa', 'Did you know': 'Tiesitkö', 'Today': 'Nyt', 'Earlier': 'Aiemmin', 'Later': 'Myöhemmin', 'This photo did not load.': 'Kuva ei latautunut.', 'Open it in the archive': 'Avaa se arkistossa',
  'Wikidata records this building as their residence.': 'Wikidatan mukaan henkilö asui tässä.',
  'Wikidata records this building as their place of work.': 'Wikidatan mukaan henkilö työskenteli tässä.',
  'Wikidata records this building as their birthplace.': 'Wikidatan mukaan henkilö syntyi tässä.',
  'Wikidata records this building as the place where they died.': 'Wikidatan mukaan henkilö kuoli tässä.',
  'Period': 'Aikakausi', 'Context layers': 'Kontekstitasot', 'Floors': 'Kerrokset', 'Energy': 'Energia', 'Aerial 3D': 'Ilmakuva 3D', 'Map': 'Kartta', 'Scale model': 'Pienoismalli', 'Under the buildings': 'Rakennusten alla', 'Old maps': 'Vanhat kartat', 'Aerial photos': 'Ilmakuvat', 'Plans': 'Kaavat', 'Noise': 'Melu',
  'What Helsinki was meant to become: the city\'s master plans and their proposals.': 'Millainen Helsingistä piti tulla: kaupungin yleiskaavat ja niiden ehdotukset.',
  'Road traffic noise by day (LAeq 7–22), as each year\'s survey found it.': 'Tieliikenteen melu päivällä (LAeq 7–22) kunkin vuoden meluselvityksessä.',
  'General plan for Greater Helsinki': 'Suur-Helsingin yleissuunnitelma', 'Master plan proposal for the central city': 'Keskiosien yleiskaavaehdotus',
  'Master plan proposal': 'Yleiskaavaehdotus', 'Revised land use for 1980': 'Tarkistettu maankäyttö vuodelle 1980', 'Master plan': 'Yleiskaava',
  'Pick a year, or drag the timeline: the map changes with it.': 'Valitse vuosi tai vedä aikajanaa: kartta vaihtuu sen mukana.',
  'Hide the buildings': 'Piilota rakennukset', 'No earlier name known': 'Ei aiempaa nimeä tiedossa',
  'Click a street to see its names and where they come from.': 'Napsauta katua: näet sen nimet ja mistä ne tulevat.',
  'Year of the aerial photos': 'Ilmakuvien vuosi',
  'buildings': 'rakennusta', 'Building the city': 'Kaupunkia rakennetaan',
  'Drag to turn. Right-drag or Shift-drag to move. Scroll to zoom.': 'Käännä vetämällä. Siirrä oikealla painikkeella tai Shift-vedolla. Zoomaa rullalla.',
  'Show legend': 'Näytä selite', 'Hide legend': 'Piilota selite',
  'Built in': 'Valmistunut', 'Click a period to see it alone. Paler buildings have an approximate year.': 'Napsauta aikakautta nähdäksesi vain sen. Haaleampien rakennusten vuosi on arvio.',
  'Storeys': 'Kerroksia', 'Use': 'Käyttötarkoitus', 'Structure': 'Kantava rakenne', 'Facade': 'Julkisivu', 'Address': 'Osoite',
  'Building ID': 'Pysyvä rakennustunnus', 'not in the register': 'ei rekisterissä', 'Height': 'Korkeus', 'floors × 3.2 m': 'kerrosluku × 3,2 m',
  'All context layers': 'Kaikki kontekstitasot', 'Find a person': 'Etsi henkilö', 'Buildings and their stories': 'Rakennukset ja niiden tarinat',
  'Architect': 'Arkkitehti', 'Architects': 'Arkkitehdit', 'Style': 'Tyyli',
  'In layers': 'Tasoissa', 'Dating': 'Ajoitus', 'Read more': 'Lue lisää', 'From the street': 'Kadulta',
  'Lived or worked here': 'Asui tai työskenteli täällä', 'Source': 'Lähde', 'Photo': 'Kuva',
  'Wikipedia': 'Wikipedia', 'Finnish Wikipedia': 'Suomenkielinen Wikipedia', 'Helsinki building register': 'Helsingin rakennusrekisteri',
  'The register gives': 'Rekisteri antaa', 'c. ': 'n. ', 'The 3D city model gives': '3D-kaupunkimalli antaa',
  'Energy label': 'Energialuokka', 'Solar potential': 'Aurinkosähköpotentiaali', 'no suitable roof': 'ei sopivaa kattoa',
  'Heating': 'Lämmitys', 'Not recorded': 'Ei kirjattu', 'Fines on the street': 'Virhemaksuja kadulla', 'Most fined streets': 'Eniten virhemaksuja', 'No fines': 'Ei virhemaksuja',
  'In all': 'Yhteensä', 'fines': 'virhemaksua', 'Per 100 m': '100 metriä kohden', 'Fines per 100 m': 'Virhemaksuja 100 metriä kohden', 'under': 'alle', '100 m or longer': 'vähintään 100 m pitkät', 'Solar': 'Aurinkosähkö', 'Click a source to see it alone.': 'Napsauta lähdettä nähdäksesi vain sen.',
  'Street name, in Finnish': 'Kadun nimi', 'History of the name': 'Nimen historia', 'Energy certificate register': 'Energiatodistusrekisteri',
  'HSY solar potential': 'HSY:n aurinkosähköpotentiaali', 'Helsinki place names': 'Helsingin nimistö', 'MWh a year': 'MWh vuodessa',
  'Street names': 'Kadunnimet', 'Earlier name known': 'Aiempi nimi tiedossa', 'Earlier names': 'Aiemmat nimet',
  'Named after, in Finnish': 'Nimen peruste', 'The place-name register gives no explanation.': 'Nimistörekisterissä ei ole selitystä.',
  'Read out of the history of the name in the place-name register.': 'Poimittu nimistörekisterin nimen historiasta.',
  'Year not known': 'Vuosi ei tiedossa', 'War': 'Sota', 'Other': 'Muut', 'Everything': 'Kaikki kohteet', 'On the map': 'Kartalla', 'Sources': 'Lähteet', 'Type': 'Tyyppi', 'Construction': 'Rakenne', 'History': 'Historia', 'Strongpoints': 'Tukikohdat', 'Find a site': 'Etsi kohde',
  'Completed': 'Valmistuneet', 'Torn down': 'Puretut', 'torn down': 'purettua', 'Demolished': 'Purettu', 'Demolished building': 'Purettu rakennus', 'Helsinki 3D city model': 'Helsingin 3D-kaupunkimalli',
  'The 3D city model gives no year. Estimated from the nearest dated buildings, before the year it was demolished.': '3D-kaupunkimallissa ei ole vuotta. Arvioitu lähimpien rakennusten vuosista, ennen purkuvuotta.',
  'Click for the story and sources': 'Napsauta: tarina ja lähteet', 'Click to keep this card open': 'Napsauta pitääksesi kortin auki',
  'Play the city\'s growth': 'Toista kaupungin kasvu', 'Pause': 'Tauko', 'Close': 'Sulje',
  'The register gives a round decade here, more often than the years around it predict. Read it as “around then”.': 'Rekisteri antaa tässä tasakymmenen useammin kuin ympäröivät vuodet antaisivat odottaa. Lue se ”noihin aikoihin”.',
  'The register gives no year, or a placeholder. Estimated from the nearest dated buildings.': 'Rekisterissä ei ole vuotta tai siinä on paikkamerkki. Arvioitu lähimpien rakennusten vuosista.',
  'The register gives no year, or a placeholder. Estimated from the other buildings on the same property.': 'Rekisterissä ei ole vuotta tai siinä on paikkamerkki. Arvioitu saman kiinteistön muiden rakennusten vuosista.',
  '–1808 Swedish era': '–1808 Ruotsin vallan aika', '1809–1869 Empire Helsinki': '1809–1869 Empire-Helsinki',
  '1870–1899 Historicism and the railway': '1870–1899 Historismi ja rautatie', '1900–1917 Art Nouveau and National Romanticism': '1900–1917 Jugend ja kansallisromantiikka',
  '1918–1939 Classicism and functionalism': '1918–1939 Klassismi ja funkis', '1940–1959 Reconstruction and the Olympics': '1940–1959 Jälleenrakennus ja olympialaiset',
  '1960–1979 Suburbs and prefab concrete': '1960–1979 Lähiöt ja elementit', '1980–1999 Postmodernism and infill': '1980–1999 Postmoderni ja täydennysrakentaminen',
  '2000–2014 Ruoholahti, Arabianranta, Viikki': '2000–2014 Ruoholahti, Arabianranta, Viikki', '2015– Jätkäsaari, Kalasatama, Pasila': '2015– Jätkäsaari, Kalasatama, Pasila',
};
let LANG = (() => {
  const q = new URLSearchParams(location.search).get('lang');
  if (q === 'fi' || q === 'en') return q;
  try { const s = localStorage.getItem('lang'); if (s === 'fi' || s === 'en') return s; } catch {}
  return navigator.language?.startsWith('fi') ? 'fi' : 'en';
})();
const t = s => (LANG === 'fi' && FI_UI[s]) || s;
const tr = (o, k) => (LANG === 'fi' && o?.[k + '_fi']) || o?.[k];
const fmtLocale = () => LANG === 'fi' ? 'fi-FI' : 'en';
const periods = config.periods;

// ---------- Scene ----------
const canvas = document.getElementById('scene');
const renderer = new THREE.WebGLRenderer({ canvas, antialias: true });
renderer.outputColorSpace = THREE.LinearSRGBColorSpace;
renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
renderer.setClearColor(SKY);
const scene = new THREE.Scene();
const camera = new THREE.PerspectiveCamera(35, 1, 5, 60000);
const controls = new MapControls(camera, canvas);
controls.enableDamping = true;
// Left drag turns and tilts the city; right drag, or Shift with the left, moves it.
controls.mouseButtons = { LEFT: THREE.MOUSE.ROTATE, MIDDLE: THREE.MOUSE.DOLLY, RIGHT: THREE.MOUSE.PAN };
controls.rotateSpeed = 0.6;
controls.maxPolarAngle = Math.PI * 0.47;
controls.minDistance = 60;
controls.maxDistance = 30000;

function goHome() {
  const h = config.home, az = THREE.MathUtils.degToRad(h.azimuth), el = THREE.MathUtils.degToRad(h.elevation);
  const d = h.span * 0.9;
  controls.target.set(h.x, 0, h.z);
  camera.position.set(h.x + d * Math.cos(el) * Math.sin(az), d * Math.sin(el), h.z + d * Math.cos(el) * Math.cos(az));
  controls.update();
}
goHome();

// Land and water: flat polygons in the local frame (see pipeline/s04_water.py).
async function loadPolygons(url) {
  const buf = await (await fetch(url)).arrayBuffer();
  const [nPoly, nRing, nVert] = new Uint32Array(buf, 0, 3);
  const ringStart = new Uint32Array(buf, 12, nPoly + 1);
  const vertStart = new Uint32Array(buf, 12 + 4 * (nPoly + 1), nRing + 1);
  const xz = new Float32Array(buf, 12 + 4 * (nPoly + 1) + 4 * (nRing + 1), 2 * nVert);
  const ring = r => {
    const pts = [];
    for (let v = vertStart[r]; v < vertStart[r + 1]; v++) pts.push(new THREE.Vector2(xz[2 * v], -xz[2 * v + 1]));
    return pts;
  };
  const shapes = [];
  for (let p = 0; p < nPoly; p++) {
    const shape = new THREE.Shape(ring(ringStart[p]));
    for (let r = ringStart[p] + 1; r < ringStart[p + 1]; r++) shape.holes.push(new THREE.Path(ring(r)));
    shapes.push(shape);
  }
  const g = new THREE.ShapeGeometry(shapes);
  g.rotateX(-Math.PI / 2);
  return g;
}
const flat = new THREE.Group();
scene.add(flat);
const [landGeo, waterGeo] = await Promise.all([loadPolygons('data/land.bin'), loadPolygons('data/water.bin')]);
const land = new THREE.Mesh(landGeo, new THREE.MeshBasicMaterial({ color: LAND }));
const water = new THREE.Mesh(waterGeo, new THREE.MeshBasicMaterial({ color: WATER }));
land.position.y = -0.05;
water.position.y = -0.4;
flat.add(land, water);

// ---------- Street and canal names ----------
// Flat on the ground, turned along the street (pipeline/s07_labels.py). Textures are drawn on first use.
const labelData = await fetch('data/labels.json').then(r => r.json());
const labelGroup = new THREE.Group();
scene.add(labelGroup);
const labelTex = new Map();
const LABEL_PX = 64;
function textureFor(L) {
  let t = labelTex.get(L.name + L.water);
  if (t) return t;
  const c = document.createElement('canvas'), ctx = c.getContext('2d');
  const font = `${L.water ? 'italic 500' : '500'} ${LABEL_PX * 0.62}px "Schibsted Grotesk", sans-serif`;
  ctx.font = font;
  c.width = Math.ceil(ctx.measureText(L.name).width + LABEL_PX * 0.4);
  c.height = LABEL_PX;
  ctx.font = font;
  ctx.textBaseline = 'middle';
  ctx.lineWidth = LABEL_PX * 0.12;
  ctx.strokeStyle = L.water ? 'rgba(181,199,198,0.85)' : 'rgba(244,243,239,0.85)';
  ctx.fillStyle = L.water ? '#3c6875' : '#50565b';
  ctx.strokeText(L.name, LABEL_PX * 0.2, LABEL_PX / 2);
  ctx.fillText(L.name, LABEL_PX * 0.2, LABEL_PX / 2);
  t = new THREE.CanvasTexture(c);
  t.anisotropy = 4;
  t.userData = { aspect: c.width / c.height };
  labelTex.set(L.name + L.water, t);
  return t;
}
const labelPlane = new THREE.PlaneGeometry(1, 1);
const labels = labelData.flatMap(L => L.pts.map(([x, z, ang, len, wid]) => ({ L, x, z, ang, len, wid: wid || 20, mesh: null })))
  .sort((a, b) => a.L.tier - b.L.tier || b.len - a.len);
function updateLabels(dist) {
  if (!document.fonts.check('500 16px "Schibsted Grotesk"')) return;
  // Label height in metres, roughly constant on screen; the canals and main streets read larger.
  const h1 = THREE.MathUtils.clamp(dist * 0.014, 4, 44), h2 = THREE.MathUtils.clamp(dist * 0.01, 3, 15);
  // Names appear only when the camera comes close: canals and main streets first, the rest closer still.
  const near = dist * 1.2, far = dist * 2;
  // Greedy collision: canals and main streets first, then the longest stretches; a label is dropped
  // when an accepted one already sits within a few label heights of it.
  const taken = new Map(), C = h1 * 5; // one grid, cells as wide as the largest separation
  const cellOf = (x, z) => `${Math.floor(x / C)},${Math.floor(z / C)}`;
  const clear = (l, sep) => {
    const cx = Math.floor(l.x / C), cz = Math.floor(l.z / C);
    for (let i = -1; i <= 1; i++) for (let j = -1; j <= 1; j++) {
      for (const q of taken.get(`${cx + i},${cz + j}`) || []) if ((q.x - l.x) ** 2 + (q.z - l.z) ** 2 < sep * sep) return false;
    }
    return true;
  };
  for (const l of labels) {
    const d = Math.hypot(l.x - camera.position.x, l.z - camera.position.z);
    let show = d < (l.L.tier === 1 ? far : near) && dist < (l.L.tier === 1 ? 3200 : 1300);
    const sep = (l.L.tier === 1 ? h1 : h2) * 5;
    if (show && !clear(l, sep)) show = false;
    if (show) {
      const key = cellOf(l.x, l.z);
      if (!taken.has(key)) taken.set(key, []);
      taken.get(key).push(l);
    }
    if (show && !l.mesh) {
      const tex = textureFor(l.L);
      l.mesh = new THREE.Mesh(labelPlane, new THREE.MeshBasicMaterial({ map: tex, transparent: true, depthWrite: false }));
      // Turn about the vertical first, then lay the plane flat.
      l.mesh.rotation.set(-Math.PI / 2, THREE.MathUtils.degToRad(-l.ang), 0, "YXZ"); // ang is measured towards +z, Y turns towards -z
      l.mesh.position.set(l.x, l.L.water ? 0.4 : 0.6, l.z);
      l.mesh.renderOrder = 2;
      labelGroup.add(l.mesh);
    }
    if (l.mesh) {
      // Never taller than the street or canal is wide, so a name stays off the buildings.
      const h = Math.min(l.L.tier === 1 ? h1 : h2, l.wid * 0.55);
      const w = h * l.mesh.material.map.userData.aspect;
      // A name much longer than its stretch of street would spill over the buildings.
      if (show && (w > l.len * 1.1 || h < 2.5)) show = false;
      l.mesh.visible = show;
      if (show) l.mesh.scale.set(w, h, 1);
    }
  }
}

// ---------- Shared uniforms ----------
const col = c => new THREE.Color(c);
const uniforms = {
  uYear: { value: config.yearMax },
  uYearFrom: { value: config.yearMin - 1 },
  uMode: { value: MODE.period },
  uPalette: { value: periods.map(p => col(p.color)) },
  uMask: { value: periods.map(() => 1) },
  uNow: { value: 0 },                              // seconds, for tiles dropping in as they load
  uPlaying: { value: 0 },                          // while the film plays buildings fly in rather than grow
  uRise: { value: 0.01 },
  uLayerAt: { value: -10 },                        // seconds; when a context layer opened, its buildings rise                          // years a building's entrance spans; only the film widens it
  uGroupBit: { value: Array(MAX_GROUPS).fill(-1) },
  uGroupColor: { value: GROUP_COLORS.map(col) },
  uMaquette: { value: col(MAQUETTE) },
  uEnergy: { value: ENERGY_COLORS.map(col) },
  uSolar: { value: SOLAR_COLORS.map(col) },
  uHeat: { value: HEAT_COLORS.map(col) },
  uFloors: { value: FLOOR_COLORS.map(col) },
  uHover: { value: -1 },
  uSelected: { value: -1 },
  uBlind: { value: 0 },
  uPale: { value: 0 },                             // the street-name view: buildings fade and take no clicks
  uFogColor: { value: col(SKY) },
  uFog: { value: new THREE.Vector2(9000, 26000) },
};

const VERT = /* glsl */`
  in float bld;
  uniform sampler2D uAttr;
  uniform float uYear, uYearFrom, uMode, uHover, uSelected, uBlind, uPale, uNow, uBorn, uPlaying, uRise, uLayerAt;
  uniform vec3 uPalette[${periods.length}];
  uniform float uMask[${periods.length}];
  uniform int uGroupBit[${MAX_GROUPS}];
  uniform vec3 uGroupColor[${MAX_GROUPS}];
  uniform vec3 uMaquette;
  uniform vec3 uEnergy[${ENERGY_COLORS.length}];
  uniform vec3 uSolar[${SOLAR_COLORS.length}];
  uniform vec3 uHeat[${HEAT_COLORS.length}];
  uniform vec3 uFloors[${FLOOR_COLORS.length}];
  out vec3 vColor;
  out vec3 vWorld;
  out float vGid;

  int floorStep(float f) {
    int k = 0;
    ${FLOOR_STEPS.slice(1).map(n => `if (f >= ${n}.0) k++;`).join(' ')}
    return k;
  }

  bool hasBit(vec4 words, int bit) {
    int w = bit / 16;
    float v = w == 0 ? words.x : w == 1 ? words.y : w == 2 ? words.z : words.w;
    return ((int(v + 0.5) >> (bit - w * 16)) & 1) == 1;
  }

  void main() {
    int i = int(bld + 0.5);
    ivec2 tc = ivec2(2 * (i % ${ATTR_W}), i / ${ATTR_W});
    vec4 a = texelFetch(uAttr, tc, 0);
    vec4 lay = texelFetch(uAttr, tc + ivec2(1, 0), 0);
    float year = a.x;
    int pf = int(a.y + 0.5);
    int period = pf % 16;
    int flag = pf / 16 % 16;
    float gone = float(pf / 256);  // the year it was demolished, 0 if it stands
    int heat = int(a.z / 16384.0);
    bool goneView = abs(uMode - 5.0) < 0.5;
    vGid = a.w;
    float vis = uMode < 1.5 ? uMask[period] : uMode > 5.5 ? uMask[heat] : 1.0;
    float g = clamp((uYear - year + 1.0) / uRise, 0.0, 1.0);
    g = g * g * (3.0 - 2.0 * g);
    bool down = gone > 0.0 && uYear >= gone;  // torn down by the year shown: gone, but in the view of the demolished
    if (g <= 0.003 || vis <= 0.003 || (down && !goneView)) { gl_Position = vec4(2.0, 2.0, 2.0, 1.0); return; }

    // Entrances, only while the film plays and while tiles load: a building drops in from its own side of the
    // sky, the same side every time (seeded by its id). Filters and scrubbing change the city at once.
    vec3 p = position;
    float seed = fract(sin(a.w * 12.9898) * 43758.5453);
    float arrive = clamp((uNow - uBorn) / 0.9 - seed * 0.35, 0.0, 1.0);
    float fly = 1.0 - arrive;
    if (uPlaying > 0.5) fly = max(fly, 1.0 - g);
    if (fly > 0.0) {
      float e = fly * fly * fly;
      float ang = seed * 6.2831853;
      // positions are in decimetres: a few hundred metres sideways and up
      p += vec3(cos(ang), 0.0, sin(ang)) * (1800.0 + 1600.0 * fract(seed * 7.13)) * e;
      p.y += (2600.0 + 2400.0 * fract(seed * 3.71)) * e;
    }
    vec3 c;
    if (uMode < 0.5) {
      c = uPalette[period];
      if (flag == 1 || flag == 2 || flag == 4) c = mix(c, uMaquette, 0.45);
    } else if (uMode < 1.5) {
      c = uFloors[floorStep(mod(a.z, 128.0))];
    } else if (uMode < 2.5) {
      c = uEnergy[int(mod(a.z / 128.0, 8.0))];
    } else if (uMode > 5.5) {
      c = uHeat[heat];
    } else if (uMode > 4.5) {
      c = down ? uPalette[period] : uMaquette;
    } else if (uMode > 3.5) {
      c = uSolar[int(mod(a.z / 1024.0, 16.0))];
    } else {
      c = uMaquette;
      for (int g = 0; g < ${MAX_GROUPS}; g++) {
        if (uGroupBit[g] >= 0 && hasBit(lay, uGroupBit[g])) {
          c = uGroupColor[g];
          // Opening a layer: its buildings rise out of the ground in a quick wave, overshoot a little, settle.
          float k = clamp((uNow - uLayerAt) / 0.55 - seed * 0.6, 0.0, 1.0);
          float q = k - 1.0;
          p.y *= 1.0 + 2.70158 * q * q * q + 1.70158 * q * q;
          break;
        }
      }
    }
    if (year <= uYearFrom) c = mix(c, uMaquette, 0.8);
    if (gone > 0.0 && !goneView) c = mix(c, vec3(1.0), 0.6);  // a ghost: torn down since
    // A quest's question about one building turns it red; a year riddle also hides every other age.
    if (uBlind > 0.5 && vGid == uSelected) c = vec3(0.925, 0.0, 0.0);
    else if (uBlind > 0.5 && uBlind < 1.5) c = uMaquette;
    if (uPale > 0.5) c = mix(c, uMaquette, 0.8);
    if (vGid == uHover || (vGid == uSelected && uBlind < 0.5)) c = mix(c, vec3(0.0), 0.35);
    vColor = c;
    vec4 w = modelMatrix * vec4(p, 1.0);
    vWorld = w.xyz;
    gl_Position = projectionMatrix * viewMatrix * w;
  }
`;

const FRAG = /* glsl */`
  precision highp float;
  uniform vec3 uFogColor;
  uniform vec2 uFog;
  in vec3 vColor;
  in vec3 vWorld;
  in float vGid;
  out vec4 outColor;
  void main() {
    #ifdef PICK
      float id = vGid + 1.0;
      outColor = vec4(mod(id, 256.0), mod(floor(id / 256.0), 256.0), floor(id / 65536.0), 255.0) / 255.0;
    #else
      vec3 n = normalize(cross(dFdx(vWorld), dFdy(vWorld)));
      // Low afternoon sun from the south-west, a soft sky from above.
      float sun = max(dot(n, normalize(vec3(-0.55, 0.55, 0.62))), 0.0);
      float light = n.y > 0.9 ? 1.04 : 0.66 + 0.34 * sun;
      float foot = mix(0.82, 1.0, clamp(vWorld.y / 12.0, 0.0, 1.0));
      vec3 c = vColor * light * foot;
      float d = length(vWorld - cameraPosition);
      c = mix(c, uFogColor, smoothstep(uFog.x, uFog.y, d));
      outColor = vec4(c, 1.0);
    #endif
  }
`;

function makeMaterial(tex, pick, born) {
  return new THREE.ShaderMaterial({
    glslVersion: THREE.GLSL3,
    uniforms: { ...uniforms, uAttr: { value: tex }, uBorn: born },
    vertexShader: VERT,
    fragmentShader: FRAG,
    defines: pick ? { PICK: 1 } : {},
    side: THREE.DoubleSide,
  });
}

// ---------- Tiles ----------
const meshes = [];
const blocks = new THREE.Group();   // hidden in the aerial view, still found by its clicks
scene.add(blocks);
let loaded = 0;
const queue = [...config.tiles];
const pool = Array.from({ length: WORKERS }, () => new Worker('worker.js', { type: 'module' }));

function addTile(m) {
  const g = new THREE.BufferGeometry();
  g.setAttribute('position', new THREE.BufferAttribute(m.pos, 3));
  g.setAttribute('bld', new THREE.BufferAttribute(m.bld, 1));
  g.setIndex(new THREE.BufferAttribute(m.idx, 1));
  const rows = Math.ceil(m.nB / ATTR_W);
  const data = new Float32Array(ATTR_W * 2 * rows * 4);
  data.set(m.attr);
  const tex = new THREE.DataTexture(data, ATTR_W * 2, rows, THREE.RGBAFormat, THREE.FloatType);
  tex.needsUpdate = true;
  const born = { value: performance.now() / 1000 };
  const mesh = new THREE.Mesh(g, makeMaterial(tex, false, born));
  mesh.userData = { draw: mesh.material, pick: makeMaterial(tex, true, born) };
  mesh.scale.setScalar(0.1);
  mesh.position.set(m.origin[0], 0, m.origin[1]);
  blocks.add(mesh);
  meshes.push(mesh);
}

// Tiles come in packs (see pipeline/s03_tiles.py); a tile is ready once its pack has arrived.
const packs = Object.fromEntries(config.packs.map(name => [name, fetch(`data/${name}`).then(r => r.arrayBuffer())]));
for (const w of pool) {
  const next = async () => {
    const t = queue.shift();
    if (!t) return;
    const buf = (await packs[t.pack]).slice(t.offset, t.offset + t.length);
    w.postMessage({ buf, id: t.file }, [buf]);
  };
  w.onmessage = ({ data }) => {
    addTile(data);
    loaded++;
    document.getElementById('progress').textContent = Math.round(100 * loaded / config.tiles.length);
    if (loaded === config.tiles.length) document.getElementById('loading').hidden = true;
    next();
  };
  next();
}

// ---------- Picking ----------
const pickTarget = new THREE.WebGLRenderTarget(1, 1);
const pickPixel = new Uint8Array(4);
function pick(x, y) {
  const w = renderer.domElement.clientWidth, h = renderer.domElement.clientHeight;
  camera.setViewOffset(w, h, x, y, 1, 1);
  for (const m of meshes) m.material = m.userData.pick;
  const groundShown = ground.visible;
  flat.visible = labelGroup.visible = ground.visible = false;
  renderer.setRenderTarget(pickTarget);
  renderer.setClearColor(0x000000, 0);
  renderer.clear();
  renderer.render(scene, camera);
  renderer.readRenderTargetPixels(pickTarget, 0, 0, 1, 1, pickPixel);
  renderer.setRenderTarget(null);
  renderer.setClearColor(SKY, 1);
  showCity();
  ground.visible = groundShown;
  for (const m of meshes) m.material = m.userData.draw;
  camera.clearViewOffset();
  return pickPixel[0] + pickPixel[1] * 256 + pickPixel[2] * 65536 - 1;
}

// ---------- Aerial view ----------
// The city's photogrammetric mesh from its aerial photos of 2017 or 2024 (3D Tiles, CC BY 4.0), streamed from the
// city's server as a view of its own: the coloured blocks, land and names hide. Loaded on first use. (2015's mesh is
// glTF 1.0, which three.js no longer reads.)
// [tileset, metres to drop it by]: 2024's heights are N2000 written as heights above the ellipsoid (the sea reads
// 0.2–0.4 m); 2017's are true heights above the ellipsoid, 17.6 m higher (the geoid): dropped by that, the two
// meshes meet to within 0.1 m by the cathedral and in Vuosaari, 11 km apart.
// Then the screen error to refine past: 2017's tiles give errors a tenth of 2024's for the same size of photo pixel
// (0.25 m for 0.12 m pixels, 3.3 m for 0.21 m), so it stopped three levels coarse under the default 16.
const PHOTOS = {
  2017: ['https://kartta.hel.fi/3d/mesh/Helsinki_2017/tileset.json', 17.6, 1.6],
  2024: ['https://kartta.hel.fi/3d/mesh/Helsinki_2024/2/tileset.json', 0, 16],  // 1/ is an untextured floor
};
const DEG = THREE.MathUtils.DEG2RAD;
let photo = null, photoLoad = null, photoOn = false, photoYear = 2024;
async function loadPhoto() {
  const [{ TilesRenderer, WGS84_ELLIPSOID: E }, { GLTFLoader }, { DRACOLoader }] = await Promise.all([
    import('./vendor/3d-tiles-renderer/index.three.js'),
    import('three/addons/loaders/GLTFLoader.js'),
    import('three/addons/loaders/DRACOLoader.js'),
  ]);
  const [url, geoid, errorTarget] = PHOTOS[photoYear], tiles = new TilesRenderer(url);
  tiles.errorTarget = errorTarget;
  const draco = new DRACOLoader().setDecoderPath('vendor/three-addons/libs/draco/');
  tiles.manager.addHandler(/\.gltf$/, new GLTFLoader(tiles.manager).setDRACOLoader(draco));  // b3dm tiles, Draco-packed
  // Globe to map: east, up and south at Senaatintori, turned by the meridian convergence so that x and z follow the
  // ETRS-GK25 grid (central meridian 25° E). One turn holds to 7 cm across the city.
  const lat = 60.1694 * DEG, lon = 24.9527 * DEG, g = (lon - 25 * DEG) * Math.sin(lat), c = Math.cos(g), s = Math.sin(g);
  const toMap = new THREE.Matrix4().set(c, -s, 0, 0, 0, 0, 1, 0, -s, -c, 0, 0, 0, 0, 0, 1)
    .multiply(E.getEastNorthUpFrame(lat, lon, 0, new THREE.Matrix4()).invert());
  const fromMap = toMap.clone().invert();
  toMap.decompose(tiles.group.position, tiles.group.quaternion, tiles.group.scale);
  // The globe curves away under the flat map, 10 m by Vuosaari: each tile is stood upright about its centre and
  // lifted to that centre's height above sea level.
  const box = new THREE.Box3(), mid = new THREE.Vector3(), up = new THREE.Vector3(), geo = {}, turn = new THREE.Matrix4();
  tiles.addEventListener('load-model', ({ scene }) => {
    E.getPositionToCartographic(box.setFromObject(scene).getCenter(mid), geo);
    E.getCartographicToNormal(geo.lat, geo.lon, up).transformDirection(toMap);
    mid.applyMatrix4(toMap);
    turn.makeRotationFromQuaternion(new THREE.Quaternion().setFromUnitVectors(up, new THREE.Vector3(0, 1, 0)))
      .premultiply(new THREE.Matrix4().makeTranslation(mid.x, geo.height - geoid, mid.z))
      .multiply(new THREE.Matrix4().makeTranslation(-mid.x, -mid.y, -mid.z));
    scene.matrix.premultiply(toMap).premultiply(turn).premultiply(fromMap);
    scene.matrix.decompose(scene.position, scene.quaternion, scene.scale);
    // The photos are sRGB and drawn as they are, like every other colour here; streets and walls are seen at a slant.
    scene.traverse(o => { if (o.material?.map) Object.assign(o.material.map, { colorSpace: THREE.NoColorSpace, anisotropy: 8 }); });
  });
  // Every tile carries a 1024² photo, some 5 MB once drawn, and a close look at the centre takes ~130 of them (750 MB).
  // The default 0.4 GB fills at 86 and refuses the finer ones, which leaves the near city blurred. Phones keep it.
  if (!phone.matches) Object.assign(tiles.lruCache, { minBytesSize: 0.75 * 2 ** 30, maxBytesSize: 2 ** 30 });
  tiles.setCamera(camera);
  tiles.setResolutionFromRenderer(camera, renderer);
  scene.add(tiles.group);
  return photo = tiles;
}
async function setPhoto(on) {
  photoOn = on;
  document.body.classList.toggle('photo', on);
  if (on && streetsOn) setStreets(false);
  if (on && viewOn) setView(false);
  markTabs(); drawPicks();
  showCity();
  if (on) { if (playing) stopPlay(); pinCard(-1); }
  if (on || photoLoad) (await (photoLoad ??= loadPhoto())).group.visible = photoOn;
}
// Another year's mesh replaces the one shown: two would hold two gigabytes.
async function setPhotoYear(y) {
  photoYear = y;
  document.querySelectorAll('.photo-years button').forEach(b => b.setAttribute('aria-pressed', +b.dataset.year === y));
  const old = photoLoad;
  photoLoad = photo = null;
  const t = await old;
  if (t) { scene.remove(t.group); t.dispose(); }
  if (photoOn) setPhoto(true);
}
document.querySelectorAll('.photo-years button').forEach(b => b.onclick = () => +b.dataset.year !== photoYear && setPhotoYear(+b.dataset.year));
// A click in the aerial view finds the point it hits, then the block standing under that point: the building's
// footprint decides, wherever the ground lies.
const ray = new THREE.Raycaster();
ray.firstHitOnly = true;
function pickPhoto(x, y) {
  ray.setFromCamera(new THREE.Vector2(x / canvas.clientWidth * 2 - 1, 1 - y / canvas.clientHeight * 2), camera);
  const hit = photo && ray.intersectObject(photo.group, true)[0];
  if (!hit) return -1;
  ray.set(new THREE.Vector3(hit.point.x, 2000, hit.point.z), new THREE.Vector3(0, -1, 0));
  const b = ray.intersectObjects(meshes, false)[0];
  // vGid in the vertex shader: the attribute texture's fourth channel, two texels per building
  return b ? b.object.userData.draw.uniforms.uAttr.value.image.data[8 * b.object.geometry.attributes.bld.getX(b.face.a) + 3] : -1;
}

// ---------- Maps on the ground ----------
// Under the year's buildings, when switched on (WMS in ETRS-GK25, CC BY 4.0). Old maps and aerial photos follow the
// timeline: the one of that year or the nearest before it. A master plan or a noise survey stays, whatever the year.
// A quadtree of 512 px tiles, each split once its pixels would show larger than the screen's. Outside a map's sheet,
// and where a photo has nothing, the server paints black: left out. Noise comes as PNG, see-through where it is quiet.
const GROUND_WMS = 'https://kartta.hel.fi/ws/geoserver/avoindata/wms';
const GROUND = [  // [year, layer, kind, its button's label if not the year]
  ...[[1749, 'Pitajakuvauskartta_1749'], [1780, 'Rekognosointikartta_1780_1782'], [1820, 'Asemakaavakartta_1820'],
    [1838, 'Asemakaavakartta_1838'], [1870, 'Senaatinkartta_1870'], [1878, 'Asemakaavakartta_1878'],
    [1900, 'Plan_af_Helsingfors_1900'], [1909, 'Kartta_Helsingin_kaupungista_ja_sen_alueista_1909'],
    [1917, 'Helsingin_kaupunki_1917_1918'], [1925, 'Helsingin_kaupungin_kartta_1925'], [1940, 'Helsinki_1940'],
    [1952, 'Helsingin_matkailijakartta_1952'], [1962, 'Helsingin_keskustan_kartta_1962'],
    ...[1965, 1966, 1971, 1975, 1977, 1979, 1983, 1985, 1987, 1989, 1991, 1999].map(y => [y, `Opaskartta_${y}`]),
    [2014, 'Kuvakartta'],  // the last dated one: a bird's-eye drawing of the inner city
    [config.yearMax, 'Opaskartta_Helsinki', 'Today'],  // today's guide map, which the city keeps up to date
  ].map(([y, src, label]) => [y, src, 'map', label]),  // 1917, 1940, 1952, 1962 and 2014 show the centre only
  ...[...[1932, 1943, 1950, 1964, 1969, 1976, 1988, 1996].map(y => [y, `Ortoilmakuva_${y}`]),
    [2008, 'Ortoilmakuva_2008_25cm'], [2017, 'Ortoilmakuva_2017_20cm'], [2021, 'Ortoilmakuva_2021_10cm'],
    [2025, 'Ortoilmakuva_2025_5cm'],
  ].map(g => [...g, 'photo']),  // years whose photo covers the city; the rest cover a strip or leave holes
  ...[[1923, 'Helsingfors_generalplan_for_stor_helsingfors_1923'], [1932, 'Helsingin_kaupungin_keskiosien_yleiskaavaehdotus_1932'],
    [1960, 'Helsingin_yleiskaavaehdotus_1960'], [1972, 'Tarkistettu_maankaytto_v_1980_1972'], [1992, 'Helsingin_yleiskaava_1992'],
    [2002, 'Yleiskaava_2002'], [2016, 'Yleiskaava_2016']].map(g => [...g, 'plan']),
  ...[[2012, 'Meluselvitys_2012_alue_01_tieliikenne_L_Aeq_paiva'], [2017, 'Meluselvitys_2017_alue_01_tieliikenne_L_Aeq_paiva'],
    [2022, 'Meluselvitys_2022_Helsinki_kadut_ja_maantiet_LAeq_7-22_NPM']].map(g => [...g, 'noise']),  // 2007's covers part of the city, on another scale
];
const GROUND_KINDS = [['map', 'Old maps'], ['photo', 'Aerial photos'], ['plan', 'Plans'], ['noise', 'Noise']];
// The Map menu: the scale model, the city with nothing under it; the aerial view's 3D model in its place; then each
// kind of map under the buildings.
const MAP_KINDS = [['', 'Scale model'], ['aerial', 'Aerial 3D'], ...GROUND_KINDS];
const PLAN_NAMES = { 1923: 'General plan for Greater Helsinki', 1932: 'Master plan proposal for the central city',
  1960: 'Master plan proposal', 1972: 'Revised land use for 1980', 1992: 'Master plan', 2002: 'Master plan', 2016: 'Master plan' };
// The surveys' own colours from 40 dB up in steps of 5, as their legends draw them; 2012's go on to 80 and 85.
const NOISE_COLORS = ['#dbff91', '#b9ff4c', '#4cb94c', '#ffff4c', '#ffe391', '#ffb94c', '#ff4c4c', '#b94cff', '#704c70', '#5e4c5e'];
const GROUND_ROOT = 65536, GROUND_PX = 512;
const GROUND_SHADER = {
  glslVersion: THREE.GLSL3,
  depthTest: false,  // drawn after the land and water, over them; the buildings come after and stand on it
  // see-through noise blends without joining the transparent pass, which would draw it over the buildings
  blending: THREE.CustomBlending, blendSrc: THREE.SrcAlphaFactor, blendDst: THREE.OneMinusSrcAlphaFactor,
  vertexShader: 'out vec2 vUv; void main() { vUv = uv; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }',
  fragmentShader: `precision highp float; uniform sampler2D map; uniform bool clear; in vec2 vUv; out vec4 outColor;
    void main() {
      vec4 c = texture(map, vUv);
      if (clear ? c.a < 0.02 : max(c.r, max(c.g, c.b)) < 0.035) discard;
      outColor = clear ? c : vec4(c.rgb, 1.0);
    }`,
};
const ground = new THREE.Group();
scene.add(ground);
land.renderOrder = water.renderOrder = -2;
const groundTiles = new Map(), groundLoader = new THREE.TextureLoader();
const groundGeo = new THREE.PlaneGeometry(1, 1).rotateX(-Math.PI / 2);
let groundOn = false, groundSrc = null, groundPrev = null;
let groundPick = 'photo';  // 'map' or 'photo' to follow the timeline, or the plan or noise survey chosen
function groundShown() {
  if (typeof groundPick !== 'string') return groundPick;
  const Y = uniforms.uYear.value, last = k => GROUND.findLast(([y, , kind]) => kind === k && y <= Y);
  return last(groundPick) ?? last('map');  // before the first photo, the map
}

function groundTile(src, L, i, j, load) {
  const key = `${src}/${L}/${i}/${j}`;
  let t = groundTiles.get(key);
  if (!t && load) {
    const s = GROUND_ROOT / 2 ** L, x = -GROUND_ROOT / 2 + i * s, z = -GROUND_ROOT / 2 + j * s;
    const e = config.origin[0] + x, n = config.origin[1] - z;  // west and north edges; WMS 1.3.0 puts northing first
    const clear = src.startsWith('Melu');
    groundTiles.set(key, t = { mesh: null, ready: false, used: 0 });
    groundLoader.load(`${GROUND_WMS}?service=WMS&version=1.3.0&request=GetMap&layers=avoindata:${src}&styles=&crs=EPSG:3879` +
      `&bbox=${n - s},${e},${n},${e + s}&width=${GROUND_PX}&height=${GROUND_PX}` +
      (clear ? '&format=image/png&transparent=true' : '&format=image/jpeg&bgcolor=0x000000'), tex => {
      Object.assign(tex, { colorSpace: THREE.NoColorSpace, anisotropy: 8 });
      t.mesh = new THREE.Mesh(groundGeo, new THREE.ShaderMaterial({ ...GROUND_SHADER, uniforms: { map: { value: tex }, clear: { value: clear } } }));
      t.mesh.position.set(x + s / 2, 0.1, z + s / 2);
      t.mesh.scale.set(s, 1, s);
      t.mesh.renderOrder = -1;
      ground.add(t.mesh);
      t.ready = true;
    }, undefined, () => { t.ready = true; });
  }
  if (t) t.used = frame;
  return t;
}

const frustum = new THREE.Frustum(), gbox = new THREE.Box3(), projView = new THREE.Matrix4();
function inView(L, i, j) {
  const s = GROUND_ROOT / 2 ** L, x = -GROUND_ROOT / 2 + i * s, z = -GROUND_ROOT / 2 + j * s;
  gbox.min.set(x, 0, z); gbox.max.set(x + s, 1, z + s);
  return frustum.intersectsBox(gbox);
}
function updateGround() {
  ground.visible = groundOn && !photoOn;
  if (!ground.visible) return;
  const src = groundShown()?.[1] ?? null;
  if (src !== groundSrc) { groundPrev = groundSrc; groundSrc = src; drawGroundBox(); }
  for (const m of ground.children) m.visible = false;
  if (!src) return;
  frustum.setFromProjectionMatrix(projView.multiplyMatrices(camera.projectionMatrix, camera.matrixWorldInverse));
  const f = canvas.clientHeight / (2 * Math.tan(camera.fov * DEG / 2)), maxL = src.startsWith('Orto') ? 9 : 8;
  const visit = (L, i, j) => {
    if (!inView(L, i, j)) return;
    const t = groundTile(src, L, i, j, true), s = GROUND_ROOT / 2 ** L;
    if (L < maxL && s * f / Math.max(1, gbox.distanceToPoint(camera.position)) > GROUND_PX) {
      const kids = [[0, 0], [1, 0], [0, 1], [1, 1]].map(([a, b]) => [L + 1, 2 * i + a, 2 * j + b]).filter(k => inView(...k));
      // Split once every child in view has arrived; until then this tile stands in for them.
      if (kids.map(k => groundTile(src, ...k, true)).every(k => k.ready)) return kids.forEach(k => visit(...k));
    }
    // A new year's tile still on its way: the year before's stays where it was.
    const shown = t.ready ? t : groundPrev && groundTile(groundPrev, L, i, j, false);
    if (shown?.mesh) shown.mesh.visible = true;
  };
  visit(0, 0, 0);
  if (groundTiles.size > 240) {  // some 1.4 MB each on the GPU
    for (const [k, t] of [...groundTiles].filter(([, t]) => t.ready).sort((a, b) => a[1].used - b[1].used).slice(0, 80)) {
      if (t.mesh) { ground.remove(t.mesh); t.mesh.material.uniforms.map.value.dispose(); t.mesh.material.dispose(); }
      groundTiles.delete(k);
    }
  }
}
const groundBox = document.getElementById('ground-box');
let mapAlone = false, groundFolded = false;
function setGround(on) {
  groundOn = on;
  groundBox.hidden = !on;
  if (on) collapsePanelOnPhone();  // the legend's sheet would cover the years
  showCity(); drawGroundBox(); drawPicks();
}
// A kind from the Map menu: a map or photo takes the timeline to its first year when it has none so early; a plan or
// survey starts at the latest. '' is the scale model.
function pickGround(k) {
  if (k === 'aerial') { setGround(false); setPhoto(true); return; }
  if (photoOn) setPhoto(false);
  if (k === 'map' || k === 'photo') {
    groundPick = k;
    const first = GROUND.find(e => e[2] === k);
    if (uniforms.uYear.value < first[0]) setGroundYear(first[0]);
  } else if (k) groundPick = GROUND.findLast(e => e[2] === k);
  setGround(!!k);
}
const groundKind = () => !groundOn ? '' : typeof groundPick === 'string' ? groundPick : groundPick[2];
// The city drawn over the ground: hidden in the aerial view, and under a map when the map is to be seen alone.
function showCity() {
  flat.visible = !photoOn;
  blocks.visible = labelGroup.visible = !photoOn && !(groundOn && mapAlone);
  if (viewOn && ERAS[viewEra].alone) blocks.visible = false;  // the parking fines' streets alone
}
function setGroundYear(y) {
  stopPlay();
  uniforms.uYear.value = y;
  uniforms.uYearFrom.value = Math.min(uniforms.uYearFrom.value, y - 1);
  drawHist();
}
// The chosen kind's years at the side: a map or photo takes the timeline to its year, a plan or survey stays put. The
// one lying on the ground is marked, and drawn again whenever the timeline brings another. Its title folds it away.
function drawGroundBox() {
  const g = groundOn && groundShown(), kind = groundKind();
  if (!kind) return;
  const focused = groundBox.contains(document.activeElement) && { ...document.activeElement.dataset };
  const top = g?.[0] === 2012 ? 10 : 8;
  groundBox.classList.toggle('folded', groundFolded);
  groundBox.innerHTML = `<button class="box-fold" data-fold="1" aria-expanded="${!groundFolded}">${t(GROUND_KINDS.find(([k]) => k === kind)[1])}</button>
    <div class="box-body"${groundFolded ? ' hidden' : ''}><p>${t({ plan: 'What Helsinki was meant to become: the city\'s master plans and their proposals.',
      noise: 'Road traffic noise by day (LAeq 7–22), as each year\'s survey found it.' }[kind] ||
      'Pick a year, or drag the timeline: the map changes with it.')}</p>
    <div class="ground-years">${GROUND.map((e, i) => e[2] !== kind ? '' :
      `<button data-i="${i}" aria-pressed="${e === g}">${e[3] ? t(e[3]) : e[0]}</button>`).join('')}</div>
    ${kind === 'plan' && g ? `<p class="ground-name">${t(PLAN_NAMES[g[0]])} ${g[0]}</p>` : ''}
    ${kind === 'noise' && g ? `<div class="noise-scale" aria-label="dB">${NOISE_COLORS.slice(0, top).map((c, i) =>
      `<span><i style="background:${c}"></i>${40 + 5 * i}${i === top - 1 ? '+' : ''}</span>`).join('')}</div>` : ''}
    <label><input type="checkbox"${mapAlone ? ' checked' : ''}> ${t('Hide the buildings')}</label></div>`;
  groundBox.querySelector('.box-fold').onclick = () => { groundFolded = !groundFolded; drawGroundBox(); };
  groundBox.querySelectorAll('[data-i]').forEach(b => b.onclick = () => {
    const e = GROUND[+b.dataset.i];
    if (e[2] === 'map' || e[2] === 'photo') { groundPick = e[2]; setGroundYear(e[0]); } else groundPick = e;
    drawGroundBox();
  });
  groundBox.querySelector('input').onchange = e => { mapAlone = e.target.checked; if (mapAlone) pinCard(-1); showCity(); };
  if (focused) groundBox.querySelector(focused.i ? `[data-i="${focused.i}"]` : focused.fold ? '.box-fold' : 'input')?.focus();
}

// ---------- Street names, then and now ----------
// The city's street areas on the ground, a tab of their own (pipeline/s07_labels.py, streetmap.*): blue where the
// place-name register's history gives the street a former name. The buildings fade, always in their periods, and take
// no clicks; a click on a street opens its names.
const STREET_COLORS = ['#3d7fd9', '#d3d0c6'];  // with a former name, without
let streetMap = null, streetLoad = null, streetsOn = false, pinnedStreet = null;
async function loadStreets() {
  const [geo, meta] = await Promise.all([loadPolygons('data/streetmap.bin'), fetch('data/streetmap.json').then(r => r.json())]);
  // ShapeGeometry gives a group per polygon: kept to find the clicked one, and drawn as two, those with a former
  // name (the first meta.old polygons) and the rest.
  const polys = geo.groups.slice(), split = polys[meta.old]?.start ?? geo.index.count;
  geo.clearGroups();
  geo.addGroup(0, split, 0);
  geo.addGroup(split, geo.index.count - split, 1);
  const mat = color => new THREE.MeshBasicMaterial({ color, transparent: true, opacity: 0.85, depthWrite: false });
  const mesh = new THREE.Mesh(geo, STREET_COLORS.map(mat));
  const picked = new THREE.Mesh(new THREE.BufferGeometry().setAttribute('position', geo.attributes.position), mat('#163a7a'));
  mesh.position.y = 0.15;
  picked.position.y = 0.2;
  picked.visible = false;
  flat.add(mesh, picked);
  return streetMap = { ...meta, polys, mesh, picked };
}
const streetsBtn = document.querySelector('.streets-mode');
function setStreets(on) {
  if (on && viewOn) setView(false);
  streetsOn = on;
  uniforms.uPale.value = on ? 1 : 0;
  uniforms.uHover.value = -1;
  if (on) {
    if (photoOn) setPhoto(false);
    uniforms.uMode.value = MODE.period;
    maskTarget = periods.map(() => 1);
  }
  markTabs();
  pinCard(-1);
  renderPanel(); drawHist();
  // the legend counts the streets once they have loaded
  if (on || streetLoad) (streetLoad ??= loadStreets()).then(s => { s.mesh.visible = streetsOn; renderPanel(); });
}
streetsBtn.onclick = () => setStreets(!streetsOn);
// One tab pressed: the street-name, war and aerial views stand over the colourings.
function markTabs() {
  const m = { [MODE.solar]: MODE.energy, [MODE.heat]: MODE.energy, [MODE.gone]: MODE.period }[uniforms.uMode.value] ?? uniforms.uMode.value;
  document.querySelectorAll('.modes button[data-mode]').forEach(b => b.setAttribute('aria-pressed', !photoOn && !streetsOn && !viewOn && +b.dataset.mode === m));
  streetsBtn.setAttribute('aria-pressed', streetsOn);
  warPick.classList.toggle('on', viewOn && ERAS[viewEra].menu === 'war');
  otherPick.classList.toggle('on', viewOn && ERAS[viewEra].menu === 'other');
}
// The street under the pointer, in the street-name view's mesh or the parking fines' (they share the street areas).
function pickStreet(x, y, mesh = streetMap?.mesh) {
  if (photoOn || !mesh) return null;
  ray.setFromCamera(new THREE.Vector2(x / canvas.clientWidth * 2 - 1, 1 - y / canvas.clientHeight * 2), camera);
  const hit = ray.intersectObject(mesh, false)[0];
  if (!hit) return null;
  const i = hit.faceIndex * 3, ps = streetMap.polys;
  let lo = 0, hi = ps.length - 1;  // the last polygon starting at or before the hit triangle
  while (lo < hi) { const m = (lo + hi + 1) >> 1; if (ps[m].start <= i) lo = m; else hi = m - 1; }
  return streetMap.names[streetMap.of[lo]];
}
// Its former names first, then why it is so named and the full history they were read from.
function streetHtml(name) {
  const [why, story, former = [], sv] = streetNames[name] || [];
  return `<button class="card-close" aria-label="Close">×</button>
    <header class="card-head"><h3>${esc(name)}</h3>${sv ? `<p class="sv" lang="sv">${esc(sv)}</p>` : ''}</header>
    ${former.length ? `<section><h4>${t('Earlier names')}</h4><ul class="former" lang="fi">${former.map(([n, w]) =>
      `<li><b>${esc(n)}</b>${w ? ` <span>${esc(w)}</span>` : ''}</li>`).join('')}</ul>
      <p class="why">${t('Read out of the history of the name in the place-name register.')}</p></section>` : ''}
    <section class="naming">${why || story ? `<h4>${t(why ? 'Named after, in Finnish' : 'History of the name')}</h4><p class="why" lang="fi">${esc(why || story)}</p>
      ${why && story ? `<details${former.length ? '' : ' open'}><summary>${t('History of the name')}</summary><p class="why" lang="fi">${esc(story)}</p></details>` : ''}`
      : `<p class="why">${t('The place-name register gives no explanation.')}</p>`}</section>
    <section class="sources"><h4>${t('Read more')}</h4><p>${link(NAMES_URL(), t('Helsinki place names'))}, CC BY 4.0</p></section>`;
}
// A street's own polygons, drawn over the rest in a colour of their own.
function markStreet(name, color) {
  const k = streetMap.names.indexOf(name), idx = streetMap.mesh.geometry.index.array, sel = [];
  streetMap.of.forEach((n, p) => { if (n === k) for (let i = streetMap.polys[p].start, e = i + streetMap.polys[p].count; i < e; i++) sel.push(idx[i]); });
  streetMap.picked.geometry.setIndex(sel);
  streetMap.picked.material.color.set(color);
  streetMap.picked.visible = true;
}
function pinStreet(name, x, y) {
  pinCard(-1);
  pinnedStreet = name;
  markStreet(name, '#163a7a');
  card.innerHTML = streetHtml(name);
  card.classList.add('pinned');
  card.hidden = false;
  lastPin = [x, y];
  collapsePanelOnPhone();
  card.querySelector('.card-close').onclick = () => pinCard(-1);
  card.querySelector('details')?.addEventListener('toggle', () => placeCard(x, y));
  placeCard(x, y);
}

// ---------- War and Other ----------
// Views of their own, each chosen from a menu in the bar (pipeline/s11_war.py, s12_other.py): one world war at a time,
// all its sites or one kind of them; public art; the trams. Lines lie on the ground (the land front's, coloured by what
// the survey of 1996 found of them; the tram tracks, by whether they run in the timeline's year), sites are dots
// coloured by kind, each opening a card. The buildings fade and take no clicks, as in the street-name view. The dots
// hang on the land, which the aerial view and the GPU pick leave out, and are made the first time their view opens.
const ERAS = [...war.eras.map(E => ({ menu: 'war', ...E })), ...other.eras];
for (const E of ERAS) for (const K of E.kinds) for (const s of K.sites) Object.assign(s, { kind: K, era: E });
let viewOn = false, viewEra = 0, viewKind = null;  // an index in ERAS; null: every kind of its sites
const warPick = document.querySelector('.war-pick'), otherPick = document.querySelector('.other-pick'), mapPick = document.querySelector('.map-pick');
const PICKS = [warPick, otherPick, mapPick];
const DOT = (() => {
  const c = document.createElement('canvas'), x = c.getContext('2d');
  c.width = c.height = 32;
  x.beginPath(); x.arc(16, 16, 14, 0, 2 * Math.PI); x.fillStyle = '#fff'; x.fill();
  return new THREE.CanvasTexture(c);
})();
async function trenchLines(E) {
  const buf = await (await fetch(`data/${E.lines}`)).arrayBuffer();
  const [nLines, nVerts] = new Uint32Array(buf, 0, 2);
  const start = new Uint32Array(buf, 8, nLines + 1), state = new Uint8Array(buf, 8 + 4 * (nLines + 1), nLines);
  const xz = new Float32Array(buf, 8 + 4 * (nLines + 1) + Math.ceil(nLines / 4) * 4, 2 * nVerts);
  const pos = new Float32Array(3 * nVerts), color = new Float32Array(3 * nVerts), index = [];
  const cols = E.legend.map(g => new THREE.Color(g.color));
  for (let l = 0; l < nLines; l++) for (let v = start[l]; v < start[l + 1]; v++) {
    pos.set([xz[2 * v], 0.3, xz[2 * v + 1]], 3 * v);
    cols[state[l]].toArray(color, 3 * v);
    if (v + 1 < start[l + 1]) index.push(v, v + 1);
  }
  const g = new THREE.BufferGeometry().setAttribute('position', new THREE.BufferAttribute(pos, 3))
    .setAttribute('color', new THREE.BufferAttribute(color, 3)).setIndex(index);
  return new THREE.LineSegments(g, new THREE.LineBasicMaterial({ vertexColors: true }));
}
// The tram tracks, three pixels wide: each line with the years it opened and closed, drawn in use, greyed once closed
// and left out before it opened, by the timeline's year. Redrawn when the year turns (a few thousand segments).
async function trackLines(E) {
  const [{ LineSegments2 }, { LineSegmentsGeometry }, { LineMaterial }] = await Promise.all([
    import('three/addons/lines/LineSegments2.js'), import('three/addons/lines/LineSegmentsGeometry.js'), import('three/addons/lines/LineMaterial.js')]);
  const buf = await (await fetch(`data/${E.tracks}`)).arrayBuffer();
  const [nLines] = new Uint32Array(buf, 0, 2), start = new Uint32Array(buf, 8, nLines + 1), at = 8 + 4 * (nLines + 1);
  const opened = new Int16Array(buf, at, nLines), closed = new Int16Array(buf, at + 2 * nLines, nLines);
  const xz = new Float32Array(buf, at + 4 * nLines, 2 * start[nLines]);
  const [on, off] = E.legend.map(g => col(g.color).toArray());
  const lines = new LineSegments2(new LineSegmentsGeometry(), new LineMaterial({ linewidth: 3, vertexColors: true }));
  lines.update = year => {
    if (Math.floor(year) === lines.year) return;
    lines.year = Math.floor(year);
    const pos = [], color = [];
    for (let l = 0; l < nLines; l++) {
      if (opened[l] > lines.year) continue;
      const c = closed[l] && closed[l] <= lines.year ? off : on;
      for (let v = start[l]; v + 1 < start[l + 1]; v++) {
        pos.push(xz[2 * v], 0.35, xz[2 * v + 1], xz[2 * v + 2], 0.35, xz[2 * v + 3]);
        color.push(...c, ...c);
      }
    }
    lines.geometry.dispose();
    lines.geometry = new LineSegmentsGeometry().setPositions(pos).setColors(color);
  };
  lines.update(uniforms.uYear.value);
  E.trackLines = lines;
  return lines;
}
async function buildEra(E) {
  if (E.built) return;
  E.built = true;
  for (const K of E.kinds) {
    K.obj = new THREE.Group();
    flat.add(K.obj);
    const g = new THREE.BufferGeometry().setAttribute('position', new THREE.Float32BufferAttribute(K.sites.flatMap(s => [s.at[0], 1, s.at[1]]), 3));
    // A white ring under each dot, so it reads on any map; on top of the buildings, so none hides behind one.
    const dots = (px, order, color) => Object.assign(new THREE.Points(g, new THREE.PointsMaterial({ size: px * renderer.getPixelRatio(),
      sizeAttenuation: false, map: DOT, alphaTest: 0.5, depthTest: false, color })), { renderOrder: order });
    K.obj.add(dots(11, 3, '#ffffff'), dots(7, 4, K.color));
  }
  if (E.lines) E.kinds.find(K => K.id === 'structures').obj.add(await trenchLines(E));  // the land front's own lines
  if (E.tracks) E.kinds[0].obj.add(await trackLines(E));
  if (E.streets) E.kinds[0].obj.add(await fineStreets(E));
}
// The parking fines lie on the street areas of the street-name view (pipeline/s12_other.py, fines.json, loaded when
// the view first opens): each street coloured by its fines in the timeline's year, in the steps of E.steps (or E.dense,
// per 100 m), the more the redder, as noise maps go from quiet to loud; a street with none is a pale grey. The ramp is
// one hue, light to dark, each step clearly darker, and its lightest clears the land at 2:1 (dataviz validator,
// ordinal). A click opens its card; the timeline holds to the years there are, and the buildings can be hidden.
const FINE_COLORS = ['#f0957a', '#eb7656', '#e05838', '#cf3d28', '#b2261e', '#8a1418', '#5c0710'];
const FINE_NONE = '#dedbd3';
async function fineStreets(E) {
  const [s, d] = await Promise.all([streetLoad ??= loadStreets(), fetch(`data/${E.streets}`).then(r => r.json())]);
  s.mesh.visible = streetsOn;
  const geo = s.mesh.geometry;  // shared: one material draws every group
  geo.setAttribute('color', new THREE.BufferAttribute(new Float32Array(3 * geo.attributes.position.count), 3));
  E.mesh = new THREE.Mesh(geo, new THREE.MeshBasicMaterial({ vertexColors: true, transparent: true, opacity: 0.9, depthWrite: false }));
  E.mesh.position.y = 0.15;
  E.data = d;
  return E.mesh;
}
const fineYear = E => Math.min(Math.max(Math.floor(uniforms.uYear.value), E.data.years[0]), E.data.years.at(-1));
// A street's measure in the year's i-th place: all its fines, or its fines per 100 m (null where its length is not known).
function fineValue(E, name, i) {
  const n = E.data.streets[name]?.[i]?.[0] || 0, m = E.data.lengths[name];
  return !E.per ? n : n && m ? n / (m / 100) : n ? null : 0;
}
const fineStep = (E, v) => (E.per ? E.dense : E.steps).findLastIndex(t => v >= t);
// Fines per 100 m read best to a decimal while few
const per100 = v => v.toLocaleString(fmtLocale(), { maximumFractionDigits: v < 10 ? 1 : 0 });
function colourFines(E) {
  if (!E.data || `${fineYear(E)}:${!!E.per}` === E.shown) return;
  E.year = fineYear(E);
  E.shown = `${E.year}:${!!E.per}`;
  const i = E.data.years.indexOf(E.year), colors = E.mesh.geometry.attributes.color, idx = E.mesh.geometry.index.array, c = new THREE.Color();
  streetMap.of.forEach((n, p) => {
    const v = fineValue(E, streetMap.names[n], i);
    c.set(v ? FINE_COLORS[fineStep(E, v)] : FINE_NONE);
    for (let k = streetMap.polys[p].start, e = k + streetMap.polys[p].count; k < e; k++) c.toArray(colors.array, 3 * idx[k]);
  });
  colors.needsUpdate = true;
  renderPanel(); drawHist();  // the legend counts the year's streets, the timeline its fines
  if (pinnedSite?.street) pinFine(E, pinnedSite.name, ...lastPin);  // its card, for the new year
}
// A street's card, as a site of the view's one kind: the year's fines, per 100 m too, and commonest reasons; its fines
// year by year.
function fineSite(E, name) {
  const d = E.data, per = d.streets[name] || [], [n = 0, ...top] = per[d.years.indexOf(E.year)] || [], m = d.lengths[name];
  const why = [];
  for (let k = 0; k < top.length; k += 2) why.push(`${d.reasons[top[k]]} (${fmt(top[k + 1])})`);
  const dense = n && m ? ` · ${per100(n / (m / 100))} / 100 m` : '';
  return { kind: E.kinds[0], era: E, name, street: true,
    sub: `${fmt(n)} fine${n === 1 ? '' : 's'} in ${E.year}${dense}`, sub_fi: `${fmt(n)} virhemaksu${n === 1 ? '' : 'a'} vuonna ${E.year}${dense}`,
    text: [m && `The street areas are about ${fmt(m)} m long.`, why.length && `The year's commonest reasons, in Finnish: ${why.join(', ')}.`].filter(Boolean).join(' '),
    text_fi: [m && `Katualueiden pituus on noin ${fmt(m)} m.`, why.length && `Vuoden yleisimmät syyt: ${why.join(', ')}.`].filter(Boolean).join(' '),
    rows: d.years.map((y, j) => [String(y), fmt(per[j]?.[0] || 0)]) };
}
// The fines view's legend: all fines or per 100 m, its years, the year's streets in each step, and the most fined of
// them; per 100 m only streets of 100 m or more are ranked, as a street area of a few metres with a few fines would
// lead it.
function fineLegend(E, row) {
  if (!E.data) return '';
  const d = E.data, y = E.year ?? fineYear(E), i = d.years.indexOf(y), steps = E.per ? E.dense : E.steps, n = steps.map(() => 0), top = [];
  let none = streetMap.names.length;
  for (const name of Object.keys(d.streets)) {
    const v = fineValue(E, name, i);
    if (v) { n[fineStep(E, v)]++; none--; if (!E.per || d.lengths[name] >= 100) top.push([v, name]); }
  }
  top.sort((a, b) => b[0] - a[0]);
  const label = j => E.per ? (j === 0 ? `${t('under')} ${steps[1]}` : j === steps.length - 1 ? `${steps[j]}+` : `${steps[j]}–${steps[j + 1]}`)
    : j === steps.length - 1 ? `${fmt(steps[j])}+` : `${fmt(steps[j])}–${fmt(steps[j + 1] - 1)}`;
  return `<div class="sub" role="group" aria-label="${t('Fines on the street')}">${[false, true].map(x => `
      <button data-fine-per="${x}" aria-pressed="${!!E.per === x}">${t(x ? 'Per 100 m' : 'In all')}</button>`).join('')}</div>
    <label class="fine-alone"><input type="checkbox"${E.alone ? ' checked' : ''}> ${t('Hide the buildings')}</label>
    <p class="note">${LANG === 'fi' ? `Vuonna ${y} ${fmt(d.totals[i])} virhemaksua, joista ${fmt(d.mapped[i])} kartan kaduilla.`
      : `${fmt(d.totals[i])} fines in ${y}, ${fmt(d.mapped[i])} of them on the map's streets.`}</p>
    <h2 class="section">${t(E.per ? 'Fines per 100 m' : 'Fines on the street')}</h2><div class="energy-scale">${steps.map((_, j) => row(FINE_COLORS[j], label(j), n[j])).reverse().join('')}
      ${row(FINE_NONE, t('No fines'), none)}</div>
    <h2 class="section">${t('Most fined streets')}${E.per ? ` <span class="note">${t('100 m or longer')}</span>` : ''}</h2><ul class="stories">${top.slice(0, 20).map(([v, name]) => `
      <li><button class="story" data-fine="${esc(name)}"><b>${esc(name)}</b><span>${E.per ? `${per100(v)} / 100 m` : fmt(v)}</span></button></li>`).join('')}</ul>`;
}
function pinFine(E, name, x, y) {
  pinSite(fineSite(E, name), x, y);
  markStreet(name, '#ec0000');
}
function streetCentre(name) {
  const k = streetMap.names.indexOf(name), idx = streetMap.mesh.geometry.index.array, pos = streetMap.mesh.geometry.attributes.position;
  const box = new THREE.Box3();
  streetMap.of.forEach((n, p) => { if (n === k) for (let i = streetMap.polys[p].start, e = i + streetMap.polys[p].count; i < e; i++)
    box.expandByPoint(new THREE.Vector3().fromBufferAttribute(pos, idx[i])); });
  return box.getCenter(new THREE.Vector3());
}
function setView(on) {
  if (on && streetsOn) setStreets(false);
  viewOn = on;
  uniforms.uPale.value = on ? 1 : 0;
  uniforms.uHover.value = -1;
  if (on) {
    if (photoOn) setPhoto(false);
    uniforms.uMode.value = MODE.period;
    maskTarget = periods.map(() => 1);
    buildEra(ERAS[viewEra]);
    const span = ERAS[viewEra].span;  // the parking fines' years: the timeline holds to them
    if (span) { stopPlay(); uniforms.uYear.value = Math.min(Math.max(Math.floor(uniforms.uYear.value), span[0]), span[1]); }
  }
  markTabs();
  pinCard(-1);
  showCity();
  renderPanel(); drawHist(); drawPicks();
}
const viewNow = () => viewOn && !photoOn ? ERAS[viewEra] : null;
const fineView = () => viewNow()?.streets ? viewNow() : null;
const viewKinds = E => E.kinds.filter(K => !viewKind || (K.group || K.id) === viewKind);  // a kind, or a group of them
const viewShown = () => viewNow() ? viewKinds(viewNow()) : [];
function showView() {
  const shown = viewShown();
  viewNow()?.trackLines?.update(uniforms.uYear.value);
  if (viewNow()?.streets) colourFines(viewNow());
  for (const E of ERAS) for (const K of E.kinds) if (K.obj) K.obj.visible = shown.includes(K);
  if (pinnedSite && !shown.includes(pinnedSite.kind)) pinCard(-1);  // its war or kind is no longer shown
}
// The menus in the bar: the war and the kinds of its sites, the other views, and the map under the buildings. A view
// whose kinds are not choices of their own (public art, by period) is one item. A choice closes its menu, as does a
// click anywhere else.
function drawPicks() {
  for (const [pick, menu, title] of [[warPick, 'war', 'War'], [otherPick, 'other', 'Other']]) {
    pick.classList.toggle('on', viewOn && ERAS[viewEra].menu === menu);
    pick.querySelector('summary').textContent = t(title);  // which one: the menu marks it, the legend names it
    const item = (e, K, label) => `<button data-view="${e}:${K ? K.id : ''}" aria-pressed="${viewOn && viewEra === e && viewKind === (K ? K.id : null)}">${label}</button>`;
    pick.querySelector('.menu').innerHTML = ERAS.map((E, e) => {
      if (E.menu !== menu) return '';
      // one item per kind, or per group of kinds
      const kinds = E.kinds.filter(K => K.menu !== false).filter((K, i, all) => !K.group || all.findIndex(o => o.group === K.group) === i)
        .map(K => K.group ? { id: K.group, ...E.groups[K.group] } : K);
      return kinds.length ? `<p class="menu-head">${esc(tr(E, 'label'))} · ${esc(tr(E, 'years'))}</p>${item(e, null, t('Everything'))}${
        kinds.map(K => item(e, K, esc(t(tr(K, 'label'))))).join('')}` : item(e, null, esc(tr(E, 'label')));
    }).join('');
  }
  const k = photoOn ? 'aerial' : groundKind();
  const item = ([x, label]) => `<button data-ground="${x}" aria-pressed="${x === k}">${t(label)}</button>`;
  mapPick.classList.toggle('on', photoOn);  // a view of its own, like War
  mapPick.querySelector('summary').innerHTML = `${t('Map')}: <b>${t(MAP_KINDS.find(([x]) => x === k)[1])}</b>`;
  mapPick.querySelector('.menu').innerHTML = MAP_KINDS.slice(0, 2).map(item).join('') +
    `<p class="menu-head">${t('Under the buildings')}</p>${GROUND_KINDS.map(item).join('')}`;
}
for (const pick of [warPick, otherPick]) pick.querySelector('.menu').onclick = e => {
  const b = e.target.closest('[data-view]');
  if (!b) return;
  const [era, kind] = b.dataset.view.split(':');
  viewEra = +era; viewKind = kind || null; pick.open = false;
  setView(true);
};
mapPick.querySelector('.menu').onclick = e => {
  const b = e.target.closest('[data-ground]');
  if (b) { mapPick.open = false; pickGround(b.dataset.ground); }
};
addEventListener('pointerdown', e => { for (const d of PICKS) if (d.open && !d.contains(e.target)) d.open = false; });
for (const d of PICKS) d.addEventListener('toggle', () => { if (d.open) for (const o of PICKS) if (o !== d) o.open = false; });
addEventListener('keydown', e => { if (e.key === 'Escape') for (const d of PICKS) d.open = false; });
// The dot nearest the pointer, within a few pixels.
const sv = new THREE.Vector3();
function pickSite(x, y) {
  let best = null, bd = 12 ** 2;
  for (const s of viewShown().flatMap(K => K.sites)) {
    sv.set(s.at[0], 1, s.at[1]).project(camera);
    if (sv.z > 1) continue;
    const d = ((sv.x + 1) / 2 * canvas.clientWidth - x) ** 2 + ((1 - sv.y) / 2 * canvas.clientHeight - y) ** 2;
    if (d < bd) { bd = d; best = s; }
  }
  return best;
}
// The survey's, the register's and the museum's own words are Finnish, and stay so. Photos browse as a building's do.
function siteHtml(s, pinned) {
  const K = s.kind, S = s.source || K.source, n = s.photos?.length;  // a site may name a source of its own
  // each photo credits its maker and its museum (o: the Heritage Agency and its collection; else the City Museum)
  slides = (s.photos || []).map((a, i) => ({ src: FINNA_IMG(a.r), label: n > 1 ? `${i + 1}/${n}` : String(a.y || ''), year: a.y, page: FINNA_PAGE(a.r),
    credit: `${[a.t, a.y, a.m].filter(Boolean).map(esc).join(', ')}, ${pinned
      ? `${link(FINNA_PAGE(a.r), a.o || 'Helsingin kaupunginmuseo')}, ${link(LICENCE[a.l], a.l)}` : `${esc(a.o || 'Helsingin kaupunginmuseo')}, ${esc(a.l)}`}` }));
  slide = 0;
  // a kind whose photos are too large to fetch on a hover (SA-kuva's originals) shows them once the card is pinned
  return `<button class="card-close" aria-label="${t('Close')}">×</button>${slides.length && (pinned || !K.large) ? figureHtml(pinned) : ''}
    <header class="card-head"><h3>${esc(tr(s, 'name'))}</h3>${tr(s, 'sub') ? `<p class="sv">${esc(tr(s, 'sub'))}</p>` : ''}</header>
    ${s.rows ? `<section><dl>${s.rows.map(([k, v]) => `<dt>${t(k)}</dt><dd lang="fi">${esc(v)}</dd>`).join('')}</dl></section>` : ''}
    ${tr(s, 'text') ? `<section><p class="why">${esc(tr(s, 'text'))}</p></section>` : ''}
    <section class="sources"><h4>${t('Source')}</h4><p>${link(tr(s, 'url') || tr(S, 'url'), tr(S, 'label'))}${S.licence ? `, ${S.licence}` : ''}</p></section>`;
}
let hoverSite = null, pinnedSite = null;
function showSite(s, x, y) {
  if (pinnedGid >= 0 || pinnedStreet || pinnedSite || phone.matches) return;
  if (s !== hoverSite || card.hidden) {
    hoverSite = s; hoverGid = -1;
    card.innerHTML = siteHtml(s, false);
    wireSlides();
    card.classList.remove('pinned');
    card.hidden = false;
    card.querySelector('img')?.addEventListener('load', () => placeCard(...(pointer || [x, y])));
  }
  placeCard(x, y);
}
// A place of the Heritage Agency's or the SA-kuva photos carries only its first; the rest come from its kind's shard
// (mvphotos, saphotos) when its card opens.
const photoShards = {};
async function allPhotos(s) {
  const url = `data/${s.kind.shards}/${String(s.shard).padStart(2, '0')}.json`;
  const shard = await (photoShards[url] ??= fetch(url).then(r => r.json()));
  s.photos = shard[s.name] || s.photos;
  s.shard = null;
}
function pinSite(s, x, y) {
  pinCard(-1);
  pinnedSite = s;
  if (s.shard != null) allPhotos(s).then(() => { if (pinnedSite === s) pinSite(s, x, y); });
  card.innerHTML = siteHtml(s, true);
  wireSlides();
  card.classList.add('pinned');
  card.hidden = false;
  lastPin = [x, y];
  collapsePanelOnPhone();
  card.querySelector('.card-close').onclick = () => pinCard(-1);
  card.querySelector('img')?.addEventListener('load', () => placeCard(x, y));
  placeCard(x, y);
}

// ---------- Building lookup ----------
const DATE_NOTE = [
  null,
  'The register gives a round decade here, more often than the years around it predict. Read it as “around then”.',
  'The register gives no year, or a placeholder. Estimated from the nearest dated buildings.',
  null,
  'The register gives no year, or a placeholder. Estimated from the other buildings on the same property.',
];
const residentsLayer = layers.find(L => L.id === 'residents');
const contextLayers = layers;
// The card shows residents in their own section, so they are left out of its list of layers.
const groupsByBit = layers.filter(L => L !== residentsLayer).flatMap(L => L.groups.map(g => ({ ...g, layer: L })));

// Layout: pipeline/s03_tiles.py, attrs. `bag` keeps Amsterdam's name: here it is the VTJ-PRT, or the city's feature id.
function building(gid) {
  const o = gid * config.attrStride;
  const lay0 = attrs.getUint32(o + 8, true), lay1 = attrs.getUint32(o + 12, true);
  return {
    gid,
    bag: info.id[gid],
    addr: info.addr[gid],
    height: attrs.getUint16(o, true) / 10,
    fsrc: attrs.getUint8(o + 2),
    flag: attrs.getUint8(o + 3),
    year: attrs.getInt16(o + 4, true),
    orig: attrs.getInt16(o + 6, true),
    wk: attrs.getInt32(o + 16, true),
    use: config.uses[attrs.getUint8(o + 20) - 1],
    floors: attrs.getUint8(o + 21),
    mat: config.materials[attrs.getUint8(o + 22)],
    fac: config.facades[attrs.getUint8(o + 23)],
    x: attrs.getFloat32(o + 24, true),
    z: attrs.getFloat32(o + 28, true),
    gone: attrs.getInt16(o + 32, true),
    eclass: attrs.getUint8(o + 34),
    ever: attrs.getUint8(o + 35),
    eluku: attrs.getUint16(o + 36, true),
    solar: attrs.getInt32(o + 38, true),
    panel: attrs.getUint16(o + 42, true),
    fuel: config.fuels[attrs.getUint8(o + 44)],
    hmethod: config.methods[attrs.getUint8(o + 45)],
    groups: groupsByBit.filter(g => g.bit < 32 ? (lay0 >>> g.bit) & 1 : (lay1 >>> (g.bit - 32)) & 1),
  };
}

const periodOf = y => periods.find(p => y >= p.from && y <= p.to) || periods[0];

// ---------- Building card ----------
// Hover shows a light card that follows the pointer; a click pins it, with the article extract and links.
let wiki = [], didYouKnow = {}, streetNames = {};
fetch('data/wiki.json').then(r => r.json()).then(w => { wiki = w; });
fetch('data/streets.json').then(r => r.json()).then(s => { streetNames = s; }); // {street: [why so named, history]}, s07_labels
fetch('data/facts.json').then(r => r.json()).then(f => { didYouKnow = f; }); // 'Did you know', checked in s11_facts
const REGISTER_URL = () => `https://hri.fi/data/${LANG === 'fi' ? 'fi' : 'en_GB'}/dataset/helsingin-rakennukset`;
const MODEL_URL = () => `https://hri.fi/data/${LANG === 'fi' ? 'fi' : 'en_GB'}/dataset/helsingin-3d-kaupunkimalli`;
const SOLAR_URL = () => `https://hri.fi/data/${LANG === 'fi' ? 'fi' : 'en_GB'}/dataset/paakaupunkiseudun-aurinkosahkopotentiaali`;
const NAMES_URL = () => `https://hri.fi/data/${LANG === 'fi' ? 'fi' : 'en_GB'}/dataset/helsingin-nimisto`;
const ENERGY_URL = 'https://www.energiatodistusrekisteri.fi/';
const mwh = kwh => (kwh / 1000).toLocaleString(fmtLocale(), { maximumFractionDigits: kwh < 10000 ? 1 : 0 });
const esc = s => String(s ?? '').replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const link = (href, text) => `<a href="${esc(href)}" target="_blank" rel="noopener">${esc(text)}</a>`;

// The article in the reader's language when there is one.
const wikiOf = w => (LANG === 'fi' && w?.wiki_fi?.extract ? w.wiki_fi : w?.wiki) || w?.wiki_fi;

function groupColor(g) {
  return GROUP_COLORS[g.layer.groups.findIndex(x => x.bit === g.bit)] || GROUP_COLORS[0];
}

function residentsHtml(b, pinned) {
  const n = residentsLayer?.notes?.[b.bag];
  if (!n) return '';
  const people = pinned ? n.people : n.people.slice(0, 3);
  return `<section><h4>${t('Lived or worked here')}</h4><ul class="residents">${people.map(p => `<li>
    <b>${pinned ? link(p.url, p.person) : esc(p.person)}</b>${p.born ? ` <span>${esc(p.born)}${p.died ? '–' + esc(p.died) : ''}</span>` : ''}
    ${tr(p, 'desc') ? `<div class="desc">${esc(tr(p, 'desc'))}</div>` : ''}
    ${pinned ? (p.quote.startsWith('Wikidata') ? `<p class="why">${esc(t(p.quote))}</p>` : `<blockquote lang="fi">${esc(p.quote)}</blockquote>`) : ''}
    ${p.died && b.year > +p.died + 5 ? `<p class="why">${LANG === 'fi' ? `Rakennus on vuodelta ${b.year}, ajalta jolloin ${esc(p.person.split(' ').slice(-1)[0])} oli jo kuollut; se seisoo talon paikalla.` : `This building dates from ${b.year}, after ${esc(p.person.split(' ').slice(-1)[0])} died; it stands where their house stood.`}</p>` : ''}</li>`).join('')}</ul>
    ${!pinned && n.people.length > 3 ? `<p class="why">${LANG === 'fi' ? 'ja' : 'and'} ${n.people.length - 3} ${LANG === 'fi' ? 'muuta' : 'more'}</p>` : ''}</section>`;
}

// ---------- Photos through the years ----------
// Archive photos of the Helsinki City Museum in Finna (s08_archive), in 64 shards keyed by a CRC-32 of the building id.
const CRC = Array.from({ length: 256 }, (_, n) => { for (let k = 0; k < 8; k++) n = n & 1 ? 0xEDB88320 ^ (n >>> 1) : n >>> 1; return n >>> 0; });
const crc32 = s => { let c = ~0; for (const ch of s) c = CRC[(c ^ ch.charCodeAt(0)) & 255] ^ (c >>> 8); return (~c) >>> 0; };
const archiveShards = {};
function archiveOf(bag, then) {
  if (!config.archive) return [];
  const n = String(crc32(bag) % 64).padStart(2, '0');
  if (archiveShards[n] === undefined) {
    archiveShards[n] = null;
    fetch(`data/archive/${n}.json`).then(r => r.json()).then(d => { archiveShards[n] = d; then(); }).catch(() => {});
  }
  return archiveShards[n]?.[bag] || [];
}
// Images and records straight from Finna, 600 px wide at most: for SA-kuva's photos Finna has no smaller size than
// the original (4,900 px, 4–8 MB), but w= has it scaled down (70 KB).
const FINNA_IMG = id => `https://api.finna.fi/Cover/Show?source=Solr&id=${encodeURIComponent(id)}&index=0&size=medium&w=600`;
const FINNA_PAGE = id => `https://www.finna.fi/Record/${encodeURIComponent(id)}`;
const LICENCE = { 'PDM': 'https://creativecommons.org/publicdomain/mark/1.0/', 'CC0': 'https://creativecommons.org/publicdomain/zero/1.0/',
  'CC BY 4.0': 'https://creativecommons.org/licenses/by/4.0/' };
let slides = [], slide = 0;
// Oldest archive photo first, today's photo (Wikimedia Commons) last; the card opens on the newest.
function photosHtml(b, im, credit, pinned) {
  const archive = archiveOf(b.bag, () => refreshCard(b.gid));
  slides = [...archive.map(a => ({
    src: FINNA_IMG(a.r), label: String(a.y), page: FINNA_PAGE(a.r),
    credit: `${a.y}${a.m ? ', ' + esc(a.m) : ''}, ${pinned
      ? `${link(FINNA_PAGE(a.r), 'Helsingin kaupunginmuseo')}, ${link(LICENCE[a.l], a.l)}` : `Helsingin kaupunginmuseo, ${esc(a.l)}`}`,
  })), ...(im ? [{ src: im.thumb, label: t('Today'), credit: `${t('Photo')}: ${credit}` }] : [])];
  if (!slides.length) return '';
  slide = slides.length - 1;
  const s = slides[slide];
  const span = archive.length && `${archive[0].y}${archive.length > 1 ? '–' + archive.at(-1).y : ''}`;
  const more = !archive.length || pinned ? '' : `<p class="more-photos">${LANG === 'fi'
    ? `+ ${archive.length} arkistokuva${archive.length > 1 ? 'a' : ''}, ${span}. Selaa napsauttamalla`
    : `+ ${archive.length} archive photo${archive.length > 1 ? 's' : ''}, ${span}. Click to browse`}</p>`;
  return figureHtml(pinned, more);
}
function figureHtml(pinned, more = '') {
  const s = slides[slide];
  return `<figure class="photo${s.sv ? ' sv' : ''}"><div class="frame">${s.sv ? `<img data-sv="${esc(s.sv)}" alt="">` : `<img src="${esc(s.src)}" alt="">`}
    ${pinned && slides.length > 1 ? `<button class="prev" aria-label="${t('Earlier')}">‹</button><button class="next" aria-label="${t('Later')}">›</button>` : ''}
    ${slides.length > 1 ? `<span class="year">${s.label}</span>` : ''}</div>
    <figcaption>${s.credit}</figcaption>${pinned && slides.length > 1 ? '<nav class="years"></nav>' : ''}${more}</figure>`;
}
function showSlide(i) {
  const fig = card.querySelector('.photo');
  if (!fig || !slides.length) return;
  slide = Math.max(0, Math.min(i, slides.length - 1));
  const s = slides[slide], img = fig.querySelector('img');
  img.removeAttribute('data-sv');
  img.src = s.sv || s.src;
  fig.classList.toggle('loading', !img.complete);  // the last photo fades until this one has come
  // The photos around it are fetched meanwhile: Finna takes seconds over a photo it has not served before.
  for (const x of [...slides.slice(slide + 1, slide + 4), ...slides.slice(Math.max(0, slide - 2), slide)]) if (!x.sv) new Image().src = x.src;
  fig.classList.toggle('sv', !!s.sv);
  const year = fig.querySelector('.year');
  if (year) year.textContent = s.label;
  fig.querySelector('figcaption').innerHTML = s.credit;
  const nav = fig.querySelector('.years');
  if (nav) {
    // A button a photo; past a dozen, a button a decade, on its first photo (the photos run oldest first).
    const decade = x => x.year ? Math.floor(x.year / 10) * 10 : null, name = d => d == null ? t('Year not known') : LANG === 'fi' ? `${d}-luku` : `${d}s`;
    const marks = slides.length <= 12 ? slides.map((x, k) => [k, x.label, k === slide])
      : slides.map((x, k) => [k, decade(x)]).filter(([, d], i, all) => i === 0 || all[i - 1][1] !== d)
        .map(([k, d]) => [k, name(d), d === decade(slides[slide])]);
    nav.innerHTML = marks.map(([k, label, on]) => `<button data-slide="${k}"${on ? ' aria-current="true"' : ''}>${label}</button>`).join('');
    nav.querySelectorAll('button').forEach(b => b.addEventListener('click', () => showSlide(+b.dataset.slide)));
  }
  fig.querySelector('.prev')?.toggleAttribute('disabled', slide === 0);
  fig.querySelector('.next')?.toggleAttribute('disabled', slide === slides.length - 1);
}
function wireSlides() {
  const fig = card.querySelector('.photo');
  if (!fig) return;
  // A picture that fails to load says so and links to the archive; with nothing else to show the frame goes.
  fig.querySelector('img').addEventListener('error', () => {
    fig.classList.remove('loading');
    if (slides.length < 2) { fig.remove(); return; }
    fig.classList.add('failed');
    fig.querySelector('.frame .gone')?.remove();
    fig.querySelector('.frame').insertAdjacentHTML('afterbegin', `<p class="gone">${t('This photo did not load.')}${
      slides[slide].page ? ` ${link(slides[slide].page, t('Open it in the archive'))}` : ''}</p>`);
  });
  fig.querySelector('img').addEventListener('load', () => { fig.classList.remove('failed', 'loading'); fig.querySelector('.frame .gone')?.remove(); });
  fig.querySelector('.prev')?.addEventListener('click', () => showSlide(slide - 1));
  fig.querySelector('.next')?.addEventListener('click', () => showSlide(slide + 1));
  let x0 = null; // swipe on phones
  fig.addEventListener('touchstart', e => { x0 = e.touches[0].clientX; }, { passive: true });
  fig.addEventListener('touchend', e => { const dx = e.changedTouches[0].clientX - x0; if (Math.abs(dx) > 40) showSlide(slide + (dx < 0 ? 1 : -1)); });
  if (fig.querySelector('.years')) showSlide(slide);
}
// A shard that arrives after the card is drawn redraws the card, if it still shows that building.
function refreshCard(gid) {
  if (card.hidden) return;
  if (pinnedGid === gid) pinCard(gid, ...lastPin);
  else if (hoverGid === gid) { hoverGid = -1; showCard(gid, ...(pointer || lastPin)); }
}

// The card reads top to bottom: photo, name and year; what the building is; the layers it belongs to and why;
// the facts; how its date was found; where to read more.
function cardHtml(gid, pinned) {
  const b = building(gid);
  const w = b.wk >= 0 ? wiki[b.wk] : null;
  const im = w?.image?.thumb ? w.image : null;
  const period = periodOf(b.year);
  const facts = [
    w?.label && b.addr && tr(w, 'label') !== b.addr && [t('Address'), esc(b.addr)],
    b.gone && [t('Demolished'), b.gone],
    b.use && [t('Use'), esc(b.use[LANG])],
    // fsrc: bit 1, floors not in the register; bit 2, height from the floors rather than the 3D city model
    [t('Height'), `${b.height.toLocaleString(fmtLocale(), { maximumFractionDigits: 1 })} m${b.fsrc & 2 ? ` (${t('floors × 3.2 m')})` : ''}`],
    [t('Storeys'), b.fsrc & 1 ? t('not in the register') : b.floors],
    b.mat && [t('Structure'), esc(b.mat[LANG])],
    b.fac && [t('Facade'), esc(b.fac[LANG])],
    w?.architects?.length && [t(w.architects.length > 1 ? 'Architects' : 'Architect'), w.architects.map(esc).join(', ')],
    w?.styles?.length && [t('Style'), (LANG === 'fi' && w.styles_fi?.length ? w.styles_fi : w.styles).map(esc).join(', ')],
    b.eclass && [t('Energy label'), `${'GFEDCBA'[b.eclass - 1]} (${LANG === 'fi' ? `E-luku ${b.eluku}, vuoden 20${b.ever} asteikko` : `E-value ${b.eluku}, 20${b.ever} scale`})`],
    b.solar >= 0 && [t('Solar potential'), b.solar ? (LANG === 'fi' ? `${mwh(b.solar)} MWh vuodessa, ${fmt(b.panel)} m² paneeleja`
      : `${mwh(b.solar)} MWh a year from ${fmt(b.panel)} m² of panels`) : t('no suitable roof')],
    (b.fuel || b.hmethod) && [t('Heating'), esc([b.fuel?.[LANG], b.hmethod?.[LANG].toLowerCase()].filter(Boolean).join(', '))],
    pinned && b.bag.length === 10 && [t('Building ID'), esc(b.bag)],
  ].filter(Boolean);
  // Why the street of its address is so named, in Finnish: the reason first, the older history folded under it.
  const street = b.addr.replace(/\s+\d.*$/, ''), named = pinned && streetNames[street];
  const naming = named && `<section class="naming"><h4>${t('Street name, in Finnish')}</h4><p class="why" lang="fi"><b>${esc(street)}.</b> ${esc(named[0] || named[1])}</p>
    ${named[2]?.length ? `<p class="why"><b>${t('Earlier names')}:</b> <span lang="fi">${named[2].map(([n, w]) => esc(n) + (w ? ` (${esc(w)})` : '')).join(', ')}</span></p>` : ''}
    ${named[0] && named[1] ? `<details><summary>${t('History of the name')}</summary><p class="why" lang="fi">${esc(named[1])}</p></details>` : ''}</section>`;
  const credit = im && (pinned
    ? `${link(im.page || im.thumb, im.artist || 'Wikimedia Commons')}${im.license ? `, ${im.licenseUrl ? link(im.licenseUrl, im.license) : esc(im.license)}` : ''}`
    : `${esc(im.artist || 'Wikimedia Commons')}${im.license ? `, ${esc(im.license)}` : ''}`);
  const sources = [
    wikiOf(w)?.url && `${link(wikiOf(w).url, t(wikiOf(w).lang === 'fi' ? 'Finnish Wikipedia' : 'Wikipedia'))} (${link('https://creativecommons.org/licenses/by-sa/4.0/', 'CC BY-SA 4.0')})`,
    b.gone ? link(MODEL_URL(), t('Helsinki 3D city model')) : link(REGISTER_URL(), t('Helsinki building register')),
    b.eclass && link(ENERGY_URL, t('Energy certificate register')),
    b.solar >= 0 && link(SOLAR_URL(), t('HSY solar potential')),
    naming && link(NAMES_URL(), t('Helsinki place names')),
  ].filter(Boolean);
  const inLayers = b.groups.map(g => {
    const note = g.layer.notes?.[b.bag];
    return `<li><i style="background:${groupColor(g)}"></i><div><b>${esc(tr(g.layer, 'title'))}</b> <span>${esc(tr(g, 'label'))}</span>
      ${pinned && note ? `<p>${esc(tr(note, 'story'))}${note.source ? ` ${link(note.source, t('Source'))}` : ''}</p>` : ''}</div></li>`;
  }).join('');
  // A demolished building's year comes from the 3D city model, not the register, and only ever before its demolition.
  const note = b.gone && b.flag ? 'The 3D city model gives no year. Estimated from the nearest dated buildings, before the year it was demolished.' : DATE_NOTE[b.flag];
  const dating = b.orig && b.orig !== b.year ? `${t(note || '')} ${t(b.gone ? 'The 3D city model gives' : 'The register gives')} ${b.orig}.` : (note && t(note));
  const title = w?.label ? tr(w, 'label') : b.addr || (b.gone ? t('Demolished building') : '');
  return `
    ${pinned ? '<button class="card-close" aria-label="Close">×</button>' : ''}
    ${photosHtml(b, im, credit, pinned)}
    <header class="card-head">
      ${title ? `<h3>${esc(title)}</h3>` : ''}
      <div class="when"><span class="y">${[1, 2, 4].includes(b.flag) ? t('c. ') : ''}${b.year}${b.gone ? `–${b.gone}` : ''}</span>
        <span class="period"><i style="background:${period.color}"></i>${esc(t(period.label))}</span></div>
    </header>
    ${pinned && wikiOf(w)?.extract ? `<section><p class="extract">${esc(wikiOf(w).extract)}</p></section>` : ''}
    ${didYouKnow[b.bag] ? `<section class="fact"><h4>${t('Did you know')}</h4><p>${esc(LANG === 'fi' ? didYouKnow[b.bag].fi : didYouKnow[b.bag].en)}${pinned ? ` ${link(didYouKnow[b.bag].source, t('Source'))}` : ''}</p></section>` : ''}
    ${residentsHtml(b, pinned)}
    ${inLayers ? `<section><h4>${t('In layers')}</h4><ul class="chips">${inLayers}</ul></section>` : ''}
    <section><dl>${facts.map(([k, v]) => `<dt>${k}</dt><dd>${v}</dd>`).join('')}</dl></section>
    ${dating ? `<section><h4>${t('Dating')}</h4><p class="why">${dating}</p></section>` : ''}
    ${naming || ''}
    ${pinned ? `<section class="sources"><h4>${t('Read more')}</h4><p>${sources.join(', ')}</p></section>`
      : `<p class="hint">${w?.wiki || b.groups.some(g => g.layer.notes?.[b.bag]) || residentsLayer?.notes?.[b.bag] ? t('Click for the story and sources') : t('Click to keep this card open')}</p>`}`;
}

const card = document.getElementById('card');
let pinnedGid = -1;
let svTimer = null;
function loadStreetViews(delay) {
  clearTimeout(svTimer);
  svTimer = setTimeout(() => card.querySelectorAll('img[data-sv]').forEach(img => {
    img.addEventListener('load', () => placeCard(...(pointer || lastPin)), { once: true });
    img.src = img.dataset.sv;
  }), delay);
}
let lastPin = [0, 0];
function placeCard(x, y) {
  const r = card.getBoundingClientRect();
  card.style.left = Math.max(12, Math.min(x + 18, innerWidth - r.width - 12)) + 'px';
  card.style.top = Math.max(12, Math.min(y + 18, innerHeight - r.height - 12)) + 'px';
}
let hoverGid = -1;
function showCard(gid, x, y) {
  if (pinnedGid >= 0 || pinnedStreet || pinnedSite || phone.matches) return;
  if (cardsLocked()) { card.hidden = true; return; }
  if (gid < 0) { card.hidden = true; hoverGid = -1; return; }
  if (gid !== hoverGid || card.hidden) {
    // Re-render only when the building changes, so the photo is not reloaded every frame.
    hoverGid = gid;
    card.innerHTML = cardHtml(gid, false);
    wireSlides();
    card.classList.remove('pinned');
    card.hidden = false;
    loadStreetViews(350);
    card.querySelector('img')?.addEventListener('load', () => placeCard(...(pointer || [x, y])));
  }
  placeCard(x, y);
}
function pinCard(gid, x, y) {
  pinnedGid = gid;
  pinnedStreet = pinnedSite = hoverSite = null;
  if (streetMap) streetMap.picked.visible = false;
  hoverGid = -1;
  uniforms.uSelected.value = gid;
  if (gid < 0) { card.hidden = true; card.classList.remove('pinned'); return; }
  card.innerHTML = cardHtml(gid, true);
  wireSlides();
  card.classList.add('pinned');
  lastPin = [x, y];
  collapsePanelOnPhone();
  loadStreetViews(0);
  card.hidden = false;
  card.querySelector('.card-close').onclick = () => pinCard(-1);
  card.querySelector('img')?.addEventListener('load', () => placeCard(x, y));
  card.querySelector('.naming details')?.addEventListener('toggle', () => placeCard(x, y));
  placeCard(x, y);
}
addEventListener('keydown', e => { if (e.key === 'Escape') pinCard(-1); });

// A click (not a drag) pins the building under the pointer, or clears the pin on empty ground.
let pointer = null, dragging = false, downAt = null;
canvas.addEventListener('pointermove', e => { pointer = [e.clientX, e.clientY]; });
canvas.addEventListener('pointerdown', e => {
  dragging = true; downAt = [e.clientX, e.clientY];
  if (pinnedGid < 0 && !pinnedStreet && !pinnedSite) card.hidden = true;
});
canvas.addEventListener('pointerup', e => {
  dragging = false;
  if (!downAt || Math.hypot(e.clientX - downAt[0], e.clientY - downAt[1]) > 5) return;
  if (streetsOn && !photoOn) {
    const street = pickStreet(e.clientX, e.clientY);
    return street && street !== pinnedStreet ? pinStreet(street, e.clientX, e.clientY) : pinCard(-1);
  }
  if (viewNow()?.streets) {
    const name = pickStreet(e.clientX, e.clientY, viewNow().mesh);
    return name && name !== pinnedSite?.name ? pinFine(viewNow(), name, e.clientX, e.clientY) : pinCard(-1);
  }
  if (viewNow()) {
    const site = pickSite(e.clientX, e.clientY);
    return site && site !== pinnedSite ? pinSite(site, e.clientX, e.clientY) : pinCard(-1);
  }
  const gid = photoOn ? pickPhoto(e.clientX, e.clientY) : pick(e.clientX, e.clientY);
  if (quest && !solved && qStep().kind === 'find') { questClick(gid); return; }
  if (cardsLocked()) return;
  pinCard(gid === pinnedGid ? -1 : gid, e.clientX, e.clientY);
});
canvas.addEventListener('pointerleave', () => { pointer = null; if (pinnedGid < 0 && !pinnedStreet && !pinnedSite) card.hidden = true; uniforms.uHover.value = -1; });

// ---------- Flying to a building ----------
let bagIndex = null;
function gidOf(bag) {
  if (!bagIndex) bagIndex = new Map(info.id.map((id, g) => [id, g]));
  return bagIndex.get(bag) ?? -1;
}
let flight = null;
function flyTo(x, z, done, distance = 520) {
  const dir = camera.position.clone().sub(controls.target).normalize();
  if (dir.y < 0.45) { dir.y = 0.45; dir.normalize(); }
  const target = new THREE.Vector3(x, 0, z);
  flight = { t0: performance.now(), dur: 1400, fromT: controls.target.clone(), toT: target,
    fromP: camera.position.clone(), toP: target.clone().add(dir.multiplyScalar(distance)), done };
}
function stepFlight(now) {
  if (!flight) return;
  const k = Math.min(1, (now - flight.t0) / flight.dur), e = k < 0.5 ? 2 * k * k : 1 - (-2 * k + 2) ** 2 / 2;
  controls.target.lerpVectors(flight.fromT, flight.toT, e);
  camera.position.lerpVectors(flight.fromP, flight.toP, e);
  if (k >= 1) { const d = flight.done; flight = null; d?.(); }
}

// ---------- Quests ----------
// Short walks through the city as riddles (pipeline/quests.py, checked by s13_quests): find a building on the map,
// guess a building's year with the colours hidden, or pick one of three answers. Each step is worth three crosses,
// the X of the city's arms; a hint or a wrong answer costs one. Progress stays in this browser.
let quests = [];
fetch('data/quests.json').then(r => r.ok ? r.json() : []).then(q => { quests = q; }).catch(() => {});
const questEl = document.getElementById('quest');
const questsDlg = document.getElementById('quests');
const L10 = o => o?.[LANG] || o?.en || '';
const LEVEL = ['', 'Easy', 'Medium', 'Hard'];
const qStore = () => { try { return JSON.parse(localStorage.getItem('hel-quests') || '{}'); } catch { return {}; } };
function qSave(id, patch) {
  try { const p = qStore(); p[id] = { ...(p[id] || {}), ...patch }; localStorage.setItem('hel-quests', JSON.stringify(p)); } catch {}
}
const crosses = (n, of = 3) => `<span class="q-x" aria-label="${n} / ${of}">${Array.from({ length: of }, (_, i) =>
  `<i class="${i < n ? 'on' : ''}">×</i>`).join('')}</span>`;
const levelMark = lv => `<span class="q-level">${crosses(lv)}${t(LEVEL[lv])}</span>`;
// A small seeded generator: the same circle offset and answer order every time a step is played.
function rng(seed) { let h = 2166136261; for (const c of seed) h = Math.imul(h ^ c.charCodeAt(0), 16777619); return () => ((h = Math.imul(h ^ (h >>> 15), 2246822507) ^ Math.imul(h ^ (h >>> 13), 3266489909)) >>> 0) / 4294967296; }

function renderQuestList() {
  const p = qStore();
  const total = quests.reduce((n, q) => n + (p[q.id]?.best || 0), 0), max = quests.reduce((n, q) => n + q.steps.length * 3, 0);
  const tile = (q, st) => {
    const n = q.steps.length, done = Math.min(st.step || 0, n), complete = done >= n;
    return `<li class="q-tile l${q.level}${complete ? ' complete' : ''}">
      ${levelMark(q.level)}
      <h3>${esc(L10(q.title))}</h3><p>${esc(L10(q.intro))}</p>
      <footer><span class="q-progress">${complete ? `${st.score || 0} / ${n * 3}` : `${done} / ${n}`}</span>
        <button class="q-start" data-q="${q.id}">${complete ? t('Play again') : done ? t('Continue') : t('Start')}</button></footer></li>`;
  };
  document.getElementById('quests-body').innerHTML = `
    <h2 id="quests-title">${t('Quests')}</h2>
    <p class="q-lede">${t('Find buildings from riddles and old photos, guess their age with the colours switched off. Every answer is worth three crosses; hints and wrong answers cost one.')}</p>
    <p class="q-score">${t('Your crosses')}: <b>${total}</b> / ${max}</p>
    <ul class="q-grid">${quests.map(q => tile(q, p[q.id] || {})).join('')}</ul>`;
  questsDlg.querySelectorAll('.q-start').forEach(b => b.onclick = () => {
    const q = quests.find(q => q.id === b.dataset.q), st = qStore()[q.id] || {};
    questsDlg.close();
    const fresh = !st.step || st.step >= q.steps.length;
    startQuest(q, fresh ? 0 : st.step, fresh ? 0 : st.score || 0, fresh ? [] : st.marks || []);
  });
}
function openQuests() { renderQuestList(); questsDlg.showModal(); }
document.querySelector('.quests-open').onclick = openQuests;
questsDlg.querySelector('.about-close').onclick = () => questsDlg.close();
questsDlg.addEventListener('click', e => { if (e.target === questsDlg) questsDlg.close(); });

// The search circle: a red ring on the ground around (not centred on) the answer.
const ring = new THREE.Group();
ring.add(new THREE.Mesh(new THREE.RingGeometry(0.97, 1, 128), new THREE.MeshBasicMaterial({ color: 0xec0000, depthTest: false, transparent: true, opacity: 0.95 })));
ring.add(new THREE.Mesh(new THREE.CircleGeometry(0.97, 128), new THREE.MeshBasicMaterial({ color: 0xec0000, depthTest: false, transparent: true, opacity: 0.06 })));
ring.children.forEach(m => { m.rotation.x = -Math.PI / 2; m.renderOrder = 20; });
ring.visible = false;
scene.add(ring);

let quest = null, step = 0, score = 0, marks = [], hintsShown = 0, tries = 0, solved = false, revealed = false, lastDist = null;
let folded = false, guess = 1850;
const qStep = () => quest.steps[step];
const stepGids = s => s.bags.map(gidOf).filter(g => g >= 0);
function centre(gids) {
  const bs = gids.map(building);
  return [bs.reduce((a, b) => a + b.x, 0) / bs.length, bs.reduce((a, b) => a + b.z, 0) / bs.length];
}
// The map's state while a step asks about one building: its card locked, its colours hidden for a year riddle.
let quizGid = -1;
function setQuiz(gid, blind) {
  quizGid = gid;
  uniforms.uSelected.value = gid;
  uniforms.uBlind.value = gid < 0 ? 0 : blind ? 1 : 2;
  if (gid >= 0) { pinCard(-1); uniforms.uSelected.value = gid; }
}
const cardsLocked = () => quest && !solved && quizGid >= 0;

function startQuest(q, n, sc = 0, mk = []) {
  quest = q; step = n; score = sc; marks = mk;
  document.body.classList.add('questing');
  setPhoto(false);
  setGround(false);  // an old photo would give the year away
  setStreets(false);  // a quest is about buildings
  setView(false);
  pinCard(-1);
  enterStep(true);
}
function enterStep(first) {
  hintsShown = 0; tries = 0; solved = false; revealed = false; lastDist = null; folded = false; guess = 1850;
  ring.visible = false;
  const s = qStep(), gids = stepGids(s);
  if (s.kind === 'find') {
    setQuiz(-1, false);
    if (first) {
      // Open on the whole quest: every building it visits in view.
      const all = quest.steps.flatMap(stepGids), [x, z] = centre(all);
      const spread = Math.max(...all.map(g => { const b = building(g); return Math.hypot(b.x - x, b.z - z); }));
      flyTo(x, z, null, Math.min(5200, Math.max(900, spread * 2.2)));
    }
  } else if (gids.length) {
    const b = building(gids[0]);
    setQuiz(gids[0], s.kind === 'year');
    questFly(b.x, b.z, s.kind === 'year' ? 300 : 380);
  }
  renderQuest();
}
// On a phone the quest sits over the top half of the map: aim past the building so it lands in the lower half.
function questFly(x, z, dist, done = null) {
  if (phone.matches) {
    const f = controls.target.clone().sub(camera.position).setY(0).normalize();
    x += f.x * dist * 0.2; z += f.z * dist * 0.2;
  }
  flyTo(x, z, done, dist);
}
function closeQuest() {
  document.body.classList.remove('questing');
  quest = null; questEl.hidden = true; ring.visible = false; setQuiz(-1, false);
}
function setModeNamed(name) {
  document.querySelector(`.modes button[data-mode="${MODE[name]}"]`)?.click();
}
function showRing() {
  const s = qStep(), [x, z] = centre(stepGids(s));
  const r = { 1: 220, 2: 300, 3: 380 }[quest.level] || 300;
  const k = rng(quest.id + step), a = k() * Math.PI * 2, d = r * 0.55 * Math.sqrt(k());
  const cx = x + Math.cos(a) * d, cz = z + Math.sin(a) * d;
  ring.position.set(cx, 2, cz); ring.scale.setScalar(r); ring.visible = true;
  questFly(cx, cz, r * 5);
}

function photoOf(s) {
  if (s.clue?.id) return { src: FINNA_IMG(s.clue.id), year: s.clue.year,
    credit: `${s.clue.year}${s.clue.m ? ', ' + esc(s.clue.m) : ''}, ${link(FINNA_PAGE(s.clue.id), 'Helsingin kaupunginmuseo')}, ${link(LICENCE[s.clue.l], s.clue.l)}` };
  if (s.clue?.thumb) return { src: s.clue.thumb, credit: link(s.clue.page || s.clue.thumb, [s.clue.artist, s.clue.license].filter(Boolean).join(', ') || 'Wikimedia Commons') };
  if (s.photo) {
    const g = stepGids(s)[0], b = g >= 0 && building(g), w = b && b.wk >= 0 ? wiki[b.wk] : null;
    if (w?.image?.thumb) return { src: w.image.thumb, credit: link(w.image.page || w.image.thumb, [w.image.artist, w.image.license].filter(Boolean).join(', ') || 'Wikimedia Commons') };
  }
  return null;
}
const progress = () => `<div class="q-steps">${quest.steps.map((_, i) => `<i class="${i < step || (i === step && solved) ? 'done' : i === step ? 'now' : ''}"></i>`).join('')}
  <span>${step + 1} / ${quest.steps.length}</span></div>`;
const worth = () => {
  const s = qStep();
  if (s.kind === 'find') return revealed ? 0 : Math.max(1, 3 - hintsShown);
  if (s.kind === 'choice') return [3, 1, 0][Math.min(tries, 2)];
  return 3;
};
function yearPoints(d) { return d <= 5 ? 3 : d <= 20 ? 2 : d <= 50 ? 1 : 0; }

function renderQuest() {
  if (!quest) return;
  const s = qStep(), ph = photoOf(s);
  const title = esc(L10(quest.title));
  questEl.className = `quest k-${s.kind}${solved ? ' solved' : ''}${folded ? ' folded' : ''}`;
  let body = '';
  if (s.kind === 'find') {
    const hints = Array.from({ length: hintsShown }, (_, i) => i === 0 ? t('Look inside the red circle.') : L10(s.hints[i - 1]));
    const more = hintsShown < s.hints.length + 1;
    body = `
      ${ph && !solved ? `<figure class="q-photo${s.clue?.id ? ' old' : ''}"><img src="${esc(ph.src)}" alt="${t('A photo of the building to find')}">${ph.year ? `<span class="year">${ph.year}</span>` : ''}</figure><p class="q-credit">${ph.credit}</p>` : ''}
      <p class="q-riddle">${esc(L10(s.riddle))}</p>
      ${hints.length ? `<ul class="q-hints">${hints.map(h => `<li>${esc(h)}</li>`).join('')}</ul>` : ''}
      ${solved ? '' : `<p class="q-feedback">${t('Find it on the map and click it.')}</p>`}
      ${solved ? '' : `<div class="q-actions">
        ${more ? `<button class="q-hint">${t('Hint')} <small>−×</small></button>` : ''}
        ${s.mode ? `<button class="q-mode">${t(s.mode === 'floors' ? 'Colour by floors' : 'Colour by period')}</button>` : ''}
        <button class="q-reveal">${t('Show me')}</button>
        <span class="q-worth">${crosses(worth())}</span></div>`}`;
  } else if (s.kind === 'year') {
    body = `
      ${ph ? `<figure class="q-photo"><img src="${esc(ph.src)}" alt=""></figure><p class="q-credit">${ph.credit}</p>` : ''}
      <p class="q-riddle">${esc(L10(s.ask))}</p>
      ${solved ? '' : `<div class="q-year"><output>${guess}</output>
        <input type="range" min="1700" max="2026" step="1" value="${guess}" aria-label="${t('Your guess')}">
        <div class="q-scale"><span>1700</span><span>1800</span><span>1900</span><span>2000</span></div></div>
        <div class="q-actions"><button class="primary q-guess">${t('Guess')}</button><span class="q-worth">${crosses(3)}</span></div>`}`;
  } else {
    const order = s.options.map((o, i) => i).sort((a, b) => rng(quest.id + step + a)() - rng(quest.id + step + b)());
    body = `
      <p class="q-riddle">${esc(L10(s.ask))}</p>
      <div class="q-options">${order.map(i => `<button data-i="${i}" ${solved ? 'disabled' : ''} class="${solved && i === 0 ? 'right' : ''}">${esc(L10(s.options[i]))}</button>`).join('')}</div>
      ${solved ? '' : `<div class="q-actions"><span class="q-feedback"></span><span class="q-worth">${crosses(worth())}</span></div>`}`;
  }
  questEl.innerHTML = `
    <button class="q-close" aria-label="${t('Close')}">×</button>
    <header><b>${title}</b>${levelMark(quest.level)}</header>
    ${progress()}${body}${solved ? revealHtml(s) : ''}`;
  questEl.hidden = false;
  wireQuest(s);
}
function revealHtml(s) {
  const got = marks[step] ?? 0, last = step === quest.steps.length - 1;
  const g = stepGids(s)[0], b = g >= 0 ? building(g) : null;
  const extra = s.kind === 'year' ? `<p class="q-yeardiff">${t('Your guess')}: <b>${guess}</b>. ${t('Built')}: <b>${s.year}</b>. ${Math.abs(guess - s.year) === 0 ? t('Exactly right.') : `${Math.abs(guess - s.year)} ${t(Math.abs(guess - s.year) === 1 ? 'year off' : 'years off')}.`}</p>` : '';
  const then = s.clue?.id && b ? `<div class="q-then"><figure><img src="${esc(photoOf(s).src)}" alt=""><figcaption>${s.clue.year}</figcaption></figure>${
    b.wk >= 0 && wiki[b.wk]?.image?.thumb ? `<figure><img src="${esc(wiki[b.wk].image.thumb)}" alt=""><figcaption>${t('Today')}</figcaption></figure>` : ''}</div>` : '';
  return `<div class="q-found">
    <div class="q-stamp" aria-hidden="true">${crosses(got)}</div>
    ${then}${extra}
    <p>${esc(L10(s.reveal))}${s.sources?.length ? ' ' + s.sources.map((u, i) => link(u, s.sources.length > 1 ? `${t('Source')} ${i + 1}` : t('Source'))).join(', ') : ''}</p>
    <p class="q-earned">${revealed ? t('Shown, not found: no crosses.') : got === 3 ? t('Full marks.') : ''}</p></div>
    <div class="q-actions">${last ? `<button class="primary q-finish">${t('See the result')}</button>`
      : `<button class="primary q-next">${t('Next')}</button>`}<button class="q-card">${t('Open its card')}</button></div>`;
}
function wireQuest(s) {
  questEl.querySelector('header').onclick = () => { folded = !folded; questEl.classList.toggle('folded', folded); };
  questEl.querySelector('.q-close').onclick = closeQuest;
  const foldOnPhone = () => { if (phone.matches) { folded = true; questEl.classList.add('folded'); } };
  questEl.querySelector('.q-hint')?.addEventListener('click', () => { hintsShown++; if (hintsShown === 1) { showRing(); foldOnPhone(); } renderQuest(); if (phone.matches && hintsShown === 1) { folded = true; questEl.classList.add('folded'); } });
  questEl.querySelector('.q-mode')?.addEventListener('click', () => { setModeNamed(s.mode); foldOnPhone(); });
  questEl.querySelector('.q-reveal')?.addEventListener('click', () => {
    const g = stepGids(s)[0]; if (g === undefined) return;
    revealed = true; const b = building(g);
    questFly(b.x, b.z, 420, () => solve(g));
  });
  const range = questEl.querySelector('.q-year input');
  if (range) range.oninput = () => { guess = +range.value; questEl.querySelector('.q-year output').textContent = guess; };
  questEl.querySelector('.q-guess')?.addEventListener('click', () => solve(stepGids(s)[0], yearPoints(Math.abs(guess - s.year))));
  questEl.querySelectorAll('.q-options button').forEach(b => b.onclick = () => {
    if (+b.dataset.i === 0) { b.classList.add('right'); solve(stepGids(s)[0]); return; }
    tries++; b.classList.add('wrong'); b.disabled = true;
    questEl.querySelector('.q-actions .q-worth').innerHTML = crosses(worth());
    const fb = questEl.querySelector('.q-feedback'); fb.textContent = t('Not that one.'); fb.classList.remove('miss'); void fb.offsetWidth; fb.classList.add('miss');
  });
  questEl.querySelector('.q-next')?.addEventListener('click', () => { step++; qSave(quest.id, { step, score, marks }); enterStep(false); });
  questEl.querySelector('.q-finish')?.addEventListener('click', finished);
  questEl.querySelector('.q-card')?.addEventListener('click', () => { const g = stepGids(s)[0]; const b = building(g); quizGid = -1; uniforms.uBlind.value = 0; flyTo(b.x, b.z, () => pinCard(g, innerWidth * 0.3, 120), 380); });
}
function solve(gid, points) {
  const s = qStep();
  solved = true; folded = false; ring.visible = false;
  const got = points ?? worth();
  marks[step] = got; score += got;
  uniforms.uBlind.value = 0;
  quizGid = -1;
  if (gid >= 0) { pinCard(-1); uniforms.uSelected.value = gid; }
  const st = qStore()[quest.id] || {};
  const patch = { step: step + 1, score, marks };
  if (step === quest.steps.length - 1) patch.best = Math.max(st.best || 0, score);
  qSave(quest.id, patch);
  renderQuest();
}
// The result, and a line to share: one group of crosses per step, a dot for each one lost.
function finished() {
  const n = quest.steps.length, line = marks.map(m => '×'.repeat(m) + '·'.repeat(3 - m)).join(' ');
  const text = `${t('Helsinki, building by building')} · ${L10(quest.title)}\n${line}\n${score} / ${n * 3}\n${location.origin}${location.pathname}`;
  const verdict = score >= n * 3 - 1 ? 'A true Helsinki local.' : score >= n * 2 ? 'You know your way around.' : score >= n ? 'A good walk.' : 'Time for a walk through town.';
  questEl.className = 'quest done';
  questEl.innerHTML = `
    <button class="q-close" aria-label="${t('Close')}">×</button>
    <header><b>${esc(L10(quest.title))}</b></header>
    <div class="q-result"><p class="q-total"><b>${score}</b> / ${n * 3}</p><p class="q-verdict">${t(verdict)}</p>
      <p class="q-line" aria-label="${score} / ${n * 3}">${line}</p></div>
    <div class="q-actions"><button class="primary q-share">${t('Copy result')}</button><button class="q-list">${t('More quests')}</button></div>`;
  questEl.hidden = false;
  ring.visible = false; setQuiz(-1, false);
  questEl.querySelector('.q-close').onclick = closeQuest;
  questEl.querySelector('.q-list').onclick = () => { closeQuest(); openQuests(); };
  questEl.querySelector('.q-share').onclick = async e => {
    try { await navigator.clipboard.writeText(text); e.target.textContent = t('Copied'); } catch { e.target.textContent = text.split('\n')[1]; }
  };
}
// Every click on the map while a find step is open.
function questClick(gid) {
  if (!quest || solved || gid < 0 || qStep().kind !== 'find') return;
  const s = qStep(), targets = stepGids(s);
  if (targets.includes(gid)) { solve(gid); return; }
  const fb = questEl.querySelector('.q-feedback');
  if (!fb) return;
  const b = building(gid);
  const d = Math.min(...targets.map(g => { const a = building(g); return Math.hypot(a.x - b.x, a.z - b.z); }));
  let msg = d < 40 ? t('Not this one, but right next to it.') : d < 200 ? t('Not this one. Very warm.')
    : d < 700 ? t('Not this one. A few streets away.') : t('Not this one. Far off.');
  if (lastDist !== null && d >= 40) msg += ' ' + t(d < lastDist - 20 ? 'Warmer than before.' : d > lastDist + 20 ? 'Colder than before.' : '');
  lastDist = d;
  fb.textContent = msg.trim();
  fb.className = `q-feedback ${d < 40 ? 'hot' : d < 200 ? 'warm' : 'cold'}`;
  void fb.offsetWidth; fb.classList.add('miss');
}
addEventListener('keydown', e => { if (e.key === 'Escape' && questsDlg.open) questsDlg.close(); });

// ---------- Panel ----------
const panelEl = document.getElementById('panel');
const panel = document.getElementById('panel-body');
const sheetHandle = panelEl.querySelector('.sheet-handle');
const phone = matchMedia('(max-width: 720px)');
// On a phone the panel is a sheet: folded to one line until opened, and folded again when the city is the point.
function setCollapsed(c) {
  panelEl.classList.toggle('collapsed', c);
  sheetHandle.setAttribute('aria-expanded', String(!c));
  sheetHandle.textContent = t(c ? 'Show legend' : 'Hide legend');
}
sheetHandle.onclick = () => setCollapsed(!panelEl.classList.contains('collapsed'));
function collapsePanelOnPhone() { if (phone.matches) setCollapsed(true); }
setCollapsed(phone.matches);
const totals = periods.map(() => 0);
for (const v of Object.values(config.histogram)) v.forEach((n, i) => totals[i] += n);
const fmt = n => n.toLocaleString(fmtLocale());
let activeLayer = null;
const SECTION_ORDER = ['Discover', 'Heritage', 'Architecture', 'Trade and empire', 'Faith and community', 'Countries and communities',
  'The modern city', 'War and occupation'];
const groupOn = {};
let maskTarget = periods.map(() => 1);

const ICON = {
  'Discover': '<circle cx="8" cy="8" r="6.2"/><path d="M10.6 5.4 9 9 5.4 10.6 7 7z"/>',
  'Architecture': '<path d="M3 14.5V7l5-4.5L13 7v7.5z"/><path d="M6.5 14.5v-4h3v4"/>',
  'Heritage': '<path d="M3 14.5V7l5-4.5L13 7v7.5z"/><path d="M6.5 14.5v-4h3v4"/>',
  'Trade and empire': '<path d="M2 11h12l-1.8 3H3.8z"/><path d="M8 2v9M8 3l4.5 6H8"/>',
  'Faith and community': '<path d="M8 1.5v4M6.2 3.3h3.6"/><path d="M4 14.5V8.5L8 5.5l4 3v6z"/><path d="M7 14.5v-3h2v3"/>',
  'The modern city': '<rect x="2.5" y="5" width="5" height="9.5"/><rect x="8.5" y="2" width="5" height="12.5"/><path d="M4.5 7.5h1M4.5 10h1M10.5 4.5h1M10.5 7h1M10.5 9.5h1"/>',
  'War and occupation': '<path d="M8 1.8 13 4v4c0 3.2-2.2 5.3-5 6.3-2.8-1-5-3.1-5-6.3V4z"/>',
};
const sectionIcon = sec => `<svg class="icon" viewBox="0 0 16 16" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linejoin="round" stroke-linecap="round">${ICON[sec] || ''}</svg>`;

function renderPanel() {
  const mode = uniforms.uMode.value;
  const row = (color, label, n) => `<div><i style="background:${color}"></i><span>${label}</span><span class="n">${n == null ? '' : fmt(n)}</span></div>`;
  if (streetsOn) {
    const old = streetMap && new Set(streetMap.of.slice(0, streetMap.old)).size;
    panel.innerHTML = `<h2>${t('Street names')}</h2><div class="energy-scale">${row(STREET_COLORS[0], t('Earlier name known'), old)}
      ${row(STREET_COLORS[1], t('No earlier name known'), streetMap && streetMap.names.length - old)}</div>
      <p class="note">${t('Click a street to see its names and where they come from.')}</p>
      <a class="src" href="${NAMES_URL()}" target="_blank" rel="noopener">${t('Helsinki place names')}, CC BY 4.0</a>`;
  } else if (viewOn) {
    const E = ERAS[viewEra], shown = viewKinds(E), land = shown.some(K => K.id === 'structures');
    const dots = shown.filter(K => K.sites.length), label = K => t(tr(K, 'label'));  // public art's kinds are the periods
    const lists = [...(land ? [[t('Strongpoints'), E.places]] : []), ...shown.filter(K => K.list).map(K => [label(K), K.sites])];
    const sources = [...shown.map(K => K.source), ...E.sources || []].filter((x, i, all) => all.findIndex(y => y.url === x.url) === i);
    panel.innerHTML = `<h2 class="layer-title">${esc(tr(E, 'label'))}</h2>
      <p class="layer-era">${esc(tr(E, 'years'))}${viewKind ? ` · ${esc(label(E.groups?.[viewKind] || shown[0]))}` : ''}</p>
      <div class="layer-detail"><p>${esc(tr(E, 'text'))}</p></div>
      ${dots.length ? `<h2 class="section">${t('On the map')}</h2><div class="energy-scale">${dots.map(K => row(K.color, esc(label(K)), K.sites.length)).join('')}</div>` : ''}
      ${land || E.tracks ? `<h2 class="section">${esc(tr(E, 'linesTitle'))}</h2><div class="energy-scale">${E.legend.map(g => row(g.color, esc(tr(g, 'label')), g.n)).join('')}</div>` : ''}
      ${E.streets ? fineLegend(E, row) : ''}
      ${lists.length ? `<input class="filter" type="search" placeholder="${t('Find a site')}" aria-label="${t('Find a site')}">` : ''}
      ${lists.map(([title, list], j) => `<h2 class="section">${esc(title)}</h2><ul class="stories">${list.map((x, i) => `
        <li data-q="${esc(`${tr(x, 'name')} ${tr(x, 'sub') || ''}`.toLowerCase())}"><button class="story" data-list="${j}" data-i="${i}">
        <b>${esc(tr(x, 'name'))}</b>${tr(x, 'sub') ? `<span>${esc(tr(x, 'sub'))}</span>` : ''}</button></li>`).join('')}</ul>`).join('')}
      <p class="caveat">${esc(tr(E, 'caveat'))}</p>
      <p class="note">${t('Sources')}: ${sources.map(x => link(tr(x, 'url'), tr(x, 'label'))).join(' · ')}</p>`;
    panel.querySelector('.filter')?.addEventListener('input', e => {
      const q = e.target.value.toLowerCase();
      panel.querySelectorAll('.stories li').forEach(li => { li.hidden = q && !li.dataset.q.includes(q); });
    });
    // The parking fines: a year moves the timeline; a street flies there and opens its card.
    panel.querySelector('.fine-alone input')?.addEventListener('change', e => { E.alone = e.target.checked; showCity(); });
    panel.querySelectorAll('[data-fine-per]').forEach(b => b.onclick = () => { E.per = b.dataset.finePer === 'true'; colourFines(E); });
    panel.querySelectorAll('[data-fine]').forEach(b => b.onclick = () => {
      const c = streetCentre(b.dataset.fine);
      collapsePanelOnPhone();
      flyTo(c.x, c.z, () => pinFine(E, b.dataset.fine, innerWidth * 0.62, innerHeight * 0.18), 700);
    });
    // A strongpoint is a place to fly to; a site also opens its card.
    panel.querySelectorAll('.story[data-list]').forEach(b => b.onclick = () => {
      const x = lists[+b.dataset.list][1][+b.dataset.i], place = !x.kind;
      collapsePanelOnPhone();
      flyTo(x.at[0], x.at[1], place ? null : () => pinSite(x, innerWidth * 0.62, innerHeight * 0.18), place ? 900 : 380);
    });
  } else if (mode === MODE.period || mode === MODE.gone) {
    const sub = `<div class="sub" role="group" aria-label="${t('Period')}">${[MODE.period, MODE.gone].map(m => `
      <button data-sub="${m}" aria-pressed="${m === mode}">${t(m === MODE.period ? 'Completed' : 'Torn down')}</button>`).join('')}</div>`;
    if (mode === MODE.period) {
      panel.innerHTML = `${sub}<h2>${t('Built in')}</h2><div class="swatches">${periods.map((p, i) => `
        <button class="swatch" data-i="${i}" aria-pressed="${!!maskTarget[i]}">
          <i style="background:${p.color}"></i><span>${t(p.label)}</span><span class="n">${fmt(totals[i])}</span>
        </button>`).join('')}</div>
        <p class="note">${t('Click a period to see it alone. Paler buildings have an approximate year.')}</p>`;
      panel.querySelectorAll('.swatch').forEach(b => b.onclick = () => {
        const i = +b.dataset.i, m = maskTarget;
        const solo = m.every((v, j) => (j === i) === !!v);
        maskTarget = periods.map((_, j) => (solo || j === i) ? 1 : 0);
        renderPanel(); drawHist();
      });
    } else {
      const gone = periods.map((_, i) => demolished.reduce((n, [, v]) => n + v[i], 0)), n = fmt(gone.reduce((a, b) => a + b, 0));
      panel.innerHTML = `${sub}<h2>${t('Built in')}</h2><div class="energy-scale">${periods.map((p, i) => row(p.color, t(p.label), gone[i])).join('')}</div>
        <p class="note">${LANG === 'fi' ? `Kaupungin 3D-mallin mukaan vuoden 2008 jälkeen puretut ${n} rakennusta rakennusaikansa värein; lähes kaikki on purettu vuodesta 2016 alkaen. Aikajana näyttää sen vuoden loppuun mennessä puretut, ja muut rakennukset ovat valkoisia. Vanhemmista purkamisista ei ole avointa aineistoa, mutta vanhat kartat ja ilmakuvat näyttävät, mitä paikalla oli.` : `The ${n} buildings the city's 3D model has torn down since 2008, in the colour of the period they were built in; nearly all came down from 2016 on. The timeline shows those gone by the end of its year, and every other building stands white. No open data records the demolitions before 2008, but the old maps and aerial photos show what stood.`}</p>
        <a class="src" href="${MODEL_URL()}" target="_blank" rel="noopener">${t('Helsinki 3D city model')}, CC BY 4.0</a>`;
    }
    panel.querySelectorAll('.sub button').forEach(b => b.onclick = () => { uniforms.uMode.value = +b.dataset.sub; renderPanel(); drawHist(); });
  } else if (mode === MODE.floors) {
    const n = FLOOR_STEPS.map(() => 0);
    for (let g = 0; g < info.id.length; g++) {
      const o = g * config.attrStride;
      if (!attrs.getInt16(o + 32, true)) n[FLOOR_STEPS.findLastIndex(s => attrs.getUint8(o + 21) >= s)]++;  // standing ones
    }
    const label = i => i === FLOOR_STEPS.length - 1 ? `${FLOOR_STEPS[i]}+`
      : FLOOR_STEPS[i + 1] - FLOOR_STEPS[i] > 1 ? `${FLOOR_STEPS[i]}–${FLOOR_STEPS[i + 1] - 1}` : `${FLOOR_STEPS[i]}`;
    panel.innerHTML = `<h2>${t('Storeys')}</h2>
      <div class="energy-scale">${FLOOR_COLORS.map((c, i) => row(c, label(i), n[i])).reverse().join('')}</div>
      <p class="note">${LANG === 'fi' ? `${fmt(config.stats.floorsRegister)} rakennuksen kerrosluku on rakennusrekisteristä; loput ${fmt(config.stats.floorsAssumed)} ovat lähes kaikki pieniä talousrakennuksia. ${fmt(config.stats.heightModel)} rakennuksen korkeus on kaupungin 3D-mallista: kattopintojen korkeuden 70. persentiili. Muiden korkeus on kerrosluku kertaa 3,2 m.` : `${fmt(config.stats.floorsRegister)} buildings take their floors from the building register; the other ${fmt(config.stats.floorsAssumed)} are nearly all small outbuildings. ${fmt(config.stats.heightModel)} buildings take their height from the city's 3D model: the 70th percentile of their roof surfaces. The rest are floors times 3.2 m.`}</p>`;
  } else if (mode === MODE.energy || mode === MODE.solar || mode === MODE.heat) {
    const sub = `<div class="sub" role="group" aria-label="${t('Energy')}">${[MODE.energy, MODE.solar, MODE.heat].map(m => `
      <button data-sub="${m}" aria-pressed="${m === mode}">${t({ [MODE.energy]: 'Energy label', [MODE.solar]: 'Solar', [MODE.heat]: 'Heating' }[m])}</button>`).join('')}</div>`;
    if (mode === MODE.heat) {
      const h = config.heat;
      panel.innerHTML = `${sub}<div class="swatches">${[...h.groups.map(g => g[LANG]), t('Not recorded')].map((label, i) => `
        <button class="swatch" data-i="${(i + 1) % HEAT_COLORS.length}" aria-pressed="${!!maskTarget[(i + 1) % HEAT_COLORS.length]}">
          <i style="background:${HEAT_COLORS[(i + 1) % HEAT_COLORS.length]}"></i><span>${esc(label)}</span><span class="n">${fmt(h.counts[(i + 1) % HEAT_COLORS.length])}</span>
        </button>`).join('')}</div>
        <p class="note">${t('Click a source to see it alone.')} ${LANG === 'fi' ? `Rakennusrekisterin mukainen pääasiallinen lämmönlähde. Se kirjataan rakennushankeilmoituksesta, kun talo rakennetaan, joten se kertoo, millä lämmöllä talo rakennettiin: moni 1950-luvun öljy- tai hiilitalo on voitu sittemmin liittää kaukolämpöön tai vaihtaa maalämpöön. Ennen vuotta 1981 valmistuneilta tieto voi puuttua tai olla virheellinen. ${fmt(h.counts[0])} rakennukselta, valkoisina kartalla, lähdettä ei ole kirjattu; ne ovat enimmäkseen varastoja, vajoja, talousrakennuksia, kesämökkejä ja autotalleja. Kortti kertoo tarkan lähteen ja lämmitystavan.` : `The main heat source in the building register. It is recorded from the notice filed when a building is built, so it tells what a building was built to be heated with: many an oil- or coal-heated house of the 1950s may since have joined the district heating or turned to ground-source heat. For buildings completed before 1981 it may be missing or wrong. ${fmt(h.counts[0])} buildings, white on the map, have none recorded; most are storehouses, sheds, outbuildings, summer cottages and garages. The card gives the exact source and the heating method.`}</p>
        <a class="src" href="${REGISTER_URL()}" target="_blank" rel="noopener">${t('Helsinki building register')}, CC BY 4.0</a>`;
      panel.querySelectorAll('.swatch').forEach(b => b.onclick = () => {
        const i = +b.dataset.i, m = maskTarget;
        const solo = m.every((v, j) => (j === i) === !!v);
        maskTarget = periods.map((_, j) => (solo || j === i) ? 1 : 0);
        renderPanel(); drawHist();
      });
    } else if (mode === MODE.energy) {
      const e = config.energy;
      panel.innerHTML = `${sub}<div class="energy-scale">${e.labels.map((l, i) => row(ENERGY_COLORS[i + 1], l, e.counts[i + 1])).reverse().join('')}</div>
        <p class="note">${LANG === 'fi' ? `Rakennuksen viimeksi laaditun voimassa olevan energiatodistuksen luokka. Todistus tarvitaan, kun rakennus tai asunto myydään tai vuokrataan; yhden ja kahden asunnon talojen todistukset eivät ole julkisia. ${fmt(e.counts[0])} rakennuksella, valkoisina kartalla, ei ole julkista todistusta. Vuosien 2013 ja 2018 asteikoissa luokkien rajat ovat eri kohdissa.` : `The label of the building's latest energy certificate in force. A certificate is needed to sell or let a building or a flat; those of houses with one or two homes are not public. ${fmt(e.counts[0])} buildings, white on the map, have no public certificate. The 2013 and 2018 scales draw the class limits in different places.`}</p>
        <a class="src" href="${ENERGY_URL}" target="_blank" rel="noopener">${t('Energy certificate register')}, Varke</a>`;
    } else {
      const s = config.solar, steps = [0, ...s.steps];
      const label = i => i === steps.length - 1 ? `${fmt(steps[i])}+` : `${fmt(steps[i])}–${fmt(steps[i + 1])}`;
      panel.innerHTML = `${sub}<p class="note">${t('MWh a year')}</p><div class="energy-scale">${steps.map((_, i) => row(SOLAR_COLORS[i + 2], label(i), s.counts[i + 2])).reverse().join('')}
        ${row(SOLAR_COLORS[1], t('no suitable roof'), s.counts[1])}</div>
        <p class="note">${LANG === 'fi' ? `HSY:n arvio vuoden sähköntuotosta, jos katon kaikki sopivat osat katettaisiin aurinkopaneeleilla (hyötysuhde 15 %). Arvio on vuodelta 2015, mutta lähes kaikille vuoden 2010 jälkeen valmistuneille se antaa nollan, joten niiltä se on jätetty pois. ${fmt(s.counts[0])} rakennuksella, valkoisina kartalla, ei ole arviota; ne ovat lähes kaikki pieniä talousrakennuksia tai vuoden 2010 jälkeen valmistuneita.` : `HSY's estimate of a year's electricity if every suitable part of the roof carried solar panels (15 % efficient). It dates from 2015 but gives nearly every building completed after 2010 zero, so those are left without one. ${fmt(s.counts[0])} buildings, white on the map, have no estimate; nearly all are small outbuildings or completed after 2010.`}</p>
        <a class="src" href="${SOLAR_URL()}" target="_blank" rel="noopener">${t('HSY solar potential')}, CC BY 4.0</a>`;
    }
    panel.querySelectorAll('.sub button').forEach(b => b.onclick = () => { setMode(+b.dataset.sub); renderPanel(); drawHist(); });
  } else if (activeLayer && activeLayer === residentsLayer) {
    const notes = Object.entries(residentsLayer?.notes || {});
    const people = notes.flatMap(([bag, n]) => n.people.map(p => ({ ...p, bag, at: n.at })))
      .sort((a, b) => b.links - a.links || a.person.localeCompare(b.person, fmtLocale()));
    panel.innerHTML = `<button class="back">${t('All context layers')}</button><h2 class="layer-title">${esc(tr(residentsLayer, 'title'))}</h2>
      <p class="layer-intro">${esc(tr(residentsLayer, 'text') || '')}</p>
      <input class="filter" type="search" placeholder="${t('Find a person')}" aria-label="${t('Find a person')}">
      <ul class="stories people">${people.map(p => `<li data-q="${esc((p.person + ' ' + (tr(p, 'desc') || '') + ' ' + p.address).toLowerCase())}">
        <button class="story" data-bag="${p.bag}"><b>${esc(p.person)}</b>
        <span>${[p.born && p.died ? `${p.born}–${p.died}` : p.born, tr(p, 'desc')].filter(Boolean).map(esc).join(', ')}</span>
        <span class="addr">${esc(p.address)}</span></button></li>`).join('')}</ul>
      ${residentsLayer?.caveat ? `<p class="caveat">${esc(tr(residentsLayer, 'caveat'))}</p>` : ''}`;
    panel.querySelector('.back').onclick = () => setLayer(null);
    panel.querySelector('.filter').oninput = e => {
      const q = e.target.value.toLowerCase();
      panel.querySelectorAll('.people li').forEach(li => { li.hidden = q && !li.dataset.q.includes(q); });
    };
    panel.querySelectorAll('.story').forEach(b => b.onclick = () => {
      const n = residentsLayer.notes[b.dataset.bag];
      collapsePanelOnPhone();
      flyTo(n.at[0], n.at[1], () => { const gid = gidOf(b.dataset.bag); if (gid >= 0) pinCard(gid, innerWidth * 0.62, innerHeight * 0.18); });
    });
  } else if (!activeLayer) {
    const sections = [...new Set(contextLayers.map(L => L.section))].sort((a, b) => SECTION_ORDER.indexOf(a) - SECTION_ORDER.indexOf(b));
    const secTitle = sec => tr(contextLayers.find(L => L.section === sec), 'section');
    panel.innerHTML = `<nav class="jump" aria-label="${t('Context layers')}">${sections.map(sec => `
      <button data-sec="${esc(sec)}" title="${esc(secTitle(sec))}" aria-label="${esc(secTitle(sec))}">${sectionIcon(sec)}</button>`).join('')}</nav>` +
      sections.map(sec => `<h2 class="section" id="sec-${sec.replace(/\W+/g, '-')}">${sectionIcon(sec)}${esc(secTitle(sec))}</h2><div class="layers">${contextLayers.filter(L => L.section === sec).map(L => `
      <button class="layer" data-id="${L.id}">
        <b>${esc(tr(L, 'title'))}</b><span class="n">${fmt(L.count)}</span><span class="era">${esc(tr(L, 'era'))}</span>
      </button>`).join('')}</div>`).join('');
    panel.querySelectorAll('.jump button').forEach(b => b.onclick = () =>
      panel.querySelector(`#sec-${b.dataset.sec.replace(/\W+/g, '-')}`).scrollIntoView({ behavior: 'smooth', block: 'start' }));
    panel.querySelectorAll('.layer').forEach(b => b.onclick = () => setLayer(contextLayers.find(l => l.id === b.dataset.id)));
  } else {
    panel.innerHTML = `<button class="back">${t('All context layers')}</button>
      <h2 class="layer-title">${sectionIcon(activeLayer.section)}${esc(tr(activeLayer, 'title'))}</h2><p class="layer-era">${esc(tr(activeLayer, 'era'))}</p>${layerDetail(activeLayer)}`;
    panel.querySelector('.back').onclick = () => setLayer(null);
    panel.querySelectorAll('.story').forEach(b => b.onclick = () => {
      const n = activeLayer.notes[b.dataset.bag];
      collapsePanelOnPhone();
      flyTo(n.at[0], n.at[1], () => {
        const gid = gidOf(b.dataset.bag);
        if (gid >= 0) pinCard(gid, innerWidth * 0.62, innerHeight * 0.18);
      });
    });
    panel.querySelectorAll('.swatch').forEach(b => b.onclick = () => {
      groupOn[b.dataset.bit] = groupOn[b.dataset.bit] === false;
      setLayer(activeLayer);
    });
  }
}

function layerDetail(L) {
  const groups = L.groups.length > 1 ? `<div class="swatches">${L.groups.map((g, i) => `
    <button class="swatch" data-bit="${g.bit}" aria-pressed="${groupOn[g.bit] !== false}">
      <i style="background:${GROUP_COLORS[i]}"></i><span>${esc(tr(g, 'label'))}</span><span class="n">${fmt(g.count)}</span>
    </button>`).join('')}</div>` : '';
  // One line per story: a building made of several BAG parts carries the same note on each.
  const seenName = new Set();
  const named = Object.entries(L.notes || {}).filter(([, n]) => n.name && n.at && !seenName.has(n.name) && seenName.add(n.name))
    .sort(([, a], [, b]) => tr(a, 'name').localeCompare(tr(b, 'name'), fmtLocale())); // ids that are all digits would come first
  const stories = named.length ? `<h2 class="section">${t('Buildings and their stories')}</h2><ul class="stories">${named.map(([bag, n]) => `
    <li><button class="story" data-bag="${bag}"><b>${esc(tr(n, 'name'))}</b><span>${esc(tr(n, 'story'))}</span></button></li>`).join('')}</ul>` : '';
  return `<div class="layer-detail"><p>${esc(tr(L, 'text'))}</p>${groups}${stories}
    ${L.caveat ? `<p class="caveat">${esc(tr(L, 'caveat'))}</p>` : ''}
    <a href="${L.source.url}" target="_blank" rel="noopener">${esc(tr(L.source, 'label'))}</a></div>`;
}

function setLayer(L) {
  if (L) uniforms.uLayerAt.value = performance.now() / 1000;
  activeLayer = L;
  const bits = Array(MAX_GROUPS).fill(-1);
  if (L) L.groups.forEach((g, i) => { if (i < MAX_GROUPS && groupOn[g.bit] !== false) bits[i] = g.bit; });
  uniforms.uGroupBit.value = bits;
  renderPanel(); drawHist();
}

// The heat colouring isolates sources with the periods' mask: entering or leaving it shows every building again.
function setMode(m) {
  if ((m === MODE.heat) !== (uniforms.uMode.value === MODE.heat)) maskTarget = periods.map(() => 1);
  uniforms.uMode.value = m;
}
document.querySelectorAll('.modes button[data-mode]').forEach(b => b.onclick = () => {
  if (photoOn) setPhoto(false);
  if (streetsOn) setStreets(false);
  if (viewOn) setView(false);
  setMode(+b.dataset.mode);
  markTabs();
  const bits = Array(MAX_GROUPS).fill(-1);
  if (activeLayer) activeLayer.groups.forEach((g, i) => { if (groupOn[g.bit] !== false) bits[i] = g.bit; });
  uniforms.uGroupBit.value = bits;
  if (uniforms.uMode.value === MODE.layers && activeLayer) uniforms.uLayerAt.value = performance.now() / 1000;
  // A folded legend opens only when there is a choice to make: a layer to pick.
  if (uniforms.uMode.value === MODE.layers && !activeLayer) setCollapsed(false);
  renderPanel(); drawHist();
});


// ---------- Timeline ----------
const hist = document.getElementById('hist');
const hctx = hist.getContext('2d');
const T0 = Math.floor(config.yearMin / 50) * 50, T1 = config.yearMax + 1;
const years = Object.entries(config.histogram).map(([y, v]) => [+y, v]);
const demolished = Object.entries(config.demolished).map(([y, v]) => [+y, v]);  // they leave the count in these years
const yMax = Math.max(...years.map(([, v]) => v.reduce((a, b) => a + b, 0)));
// The timeline's years: the city's, or in the parking fines' view only theirs, a bar a year.
const span = () => fineView() ? [fineView().span[0], fineView().span[1] + 1] : [T0, T1];
const xOf = y => { const [a, b] = span(); return (y - a) / (b - a) * hist.clientWidth; };
const yearOf = x => { const [a, b] = span(), y = a + x / hist.clientWidth * (b - a); return fineView() ? Math.floor(y) : Math.round(y); };

function layerGroupsShown() {
  if (uniforms.uMode.value !== MODE.layers || !activeLayer) return [];
  return activeLayer.groups.map((g, i) => ({ ...g, color: GROUP_COLORS[i] })).filter(g => groupOn[g.bit] !== false);
}

function visibleCount() {
  const Y = uniforms.uYear.value;
  if (uniforms.uMode.value === MODE.gone) return demolished.reduce((n, [y, v]) => n + (y <= Y ? v.reduce((a, b) => a + b, 0) : 0), 0);
  // a heat source seen alone: those of it built by then, less the torn down, who all have none recorded
  if (uniforms.uMode.value === MODE.heat && !maskTarget.every(Boolean))
    return Object.entries(config.heat.years).reduce((n, [y, v]) => n + (+y <= Y ? v.reduce((a, c, i) => a + (maskTarget[i] ? c : 0), 0) : 0), 0)
      - (maskTarget[0] ? demolished.reduce((n, [y, v]) => n + (y <= Y ? v.reduce((a, b) => a + b, 0) : 0), 0) : 0);
  const shown = layerGroupsShown();
  if (shown.length) return shown.reduce((n, g) => n + Object.entries(g.years).reduce((m, [y, c]) => m + (+y <= Y ? c : 0), 0), 0);
  let n = 0;
  const count = (hist, sign) => { for (const [y, v] of hist) if (y <= Y) v.forEach((c, i) => { if (uniforms.uMode.value !== MODE.period || maskTarget[i]) n += sign * c; }); };
  count(years, 1);
  count(demolished, -1);
  return n;
}

function drawHist() {
  const w = hist.clientWidth, h = hist.clientHeight, dpr = devicePixelRatio;
  hist.width = w * dpr; hist.height = h * dpr;
  hctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  hctx.clearRect(0, 0, w, h);
  if (fineView()) return drawFineYears(fineView(), w, h);
  const plotH = h - 20, bw = Math.max(1, w / (T1 - T0));
  const Y = uniforms.uYear.value, Yf = uniforms.uYearFrom.value;
  const shown = layerGroupsShown();
  const bar = (y, bh, top, color, on) => {
    hctx.fillStyle = color;
    hctx.globalAlpha = on ? (y <= Yf ? 0.3 : 1) : 0.18;
    hctx.fillRect(xOf(y), top - bh, bw, bh);
  };
  if (shown.length) {
    // Layer mode: the city in grey behind, the layer's own buildings in its colours.
    for (const [y, v] of years) {
      const bh = Math.sqrt(v.reduce((a, b) => a + b, 0) / yMax) * (plotH - 6);
      bar(y, bh, plotH, '#b9c0c4', false);
    }
    // Stack the groups per year; the stack's total height follows sqrt(total), split in proportion.
    const total = {};
    for (const g of shown) for (const [y, c] of Object.entries(g.years)) total[y] = (total[y] || 0) + c;
    const lMax = Math.max(1, ...Object.values(total));
    const stack = {};
    for (const g of shown) for (const [ys, c] of Object.entries(g.years)) {
      const y = +ys, full = Math.sqrt(total[ys] / lMax) * (plotH - 6) * 0.9, bh = full * c / total[ys];
      bar(y, bh, plotH - (stack[y] || 0), g.color, y <= Y);
      stack[y] = (stack[y] || 0) + bh;
    }
  } else {
    for (const [y, v] of years) {
      let top = plotH;
      v.forEach((c, i) => {
        if (!c) return;
        const bh = Math.sqrt(c / yMax) * (plotH - 6);
        const masked = uniforms.uMode.value === MODE.period && !maskTarget[i];
        bar(y, bh, top, periods[i].color, !masked && y <= Y);
        top -= bh;
      });
    }
  }
  hctx.globalAlpha = 1;
  hctx.fillStyle = '#5d6266';
  hctx.font = '500 11px "Schibsted Grotesk", sans-serif';
  const step = w < 500 ? 200 : 100;
  for (let y = Math.ceil(T0 / step) * step; y <= T1; y += step) hctx.fillText(y, Math.min(w - 28, Math.max(0, xOf(y) - 13)), h - 4);
  hctx.fillStyle = '#000';
  hctx.fillRect(xOf(Y) - 1, 0, 2, plotH);
  if (Yf >= T0) { hctx.fillStyle = '#5d6266'; hctx.fillRect(xOf(Yf) - 0.5, 0, 1, plotH); }
  // at the end of the timeline the map shows the city as it stands, not a year that reads like a date
  document.getElementById('year').textContent = Y >= config.yearMax ? t('Today') : Math.round(Y);
  document.getElementById('count').textContent = fmt(visibleCount());
  document.querySelector('.tally-count').childNodes[1].textContent = ' ' + t(uniforms.uMode.value === MODE.gone ? 'torn down' : 'buildings');
}

// The parking fines' timeline: a bar a year, as tall as the year's fines, the year shown in full; the tally counts them.
function drawFineYears(E, w, h) {
  const plotH = h - 20, Y = Math.floor(uniforms.uYear.value), [a, b] = E.span, d = E.data;
  const max = d ? Math.max(...d.totals) : 1;
  hctx.font = '500 11px "Schibsted Grotesk", sans-serif';
  for (let y = a; y <= b; y++) {
    const x0 = xOf(y) + 2, x1 = xOf(y + 1) - 2, bh = d ? d.totals[y - a] / max * (plotH - 6) : 0;
    hctx.globalAlpha = y === Y ? 1 : 0.3;
    hctx.fillStyle = FINE_COLORS[4];
    hctx.fillRect(x0, plotH - bh, x1 - x0, bh);
    hctx.globalAlpha = 1;
    hctx.fillStyle = y === Y ? '#000' : '#5d6266';
    if (w >= 500 || (y - a) % 2 === 0 || y === Y) hctx.fillText(y, (x0 + x1) / 2 - 13, h - 4);
  }
  document.getElementById('year').textContent = Y;
  document.getElementById('count').textContent = d ? fmt(d.totals[Y - a]) : '';
  document.querySelector('.tally-count').childNodes[1].textContent = ' ' + t('fines');
}

let handle = null;
hist.addEventListener('pointerdown', e => {
  hist.setPointerCapture(e.pointerId);
  const x = e.offsetX;
  handle = !fineView() && Math.abs(x - xOf(uniforms.uYearFrom.value)) < Math.abs(x - xOf(uniforms.uYear.value)) ? 'uYearFrom' : 'uYear';
  moveHandle(x);
  stopPlay();
});
hist.addEventListener('pointermove', e => handle && moveHandle(e.offsetX));
hist.addEventListener('pointerup', () => handle = null);
function moveHandle(x) {
  const [a, b] = span(), y = Math.max(a, Math.min(Math.min(b - 1, config.yearMax), yearOf(x)));
  if (handle === 'uYear') uniforms.uYear.value = Math.max(y, uniforms.uYearFrom.value + 1);
  else uniforms.uYearFrom.value = Math.min(y, uniforms.uYear.value - 1);
  drawHist();
}

// Play: quickly through the sparse centuries, then slowly through the dense ones.
let playing = false, playT0 = 0, playStart = 0;
const playBtn = document.getElementById('play');
const playIcon = document.getElementById('play-icon');
const DURATION = (+new URLSearchParams(location.search).get('film') || 30) * 1000; // ?film=6 for a short film
function playYear(t) {
  if (fineView()) { const [a, b] = span(); return a + (b - a) * Math.min(t, 0.9999); }  // the fines' years, each as long
  const k = 0.35; // share of time spent before 1850
  return t < k ? T0 + (1850 - T0) * (t / k) : 1850 + (config.yearMax - 1850) * ((t - k) / (1 - k));
}
function startPlay() {
  playing = true; playStart = performance.now();
  if (uniforms.uYear.value >= Math.min(span()[1] - 1, config.yearMax)) uniforms.uYear.value = span()[0];
  playT0 = 0;
  while (playT0 < 1 && playYear(playT0) < uniforms.uYear.value) playT0 += 0.001;
  playIcon.setAttribute('d', 'M4 2.5h3v11H4zM9 2.5h3v11H9z');
  uniforms.uPlaying.value = 1;
  playBtn.setAttribute('aria-label', t('Pause'));
}
function stopPlay() {
  playing = false;
  uniforms.uPlaying.value = 0;
  uniforms.uRise.value = 0.01;
  uniforms.uYear.value = (fineView() ? Math.floor : Math.round)(uniforms.uYear.value);
  playIcon.setAttribute('d', 'M4 2.5v11l9-5.5z');
  playBtn.setAttribute('aria-label', "Play the city's growth");
}
playBtn.onclick = () => playing ? stopPlay() : startPlay();

// ---------- Loop ----------
function resize() {
  const w = innerWidth, h = innerHeight;
  renderer.setSize(w, h, false);
  camera.aspect = w / h;
  camera.updateProjectionMatrix();
  photo?.setResolutionFromRenderer(camera, renderer);
  drawHist();
}
addEventListener('resize', resize);
function applyStaticText() {
  document.documentElement.lang = LANG;
  document.title = t('Helsinki, building by building');
  document.querySelector('.dek').textContent = t('Every building standing today, by the year it was completed.');
  document.querySelector('.about-open').textContent = t('About');
  document.querySelectorAll('[data-lang-block]').forEach(a => { a.hidden = a.dataset.langBlock !== LANG; });
  document.querySelectorAll('.modes button[data-mode]').forEach(b => { b.textContent = t(b.dataset.label); });
  document.querySelector('.quests-open span').textContent = t('Quests');
  streetsBtn.textContent = t('Street names');
  drawPicks();
  document.querySelector('.photo-years').setAttribute('aria-label', t('Year of the aerial photos'));
  drawGroundBox();
  document.querySelector('.howto').textContent = t('Drag to turn. Right-drag or Shift-drag to move. Scroll to zoom.');
  const ld = document.getElementById('loading'); if (ld.firstChild) ld.firstChild.textContent = t('Building the city') + ' ';
  playBtn.setAttribute('aria-label', t(playing ? 'Pause' : "Play the city's growth"));
  document.querySelectorAll('.lang [data-lang]').forEach(b => b.setAttribute('aria-pressed', b.dataset.lang === LANG));
  sheetHandle.textContent = t(panelEl.classList.contains('collapsed') ? 'Show legend' : 'Hide legend');
}
document.querySelectorAll('.modes button[data-mode]').forEach(b => { b.dataset.label = b.textContent.trim(); });
const about = document.getElementById('about');
document.querySelector('.about-open').onclick = () => about.showModal();
about.querySelector('.about-close').onclick = () => about.close();
about.addEventListener('click', e => { if (e.target === about) about.close(); });

function setLang(l) {
  LANG = l;
  try { localStorage.setItem('lang', l); } catch {}
  const u = new URL(location.href); u.searchParams.set('lang', l); history.replaceState(null, '', u);
  applyStaticText(); renderPanel(); drawHist();
  if (pinnedGid >= 0) pinCard(pinnedGid, ...lastPin);
  else if (pinnedStreet) pinStreet(pinnedStreet, ...lastPin);
  else if (pinnedSite?.street) pinFine(pinnedSite.era, pinnedSite.name, ...lastPin);
  else if (pinnedSite) pinSite(pinnedSite, ...lastPin);
  if (quest && !questEl.hidden && !questEl.classList.contains('done')) renderQuest();
  if (questsDlg.open) renderQuestList();
}
document.querySelectorAll('.lang [data-lang]').forEach(b => b.onclick = () => setLang(b.dataset.lang));
applyStaticText();
renderPanel();
resize();
document.fonts?.ready.then(drawHist);

let frame = 0;
renderer.setAnimationLoop(now => {
  frame++;
  stepFlight(now);
  uniforms.uNow.value = now / 1000;
  uniforms.uMask.value = maskTarget;
  controls.update();
  const dist = camera.position.distanceTo(controls.target);
  uniforms.uFog.value.set(dist * 1.6, dist * 4);
  if (frame % 6 === 0) updateLabels(dist);
  if (playing) {
    const t = Math.min(1, playT0 + (now - playStart) / DURATION);
    uniforms.uYear.value = playYear(t);
    // A flight lasts about 0.8 s on screen whatever the film's pace: as many years as the film covers in that time.
    uniforms.uRise.value = Math.max(2, (playYear(Math.min(1, t + 800 / DURATION)) - playYear(t)));
    if (t >= 1) stopPlay();
    drawHist();
  }
  // ponytail: a ray into the aerial mesh costs ~15 ms close up (450k triangles), so it hovers at 5 Hz; a BVH
  // (three-mesh-bvh) would let it keep pace with the blocks' GPU pick
  if (pointer && !dragging && !(streetsOn && !photoOn) && frame % (photoOn ? 12 : 3) === 0) {
    const site = pickSite(pointer[0], pointer[1]);
    canvas.style.cursor = site ? 'pointer' : '';
    const gid = site || viewNow() ? -1 : photoOn ? pickPhoto(pointer[0], pointer[1]) : pick(pointer[0], pointer[1]);
    uniforms.uHover.value = gid;
    if (site) showSite(site, pointer[0], pointer[1]); else showCard(gid, pointer[0], pointer[1]);
  }
  showView();
  camera.updateMatrixWorld();
  updateGround();
  if (photoOn && photo) photo.update();
  renderer.render(scene, camera);
});


window.__dbg = { renderer, pick, pickPhoto, setPhoto, get photo() { return photo; }, pickStreet, setStreets, get streetMap() { return streetMap; }, uniforms, camera, controls, setLayer, layers, pinCard, showCard, building, labelGroup, labels, flyTo, startPlay, gidOf, questClick, startQuest, get quests() { return quests; } };
