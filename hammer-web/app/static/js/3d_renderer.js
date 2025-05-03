import {
  AmbientLight,
  DirectionalLight,
  Vector3,
  WebGLRenderer,
  PerspectiveCamera,
  Scene
} from 'three';
import { MTLLoader } from 'mtl-loader';
import { OBJLoader } from 'obj-loader';
import { OrbitControls } from 'orbit-controls';
import { update } from 'tween';

const MaxRenderDistanceDefault = 1000;
const MinRenderDistanceDefault = 0.1;

const containerWidth = (container) => {
  return container.parentElement.clientWidth;
};

const containerHeight = (container) => {
  return container.parentElement.clientHeight;
};

const addLightsToScene = (scene, camera, useDynamicLighting) => {
  if (useDynamicLighting) {
    const ambient = new AmbientLight(0x444444);
    camera.add(ambient);

    const keylight = new DirectionalLight(0xd4d4d4);
    keylight.target = camera;
    keylight.position.set(-7.5, 0.5, -6.0).normalize();
    camera.add(keylight);

    const fillLight = new DirectionalLight(0xacacac);
    fillLight.target = camera;
    fillLight.position.set(20.0, 4.0, -0).normalize();
    camera.add(fillLight);

    const rimLight = new DirectionalLight(0xacacac);
    rimLight.target = camera;
    rimLight.position.set(0, 1, 1).normalize();
    camera.add(rimLight);
  } else {
    const ambient = new AmbientLight(0x878780);
    scene.add(ambient);

    const sunLight = new DirectionalLight(0xacacac);
    sunLight.position.set(-0.671597898, 0.671597898, 0.312909544).normalize();
    scene.add(sunLight);

    const backLight = new DirectionalLight(0x444444);
    const backLightPos = new Vector3()
      .copy(sunLight.position)
      .negate()
      .normalize(); // inverse of sun direction
    backLight.position.set(backLightPos);
    scene.add(backLight);
  }

  return {
    scene,
    camera
  };
};

const render = (renderer, scene, camera) => {
  renderer.render(scene, camera);
};

const animate = (
  controls,
  renderer,
  scene,
  camera
) => {
  if (controls.enabled) {
    controls.update();
  }

  update();
  render(renderer, scene, camera);
  const handleid = requestAnimationFrame(() => animate(controls, renderer, scene, camera));
  return handleid;
};

const initializeControls = (
  renderer,
  scene,
  camera,
  container,
  json
) => {
  const orbitControls = new OrbitControls(camera, container, json, 'static');

  orbitControls.rotateSpeed = 1.5;
  orbitControls.zoomSpeed = 1.5;
  orbitControls.dampingFactor = 0.3;
  orbitControls.addEventListener('change', () => render(renderer, scene, camera));
  return orbitControls;
};

const createCanvas = (renderer, container, camera, is_square) => {
  const setRendererSize = () => {
    camera.aspect = is_square ? 1 : (containerWidth(container) / containerHeight(container));
    camera.updateProjectionMatrix();
    renderer.setSize(containerWidth(container), is_square ? containerWidth(container) : containerHeight(container));
  };

  renderer.setSize(containerWidth(container), containerHeight(container));
  const canvas = renderer.domElement;
  container.appendChild(canvas);
  let resizeTimer = 0;
  window.addEventListener('resize', () => {
    clearTimeout(resizeTimer);
    resizeTimer = setTimeout(setRendererSize, 100);
  });
  window.addEventListener('beforeunload', () => {
    canvas.style.display = 'none';
  });
  return canvas;
};

async function initContainer( container_elem, cache_hash = null, is_square = false ) {
  const render_type = container_elem.getAttribute('data-render-type');
  if (render_type === null) {
    console.error('Hammer Renderer > Missing required attributes on container element.');
    return;
  }
  var fetch_obj_url = null;
  if (render_type === 'user_avatar') {
    var user_id = container_elem.getAttribute('data-user-id');
    fetch_obj_url = `${await HammerLib.get_endpoint('user_3d_avatar_thumb')}?userId=${user_id}&cacheHash=${cache_hash}`;
  } else {
    console.error('Hammer Renderer > Unknown render type.');
    return;
  }

  if (container_elem.getAttribute('data-renderer-initialized') === 'true') {
    return;
  }
  container_elem.setAttribute('data-renderer-initialized', 'true');

  const obj_metadata_location_response = await fetch(fetch_obj_url);
  if (obj_metadata_location_response.status !== 200) {
    console.error('Hammer Renderer > Failed to fetch object metadata.');
    return;
  }
  
  const obj_metadata_location = await obj_metadata_location_response.json();
  const obj_metadata_url = obj_metadata_location.imageUrl;
  const obj_metadata = await fetch(obj_metadata_url);
  if (obj_metadata.status !== 200) {
    console.error('Hammer Renderer > Failed to fetch object metadata.');
    return;
  }
  const obj_metadata_json = await obj_metadata.json();

  const calculatedMaxRenderDistance = new Vector3(obj_metadata_json.aabb.max.x, obj_metadata_json.aabb.max.y, obj_metadata_json.aabb.max.z).length() * 4;
  const maxRenderDistance = Math.max(calculatedMaxRenderDistance, MaxRenderDistanceDefault);
  const fieldOfView = typeof obj_metadata_json.camera.fov !== 'undefined' ? obj_metadata_json.camera.fov : 70;

  const renderer = new WebGLRenderer({ antialias: true, alpha: true });

  const camera = new PerspectiveCamera(
    fieldOfView,
    is_square ? 1 : (containerWidth(container_elem) / containerHeight(container_elem)),
    MinRenderDistanceDefault,
    maxRenderDistance
  );

  const scene = new Scene();
  const mtlLoader = new MTLLoader();
  const objLoader = new OBJLoader();

  const CDNUrl = await HammerLib.get_endpoint('cdn_url')

  return new Promise((resolve, reject) => {
    const objAndMtlLoaded = (modelObject) => {
      addLightsToScene(scene, camera, true);
      scene.add(camera);
      scene.add(modelObject);

      const canvas = createCanvas(renderer, container_elem, camera, is_square);

      var controls = initializeControls(renderer, scene, camera, container_elem, obj_metadata_json);
      render(renderer, scene, camera);
      const callback_handleid = animate(controls, renderer, scene, camera);
      const observer = new MutationObserver((mutations) => {
        mutations.forEach((mutation) => {
          if (mutation.type === 'childList' && mutation.removedNodes.length > 0) {
            console.log('Hammer Renderer > Container removed from DOM. Stopping rendering loop.');
            cancelAnimationFrame(callback_handleid);
            observer.disconnect();
          }
        });
      });
      
      resolve(canvas);
    };

    mtlLoader.load(`${CDNUrl}/${obj_metadata_json.mtl}`, (materials) => {
      materials.preload();
      objLoader
        .setMaterials(materials)
        .load(`${CDNUrl}/${obj_metadata_json.obj}`, objAndMtlLoaded, undefined, reject);
    }, undefined, reject);
  });
}

export { initContainer };