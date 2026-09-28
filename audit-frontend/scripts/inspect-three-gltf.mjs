import { readFile } from 'node:fs/promises';

globalThis.ProgressEvent ??= class ProgressEvent { constructor(type, init = {}) { this.type = type; Object.assign(this, init) } };
const THREE = await import('three');
const { GLTFLoader } = await import('three/examples/jsm/loaders/GLTFLoader.js');

const modelPath = process.argv[2];
const bytes = await readFile(modelPath);
const buffer = bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength);

const gltf = await new Promise((resolve, reject) => new GLTFLoader().parse(buffer, '', resolve, reject));

console.log("=== GLTFLoader Parsed Output ===");
gltf.scene.traverse((child) => {
  if (child.isMesh) {
    console.log("Mesh name:", child.name);
    console.log("Geometry attributes:", Object.keys(child.geometry.attributes));
    const colorAttr = child.geometry.getAttribute('color');
    if (colorAttr) {
      console.log("Color attribute itemSize:", colorAttr.itemSize, "count:", colorAttr.count);
      console.log("First 3 color tuples:", [
        colorAttr.getX(0), colorAttr.getY(0), colorAttr.getZ(0),
        colorAttr.getX(1), colorAttr.getY(1), colorAttr.getZ(1),
        colorAttr.getX(2), colorAttr.getY(2), colorAttr.getZ(2)
      ]);
    } else {
      console.log("NO COLOR ATTRIBUTE FOUND!");
    }
    
    console.log("Material type:", child.material.type);
    console.log("Material vertexColors:", child.material.vertexColors);
    console.log("Material color:", child.material.color?.getHexString());
    console.log("Material roughness:", child.material.roughness);
    console.log("Material metalness:", child.material.metalness);
    console.log("Material side:", child.material.side);
  }
});
