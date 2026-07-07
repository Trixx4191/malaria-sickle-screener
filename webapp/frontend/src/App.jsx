import { useMemo, useState } from 'react';
import { Canvas, useFrame } from '@react-three/fiber';
import { Float, Stars, Html, PerspectiveCamera } from '@react-three/drei';
import { motion } from 'framer-motion';
import { Sparkles, Radar, ShieldCheck, Activity } from 'lucide-react';
import * as THREE from 'three';

const REGION_LABELS = {
  'Exonic (coding)': 'Exonic (coding)',
  'UTR (untranslated)': 'UTR (untranslated)',
  'Intronic / other': 'Intronic / other',
};

const REGION_VALUE = {
  'Exonic (coding)': 2,
  'UTR (untranslated)': 1,
  'Intronic / other': 0,
};

const TIER_COLORS = {
  high: '#c4432e',
  medium: '#d9a62e',
  low: '#21a190',
  default: '#4e6570',
};

function HelixScene({ tier, regionValue }) {
  const rungCount = 24;
  const strandRadius = 1.35;
  const points = useMemo(() => {
    const pts = [];
    for (let i = 0; i <= 220; i++) {
      const t = i / 220;
      const angle = t * Math.PI * 5.6;
      const y = (t - 0.5) * 4.5;
      pts.push(new THREE.Vector3(Math.cos(angle) * strandRadius, y, Math.sin(angle) * strandRadius));
    }
    return pts;
  }, []);

  const rungPositions = useMemo(() => {
    return Array.from({ length: rungCount }, (_, i) => {
      const t = (i + 0.5) / rungCount;
      const angle = t * Math.PI * 5.6;
      const y = (t - 0.5) * 4.5;
      const a = new THREE.Vector3(Math.cos(angle) * strandRadius, y, Math.sin(angle) * strandRadius);
      const b = new THREE.Vector3(Math.cos(angle + Math.PI) * strandRadius, y, Math.sin(angle + Math.PI) * strandRadius);
      return { a, b, mid: new THREE.Vector3().copy(a).add(b).multiplyScalar(0.5) };
    });
  }, []);

  const highlightIndex = useMemo(() => Math.min(rungCount - 1, Math.floor((REGION_VALUE[regionValue] ?? 0.4) * rungCount)), [regionValue]);

  const color = TIER_COLORS[tier] || TIER_COLORS.default;

  useFrame((state, delta) => {
    state.camera.position.x = Math.sin(state.clock.elapsedTime * 0.22) * 6.4;
    state.camera.position.z = Math.cos(state.clock.elapsedTime * 0.22) * 8.2;
    state.camera.position.y = 0.4 + Math.sin(state.clock.elapsedTime * 0.18) * 0.8;
    state.camera.lookAt(0, 0, 0);
  });

  return (
    <>
      <PerspectiveCamera makeDefault position={[0, 0.3, 8.4]} fov={34} />
      <ambientLight intensity={0.5} />
      <pointLight position={[5, 3, 5]} intensity={2.3} color="#31d7c6" />
      <pointLight position={[-6, -2, -4]} intensity={1.6} color="#f2b84b" />
      <Float speed={1.2} rotationIntensity={0.15} floatIntensity={0.25}>
        <mesh rotation={[1.1, 0.65, 0.1]}>
          <torusKnotGeometry args={[0.9, 0.15, 220, 18]} />
          <meshBasicMaterial color="#f8d36a" transparent opacity={0.15} />
        </mesh>
      </Float>
      <group>
        {[0, Math.PI].map((offset, idx) => {
          const curve = new THREE.CatmullRomCurve3(points.map((p, i) => new THREE.Vector3(p.x * (idx === 1 ? 1 : 1), p.y, p.z)));
          const geometry = new THREE.TubeGeometry(curve, 260, 0.034, 12, false);
          return (
            <mesh key={idx} geometry={geometry}>
              <meshPhysicalMaterial
                color={idx === 0 ? '#111b21' : '#22b39b'}
                emissive={idx === 0 ? '#111b21' : '#4be0be'}
                emissiveIntensity={idx === 0 ? 0.2 : 0.35}
                roughness={0.24}
                metalness={0.45}
                transparent
                opacity={0.95}
              />
            </mesh>
          );
        })}
        {rungPositions.map((rung, i) => {
          const dist = rung.a.distanceTo(rung.b);
          const geometry = new THREE.CylinderGeometry(0.02, 0.02, dist, 12);
          return (
            <mesh key={i} geometry={geometry} position={rung.mid}>
              <meshStandardMaterial
                color={i === highlightIndex ? '#f2c13d' : color}
                emissive={i === highlightIndex ? '#f2c13d' : color}
                emissiveIntensity={i === highlightIndex ? 1.0 : 0.24}
                roughness={0.35}
                metalness={0.2}
              />
              <primitive object={new THREE.Mesh(geometry)} />
            </mesh>
          );
        })}
      </group>
      <Stars radius={90} depth={40} count={1400} factor={4} saturation={0} fade speed={1.4} />
      <Html center position={[0, -3.2, 0]}>
        <div className="helix-legend">{tier ? `Signal intensity · ${tier}` : 'Ready for inference'}</div>
      </Html>
    </>
  );
}

