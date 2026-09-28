// Local integration check: parse a produced GLB with the same Three.js loader
// used by Photo3DPage. This does not publish or hard-code an experiment artifact.
import { readFile } from 'node:fs/promises'
// Three's FileLoader reports progress in browsers. Node has no ProgressEvent,
// so provide the minimal testing-only shape before dynamically loading Three.
globalThis.ProgressEvent ??= class ProgressEvent { constructor(type, init = {}) { this.type = type; Object.assign(this, init) } }
const { GLTFLoader } = await import('three/examples/jsm/loaders/GLTFLoader.js')

const modelPath = process.argv[2]
if (!modelPath) throw new Error('Usage: node scripts/validate-glb.mjs <model.glb>')
const bytes = await readFile(modelPath)
const buffer = bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength)
const gltf = await new Promise((resolve, reject) => new GLTFLoader().parse(buffer, '', resolve, reject))
let meshes = 0
let vertices = 0
gltf.scene.traverse((node) => {
  if (node.isMesh) {
    meshes += 1
    vertices += node.geometry.getAttribute('position')?.count || 0
  }
})
if (!meshes || !vertices) throw new Error('GLTFLoader parsed no renderable mesh geometry.')
console.log(JSON.stringify({ renderedBy: 'GLTFLoader', meshes, vertices }))
