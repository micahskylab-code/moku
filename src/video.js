// Deterministic camera timeline for rendered films. The page exposes window.renderFrame(i);
// scripts/video.mjs steps through the frames and encodes them.
//
// "night": from the lower lawn below the infinity edge, push slowly across the glowing pool
// toward the lit house, then crane up and tilt to Na Hiku (the Big Dipper) rising over the roof
// in the north-north-east, as it does from Kukui'ula on a March evening.
import * as THREE from 'three';

const ease = t => t * t * (3 - 2 * t);
const lerp = (a, b, t) => a + (b - a) * t;

// The night camera path alone (no DOM), shared by the film and by the Blender exporter.
export function nightCameraPath(camera, nightSky, terrainH) {
  const c = nightSky?.center ?? new THREE.Vector3(0.7, 0.55, 0.45).normalize();
  const starYaw = Math.atan2(c.z, c.x), starPitch = Math.asin(c.y);
  const house = new THREE.Vector3(14, 7, 20);
  return t => {
    const m = ease(Math.min(1, t / 0.6));
    const p = new THREE.Vector3(lerp(-64, -48, m), 0, lerp(8, 15, m));
    p.y = terrainH(p.x, p.z) + lerp(5.5, 12.5, ease(Math.max(0, (t - 0.3) / 0.7)));
    const toHouse = house.clone().sub(p);
    const houseYaw = Math.atan2(toHouse.z, toHouse.x), housePitch = Math.atan2(toHouse.y, Math.hypot(toHouse.x, toHouse.z));
    const k = ease(Math.max(0, Math.min(1, (t - 0.3) / 0.55)));
    const yaw = lerp(houseYaw, starYaw - 0.04, k), pitch = lerp(housePitch + 0.02, starPitch - 0.2, k);
    const dir = new THREE.Vector3(Math.cos(pitch) * Math.cos(yaw), Math.sin(pitch), Math.cos(pitch) * Math.sin(yaw));
    camera.position.copy(p);
    camera.lookAt(p.clone().add(dir));
  };
}

export async function runVideo({ params, camera, render, nightSky, terrainH }) {
  const fps = Number(params.get('fps') ?? 24), seconds = Number(params.get('seconds') ?? 18);
  const frames = Math.round(fps * seconds);
  camera.fov = 58; camera.updateProjectionMatrix();
  const caption = document.getElementById('caption');
  caption.innerHTML = 'N&#256; HIKU<small>the seven stars over Kukui&#699;ula</small>';

  // where Na Hiku sits, as yaw (from +x toward +z) and pitch
  const c = nightSky?.center ?? new THREE.Vector3(0.7, 0.55, 0.45).normalize();
  const starYaw = Math.atan2(c.z, c.x), starPitch = Math.asin(c.y);
  const house = new THREE.Vector3(14, 7, 20);

  const move = nightCameraPath(camera, nightSky, terrainH);
  const shot = t => {
    move(t);
    // reveal
    if (nightSky) {
      nightSky.lines.material.opacity = 0.32 * ease(Math.max(0, Math.min(1, (t - 0.74) / 0.14)));
      nightSky.starMat.uniforms.uTwinkle.value = t * seconds;
    }
    caption.style.opacity = String(ease(Math.max(0, Math.min(1, (t - 0.8) / 0.12))));
  };

  window.__frames = frames;
  window.renderFrame = i => { shot(i / Math.max(1, frames - 1)); render(); return true; };
  window.renderFrame(Number(params.get('frame') ?? 0));
  document.body.dataset.ready = '1';
}