function App() {
  const [form, setForm] = useState({
    allele_freq_afr: 0.01,
    cadd_score: 15,
    gene_region: 'Exonic (coding)',
    conservation_phylop: 0.5,
    gene_name: 'HBB',
  });
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [tier, setTier] = useState('default');

  const handlePredict = async () => {
    setLoading(true);
    try {
      const res = await fetch('/api/predict', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          ...form,
          gene_region: REGION_LABELS[form.gene_region],
        }),
      });
      const data = await res.json();
      setResult(data);
      setTier(data.tier || 'default');
    } catch (error) {
      setResult({ label: 'Request failed', tier: 'default', probability: 0, interpretation: ['The prediction service could not be reached.'] });
      setTier('default');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="app-shell">
      <motion.header className="hero-panel" initial={{ opacity: 0, y: 24 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.45 }}>
        <div className="hero-copy">
          <div className="eyebrow"><Sparkles size={16} /> cinematic variant intelligence</div>
          <h1>Pathogenicity, modeled like a cinematic signal map.</h1>
          <p>We fuse African ancestry-aware features, clinical strength, and a real-time 3D helix to make variant interpretation feel immediate, precise, and beautiful.</p>
          <div className="metrics-row">
            <div><strong>0.87</strong><span>AUC · AFR cohort</span></div>
            <div><strong>0.91</strong><span>AUC · HBB</span></div>
            <div><strong>Accra</strong><span>Built in Ghana</span></div>
          </div>
        </div>
        <div className="hero-visual">
          <div className="canvas-shell">
            <Canvas shadows>
              <HelixScene tier={tier} regionValue={form.gene_region} />
            </Canvas>
          </div>
        </div>
      </motion.header>

      <main className="control-grid">
        <motion.section className="panel" initial={{ opacity: 0, y: 24 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5, delay: 0.05 }}>
          <div className="panel-title">
            <h2>Variant requisition</h2>
            <span>01 / input</span>
          </div>

          <label className="field">
            <span>AFR allele frequency</span>
            <input type="range" min="0" max="1" step="0.001" value={form.allele_freq_afr} onChange={(e) => setForm({ ...form, allele_freq_afr: Number(e.target.value) })} />
            <small>{form.allele_freq_afr.toFixed(3)}</small>
          </label>

          <label className="field">
            <span>CADD Phred score</span>
            <input type="range" min="0" max="60" step="0.5" value={form.cadd_score} onChange={(e) => setForm({ ...form, cadd_score: Number(e.target.value) })} />
            <small>{form.cadd_score.toFixed(1)}</small>
          </label>

          <div className="field">
            <span>Gene region</span>
            <div className="segmented">
              {Object.keys(REGION_LABELS).map((key) => (
                <button key={key} className={form.gene_region === key ? 'active' : ''} onClick={() => setForm({ ...form, gene_region: key })}>{key === 'Exonic (coding)' ? 'Exonic' : key === 'UTR (untranslated)' ? 'UTR' : 'Intronic'}</button>
              ))}
            </div>
          </div>

          <label className="field">
            <span>Conservation (phyloP)</span>
            <input type="range" min="-3" max="3" step="0.1" value={form.conservation_phylop} onChange={(e) => setForm({ ...form, conservation_phylop: Number(e.target.value) })} />
            <small>{form.conservation_phylop.toFixed(1)}</small>
          </label>

          <label className="field">
            <span>Gene symbol</span>
            <input className="text-input" value={form.gene_name} onChange={(e) => setForm({ ...form, gene_name: e.target.value })} />
          </label>

          <button className="predict-btn" onClick={handlePredict} disabled={loading}>
            {loading ? 'Scanning…' : 'Predict pathogenicity →'}
          </button>
        </motion.section>

        <motion.section className="panel" initial={{ opacity: 0, y: 24 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5, delay: 0.1 }}>
          <div className="panel-title">
            <h2>Prediction</h2>
            <span>02 / result</span>
          </div>
          {result ? (
            <div className="result-card">
              <div className={`result-badge ${result.tier || 'default'}`}>
                <ShieldCheck size={16} />
                {result.label}
              </div>
              <div className="probability">{result.probability}% <small>pathogenic probability</small></div>
              <ul>
                {(result.interpretation || []).map((line) => <li key={line}>{line}</li>)}
              </ul>
              <div className="result-footer">
                <div><Radar size={14} /> {form.gene_name}</div>
                <div><Activity size={14} /> {form.gene_region}</div>
              </div>
            </div>
          ) : (
            <div className="empty-state">Set the parameters and let the system run a cinematic inference.</div>
          )}
        </motion.section>
      </main>
    </div>
  );
}

export default App;
