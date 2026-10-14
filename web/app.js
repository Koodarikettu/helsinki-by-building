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
// Solar shares the Energy button: the panel switches between the two.
const MODE = { period: 0, floors: 1, energy: 2, layers: 3, solar: 4 };
// Energy labels G … A (index 1–7; 0 = no label), from red through yellow to green.
const ENERGY_COLORS = ['#efeee9', '#c1272d', '#e4572e', '#f08a24', '#f6c445', '#c9d64a', '#8cc152', '#2e9a49'];
// Solar potential: none, no suitable roof, then the steps of config.solar.steps from pale yellow to deep orange.
const SOLAR_COLORS = ['#efeee9', '#c4c9cc', '#fbeeb0', '#f9dc7a', '#f6c445', '#f0a830', '#e88a24', '#d9661f', '#bf4a1c', '#8f2f14'];

const [config, layers, attrBuf, info] = await Promise.all([
  fetch('data/helsinki.json').then(r => r.json()),
  fetch('data/layers.json').then(r => r.json()),
  fetch('data/attrs.bin').then(r => r.arrayBuffer()),
  fetch('data/info.json').then(r => r.json()),   // per building: id (VTJ-PRT or the city's feature id), address
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
  'Period': 'Aikakausi', 'Context layers': 'Kontekstitasot', 'Floors': 'Kerrokset', 'Energy': 'Energia', 'Aerial': 'Ilmakuva', 'Old maps': 'Vanhat kartat', 'Aerial photo': 'Ilmakuva', 'Map': 'Kartta',
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
  'Street name, in Finnish': 'Kadun nimi', 'History of the name': 'Nimen historia', 'Energy certificate register': 'Energiatodistusrekisteri',
  'HSY solar potential': 'HSY:n aurinkosähköpotentiaali', 'Helsinki place names': 'Helsingin nimistö', 'MWh a year': 'MWh vuodessa',
  'Demolished': 'Purettu', 'Demolished building': 'Purettu rakennus', 'Helsinki 3D city model': 'Helsingin 3D-kaupunkimalli',
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
  uHover: { value: -1 },
  uSelected: { value: -1 },
  uBlind: { value: 0 },
  uFogColor: { value: col(SKY) },
  uFog: { value: new THREE.Vector2(9000, 26000) },
};

const VERT = /* glsl */`
  in float bld;
  uniform sampler2D uAttr;
  uniform float uYear, uYearFrom, uMode, uHover, uSelected, uBlind, uNow, uBorn, uPlaying, uRise, uLayerAt;
  uniform vec3 uPalette[${periods.length}];
  uniform float uMask[${periods.length}];
  uniform int uGroupBit[${MAX_GROUPS}];
  uniform vec3 uGroupColor[${MAX_GROUPS}];
  uniform vec3 uMaquette;
  uniform vec3 uEnergy[${ENERGY_COLORS.length}];
  uniform vec3 uSolar[${SOLAR_COLORS.length}];
  out vec3 vColor;
  out vec3 vWorld;
  out float vGid;

  vec3 floorsRamp(float f) {
    float t = clamp(log(f) / log(40.0), 0.0, 1.0);
    vec3 a = vec3(0.86, 0.89, 0.90), b = vec3(0.49, 0.66, 0.75), c = vec3(0.17, 0.36, 0.55), d = vec3(0.05, 0.10, 0.25);
    return t < 0.33 ? mix(a, b, t / 0.33) : t < 0.66 ? mix(b, c, (t - 0.33) / 0.33) : mix(c, d, (t - 0.66) / 0.34);
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
    vGid = a.w;
    float vis = uMode < 1.5 ? uMask[period] : 1.0;
    float g = clamp((uYear - year + 1.0) / uRise, 0.0, 1.0);
    g = g * g * (3.0 - 2.0 * g);
    if (g <= 0.003 || vis <= 0.003 || (gone > 0.0 && uYear >= gone)) { gl_Position = vec4(2.0, 2.0, 2.0, 1.0); return; }

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
      c = floorsRamp(mod(a.z, 128.0));
    } else if (uMode < 2.5) {
      c = uEnergy[int(mod(a.z / 128.0, 8.0))];
    } else if (uMode > 3.5) {
      c = uSolar[int(a.z / 1024.0)];
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
    if (gone > 0.0) c = mix(c, vec3(1.0), 0.6);  // a ghost: torn down since
    // A quest's question about one building turns it red; a year riddle also hides every other age.
    if (uBlind > 0.5 && vGid == uSelected) c = vec3(0.925, 0.0, 0.0);
    else if (uBlind > 0.5 && uBlind < 1.5) c = uMaquette;
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
  flat.visible = labelGroup.visible = true;
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
const PHOTOS = {
  2017: ['https://kartta.hel.fi/3d/mesh/Helsinki_2017/tileset.json', 17.6],
  2024: ['https://kartta.hel.fi/3d/mesh/Helsinki_2024/2/tileset.json', 0],  // 1/ is an untextured floor
};
const DEG = THREE.MathUtils.DEG2RAD;
let photo = null, photoLoad = null, photoOn = false, photoYear = 2024;
async function loadPhoto() {
  const [{ TilesRenderer, WGS84_ELLIPSOID: E }, { GLTFLoader }, { DRACOLoader }] = await Promise.all([
    import('./vendor/3d-tiles-renderer/index.three.js'),
    import('three/addons/loaders/GLTFLoader.js'),
    import('three/addons/loaders/DRACOLoader.js'),
  ]);
  const [url, geoid] = PHOTOS[photoYear], tiles = new TilesRenderer(url);
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
  document.querySelector('.photo-mode').setAttribute('aria-pressed', on);
  const m = uniforms.uMode.value === MODE.solar ? MODE.energy : uniforms.uMode.value;
  document.querySelectorAll('.modes button[data-mode]').forEach(b => b.setAttribute('aria-pressed', !on && +b.dataset.mode === m));
  blocks.visible = flat.visible = labelGroup.visible = !on;
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

// ---------- Old maps and aerial photos ----------
// On the ground under the year's buildings, when switched on: the city's map or aerial photo of that year or the
// nearest before it (WMS in ETRS-GK25, CC BY 4.0). A quadtree of 512 px tiles, each split once its pixels would show
// larger than the screen's. Outside a map's sheet, and where a photo has nothing, the server paints black: left out.
const GROUND_WMS = 'https://kartta.hel.fi/ws/geoserver/avoindata/wms';
const GROUND = [
  [1749, 'Pitajakuvauskartta_1749'], [1780, 'Rekognosointikartta_1780_1782'], [1820, 'Asemakaavakartta_1820'],
  [1838, 'Asemakaavakartta_1838'], [1870, 'Senaatinkartta_1870'], [1878, 'Asemakaavakartta_1878'],
  [1900, 'Plan_af_Helsingfors_1900'], [1909, 'Kartta_Helsingin_kaupungista_ja_sen_alueista_1909'],
  [1917, 'Helsingin_kaupunki_1917_1918'], [1925, 'Helsingin_kaupungin_kartta_1925'],
  ...[1932, 1943, 1950, 1964, 1969, 1976, 1988, 1996].map(y => [y, `Ortoilmakuva_${y}`]),
  [2008, 'Ortoilmakuva_2008_25cm'], [2017, 'Ortoilmakuva_2017_20cm'], [2021, 'Ortoilmakuva_2021_10cm'],
  [2025, 'Ortoilmakuva_2025_5cm'],
];  // years whose map or photo covers the city; the rest cover a strip or leave holes
const GROUND_ROOT = 65536, GROUND_PX = 512;
const GROUND_SHADER = {
  glslVersion: THREE.GLSL3,
  depthTest: false,  // drawn after the land and water, over them; the buildings come after and stand on it
  vertexShader: 'out vec2 vUv; void main() { vUv = uv; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }',
  fragmentShader: `precision highp float; uniform sampler2D map; in vec2 vUv; out vec4 outColor;
    void main() { vec3 c = texture(map, vUv).rgb; if (max(c.r, max(c.g, c.b)) < 0.035) discard; outColor = vec4(c, 1.0); }`,
};
const ground = new THREE.Group();
scene.add(ground);
land.renderOrder = water.renderOrder = -2;
const groundTiles = new Map(), groundLoader = new THREE.TextureLoader();
const groundGeo = new THREE.PlaneGeometry(1, 1).rotateX(-Math.PI / 2);
let groundOn = false, groundSrc = null, groundPrev = null;
const groundAt = Y => GROUND.findLast(([y]) => y <= Y);

function groundTile(src, L, i, j, load) {
  const key = `${src}/${L}/${i}/${j}`;
  let t = groundTiles.get(key);
  if (!t && load) {
    const s = GROUND_ROOT / 2 ** L, x = -GROUND_ROOT / 2 + i * s, z = -GROUND_ROOT / 2 + j * s;
    const e = config.origin[0] + x, n = config.origin[1] - z;  // west and north edges; WMS 1.3.0 puts northing first
    groundTiles.set(key, t = { mesh: null, ready: false, used: 0 });
    groundLoader.load(`${GROUND_WMS}?service=WMS&version=1.3.0&request=GetMap&layers=avoindata:${src}&styles=&crs=EPSG:3879` +
      `&bbox=${n - s},${e},${n},${e + s}&width=${GROUND_PX}&height=${GROUND_PX}&format=image/jpeg&bgcolor=0x000000`, tex => {
      Object.assign(tex, { colorSpace: THREE.NoColorSpace, anisotropy: 8 });
      t.mesh = new THREE.Mesh(groundGeo, new THREE.ShaderMaterial({ ...GROUND_SHADER, uniforms: { map: { value: tex } } }));
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
  const src = groundAt(uniforms.uYear.value)?.[1] ?? null;
  if (src !== groundSrc) { groundPrev = groundSrc; groundSrc = src; drawGroundCaption(); }
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
const groundBtn = document.getElementById('ground');
function setGround(on) { groundOn = on; groundBtn.setAttribute('aria-pressed', on); drawGroundCaption(); }
groundBtn.onclick = () => setGround(!groundOn);
function drawGroundCaption() {
  const g = groundOn && groundAt(uniforms.uYear.value);
  document.getElementById('ground-src').textContent = g ? `${t(g[1].startsWith('Orto') ? 'Aerial photo' : 'Map')} ${g[0]}` : '';
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
    ${p.desc ? `<div class="desc">${esc(p.desc)}</div>` : ''}
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
// Images and records straight from Finna; medium is 600 px wide.
const FINNA_IMG = id => `https://api.finna.fi/Cover/Show?source=Solr&id=${encodeURIComponent(id)}&index=0&size=medium`;
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
  fig.classList.toggle('sv', !!s.sv);
  const year = fig.querySelector('.year');
  if (year) year.textContent = s.label;
  fig.querySelector('figcaption').innerHTML = s.credit;
  const nav = fig.querySelector('.years');
  if (nav) {
    nav.innerHTML = slides.map((x, k) => `<button data-slide="${k}"${k === slide ? ' aria-current="true"' : ''}>${x.label}</button>`).join('');
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
    if (slides.length < 2) { fig.remove(); return; }
    fig.classList.add('failed');
    fig.querySelector('.frame .gone')?.remove();
    fig.querySelector('.frame').insertAdjacentHTML('afterbegin', `<p class="gone">${t('This photo did not load.')}${
      slides[slide].page ? ` ${link(slides[slide].page, t('Open it in the archive'))}` : ''}</p>`);
  });
  fig.querySelector('img').addEventListener('load', () => { fig.classList.remove('failed'); fig.querySelector('.frame .gone')?.remove(); });
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
    pinned && b.bag.length === 10 && [t('Building ID'), esc(b.bag)],
  ].filter(Boolean);
  // Why the street of its address is so named, in Finnish: the reason first, the older history folded under it.
  const street = b.addr.replace(/\s+\d.*$/, ''), named = pinned && streetNames[street];
  const naming = named && `<section class="naming"><h4>${t('Street name, in Finnish')}</h4><p class="why" lang="fi"><b>${esc(street)}.</b> ${esc(named[0] || named[1])}</p>
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
      : `<p class="hint">${w?.wiki || b.groups.some(g => g.layer.notes?.[b.bag]) ? t('Click for the story and sources') : t('Click to keep this card open')}</p>`}`;
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
  if (pinnedGid >= 0 || phone.matches) return;
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
  if (pinnedGid < 0) card.hidden = true;
});
canvas.addEventListener('pointerup', e => {
  dragging = false;
  if (!downAt || Math.hypot(e.clientX - downAt[0], e.clientY - downAt[1]) > 5) return;
  const gid = photoOn ? pickPhoto(e.clientX, e.clientY) : pick(e.clientX, e.clientY);
  if (quest && !solved && qStep().kind === 'find') { questClick(gid); return; }
  if (cardsLocked()) return;
  pinCard(gid === pinnedGid ? -1 : gid, e.clientX, e.clientY);
});
canvas.addEventListener('pointerleave', () => { pointer = null; if (pinnedGid < 0) card.hidden = true; uniforms.uHover.value = -1; });

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
  if (mode === MODE.period) {
    panel.innerHTML = `<h2>${t('Built in')}</h2><div class="swatches">${periods.map((p, i) => `
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
  } else if (mode === MODE.floors) {
    panel.innerHTML = `<h2>${t('Storeys')}</h2>
      <div class="ramp" style="background:linear-gradient(90deg,#dbe3e6,#7da8bf,#2b5c8c,#0d1a40)"></div>
      <div class="ramp-scale"><span>1</span><span>3</span><span>8</span><span>20</span><span>40+</span></div>
      <p class="note">${LANG === 'fi' ? `${fmt(config.stats.floorsRegister)} rakennuksen kerrosluku on rakennusrekisteristä; loput ${fmt(config.stats.floorsAssumed)} ovat lähes kaikki pieniä talousrakennuksia. ${fmt(config.stats.heightModel)} rakennuksen korkeus on kaupungin 3D-mallista: kattopintojen korkeuden 70. persentiili. Muiden korkeus on kerrosluku kertaa 3,2 m.` : `${fmt(config.stats.floorsRegister)} buildings take their floors from the building register; the other ${fmt(config.stats.floorsAssumed)} are nearly all small outbuildings. ${fmt(config.stats.heightModel)} buildings take their height from the city's 3D model: the 70th percentile of their roof surfaces. The rest are floors times 3.2 m.`}</p>`;
  } else if (mode === MODE.energy || mode === MODE.solar) {
    const sub = `<div class="sub" role="group" aria-label="${t('Energy')}">${[MODE.energy, MODE.solar].map(m => `
      <button data-sub="${m}" aria-pressed="${m === mode}">${t(m === MODE.energy ? 'Energy label' : 'Solar potential')}</button>`).join('')}</div>`;
    const row = (color, label, n) => `<div><i style="background:${color}"></i><span>${label}</span><span class="n">${fmt(n)}</span></div>`;
    if (mode === MODE.energy) {
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
    panel.querySelectorAll('.sub button').forEach(b => b.onclick = () => { uniforms.uMode.value = +b.dataset.sub; renderPanel(); });
  } else if (activeLayer && activeLayer === residentsLayer) {
    const notes = Object.entries(residentsLayer?.notes || {});
    const people = notes.flatMap(([bag, n]) => n.people.map(p => ({ ...p, bag, at: n.at })))
      .sort((a, b) => b.links - a.links);
    panel.innerHTML = `<button class="back">${t('All context layers')}</button><h2 class="layer-title">${esc(tr(residentsLayer, 'title'))}</h2>
      <p class="layer-intro">${esc(tr(residentsLayer, 'text') || '')}</p>
      <input class="filter" type="search" placeholder="${t('Find a person')}" aria-label="${t('Find a person')}">
      <ul class="stories people">${people.map(p => `<li data-q="${esc((p.person + ' ' + (p.desc || '')).toLowerCase())}">
        <button class="story" data-bag="${p.bag}"><b>${esc(p.person)}</b>
        <span>${[p.born && p.died ? `${p.born}–${p.died}` : p.born, p.desc].filter(Boolean).map(esc).join(', ')}</span>
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

document.querySelectorAll('.modes button[data-mode]').forEach(b => b.onclick = () => {
  if (photoOn) setPhoto(false);
  uniforms.uMode.value = +b.dataset.mode;
  document.querySelectorAll('.modes button[data-mode]').forEach(x => x.setAttribute('aria-pressed', x === b));
  const bits = Array(MAX_GROUPS).fill(-1);
  if (activeLayer) activeLayer.groups.forEach((g, i) => { if (groupOn[g.bit] !== false) bits[i] = g.bit; });
  uniforms.uGroupBit.value = bits;
  if (uniforms.uMode.value === MODE.layers && activeLayer) uniforms.uLayerAt.value = performance.now() / 1000;
  // On a phone the sheet opens only when there is a choice to make: a layer to pick.
  if (!phone.matches || (uniforms.uMode.value === MODE.layers && !activeLayer)) setCollapsed(false);
  renderPanel(); drawHist();
});

document.querySelector('.photo-mode').onclick = () => setPhoto(!photoOn);

// ---------- Timeline ----------
const hist = document.getElementById('hist');
const hctx = hist.getContext('2d');
const T0 = Math.floor(config.yearMin / 50) * 50, T1 = config.yearMax + 1;
const years = Object.entries(config.histogram).map(([y, v]) => [+y, v]);
const demolished = Object.entries(config.demolished).map(([y, v]) => [+y, v]);  // they leave the count in these years
const yMax = Math.max(...years.map(([, v]) => v.reduce((a, b) => a + b, 0)));
const xOf = y => (y - T0) / (T1 - T0) * hist.clientWidth;
const yearOf = x => Math.round(T0 + x / hist.clientWidth * (T1 - T0));

function layerGroupsShown() {
  if (uniforms.uMode.value !== MODE.layers || !activeLayer) return [];
  return activeLayer.groups.map((g, i) => ({ ...g, color: GROUP_COLORS[i] })).filter(g => groupOn[g.bit] !== false);
}

function visibleCount() {
  const Y = uniforms.uYear.value;
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
}

let handle = null;
hist.addEventListener('pointerdown', e => {
  hist.setPointerCapture(e.pointerId);
  const x = e.offsetX;
  handle = Math.abs(x - xOf(uniforms.uYearFrom.value)) < Math.abs(x - xOf(uniforms.uYear.value)) ? 'uYearFrom' : 'uYear';
  moveHandle(x);
  stopPlay();
});
hist.addEventListener('pointermove', e => handle && moveHandle(e.offsetX));
hist.addEventListener('pointerup', () => handle = null);
function moveHandle(x) {
  const y = Math.max(T0, Math.min(config.yearMax, yearOf(x)));
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
  const k = 0.35; // share of time spent before 1850
  return t < k ? T0 + (1850 - T0) * (t / k) : 1850 + (config.yearMax - 1850) * ((t - k) / (1 - k));
}
function startPlay() {
  playing = true; playStart = performance.now();
  if (uniforms.uYear.value >= config.yearMax) uniforms.uYear.value = T0;
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
  uniforms.uYear.value = Math.round(uniforms.uYear.value);
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
  document.querySelector('.photo-mode').textContent = t('Aerial');
  groundBtn.textContent = t('Old maps');
  document.querySelector('.photo-years').setAttribute('aria-label', t('Year of the aerial photos'));
  drawGroundCaption();
  document.querySelector('.tally-count').childNodes[1].textContent = ' ' + t('buildings');
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
  if (pointer && !dragging && frame % (photoOn ? 12 : 3) === 0) {
    const gid = photoOn ? pickPhoto(pointer[0], pointer[1]) : pick(pointer[0], pointer[1]);
    uniforms.uHover.value = gid;
    showCard(gid, pointer[0], pointer[1]);
  }
  camera.updateMatrixWorld();
  updateGround();
  if (photoOn && photo) photo.update();
  renderer.render(scene, camera);
});


window.__dbg = { pick, pickPhoto, setPhoto, get photo() { return photo; }, uniforms, camera, controls, setLayer, layers, pinCard, showCard, building, labelGroup, labels, flyTo, startPlay, gidOf, questClick, startQuest, get quests() { return quests; } };
