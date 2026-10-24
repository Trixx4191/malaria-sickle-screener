import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { test } from 'node:test';
import vm from 'node:vm';

const source = readFileSync(new URL('../webapp/static/script.js', import.meta.url), 'utf8');
const html = readFileSync(new URL('../webapp/static/index.html', import.meta.url), 'utf8');

function harness(fetch, viewer = null) {
  class Element {
    constructor(tag = 'div') {
      this.tag = tag;
      this.children = [];
      this.style = {};
      this.listeners = {};
      const names = new Set();
      this.classList = {
        add: name => names.add(name),
        remove: name => names.delete(name),
        contains: name => names.has(name),
        toggle: (name, force) => force ? names.add(name) : names.delete(name),
      };
    }
    addEventListener(name, callback) { this.listeners[name] = callback; }
    appendChild(child) {
      this.children.push(child);
      if (child.tag === 'script') queueMicrotask(() => child.onerror());
    }
    set innerHTML(value) { this.markup = value; this.children = []; }
    get innerHTML() { return this.markup || ''; }
    querySelectorAll() { return []; }
    click() { this.clicked = true; }
    remove() { this.removed = true; }
  }
  const elements = Object.fromEntries([...html.matchAll(/id="([^"]+)"/g)].map(([, id]) => [id, new Element()]));
  const button = new Element('button');
  const created = [];
  const document = {
    events: {}, head: new Element('head'), body: new Element('body'),
    getElementById: id => elements[id],
    querySelector: () => button,
    querySelectorAll: () => [],
    createElement: tag => { const el = new Element(tag); created.push(el); return el; },
    addEventListener(name, callback) { this.events[name] = callback; },
  };
  Object.entries({gene_name:'HBB', gene_region:'exonic', allele_freq_afr:'0.01', cadd_score:'15', conservation_phylop:'0.5'}).forEach(([id,value]) => elements[id].value = value);
  const context = vm.createContext({
    document, fetch, console: { error() {} }, setTimeout, clearTimeout,
    AbortController, URL, Blob, window: viewer ? { $3Dmol: { createViewer: () => viewer } } : {},
  });
  vm.runInContext(source, context);
  return { context, document, elements, button, created };
}
const jsonResponse = (value, ok = true) => ({ ok, json: async () => value });
const flush = async () => { for (let i = 0; i < 5; i++) await new Promise(resolve => setImmediate(resolve)); };
const prediction = { tier:'pathogenic', color:'high', probability:84.2, notes:['Example interpretation'], contributions:[{feature:'cadd_score',weight:-1}], demo_mode:false, data_provenance:'real' };

test('failed optional viewer download leaves status and predictions functional', async () => {
  const h = harness(async url => {
    if (url === '/api/model-info') return jsonResponse({demo_mode:false,data_provenance:'real',meta:{model_type:'random_forest',auc_all:.98,training_variants:1805}});
    if (url === '/api/predict') return jsonResponse(prediction);
    return jsonResponse({}, false);
  });
  h.document.events.DOMContentLoaded();
  await flush();
  assert.match(h.elements['viewer-status'].textContent, /viewer unavailable/);
  assert.match(h.elements['status-bar'].textContent, /real data/);
  assert.equal(typeof h.elements['variant-form'].listeners.submit, 'function');
  h.elements['variant-form'].listeners.submit({ preventDefault() {} });
  await flush();
  assert.match(h.elements['prob-label'].textContent, /84.2%/);
  assert.equal(h.button.disabled, false);
  const fill = h.elements['contrib-bars'].children[0].children[1].children[0];
  assert.equal(fill.style.left, '0%');
  assert.equal(fill.style.width, '100%');
});

for (const key of ['effects', 'scores']) {
  test(`renders and ranks the ${key} heatmap schema`, () => {
    const h = harness(async () => jsonResponse({}, false));
    h.context.matrix = { positions:[{pos:6,wt:'E',[key]:{A:-2,C:-4}}] };
    vm.runInContext('renderMatrix(matrix); showColumnDetail(matrix, 6);', h.context);
    const table = h.elements['matrix-scroll'].children[0];
    assert.equal(table.children.length, 21);
    assert.match(table.children[1].innerHTML, /background:rgb\(/);
    const detail = h.elements['matrix-detail'].innerHTML;
    assert.ok(detail.indexOf('E6C') < detail.indexOf('E6A'));
    assert.match(detail, /-4\.00/);
  });
}

test('AlphaFold resolves current metadata URL and downloads the loaded PDB', async () => {
  const requests = [];
  const loaded = [];
  const pdbText = 'ATOM      1  CA  GLU A   6       1.000   2.000   3.000\n';
  const viewer = { clear() {}, render() {}, setStyle() {}, removeAllLabels() {}, zoomTo() {}, selectedAtoms() { return [{}]; }, addModel(text, format) { loaded.push({text,format}); } };
  const currentUrl = 'https://alphafold.ebi.ac.uk/files/AF-Q16570-F1-model_v99.pdb';
  const h = harness(async url => {
    requests.push(url);
    if (url === '/api/model-info') return jsonResponse({demo_mode:false,data_provenance:'real'});
    if (url === '/api/structure/DARC') return jsonResponse({pdb_id:'AF-Q16570-F1',chain:'A',source:'alphafold',label:'Predicted DARC'});
    if (url === 'https://alphafold.ebi.ac.uk/api/prediction/Q16570') return jsonResponse([{entryId:'AF-Q16570-F1_v99',pdbUrl:currentUrl}]);
    if (url === currentUrl) return {ok:true,text:async () => pdbText};
    return jsonResponse({}, false);
  }, viewer);
  h.elements.gene_name.value = 'DARC';
  h.document.events.DOMContentLoaded();
  await flush();
  assert.ok(requests.includes(currentUrl));
  assert.equal(requests.some(url => url.includes('rcsb.org')), false);
  assert.deepEqual(loaded, [{text:pdbText,format:'pdb'}]);
  assert.equal(h.elements['btn-download'].disabled, false);
  assert.equal(vm.runInContext('state.currentStructureText', h.context), pdbText);
  vm.runInContext('downloadStructure()', h.context);
  const download = h.created.find(el => el.tag === 'a');
  assert.equal(download.download, 'AF-Q16570-F1.pdb');
  assert.equal(download.clicked, true);
});

test('late structure responses cannot overwrite the newly selected gene', async () => {
  let releaseHbb;
  const pendingHbb = new Promise(resolve => { releaseHbb = resolve; });
  const loaded = [];
  const viewer = { clear() {}, render() {}, setStyle() {}, removeAllLabels() {}, zoomTo() {}, selectedAtoms() { return [{}]; }, addModel(text) { loaded.push(text); } };
  const h = harness(async url => {
    if (url === '/api/structure/HBB') return pendingHbb;
    if (url === '/api/structure/G6PD') return jsonResponse({pdb_id:'2BH9',chain:'A',source:'experimental',label:'G6PD'});
    if (url === 'https://files.rcsb.org/download/2BH9.pdb') return {ok:true,text:async () => 'G6PD atoms'};
    return jsonResponse({}, false);
  }, viewer);
  await vm.runInContext('initViewer()', h.context);
  const first = vm.runInContext('onGeneChange()', h.context);
  h.elements.gene_name.value = 'G6PD';
  await vm.runInContext('onGeneChange()', h.context);
  releaseHbb(jsonResponse({pdb_id:'2HHB',chain:'B',source:'experimental',label:'HBB'}));
  await first;
  assert.deepEqual(loaded, ['G6PD atoms']);
  assert.equal(vm.runInContext('state.currentPdbId', h.context), '2BH9');
});

test('secondary structure and element colors survive predictions and residue highlighting', async () => {
  const atoms = [
    {chain:'B',resi:6,atom:'CA',elem:'C',x:1,y:2,z:3},
    {chain:'B',resi:6,atom:'N',elem:'N',x:2,y:2,z:3},
    {chain:'B',resi:6,atom:'O',elem:'O',x:3,y:2,z:3},
    {chain:'B',resi:8,atom:'CA',elem:'C',x:4,y:2,z:3},
    {chain:'A',resi:6,atom:'CA',elem:'C',x:5,y:2,z:3},
  ];
  const labels = [];
  const zoomSelections = [];
  const selectedAtoms = selection => atoms.filter(atom =>
    Object.entries(selection).every(([key,value]) => atom[key] === value)
  );
  const viewer = {
    clear() {}, render() {}, addModel() {}, zoom() {},
    selectedAtoms,
    setStyle(selection, style) {
      for (const atom of selectedAtoms(selection)) atom.style = JSON.parse(JSON.stringify(style));
    },
    removeAllLabels() { labels.length = 0; },
    addLabel(text, options) { labels.push({text,options:JSON.parse(JSON.stringify(options))}); },
    zoomTo(selection) { zoomSelections.push(selection ? JSON.parse(JSON.stringify(selection)) : null); },
  };
  let result = prediction;
  const h = harness(async url => {
    if (url === '/api/model-info') return jsonResponse({demo_mode:false,data_provenance:'real'});
    if (url === '/api/structure/HBB') return jsonResponse({pdb_id:'2HHB',chain:'B',source:'experimental',label:'Hemoglobin'});
    if (url === 'https://files.rcsb.org/download/2HHB.pdb') return {ok:true,text:async () => 'Hemoglobin fixture'};
    if (url === '/api/predict') return jsonResponse(result);
    return jsonResponse({}, false);
  }, viewer);
  h.document.events.DOMContentLoaded();
  await flush();

  const assertCartoonColors = () => {
    for (const atom of atoms) {
      assert.equal(atom.style.cartoon.colorscheme, 'ssPyMol');
      assert.equal(atom.style.cartoon.arrows, true);
      assert.equal(atom.style.cartoon.color, undefined);
      assert.equal(atom.style.cartoon.opacity, atom.chain === 'B' ? 1 : 0.35);
    }
  };
  assertCartoonColors();
  const initialStyles = JSON.stringify(atoms.map(atom => atom.style));
  await vm.runInContext('submitPrediction()', h.context);
  assert.match(h.elements['prob-label'].textContent, /84.2%/);
  assert.equal(JSON.stringify(atoms.map(atom => atom.style)), initialStyles);

  vm.runInContext('highlightResidue(6, "GLU", "VAL", "residue 6 illustration")', h.context);
  assertCartoonColors();
  for (const atom of atoms) {
    const highlighted = atom.chain === 'B' && atom.resi === 6;
    assert.equal(Boolean(atom.style.stick), highlighted);
    assert.equal(Boolean(atom.style.sphere), highlighted);
    if (highlighted) {
      assert.equal(atom.style.stick.colorscheme, 'Jmol');
      assert.equal(atom.style.sphere.colorscheme, 'Jmol');
      assert.equal(atom.style.stick.color, undefined);
      assert.equal(atom.style.sphere.color, undefined);
    }
  }
  assert.equal(labels.length, 1);
  assert.equal(labels[0].text, 'residue 6 illustration');
  assert.deepEqual(labels[0].options.position, {x:1,y:2,z:3});
  assert.deepEqual(zoomSelections.at(-1), {chain:'B',resi:6});

  const highlightedStyles = JSON.stringify(atoms.map(atom => atom.style));
  result = {...prediction,tier:'benign',color:'low',probability:4};
  await vm.runInContext('submitPrediction()', h.context);
  assert.match(h.elements['prob-label'].textContent, /4%/);
  assert.equal(JSON.stringify(atoms.map(atom => atom.style)), highlightedStyles);
  assertCartoonColors();
  assert.equal(labels.length, 1);
});

test('older predictions cannot overwrite a newer request or unlock its submit button', async () => {
  const pending = [];
  const h = harness(url => url === '/api/predict'
    ? new Promise(resolve => pending.push(resolve))
    : Promise.resolve(jsonResponse({}, false)));
  const oldRequest = vm.runInContext('submitPrediction()', h.context);
  h.elements.gene_name.value = 'G6PD';
  const newRequest = vm.runInContext('submitPrediction()', h.context);
  pending[0](jsonResponse(prediction));
  await oldRequest;
  assert.equal(h.button.disabled, true);
  assert.equal(h.elements['result-body'].classList.contains('hidden'), true);
  pending[1](jsonResponse({...prediction,tier:'benign',color:'low',probability:4}));
  await newRequest;
  assert.match(h.elements['prob-label'].textContent, /^4%/);
  assert.equal(h.button.disabled, false);
});

test('changed input invalidates an in-flight result even when a response ignores cancellation', async () => {
  let release;
  const h = harness(url => url === '/api/predict'
    ? new Promise(resolve => { release = resolve; })
    : Promise.resolve(jsonResponse({}, false)));
  const request = vm.runInContext('submitPrediction()', h.context);
  h.elements.gene_name.value = 'G6PD';
  release(jsonResponse(prediction));
  await request;
  assert.equal(h.elements['result-body'].classList.contains('hidden'), true);
  assert.match(h.elements['result-empty'].textContent, /Inputs changed/);
  assert.equal(h.button.disabled, false);
});

function residueViewer() {
  const labels = [];
  const zooms = [];
  const atoms = [{chain:'B',resi:6,atom:'CA',x:1,y:2,z:3}];
  return {
    labels, zooms,
    clear() {}, render() {}, addModel() {}, zoom() {}, setStyle() {},
    selectedAtoms(selection) {
      return atoms.filter(atom => Object.entries(selection).every(([key,value]) => atom[key] === value));
    },
    removeAllLabels() { labels.length = 0; },
    addLabel(text) { labels.push(text); },
    zoomTo(selection) { zooms.push(selection); },
  };
}

test('clearing a residue removes its highlight and missing or fractional residues are not highlighted', async () => {
  const viewer = residueViewer();
  const h = harness(async () => jsonResponse({}, false), viewer);
  await vm.runInContext('initViewer()', h.context);
  vm.runInContext('state.currentChain = "B"', h.context);
  h.elements.residue_number.value = '6';
  vm.runInContext('readManualResidue()', h.context);
  assert.equal(vm.runInContext('state.currentResidue.pos', h.context), 6);
  assert.equal(viewer.labels.length, 1);
  const zoomCount = viewer.zooms.length;
  h.elements.residue_number.value = '';
  vm.runInContext('readManualResidue()', h.context);
  assert.equal(vm.runInContext('state.currentResidue', h.context), null);
  assert.equal(viewer.labels.length, 0);
  assert.equal(h.elements['btn-zoom-residue'].classList.contains('hidden'), true);
  h.elements.residue_number.value = '999999';
  vm.runInContext('readManualResidue()', h.context);
  assert.equal(vm.runInContext('state.currentResidue', h.context), null);
  assert.match(h.elements['residue-readout'].textContent, /not present in chain B/);
  h.elements.residue_number.value = '1.5';
  vm.runInContext('readManualResidue()', h.context);
  assert.match(h.elements['residue-readout'].textContent, /whole-number residue/);
  assert.equal(viewer.zooms.length, zoomCount);
});

test('a residue entered before the viewer loads is highlighted when the structure becomes available', async () => {
  const viewer = residueViewer();
  const h = harness(async url => {
    if (url === '/api/model-info') return jsonResponse({demo_mode:false,data_provenance:'real'});
    if (url === '/api/structure/HBB') return jsonResponse({pdb_id:'2HHB',chain:'B',source:'experimental',label:'Hemoglobin'});
    if (url === 'https://files.rcsb.org/download/2HHB.pdb') return {ok:true,text:async () => 'Hemoglobin fixture'};
    return jsonResponse({}, false);
  }, viewer);
  h.elements.residue_number.value = '6';
  vm.runInContext('readManualResidue()', h.context);
  assert.equal(vm.runInContext('state.currentResidue', h.context), null);
  h.document.events.DOMContentLoaded();
  await flush();
  assert.equal(h.elements.residue_number.value, '6');
  assert.equal(vm.runInContext('state.currentResidue.pos', h.context), 6);
  assert.match(h.elements['residue-readout'].innerHTML, /manually selected residue 6/);
  assert.equal(viewer.labels.length, 1);
});

test('a preset cannot restore a residue the user cleared while its structure was loading', async () => {
  let releaseStructure;
  const viewer = residueViewer();
  const h = harness(async url => {
    if (url === '/api/structure/HBB') return jsonResponse({pdb_id:'2HHB',chain:'B',source:'experimental',label:'Hemoglobin'});
    if (url === 'https://files.rcsb.org/download/2HHB.pdb') {
      return new Promise(resolve => { releaseStructure = resolve; });
    }
    if (url === '/api/predict') return jsonResponse(prediction);
    return jsonResponse({}, false);
  }, viewer);
  await vm.runInContext('initViewer()', h.context);
  vm.runInContext('applyExample("hbb-high-cadd")', h.context);
  await flush();
  assert.equal(h.elements.residue_number.value, 6);
  h.elements.residue_number.value = '';
  vm.runInContext('readManualResidue()', h.context);
  releaseStructure({ok:true,text:async () => 'Hemoglobin fixture'});
  await flush();
  assert.equal(vm.runInContext('state.currentResidue', h.context), null);
  assert.equal(viewer.labels.length, 0);
  assert.equal(h.elements['btn-zoom-residue'].classList.contains('hidden'), true);
});
